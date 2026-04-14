/**
 * Hermes Bridge Lifecycle Manager
 *
 * 管理 Python bridge-server.py 子进程的完整生命周期：
 * - 自动检测 Python 环境是否可用
 * - 启动/停止/重启 bridge 子进程
 * - 健康检查与自动恢复
 * - 进程 PID 持久化（避免重复启动）
 */

import { spawn, execSync } from "node:child_process";
import type { ChildProcess } from "node:child_process";
import { readFile, writeFile, rm, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface HermesBridgeLifecycleOptions {
  /** Python 可执行文件路径（默认自动检测） */
  pythonPath?: string;
  /** bridge_server.py 所在目录 */
  bridgeDir?: string;
  /** hermes-agent 源码目录 */
  hermesAgentDir?: string;
  /** bridge 监听地址 */
  bridgeHost?: string;
  /** bridge 监听端口 */
  bridgePort?: number;
  /** PID 文件路径 */
  pidFilePath?: string;
  /** 启动后等待健康检查的毫秒数 */
  startupWaitMs?: number;
  /** 健康检查重试次数 */
  healthCheckRetries?: number;
}

export interface PythonEnvironmentInfo {
  available: boolean;
  path?: string;
  version?: string;
  error?: string;
}

interface PersistedBridgeState {
  pid: number;
  startedAt: string;
  pythonPath: string;
  bridgePort: number;
}

// ---------------------------------------------------------------------------
// Default Values
// ---------------------------------------------------------------------------

const DEFAULT_BRIDGE_HOST = "127.0.0.1";
const DEFAULT_BRIDGE_PORT = 21747;
const DEFAULT_STARTUP_WAIT_MS = 3000;
const DEFAULT_HEALTH_RETRIES = 5;

// ---------------------------------------------------------------------------
// Python Environment Detection
// ---------------------------------------------------------------------------

/**
 * 检测本机 Python 3.11+ 环境是否可用。
 * 按优先级依次尝试：python3、python
 */
export function detectPythonEnvironment(preferredPath?: string): PythonEnvironmentInfo {
  const candidates = preferredPath
    ? [preferredPath]
    : ["python3", "python"];

  for (const cmd of candidates) {
    try {
      const version = execSync(`${cmd} --version 2>&1`, {
        encoding: "utf8",
        timeout: 5000,
      }).trim();

      // 解析版本号：Python 3.11.x
      const match = version.match(/Python (\d+)\.(\d+)/);
      if (match) {
        const major = parseInt(match[1], 10);
        const minor = parseInt(match[2], 10);
        if (major >= 3 && minor >= 11) {
          // 获取完整路径
          let fullPath = cmd;
          try {
            fullPath = execSync(`which ${cmd} 2>/dev/null || where ${cmd} 2>nul`, {
              encoding: "utf8",
              timeout: 3000,
            }).trim().split("\n")[0];
          } catch {
            // 忽略，使用原始命令
          }

          return {
            available: true,
            path: fullPath,
            version,
          };
        } else {
          return {
            available: false,
            path: cmd,
            version,
            error:
              `Python version ${version} is too old. ` +
              `hermes-agent requires Python 3.11 or higher. ` +
              `Please upgrade: https://www.python.org/downloads/`,
          };
        }
      }
    } catch {
      // 此候选不可用，继续尝试下一个
    }
  }

  return {
    available: false,
    error:
      "Python 3.11+ is not installed or not in PATH. " +
      "hermes-agent requires Python 3.11 or higher. " +
      "Please install: https://www.python.org/downloads/",
  };
}

// ---------------------------------------------------------------------------
// Lifecycle Manager
// ---------------------------------------------------------------------------

export class HermesBridgeLifecycle {
  private readonly options: Required<HermesBridgeLifecycleOptions>;
  private childProcess: ChildProcess | null = null;
  private hudProcess: ChildProcess | null = null;
  private pythonEnv: PythonEnvironmentInfo | null = null;
  private intentionallyStopped: boolean = false;

  constructor(options: HermesBridgeLifecycleOptions = {}) {
    const sdkRoot = path.resolve(__dirname, "..", "..");
    this.options = {
      pythonPath: options.pythonPath ?? "",
      bridgeDir: options.bridgeDir ?? path.join(sdkRoot, "qeeclaw-hermes-bridge"),
      hermesAgentDir: options.hermesAgentDir ?? path.join(sdkRoot, "vendor", "hermes-agent"),
      bridgeHost: options.bridgeHost ?? DEFAULT_BRIDGE_HOST,
      bridgePort: options.bridgePort ?? DEFAULT_BRIDGE_PORT,
      pidFilePath: options.pidFilePath ?? path.join(sdkRoot, "qeeclaw-hermes-bridge", ".bridge-pid.json"),
      startupWaitMs: options.startupWaitMs ?? DEFAULT_STARTUP_WAIT_MS,
      healthCheckRetries: options.healthCheckRetries ?? DEFAULT_HEALTH_RETRIES,
    };
  }

  /** 检测 Python 环境 */
  detectPython(): PythonEnvironmentInfo {
    if (!this.pythonEnv) {
      this.pythonEnv = detectPythonEnvironment(this.options.pythonPath || undefined);
    }
    return this.pythonEnv;
  }

  /** 获取 bridge HTTP 地址 */
  getBridgeUrl(): string {
    return `http://${this.options.bridgeHost}:${this.options.bridgePort}`;
  }

  /** 启动 bridge 子进程 */
  async start(): Promise<void> {
    this.intentionallyStopped = false;

    // 在生产环境下（C/S分离架构），客户端不再试图管理服务端的生命周期
    const isPackaged = __dirname.includes('app.asar') || process.env.NODE_ENV === 'production';
    if (isPackaged) {
      process.stderr.write(
        `[hermes-lifecycle] Client-only production mode detected.\n` + 
        `[hermes-lifecycle] Bridge lifecycle management is disabled. Relying on remote QeeClaw Server.\n`
      );
      return;
    }

    // 1. 检查是否已有运行的进程
    const existing = await this.getPersistedState();
    if (existing && this.isProcessAlive(existing.pid)) {
      process.stderr.write(
        `[hermes-lifecycle] Bridge already running at PID ${existing.pid}\n`,
      );
      return;
    }

    // 2. 检测 Python 环境
    const pyEnv = this.detectPython();
    if (!pyEnv.available || !pyEnv.path) {
      throw new Error(
        `Cannot start Hermes bridge: ${pyEnv.error ?? "Python not found."}`,
      );
    }

    // 3. 检查 bridge_server.py 是否存在
    const bridgeScript = path.join(this.options.bridgeDir, "bridge_server.py");
    if (!existsSync(bridgeScript)) {
      throw new Error(
        `Bridge server script not found: ${bridgeScript}. ` +
        `Ensure the qeeclaw-hermes-bridge package is properly installed.`,
      );
    }

    // 4. 构建子进程环境变量（包括凭证传递）
    const { collectExistingCredentialEnvVars } = await import("./credential-map.js");
    const credentialEnv = collectExistingCredentialEnvVars(
      process.env as Record<string, string | undefined>,
    );

    const env: Record<string, string> = {
      ...(process.env as Record<string, string>),
      ...credentialEnv,
      QEECLAW_HERMES_BRIDGE_HOST: this.options.bridgeHost,
      QEECLAW_HERMES_BRIDGE_PORT: String(this.options.bridgePort),
      QEECLAW_HERMES_AGENT_DIR: this.options.hermesAgentDir,
    };

    const child = spawn(pyEnv.path, [bridgeScript], {
      env,
      stdio: ["ignore", "pipe", "pipe"],
      detached: false,
    });

    this.childProcess = child;

    // 转发 stderr 日志并脱敏
    child.stderr?.on("data", (data: Buffer) => {
      let text = data.toString();
      // Masking basic app keys / tokens
      text = text.replace(/([a-zA-Z0-9_\-]{8})[a-zA-Z0-9_\-]{16,}/g, "$1****");
      process.stderr.write(text);
    });

    child.on("exit", (code, signal) => {
      process.stderr.write(
        `[hermes-lifecycle] Bridge process exited (code: ${code}, signal: ${signal})\n`,
      );
      this.childProcess = null;

      // Watchdog 自动拉起
      if (!this.intentionallyStopped) {
        process.stderr.write(`[hermes-lifecycle] Unexpected exit, applying watchdog restart in 3s...\n`);
        setTimeout(() => {
          this.start().catch((err) => {
            process.stderr.write(`[hermes-lifecycle] Watchdog failed to restart bridge: ${err}\n`);
          });
        }, 3000);
      }
    });

    // 5. 拉起 HUD Dashboard 微服务
    const hudDir = path.join(__dirname, "..", "..", "vendor", "hermes-hudui");
    if (existsSync(path.join(hudDir, "backend", "main.py"))) {
      const hudEnv: Record<string, string> = {
        ...env,
        HERMES_HOME: this.options.hermesAgentDir,
      };
      
      const hud = spawn(pyEnv.path, ["-m", "backend.main", "--port", "8134"], {
        cwd: hudDir,
        env: hudEnv,
        stdio: ["ignore", "pipe", "pipe"],
        detached: false,
      });

      this.hudProcess = hud;

      hud.stderr?.on("data", (data: Buffer) => {
        let text = data.toString();
        // Masking basic keys doesn't usually apply to HUD but safe guard
        text = text.replace(/([a-zA-Z0-9_\-]{8})[a-zA-Z0-9_\-]{16,}/g, "$1****");
        process.stderr.write(`[hudui] ${text}`);
      });

      hud.on("exit", (code) => {
        process.stderr.write(`[hudui] HUD process exited (code: ${code})\n`);
        this.hudProcess = null;
        if (!this.intentionallyStopped) {
           process.stderr.write(`[hudui] Watchdog restart in 5s...\n`);
           setTimeout(() => { if (!this.intentionallyStopped) this.start().catch(()=>{}); }, 5000);
        }
      });
    }

    // 6. 持久化 PID
    await this.persistState({
      pid: child.pid ?? -1,
      startedAt: new Date().toISOString(),
      pythonPath: pyEnv.path,
      bridgePort: this.options.bridgePort,
    });

    // 6. 等待健康检查通过
    await this.waitForReady();
  }

  /** 停止 bridge 子进程 */
  async stop(): Promise<void> {
    this.intentionallyStopped = true;

    if (this.childProcess) {
      this.childProcess.kill("SIGTERM");
      this.childProcess = null;
    }

    if (this.hudProcess) {
       this.hudProcess.kill("SIGTERM");
       this.hudProcess = null;
    }

    // 也检查持久化的 PID
    const state = await this.getPersistedState();
    if (state?.pid && this.isProcessAlive(state.pid)) {
      try {
        process.kill(state.pid, "SIGTERM");
      } catch {
        // 进程可能已退出
      }
    }

    await this.clearPersistedState();
  }

  /** 重启 */
  async restart(): Promise<void> {
    await this.stop();
    // 短暂等待端口释放
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await this.start();
  }

  /** 健康检查 */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.getBridgeUrl()}/health`, {
        signal: AbortSignal.timeout(3000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  // ----- 内部方法 -----

  private async waitForReady(): Promise<void> {
    const retries = this.options.healthCheckRetries;
    const interval = this.options.startupWaitMs / retries;

    for (let i = 0; i < retries; i++) {
      await new Promise((resolve) => setTimeout(resolve, interval));
      if (await this.healthCheck()) {
        process.stderr.write(
          `[hermes-lifecycle] Bridge is ready at ${this.getBridgeUrl()}\n`,
        );
        return;
      }
    }

    throw new Error(
      `Hermes bridge failed to start within ${this.options.startupWaitMs}ms. ` +
      `Check Python installation and bridge logs.`,
    );
  }

  private isProcessAlive(pid: number): boolean {
    try {
      process.kill(pid, 0);
      return true;
    } catch {
      return false;
    }
  }

  private async getPersistedState(): Promise<PersistedBridgeState | null> {
    try {
      const raw = await readFile(this.options.pidFilePath, "utf8");
      return JSON.parse(raw) as PersistedBridgeState;
    } catch {
      return null;
    }
  }

  private async persistState(state: PersistedBridgeState): Promise<void> {
    await mkdir(path.dirname(this.options.pidFilePath), { recursive: true });
    await writeFile(this.options.pidFilePath, JSON.stringify(state, null, 2));
  }

  private async clearPersistedState(): Promise<void> {
    await rm(this.options.pidFilePath, { force: true });
  }
}

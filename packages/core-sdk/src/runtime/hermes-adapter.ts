/**
 * HermesAdapter — Hermes Agent Runtime 适配器（默认 Runtime）
 *
 * 通过 HTTP 与本地 Python 桥接服务 (bridge-server.py) 通信，
 * 调用 hermes-agent 的 AIAgent 核心。
 *
 * 集成 HermesBridgeLifecycle 实现自动启动 Python 子进程。
 */

import type {
  RuntimeAdapter,
  RuntimeCapabilities,
  RuntimeHealthCheck,
  RuntimeInvokeRequest,
  RuntimeInvokeResult,
  RuntimeStreamChunk,
  RuntimeGatewayStatus,
  GatewaySupportedPlatform,
  GatewayConfiguredPlatform,
  GatewayOperationResult,
  GatewayConfigureRequest,
} from "./types.js";
import { HermesBridgeLifecycle } from "./lifecycle.js";
import type { HermesBridgeLifecycleOptions } from "./lifecycle.js";

const DEFAULT_BRIDGE_URL = "http://127.0.0.1:21747";

export interface HermesAdapterOptions {
  /** Hermes bridge HTTP 服务的地址 */
  bridgeUrl?: string;
  /** Python 可执行文件路径（默认自动检测） */
  pythonPath?: string;
  /** hermes-agent 源码根目录 */
  hermesAgentDir?: string;
  /** bridge_server.py 所在目录 */
  bridgeDir?: string;
  /** 是否自动启动 bridge 子进程（默认 true） */
  autoStart?: boolean;
  /** 自定义 fetch 实现 */
  fetch?: typeof fetch;
}

export class HermesAdapter implements RuntimeAdapter {
  readonly type = "hermes" as const;
  private readonly bridgeUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly lifecycle: HermesBridgeLifecycle;
  private readonly autoStart: boolean;

  constructor(options: HermesAdapterOptions = {}) {
    this.bridgeUrl = (options.bridgeUrl ?? DEFAULT_BRIDGE_URL).replace(/\/+$/, "");
    this.fetchImpl = options.fetch ?? globalThis.fetch;
    this.autoStart = options.autoStart ?? true;

    // 从 bridgeUrl 中解析 host 和 port
    let host = "127.0.0.1";
    let port = 21747;
    try {
      const url = new URL(this.bridgeUrl);
      host = url.hostname;
      port = parseInt(url.port, 10) || 21747;
    } catch {
      // 使用默认值
    }

    const lifecycleOptions: HermesBridgeLifecycleOptions = {
      pythonPath: options.pythonPath,
      hermesAgentDir: options.hermesAgentDir,
      bridgeDir: options.bridgeDir,
      bridgeHost: host,
      bridgePort: port,
    };

    this.lifecycle = new HermesBridgeLifecycle(lifecycleOptions);
  }

  getCapabilities(): RuntimeCapabilities {
    return {
      supportsStreaming: true,
      supportsToolCalls: true,
      supportsMemory: true,
      supportsSkills: true,
      supportsGateway: true,
      supportedProviders: [
        "openrouter",
        "openai",
        "anthropic",
        "zhipu",      // z.ai / GLM
        "moonshot",   // Kimi
        "minimax",
        "nous-portal",
        "custom",     // 自定义 endpoint
      ],
    };
  }

  async healthCheck(): Promise<RuntimeHealthCheck> {
    try {
      const response = await this.fetchImpl(`${this.bridgeUrl}/health`, {
        method: "GET",
        signal: AbortSignal.timeout(5000),
      });

      if (!response.ok) {
        return {
          ok: false,
          runtimeType: "hermes",
          message: `Hermes bridge returned HTTP ${response.status}.`,
        };
      }

      const data = await response.json() as Record<string, unknown>;
      return {
        ok: true,
        runtimeType: "hermes",
        message: "Hermes Agent runtime is active.",
        version: typeof data.version === "string" ? data.version : undefined,
        details: data,
      };
    } catch (error) {
      // 检测 Python 环境，提供更有用的诊断信息
      const pyEnv = this.lifecycle.detectPython();
      const pythonHint = pyEnv.available
        ? `Python ${pyEnv.version} found at ${pyEnv.path}.`
        : `${pyEnv.error}`;

      return {
        ok: false,
        runtimeType: "hermes",
        message:
          `Hermes bridge is not reachable at ${this.bridgeUrl}. ` +
          pythonHint + " " +
          (error instanceof Error ? error.message : String(error)),
        details: {
          pythonAvailable: pyEnv.available,
          pythonPath: pyEnv.path,
          pythonVersion: pyEnv.version,
        },
      };
    }
  }

  async invoke(request: RuntimeInvokeRequest): Promise<RuntimeInvokeResult> {
    const timeoutMs = request.timeoutMs ?? 120_000;

    let response: Response;
    try {
      response = await this.fetchImpl(`${this.bridgeUrl}/invoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: request.prompt,
          model: request.model,
          provider: request.provider,
          max_tokens: request.maxTokens,
          temperature: request.temperature,
          system_prompt: request.systemPrompt,
        }),
        signal: AbortSignal.timeout(timeoutMs),
      });
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "TypeError") {
        throw new Error(`Hermes Bridge 连接失败 (可能服务未启动): ${this.bridgeUrl}`);
      }
      throw e;
    }

    if (!response.ok) {
      let text = "";
      try {
        const errJson = await response.json() as { error?: string };
        text = errJson.error || response.statusText;
      } catch {
        text = await response.text();
      }
      throw new Error(`Hermes 调用失败 [HTTP ${response.status}]: ${text}`);
    }

    const result = await response.json() as {
      text: string;
      model?: string;
      provider?: string;
      usage?: {
        prompt_tokens?: number;
        completion_tokens?: number;
        total_tokens?: number;
      };
    };

    return {
      text: result.text,
      model: result.model,
      provider: result.provider,
      usage: result.usage
        ? {
            promptTokens: result.usage.prompt_tokens,
            completionTokens: result.usage.completion_tokens,
            totalTokens: result.usage.total_tokens,
          }
        : undefined,
    };
  }

  async *invokeStream(request: RuntimeInvokeRequest): AsyncIterable<RuntimeStreamChunk> {
    const timeoutMs = request.timeoutMs ?? 120_000;

    let response: Response;
    try {
      response = await this.fetchImpl(`${this.bridgeUrl}/invoke/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          prompt: request.prompt,
          model: request.model,
          provider: request.provider,
          max_tokens: request.maxTokens,
          temperature: request.temperature,
          system_prompt: request.systemPrompt,
        }),
        signal: AbortSignal.timeout(timeoutMs),
      });
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "TypeError") {
        throw new Error(`Hermes Bridge 连接失败 (可能服务未启动): ${this.bridgeUrl}`);
      }
      throw e;
    }

    if (!response.ok || !response.body) {
      let text = "";
      try {
        const errJson = await response.json() as { error?: string };
        text = errJson.error || response.statusText;
      } catch {
        text = response.statusText;
      }
      throw new Error(`Hermes 流式请求失败 [HTTP ${response.status}]: ${text}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const dataStr = line.slice(6).trim();
          if (dataStr === "[DONE]") {
            yield { type: "done" };
            return;
          }
          try {
            const chunk = JSON.parse(dataStr) as RuntimeStreamChunk;
            yield chunk;
          } catch {
            // 非 JSON 数据行，跳过
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  async start(): Promise<void> {
    // 先检查 bridge 是否已经在运行
    const health = await this.healthCheck();
    if (health.ok) {
      return; // 已就绪，无需启动
    }

    // 如果开启了自动启动，尝试启动 bridge 子进程
    if (this.autoStart) {
      try {
        await this.lifecycle.start();
      } catch (error) {
        process.stderr?.write?.(
          `[hermes-adapter] Failed to auto-start bridge: ` +
          `${error instanceof Error ? error.message : String(error)}\n`,
        );
      }
    } else {
      process.stderr?.write?.(
        `[hermes-adapter] Bridge is not running and autoStart is disabled. ` +
        `Please start the bridge manually: python bridge_server.py\n`,
      );
    }
  }

  async stop(): Promise<void> {
    await this.lifecycle.stop();
  }

  // --------- Gateway 管理方法 ---------

  async getGatewayStatus(): Promise<RuntimeGatewayStatus> {
    try {
      const response = await this.fetchImpl(`${this.bridgeUrl}/gateway/status`, {
        method: "GET",
        signal: AbortSignal.timeout(5000),
      });

      if (!response.ok) {
        return { running: false, platforms: [], activePlatformCount: 0 };
      }

      return await response.json() as RuntimeGatewayStatus;
    } catch {
      return { running: false, platforms: [], activePlatformCount: 0 };
    }
  }

  async getSupportedPlatforms(): Promise<GatewaySupportedPlatform[]> {
    try {
      const response = await this.fetchImpl(
        `${this.bridgeUrl}/gateway/supported-platforms`,
        { method: "GET", signal: AbortSignal.timeout(5000) },
      );
      if (!response.ok) return [];
      const data = await response.json() as { platforms: GatewaySupportedPlatform[] };
      return data.platforms ?? [];
    } catch {
      return [];
    }
  }

  async getConfiguredPlatforms(): Promise<GatewayConfiguredPlatform[]> {
    try {
      const response = await this.fetchImpl(
        `${this.bridgeUrl}/gateway/platforms`,
        { method: "GET", signal: AbortSignal.timeout(5000) },
      );
      if (!response.ok) return [];
      const data = await response.json() as { configured: GatewayConfiguredPlatform[] };
      return data.configured ?? [];
    } catch {
      return [];
    }
  }

  async startGateway(): Promise<GatewayOperationResult> {
    try {
      const response = await this.fetchImpl(`${this.bridgeUrl}/gateway/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
        signal: AbortSignal.timeout(10_000),
      });
      return await response.json() as GatewayOperationResult;
    } catch (error) {
      return { status: "error", error: error instanceof Error ? error.message : String(error) };
    }
  }

  async stopGateway(): Promise<GatewayOperationResult> {
    try {
      const response = await this.fetchImpl(`${this.bridgeUrl}/gateway/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
        signal: AbortSignal.timeout(10_000),
      });
      return await response.json() as GatewayOperationResult;
    } catch (error) {
      return { status: "error", error: error instanceof Error ? error.message : String(error) };
    }
  }

  async configureGateway(request: GatewayConfigureRequest): Promise<GatewayOperationResult> {
    try {
      const response = await this.fetchImpl(`${this.bridgeUrl}/gateway/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: AbortSignal.timeout(10_000),
      });
      return await response.json() as GatewayOperationResult;
    } catch (error) {
      return { status: "error", error: error instanceof Error ? error.message : String(error) };
    }
  }
}

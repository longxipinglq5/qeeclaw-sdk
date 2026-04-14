import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

import type { GatewayAdapterStatus } from "../types.js";

type GatewayAdapterOptions = {
  command?: string;
  args?: string[];
  pidFilePath: string;
  localGatewayWsUrl: string;
  workingDir?: string;
  bridgeEntryPath?: string;
};

type PersistedGatewayState = {
  pid: number;
  startedAt: string;
  command?: string;
  args?: string[];
  workingDir?: string;
  bridgeEntryPath?: string;
};

async function readJsonFile<T>(filePath: string): Promise<T | null> {
  try {
    const raw = await readFile(filePath, "utf8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export class GatewayAdapter {
  constructor(private readonly options: GatewayAdapterOptions) {}

  private baseStatus(): GatewayAdapterStatus {
    return {
      configured: Boolean(this.options.command),
      running: false,
      command: this.options.command,
      args: this.options.args ? [...this.options.args] : [],
      workingDir: this.options.workingDir,
      bridgeEntryPath: this.options.bridgeEntryPath,
    };
  }

  async status(): Promise<GatewayAdapterStatus> {
    const persisted = await readJsonFile<PersistedGatewayState>(this.options.pidFilePath);
    if (!this.options.command) {
      return this.baseStatus();
    }
    if (!persisted?.pid) {
      return this.baseStatus();
    }

    try {
      process.kill(persisted.pid, 0);
      return {
        configured: true,
        running: true,
        command: persisted.command || this.options.command,
        args: persisted.args || this.options.args || [],
        workingDir: persisted.workingDir || this.options.workingDir,
        pid: persisted.pid,
        startedAt: persisted.startedAt,
        bridgeEntryPath: persisted.bridgeEntryPath || this.options.bridgeEntryPath,
      };
    } catch {
      await rm(this.options.pidFilePath, { force: true });
      return this.baseStatus();
    }
  }

  async start(): Promise<GatewayAdapterStatus> {
    const existing = await this.status();
    if (existing.running) {
      return existing;
    }
    if (!this.options.command) {
      throw new Error(
        "No gateway command configured. Set QEECLAW_GATEWAY_COMMAND or QEECLAW_GATEWAY_ENTRY/QEECLAW_BRIDGE_ENTRY before starting the gateway adapter.",
      );
    }

    await mkdir(path.dirname(this.options.pidFilePath), { recursive: true });
    const spawnOptions: Parameters<typeof spawn>[2] = {
      detached: false,
      stdio: "ignore",
      env: {
        ...process.env,
        QEECLAW_GATEWAY_WS_URL: this.options.localGatewayWsUrl,
        OPENCLAW_WS_URL: this.options.localGatewayWsUrl,
      },
    };
    if (this.options.workingDir) {
      (spawnOptions as Record<string, unknown>).cwd = this.options.workingDir;
    }
    const child = spawn(this.options.command, this.options.args || [], spawnOptions);
    child.unref();

    const persisted: PersistedGatewayState = {
      pid: child.pid ?? -1,
      startedAt: new Date().toISOString(),
      command: this.options.command,
      args: this.options.args ? [...this.options.args] : [],
      workingDir: this.options.workingDir,
      bridgeEntryPath: this.options.bridgeEntryPath,
    };
    await writeFile(this.options.pidFilePath, JSON.stringify(persisted, null, 2));
    return {
      configured: true,
      running: true,
      command: persisted.command,
      args: persisted.args,
      workingDir: persisted.workingDir,
      pid: persisted.pid,
      startedAt: persisted.startedAt,
      bridgeEntryPath: persisted.bridgeEntryPath,
    };
  }

  async stop(): Promise<GatewayAdapterStatus> {
    const current = await this.status();
    if (current.running && current.pid) {
      process.kill(current.pid);
    }
    await rm(this.options.pidFilePath, { force: true });
    return this.baseStatus();
  }
}

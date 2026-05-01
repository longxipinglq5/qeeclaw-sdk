import { existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";

import type { SidecarConfig } from "./types.js";

function boolFromEnv(value: string | undefined, fallback: boolean): boolean {
  if (!value) {
    return fallback;
  }
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "no", "off"].includes(normalized)) {
    return false;
  }
  return fallback;
}

function numberFromEnv(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function listFromEnv(value: string | undefined): string[] {
  if (!value?.trim()) {
    return [];
  }
  const raw = value.trim();
  if (raw.startsWith("[")) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
      }
    } catch {
      // Fall through to whitespace splitting.
    }
  }
  return raw
    .split(/\s+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function resolveDefaultGatewayEntryPath(): string | undefined {
  const candidates = [
    path.resolve(process.cwd(), "bridge.js"),
    path.resolve(process.cwd(), "openclaw-extensions", "nexus-bridge", "bridge.js"),
  ];
  return candidates.find((candidate) => existsSync(candidate));
}

function resolveDefaultStateRootDir(env: NodeJS.ProcessEnv): string {
  if (env.QEECLAW_STATE_DIR?.trim()) {
    return path.resolve(env.QEECLAW_STATE_DIR);
  }
  if (env.QEECLAW_OPENCLAW_STATE_DIR?.trim()) {
    return path.resolve(env.QEECLAW_OPENCLAW_STATE_DIR);
  }

  const qeeclawStateDir = path.join(os.homedir(), ".qeeclaw");
  const legacyOpenClawStateDir = path.join(os.homedir(), ".openclaw");
  if (existsSync(qeeclawStateDir)) {
    return qeeclawStateDir;
  }
  if (existsSync(legacyOpenClawStateDir)) {
    return legacyOpenClawStateDir;
  }
  return qeeclawStateDir;
}

function resolveStateFilePath(env: NodeJS.ProcessEnv, stateRootDir: string): string {
  if (env.QEECLAW_AUTH_STATE_FILE?.trim()) {
    return path.resolve(env.QEECLAW_AUTH_STATE_FILE);
  }

  const genericStateFilePath = path.join(stateRootDir, "auth-state.json");
  const legacyStateFilePath = path.join(stateRootDir, "nexus-auth.json");
  if (existsSync(genericStateFilePath)) {
    return genericStateFilePath;
  }
  if (existsSync(legacyStateFilePath)) {
    return legacyStateFilePath;
  }
  if (/(^|[\\/])\.openclaw$/.test(stateRootDir)) {
    return legacyStateFilePath;
  }
  return genericStateFilePath;
}

function resolveGatewayLaunch(env: NodeJS.ProcessEnv): Pick<
  SidecarConfig,
  "gatewayCommand" | "gatewayArgs" | "gatewayWorkingDir" | "bridgeEntryPath"
> {
  const gatewayCommand = env.QEECLAW_GATEWAY_COMMAND?.trim();
  if (gatewayCommand) {
    return {
      gatewayCommand,
      gatewayArgs: listFromEnv(env.QEECLAW_GATEWAY_ARGS),
      gatewayWorkingDir: env.QEECLAW_GATEWAY_WORKDIR?.trim() || undefined,
      bridgeEntryPath: undefined,
    };
  }

  const legacyEntryPath =
    env.QEECLAW_GATEWAY_ENTRY?.trim() ||
    env.QEECLAW_BRIDGE_ENTRY?.trim() ||
    resolveDefaultGatewayEntryPath();
  if (!legacyEntryPath) {
    return {
      gatewayCommand: undefined,
      gatewayArgs: [],
      gatewayWorkingDir: env.QEECLAW_GATEWAY_WORKDIR?.trim() || undefined,
      bridgeEntryPath: undefined,
    };
  }

  return {
    gatewayCommand: process.execPath,
    gatewayArgs: [legacyEntryPath],
    gatewayWorkingDir: env.QEECLAW_GATEWAY_WORKDIR?.trim() || path.dirname(legacyEntryPath),
    bridgeEntryPath: legacyEntryPath,
  };
}

export function loadSidecarConfig(env: NodeJS.ProcessEnv = process.env): SidecarConfig {
  const stateRootDir = resolveDefaultStateRootDir(env);
  const sidecarStateDir = env.QEECLAW_SIDECAR_STATE_DIR || path.join(stateRootDir, "sidecar");
  const gatewayLaunch = resolveGatewayLaunch(env);
  const startGatewayOnBoot = boolFromEnv(
    env.QEECLAW_SIDECAR_START_GATEWAY,
    boolFromEnv(env.QEECLAW_SIDECAR_START_BRIDGE, false),
  );

  return {
    controlPlaneBaseUrl: (env.QEECLAW_CONTROL_PLANE_URL || "http://localhost:3456").replace(/\/+$/, ""),
    localGatewayWsUrl: env.QEECLAW_GATEWAY_WS_URL || env.OPENCLAW_WS_URL || "ws://127.0.0.1:18789",
    sidecarHost: env.QEECLAW_SIDECAR_HOST?.trim() || "127.0.0.1",
    sidecarPort: numberFromEnv(env.QEECLAW_SIDECAR_PORT, 21736),
    sidecarAuthToken: env.QEECLAW_SIDECAR_AUTH_TOKEN?.trim() || undefined,
    gatewayAuthToken:
      env.QEECLAW_GATEWAY_AUTH_TOKEN?.trim() ||
      env.OPENCLAW_GATEWAY_TOKEN?.trim() ||
      env.QEECLAW_GATEWAY_TOKEN?.trim() ||
      undefined,
    gatewayAuthPassword:
      env.QEECLAW_GATEWAY_AUTH_PASSWORD?.trim() ||
      env.OPENCLAW_GATEWAY_PASSWORD?.trim() ||
      env.QEECLAW_GATEWAY_PASSWORD?.trim() ||
      undefined,
    allowRemoteAccess: boolFromEnv(env.QEECLAW_SIDECAR_ALLOW_REMOTE, false),
    startGatewayOnBoot,
    startBridgeOnBoot: startGatewayOnBoot,
    autoBootstrapDevice: boolFromEnv(env.QEECLAW_SIDECAR_AUTO_BOOTSTRAP, false),
    stateRootDir,
    stateFilePath: resolveStateFilePath(env, stateRootDir),
    gatewayCommand: gatewayLaunch.gatewayCommand,
    gatewayArgs: gatewayLaunch.gatewayArgs,
    gatewayWorkingDir: gatewayLaunch.gatewayWorkingDir,
    bridgeEntryPath: gatewayLaunch.bridgeEntryPath,
    gatewayPidFilePath: path.join(sidecarStateDir, "gateway-adapter.json"),
    bridgePidFilePath: path.join(sidecarStateDir, "gateway-adapter.json"),
    knowledgeConfigFilePath: path.join(sidecarStateDir, "knowledge-worker.json"),
    approvalsCacheFilePath: path.join(sidecarStateDir, "approval-agent.json"),
    channelSecretsFilePath: env.QEECLAW_CHANNEL_SECRETS_FILE?.trim() || path.join(sidecarStateDir, "channel-secrets.json"),
    channelAttachmentDirPath: env.QEECLAW_CHANNEL_ATTACHMENT_DIR?.trim() || path.join(sidecarStateDir, "channel-attachments"),
    channelRuntimeMode: env.QEECLAW_CHANNEL_RUNTIME_MODE === "echo" ? "echo" : "gateway",
    deviceName: env.QEECLAW_DEVICE_NAME || os.hostname() || "QeeClaw Device",
    hostname: env.QEECLAW_HOSTNAME || os.hostname() || "localhost",
    osInfo: env.QEECLAW_OS_INFO || `${os.platform()} ${os.release()}`,
  };
}

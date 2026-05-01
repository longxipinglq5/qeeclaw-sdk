import { ApprovalAgent } from "./agents/approval-agent.js";
import { LocalSecurityAgent } from "./agents/local-security-agent.js";
import { loadSidecarConfig } from "./config.js";
import { ControlPlaneClient } from "./control-plane/client.js";
import { GatewayAdapter } from "./gateway/gateway-adapter.js";
import { HttpSidecarServer } from "./server/http-sidecar-server.js";
import { AuthStateStore, toPublicAuthState } from "./state/auth-state-store.js";
import { SyncService } from "./sync/sync-service.js";
import { access, mkdir, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import type { SidecarConfig, SidecarSelfCheck } from "./types.js";
import { ChannelAttachmentStore } from "./channels/attachment-store.js";
import { ChannelManager } from "./channels/manager.js";
import { EchoRuntimeInvoker, GatewayRuntimeInvoker } from "./channels/runtime-invoker.js";
import { ChannelSecretStore } from "./channels/secret-store.js";
import { FeishuLocalAdapter } from "./channels/feishu/adapter.js";
import { FeishuWebSocketTransport } from "./channels/feishu/websocket-transport.js";
import { WechatWorkLocalAdapter, WechatWorkRestTransport, type WechatWorkIncomingPayload } from "./channels/wechat-work/adapter.js";
import { MemoryWechatPersonalTransport, WechatPersonalLocalAdapter } from "./channels/wechat-personal/adapter.js";
import { KnowledgeWorker } from "./workers/knowledge-worker.js";
import { MemoryWorker } from "./workers/memory-worker.js";

export * from "./types.js";
export * from "./config.js";
export * from "./state/auth-state-store.js";
export * from "./control-plane/client.js";
export * from "./gateway/gateway-adapter.js";
export * from "./workers/memory-worker.js";
export * from "./workers/knowledge-worker.js";
export * from "./agents/local-security-agent.js";
export * from "./agents/approval-agent.js";
export * from "./sync/sync-service.js";
export * from "./server/http-sidecar-server.js";
export * from "./channels/index.js";

export class QeeClawRuntimeSidecar {
  readonly config: SidecarConfig;
  readonly stateStore: AuthStateStore;
  readonly controlPlane: ControlPlaneClient;
  readonly gatewayAdapter: GatewayAdapter;
  readonly memoryWorker: MemoryWorker;
  readonly knowledgeWorker: KnowledgeWorker;
  readonly securityAgent: LocalSecurityAgent;
  readonly approvalAgent: ApprovalAgent;
  readonly syncService: SyncService;
  readonly channelAttachmentStore: ChannelAttachmentStore;
  readonly channelSecretStore: ChannelSecretStore;
  readonly channelManager: ChannelManager;
  readonly wechatPersonalTransport: MemoryWechatPersonalTransport;
  private wechatWorkTransport?: WechatWorkRestTransport;
  readonly server: HttpSidecarServer;

  constructor(config: SidecarConfig = loadSidecarConfig()) {
    this.config = config;
    this.stateStore = new AuthStateStore(config.stateFilePath);
    this.controlPlane = new ControlPlaneClient(config.controlPlaneBaseUrl);
    this.gatewayAdapter = new GatewayAdapter({
      command: config.gatewayCommand,
      args: config.gatewayArgs,
      pidFilePath: config.gatewayPidFilePath,
      localGatewayWsUrl: config.localGatewayWsUrl,
      workingDir: config.gatewayWorkingDir,
      bridgeEntryPath: config.bridgeEntryPath,
    });
    this.memoryWorker = new MemoryWorker(this.stateStore, this.controlPlane);
    this.knowledgeWorker = new KnowledgeWorker(config.knowledgeConfigFilePath);
    this.securityAgent = new LocalSecurityAgent();
    this.approvalAgent = new ApprovalAgent(config.approvalsCacheFilePath, this.stateStore, this.controlPlane);
    this.syncService = new SyncService(config, this.stateStore, this.controlPlane);
    this.channelAttachmentStore = new ChannelAttachmentStore(config.channelAttachmentDirPath);
    this.channelSecretStore = new ChannelSecretStore(config.channelSecretsFilePath);
    this.wechatPersonalTransport = new MemoryWechatPersonalTransport();
    this.channelManager = new ChannelManager({
      invoker:
        config.channelRuntimeMode === "echo"
          ? new EchoRuntimeInvoker()
          : new GatewayRuntimeInvoker({
              wsUrl: config.localGatewayWsUrl,
              authToken: config.gatewayAuthToken,
              authPassword: config.gatewayAuthPassword,
              authTokenProvider: async () => (await this.stateStore.read()).deviceKey,
            }),
      attachmentStore: this.channelAttachmentStore,
      adapters: [],
      logger: {
        log: (message) => process.stdout.write(`[qeeclaw-runtime-sidecar] ${message}\n`),
        error: (message) => process.stderr.write(`[qeeclaw-runtime-sidecar] ${message}\n`),
      },
    });
    this.server = new HttpSidecarServer({
      config,
      stateStore: this.stateStore,
      syncService: this.syncService,
      gatewayAdapter: this.gatewayAdapter,
      memoryWorker: this.memoryWorker,
      knowledgeWorker: this.knowledgeWorker,
      securityAgent: this.securityAgent,
      approvalAgent: this.approvalAgent,
      channelManager: this.channelManager,
      channelSecretStore: this.channelSecretStore,
      reloadChannels: () => this.configureLocalChannelsFromSecrets(),
      emitWechatWorkMessage: (payload: WechatWorkIncomingPayload) => this.emitWechatWorkMessage(payload),
      wechatPersonalTransport: this.wechatPersonalTransport,
    });
  }

  async getLocalApiToken(): Promise<string> {
    return this.stateStore.ensureSidecarAuthToken(this.config.sidecarAuthToken);
  }

  async start(): Promise<void> {
    await this.stateStore.ensureInstallationId();
    await this.stateStore.ensureSidecarAuthToken(this.config.sidecarAuthToken);
    await this.configureLocalChannelsFromSecrets();
    if (this.config.autoBootstrapDevice) {
      try {
        await this.syncService.sync();
      } catch (error) {
        process.stderr.write(
          `[qeeclaw-runtime-sidecar] startup sync skipped: ${error instanceof Error ? error.message : String(error)}\n`,
        );
      }
    }
    if (this.config.startGatewayOnBoot || this.config.startBridgeOnBoot) {
      await this.gatewayAdapter.start();
    }
    await this.channelManager.start();
    await this.server.start();
  }

  async configureLocalChannelsFromSecrets(): Promise<void> {
    const wechatWork = await this.channelSecretStore.get("wechat_work");
    const wechatWorkCredentials = wechatWork?.credentials || {};
    if (
      !wechatWork?.enabled ||
      !wechatWorkCredentials.corpId?.trim() ||
      !wechatWorkCredentials.corpSecret?.trim() ||
      !wechatWorkCredentials.agentId?.trim()
    ) {
      this.wechatWorkTransport = undefined;
      await this.channelManager.removeAdapter("wechat_work");
    } else {
      this.wechatWorkTransport = new WechatWorkRestTransport({
        corpId: wechatWorkCredentials.corpId,
        corpSecret: wechatWorkCredentials.corpSecret,
        agentId: wechatWorkCredentials.agentId,
        apiBaseUrl: wechatWorkCredentials.apiBaseUrl,
      });
      await this.channelManager.replaceAdapter(new WechatWorkLocalAdapter(this.wechatWorkTransport));
    }

    const feishu = await this.channelSecretStore.get("feishu");
    const credentials = feishu?.credentials || {};
    if (!feishu?.enabled || !credentials.appId?.trim() || !credentials.appSecret?.trim()) {
      await this.channelManager.removeAdapter("feishu");
    } else {
      await this.channelManager.replaceAdapter(
        new FeishuLocalAdapter({
          transport: new FeishuWebSocketTransport({
            appId: credentials.appId,
            appSecret: credentials.appSecret,
            domain: credentials.domain,
            encryptKey: credentials.encryptKey,
            verificationToken: credentials.verificationToken,
          }),
        }),
      );
    }

    const wechatPersonal = await this.channelSecretStore.get("wechat_personal");
    if (!wechatPersonal?.enabled) {
      await this.channelManager.removeAdapter("wechat_personal");
      return;
    }

    await this.channelManager.replaceAdapter(new WechatPersonalLocalAdapter(this.wechatPersonalTransport));
  }

  async emitWechatWorkMessage(payload: WechatWorkIncomingPayload): Promise<void> {
    if (!this.wechatWorkTransport) {
      throw new Error("WeChat Work local bridge is not configured");
    }
    await this.wechatWorkTransport.emit(payload);
  }

  async stop(): Promise<void> {
    await this.server.stop();
    await this.channelManager.stop();
  }

  async selfCheck(): Promise<SidecarSelfCheck> {
    const authState = await this.stateStore.read();
    const gateway = await this.gatewayAdapter.status();
    const knowledge = await this.knowledgeWorker.getConfig();
    const gatewayCommandConfigured = Boolean(this.config.gatewayCommand?.trim());
    let gatewayCommandCheck: SidecarSelfCheck["checks"]["gatewayCommandCheck"] = "not_configured";

    if (gatewayCommandConfigured && this.config.gatewayCommand) {
      if (this.config.gatewayCommand.includes("/") || this.config.gatewayCommand.includes("\\") || this.config.gatewayCommand.startsWith(".")) {
        const resolvedCommandPath = path.resolve(this.config.gatewayWorkingDir || process.cwd(), this.config.gatewayCommand);
        gatewayCommandCheck = await access(resolvedCommandPath)
          .then(() => "path_exists" as const)
          .catch(() => "path_missing" as const);
      } else {
        gatewayCommandCheck = "lookup_skipped";
      }
    }

    const stateDirPath = path.dirname(this.config.knowledgeConfigFilePath);
    const tempProbePath = path.join(stateDirPath, ".write-probe");
    const stateDirWritable = await mkdir(stateDirPath, { recursive: true })
      .then(async () => {
        await writeFile(tempProbePath, "ok");
        await rm(tempProbePath, { force: true });
        return true;
      })
      .catch(() => false);
    const stateDirWritableHint = stateDirWritable
      ? undefined
      : "Current process cannot write sidecar state dir. Set QEECLAW_SIDECAR_STATE_DIR to a writable path or adjust directory permissions.";

    return {
      status: "ok",
      checks: {
        gatewayConfigured: gatewayCommandConfigured,
        gatewayCommand: this.config.gatewayCommand,
        gatewayArgs: [...this.config.gatewayArgs],
        gatewayWorkingDir: this.config.gatewayWorkingDir,
        bridgeEntryPath: this.config.bridgeEntryPath,
        gatewayCommandCheck,
        stateFilePath: this.config.stateFilePath,
        stateRootDir: this.config.stateRootDir,
        stateDirPath,
        stateDirWritable,
        stateDirWritableHint,
        knowledgeConfigPath: this.config.knowledgeConfigFilePath,
        approvalsCachePath: this.config.approvalsCacheFilePath,
        channelSecretsPath: this.config.channelSecretsFilePath,
        channelAttachmentDirPath: this.config.channelAttachmentDirPath,
      },
      auth: {
        ...toPublicAuthState(authState, {
          configuredAuthToken: this.config.sidecarAuthToken,
        }),
      },
      gateway,
      knowledge,
      channels: this.channelManager.getStatus(),
    };
  }
}

export function createRuntimeSidecar(config?: SidecarConfig): QeeClawRuntimeSidecar {
  return new QeeClawRuntimeSidecar(config);
}

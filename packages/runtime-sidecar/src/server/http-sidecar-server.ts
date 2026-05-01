import http from "node:http";

import type { ApprovalAgent } from "../agents/approval-agent.js";
import type { LocalSecurityAgent } from "../agents/local-security-agent.js";
import type { GatewayAdapter } from "../gateway/gateway-adapter.js";
import type { AuthStateStore } from "../state/auth-state-store.js";
import { toPublicAuthState } from "../state/auth-state-store.js";
import type { MemoryWorker } from "../workers/memory-worker.js";
import type { KnowledgeWorker } from "../workers/knowledge-worker.js";
import type { SidecarConfig, SidecarHealth, SyncResult } from "../types.js";
import type { SyncService } from "../sync/sync-service.js";
import type { ChannelManager } from "../channels/manager.js";
import type { ChannelSecretStore } from "../channels/secret-store.js";
import type { WechatWorkIncomingPayload } from "../channels/wechat-work/adapter.js";
import {
  parseWechatWorkCallbackBody,
  verifyWechatWorkUrl,
  type WechatWorkCallbackCredentials,
} from "../channels/wechat-work/callback-crypto.js";
import type {
  MemoryWechatPersonalTransport,
  WechatPersonalIncomingPayload,
} from "../channels/wechat-personal/adapter.js";

type Dependencies = {
  config: SidecarConfig;
  stateStore: AuthStateStore;
  syncService: SyncService;
  gatewayAdapter: GatewayAdapter;
  memoryWorker: MemoryWorker;
  knowledgeWorker: KnowledgeWorker;
  securityAgent: LocalSecurityAgent;
  approvalAgent: ApprovalAgent;
  channelManager: ChannelManager;
  channelSecretStore: ChannelSecretStore;
  reloadChannels?: () => Promise<void>;
  emitWechatWorkMessage?: (payload: WechatWorkIncomingPayload) => Promise<void>;
  wechatPersonalTransport?: MemoryWechatPersonalTransport;
};

async function readJsonBody(request: http.IncomingMessage): Promise<Record<string, unknown>> {
  const raw = await readRawBody(request);
  if (!raw.trim()) {
    return {};
  }
  return JSON.parse(raw) as Record<string, unknown>;
}

async function readRawBody(request: http.IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk)));
  }
  if (!chunks.length) {
    return "";
  }
  return Buffer.concat(chunks).toString("utf8");
}

function isLoopbackHost(host: string): boolean {
  const normalized = (host || "").trim().toLowerCase();
  return normalized === "127.0.0.1" || normalized === "localhost" || normalized === "::1";
}

function extractBearerToken(request: http.IncomingMessage): string | undefined {
  const raw = request.headers.authorization;
  if (!raw) {
    return undefined;
  }
  const match = raw.match(/^Bearer\s+(.+)$/i);
  return match?.[1]?.trim();
}

function sendJson(response: http.ServerResponse, status: number, data: unknown): void {
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json");
  response.end(JSON.stringify({ code: 0, data, message: "success" }));
}

function sendError(response: http.ServerResponse, status: number, error: unknown): void {
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json");
  response.end(
    JSON.stringify({
      code: status,
      message: error instanceof Error ? error.message : String(error),
    }),
  );
}

function sendText(response: http.ServerResponse, status: number, data: string): void {
  response.statusCode = status;
  response.setHeader("Content-Type", "text/plain; charset=utf-8");
  response.end(data);
}

export class HttpSidecarServer {
  private server?: http.Server;

  constructor(private readonly deps: Dependencies) {}

  private async getWechatWorkCallbackCredentials(): Promise<WechatWorkCallbackCredentials> {
    const record = await this.deps.channelSecretStore.get("wechat_work");
    const credentials = record?.credentials || {};
    const corpId = credentials.corpId?.trim();
    const token = credentials.token?.trim();
    const encodingAesKey = credentials.encodingAesKey?.trim() || credentials.aesKey?.trim();
    if (!record?.enabled || !corpId || !token || !encodingAesKey) {
      throw new Error("WeChat Work local callback is not configured");
    }
    return {
      corpId,
      token,
      encodingAesKey,
    };
  }

  private async ensureRequestAuthorized(
    request: http.IncomingMessage,
    response: http.ServerResponse,
  ): Promise<boolean> {
    const expectedToken = await this.deps.stateStore.ensureSidecarAuthToken(this.deps.config.sidecarAuthToken);
    const actualToken = extractBearerToken(request);
    if (actualToken && actualToken === expectedToken) {
      return true;
    }

    response.statusCode = 401;
    response.setHeader("Content-Type", "application/json");
    response.setHeader("WWW-Authenticate", 'Bearer realm="qeeclaw-sidecar"');
    response.end(
      JSON.stringify({
        code: 401,
        message: "Unauthorized sidecar request",
      }),
    );
    return false;
  }

  async start(): Promise<void> {
    if (this.server) {
      return;
    }

    if (!this.deps.config.allowRemoteAccess && !isLoopbackHost(this.deps.config.sidecarHost)) {
      throw new Error(
        `Refusing to bind sidecar HTTP server to non-loopback host '${this.deps.config.sidecarHost}'. ` +
          "Set QEECLAW_SIDECAR_ALLOW_REMOTE=true only when you fully understand the risk.",
      );
    }

    await this.deps.stateStore.ensureSidecarAuthToken(this.deps.config.sidecarAuthToken);

    this.server = http.createServer(async (request: http.IncomingMessage, response: http.ServerResponse) => {
      try {
        const method = request.method || "GET";
        const origin = request.headers.origin;
        response.setHeader("Access-Control-Allow-Origin", origin || "*");
        response.setHeader("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS");
        response.setHeader("Access-Control-Allow-Headers", "Authorization,Content-Type");
        response.setHeader("Vary", "Origin");

        if (method === "OPTIONS") {
          response.statusCode = 204;
          response.end("");
          return;
        }

        const url = new URL(
          request.url || "/",
          `http://${this.deps.config.sidecarHost}:${this.deps.config.sidecarPort}`,
        );
        const pathname = url.pathname;

        if (pathname === "/channels/wechat-work/callback") {
          if (!this.deps.emitWechatWorkMessage) {
            sendText(response, 404, "not available");
            return;
          }
          const credentials = await this.getWechatWorkCallbackCredentials();
          const msgSignature = url.searchParams.get("msg_signature") || "";
          const timestamp = url.searchParams.get("timestamp") || "";
          const nonce = url.searchParams.get("nonce") || "";

          if (method === "GET") {
            const echostr = url.searchParams.get("echostr") || "";
            const reply = verifyWechatWorkUrl({
              msgSignature,
              timestamp,
              nonce,
              echostr,
              credentials,
            });
            sendText(response, 200, reply);
            return;
          }

          if (method === "POST") {
            const rawBody = await readRawBody(request);
            const payload = parseWechatWorkCallbackBody({
              rawBody,
              msgSignature,
              timestamp,
              nonce,
              credentials,
            });
            await this.deps.emitWechatWorkMessage(payload);
            sendText(response, 200, "success");
            return;
          }

          sendText(response, 405, "method not allowed");
          return;
        }

        if (!(await this.ensureRequestAuthorized(request, response))) {
          return;
        }

        if (method === "GET" && pathname === "/health") {
          const authState = await this.deps.stateStore.read();
          const gateway = await this.deps.gatewayAdapter.status();
          const payload: SidecarHealth = {
            status: "ok",
            config: {
              controlPlaneBaseUrl: this.deps.config.controlPlaneBaseUrl,
              sidecarHost: this.deps.config.sidecarHost,
              sidecarPort: this.deps.config.sidecarPort,
              authRequired: true,
              allowRemoteAccess: this.deps.config.allowRemoteAccess,
              startGatewayOnBoot: this.deps.config.startGatewayOnBoot,
              startBridgeOnBoot: this.deps.config.startBridgeOnBoot ?? this.deps.config.startGatewayOnBoot,
              autoBootstrapDevice: this.deps.config.autoBootstrapDevice,
            },
            auth: toPublicAuthState(authState, {
              configuredAuthToken: this.deps.config.sidecarAuthToken,
            }) as SidecarHealth["auth"],
            gateway,
            channels: this.deps.channelManager.getStatus(),
          };
          sendJson(response, 200, payload);
          return;
        }

        if (method === "GET" && pathname === "/state") {
          sendJson(
            response,
            200,
            toPublicAuthState(await this.deps.stateStore.read(), {
              configuredAuthToken: this.deps.config.sidecarAuthToken,
            }),
          );
          return;
        }

        if (method === "POST" && pathname === "/sync") {
          const result: SyncResult = await this.deps.syncService.sync();
          sendJson(response, 200, result);
          return;
        }

        if (method === "GET" && pathname === "/gateway/status") {
          sendJson(response, 200, await this.deps.gatewayAdapter.status());
          return;
        }

        if (method === "GET" && pathname === "/channels/status") {
          sendJson(response, 200, {
            ...this.deps.channelManager.getStatus(),
            secrets: await this.deps.channelSecretStore.publicStatus(),
          });
          return;
        }

        if (method === "POST" && pathname === "/channels/reload") {
          if (!this.deps.reloadChannels) {
            sendError(response, 501, "Channel reload is not available");
            return;
          }
          await this.deps.reloadChannels();
          sendJson(response, 200, {
            ...this.deps.channelManager.getStatus(),
            secrets: await this.deps.channelSecretStore.publicStatus(),
          });
          return;
        }

        if (method === "PATCH" && pathname.startsWith("/channels/secrets/")) {
          const channel = decodeURIComponent(pathname.replace("/channels/secrets/", ""));
          if (!["feishu", "wechat_work", "wechat_personal"].includes(channel)) {
            sendError(response, 400, `Unsupported channel: ${channel}`);
            return;
          }
          const body = await readJsonBody(request);
          const credentials =
            body.credentials && typeof body.credentials === "object" && !Array.isArray(body.credentials)
              ? Object.fromEntries(
                  Object.entries(body.credentials as Record<string, unknown>)
                    .filter(([, value]) => typeof value === "string")
                    .map(([key, value]) => [key, String(value)]),
                )
              : undefined;
          await this.deps.channelSecretStore.patch(channel as "feishu" | "wechat_work" | "wechat_personal", {
            enabled: typeof body.enabled === "boolean" ? body.enabled : undefined,
            credentials,
          });
          sendJson(response, 200, {
            secrets: await this.deps.channelSecretStore.publicStatus(),
            reloadRequired: true,
          });
          return;
        }

        if (method === "POST" && pathname === "/channels/wechat-personal/upstream") {
          if (!this.deps.wechatPersonalTransport) {
            sendError(response, 404, "WeChat personal local bridge transport is not available");
            return;
          }
          const body = await readJsonBody(request);
          const payload =
            body.payload && typeof body.payload === "object" && !Array.isArray(body.payload)
              ? (body.payload as WechatPersonalIncomingPayload)
              : (body as WechatPersonalIncomingPayload);
          const replies = await this.deps.wechatPersonalTransport.emitAndCollectReplies(payload);
          sendJson(response, 200, {
            handled: true,
            replies,
          });
          return;
        }

        if (method === "POST" && pathname === "/channels/wechat-work/upstream") {
          if (!this.deps.emitWechatWorkMessage) {
            sendError(response, 404, "WeChat Work local bridge transport is not available");
            return;
          }
          const body = await readJsonBody(request);
          const payload =
            body.payload && typeof body.payload === "object" && !Array.isArray(body.payload)
              ? (body.payload as WechatWorkIncomingPayload)
              : (body as WechatWorkIncomingPayload);
          await this.deps.emitWechatWorkMessage(payload);
          sendJson(response, 200, {
            handled: true,
          });
          return;
        }

        if (method === "POST" && pathname === "/gateway/start") {
          sendJson(response, 200, await this.deps.gatewayAdapter.start());
          return;
        }

        if (method === "POST" && pathname === "/gateway/stop") {
          sendJson(response, 200, await this.deps.gatewayAdapter.stop());
          return;
        }

        if (method === "POST" && pathname === "/memory/store") {
          sendJson(response, 200, await this.deps.memoryWorker.store(await readJsonBody(request)));
          return;
        }

        if (method === "POST" && pathname === "/memory/search") {
          sendJson(response, 200, await this.deps.memoryWorker.search(await readJsonBody(request)));
          return;
        }

        if (method === "DELETE" && pathname.startsWith("/memory/")) {
          const entryId = decodeURIComponent(pathname.replace("/memory/", ""));
          sendJson(response, 200, await this.deps.memoryWorker.delete(entryId));
          return;
        }

        if (method === "GET" && pathname === "/memory/stats") {
          sendJson(response, 200, await this.deps.memoryWorker.stats(url.searchParams.get("agent_id") || undefined));
          return;
        }

        if (method === "GET" && pathname === "/knowledge/config") {
          sendJson(response, 200, await this.deps.knowledgeWorker.getConfig());
          return;
        }

        if (method === "POST" && pathname === "/knowledge/config") {
          const body = await readJsonBody(request);
          sendJson(
            response,
            200,
            await this.deps.knowledgeWorker.updateConfig({
              watchDir: typeof body.watchDir === "string" ? body.watchDir : undefined,
            }),
          );
          return;
        }

        if (method === "POST" && pathname === "/knowledge/sync") {
          const body = await readJsonBody(request);
          const limit = typeof body.limit === "number" ? body.limit : undefined;
          sendJson(response, 200, await this.deps.knowledgeWorker.sync(limit));
          return;
        }

        if (method === "GET" && pathname === "/knowledge/inventory") {
          sendJson(response, 200, await this.deps.knowledgeWorker.getConfig());
          return;
        }

        if (method === "POST" && pathname === "/policy/tool-access/check") {
          const body = await readJsonBody(request);
          const decision = this.deps.securityAgent.checkToolAccess({
            tool_name: typeof body.tool_name === "string" ? body.tool_name : undefined,
            risk_level: typeof body.risk_level === "string" ? body.risk_level : undefined,
            requires_approval: Boolean(body.requires_approval),
          });
          sendJson(response, 200, decision);
          return;
        }

        if (method === "POST" && pathname === "/policy/data-access/check") {
          const body = await readJsonBody(request);
          const decision = this.deps.securityAgent.checkDataAccess({
            classification: typeof body.classification === "string" ? body.classification : undefined,
            operation: typeof body.operation === "string" ? body.operation : undefined,
            requires_approval: Boolean(body.requires_approval),
          });
          sendJson(response, 200, decision);
          return;
        }

        if (method === "POST" && pathname === "/policy/exec-access/check") {
          const body = await readJsonBody(request);
          const decision = this.deps.securityAgent.checkExecAccess({
            command: typeof body.command === "string" ? body.command : undefined,
            risk_level: typeof body.risk_level === "string" ? body.risk_level : undefined,
            requires_approval: Boolean(body.requires_approval),
          });
          sendJson(response, 200, decision);
          return;
        }

        if (method === "POST" && pathname === "/approvals/request") {
          const body = await readJsonBody(request);
          sendJson(
            response,
            200,
            await this.deps.approvalAgent.requestApproval({
              approvalType:
                body.approvalType === "tool_access" ||
                body.approvalType === "data_access" ||
                body.approvalType === "exec_access" ||
                body.approvalType === "custom"
                  ? body.approvalType
                  : undefined,
              title: String(body.title || "Sidecar approval request"),
              reason: String(body.reason || "manual sidecar approval"),
              riskLevel:
                body.riskLevel === "low" ||
                body.riskLevel === "medium" ||
                body.riskLevel === "high" ||
                body.riskLevel === "critical"
                  ? body.riskLevel
                  : undefined,
              payload: typeof body.payload === "object" && body.payload ? (body.payload as Record<string, unknown>) : {},
              expiresInSeconds: typeof body.expiresInSeconds === "number" ? body.expiresInSeconds : undefined,
            }),
          );
          return;
        }

        if (method === "GET" && pathname === "/approvals") {
          sendJson(
            response,
            200,
            await this.deps.approvalAgent.listApprovals({
              scope: url.searchParams.get("scope") === "all" ? "all" : "mine",
              status:
                url.searchParams.get("status") === "pending" ||
                url.searchParams.get("status") === "approved" ||
                url.searchParams.get("status") === "rejected" ||
                url.searchParams.get("status") === "expired"
                  ? (url.searchParams.get("status") as "pending" | "approved" | "rejected" | "expired")
                  : undefined,
            }),
          );
          return;
        }

        if (method === "GET" && pathname === "/approvals/pending-local") {
          sendJson(response, 200, await this.deps.approvalAgent.listPendingLocalCache());
          return;
        }

        sendError(response, 404, "Not found");
      } catch (error) {
        sendError(response, 500, error);
      }
    });

    await new Promise<void>((resolve, reject) => {
      if (!this.server) {
        reject(new Error("Sidecar server was not initialized"));
        return;
      }

      const onError = (error: Error) => {
        this.server?.removeListener("error", onError);
        reject(
          new Error(
            `Failed to start sidecar HTTP server on ${this.deps.config.sidecarHost}:${this.deps.config.sidecarPort}: ${error.message}`,
          ),
        );
      };

      this.server.once("error", onError);
      this.server.listen(this.deps.config.sidecarPort, this.deps.config.sidecarHost, () => {
        this.server?.removeListener("error", onError);
        resolve();
      });
    });
  }

  async stop(): Promise<void> {
    if (!this.server) {
      return;
    }
    await new Promise<void>((resolve, reject) => {
      this.server?.close((error?: Error | null) => {
        if (error) {
          reject(error);
          return;
        }
        resolve();
      });
    });
    this.server = undefined;
  }
}

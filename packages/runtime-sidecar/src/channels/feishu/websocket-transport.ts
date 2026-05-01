import type { FeishuEventEnvelope, FeishuLocalTransport, FeishuSendPayload } from "./adapter.js";

export type FeishuWebSocketTransportOptions = {
  appId: string;
  appSecret: string;
  domain?: "feishu" | "lark" | string;
  encryptKey?: string;
  verificationToken?: string;
  sdkLoader?: () => Promise<unknown>;
  fetchImpl?: typeof fetch;
};

type FeishuTokenCache = {
  token: string;
  expiresAt: number;
};

function resolveOpenApiBaseUrl(domain?: string): string {
  if (!domain || domain === "feishu") {
    return "https://open.feishu.cn";
  }
  if (domain === "lark") {
    return "https://open.larksuite.com";
  }
  return domain.replace(/\/+$/, "");
}

function resolveSdkDomain(sdk: Record<string, unknown>, domain?: string): unknown {
  const domainEnum = sdk.Domain as Record<string, unknown> | undefined;
  if (domain === "lark") {
    return domainEnum?.Lark ?? "https://open.larksuite.com";
  }
  if (!domain || domain === "feishu") {
    return domainEnum?.Feishu ?? "https://open.feishu.cn";
  }
  return domain.replace(/\/+$/, "");
}

async function loadLarkSdk(): Promise<Record<string, unknown>> {
  const dynamicImport = new Function("specifier", "return import(specifier)") as (specifier: string) => Promise<unknown>;
  const mod = await dynamicImport("@larksuiteoapi/node-sdk");
  return (mod && typeof mod === "object" ? mod : {}) as Record<string, unknown>;
}

export class FeishuWebSocketTransport implements FeishuLocalTransport {
  private wsClient?: { start(params: { eventDispatcher: unknown }): void; close(): void };
  private tokenCache?: FeishuTokenCache;
  private readonly fetchImpl: typeof fetch;

  constructor(private readonly options: FeishuWebSocketTransportOptions) {
    this.fetchImpl = options.fetchImpl || fetch;
  }

  async start(handlers: { onEvent(event: FeishuEventEnvelope): Promise<void> }): Promise<void> {
    if (!this.options.appId?.trim() || !this.options.appSecret?.trim()) {
      throw new Error("Feishu local bridge requires appId and appSecret");
    }

    const sdk = (this.options.sdkLoader ? await this.options.sdkLoader() : await loadLarkSdk()) as Record<string, unknown>;
    const EventDispatcher = sdk.EventDispatcher as
      | (new (params: { encryptKey?: string; verificationToken?: string }) => { register(handlers: Record<string, (data: unknown) => Promise<void> | void>): void })
      | undefined;
    const WSClient = sdk.WSClient as
      | (new (params: { appId: string; appSecret: string; domain?: unknown; loggerLevel?: unknown }) => { start(params: { eventDispatcher: unknown }): void; close(): void })
      | undefined;
    if (!EventDispatcher || !WSClient) {
      throw new Error("@larksuiteoapi/node-sdk does not expose EventDispatcher or WSClient");
    }

    const eventDispatcher = new EventDispatcher({
      encryptKey: this.options.encryptKey,
      verificationToken: this.options.verificationToken,
    });
    eventDispatcher.register({
      "im.message.receive_v1": async (data: unknown) => {
        await handlers.onEvent({
          header: { event_type: "im.message.receive_v1" },
          event: data as FeishuEventEnvelope["event"],
        });
      },
    });

    const loggerLevelEnum = sdk.LoggerLevel as Record<string, unknown> | undefined;
    this.wsClient = new WSClient({
      appId: this.options.appId,
      appSecret: this.options.appSecret,
      domain: resolveSdkDomain(sdk, this.options.domain),
      loggerLevel: loggerLevelEnum?.info,
    });
    this.wsClient.start({ eventDispatcher });
  }

  async stop(): Promise<void> {
    this.wsClient?.close();
    this.wsClient = undefined;
  }

  async sendMessage(payload: FeishuSendPayload): Promise<void> {
    const token = await this.getTenantAccessToken();
    const baseUrl = resolveOpenApiBaseUrl(this.options.domain);
    const url = new URL(`/open-apis/im/v1/messages`, `${baseUrl}/`);
    url.searchParams.set("receive_id_type", payload.receiveIdType);
    const response = await this.fetchImpl(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        receive_id: payload.receiveId,
        msg_type: payload.msgType,
        content: payload.content,
      }),
    });
    const data = (await response.json().catch(() => null)) as { code?: number; msg?: string } | null;
    if (!response.ok || data?.code !== 0) {
      throw new Error(`Feishu send message failed: ${data?.msg || response.statusText || response.status}`);
    }
  }

  private async getTenantAccessToken(): Promise<string> {
    const now = Date.now();
    if (this.tokenCache && this.tokenCache.expiresAt > now + 300_000) {
      return this.tokenCache.token;
    }

    const baseUrl = resolveOpenApiBaseUrl(this.options.domain);
    const response = await this.fetchImpl(new URL("/open-apis/auth/v3/tenant_access_token/internal", `${baseUrl}/`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        app_id: this.options.appId,
        app_secret: this.options.appSecret,
      }),
    });
    const data = (await response.json().catch(() => null)) as
      | { code?: number; msg?: string; tenant_access_token?: string; expire?: number }
      | null;
    if (!response.ok || data?.code !== 0 || !data.tenant_access_token) {
      throw new Error(`Feishu token request failed: ${data?.msg || response.statusText || response.status}`);
    }

    this.tokenCache = {
      token: data.tenant_access_token,
      expiresAt: now + Math.max(Number(data.expire || 7200) - 60, 60) * 1000,
    };
    return this.tokenCache.token;
  }
}

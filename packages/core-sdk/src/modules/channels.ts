import type { HttpClient } from "../client/http-client.js";

export type ChannelKey =
  | "wechat_work"
  | "feishu"
  | "wechat_personal_plugin"
  | "wechat_personal_openclaw";
export type ChannelGroup = "enterprise_collab" | "personal_reach";
export type ChannelKernel =
  | "wechat_work"
  | "feishu"
  | "wechat_work_plugin"
  | "openclaw_wechat_plugin";

export interface ChannelConfigItem {
  channelKey: ChannelKey;
  channelName: string;
  channelGroup: ChannelGroup;
  channelKernel: ChannelKernel;
  configured: boolean;
  enabled: boolean;
  bindingEnabled: boolean;
  callbackUrl: string;
  riskLevel: string;
  updatedTime?: string | null;
}

export interface ChannelOverview {
  supportedCount: number;
  configuredCount: number;
  activeCount: number;
  items: ChannelConfigItem[];
}

export interface WechatWorkChannelConfig extends ChannelConfigItem {
  corpId: string;
  agentId: string;
  secret: string;
  secretConfigured: boolean;
  verifyToken: string;
  aesKey: string;
}

export interface FeishuChannelConfig extends ChannelConfigItem {
  appId: string;
  appSecret: string;
  verificationToken: string;
  encryptKey: string;
  secretConfigured: boolean;
}

export interface WechatPersonalPluginChannelConfig extends ChannelConfigItem {
  displayName: string;
  kernelSource: "unconfigured" | "independent";
  kernelConfigured: boolean;
  kernelIsolated: boolean;
  kernelCorpId: string;
  kernelAgentId: string;
  kernelSecret: string;
  kernelSecretConfigured: boolean;
  kernelVerifyToken: string;
  kernelAesKey: string;
  effectiveKernelCorpId: string;
  effectiveKernelAgentId: string;
  effectiveKernelVerifyToken: string;
  effectiveKernelAesKey: string;
  setupStatus: "planned" | "beta" | "active";
  assistantName: string;
  welcomeMessage: string;
  capabilityStage: string;
}

export interface WechatPersonalOpenClawChannelConfig extends ChannelConfigItem {
  displayName: string;
  channelMode: "official_openclaw_plugin";
  setupStatus: "ready" | "waiting_gateway" | "waiting_plugin";
  manualCliRequired: boolean;
  preinstallSupported: boolean;
  qrSupported: boolean;
  gatewayOnline: boolean;
  officialPluginAvailable?: boolean | null;
  installHint: string;
  capabilityStage: string;
}

export interface ChannelBindingIdentitySnapshot {
  id: number;
  externalUserId: string;
  externalUnionId?: string | null;
  nickname?: string | null;
  avatarUrl?: string | null;
  status: string;
  lastSeenAt?: string | null;
}

export interface ChannelBindingRecord {
  id: number;
  teamId: number;
  channelKey: ChannelKey;
  bindingType: string;
  bindingTargetId: string;
  bindingTargetName?: string | null;
  bindingCode: string;
  codeExpiresAt?: string | null;
  status: string;
  createdByUserId?: number | null;
  boundByUserId?: number | null;
  bindingEnabledSnapshot: boolean;
  notes?: string | null;
  boundAt?: string | null;
  createdTime?: string | null;
  updatedTime?: string | null;
  identity?: ChannelBindingIdentitySnapshot | null;
}

export interface UpdateWechatWorkChannelInput {
  teamId: number;
  corpId: string;
  agentId: string;
  secret?: string;
}

export interface UpdateFeishuChannelInput {
  teamId: number;
  appId: string;
  appSecret?: string;
  verificationToken?: string;
  encryptKey?: string;
}

export interface UpdateWechatPersonalPluginChannelInput {
  teamId: number;
  displayName: string;
  assistantName?: string;
  welcomeMessage?: string;
  kernelCorpId?: string;
  kernelAgentId?: string;
  kernelSecret?: string;
  kernelVerifyToken?: string;
  kernelAesKey?: string;
  bindingEnabled?: boolean;
  enabled?: boolean;
}

export interface CreateChannelBindingInput {
  teamId: number;
  channelKey?: ChannelKey;
  bindingType: string;
  bindingTargetId: string;
  bindingTargetName?: string;
  expiresInHours?: number;
  notes?: string;
}

export interface StartWechatPersonalOpenClawQrInput {
  teamId: number;
  forceRefresh?: boolean;
  timeoutMs?: number;
  accountId?: string;
}

export interface GetWechatPersonalOpenClawQrStatusInput {
  teamId: number;
  sessionId?: string;
  accountId?: string;
}

export interface WechatPersonalOpenClawQrSession {
  status: string;
  message: string;
  qrDataUrl: string;
  qrUrl: string;
  sessionId: string;
  accountId: string;
  expiresAt?: string | null;
  connected: boolean;
  binding?: ChannelBindingRecord | null;
  raw?: unknown;
}

interface RawChannelConfigItem {
  channel_key: ChannelKey;
  channel_name: string;
  channel_group: ChannelGroup;
  channel_kernel: ChannelKernel;
  configured: boolean;
  enabled: boolean;
  binding_enabled: boolean;
  callback_url: string;
  risk_level: string;
  updated_time?: string | null;
}

interface RawChannelOverview {
  supported_count: number;
  configured_count: number;
  active_count: number;
  items: RawChannelConfigItem[];
}

interface RawWechatWorkChannelConfig extends RawChannelConfigItem {
  corp_id: string;
  agent_id: string;
  secret: string;
  secret_configured: boolean;
  verify_token: string;
  aes_key: string;
}

interface RawFeishuChannelConfig extends RawChannelConfigItem {
  app_id: string;
  app_secret: string;
  verification_token: string;
  encrypt_key: string;
  secret_configured: boolean;
}

interface RawWechatPersonalPluginChannelConfig extends RawChannelConfigItem {
  display_name: string;
  kernel_source: "unconfigured" | "independent";
  kernel_configured: boolean;
  kernel_isolated: boolean;
  kernel_corp_id: string;
  kernel_agent_id: string;
  kernel_secret: string;
  kernel_secret_configured: boolean;
  kernel_verify_token: string;
  kernel_aes_key: string;
  effective_kernel_corp_id: string;
  effective_kernel_agent_id: string;
  effective_kernel_verify_token: string;
  effective_kernel_aes_key: string;
  setup_status: "planned" | "beta" | "active";
  assistant_name: string;
  welcome_message: string;
  capability_stage: string;
}

interface RawWechatPersonalOpenClawChannelConfig extends RawChannelConfigItem {
  display_name: string;
  channel_mode: "official_openclaw_plugin";
  setup_status: "ready" | "waiting_gateway" | "waiting_plugin";
  manual_cli_required: boolean;
  preinstall_supported: boolean;
  qr_supported: boolean;
  gateway_online: boolean;
  official_plugin_available?: boolean | null;
  install_hint: string;
  capability_stage: string;
}

interface RawChannelBindingIdentitySnapshot {
  id: number;
  external_user_id: string;
  external_union_id?: string | null;
  nickname?: string | null;
  avatar_url?: string | null;
  status: string;
  last_seen_at?: string | null;
}

interface RawChannelBindingRecord {
  id: number;
  team_id: number;
  channel_key: ChannelKey;
  binding_type: string;
  binding_target_id: string;
  binding_target_name?: string | null;
  binding_code: string;
  code_expires_at?: string | null;
  status: string;
  created_by_user_id?: number | null;
  bound_by_user_id?: number | null;
  binding_enabled_snapshot: boolean;
  notes?: string | null;
  bound_at?: string | null;
  created_time?: string | null;
  updated_time?: string | null;
  identity?: RawChannelBindingIdentitySnapshot | null;
}

interface RawChannelBindingList {
  items: RawChannelBindingRecord[];
  total: number;
}

interface RawWechatPersonalOpenClawQrSession {
  status: string;
  message?: string;
  qr_data_url?: string;
  qr_url?: string;
  session_id?: string;
  account_id?: string;
  expires_at?: string | null;
  connected?: boolean;
  binding?: RawChannelBindingRecord | null;
  raw?: unknown;
}

function mapChannelItem(value: RawChannelConfigItem): ChannelConfigItem {
  return {
    channelKey: value.channel_key,
    channelName: value.channel_name,
    channelGroup: value.channel_group,
    channelKernel: value.channel_kernel,
    configured: value.configured,
    enabled: value.enabled,
    bindingEnabled: value.binding_enabled,
    callbackUrl: value.callback_url,
    riskLevel: value.risk_level,
    updatedTime: value.updated_time,
  };
}

function mapWechatWorkConfig(value: RawWechatWorkChannelConfig): WechatWorkChannelConfig {
  return {
    ...mapChannelItem(value),
    corpId: value.corp_id,
    agentId: value.agent_id,
    secret: value.secret,
    secretConfigured: value.secret_configured,
    verifyToken: value.verify_token,
    aesKey: value.aes_key,
  };
}

function mapFeishuConfig(value: RawFeishuChannelConfig): FeishuChannelConfig {
  return {
    ...mapChannelItem(value),
    appId: value.app_id,
    appSecret: value.app_secret,
    verificationToken: value.verification_token,
    encryptKey: value.encrypt_key,
    secretConfigured: value.secret_configured,
  };
}

function mapWechatPersonalPluginConfig(
  value: RawWechatPersonalPluginChannelConfig,
): WechatPersonalPluginChannelConfig {
  return {
    ...mapChannelItem(value),
    displayName: value.display_name,
    kernelSource: value.kernel_source,
    kernelConfigured: value.kernel_configured,
    kernelIsolated: value.kernel_isolated,
    kernelCorpId: value.kernel_corp_id,
    kernelAgentId: value.kernel_agent_id,
    kernelSecret: value.kernel_secret,
    kernelSecretConfigured: value.kernel_secret_configured,
    kernelVerifyToken: value.kernel_verify_token,
    kernelAesKey: value.kernel_aes_key,
    effectiveKernelCorpId: value.effective_kernel_corp_id,
    effectiveKernelAgentId: value.effective_kernel_agent_id,
    effectiveKernelVerifyToken: value.effective_kernel_verify_token,
    effectiveKernelAesKey: value.effective_kernel_aes_key,
    setupStatus: value.setup_status,
    assistantName: value.assistant_name,
    welcomeMessage: value.welcome_message,
    capabilityStage: value.capability_stage,
  };
}

function mapWechatPersonalOpenClawConfig(
  value: RawWechatPersonalOpenClawChannelConfig,
): WechatPersonalOpenClawChannelConfig {
  return {
    ...mapChannelItem(value),
    displayName: value.display_name,
    channelMode: value.channel_mode,
    setupStatus: value.setup_status,
    manualCliRequired: value.manual_cli_required,
    preinstallSupported: value.preinstall_supported,
    qrSupported: value.qr_supported,
    gatewayOnline: value.gateway_online,
    officialPluginAvailable: value.official_plugin_available ?? null,
    installHint: value.install_hint,
    capabilityStage: value.capability_stage,
  };
}

function mapChannelBindingIdentity(
  value: RawChannelBindingIdentitySnapshot,
): ChannelBindingIdentitySnapshot {
  return {
    id: value.id,
    externalUserId: value.external_user_id,
    externalUnionId: value.external_union_id,
    nickname: value.nickname,
    avatarUrl: value.avatar_url,
    status: value.status,
    lastSeenAt: value.last_seen_at,
  };
}

function mapChannelBindingRecord(value: RawChannelBindingRecord): ChannelBindingRecord {
  return {
    id: value.id,
    teamId: value.team_id,
    channelKey: value.channel_key,
    bindingType: value.binding_type,
    bindingTargetId: value.binding_target_id,
    bindingTargetName: value.binding_target_name,
    bindingCode: value.binding_code,
    codeExpiresAt: value.code_expires_at,
    status: value.status,
    createdByUserId: value.created_by_user_id,
    boundByUserId: value.bound_by_user_id,
    bindingEnabledSnapshot: value.binding_enabled_snapshot,
    notes: value.notes,
    boundAt: value.bound_at,
    createdTime: value.created_time,
    updatedTime: value.updated_time,
    identity: value.identity ? mapChannelBindingIdentity(value.identity) : null,
  };
}

function mapWechatPersonalOpenClawQrSession(
  value: RawWechatPersonalOpenClawQrSession,
): WechatPersonalOpenClawQrSession {
  return {
    status: value.status,
    message: value.message || "",
    qrDataUrl: value.qr_data_url || "",
    qrUrl: value.qr_url || "",
    sessionId: value.session_id || "",
    accountId: value.account_id || "",
    expiresAt: value.expires_at,
    connected: Boolean(value.connected),
    binding: value.binding ? mapChannelBindingRecord(value.binding) : null,
    raw: value.raw,
  };
}

export class ChannelsModule {
  constructor(private readonly http: HttpClient) {}

  async getOverview(teamId: number): Promise<ChannelOverview> {
    const result = await this.http.request<RawChannelOverview>({
      method: "GET",
      path: "/api/platform/channels",
      query: {
        team_id: teamId,
      },
    });
    return {
      supportedCount: result.supported_count,
      configuredCount: result.configured_count,
      activeCount: result.active_count,
      items: result.items.map(mapChannelItem),
    };
  }

  async list(teamId: number): Promise<ChannelConfigItem[]> {
    const result = await this.getOverview(teamId);
    return result.items;
  }

  async getWechatWorkConfig(teamId: number): Promise<WechatWorkChannelConfig> {
    const result = await this.http.request<RawWechatWorkChannelConfig>({
      method: "GET",
      path: "/api/platform/channels/wechat-work/config",
      query: {
        team_id: teamId,
      },
    });
    return mapWechatWorkConfig(result);
  }

  async updateWechatWorkConfig(payload: UpdateWechatWorkChannelInput): Promise<WechatWorkChannelConfig> {
    const result = await this.http.request<RawWechatWorkChannelConfig>({
      method: "POST",
      path: "/api/platform/channels/wechat-work/config",
      body: {
        team_id: payload.teamId,
        corp_id: payload.corpId,
        agent_id: payload.agentId,
        secret: payload.secret,
      },
    });
    return mapWechatWorkConfig(result);
  }

  async getFeishuConfig(teamId: number): Promise<FeishuChannelConfig> {
    const result = await this.http.request<RawFeishuChannelConfig>({
      method: "GET",
      path: "/api/platform/channels/feishu/config",
      query: {
        team_id: teamId,
      },
    });
    return mapFeishuConfig(result);
  }

  async updateFeishuConfig(payload: UpdateFeishuChannelInput): Promise<FeishuChannelConfig> {
    const result = await this.http.request<RawFeishuChannelConfig>({
      method: "POST",
      path: "/api/platform/channels/feishu/config",
      body: {
        team_id: payload.teamId,
        app_id: payload.appId,
        app_secret: payload.appSecret,
        verification_token: payload.verificationToken,
        encrypt_key: payload.encryptKey,
      },
    });
    return mapFeishuConfig(result);
  }

  async getWechatPersonalPluginConfig(teamId: number): Promise<WechatPersonalPluginChannelConfig> {
    const result = await this.http.request<RawWechatPersonalPluginChannelConfig>({
      method: "GET",
      path: "/api/platform/channels/wechat-personal-plugin/config",
      query: {
        team_id: teamId,
      },
    });
    return mapWechatPersonalPluginConfig(result);
  }

  async updateWechatPersonalPluginConfig(
    payload: UpdateWechatPersonalPluginChannelInput,
  ): Promise<WechatPersonalPluginChannelConfig> {
    const result = await this.http.request<RawWechatPersonalPluginChannelConfig>({
      method: "POST",
      path: "/api/platform/channels/wechat-personal-plugin/config",
      body: {
        team_id: payload.teamId,
        display_name: payload.displayName,
        assistant_name: payload.assistantName,
        welcome_message: payload.welcomeMessage,
        kernel_corp_id: payload.kernelCorpId,
        kernel_agent_id: payload.kernelAgentId,
        kernel_secret: payload.kernelSecret,
        kernel_verify_token: payload.kernelVerifyToken,
        kernel_aes_key: payload.kernelAesKey,
        binding_enabled: payload.bindingEnabled,
        enabled: payload.enabled,
      },
    });
    return mapWechatPersonalPluginConfig(result);
  }

  async getWechatPersonalOpenClawConfig(
    teamId: number,
  ): Promise<WechatPersonalOpenClawChannelConfig> {
    const result = await this.http.request<RawWechatPersonalOpenClawChannelConfig>({
      method: "GET",
      path: "/api/platform/channels/wechat-personal-openclaw/config",
      query: {
        team_id: teamId,
      },
    });
    return mapWechatPersonalOpenClawConfig(result);
  }

  async startWechatPersonalOpenClawQr(
    payload: StartWechatPersonalOpenClawQrInput,
  ): Promise<WechatPersonalOpenClawQrSession> {
    const result = await this.http.request<RawWechatPersonalOpenClawQrSession>({
      method: "POST",
      path: "/api/platform/channels/wechat-personal-openclaw/qr/start",
      body: {
        team_id: payload.teamId,
        force_refresh: payload.forceRefresh,
        timeout_ms: payload.timeoutMs,
        account_id: payload.accountId,
      },
    });
    return mapWechatPersonalOpenClawQrSession(result);
  }

  async getWechatPersonalOpenClawQrStatus(
    payload: GetWechatPersonalOpenClawQrStatusInput,
  ): Promise<WechatPersonalOpenClawQrSession> {
    const result = await this.http.request<RawWechatPersonalOpenClawQrSession>({
      method: "GET",
      path: "/api/platform/channels/wechat-personal-openclaw/qr/status",
      query: {
        team_id: payload.teamId,
        session_id: payload.sessionId,
        account_id: payload.accountId,
      },
    });
    return mapWechatPersonalOpenClawQrSession(result);
  }

  async listChannelBindings(
    teamId: number,
    channelKey: ChannelKey = "wechat_personal_plugin",
  ): Promise<{ items: ChannelBindingRecord[]; total: number }> {
    const result = await this.http.request<RawChannelBindingList>({
      method: "GET",
      path: "/api/platform/channels/bindings",
      query: {
        team_id: teamId,
        channel_key: channelKey,
      },
    });
    return {
      items: result.items.map(mapChannelBindingRecord),
      total: result.total,
    };
  }

  async createChannelBinding(payload: CreateChannelBindingInput): Promise<ChannelBindingRecord> {
    const result = await this.http.request<RawChannelBindingRecord>({
      method: "POST",
      path: "/api/platform/channels/bindings/create",
      body: {
        team_id: payload.teamId,
        channel_key: payload.channelKey ?? "wechat_personal_plugin",
        binding_type: payload.bindingType,
        binding_target_id: payload.bindingTargetId,
        binding_target_name: payload.bindingTargetName,
        expires_in_hours: payload.expiresInHours,
        notes: payload.notes,
      },
    });
    return mapChannelBindingRecord(result);
  }

  async disableChannelBinding(bindingId: number): Promise<ChannelBindingRecord> {
    const result = await this.http.request<RawChannelBindingRecord>({
      method: "POST",
      path: "/api/platform/channels/bindings/disable",
      body: {
        binding_id: bindingId,
      },
    });
    return mapChannelBindingRecord(result);
  }

  async regenerateChannelBindingCode(
    bindingId: number,
    expiresInHours = 72,
  ): Promise<ChannelBindingRecord> {
    const result = await this.http.request<RawChannelBindingRecord>({
      method: "POST",
      path: "/api/platform/channels/bindings/regenerate-code",
      body: {
        binding_id: bindingId,
        expires_in_hours: expiresInHours,
      },
    });
    return mapChannelBindingRecord(result);
  }
}

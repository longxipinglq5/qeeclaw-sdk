export interface SidecarAuthState {
  userToken?: string;
  deviceKey?: string;
  sidecarAuthToken?: string;
  authMode?: string;
  deviceId?: number;
  installationId?: string;
  updatedAt?: string;
}

export interface SidecarConfig {
  controlPlaneBaseUrl: string;
  localGatewayWsUrl: string;
  sidecarHost: string;
  sidecarPort: number;
  sidecarAuthToken?: string;
  gatewayAuthToken?: string;
  gatewayAuthPassword?: string;
  allowRemoteAccess: boolean;
  startGatewayOnBoot: boolean;
  startBridgeOnBoot?: boolean;
  autoBootstrapDevice: boolean;
  stateRootDir: string;
  stateFilePath: string;
  gatewayCommand?: string;
  gatewayArgs: string[];
  gatewayWorkingDir?: string;
  bridgeEntryPath?: string;
  gatewayPidFilePath: string;
  bridgePidFilePath?: string;
  knowledgeConfigFilePath: string;
  approvalsCacheFilePath: string;
  channelSecretsFilePath: string;
  channelAttachmentDirPath: string;
  channelRuntimeMode: "gateway" | "echo";
  deviceName: string;
  hostname: string;
  osInfo: string;
}

export interface PlatformAccountDeviceState {
  installation_id: string;
  state: "current_user" | "other_user" | "unregistered";
  can_register_current_account: boolean;
  current_user_device_id?: number | null;
  current_user_has_devices: boolean;
}

export interface BootstrapDeviceResult {
  api_key: string;
  base_url: string;
  ws_url: string;
  device_id: number;
  device_name: string;
}

export interface PolicyDecision {
  allowed: boolean;
  reason: string;
  matchedPolicy: string;
  requiresApproval: boolean;
  source: "sidecar-local" | "control-plane";
  checkedAt: string;
}

export interface ApprovalRecord {
  approvalId: string;
  status: "pending" | "approved" | "rejected" | "expired";
  approvalType: "tool_access" | "data_access" | "exec_access" | "custom";
  title: string;
  reason: string;
  riskLevel: "low" | "medium" | "high" | "critical";
  payload: Record<string, unknown>;
  requestedBy: {
    userId: number;
    username: string;
  };
  resolvedBy?: {
    userId: number;
    username: string;
  } | null;
  resolutionComment?: string | null;
  createdAt: string;
  expiresAt: string;
  resolvedAt?: string | null;
}

export interface ApprovalListResult {
  total: number;
  page: number;
  pageSize: number;
  items: ApprovalRecord[];
}

export interface GatewayAdapterStatus {
  configured: boolean;
  running: boolean;
  command?: string;
  args?: string[];
  workingDir?: string;
  pid?: number;
  bridgeEntryPath?: string;
  startedAt?: string;
}

export interface MemorySearchResult {
  id: string;
  content: string;
  category?: string;
  importance?: number;
  score?: number;
  device_id?: string | null;
  agent_id?: string | null;
  source_session?: string | null;
  created_time?: string | null;
}

export interface KnowledgeInventoryItem {
  relativePath: string;
  absolutePath: string;
  size: number;
  modifiedAt: string;
  extension: string;
}

export interface KnowledgeConfig {
  watchDir?: string;
  lastSyncedAt?: string;
  inventoryCount: number;
  items: KnowledgeInventoryItem[];
}

export interface SyncResult {
  installationId: string;
  authMode: string;
  hasUserToken: boolean;
  hasDeviceKey: boolean;
  bootstrapPerformed: boolean;
  deviceId?: number;
  accountState?: PlatformAccountDeviceState;
}

export interface SidecarHealth {
  status: "ok";
  config: {
    controlPlaneBaseUrl: string;
    sidecarHost: string;
    sidecarPort: number;
    authRequired: boolean;
    allowRemoteAccess: boolean;
    startGatewayOnBoot: boolean;
    startBridgeOnBoot: boolean;
    autoBootstrapDevice: boolean;
  };
  auth: {
    installationId?: string;
    authMode?: string;
    hasUserToken: boolean;
    hasDeviceKey: boolean;
    sidecarAuthTokenConfigured: boolean;
    deviceId?: number;
  };
  gateway: GatewayAdapterStatus;
  channels?: ChannelManagerStatus;
}

export interface SidecarPublicAuthState {
  installationId?: string;
  authMode?: string;
  hasUserToken: boolean;
  hasDeviceKey: boolean;
  sidecarAuthTokenConfigured: boolean;
  deviceId?: number;
  updatedAt?: string;
}

export interface SidecarSelfCheck {
  status: "ok";
  checks: {
    gatewayConfigured: boolean;
    gatewayCommand?: string;
    gatewayArgs: string[];
    gatewayWorkingDir?: string;
    bridgeEntryPath?: string;
    gatewayCommandCheck: "not_configured" | "path_exists" | "path_missing" | "lookup_skipped";
    stateFilePath: string;
    stateRootDir: string;
    stateDirPath: string;
    stateDirWritable: boolean;
    stateDirWritableHint?: string;
    knowledgeConfigPath: string;
    approvalsCachePath: string;
    channelSecretsPath: string;
    channelAttachmentDirPath: string;
  };
  auth: {
    installationId?: string;
    authMode?: string;
    hasUserToken: boolean;
    hasDeviceKey: boolean;
    sidecarAuthTokenConfigured: boolean;
    deviceId?: number;
  };
  gateway: GatewayAdapterStatus;
  knowledge: KnowledgeConfig;
  channels?: ChannelManagerStatus;
}

export type ChannelKey = "feishu" | "wechat_work" | "wechat_personal";

export type ChannelChatType = "dm" | "group";

export type ChannelAttachmentType = "image" | "file" | "voice" | "video";

export interface ChannelAttachment {
  id?: string;
  type: ChannelAttachmentType;
  name?: string;
  mimeType?: string;
  sizeBytes?: number;
  localPath?: string;
  dataBase64?: string;
  remoteUrl?: string;
  rawMeta?: Record<string, unknown>;
}

export interface ChannelMessage {
  channel: ChannelKey;
  messageId: string;
  chatId: string;
  chatType: ChannelChatType;
  senderId: string;
  senderName?: string;
  text?: string;
  attachments: ChannelAttachment[];
  rawMeta?: Record<string, unknown>;
  receivedAt: string;
}

export interface ChannelReply {
  text?: string;
  attachments?: ChannelAttachment[];
  rawMeta?: Record<string, unknown>;
}

export interface ChannelAdapterStatus {
  channel: ChannelKey;
  configured: boolean;
  running: boolean;
  mode: "local_bridge";
  lastMessageAt?: string;
  lastError?: string;
}

export interface ChannelManagerStatus {
  running: boolean;
  adapters: ChannelAdapterStatus[];
}

export interface ChannelRouteResult {
  accepted: boolean;
  duplicate: boolean;
  messageId: string;
  channel: ChannelKey;
  reply?: ChannelReply;
}

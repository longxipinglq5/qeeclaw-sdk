export interface PaginatedResult<T> {
  total: number;
  page: number;
  pageSize: number;
  items: T[];
}

export interface ProductDeviceInfo {
  id: number;
  deviceName: string;
  hostname?: string | null;
  osInfo?: string | null;
  status: string;
  lastSeen?: string | null;
  createdTime?: string | null;
  teamId?: number;
  registrationMode?: string | null;
  installationId?: string | null;
}

export interface ProductDeviceAccountState {
  installationId: string;
  state: "current_user" | "other_user" | "unregistered";
  canRegisterCurrentAccount: boolean;
  currentUserDeviceId?: number | null;
  currentUserHasDevices: boolean;
}

export interface ProductDeviceConnectionConfig {
  apiKey: string;
  baseUrl: string;
  wsUrl: string;
  deviceId: number;
  deviceName: string;
  installationId?: string;
  registrationMode?: string;
}

export interface ProductApprovalRecord {
  approvalId: string;
  status: "pending" | "approved" | "rejected" | "expired";
  approvalType: "tool_access" | "data_access" | "exec_access" | "custom";
  title: string;
  reason: string;
  riskLevel: "low" | "medium" | "high" | "critical";
  payload: Record<string, unknown>;
  createdAt: string;
  expiresAt: string;
  resolvedAt?: string | null;
}

export interface ProductAuditEvent {
  eventId: string;
  category: "operation" | "approval";
  eventType: string;
  title: string;
  summary?: string | null;
  status?: string | null;
  riskLevel?: string | null;
  createdAt?: string | null;
}

export interface ProductAuditSummary {
  total: number;
  operationCount: number;
  approvalCount: number;
  pendingApprovalCount: number;
  approvedApprovalCount: number;
  rejectedApprovalCount: number;
  expiredApprovalCount: number;
}

export interface ProductConversationStats {
  groupCount: number;
  msgCount: number;
  entityCount: number;
  historyCount?: number;
}

export interface ProductConversationGroup {
  roomId: string;
  roomName: string;
  lastActive?: string | null;
  msgCount: number;
  memberCount: number;
}

export interface ProductConversationEntity {
  type: string;
  value: string;
  confidence?: number;
}

export interface ProductConversationGroupMessage {
  id: number;
  senderName?: string | null;
  senderRole?: string | null;
  msgType?: string | null;
  content?: string | null;
  createdTime?: string | null;
  entities: ProductConversationEntity[];
}

export interface ProductConversationHistoryMessage {
  id: number;
  senderId?: number | null;
  agentId?: number | null;
  channelId?: string | null;
  direction: string;
  content?: string | null;
  createdTime?: string | null;
}

export interface ProductConversationHome {
  stats: ProductConversationStats;
  groups: ProductConversationGroup[];
  history: ProductConversationHistoryMessage[];
}

export interface ProductChannelConfigItem {
  channelKey: "wechat_work" | "feishu" | "wechat_personal_plugin";
  channelName: string;
  channelGroup: "enterprise_collab" | "personal_reach";
  channelKernel: "wechat_work" | "feishu" | "wechat_work_plugin";
  configured: boolean;
  enabled: boolean;
  bindingEnabled: boolean;
  callbackUrl: string;
  riskLevel: string;
  updatedTime?: string | null;
}

export interface ProductChannelOverview {
  supportedCount: number;
  configuredCount: number;
  activeCount: number;
  items: ProductChannelConfigItem[];
}

export interface ProductWechatWorkChannelConfig extends ProductChannelConfigItem {
  corpId: string;
  agentId: string;
  secret: string;
  secretConfigured: boolean;
  verifyToken: string;
  aesKey: string;
}

export interface ProductFeishuChannelConfig extends ProductChannelConfigItem {
  appId: string;
  appSecret: string;
  verificationToken: string;
  encryptKey: string;
  secretConfigured: boolean;
}

export interface ProductWechatPersonalPluginChannelConfig extends ProductChannelConfigItem {
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

export interface ProductChannelBindingIdentitySnapshot {
  id: number;
  externalUserId: string;
  externalUnionId?: string | null;
  nickname?: string | null;
  avatarUrl?: string | null;
  status: string;
  lastSeenAt?: string | null;
}

export interface ProductChannelBindingRecord {
  id: number;
  teamId: number;
  channelKey: "wechat_work" | "feishu" | "wechat_personal_plugin";
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
  identity?: ProductChannelBindingIdentitySnapshot | null;
}

export interface ProductChannelHome {
  overview: ProductChannelOverview;
  wechatWork: ProductWechatWorkChannelConfig;
  feishu: ProductFeishuChannelConfig;
  wechatPersonalPlugin: ProductWechatPersonalPluginChannelConfig;
}

export interface ProductWalletSummary {
  balance: number;
  currency: string;
  totalSpent: number;
  totalRecharge: number;
  currentMonthSpent: number;
  updatedTime: string;
}

export interface ProductBillingSummary {
  totalSpent: number;
  totalRecharge: number;
}

export interface ProductUserProfile {
  id: number;
  username: string;
  fullName?: string | null;
  email?: string | null;
  phone?: string | null;
  role: string;
  isActive: boolean;
  createdTime: string;
  walletBalance: number;
  isEnterpriseVerified: boolean;
  teams: Array<{
    id: number;
    name: string;
    isPersonal: boolean;
    ownerId: number;
  }>;
}

export interface ProductUserProduct {
  id: number;
  name: string;
  description?: string | null;
  unitPrice: number;
  outputUnitPrice?: number | null;
  currency: string;
  billingMode?: string | null;
  docId?: number | null;
  labels?: string | null;
  isActive: boolean;
}

export interface ProductTenantContext {
  userId: number;
  username: string;
  role: string;
  isEnterpriseVerified: boolean;
  teams: Array<{
    id: number;
    name: string;
    isPersonal?: boolean;
    ownerId?: number;
  }>;
}

export interface ProductCompanyVerification {
  status: "none" | "pending" | "approved" | "rejected";
  companyName?: string | null;
  updatedTime?: string | null;
}

export interface ProductPlatformDocument {
  id: number;
  documentTitle: string;
  documentDetail?: string | null;
  sortNum: number;
  labels?: string | null;
  createTime: string;
  updateTime: string;
}

export interface ProductWorkflow {
  id: string;
  name: string;
  description?: string | null;
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
  enabled: boolean;
}

export interface ProductWorkflowRunResult {
  executionId: string;
}

export interface ProductAgentToolDefinition {
  name: string;
  description?: string | null;
  inputSchema: {
    type: string;
    properties: Record<string, unknown>;
    required?: string[];
  };
  tags: string[];
}

export interface ProductMyAgent {
  id: number;
  name: string;
  code: string;
  description?: string | null;
  avatar?: string | null;
  voiceId?: string | null;
  runtimeType?: string | null;
  runtimeLabel?: string | null;
  model?: string | null;
}

export interface ProductAgentTemplate {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  avatar?: string | null;
  allowedTools: string[];
}

export interface ProductRuntimeKnowledgeScope {
  teamId: number;
  deviceId?: number;
  runtimeType?: string | null;
  agentId?: string | null;
}

export interface ProductSdkClient {
  billing: {
    getWallet(): Promise<ProductWalletSummary>;
    getSummary(): Promise<ProductBillingSummary>;
  };
  iam: {
    getProfile(): Promise<ProductUserProfile>;
    listProducts(): Promise<ProductUserProduct[]>;
  };
  tenant: {
    getCurrentContext(): Promise<ProductTenantContext>;
    getCompanyVerification(): Promise<ProductCompanyVerification>;
  };
  file: {
    listDocuments(params?: { skip?: number; limit?: number }): Promise<ProductPlatformDocument[]>;
    getDocument(documentId: number): Promise<ProductPlatformDocument>;
  };
  workflow: {
    list(): Promise<ProductWorkflow[]>;
    run(workflowId: string, payload?: Record<string, unknown>): Promise<ProductWorkflowRunResult>;
    getExecutionLogs(executionId: string): Promise<string[]>;
  };
  agent: {
    listTools(): Promise<ProductAgentToolDefinition[]>;
    listMyAgents(): Promise<ProductMyAgent[]>;
    listDefaultTemplates(): Promise<ProductAgentTemplate[]>;
  };
  devices: {
    list(): Promise<ProductDeviceInfo[]>;
    getAccountState(installationId: string): Promise<ProductDeviceAccountState>;
    bootstrap(payload: {
      installationId: string;
      deviceName: string;
      hostname?: string;
      osInfo?: string;
    }): Promise<ProductDeviceConnectionConfig>;
  };
  knowledge: {
    list(payload: ProductRuntimeKnowledgeScope & { page?: number; pageSize?: number }): Promise<Record<string, unknown>>;
    search(payload: ProductRuntimeKnowledgeScope & { query?: string; filename?: string; limit?: number }): Promise<Record<string, unknown>>;
    ingest(payload: ProductRuntimeKnowledgeScope & {
      file?: Blob | Uint8Array | ArrayBuffer;
      filename?: string;
      contentType?: string;
      content?: string;
      sourceName?: string;
    }): Promise<Record<string, unknown>>;
    getConfig(payload: ProductRuntimeKnowledgeScope): Promise<Record<string, unknown>>;
    updateConfig(payload: ProductRuntimeKnowledgeScope & { watchDir: string }): Promise<Record<string, unknown>>;
    stats(payload: ProductRuntimeKnowledgeScope): Promise<Record<string, unknown>>;
  };
  approval: {
    list(params?: {
      scope?: "mine" | "all";
      status?: "pending" | "approved" | "rejected" | "expired";
      page?: number;
      pageSize?: number;
    }): Promise<PaginatedResult<ProductApprovalRecord>>;
  };
  audit: {
    listEvents(params?: {
      scope?: "mine" | "all";
      category?: "all" | "operation" | "approval";
      page?: number;
      pageSize?: number;
    }): Promise<PaginatedResult<ProductAuditEvent>>;
    getSummary(params?: {
      scope?: "mine" | "all";
      category?: "all" | "operation" | "approval";
    }): Promise<ProductAuditSummary>;
  };
  conversations: {
    getHome(teamId: number, groupLimit?: number, historyLimit?: number): Promise<ProductConversationHome>;
    getStats(teamId: number): Promise<ProductConversationStats>;
    listGroups(params: { teamId: number; limit?: number }): Promise<ProductConversationGroup[]>;
    listGroupMessages(params: { teamId: number; roomId: string; limit?: number }): Promise<ProductConversationGroupMessage[]>;
    listHistory(params: { teamId: number; channelId?: string; limit?: number }): Promise<ProductConversationHistoryMessage[]>;
    sendMessage(payload: {
      teamId: number;
      content: string;
      agentId?: number;
      channelId?: string;
      direction?: string;
    }): Promise<ProductConversationHistoryMessage>;
  };
  channels: {
    getOverview(teamId: number): Promise<ProductChannelOverview>;
    getWechatWorkConfig(teamId: number): Promise<ProductWechatWorkChannelConfig>;
    updateWechatWorkConfig(payload: {
      teamId: number;
      corpId: string;
      agentId: string;
      secret?: string;
    }): Promise<ProductWechatWorkChannelConfig>;
    getFeishuConfig(teamId: number): Promise<ProductFeishuChannelConfig>;
    updateFeishuConfig(payload: {
      teamId: number;
      appId: string;
      appSecret?: string;
      verificationToken?: string;
      encryptKey?: string;
    }): Promise<ProductFeishuChannelConfig>;
    getWechatPersonalPluginConfig(teamId: number): Promise<ProductWechatPersonalPluginChannelConfig>;
    updateWechatPersonalPluginConfig(payload: {
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
    }): Promise<ProductWechatPersonalPluginChannelConfig>;
    listChannelBindings(teamId: number, channelKey?: "wechat_work" | "feishu" | "wechat_personal_plugin"): Promise<{
      items: ProductChannelBindingRecord[];
      total: number;
    }>;
    createChannelBinding(payload: {
      teamId: number;
      channelKey?: "wechat_work" | "feishu" | "wechat_personal_plugin";
      bindingType: string;
      bindingTargetId: string;
      bindingTargetName?: string;
      expiresInHours?: number;
      notes?: string;
    }): Promise<ProductChannelBindingRecord>;
    disableChannelBinding(bindingId: number): Promise<ProductChannelBindingRecord>;
    regenerateChannelBindingCode(bindingId: number, expiresInHours?: number): Promise<ProductChannelBindingRecord>;
  };
}

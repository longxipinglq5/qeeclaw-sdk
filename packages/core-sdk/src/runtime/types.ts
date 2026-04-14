/**
 * QeeClaw Runtime Adapter — 多 Runtime 抽象层
 *
 * 定义 RuntimeAdapter 接口，使上层代码（core-sdk、前端）完全不感知
 * 底层使用的是 Hermes 还是 OpenClaw。
 *
 * 默认 Runtime 为 Hermes。OpenClaw 为可选打包项。
 */

// ---------------------------------------------------------------------------
// Runtime Type
// ---------------------------------------------------------------------------

/** 支持的 Runtime 类型 */
export type RuntimeType = "hermes" | "openclaw";

/** 默认 Runtime */
export const DEFAULT_RUNTIME: RuntimeType = "hermes";

// ---------------------------------------------------------------------------
// Capability Declaration
// ---------------------------------------------------------------------------

/** Runtime 能力声明 */
export interface RuntimeCapabilities {
  /** 是否支持流式响应 */
  supportsStreaming: boolean;
  /** 是否支持工具调用 (function calling) */
  supportsToolCalls: boolean;
  /** 是否支持记忆系统 */
  supportsMemory: boolean;
  /** 是否支持技能系统 */
  supportsSkills: boolean;
  /** 是否支持消息平台 Gateway */
  supportsGateway: boolean;
  /** 支持的 LLM 提供商列表 */
  supportedProviders: string[];
}

// ---------------------------------------------------------------------------
// Invoke Request / Result
// ---------------------------------------------------------------------------

/** 模型调用请求 */
export interface RuntimeInvokeRequest {
  /** 用户 prompt */
  prompt: string;
  /** 指定模型名（可选） */
  model?: string;
  /** 指定提供商（可选） */
  provider?: string;
  /** 最大 token 数 */
  maxTokens?: number;
  /** 温度参数 */
  temperature?: number;
  /** 系统 prompt（可选） */
  systemPrompt?: string;
  /** 请求超时毫秒数 */
  timeoutMs?: number;
}

/** 模型调用结果 */
export interface RuntimeInvokeResult {
  /** 生成的文本 */
  text: string;
  /** 实际使用的模型名 */
  model?: string;
  /** 实际使用的提供商名 */
  provider?: string;
  /** Token 用量统计 */
  usage?: {
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
  };
}

// ---------------------------------------------------------------------------
// Streaming
// ---------------------------------------------------------------------------

/** 流式响应块类型 */
export type RuntimeStreamChunkType = "text" | "tool_call" | "done" | "error";

/** 流式响应块 */
export interface RuntimeStreamChunk {
  type: RuntimeStreamChunkType;
  content?: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// Health Check
// ---------------------------------------------------------------------------

/** 健康检查结果 */
export interface RuntimeHealthCheck {
  ok: boolean;
  runtimeType: RuntimeType;
  message?: string;
  /** Runtime 版本号（如果可获取） */
  version?: string;
  /** 附加诊断信息 */
  details?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Gateway (消息平台)
// ---------------------------------------------------------------------------

/** Gateway 平台状态 */
export interface RuntimeGatewayStatus {
  running: boolean;
  pid?: number;
  platforms: string[];
  activePlatformCount: number;
  platformDetails?: GatewayPlatformDetail[];
}

/** 单个平台的运行状态详情 */
export interface GatewayPlatformDetail {
  name: string;
  state: "connected" | "disconnected" | "fatal" | "unknown";
  error?: string;
}

/** 支持的平台定义 */
export interface GatewaySupportedPlatform {
  id: string;
  name: string;
  authType: string;
  envVar: string;
}

/** 已配置的平台 */
export interface GatewayConfiguredPlatform {
  id: string;
  enabled: boolean;
  hasToken: boolean;
  hasHomeChannel: boolean;
}

/** Gateway 配置请求 */
export interface GatewayConfigureRequest {
  platform: string;
  credentials: Record<string, string>;
}

/** Gateway 操作结果 */
export interface GatewayOperationResult {
  status: string;
  pid?: number;
  error?: string;
}

// ---------------------------------------------------------------------------
// RuntimeAdapter Interface
// ---------------------------------------------------------------------------

/**
 * 核心接口：所有 Runtime 实现必须遵循此契约。
 *
 * - HermesAdapter：通过 Python 桥接 HTTP 服务调用 hermes-agent
 * - OpenClawAdapter：通过现有平台 API 调用（可选打包项）
 */
export interface RuntimeAdapter {
  /** 此 adapter 的 runtime 类型标识 */
  readonly type: RuntimeType;

  /** 获取此 runtime 的能力声明 */
  getCapabilities(): RuntimeCapabilities;

  /** 健康检查：验证 runtime 是否可用 */
  healthCheck(): Promise<RuntimeHealthCheck>;

  /** 调用模型（非流式） */
  invoke(request: RuntimeInvokeRequest): Promise<RuntimeInvokeResult>;

  /** 调用模型（流式，可选实现） */
  invokeStream?(request: RuntimeInvokeRequest): AsyncIterable<RuntimeStreamChunk>;

  /** 启动 runtime（如果需要启动子进程等） */
  start(): Promise<void>;

  /** 停止 runtime */
  stop(): Promise<void>;

  // ----- Gateway 方法（可选，当前仅 Hermes 支持） -----

  /** 获取 Gateway 运行状态 */
  getGatewayStatus?(): Promise<RuntimeGatewayStatus>;

  /** 获取支持的全部平台列表 */
  getSupportedPlatforms?(): Promise<GatewaySupportedPlatform[]>;

  /** 获取已配置的平台列表 */
  getConfiguredPlatforms?(): Promise<GatewayConfiguredPlatform[]>;

  /** 启动 Gateway */
  startGateway?(): Promise<GatewayOperationResult>;

  /** 停止 Gateway */
  stopGateway?(): Promise<GatewayOperationResult>;

  /** 配置平台凭证 */
  configureGateway?(request: GatewayConfigureRequest): Promise<GatewayOperationResult>;
}

// ---------------------------------------------------------------------------
// Resolver Options
// ---------------------------------------------------------------------------

/** RuntimeResolver 的配置选项 */
export interface RuntimeResolverOptions {
  /** 指定使用的 runtime 类型，不指定则使用默认值 (hermes) */
  preferredRuntime?: RuntimeType;
  /** Hermes bridge 服务的地址（默认 http://127.0.0.1:21747） */
  hermesBridgeUrl?: string;
  /** Hermes Python 可执行文件路径（默认自动检测） */
  hermesPythonPath?: string;
  /** hermes-agent 源码根目录（默认 vendor/hermes-agent） */
  hermesAgentDir?: string;
  /** OpenClaw 平台 API 地址（仅 openclaw runtime 使用） */
  openclawBaseUrl?: string;
  /** OpenClaw API Token */
  openclawToken?: string;
}

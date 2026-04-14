/**
 * Hermes 认证凭证映射
 *
 * 将 QeeClaw 平台的凭证体系映射到 hermes-agent 的 provider 配置。
 *
 * hermes-agent 的认证机制：
 * 1. 通过环境变量传递 API Key（如 OPENROUTER_API_KEY、GLM_API_KEY 等）
 * 2. 通过 ~/.hermes/config.yaml 配置默认 provider 和 model
 * 3. 通过 ~/.hermes/auth.json 持久化 OAuth 认证状态
 *
 * 我们的映射策略：
 * - QeeClaw 平台凭证 → 环境变量注入到 bridge 子进程
 * - 不修改 hermes 源码，所有适配在此文件完成
 */

// ---------------------------------------------------------------------------
// Provider 映射表
// ---------------------------------------------------------------------------

/**
 * QeeClaw 平台 provider 名称 → hermes-agent provider 名称映射。
 * hermes 使用的 provider id 在 hermes_cli/auth.py 的 PROVIDER_REGISTRY 中定义。
 */
export const PROVIDER_NAME_MAP: Record<string, string> = {
  // QeeClaw 名称        →  hermes provider id
  "ZHIPU":               "zai",
  "zhipu":               "zai",
  "glm":                 "zai",
  "GLM":                 "zai",
  "z.ai":                "zai",
  "openai":              "openai",
  "OPENAI":              "openai",
  "anthropic":           "anthropic",
  "ANTHROPIC":           "anthropic",
  "openrouter":          "openrouter",
  "OPENROUTER":          "openrouter",
  "moonshot":            "kimi-coding",
  "MOONSHOT":            "kimi-coding",
  "kimi":                "kimi-coding",
  "KIMI":                "kimi-coding",
  "minimax":             "minimax",
  "MINIMAX":             "minimax",
  "deepseek":            "deepseek",
  "DEEPSEEK":            "deepseek",
  "alibaba":             "alibaba",
  "ALIBABA":             "alibaba",
  "dashscope":           "alibaba",
  "gemini":              "gemini",
  "GEMINI":              "gemini",
  "google":              "gemini",
  "huggingface":         "huggingface",
  "nous":                "nous",
};

/**
 * hermes provider id → 对应的环境变量名称映射。
 * 用于将 QeeClaw 凭证注入到 bridge 子进程的环境变量中。
 */
export const PROVIDER_ENV_MAP: Record<string, {
  apiKeyEnv: string;
  baseUrlEnv?: string;
  defaultBaseUrl?: string;
}> = {
  "openrouter": {
    apiKeyEnv: "OPENROUTER_API_KEY",
    baseUrlEnv: "OPENROUTER_BASE_URL",
    defaultBaseUrl: "https://openrouter.ai/api/v1",
  },
  "openai": {
    apiKeyEnv: "OPENAI_API_KEY",
    baseUrlEnv: "OPENAI_BASE_URL",
  },
  "anthropic": {
    apiKeyEnv: "ANTHROPIC_API_KEY",
  },
  "zai": {
    apiKeyEnv: "GLM_API_KEY",
    baseUrlEnv: "GLM_BASE_URL",
    defaultBaseUrl: "https://api.z.ai/api/paas/v4",
  },
  "kimi-coding": {
    apiKeyEnv: "KIMI_API_KEY",
    baseUrlEnv: "KIMI_BASE_URL",
    defaultBaseUrl: "https://api.moonshot.ai/v1",
  },
  "minimax": {
    apiKeyEnv: "MINIMAX_API_KEY",
    baseUrlEnv: "MINIMAX_BASE_URL",
    defaultBaseUrl: "https://api.minimax.io/anthropic",
  },
  "deepseek": {
    apiKeyEnv: "DEEPSEEK_API_KEY",
    baseUrlEnv: "DEEPSEEK_BASE_URL",
    defaultBaseUrl: "https://api.deepseek.com/v1",
  },
  "alibaba": {
    apiKeyEnv: "DASHSCOPE_API_KEY",
    baseUrlEnv: "DASHSCOPE_BASE_URL",
    defaultBaseUrl: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
  },
  "gemini": {
    apiKeyEnv: "GOOGLE_API_KEY",
    baseUrlEnv: "GEMINI_BASE_URL",
    defaultBaseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
  },
  "huggingface": {
    apiKeyEnv: "HF_TOKEN",
    baseUrlEnv: "HF_BASE_URL",
    defaultBaseUrl: "https://router.huggingface.co/v1",
  },
};

// ---------------------------------------------------------------------------
// Credential Mapping
// ---------------------------------------------------------------------------

/** QeeClaw 侧的凭证输入 */
export interface QeeClawCredentials {
  /** QeeClaw 平台的 provider 名称（如 "ZHIPU", "openai"） */
  providerName?: string;
  /** API Key */
  apiKey?: string;
  /** 自定义 Base URL（可选） */
  baseUrl?: string;
  /** QeeClaw 平台 user token（用于平台 API 认证） */
  platformToken?: string;
}

/** 映射后的 hermes 环境变量 */
export interface HermesEnvVars {
  [key: string]: string;
}

/**
 * 将 QeeClaw 凭证映射为 hermes-agent bridge 子进程的环境变量。
 *
 * 用法：将返回的 env 对象合并到 bridge 子进程的 env 中即可。
 * 这是唯一的凭证适配点——hermes-agent 会自动从环境变量中读取。
 */
export function mapCredentialsToHermesEnv(credentials: QeeClawCredentials): HermesEnvVars {
  const env: HermesEnvVars = {};

  if (!credentials.providerName && !credentials.apiKey) {
    return env;
  }

  // 1. 映射 provider 名称
  const hermesProviderId = credentials.providerName
    ? PROVIDER_NAME_MAP[credentials.providerName] ?? credentials.providerName.toLowerCase()
    : "openrouter";

  // 2. 查找对应的环境变量配置
  const providerEnv = PROVIDER_ENV_MAP[hermesProviderId];

  if (providerEnv && credentials.apiKey) {
    // 设置 API Key 环境变量
    env[providerEnv.apiKeyEnv] = credentials.apiKey;

    // 设置 Base URL（用户指定 > provider 默认）
    if (credentials.baseUrl && providerEnv.baseUrlEnv) {
      env[providerEnv.baseUrlEnv] = credentials.baseUrl;
    }
  } else if (credentials.apiKey) {
    // 未知 provider，作为 OpenAI 兼容接口处理
    env["OPENAI_API_KEY"] = credentials.apiKey;
    if (credentials.baseUrl) {
      env["OPENAI_BASE_URL"] = credentials.baseUrl;
    }
  }

  // 3. 设置 hermes 的默认 provider 配置
  env["HERMES_PROVIDER"] = hermesProviderId;

  return env;
}

/**
 * 从现有进程环境变量中收集所有可能的 hermes 凭证。
 * 用于将宿主进程已有的 API Key 传递给 bridge 子进程。
 */
export function collectExistingCredentialEnvVars(
  sourceEnv: Record<string, string | undefined> = process.env as Record<string, string | undefined>,
): HermesEnvVars {
  const env: HermesEnvVars = {};
  const relevantKeys = new Set<string>();

  // 收集所有 provider 相关的环境变量名
  for (const config of Object.values(PROVIDER_ENV_MAP)) {
    relevantKeys.add(config.apiKeyEnv);
    if (config.baseUrlEnv) {
      relevantKeys.add(config.baseUrlEnv);
    }
  }

  // 额外的通用 key
  relevantKeys.add("OPENROUTER_API_KEY");
  relevantKeys.add("OPENROUTER_BASE_URL");
  relevantKeys.add("OPENAI_API_KEY");
  relevantKeys.add("OPENAI_BASE_URL");

  // 从源环境中提取
  for (const key of relevantKeys) {
    const value = sourceEnv[key];
    if (value && value.trim()) {
      env[key] = value;
    }
  }

  return env;
}

#!/usr/bin/env node

import http from "node:http";
import { randomUUID } from "node:crypto";

const port = Number(process.env.PORT || 3456);
const defaultTeamId = Number(process.env.QEECLAW_MOCK_TEAM_ID || 10001);

const now = () => new Date().toISOString();

const devices = [
  {
    id: 7,
    device_name: "QeeClaw Demo Mac",
    hostname: "demo-mac.local",
    os_info: "macOS 15",
    status: "online",
    last_seen: now(),
    created_time: now(),
    team_id: defaultTeamId,
    registration_mode: "bootstrap",
    installation_id: "inst-demo-001",
  },
];

const models = [
  {
    id: 1,
    provider_name: "openai",
    model_name: "gpt-5.4",
    provider_model_id: "gpt-5.4",
    label: "GPT-5.4",
    is_preferred: true,
    availability_status: "active",
    unit_price: 0.002,
    output_unit_price: 0.006,
    currency: "USD",
    billing_mode: "token",
    text_unit_chars: 1000,
    text_min_amount: 1,
  },
  {
    id: 2,
    provider_name: "anthropic",
    model_name: "claude-sonnet-4-6",
    provider_model_id: "claude-sonnet-4-6",
    label: "Claude Sonnet 4.6",
    is_preferred: false,
    availability_status: "active",
    unit_price: 0.003,
    output_unit_price: 0.015,
    currency: "USD",
    billing_mode: "token",
    text_unit_chars: 1000,
    text_min_amount: 1,
  },
];

const channelItems = [
  {
    channel_key: "wechat_work",
    channel_name: "Wechat Work",
    channel_group: "enterprise_collab",
    channel_kernel: "wechat_work",
    configured: true,
    enabled: true,
    binding_enabled: false,
    callback_url: "https://example.com/wechat/callback",
    risk_level: "medium",
    updated_time: now(),
  },
  {
    channel_key: "feishu",
    channel_name: "Feishu",
    channel_group: "enterprise_collab",
    channel_kernel: "feishu",
    configured: false,
    enabled: false,
    binding_enabled: false,
    callback_url: "https://example.com/feishu/callback",
    risk_level: "medium",
    updated_time: now(),
  },
  {
    channel_key: "wechat_personal_plugin",
    channel_name: "Personal Wechat Plugin",
    channel_group: "personal_reach",
    channel_kernel: "wechat_work_plugin",
    configured: false,
    enabled: false,
    binding_enabled: false,
    callback_url: "https://example.com/wechat/personal-plugin/callback",
    risk_level: "high",
    updated_time: now(),
  },
  {
    channel_key: "wechat_personal_openclaw",
    channel_name: "Personal Wechat Official Plugin",
    channel_group: "personal_reach",
    channel_kernel: "openclaw_wechat_plugin",
    configured: true,
    enabled: true,
    binding_enabled: true,
    callback_url: "",
    risk_level: "medium",
    updated_time: null,
  },
];

const channelConfigs = {
  wechat: {
    ...channelItems[0],
    corp_id: "corp-demo",
    agent_id: "agent-demo",
    secret: "mock-secret",
    secret_configured: true,
    verify_token: "mock-verify-token",
    aes_key: "mock-aes-key",
  },
  feishu: {
    ...channelItems[1],
    app_id: "cli_a1b2c3",
    app_secret: "",
    verification_token: "mock-verification-token",
    encrypt_key: "mock-encrypt-key",
    secret_configured: false,
  },
  wechatPersonalPlugin: {
    ...channelItems[2],
    display_name: "QeeClaw Personal Assistant",
    kernel_source: "unconfigured",
    kernel_configured: false,
    kernel_isolated: false,
    kernel_corp_id: "",
    kernel_agent_id: "",
    kernel_secret: "",
    kernel_secret_configured: false,
    kernel_verify_token: "",
    kernel_aes_key: "",
    effective_kernel_corp_id: "",
    effective_kernel_agent_id: "",
    effective_kernel_verify_token: "",
    effective_kernel_aes_key: "",
    setup_status: "planned",
    assistant_name: "",
    welcome_message: "",
    capability_stage: "phase_1_placeholder",
  },
  wechatPersonalOpenClaw: {
    ...channelItems[3],
    display_name: "QeeClaw 微信官方插件",
    channel_mode: "official_openclaw_plugin",
    setup_status: "ready",
    manual_cli_required: false,
    preinstall_supported: true,
    qr_supported: true,
    gateway_online: true,
    official_plugin_available: true,
    install_hint: "安装包预装插件，后台直接展示二维码供微信扫码绑定。",
    capability_stage: "phase_0_5_qr_productized",
  },
};

let channelBindings = [];
let officialQrSession = null;

const groups = [
  {
    room_id: "sales-room-001",
    room_name: "North Region Sales",
    last_active: now(),
    msg_count: 12,
    member_count: 8,
  },
];

const groupMessages = {
  "sales-room-001": [
    {
      id: 101,
      sender_name: "Alice",
      sender_role: "sales",
      msg_type: "text",
      content: "Please share the latest product pricing notes.",
      created_time: now(),
      entities: [{ type: "topic", value: "pricing", confidence: 0.96 }],
    },
  ],
};

const historyMessages = [
  {
    id: 201,
    sender_id: 1,
    agent_id: 9,
    channel_id: "mobile",
    direction: "user_to_agent",
    content: "Summarize the opportunities closing this week.",
    created_time: now(),
  },
];

const memories = [
  {
    id: "mem-001",
    content: "Customer prefers quarterly billing.",
    category: "preference",
    importance: 0.9,
    team_id: defaultTeamId,
    runtime_type: "openclaw",
    agent_id: "sales-copilot",
    device_id: "device-demo-1",
    source_session: "session-001",
    created_at: now(),
  },
];

const knowledgeAssets = [
  {
    source_name: "pricing-policy.md",
    filename: "pricing-policy.md",
    size: 2048,
    status: "indexed",
    team_id: defaultTeamId,
    runtime_type: "openclaw",
    agent_id: "sales-copilot",
    updated_at: now(),
  },
  {
    source_name: "sales-playbook.txt",
    filename: "sales-playbook.txt",
    size: 1024,
    status: "indexed",
    team_id: defaultTeamId,
    runtime_type: "openclaw",
    agent_id: "sales-copilot",
    updated_at: now(),
  },
];

let knowledgeConfig = {
  watchDir: "/Users/demo/QeeClawKnowledge",
  lastSyncAt: now(),
};

const approvals = [
  {
    approval_id: "apr-001",
    status: "pending",
    approval_type: "exec_access",
    title: "Approve export pipeline",
    reason: "Exporting customer report to secure destination",
    risk_level: "medium",
    payload: { command: "python export.py" },
    requested_by: { user_id: 1, username: "demo" },
    resolved_by: null,
    resolution_comment: null,
    created_at: now(),
    expires_at: new Date(Date.now() + 3600_000).toISOString(),
    resolved_at: null,
  },
];

const auditEvents = [
  {
    event_id: "evt-001",
    category: "operation",
    event_type: "knowledge.search",
    title: "Knowledge search executed",
    summary: "Search over pricing policy",
    module: "knowledge",
    path: "/api/platform/knowledge/search",
    status: "success",
    risk_level: "low",
    actor: { user_id: 1, username: "demo" },
    metadata: { query: "pricing" },
    created_at: now(),
  },
];

const walletSummary = {
  balance: 256.38,
  currency: "CNY",
  total_spent: 143.62,
  total_recharge: 400.0,
  current_month_spent: 68.2,
  updated_time: now(),
};

const billingRecords = [
  {
    id: 1,
    product_name: "GeneralLLM",
    record_type: "deduction",
    duration_seconds: 0,
    text_input_length: 1680,
    text_output_length: 920,
    unit_price: 0.02,
    output_unit_price: 0.05,
    amount: 18.2,
    currency: "CNY",
    remark: "Sales assistant knowledge answer",
    balance_snapshot: 256.38,
    created_time: now(),
  },
  {
    id: 3,
    product_name: "gpt-5.4",
    record_type: "deduction",
    duration_seconds: 0,
    text_input_length: 820,
    text_output_length: 640,
    unit_price: 0.025,
    output_unit_price: 0.06,
    amount: 11.6,
    currency: "CNY",
    remark: "Model hub direct invoke",
    balance_snapshot: 274.58,
    created_time: new Date(Date.now() - 6 * 3600_000).toISOString(),
  },
  {
    id: 2,
    product_name: "Wallet Recharge",
    record_type: "recharge",
    duration_seconds: 0,
    text_input_length: 0,
    text_output_length: 0,
    unit_price: 0,
    output_unit_price: 0,
    amount: 400,
    currency: "CNY",
    remark: "Mock recharge order",
    balance_snapshot: 400,
    created_time: new Date(Date.now() - 86400_000).toISOString(),
  },
];

let preferredModel = "gpt-5.4";

const teams = [
  {
    id: defaultTeamId,
    name: "Demo Personal Workspace",
    is_personal: true,
    owner_id: 1,
  },
];

const currentUser = {
  id: 1,
  username: "demo",
  full_name: "Demo User",
  email: "demo@qeeclaw.ai",
  phone: "13800138000",
  role: "ADMIN",
  is_active: true,
  last_login_time: now(),
  created_time: new Date(Date.now() - 15 * 86400_000).toISOString(),
};

const listUsers = [
  currentUser,
  {
    id: 2,
    username: "sales-admin",
    full_name: "Sales Admin",
    email: "sales-admin@qeeclaw.ai",
    phone: "13900139000",
    role: "USER",
    is_active: true,
    last_login_time: now(),
    created_time: new Date(Date.now() - 30 * 86400_000).toISOString(),
  },
];

const userProducts = [
  {
    id: 101,
    name: "GeneralLLM",
    description: "通用大模型调用能力",
    unit_price: 0.02,
    output_unit_price: 0.05,
    currency: "CNY",
    billing_mode: "text_in_out",
    duration_unit_sec: 60,
    duration_min_amount: 0,
    text_unit_chars: 1000,
    text_min_amount: 0.01,
    http_method: "POST",
    api_path: "/api/llm/chat/completions",
    docs_url: "https://docs.example.com/general-llm",
    doc_id: 9001,
    labels: "llm,general",
    is_active: true,
    create_time: new Date(Date.now() - 20 * 86400_000).toISOString(),
    update_time: now(),
  },
  {
    id: 102,
    name: "RealtimeTranslation",
    description: "实时语音翻译能力",
    unit_price: 0.12,
    output_unit_price: 0.0,
    currency: "CNY",
    billing_mode: "duration",
    duration_unit_sec: 60,
    duration_min_amount: 0.1,
    text_unit_chars: 100,
    text_min_amount: 0.01,
    http_method: "WS",
    api_path: "/api/realtime/translate",
    docs_url: "https://docs.example.com/realtime-translation",
    doc_id: 9002,
    labels: "voice,realtime",
    is_active: true,
    create_time: new Date(Date.now() - 18 * 86400_000).toISOString(),
    update_time: now(),
  },
];

let appKeys = [
  {
    id: 1,
    app_key: "qck_live_demo_001",
    key_name: "Default Desktop Key",
    role: currentUser.role,
    is_active: true,
    expire_time: null,
    create_time: new Date(Date.now() - 12 * 86400_000).toISOString(),
  },
];

let llmKeys = [
  {
    id: 1,
    key: "sk-demo-provider-001",
    name: "OpenAI Production",
    description: "用于模型中心演示的 Provider 密钥",
    limit_config: {
      monthly_budget: 200,
      currency: "USD",
    },
    expire_time: null,
    is_active: true,
    created_time: new Date(Date.now() - 10 * 86400_000).toISOString(),
  },
];

let companyVerification = {
  status: "none",
  company_name: null,
  tax_number: null,
  address: null,
  phone: null,
  bank_name: null,
  bank_account: null,
  license_url: null,
  rejection_reason: null,
  updated_time: null,
};

const documents = [
  {
    id: 9001,
    document_title: "QeeClaw 平台接入说明",
    document_detail: "面向集成团队的标准接入说明文档。",
    sort_num: 1,
    labels: "sdk,platform",
    create_time: new Date(Date.now() - 7 * 86400_000).toISOString(),
    update_time: now(),
  },
  {
    id: 9002,
    document_title: "销售知识库构建规范",
    document_detail: "适用于销售超级驾驶舱的知识组织规范。",
    sort_num: 2,
    labels: "sales,knowledge",
    create_time: new Date(Date.now() - 5 * 86400_000).toISOString(),
    update_time: now(),
  },
];

const productDocuments = {
  101: [
    {
      id: 5001,
      product_id: 101,
      document_title: "GeneralLLM API 调用说明",
      document_detail: "包含基础鉴权、模型调用与计费说明。",
      sort_num: 1,
      create_time: new Date(Date.now() - 4 * 86400_000).toISOString(),
      update_time: now(),
    },
  ],
};

const workflows = new Map([
  [
    "sales-followup",
    {
      id: "sales-followup",
      name: "销售跟进提醒",
      description: "每日聚合待跟进客户并推送提醒。",
      enabled: true,
      nodes: [
        {
          id: "node-trigger",
          position: { x: 0, y: 0 },
          data: {
            label: "手动触发",
            type: "trigger",
            handler: "manual_trigger",
            config: {},
          },
        },
        {
          id: "node-log",
          position: { x: 240, y: 0 },
          data: {
            label: "记录日志",
            type: "action",
            handler: "log_message",
            config: {
              message: "已触发销售跟进提醒工作流",
            },
          },
        },
      ],
      edges: [
        {
          id: "edge-1",
          source: "node-trigger",
          target: "node-log",
        },
      ],
    },
  ],
]);

const workflowExecutions = new Map();

const agentTools = [
  {
    name: "knowledge.search",
    description: "Search indexed enterprise knowledge",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string" },
        teamId: { type: "number" },
      },
      required: ["query"],
    },
    tags: ["knowledge", "search"],
  },
  {
    name: "billing.summary",
    description: "Read current billing summary",
    inputSchema: {
      type: "object",
      properties: {},
      required: [],
    },
    tags: ["billing", "governance"],
  },
];

let myAgents = [
  {
    id: 0,
    name: "小智",
    code: "xiaozhi",
    description: "虽然只有七岁，但智商超群的小男孩",
    avatar: "https://api.dicebear.com/7.x/adventurer/svg?seed=xiaozhi",
    voice_id: "xiaozhi",
    runtime_type: "openclaw",
    runtime_label: "OpenClaw",
    model: "gpt-4o",
  },
];

const agentTemplates = [
  {
    id: 3001,
    code: "sales_coach",
    name: "销售教练",
    description: "用于销售话术复盘和训练建议输出",
    avatar: "https://api.dicebear.com/7.x/adventurer/svg?seed=sales-coach",
    allowed_tools: ["knowledge.search", "billing.summary"],
  },
];

function sendJson(response, statusCode, data) {
  response.statusCode = statusCode;
  response.setHeader("Content-Type", "application/json");
  response.end(JSON.stringify({ code: 0, data, message: "success" }));
}

function sendBinary(response, statusCode, body, contentType, filename) {
  response.statusCode = statusCode;
  response.setHeader("Content-Type", contentType);
  if (filename) {
    response.setHeader("Content-Disposition", `attachment; filename=${filename}`);
  }
  response.end(body);
}

function sendError(response, statusCode, message) {
  response.statusCode = statusCode;
  response.setHeader("Content-Type", "application/json");
  response.end(JSON.stringify({ code: statusCode, message }));
}

async function readBody(request) {
  const chunks = [];
  for await (const chunk of request) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  if (!chunks.length) {
    return { raw: "", json: null };
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  try {
    return { raw, json: JSON.parse(raw) };
  } catch {
    return { raw, json: null };
  }
}

function parseFormFields(contentType, raw) {
  if (!raw) {
    return {};
  }

  if (contentType.includes("application/x-www-form-urlencoded")) {
    return Object.fromEntries(new URLSearchParams(raw).entries());
  }

  const boundaryMatch = contentType.match(/boundary=([^;]+)/i);
  if (!boundaryMatch) {
    return {};
  }

  const boundary = `--${boundaryMatch[1]}`;
  const fields = {};

  for (const part of raw.split(boundary)) {
    if (!part.includes("Content-Disposition")) {
      continue;
    }
    const nameMatch = part.match(/name="([^"]+)"/i);
    if (!nameMatch) {
      continue;
    }
    const filenameMatch = part.match(/filename="([^"]+)"/i);
    const [, fieldName] = nameMatch;
    const body = part.split("\r\n\r\n")[1];
    if (!body) {
      continue;
    }
    const cleaned = body.replace(/\r\n$/, "");
    fields[fieldName] = filenameMatch ? filenameMatch[1] : cleaned;
  }

  return fields;
}

function pickModelByName(name) {
  return (
    buildPlatformModels().find((item) => item.model_name === name || item.provider_model_id === name) ||
    buildPlatformModels().find((item) => item.is_preferred) ||
    models[0]
  );
}

function paginate(items, page, pageSize) {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

function parseOptionalNumber(value) {
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseOptionalString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function parseOptionalScalar(value) {
  return value === undefined || value === null || value === "" ? undefined : value;
}

function buildRuntimeScope(input = {}) {
  return {
    team_id: parseOptionalNumber(input.team_id),
    runtime_type: parseOptionalString(input.runtime_type),
    device_id: parseOptionalScalar(input.device_id),
    agent_id: parseOptionalString(input.agent_id),
  };
}

function buildRuntimeScopeFromSearchParams(searchParams) {
  return buildRuntimeScope({
    team_id: searchParams.get("team_id"),
    runtime_type: searchParams.get("runtime_type"),
    device_id: searchParams.get("device_id"),
    agent_id: searchParams.get("agent_id"),
  });
}

function matchesRuntimeScope(item, scope) {
  if (scope.team_id !== undefined && item.team_id !== scope.team_id) {
    return false;
  }
  if (scope.runtime_type !== undefined && item.runtime_type !== scope.runtime_type) {
    return false;
  }
  if (scope.device_id !== undefined && String(item.device_id ?? "") !== String(scope.device_id)) {
    return false;
  }
  if (scope.agent_id !== undefined && item.agent_id !== scope.agent_id) {
    return false;
  }
  return true;
}

function filterByRuntimeScope(items, scope) {
  return items.filter((item) => matchesRuntimeScope(item, scope));
}

function serializeRuntimeScope(scope) {
  return {
    team_id: scope.team_id ?? null,
    runtime_type: scope.runtime_type ?? null,
    device_id: scope.device_id ?? null,
    agent_id: scope.agent_id ?? null,
  };
}

function buildAuditSummary() {
  const approvalCount = approvals.length;
  return {
    total: auditEvents.length + approvalCount,
    operation_count: auditEvents.filter((item) => item.category === "operation").length,
    approval_count: approvalCount,
    pending_approval_count: approvals.filter((item) => item.status === "pending").length,
    approved_approval_count: approvals.filter((item) => item.status === "approved").length,
    rejected_approval_count: approvals.filter((item) => item.status === "rejected").length,
    expired_approval_count: approvals.filter((item) => item.status === "expired").length,
  };
}

function buildModelProviderSummary() {
  const byProvider = new Map();
  const route = buildModelRouteProfile();
  for (const model of buildPlatformModels()) {
    const current = byProvider.get(model.provider_name) || {
      provider_name: model.provider_name,
      configured: true,
      provider_status: "ready",
      visible_count: 0,
      hidden_count: 0,
      disabled_count: 0,
      models: [],
      preferred_model_supported: preferredModel === model.model_name,
      is_default_route_provider: route.resolved_provider_name === model.provider_name,
      default_route_model: route.resolved_provider_name === model.provider_name ? route.resolved_model : null,
      default_route_provider_model_id:
        route.resolved_provider_name === model.provider_name ? route.resolved_provider_model_id : null,
    };
    if (model.availability_status === "hidden") {
      current.hidden_count += 1;
    } else {
      current.visible_count += 1;
    }
    current.models.push(model.model_name);
    byProvider.set(model.provider_name, current);
  }
  return [...byProvider.values()];
}

function buildPlatformModels() {
  return models.map((item) => ({
    ...item,
    is_preferred: item.model_name === preferredModel,
  }));
}

function buildModelRouteProfile() {
  const availableModels = buildPlatformModels();
  const selected = pickModelByName(preferredModel || "");
  return {
    preferred_model: preferredModel || null,
    preferred_model_available: Boolean(preferredModel),
    resolved_model: selected?.model_name || null,
    resolved_provider_name: selected?.provider_name || null,
    resolved_provider_model_id: selected?.provider_model_id || null,
    candidate_count: selected ? availableModels.filter((item) => item.model_name === selected.model_name).length : 0,
    configured_provider_count: new Set(availableModels.map((item) => item.provider_name)).size,
    available_model_count: availableModels.length,
    resolution_reason: preferredModel ? "preferred_model" : "first_available",
    selected: selected || null,
  };
}

function listModelBillingRecords(days = 30) {
  const periodStart = Date.now() - days * 86400_000;
  const modelNames = new Set(buildPlatformModels().map((item) => item.model_name));
  const genericNames = new Set(["GeneralLLM", "通用大模型", "大语言模型"]);
  return billingRecords.filter((item) => {
    if (item.record_type !== "deduction") {
      return false;
    }
    const createdAt = Date.parse(item.created_time || "");
    if (Number.isFinite(createdAt) && createdAt < periodStart) {
      return false;
    }
    return modelNames.has(item.product_name) || genericNames.has(item.product_name);
  });
}

function buildModelUsageSummary(days = 30) {
  const records = listModelBillingRecords(days);
  const byProduct = new Map();
  const lastUsedAt = records.reduce((latest, item) => {
    if (!latest || latest < item.created_time) return item.created_time;
    return latest;
  }, null);

  for (const record of records) {
    const matchedModel = buildPlatformModels().find((item) => item.model_name === record.product_name) || null;
    const group = byProduct.get(record.product_name) || {
      product_name: record.product_name,
      label: matchedModel?.label || (record.product_name === "GeneralLLM" ? "通用大模型" : record.product_name),
      group_type: matchedModel ? "catalog_model" : "generic_llm",
      model_name: matchedModel?.model_name || null,
      provider_names: matchedModel ? [matchedModel.provider_name] : [],
      call_count: 0,
      text_input_chars: 0,
      text_output_chars: 0,
      duration_seconds: 0,
      last_used_at: null,
    };
    group.call_count += 1;
    group.text_input_chars += Number(record.text_input_length || 0);
    group.text_output_chars += Number(record.text_output_length || 0);
    group.duration_seconds += Number(record.duration_seconds || 0);
    if (!group.last_used_at || group.last_used_at < record.created_time) {
      group.last_used_at = record.created_time;
    }
    byProduct.set(record.product_name, group);
  }

  const breakdown = [...byProduct.values()].sort((a, b) => {
    if (b.call_count !== a.call_count) return b.call_count - a.call_count;
    return (b.text_input_chars + b.text_output_chars) - (a.text_input_chars + a.text_output_chars);
  });

  return {
    window_days: days,
    period_start: new Date(Date.now() - days * 86400_000).toISOString(),
    period_end: now(),
    attribution_mode: "product_name_and_product_id",
    record_count: records.length,
    total_calls: records.length,
    total_input_chars: records.reduce((sum, item) => sum + Number(item.text_input_length || 0), 0),
    total_output_chars: records.reduce((sum, item) => sum + Number(item.text_output_length || 0), 0),
    total_duration_seconds: records.reduce((sum, item) => sum + Number(item.duration_seconds || 0), 0),
    last_used_at: lastUsedAt,
    breakdown,
  };
}

function buildModelCostSummary(days = 30) {
  const records = listModelBillingRecords(days);
  const byProduct = new Map();
  let totalAmount = 0;
  const lastBilledAt = records.reduce((latest, item) => {
    if (!latest || latest < item.created_time) return item.created_time;
    return latest;
  }, null);

  for (const record of records) {
    const matchedModel = buildPlatformModels().find((item) => item.model_name === record.product_name) || null;
    const group = byProduct.get(record.product_name) || {
      product_name: record.product_name,
      label: matchedModel?.label || (record.product_name === "GeneralLLM" ? "通用大模型" : record.product_name),
      group_type: matchedModel ? "catalog_model" : "generic_llm",
      model_name: matchedModel?.model_name || null,
      provider_names: matchedModel ? [matchedModel.provider_name] : [],
      call_count: 0,
      amount: 0,
      average_amount: 0,
      currency: record.currency || "CNY",
      currency_breakdown: [],
      last_billed_at: null,
    };
    group.call_count += 1;
    group.amount += Number(record.amount || 0);
    group.average_amount = group.amount / group.call_count;
    group.currency_breakdown = [{ currency: group.currency, amount: Number(group.amount.toFixed(4)) }];
    if (!group.last_billed_at || group.last_billed_at < record.created_time) {
      group.last_billed_at = record.created_time;
    }
    byProduct.set(record.product_name, group);
    totalAmount += Number(record.amount || 0);
  }

  const breakdown = [...byProduct.values()]
    .map((item) => ({
      ...item,
      amount: Number(item.amount.toFixed(4)),
      average_amount: Number(item.average_amount.toFixed(4)),
    }))
    .sort((a, b) => b.amount - a.amount);

  return {
    window_days: days,
    period_start: new Date(Date.now() - days * 86400_000).toISOString(),
    period_end: now(),
    attribution_mode: "product_name_and_product_id",
    record_count: records.length,
    total_amount: Number(totalAmount.toFixed(4)),
    primary_currency: "CNY",
    currency_breakdown: [{ currency: "CNY", amount: Number(totalAmount.toFixed(4)) }],
    last_billed_at: lastBilledAt,
    breakdown,
  };
}

function buildModelQuotaSummary() {
  const dailySpent = listModelBillingRecords(1).reduce((sum, item) => sum + Number(item.amount || 0), 0);
  const monthlySpent = listModelBillingRecords(30).reduce((sum, item) => sum + Number(item.amount || 0), 0);
  const dailyLimit = 80;
  const monthlyLimit = 300;
  return {
    wallet_balance: walletSummary.balance,
    currency: walletSummary.currency,
    daily_limit: dailyLimit,
    daily_spent: Number(dailySpent.toFixed(4)),
    daily_remaining: Number(Math.max(dailyLimit - dailySpent, 0).toFixed(4)),
    daily_unlimited: false,
    monthly_limit: monthlyLimit,
    monthly_spent: Number(monthlySpent.toFixed(4)),
    monthly_remaining: Number(Math.max(monthlyLimit - monthlySpent, 0).toFixed(4)),
    monthly_unlimited: false,
    updated_time: walletSummary.updated_time,
  };
}

function getBillingTotals() {
  return {
    total_spent: billingRecords
      .filter((item) => item.record_type === "deduction")
      .reduce((sum, item) => sum + Number(item.amount || 0), 0),
    total_recharge: billingRecords
      .filter((item) => item.record_type === "recharge")
      .reduce((sum, item) => sum + Number(item.amount || 0), 0),
  };
}

function buildCurrentUserProfile() {
  return {
    ...currentUser,
    wallet_balance: walletSummary.balance,
    is_enterprise_verified: companyVerification.status === "approved",
    teams,
  };
}

function buildListedUsers() {
  return listUsers.map((item) => ({
    ...item,
    wallet_balance: item.id === currentUser.id ? walletSummary.balance : 88.8,
    is_enterprise_verified: item.id === currentUser.id
      ? companyVerification.status === "approved"
      : false,
  }));
}

function approvalToAuditEvent(item) {
  return {
    event_id: `approval-${item.approval_id}`,
    category: "approval",
    event_type: item.approval_type,
    title: item.title,
    summary: item.reason,
    module: "approval",
    path: "/api/platform/approvals",
    status: item.status,
    risk_level: item.risk_level,
    actor: item.requested_by,
    metadata: item.payload,
    created_at: item.created_at,
  };
}

const server = http.createServer(async (request, response) => {
  const method = request.method || "GET";
  const url = new URL(request.url || "/", `http://127.0.0.1:${port}`);
  const pathname = url.pathname;

  if (method === "GET" && pathname === "/health") {
    sendJson(response, 200, { status: "ok", service: "qeeclaw-mock-platform-server" });
    return;
  }

  if (method === "GET" && pathname === "/api/billing/wallet") {
    sendJson(response, 200, walletSummary);
    return;
  }

  if (method === "GET" && pathname === "/api/billing/records") {
    const page = Number(url.searchParams.get("page") || 1);
    const pageSize = Number(url.searchParams.get("page_size") || 20);
    const requestedType = url.searchParams.get("type");
    const normalizedType = requestedType === "consumption" ? "deduction" : requestedType;
    const items = billingRecords.filter((item) => !normalizedType || item.record_type === normalizedType);
    sendJson(response, 200, {
      total: items.length,
      page,
      page_size: pageSize,
      items: paginate(items, page, pageSize),
    });
    return;
  }

  if (method === "GET" && pathname === "/api/billing/summary") {
    sendJson(response, 200, getBillingTotals());
    return;
  }

  if (method === "GET" && pathname === "/api/users") {
    const page = Number(url.searchParams.get("page") || 1);
    const pageSize = Number(url.searchParams.get("page_size") || 20);
    const keyword = String(url.searchParams.get("keyword") || "").trim().toLowerCase();
    const items = buildListedUsers().filter((item) => {
      if (!keyword) {
        return true;
      }
      return [item.username, item.full_name, item.email, item.phone]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(keyword));
    });
    sendJson(response, 200, {
      total: items.length,
      page,
      page_size: pageSize,
      items: paginate(items, page, pageSize),
    });
    return;
  }

  if (method === "GET" && pathname === "/api/users/me") {
    sendJson(response, 200, buildCurrentUserProfile());
    return;
  }

  if (method === "PUT" && pathname === "/api/users/me") {
    const { json } = await readBody(request);
    currentUser.full_name = json?.full_name ?? currentUser.full_name;
    currentUser.email = json?.email ?? currentUser.email;
    currentUser.phone = json?.phone ?? currentUser.phone;
    sendJson(response, 200, buildCurrentUserProfile());
    return;
  }

  if (method === "PUT" && pathname === "/api/users/me/preference") {
    const { json } = await readBody(request);
    preferredModel = String(json?.preferred_model || preferredModel);
    sendJson(response, 200, {
      preferred_model: preferredModel,
    });
    return;
  }

  if (method === "GET" && pathname === "/api/users/products") {
    sendJson(response, 200, userProducts);
    return;
  }

  if (method === "POST" && pathname === "/api/users/app-keys/default/token") {
    const activeKey = appKeys.find((item) => item.is_active);
    if (!activeKey) {
      sendError(response, 400, "No active app key available");
      return;
    }
    sendJson(response, 200, {
      token: `mock-app-token-${activeKey.id}`,
      expires_in: 7200,
      app_key: activeKey.app_key,
      app_key_id: activeKey.id,
    });
    return;
  }

  if (method === "GET" && pathname === "/api/users/app-keys") {
    const page = Number(url.searchParams.get("page") || 1);
    const pageSize = Number(url.searchParams.get("page_size") || 20);
    sendJson(response, 200, {
      total: appKeys.length,
      page,
      page_size: pageSize,
      items: paginate(appKeys, page, pageSize),
    });
    return;
  }

  if (method === "POST" && pathname === "/api/users/app-keys") {
    const id = appKeys.length ? Math.max(...appKeys.map((item) => item.id)) + 1 : 1;
    const appKey = {
      id,
      app_key: `qck_live_demo_${String(id).padStart(3, "0")}`,
      key_name: `Mock Key ${id}`,
      role: currentUser.role,
      is_active: true,
      expire_time: null,
      create_time: now(),
    };
    appKeys.unshift(appKey);
    sendJson(response, 200, {
      id: appKey.id,
      app_key: appKey.app_key,
      app_secret: `mock-secret-${randomUUID()}`,
    });
    return;
  }

  if (method === "DELETE" && pathname.startsWith("/api/users/app-keys/")) {
    const appKeyId = Number(pathname.replace("/api/users/app-keys/", ""));
    appKeys = appKeys.filter((item) => item.id !== appKeyId);
    sendJson(response, 200, null);
    return;
  }

  if (method === "PATCH" && pathname.startsWith("/api/users/app-keys/")) {
    const appKeyId = Number(pathname.replace("/api/users/app-keys/", ""));
    const target = appKeys.find((item) => item.id === appKeyId);
    if (!target) {
      sendError(response, 404, `App key not found: ${appKeyId}`);
      return;
    }
    const { json } = await readBody(request);
    target.is_active = Boolean(json?.is_active);
    sendJson(response, 200, null);
    return;
  }

  if (method === "PUT" && pathname.startsWith("/api/users/app-keys/") && pathname.endsWith("/name")) {
    const appKeyId = Number(pathname.split("/")[4] || 0);
    const target = appKeys.find((item) => item.id === appKeyId);
    if (!target) {
      sendError(response, 404, `App key not found: ${appKeyId}`);
      return;
    }
    const { json } = await readBody(request);
    target.key_name = String(json?.key_name || target.key_name || `Mock Key ${appKeyId}`);
    sendJson(response, 200, null);
    return;
  }

  if (method === "GET" && pathname === "/api/llm/keys") {
    sendJson(response, 200, llmKeys);
    return;
  }

  if (method === "POST" && pathname === "/api/llm/keys") {
    const { json } = await readBody(request);
    const id = llmKeys.length ? Math.max(...llmKeys.map((item) => item.id)) + 1 : 1;
    const llmKey = {
      id,
      key: `sk-demo-provider-${String(id).padStart(3, "0")}`,
      name: String(json?.name || `Provider Key ${id}`),
      description: json?.description ?? null,
      limit_config: json?.limit_config ?? null,
      expire_time: json?.expire_time ?? null,
      is_active: true,
      created_time: now(),
    };
    llmKeys.unshift(llmKey);
    sendJson(response, 200, llmKey);
    return;
  }

  if (method === "PUT" && pathname.startsWith("/api/llm/keys/")) {
    const keyId = Number(pathname.replace("/api/llm/keys/", ""));
    const target = llmKeys.find((item) => item.id === keyId);
    if (!target) {
      sendError(response, 404, `LLM key not found: ${keyId}`);
      return;
    }
    const { json } = await readBody(request);
    if (json?.name !== undefined) {
      target.name = json.name;
    }
    if (json?.description !== undefined) {
      target.description = json.description;
    }
    if (json?.expire_time !== undefined) {
      target.expire_time = json.expire_time;
    }
    if (json?.is_active !== undefined) {
      target.is_active = Boolean(json.is_active);
    }
    sendJson(response, 200, target);
    return;
  }

  if (method === "DELETE" && pathname.startsWith("/api/llm/keys/")) {
    const keyId = Number(pathname.replace("/api/llm/keys/", ""));
    llmKeys = llmKeys.filter((item) => item.id !== keyId);
    sendJson(response, 200, { deleted: true });
    return;
  }

  if (method === "GET" && pathname === "/api/company/verification") {
    sendJson(response, 200, companyVerification);
    return;
  }

  if (method === "POST" && pathname === "/api/company/verification") {
    const { raw } = await readBody(request);
    const contentType = String(request.headers["content-type"] || "");
    const fields = parseFormFields(contentType, raw);
    companyVerification = {
      status: "pending",
      company_name: fields.company_name || companyVerification.company_name,
      tax_number: fields.tax_number || companyVerification.tax_number,
      address: fields.address || companyVerification.address,
      phone: fields.phone || companyVerification.phone,
      bank_name: fields.bank_name || companyVerification.bank_name,
      bank_account: fields.bank_account || companyVerification.bank_account,
      license_url: fields.license_file
        ? `https://mock-cdn.qeeclaw.ai/company-license/${encodeURIComponent(String(fields.license_file))}`
        : companyVerification.license_url,
      rejection_reason: null,
      updated_time: now(),
    };
    sendJson(response, 200, companyVerification);
    return;
  }

  if (method === "POST" && pathname === "/api/company/verification/approve") {
    companyVerification = {
      ...companyVerification,
      status: "approved",
      updated_time: now(),
    };
    if (!teams.find((item) => item.is_personal === false)) {
      teams.push({
        id: defaultTeamId + 1,
        name: `${companyVerification.company_name || "QeeClaw"} 工作空间`,
        is_personal: false,
        owner_id: currentUser.id,
      });
    }
    sendJson(response, 200, null);
    return;
  }

  if (method === "GET" && pathname === "/api/documents") {
    const skip = Number(url.searchParams.get("skip") || 0);
    const limit = Number(url.searchParams.get("limit") || 100);
    sendJson(response, 200, documents.slice(skip, skip + limit));
    return;
  }

  if (method === "GET" && pathname.startsWith("/api/documents/")) {
    const documentId = Number(pathname.replace("/api/documents/", ""));
    const target = documents.find((item) => item.id === documentId);
    if (!target) {
      sendError(response, 404, `Document not found: ${documentId}`);
      return;
    }
    sendJson(response, 200, target);
    return;
  }

  if (method === "GET" && pathname.startsWith("/api/products/") && pathname.endsWith("/documents")) {
    const productId = Number(pathname.split("/")[3] || 0);
    sendJson(response, 200, productDocuments[productId] || []);
    return;
  }

  if (method === "GET" && pathname === "/api/workflows") {
    sendJson(response, 200, [...workflows.values()]);
    return;
  }

  if (method === "POST" && pathname === "/api/workflows") {
    const { json } = await readBody(request);
    if (!json?.id) {
      sendError(response, 400, "Workflow id is required");
      return;
    }
    workflows.set(String(json.id), json);
    sendJson(response, 200, null);
    return;
  }

  if (method === "GET" && pathname.startsWith("/api/workflows/") && !pathname.includes("/executions/")) {
    const workflowId = decodeURIComponent(pathname.replace("/api/workflows/", ""));
    const workflow = workflows.get(workflowId);
    if (!workflow) {
      sendError(response, 404, `Workflow not found: ${workflowId}`);
      return;
    }
    sendJson(response, 200, workflow);
    return;
  }

  if (method === "POST" && pathname.startsWith("/api/workflows/") && pathname.endsWith("/run")) {
    const workflowId = decodeURIComponent(pathname.split("/")[3] || "");
    const workflow = workflows.get(workflowId);
    if (!workflow) {
      sendError(response, 404, `Workflow not found: ${workflowId}`);
      return;
    }
    const { json } = await readBody(request);
    const executionId = `wfexec-${Date.now()}`;
    workflowExecutions.set(executionId, [
      `Execution started for ${workflow.name}`,
      `Payload: ${JSON.stringify(json || {})}`,
      "Execution finished",
    ]);
    sendJson(response, 200, {
      execution_id: executionId,
    });
    return;
  }

  if (method === "GET" && pathname.startsWith("/api/workflows/executions/") && pathname.endsWith("/logs")) {
    const executionId = decodeURIComponent(pathname.split("/")[4] || "");
    sendJson(response, 200, workflowExecutions.get(executionId) || []);
    return;
  }

  if (method === "GET" && pathname === "/api/agent/tools") {
    sendJson(response, 200, agentTools);
    return;
  }

  if (method === "GET" && pathname === "/api/agent/my-agents") {
    sendJson(response, 200, myAgents);
    return;
  }

  if (method === "POST" && pathname === "/api/agent/create") {
    const { json } = await readBody(request);
    const id = myAgents.length ? Math.max(...myAgents.map((item) => item.id)) + 1 : 1;
    const created = {
      id,
      name: json?.name || `Agent ${id}`,
      code: `user_agent_${id}`,
      description: json?.description || "",
      avatar: `https://api.dicebear.com/7.x/adventurer/svg?seed=${encodeURIComponent(String(json?.name || `Agent ${id}`))}`,
      voice_id: "xiaozhi",
      runtime_type: String(json?.runtime_type || "openclaw"),
      runtime_label: String(json?.runtime_type || "openclaw") === "deeflow2" ? "DeeFlow2" : "OpenClaw",
      model: String(json?.model || "gpt-4o"),
    };
    myAgents.push(created);
    sendJson(response, 200, {
      id: created.id,
      code: created.code,
      runtime_type: created.runtime_type,
    });
    return;
  }

  if (method === "PUT" && pathname.startsWith("/api/agent/")) {
    const agentId = Number(pathname.replace("/api/agent/", ""));
    const target = myAgents.find((item) => item.id === agentId);
    if (!target) {
      sendError(response, 404, `Agent not found: ${agentId}`);
      return;
    }
    const { json } = await readBody(request);
    target.name = json?.name || target.name;
    target.description = json?.description || target.description;
    target.avatar = `https://api.dicebear.com/7.x/adventurer/svg?seed=${encodeURIComponent(String(target.name))}`;
    target.runtime_type = String(json?.runtime_type || target.runtime_type || "openclaw");
    target.runtime_label = target.runtime_type === "deeflow2" ? "DeeFlow2" : "OpenClaw";
    target.model = String(json?.model || target.model || "gpt-4o");
    sendJson(response, 200, null);
    return;
  }

  if (method === "GET" && pathname === "/agent_config/default") {
    sendJson(response, 200, agentTemplates);
    return;
  }

  if (method === "GET" && pathname.startsWith("/agent_config/")) {
    const code = decodeURIComponent(pathname.replace("/agent_config/", ""));
    const target = agentTemplates.find((item) => item.code === code);
    if (!target) {
      sendError(response, 404, `Agent template not found: ${code}`);
      return;
    }
    sendJson(response, 200, target);
    return;
  }

  if (method === "POST" && pathname === "/api/asr") {
    sendJson(response, 200, {
      text: "Mock transcription result for uploaded audio",
      language: "auto",
      duration: 3.2,
    });
    return;
  }

  if (method === "POST" && pathname === "/api/tts") {
    sendBinary(
      response,
      200,
      Buffer.from("MOCK_TTS_AUDIO"),
      "audio/mpeg",
      "tts.mp3",
    );
    return;
  }

  if (method === "POST" && pathname === "/api/audio/speech") {
    const { json } = await readBody(request);
    const format = String(json?.response_format || "mp3");
    const contentType = format === "wav"
      ? "audio/wav"
      : format === "opus"
        ? "audio/opus"
        : format === "pcm"
          ? "audio/pcm"
          : "audio/mpeg";
    sendBinary(
      response,
      200,
      Buffer.from(`MOCK_SPEECH_AUDIO_${format.toUpperCase()}`),
      contentType,
      `speech.${format}`,
    );
    return;
  }

  if (method === "GET" && pathname === "/api/platform/devices") {
    sendJson(response, 200, devices);
    return;
  }

  if (method === "GET" && pathname === "/api/platform/devices/account-state") {
    sendJson(response, 200, {
      installation_id: url.searchParams.get("installation_id") || "inst-demo-001",
      state: "current_user",
      can_register_current_account: true,
      current_user_device_id: devices[0].id,
      current_user_has_devices: true,
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/devices/pair-code") {
    sendJson(response, 200, {
      pair_code: "PAIR-DEMO",
      expires_in_seconds: 600,
      expires_at: new Date(Date.now() + 600_000).toISOString(),
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/devices/bootstrap") {
    const { json } = await readBody(request);
    sendJson(response, 200, {
      api_key: "mock-device-key",
      base_url: `http://127.0.0.1:${port}`,
      ws_url: `ws://127.0.0.1:${port}/api/openclaw/ws`,
      device_id: devices[0].id,
      device_name: json?.device_name || devices[0].device_name,
      installation_id: json?.installation_id || devices[0].installation_id,
      registration_mode: "bootstrap",
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/devices/claim") {
    const { json } = await readBody(request);
    sendJson(response, 200, {
      api_key: "mock-device-key",
      base_url: `http://127.0.0.1:${port}`,
      ws_url: `ws://127.0.0.1:${port}/api/openclaw/ws`,
      device_id: devices[0].id,
      device_name: json?.device_name || devices[0].device_name,
      installation_id: devices[0].installation_id,
      registration_mode: "claim",
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/devices/online") {
    sendJson(response, 200, {
      runtime_type: "openclaw",
      runtime_label: "OpenClaw",
      runtime_status: "ready",
      runtime_stage: "phase_device_bridge_ready",
      supports_device_bridge: true,
      supports_managed_download: true,
      online_team_ids: [defaultTeamId],
      notes: "Device Center currently manages the OpenClaw device bridge only.",
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/models") {
    sendJson(response, 200, buildPlatformModels());
    return;
  }

  if (method === "GET" && pathname === "/api/platform/models/providers") {
    sendJson(response, 200, buildModelProviderSummary());
    return;
  }

  if (method === "GET" && pathname === "/api/platform/models/route") {
    sendJson(response, 200, buildModelRouteProfile());
    return;
  }

  if (method === "GET" && pathname === "/api/platform/models/usage") {
    const days = Number(url.searchParams.get("days") || "30");
    sendJson(response, 200, buildModelUsageSummary(days));
    return;
  }

  if (method === "GET" && pathname === "/api/platform/models/cost") {
    const days = Number(url.searchParams.get("days") || "30");
    sendJson(response, 200, buildModelCostSummary(days));
    return;
  }

  if (method === "GET" && pathname === "/api/platform/models/quota") {
    sendJson(response, 200, buildModelQuotaSummary());
    return;
  }

  if (method === "PUT" && pathname === "/api/platform/models/route") {
    const { json } = await readBody(request);
    preferredModel = String(json?.preferred_model || preferredModel);
    sendJson(response, 200, buildModelRouteProfile());
    return;
  }

  if (method === "GET" && pathname === "/api/platform/models/resolve") {
    const modelName = url.searchParams.get("model_name") || "";
    const selected = pickModelByName(modelName);
    sendJson(response, 200, {
      requested_model: modelName,
      resolved_model: selected.model_name,
      provider_name: selected.provider_name,
      provider_model_id: selected.provider_model_id,
      candidate_count: buildPlatformModels().filter((item) => item.model_name === selected.model_name).length,
      selected,
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/models/invoke") {
    const { json } = await readBody(request);
    const chosenModel = pickModelByName(json?.model || json?.model_id || "");
    sendJson(response, 200, {
      text: `Mock response from ${chosenModel.model_name}: ${String(json?.prompt || "").slice(0, 80)}`,
      model: chosenModel.model_name,
      provider_name: chosenModel.provider_name,
      provider_model_id: chosenModel.provider_model_id,
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/channels") {
    sendJson(response, 200, {
      supported_count: channelItems.length,
      configured_count: channelItems.filter((item) => item.configured).length,
      active_count: channelItems.filter((item) => item.enabled).length,
      items: channelItems,
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/channels/wechat-work/config") {
    sendJson(response, 200, channelConfigs.wechat);
    return;
  }

  if (method === "POST" && pathname === "/api/platform/channels/wechat-work/config") {
    const { json } = await readBody(request);
    channelConfigs.wechat = {
      ...channelConfigs.wechat,
      corp_id: json?.corp_id || channelConfigs.wechat.corp_id,
      agent_id: json?.agent_id || channelConfigs.wechat.agent_id,
      secret: json?.secret || channelConfigs.wechat.secret,
      secret_configured: Boolean(json?.secret || channelConfigs.wechat.secret),
    };
    sendJson(response, 200, channelConfigs.wechat);
    return;
  }

  if (method === "GET" && pathname === "/api/platform/channels/feishu/config") {
    sendJson(response, 200, channelConfigs.feishu);
    return;
  }

  if (method === "GET" && pathname === "/api/platform/channels/wechat-personal-plugin/config") {
    sendJson(response, 200, channelConfigs.wechatPersonalPlugin);
    return;
  }

  if (method === "POST" && pathname === "/api/platform/channels/wechat-personal-plugin/config") {
    const { json } = await readBody(request);
    const kernelCorpId = json?.kernel_corp_id || channelConfigs.wechatPersonalPlugin.kernel_corp_id || "";
    const kernelAgentId = json?.kernel_agent_id || channelConfigs.wechatPersonalPlugin.kernel_agent_id || "";
    const kernelSecret = json?.kernel_secret || channelConfigs.wechatPersonalPlugin.kernel_secret || "";
    const kernelConfigured = Boolean(kernelCorpId && kernelAgentId && kernelSecret);
    const kernelSource = kernelConfigured ? "independent" : "unconfigured";
    channelConfigs.wechatPersonalPlugin = {
      ...channelConfigs.wechatPersonalPlugin,
      configured: kernelConfigured,
      enabled: Boolean(json?.enabled),
      binding_enabled: Boolean(json?.binding_enabled),
      display_name: json?.display_name || channelConfigs.wechatPersonalPlugin.display_name,
      assistant_name: json?.assistant_name || "",
      welcome_message: json?.welcome_message || "",
      kernel_source: kernelSource,
      kernel_configured: kernelConfigured,
      kernel_isolated: kernelConfigured,
      kernel_corp_id: kernelCorpId,
      kernel_agent_id: kernelAgentId,
      kernel_secret: kernelSecret ? "moc****cret" : "",
      kernel_secret_configured: Boolean(kernelSecret),
      kernel_verify_token:
        json?.kernel_verify_token ||
        channelConfigs.wechatPersonalPlugin.kernel_verify_token ||
        (kernelConfigured ? "mock-plugin-verify-token" : ""),
      kernel_aes_key:
        json?.kernel_aes_key ||
        channelConfigs.wechatPersonalPlugin.kernel_aes_key ||
        (kernelConfigured ? "mock-plugin-aes-key" : ""),
      effective_kernel_corp_id: kernelConfigured ? kernelCorpId : "",
      effective_kernel_agent_id: kernelConfigured ? kernelAgentId : "",
      effective_kernel_verify_token:
        json?.kernel_verify_token ||
        channelConfigs.wechatPersonalPlugin.kernel_verify_token ||
        (kernelConfigured ? "mock-plugin-verify-token" : ""),
      effective_kernel_aes_key:
        json?.kernel_aes_key ||
        channelConfigs.wechatPersonalPlugin.kernel_aes_key ||
        (kernelConfigured ? "mock-plugin-aes-key" : ""),
      setup_status: kernelConfigured && (json?.binding_enabled || json?.enabled) ? "beta" : "planned",
      capability_stage: kernelConfigured ? "phase_3_callback_runtime" : "phase_2_binding_mvp",
      updated_time: now(),
    };
    channelItems[2] = { ...channelConfigs.wechatPersonalPlugin };
    sendJson(response, 200, channelConfigs.wechatPersonalPlugin);
    return;
  }

  if (method === "GET" && pathname === "/api/platform/channels/wechat-personal-openclaw/config") {
    sendJson(response, 200, channelConfigs.wechatPersonalOpenClaw);
    return;
  }

  if (method === "POST" && pathname === "/api/platform/channels/wechat-personal-openclaw/qr/start") {
    const { json } = await readBody(request);
    const boundBinding = channelBindings.find(
      (item) => item.channel_key === "wechat_personal_openclaw" && item.status === "bound",
    );
    if (boundBinding && !json?.force_refresh) {
      sendJson(response, 200, {
        status: "bound",
        message: `当前个人微信已绑定到 ${boundBinding.binding_target_name || boundBinding.binding_target_id}。`,
        qr_data_url: "",
        qr_url: "",
        session_id: "",
        account_id: boundBinding.identity?.external_user_id || "wx-openclaw-user-001",
        expires_at: null,
        connected: true,
        binding: boundBinding,
      });
      return;
    }

    officialQrSession = {
      status: "ready",
      message: "二维码已生成，请使用手机微信扫码。",
      qr_data_url: "data:image/png;base64,mock-openclaw-qr",
      qr_url: "",
      session_id: `wx-session-${randomUUID().slice(0, 8)}`,
      account_id: json?.account_id || "wx-openclaw-user-001",
      expires_at: new Date(Date.now() + 5 * 60_000).toISOString(),
      connected: false,
      raw: {
        provider: "wechat",
        mode: "official_plugin",
      },
    };
    sendJson(response, 200, officialQrSession);
    return;
  }

  if (method === "GET" && pathname === "/api/platform/channels/wechat-personal-openclaw/qr/status") {
    const sessionId = url.searchParams.get("session_id") || officialQrSession?.session_id || "";
    const accountId = url.searchParams.get("account_id") || officialQrSession?.account_id || "wx-openclaw-user-001";
    const binding = channelBindings.find((item) => item.channel_key === "wechat_personal_openclaw");
    if (binding) {
      binding.status = "bound";
      binding.bound_by_user_id = 1;
      binding.bound_at = binding.bound_at || now();
      binding.updated_time = now();
      binding.identity = {
        id: 1,
        external_user_id: accountId,
        external_union_id: null,
        nickname: "Mock OpenClaw User",
        avatar_url: null,
        status: "active",
        last_seen_at: now(),
      };
    }

    officialQrSession = {
      status: "bound",
      message: "个人微信官方插件已连接成功。",
      qr_data_url: "",
      qr_url: "",
      session_id: sessionId,
      account_id: accountId,
      expires_at: officialQrSession?.expires_at || null,
      connected: true,
      binding: binding || null,
      raw: {
        provider: "wechat",
        mode: "official_plugin",
      },
    };
    sendJson(response, 200, officialQrSession);
    return;
  }

  if (method === "GET" && pathname === "/api/platform/channels/bindings") {
    sendJson(response, 200, {
      items: channelBindings,
      total: channelBindings.length,
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/channels/bindings/create") {
    const { json } = await readBody(request);
    const binding = {
      id: channelBindings.length + 1,
      team_id: Number(json?.team_id || 1),
      channel_key: json?.channel_key || "wechat_personal_plugin",
      binding_type: json?.binding_type || "assistant",
      binding_target_id: json?.binding_target_id || "",
      binding_target_name: json?.binding_target_name || "",
      binding_code: `BIND${String(channelBindings.length + 1).padStart(4, "0")}`,
      code_expires_at: now(),
      status: "pending",
      created_by_user_id: 1,
      bound_by_user_id: null,
      binding_enabled_snapshot: true,
      notes: json?.notes || null,
      bound_at: null,
      created_time: now(),
      updated_time: now(),
      identity: null,
    };
    channelBindings = [binding, ...channelBindings];
    sendJson(response, 200, binding);
    return;
  }

  if (method === "POST" && pathname === "/api/platform/channels/bindings/disable") {
    const { json } = await readBody(request);
    const binding = channelBindings.find((item) => item.id === Number(json?.binding_id));
    if (!binding) {
      sendJson(response, 404, { detail: "绑定记录不存在" });
      return;
    }
    binding.status = "disabled";
    binding.updated_time = now();
    sendJson(response, 200, binding);
    return;
  }

  if (method === "POST" && pathname === "/api/platform/channels/bindings/regenerate-code") {
    const { json } = await readBody(request);
    const binding = channelBindings.find((item) => item.id === Number(json?.binding_id));
    if (!binding) {
      sendJson(response, 404, { detail: "绑定记录不存在" });
      return;
    }
    binding.binding_code = `BIND${String(binding.id).padStart(4, "0")}-${Date.now().toString().slice(-4)}`;
    binding.updated_time = now();
    if (binding.status === "disabled" || binding.status === "expired") {
      binding.status = "pending";
    }
    sendJson(response, 200, binding);
    return;
  }

  if (method === "POST" && pathname === "/api/platform/channels/feishu/config") {
    const { json } = await readBody(request);
    channelConfigs.feishu = {
      ...channelConfigs.feishu,
      app_id: json?.app_id || channelConfigs.feishu.app_id,
      app_secret: json?.app_secret || channelConfigs.feishu.app_secret,
      verification_token: json?.verification_token || channelConfigs.feishu.verification_token,
      encrypt_key: json?.encrypt_key || channelConfigs.feishu.encrypt_key,
      secret_configured: Boolean(json?.app_secret || channelConfigs.feishu.app_secret),
    };
    sendJson(response, 200, channelConfigs.feishu);
    return;
  }

  if (method === "GET" && pathname === "/api/platform/conversations") {
    sendJson(response, 200, {
      stats: {
        group_count: groups.length,
        msg_count: historyMessages.length + Object.values(groupMessages).flat().length,
        entity_count: 1,
        history_count: historyMessages.length,
      },
      groups,
      history: historyMessages,
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/conversations/stats") {
    sendJson(response, 200, {
      group_count: groups.length,
      msg_count: historyMessages.length + Object.values(groupMessages).flat().length,
      entity_count: 1,
      history_count: historyMessages.length,
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/conversations/groups") {
    sendJson(response, 200, groups);
    return;
  }

  if (method === "GET" && pathname.startsWith("/api/platform/conversations/groups/") && pathname.endsWith("/messages")) {
    const roomId = decodeURIComponent(pathname.split("/")[5] || "");
    sendJson(response, 200, groupMessages[roomId] || []);
    return;
  }

  if (method === "GET" && pathname === "/api/platform/conversations/history") {
    sendJson(response, 200, historyMessages);
    return;
  }

  if (method === "POST" && pathname === "/api/platform/conversations/messages") {
    const { json } = await readBody(request);
    const created = {
      id: Date.now(),
      sender_id: 1,
      agent_id: json?.agent_id || null,
      channel_id: json?.channel_id || "manual",
      direction: json?.direction || "user_to_agent",
      content: json?.content || "",
      created_time: now(),
    };
    historyMessages.unshift(created);
    sendJson(response, 200, created);
    return;
  }

  if (method === "POST" && pathname === "/api/platform/memory/store") {
    const { json } = await readBody(request);
    const scope = buildRuntimeScope(json || {});
    const entry = {
      id: `mem-${Date.now()}`,
      content: String(json?.content || ""),
      category: json?.category || "other",
      importance: json?.importance || 0.5,
      team_id: scope.team_id ?? defaultTeamId,
      runtime_type: scope.runtime_type ?? "openclaw",
      device_id: scope.device_id ?? null,
      agent_id: scope.agent_id ?? null,
      source_session: json?.source_session || null,
      created_at: now(),
    };
    memories.unshift(entry);
    sendJson(response, 200, entry);
    return;
  }

  if (method === "POST" && pathname === "/api/platform/memory/search") {
    const { json } = await readBody(request);
    const scope = buildRuntimeScope(json || {});
    const query = String(json?.query || "").toLowerCase();
    const limit = Number(json?.limit || 5);
    const results = filterByRuntimeScope(memories, scope)
      .filter((item) => item.content.toLowerCase().includes(query))
      .slice(0, limit);
    sendJson(response, 200, results);
    return;
  }

  if (method === "DELETE" && pathname.startsWith("/api/platform/memory/agent/")) {
    const agentId = decodeURIComponent(pathname.replace("/api/platform/memory/agent/", ""));
    const scope = buildRuntimeScopeFromSearchParams(url.searchParams);
    let clearedCount = 0;
    for (let index = memories.length - 1; index >= 0; index -= 1) {
      if (
        memories[index].agent_id === agentId &&
        matchesRuntimeScope(memories[index], { ...scope, agent_id: agentId })
      ) {
        memories.splice(index, 1);
        clearedCount += 1;
      }
    }
    sendJson(response, 200, {
      cleared_count: clearedCount,
      resolved_scope: serializeRuntimeScope({ ...scope, agent_id: agentId }),
    });
    return;
  }

  if (method === "DELETE" && pathname.startsWith("/api/platform/memory/")) {
    const entryId = decodeURIComponent(pathname.replace("/api/platform/memory/", ""));
    const scope = buildRuntimeScopeFromSearchParams(url.searchParams);
    const index = memories.findIndex((item) => item.id === entryId && matchesRuntimeScope(item, scope));
    if (index >= 0) {
      memories.splice(index, 1);
    }
    sendJson(response, 200, {
      deleted: index >= 0,
      resolved_scope: serializeRuntimeScope(scope),
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/memory/stats") {
    const scope = buildRuntimeScopeFromSearchParams(url.searchParams);
    const scopedMemories = filterByRuntimeScope(memories, scope);
    sendJson(response, 200, {
      total: scopedMemories.length,
      by_category: scopedMemories.reduce((acc, item) => {
        acc[item.category] = (acc[item.category] || 0) + 1;
        return acc;
      }, {}),
      resolved_scope: serializeRuntimeScope(scope),
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/knowledge/upload") {
    const { raw, json } = await readBody(request);
    const formFields = parseFormFields(String(request.headers["content-type"] || ""), raw);
    const scope = buildRuntimeScope({
      team_id: formFields.team_id ?? json?.team_id,
      runtime_type: formFields.runtime_type ?? json?.runtime_type,
      device_id: formFields.device_id ?? json?.device_id,
      agent_id: formFields.agent_id ?? json?.agent_id,
    });
    const filename = String(formFields.file || formFields.filename || `upload-${Date.now()}.txt`);
    const sourceName = String(formFields.source_name || json?.source_name || filename);
    const asset = {
      source_name: sourceName,
      filename,
      size: Number(request.headers["content-length"] || 0),
      status: "indexed",
      team_id: scope.team_id ?? defaultTeamId,
      runtime_type: scope.runtime_type ?? "openclaw",
      device_id: scope.device_id ?? null,
      agent_id: scope.agent_id ?? null,
      updated_at: now(),
    };
    knowledgeAssets.unshift(asset);
    sendJson(response, 200, {
      accepted: true,
      asset,
      resolved_scope: serializeRuntimeScope(scope),
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/knowledge/list") {
    const page = Number(url.searchParams.get("page") || 1);
    const pageSize = Number(url.searchParams.get("pageSize") || 20);
    const scope = buildRuntimeScopeFromSearchParams(url.searchParams);
    const scopedAssets = filterByRuntimeScope(knowledgeAssets, scope);
    sendJson(response, 200, {
      list: paginate(scopedAssets, page, pageSize),
      total: scopedAssets.length,
      page,
      pageSize,
      resolved_scope: serializeRuntimeScope(scope),
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/knowledge/search") {
    const scope = buildRuntimeScopeFromSearchParams(url.searchParams);
    const query = String(url.searchParams.get("query") || url.searchParams.get("filename") || "").toLowerCase();
    const limit = Number(url.searchParams.get("limit") || 5);
    const results = filterByRuntimeScope(knowledgeAssets, scope)
      .filter((item) => item.filename.toLowerCase().includes(query) || item.source_name.toLowerCase().includes(query))
      .slice(0, limit);
    sendJson(response, 200, results);
    return;
  }

  if (method === "POST" && pathname === "/api/platform/knowledge/delete") {
    const sourceName = url.searchParams.get("source_name") || "";
    const scope = buildRuntimeScopeFromSearchParams(url.searchParams);
    const index = knowledgeAssets.findIndex((item) => item.source_name === sourceName && matchesRuntimeScope(item, scope));
    if (index >= 0) {
      knowledgeAssets.splice(index, 1);
    }
    sendJson(response, 200, {
      deleted: index >= 0,
      source_name: sourceName,
      resolved_scope: serializeRuntimeScope(scope),
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/knowledge/download") {
    const sourceName = url.searchParams.get("source_name") || "";
    const mode = url.searchParams.get("mode") || "path";
    const scope = buildRuntimeScopeFromSearchParams(url.searchParams);
    const target = knowledgeAssets.find((item) => item.source_name === sourceName && matchesRuntimeScope(item, scope));
    const content = `Mock content for ${sourceName || "knowledge asset"}`;
    sendJson(response, 200, mode === "base64"
      ? {
          source_name: sourceName,
          mode,
          runtime_type: target?.runtime_type || scope.runtime_type || "openclaw",
          agent_id: target?.agent_id || scope.agent_id || null,
          data_base64: Buffer.from(content).toString("base64"),
        }
      : {
          source_name: sourceName,
          mode,
          runtime_type: target?.runtime_type || scope.runtime_type || "openclaw",
          agent_id: target?.agent_id || scope.agent_id || null,
          path: `/tmp/${sourceName || "mock-knowledge.txt"}`,
        });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/knowledge/stats") {
    const scope = buildRuntimeScopeFromSearchParams(url.searchParams);
    const scopedAssets = filterByRuntimeScope(knowledgeAssets, scope);
    sendJson(response, 200, {
      assetCount: scopedAssets.length,
      indexedCount: scopedAssets.filter((item) => item.status === "indexed").length,
      lastSyncAt: knowledgeConfig.lastSyncAt,
      resolved_scope: serializeRuntimeScope(scope),
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/knowledge/config") {
    const scope = buildRuntimeScopeFromSearchParams(url.searchParams);
    sendJson(response, 200, {
      ...knowledgeConfig,
      runtime_type: scope.runtime_type || "openclaw",
      agent_id: scope.agent_id || null,
      device_id: scope.device_id || null,
      supportsDeviceBridge: scope.runtime_type === "deeflow2" ? false : true,
      resolved_scope: serializeRuntimeScope(scope),
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/knowledge/config/update") {
    const scope = buildRuntimeScopeFromSearchParams(url.searchParams);
    knowledgeConfig = {
      ...knowledgeConfig,
      watchDir: url.searchParams.get("watchDir") || knowledgeConfig.watchDir,
      lastSyncAt: now(),
    };
    sendJson(response, 200, {
      ...knowledgeConfig,
      runtime_type: scope.runtime_type || "openclaw",
      agent_id: scope.agent_id || null,
      device_id: scope.device_id || null,
      supportsDeviceBridge: scope.runtime_type === "deeflow2" ? false : true,
      resolved_scope: serializeRuntimeScope(scope),
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/policy/tool-access/check") {
    const { json } = await readBody(request);
    const risk = String(json?.risk_level || "medium");
    const toolName = String(json?.tool_name || "");
    const blocked = risk === "critical" || toolName.includes("delete");
    sendJson(response, 200, {
      allowed: !blocked,
      reason: blocked ? "Blocked by mock tool policy" : "Allowed by mock tool policy",
      matchedPolicy: blocked ? "mock.tool.block" : "mock.tool.allow",
      requiresApproval: risk === "high" || risk === "critical" || Boolean(json?.requires_approval),
      checkedAt: now(),
      checkedFor: { tool_name: toolName, risk_level: risk },
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/policy/data-access/check") {
    const { json } = await readBody(request);
    const classification = String(json?.classification || "internal");
    const blocked = classification === "secret";
    sendJson(response, 200, {
      allowed: !blocked,
      reason: blocked ? "Secret data is blocked in mock policy" : "Allowed by mock data policy",
      matchedPolicy: blocked ? "mock.data.block" : "mock.data.allow",
      requiresApproval: classification === "restricted" || classification === "secret" || Boolean(json?.requires_approval),
      checkedAt: now(),
      checkedFor: { resource_type: json?.resource_type, classification },
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/policy/exec-access/check") {
    const { json } = await readBody(request);
    const command = String(json?.command || "");
    const risk = String(json?.risk_level || "medium");
    const blocked = command.includes("rm -rf") || risk === "critical";
    sendJson(response, 200, {
      allowed: !blocked,
      reason: blocked ? "High-risk command blocked by mock exec policy" : "Allowed by mock exec policy",
      matchedPolicy: blocked ? "mock.exec.block" : "mock.exec.allow",
      requiresApproval: risk === "high" || risk === "critical" || Boolean(json?.requires_approval),
      checkedAt: now(),
      checkedFor: { command, risk_level: risk },
    });
    return;
  }

  if (method === "POST" && pathname === "/api/platform/approvals/request") {
    const { json } = await readBody(request);
    const item = {
      approval_id: `apr-${Date.now()}`,
      status: "pending",
      approval_type: json?.approval_type || "custom",
      title: json?.title || "Mock approval",
      reason: json?.reason || "Mock reason",
      risk_level: json?.risk_level || "medium",
      payload: json?.payload || {},
      requested_by: { user_id: 1, username: "demo" },
      resolved_by: null,
      resolution_comment: null,
      created_at: now(),
      expires_at: new Date(Date.now() + Number(json?.expires_in_seconds || 3600) * 1000).toISOString(),
      resolved_at: null,
    };
    approvals.unshift(item);
    sendJson(response, 200, item);
    return;
  }

  if (method === "GET" && pathname === "/api/platform/approvals") {
    const page = Number(url.searchParams.get("page") || 1);
    const pageSize = Number(url.searchParams.get("page_size") || 20);
    const status = url.searchParams.get("status");
    const items = approvals.filter((item) => !status || item.status === status);
    sendJson(response, 200, {
      total: items.length,
      page,
      page_size: pageSize,
      items: paginate(items, page, pageSize),
    });
    return;
  }

  if (method === "GET" && pathname.startsWith("/api/platform/approvals/")) {
    const approvalId = decodeURIComponent(pathname.replace("/api/platform/approvals/", ""));
    const item = approvals.find((entry) => entry.approval_id === approvalId);
    if (!item) {
      sendError(response, 404, `Approval not found: ${approvalId}`);
      return;
    }
    sendJson(response, 200, item);
    return;
  }

  if (method === "POST" && pathname.startsWith("/api/platform/approvals/") && pathname.endsWith("/resolve")) {
    const approvalId = decodeURIComponent(pathname.split("/")[4] || "");
    const item = approvals.find((entry) => entry.approval_id === approvalId);
    if (!item) {
      sendError(response, 404, `Approval not found: ${approvalId}`);
      return;
    }
    const { json } = await readBody(request);
    item.status = json?.approved ? "approved" : "rejected";
    item.resolution_comment = json?.comment || null;
    item.resolved_by = { user_id: 2, username: "reviewer" };
    item.resolved_at = now();
    sendJson(response, 200, item);
    return;
  }

  if (method === "GET" && pathname === "/api/platform/audit/events") {
    const page = Number(url.searchParams.get("page") || 1);
    const pageSize = Number(url.searchParams.get("page_size") || 50);
    const items = [...auditEvents, ...approvals.map(approvalToAuditEvent)];
    sendJson(response, 200, {
      total: items.length,
      page,
      page_size: pageSize,
      items: paginate(items, page, pageSize),
    });
    return;
  }

  if (method === "GET" && pathname === "/api/platform/audit/summary") {
    sendJson(response, 200, buildAuditSummary());
    return;
  }

  if (
    method === "POST" &&
    (pathname === "/api/platform/audit/events" || pathname === "/api/monitor/log")
  ) {
    const { json } = await readBody(request);
    auditEvents.unshift({
      event_id: `evt-${Date.now()}`,
      category: "operation",
      event_type: json?.action_type || "operation",
      title: json?.title || "SDK log",
      summary: null,
      module: json?.module || "sdk",
      path: json?.path || null,
      status: "success",
      risk_level: "low",
      actor: { user_id: 1, username: "demo" },
      metadata: json || {},
      created_at: now(),
    });
    sendJson(response, 200, null);
    return;
  }

  if (method === "GET" && pathname.startsWith("/api/workflows/executions/") && pathname.endsWith("/logs")) {
    sendJson(response, 200, [
      { level: "info", message: "Mock workflow started", created_at: now() },
      { level: "info", message: "Mock workflow finished", created_at: now() },
    ]);
    return;
  }

  sendError(response, 404, `Mock route not found: ${method} ${pathname}`);
});

server.listen(port, "127.0.0.1", () => {
  process.stdout.write(
    `qeeclaw mock platform server listening on http://127.0.0.1:${port}\n`,
  );
});

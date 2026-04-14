import { createQeeClawClient } from "../../qeeclaw-core-sdk/dist/index.js";
import { createQeeClawProductSDK } from "../../qeeclaw-product-sdk/dist/index.js";

const STORAGE_KEY = "qeeclaw.sales-cockpit-web-verifier.config";

const form = document.querySelector("#config-form");
const baseUrlInput = document.querySelector("#base-url");
const tokenInput = document.querySelector("#token");
const teamIdInput = document.querySelector("#team-id");
const runtimeTypeInput = document.querySelector("#runtime-type");
const agentIdInput = document.querySelector("#agent-id");
const scopeInput = document.querySelector("#scope");
const prefillButton = document.querySelector("#prefill-online");
const runButton = document.querySelector("#run-checks");
const banner = document.querySelector("#status-banner");
const summaryCards = document.querySelector("#summary-cards");
const resultList = document.querySelector("#result-list");

function readConfig() {
  return {
    baseUrl: baseUrlInput.value.trim(),
    token: normalizeToken(tokenInput.value),
    teamId: teamIdInput.value.trim(),
    runtimeType: runtimeTypeInput.value.trim() || "openclaw",
    agentId: agentIdInput.value.trim() || "sales-copilot",
    scope: scopeInput.value || "mine",
  };
}

function writeConfig(config) {
  baseUrlInput.value = config.baseUrl ?? "";
  tokenInput.value = normalizeToken(config.token ?? "");
  teamIdInput.value = config.teamId ?? "";
  runtimeTypeInput.value = config.runtimeType ?? "openclaw";
  agentIdInput.value = config.agentId ?? "sales-copilot";
  scopeInput.value = config.scope ?? "mine";
}

function saveConfig() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(readConfig()));
}

function loadSavedConfig() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    writeConfig({
      baseUrl: "",
      token: "",
      teamId: "",
      runtimeType: "openclaw",
      agentId: "sales-copilot",
      scope: "mine",
    });
    return;
  }

  try {
    writeConfig(JSON.parse(raw));
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function setBanner(state, message) {
  banner.className = `status-banner ${state}`;
  banner.textContent = message;
}

function normalizeToken(value) {
  return value.trim().replace(/^Bearer\s+/i, "");
}

function summarizeError(error) {
  if (!error) {
    return "Unknown error";
  }

  if (typeof error === "string") {
    return error;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return String(error);
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderSummary(results, context) {
  const successCount = results.filter((item) => item.status === "success").length;
  const errorCount = results.filter((item) => item.status === "error").length;
  const pendingCount = results.length - successCount - errorCount;

  summaryCards.innerHTML = `
    <article class="summary-card ${errorCount === 0 ? "success" : "error"}">
      <h3>验证结果</h3>
      <div class="big">${successCount}/${results.length}</div>
      <p>${errorCount === 0 ? "所有关键验证项都已通过。" : `有 ${errorCount} 项失败，需要继续排查。`}</p>
    </article>
    <article class="summary-card ${context.teamId ? "success" : "pending"}">
      <h3>当前上下文</h3>
      <div class="big">${context.teamId || "-"}</div>
      <p>teamId / runtimeType / agentId: ${context.runtimeType || "-"} / ${context.agentId || "-"}</p>
    </article>
    <article class="summary-card ${pendingCount > 0 ? "pending" : "success"}">
      <h3>账号信息</h3>
      <div class="big">${context.username || "-"}</div>
      <p>${context.teamCount ? `可用团队 ${context.teamCount} 个` : "尚未读取到团队上下文"}</p>
    </article>
  `;
}

function renderResults(results) {
  resultList.innerHTML = results
    .map((item) => {
      const summary = item.summary ? `<div class="result-meta">${escapeHtml(item.summary)}</div>` : "";
      const payload = item.payload !== undefined ? `<pre>${escapeHtml(pretty(item.payload))}</pre>` : "";
      return `
        <article class="result-card">
          <div class="result-head">
            <div class="result-title">
              <h3>${escapeHtml(item.title)}</h3>
              <p>${escapeHtml(item.description)}</p>
            </div>
            <span class="pill ${item.status}">${item.status.toUpperCase()}</span>
          </div>
          <div class="result-body">
            ${summary}
            ${payload}
          </div>
        </article>
      `;
    })
    .join("");
}

async function runStep(title, description, fn, summarize) {
  try {
    const payload = await fn();
    return {
      title,
      description,
      status: "success",
      summary: summarize ? summarize(payload) : "验证通过",
      payload,
    };
  } catch (error) {
    return {
      title,
      description,
      status: "error",
      summary: summarizeError(error),
      payload: {
        error: summarizeError(error),
      },
    };
  }
}

function buildRuntimeScope(context) {
  return {
    teamId: context.teamId,
    runtimeType: context.runtimeType,
    ...(context.agentId ? { agentId: context.agentId } : {}),
  };
}

async function runVerification() {
  const config = readConfig();

  if (!config.baseUrl || !config.token) {
    setBanner("error", "请先填写 Base URL 和 Token。");
    return;
  }

  saveConfig();
  runButton.disabled = true;
  prefillButton.disabled = true;
  setBanner("running", "正在连接 QeeClaw 平台并执行验证，请稍候...");
  summaryCards.innerHTML = "";
  resultList.innerHTML = "";

  const client = createQeeClawClient({
    baseUrl: config.baseUrl,
    token: config.token,
    userAgent: "sales-cockpit-web-verifier",
  });
  const product = createQeeClawProductSDK(client);

  const context = {
    teamId: config.teamId ? Number(config.teamId) : null,
    runtimeType: config.runtimeType || "openclaw",
    agentId: config.agentId || "sales-copilot",
    username: "",
    teamCount: 0,
  };

  const results = [];

  const tenantResult = await runStep(
    "团队上下文",
    "读取 tenant.getCurrentContext()，确认当前账号是否能识别团队范围。",
    async () => {
      const tenant = await client.tenant.getCurrentContext();
      context.teamCount = tenant.teams?.length ?? 0;
      if (!context.teamId && tenant.teams?.length) {
        context.teamId = Number(tenant.teams[0].id);
        teamIdInput.value = String(context.teamId);
        saveConfig();
      }
      return tenant;
    },
    (tenant) => `读取成功，可用团队 ${tenant.teams?.length ?? 0} 个。`
  );
  results.push(tenantResult);

  const profileResult = await runStep(
    "当前账号",
    "读取 iam.getProfile()，确认 token 对应账号是否正常。",
    async () => {
      const profile = await client.iam.getProfile();
      context.username = profile.username || "";
      return profile;
    },
    (profile) => `当前账号：${profile.username || "unknown"}`
  );
  results.push(profileResult);

  if (!context.teamId) {
    results.push({
      title: "销售驾驶仓装配验证",
      description: "由于未能拿到 teamId，后续依赖团队范围的验证项已跳过。",
      status: "error",
      summary: "teamId 缺失，无法继续验证销售驾驶仓相关 kit。",
      payload: {
        hint: "请手动填写 Team ID，或确认 tenant.getCurrentContext() 能返回可用团队。",
      },
    });

    renderSummary(results, context);
    renderResults(results);
    setBanner("error", "未获取到 teamId，验证已提前结束。");
    runButton.disabled = false;
    prefillButton.disabled = false;
    return;
  }

  const runtimeScope = buildRuntimeScope(context);

  const checks = [
    {
      title: "模型目录",
      description: "验证 Core SDK 的 models.listAvailable() 是否可用。",
      fn: () => client.models.listAvailable(),
      summarize: (items) => `模型数：${items.length ?? 0}`,
    },
    {
      title: "模型路由",
      description: "验证 models.getRouteProfile() 是否返回默认路由信息。",
      fn: () => client.models.getRouteProfile(),
      summarize: (payload) => `默认模型：${payload.resolvedModel || payload.preferredModel || "unknown"}`,
    },
    {
      title: "Runtime 摘要",
      description: "验证 models.listRuntimes() 是否能识别当前 runtime 能力。",
      fn: () => client.models.listRuntimes(),
      summarize: (items) => `runtime 数：${items.length ?? 0}`,
    },
    {
      title: "渠道中心",
      description: "验证 product.channelCenter.loadHome(teamId) 能否聚合渠道数据。",
      fn: () => product.channelCenter.loadHome(context.teamId),
      summarize: (payload) => `activeCount：${payload.overview?.activeCount ?? payload.overview?.active_count ?? "-"}`,
    },
    {
      title: "会话中心",
      description: "验证 product.conversationCenter.loadHome(teamId) 能否聚合会话数据。",
      fn: () => product.conversationCenter.loadHome(context.teamId),
      summarize: (payload) => `群聊数：${payload.stats?.groupCount ?? payload.stats?.group_count ?? "-"}`,
    },
    {
      title: "治理中心",
      description: "验证 product.governanceCenter.loadHome(scope) 能否聚合审批与审计信息。",
      fn: () => product.governanceCenter.loadHome(config.scope),
      summarize: (payload) => `审计总数：${payload.summary?.total ?? "-"}`,
    },
    {
      title: "知识中心",
      description: "验证 product.knowledgeCenter.loadHome(runtimeScope) 是否能聚合知识统计。",
      fn: () => product.knowledgeCenter.loadHome(runtimeScope),
      summarize: (payload) => `知识资产：${payload.stats?.assetCount ?? payload.stats?.asset_count ?? "-"}`,
    },
    {
      title: "销售驾驶仓首页",
      description: "验证 product.salesCockpit.loadHome(teamId, scope) 是否可用。",
      fn: () => product.salesCockpit.loadHome(context.teamId, config.scope),
      summarize: (payload) => `摘要模块：${Object.keys(payload.summary || {}).length}`,
    },
    {
      title: "销售知识助手",
      description: "验证 product.salesKnowledge.loadAssistantContext(runtimeScope) 是否能返回销售助手上下文。",
      fn: () => product.salesKnowledge.loadAssistantContext(runtimeScope),
      summarize: (payload) => `话术数：${payload.talkTracks?.length ?? 0}`,
    },
    {
      title: "销售培训与复盘",
      description: "验证 product.salesCoaching.loadTrainingOverview(teamId, scope) 是否可用。",
      fn: () => product.salesCoaching.loadTrainingOverview(context.teamId, config.scope),
      summarize: (payload) => `训练任务数：${payload.trainingTasks?.length ?? 0}`,
    },
  ];

  for (const check of checks) {
    results.push(await runStep(check.title, check.description, check.fn, check.summarize));
  }

  renderSummary(results, context);
  renderResults(results);

  const hasErrors = results.some((item) => item.status === "error");
  setBanner(
    hasErrors ? "error" : "success",
    hasErrors
      ? "验证完成，但有部分能力未通过。请根据分项结果排查权限、CORS、teamId 或数据准备情况。"
      : "验证完成，核心 SDK 与销售驾驶仓相关 Product SDK 能力均已跑通。"
  );

  runButton.disabled = false;
  prefillButton.disabled = false;
}

function prefillOnline() {
  writeConfig({
    ...readConfig(),
    baseUrl: "https://paas.qeeshu.com",
    runtimeType: "openclaw",
    agentId: "sales-copilot",
    scope: "mine",
  });
  saveConfig();
  setBanner("idle", "已填入线上环境示例，请继续补充 Token 和 Team ID。");
}

loadSavedConfig();

form.addEventListener("input", () => {
  saveConfig();
});

prefillButton.addEventListener("click", prefillOnline);
runButton.addEventListener("click", () => {
  void runVerification();
});

import { createQeeClawClient } from "../../qeeclaw-core-sdk/dist/index.js";
import { createQeeClawProductSDK } from "../../qeeclaw-product-sdk/dist/index.js";

const STORAGE_KEY = "qeeclaw.sales-cockpit-starter-web.config";

const form = document.querySelector("#config-form");
const baseUrlInput = document.querySelector("#base-url");
const tokenInput = document.querySelector("#token");
const teamIdInput = document.querySelector("#team-id");
const runtimeTypeInput = document.querySelector("#runtime-type");
const agentIdInput = document.querySelector("#agent-id");
const scopeInput = document.querySelector("#scope");
const prefillButton = document.querySelector("#prefill-online");
const loadButton = document.querySelector("#load-dashboard");
const exportButton = document.querySelector("#export-snapshot");
const statusBanner = document.querySelector("#status-banner");
const contextStrip = document.querySelector("#context-strip");
const summaryGrid = document.querySelector("#summary-grid");
const boardGrid = document.querySelector("#board-grid");

let latestSnapshot = null;

function normalizeToken(value) {
  return value.trim().replace(/^Bearer\s+/i, "");
}

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
  const defaults = {
    baseUrl: "",
    token: "",
    teamId: "",
    runtimeType: "openclaw",
    agentId: "sales-copilot",
    scope: "mine",
  };

  if (!raw) {
    writeConfig(defaults);
    return;
  }

  try {
    writeConfig({
      ...defaults,
      ...JSON.parse(raw),
    });
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    writeConfig(defaults);
  }
}

function setBanner(state, message) {
  statusBanner.className = `status-banner ${state}`;
  statusBanner.textContent = message;
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

async function runTask(loader) {
  try {
    return {
      ok: true,
      data: await loader(),
      error: null,
    };
  } catch (error) {
    return {
      ok: false,
      data: null,
      error: summarizeError(error),
    };
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function formatNumber(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return new Intl.NumberFormat("zh-CN").format(value);
}

function formatMoney(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  if (Math.abs(value) >= 1000) {
    return new Intl.NumberFormat("zh-CN", {
      maximumFractionDigits: 0,
    }).format(value);
  }
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDateTime(value) {
  if (!value) {
    return "时间未知";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function safeText(value, fallback = "--") {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  return String(value);
}

function pickNumber(...candidates) {
  for (const candidate of candidates) {
    if (typeof candidate === "number" && !Number.isNaN(candidate)) {
      return candidate;
    }
  }
  return null;
}

function getSection(snapshot, key) {
  return snapshot.sections[key] ?? { ok: false, data: null, error: "Section not found" };
}

function isSectionOk(snapshot, key) {
  return Boolean(getSection(snapshot, key).ok);
}

function getSectionData(snapshot, key) {
  const section = getSection(snapshot, key);
  return section.ok ? section.data : null;
}

function renderContextStrip(snapshot) {
  const routeProfile = snapshot.meta.routeProfile;
  const runtimes = snapshot.meta.runtimes || [];
  const runtimeSummary =
    runtimes.find((item) => item.runtimeType === snapshot.context.runtimeType) ||
    runtimes.find((item) => item.isDefault) ||
    null;

  contextStrip.innerHTML = [
    {
      label: "当前账号",
      value: snapshot.context.username || "--",
      note: `${snapshot.context.role || "--"} / 团队 ${formatNumber(snapshot.context.teamCount)}`,
    },
    {
      label: "团队范围",
      value: safeText(snapshot.context.teamId),
      note: `${snapshot.context.scope} / ${snapshot.context.enterpriseVerified ? "企业已认证" : "企业未认证"}`,
    },
    {
      label: "Runtime",
      value: runtimeSummary?.runtimeLabel || snapshot.context.runtimeType || "--",
      note: runtimeSummary?.notes || `agentId: ${snapshot.context.agentId || "--"}`,
    },
    {
      label: "默认模型",
      value: routeProfile?.resolvedModel || routeProfile?.preferredModel || "--",
      note: routeProfile?.resolutionReason || "未返回路由摘要",
    },
  ]
    .map(
      (item) => `
        <article class="context-card">
          <span>${escapeHtml(item.label)}</span>
          <strong>${escapeHtml(item.value)}</strong>
          <p>${escapeHtml(item.note)}</p>
        </article>
      `,
    )
    .join("");
}

function renderSummaryGrid(snapshot) {
  const salesHome = getSectionData(snapshot, "salesCockpit");
  const summary = salesHome?.summary;
  const routeProfile = snapshot.meta.routeProfile;
  const cards = [
    {
      label: "钱包余额",
      value: summary ? formatMoney(summary.walletBalance) : "--",
      note: "来自销售驾驶仓 summary.walletBalance",
      className: "highlight",
    },
    {
      label: "待跟进会话",
      value: summary ? formatNumber(summary.pendingFollowUpCount) : "--",
      note: "适合做销售当天优先处理列表",
      className: "highlight",
    },
    {
      label: "风险商机",
      value: summary ? formatNumber(summary.riskOpportunityCount) : "--",
      note: "来自审批与治理信号聚合",
      className: "alert",
    },
    {
      label: "待审批项",
      value: summary ? formatNumber(summary.pendingApprovalCount) : "--",
      note: "可用于驾驶仓顶部风控提示",
      className: "warn",
    },
    {
      label: "知识命中",
      value: summary ? formatNumber(summary.knowledgeHitCount) : "--",
      note: "反映知识库对销售动作的支撑度",
      className: "",
    },
    {
      label: "默认模型",
      value: routeProfile?.resolvedModel || routeProfile?.preferredModel || "--",
      note: routeProfile?.resolvedProviderName || "来自 models.getRouteProfile()",
      className: "",
    },
  ];

  summaryGrid.innerHTML = cards
    .map(
      (card) => `
        <article class="summary-card ${card.className}">
          <span>${escapeHtml(card.label)}</span>
          <strong>${escapeHtml(card.value)}</strong>
          <p>${escapeHtml(card.note)}</p>
        </article>
      `,
    )
    .join("");
}

function sectionStatus(section) {
  if (section.ok) {
    return `<span class="status-pill success">READY</span>`;
  }
  return `<span class="status-pill error">ERROR</span>`;
}

function renderErrorState(section, fallback) {
  if (section.ok) {
    return fallback;
  }
  return `<div class="error-state">${escapeHtml(section.error || "加载失败")}</div>`;
}

function renderFollowUps(snapshot) {
  const section = getSection(snapshot, "salesCockpit");
  if (!section.ok) {
    return renderErrorState(section, "");
  }

  const items = section.data.followUps || [];
  if (items.length === 0) {
    return `<div class="empty-state">当前没有待跟进项，可以把这个区域改成“今日成交预测”或“空闲提醒”。</div>`;
  }

  return `
    <div class="list-grid">
      ${items
        .map(
          (item) => `
            <article class="list-card">
              <div class="board-head">
                <div>
                  <h4>${escapeHtml(item.roomName)}</h4>
                  <p>${escapeHtml(item.suggestedAction)}</p>
                </div>
                <span class="priority-pill ${escapeHtml(item.priority)}">${escapeHtml(item.priority)}</span>
              </div>
              <div class="list-meta summary-row">
                <span class="tag">${formatNumber(item.msgCount)} 条消息</span>
                <span class="tag">${formatNumber(item.memberCount)} 位成员</span>
                <span class="tag">${escapeHtml(formatDateTime(item.lastActive))}</span>
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderOpportunityBoard(snapshot) {
  const salesSection = getSection(snapshot, "salesCockpit");
  const boardSection = getSection(snapshot, "salesOpportunityBoard");

  if (!salesSection.ok && !boardSection.ok) {
    return `<div class="error-state">${escapeHtml(salesSection.error || boardSection.error || "无法加载商机看板")}</div>`;
  }

  const riskItems = salesSection.ok ? salesSection.data.riskOpportunities || [] : [];
  const board = boardSection.ok ? boardSection.data : null;

  const stageCards = board?.stageDistribution?.length
    ? `
        <div class="summary-row">
          ${board.stageDistribution
            .map(
              (item) => `
                <span class="tag">${escapeHtml(item.stage)} ${formatNumber(item.count)}</span>
              `,
            )
            .join("")}
        </div>
      `
    : `<div class="empty-state">当前没有 stageDistribution，可在后端补全销售阶段口径后接入。</div>`;

  const riskCards = riskItems.length
    ? `
        <div class="list-grid">
          ${riskItems
            .map(
              (item) => `
                <article class="risk-card">
                  <div class="board-head">
                    <div>
                      <h4>${escapeHtml(item.title)}</h4>
                      <p>${escapeHtml(item.reason)}</p>
                    </div>
                    <span class="risk-pill ${escapeHtml(item.riskLevel || "medium")}">${escapeHtml(item.riskLevel || "medium")}</span>
                  </div>
                  <div class="risk-meta summary-row">
                    <span class="tag">${escapeHtml(item.status)}</span>
                    <span class="tag">${escapeHtml(item.actionHint)}</span>
                  </div>
                </article>
              `,
            )
            .join("")}
        </div>
      `
    : `<div class="empty-state">当前没有风险商机，可把这里换成“重点客户推进板”。</div>`;

  const actionCards = board?.recommendedActions?.length
    ? `
        <div class="list-grid">
          ${board.recommendedActions
            .map(
              (item) => `
                <article class="note-item">
                  <h4>建议动作</h4>
                  <p>${escapeHtml(item)}</p>
                </article>
              `,
            )
            .join("")}
        </div>
      `
    : `<div class="empty-state">当前没有推荐动作。</div>`;

  return `
    <div class="split-grid">
      <div>
        <span class="mini-label">Stage Distribution</span>
        ${stageCards}
      </div>
      <div>
        <span class="mini-label">Recommended Actions</span>
        ${actionCards}
      </div>
    </div>
    <div class="summary-row">
      <span class="tag">高风险客户 ${formatNumber(board?.highRiskCustomers?.length ?? 0)}</span>
      <span class="tag">热度榜单 ${formatNumber(board?.recentConversationHeat?.length ?? 0)}</span>
    </div>
    ${riskCards}
  `;
}

function renderChannels(snapshot) {
  const section = getSection(snapshot, "channelHome");
  if (!section.ok) {
    return renderErrorState(section, "");
  }

  const overview = section.data.overview;
  return `
    <div class="metric-row">
      <article class="metric-card">
        <span class="kpi-label">supported</span>
        <strong>${formatNumber(overview.supportedCount)}</strong>
      </article>
      <article class="metric-card">
        <span class="kpi-label">configured</span>
        <strong>${formatNumber(overview.configuredCount)}</strong>
      </article>
      <article class="metric-card">
        <span class="kpi-label">active</span>
        <strong>${formatNumber(overview.activeCount)}</strong>
      </article>
      <article class="metric-card">
        <span class="kpi-label">personal plugin</span>
        <strong>${section.data.wechatPersonalPlugin?.setupStatus || "--"}</strong>
      </article>
    </div>
    <div class="list-grid">
      ${overview.items
        .map(
          (item) => `
            <article class="list-card">
              <div class="board-head">
                <div>
                  <h4>${escapeHtml(item.channelName)}</h4>
                  <p>${escapeHtml(item.channelKey)} / ${escapeHtml(item.channelGroup)}</p>
                </div>
                <span class="status-pill ${item.enabled ? "success" : "partial"}">${item.enabled ? "ENABLED" : "DISABLED"}</span>
              </div>
              <div class="tag-row summary-row">
                <span class="tag">${item.configured ? "已配置" : "未配置"}</span>
                <span class="tag">${item.bindingEnabled ? "可绑定" : "未开放绑定"}</span>
                <span class="tag">${escapeHtml(item.riskLevel)}</span>
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderConversations(snapshot) {
  const section = getSection(snapshot, "conversationHome");
  if (!section.ok) {
    return renderErrorState(section, "");
  }

  const stats = section.data.stats;
  const groups = section.data.groups || [];
  const history = section.data.history || [];

  return `
    <div class="mini-kpis">
      <article>
        <span class="mini-label">群聊数</span>
        <strong>${formatNumber(stats.groupCount)}</strong>
      </article>
      <article>
        <span class="mini-label">消息总量</span>
        <strong>${formatNumber(stats.msgCount)}</strong>
      </article>
      <article>
        <span class="mini-label">识别实体</span>
        <strong>${formatNumber(stats.entityCount)}</strong>
      </article>
      <article>
        <span class="mini-label">历史消息</span>
        <strong>${formatNumber(stats.historyCount ?? history.length)}</strong>
      </article>
    </div>
    <div class="two-column-grid">
      <div>
        <span class="mini-label">重点群组</span>
        <div class="list-grid">
          ${
            groups.length
              ? groups
                  .map(
                    (item) => `
                      <article class="list-card">
                        <h4>${escapeHtml(item.roomName)}</h4>
                        <p>${formatNumber(item.msgCount)} 条消息 / ${formatNumber(item.memberCount)} 位成员</p>
                        <div class="summary-row">
                          <span class="tag">${escapeHtml(formatDateTime(item.lastActive))}</span>
                        </div>
                      </article>
                    `,
                  )
                  .join("")
              : `<div class="empty-state">当前没有群聊摘要。</div>`
          }
        </div>
      </div>
      <div>
        <span class="mini-label">近期会话</span>
        <div class="timeline">
          ${
            history.length
              ? history
                  .map(
                    (item) => `
                      <article class="timeline-item">
                        <h4>${escapeHtml(item.direction)}</h4>
                        <p>${escapeHtml(item.content || "无内容")}</p>
                        <small>${escapeHtml(formatDateTime(item.createdTime))}</small>
                      </article>
                    `,
                  )
                  .join("")
              : `<div class="empty-state">当前没有近期历史消息。</div>`
          }
        </div>
      </div>
    </div>
  `;
}

function renderKnowledge(snapshot) {
  const salesKnowledgeSection = getSection(snapshot, "salesKnowledge");
  const knowledgeCenterSection = getSection(snapshot, "knowledgeHome");

  if (!salesKnowledgeSection.ok && !knowledgeCenterSection.ok) {
    return `<div class="error-state">${escapeHtml(salesKnowledgeSection.error || knowledgeCenterSection.error || "知识模块加载失败")}</div>`;
  }

  const assistant = salesKnowledgeSection.ok ? salesKnowledgeSection.data.assistant : null;
  const configSummary = salesKnowledgeSection.ok ? salesKnowledgeSection.data.configSummary : null;
  const stats = knowledgeCenterSection.ok ? knowledgeCenterSection.data.stats || {} : {};
  const assets = knowledgeCenterSection.ok ? knowledgeCenterSection.data.assets || {} : {};
  const assetCount = pickNumber(
    configSummary?.indexedAssetCount,
    stats.assetCount,
    stats.asset_count,
    assets.total,
    assets.assetCount,
  );

  const renderKnowledgeColumn = (title, items) => {
    if (!items?.length) {
      return `
        <article class="knowledge-card">
          <h4>${escapeHtml(title)}</h4>
          <p>当前没有内容。</p>
        </article>
      `;
    }

    return `
      <article class="knowledge-card">
        <h4>${escapeHtml(title)}</h4>
        ${items
          .slice(0, 3)
          .map(
            (item) => `
              <p><strong>${escapeHtml(item.title)}</strong><br />${escapeHtml(item.summary || item.source || "")}</p>
            `,
          )
          .join("")}
      </article>
    `;
  };

  return `
    <div class="board-head">
      <div class="board-title">
        <h3>销售知识助手</h3>
        <p class="board-subtitle">把 FAQ、产品知识、竞品回应和成功案例装成可直接引用的话术上下文。</p>
      </div>
      <div class="tag-row">
        <span class="tag">${assistant?.role || "assistant"}</span>
        <span class="tag">资产 ${assetCount !== null ? formatNumber(assetCount) : "--"}</span>
        <span class="tag">${escapeHtml(configSummary?.watchDir || "未返回 watchDir")}</span>
      </div>
    </div>
    <div class="summary-row">
      <span class="tag">账号 ${escapeHtml(assistant?.username || "--")}</span>
      <span class="tag">${assistant?.enterpriseVerified ? "企业已认证" : "企业未认证"}</span>
      <span class="tag">workspace ${formatNumber(assistant?.workspaceCount ?? 0)}</span>
    </div>
    <div class="three-column-grid">
      ${renderKnowledgeColumn("标准话术", salesKnowledgeSection.ok ? salesKnowledgeSection.data.talkTracks : [])}
      ${renderKnowledgeColumn("产品知识", salesKnowledgeSection.ok ? salesKnowledgeSection.data.productKnowledge : [])}
      ${renderKnowledgeColumn("竞品回应", salesKnowledgeSection.ok ? salesKnowledgeSection.data.competitorResponses : [])}
    </div>
    <div class="two-column-grid">
      ${renderKnowledgeColumn("成功案例", salesKnowledgeSection.ok ? salesKnowledgeSection.data.successCases : [])}
      <article class="knowledge-card">
        <h4>知识中心原始统计</h4>
        <p>${escapeHtml(pretty(stats))}</p>
      </article>
    </div>
  `;
}

function renderCoaching(snapshot) {
  const section = getSection(snapshot, "salesCoaching");
  if (!section.ok) {
    return renderErrorState(section, "");
  }

  const data = section.data;
  return `
    <div class="two-column-grid">
      <div>
        <span class="mini-label">训练任务</span>
        <div class="list-grid">
          ${
            data.trainingTasks.length
              ? data.trainingTasks
                  .map(
                    (item) => `
                      <article class="task-card">
                        <div class="board-head">
                          <div>
                            <h4>${escapeHtml(item.title)}</h4>
                            <p>${escapeHtml(item.hint)}</p>
                          </div>
                          <span class="task-pill ${escapeHtml(item.status)}">${escapeHtml(item.status)}</span>
                        </div>
                        <div class="summary-row">
                          <span class="tag">${escapeHtml(item.type)}</span>
                        </div>
                      </article>
                    `,
                  )
                  .join("")
              : `<div class="empty-state">当前没有训练任务。</div>`
          }
        </div>
      </div>
      <div>
        <span class="mini-label">常见问题与最佳实践</span>
        <div class="list-grid">
          ${
            data.commonMistakes.length
              ? data.commonMistakes
                  .map(
                    (item) => `
                      <article class="task-card">
                        <h4>${escapeHtml(item.title)}</h4>
                        <p>${escapeHtml(item.suggestion)}</p>
                        <div class="summary-row">
                          <span class="risk-pill ${escapeHtml(item.level)}">${escapeHtml(item.level)}</span>
                        </div>
                      </article>
                    `,
                  )
                  .join("")
              : `<div class="empty-state">当前没有常见问题。</div>`
          }
          ${
            data.bestPractices.length
              ? data.bestPractices
                  .map(
                    (item) => `
                      <article class="note-item">
                        <h4>${escapeHtml(item.title)}</h4>
                        <p>${escapeHtml(item.reason)}</p>
                      </article>
                    `,
                  )
                  .join("")
              : ""
          }
        </div>
      </div>
    </div>
    <div class="summary-row">
      ${data.assistantTemplates
        .map(
          (item) => `
            <span class="tag">${escapeHtml(item.code)} / ${escapeHtml(item.name)}</span>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderGovernance(snapshot) {
  const section = getSection(snapshot, "governanceHome");
  if (!section.ok) {
    return renderErrorState(section, "");
  }

  const data = section.data;
  return `
    <div class="metric-row">
      <article class="metric-card">
        <span class="kpi-label">审计总数</span>
        <strong>${formatNumber(data.summary.total)}</strong>
      </article>
      <article class="metric-card">
        <span class="kpi-label">待审批</span>
        <strong>${formatNumber(data.summary.pendingApprovalCount)}</strong>
      </article>
      <article class="metric-card">
        <span class="kpi-label">已通过</span>
        <strong>${formatNumber(data.summary.approvedApprovalCount)}</strong>
      </article>
      <article class="metric-card">
        <span class="kpi-label">已拒绝</span>
        <strong>${formatNumber(data.summary.rejectedApprovalCount)}</strong>
      </article>
    </div>
    <div class="two-column-grid">
      <div>
        <span class="mini-label">待审批事项</span>
        <div class="list-grid">
          ${
            data.pendingApprovals.length
              ? data.pendingApprovals
                  .map(
                    (item) => `
                      <article class="list-card">
                        <div class="board-head">
                          <div>
                            <h4>${escapeHtml(item.title)}</h4>
                            <p>${escapeHtml(item.reason)}</p>
                          </div>
                          <span class="risk-pill ${escapeHtml(item.riskLevel)}">${escapeHtml(item.riskLevel)}</span>
                        </div>
                        <div class="summary-row">
                          <span class="tag">${escapeHtml(item.approvalType)}</span>
                          <span class="tag">${escapeHtml(formatDateTime(item.expiresAt))} 截止</span>
                        </div>
                      </article>
                    `,
                  )
                  .join("")
              : `<div class="empty-state">当前没有待审批项。</div>`
          }
        </div>
      </div>
      <div>
        <span class="mini-label">近期事件</span>
        <div class="timeline">
          ${
            data.recentEvents.length
              ? data.recentEvents
                  .map(
                    (item) => `
                      <article class="timeline-item">
                        <h4>${escapeHtml(item.title)}</h4>
                        <p>${escapeHtml(item.summary || item.eventType)}</p>
                        <small>${escapeHtml(formatDateTime(item.createdAt))}</small>
                      </article>
                    `,
                  )
                  .join("")
              : `<div class="empty-state">当前没有近期事件。</div>`
          }
        </div>
      </div>
    </div>
  `;
}

function renderRawPanel(snapshot) {
  const exportPayload = {
    loadedAt: snapshot.loadedAt,
    context: snapshot.context,
    meta: snapshot.meta,
    sections: snapshot.sections,
  };

  return `
    <article class="board-panel span-12 raw-panel">
      <div class="board-head">
        <div class="board-title">
          <h3>开发快照</h3>
          <p class="board-subtitle">给客户前端研发查看真实返回字段，方便继续拆成组件、hooks 或 store。</p>
        </div>
        <span class="status-pill ${snapshot.errorCount > 0 ? "partial" : "success"}">${snapshot.errorCount > 0 ? "PARTIAL" : "READY"}</span>
      </div>
      <pre>${escapeHtml(pretty(exportPayload))}</pre>
    </article>
  `;
}

function renderBoard(snapshot) {
  const channelSection = getSection(snapshot, "channelHome");
  const conversationSection = getSection(snapshot, "conversationHome");
  const salesSection = getSection(snapshot, "salesCockpit");
  const coachingSection = getSection(snapshot, "salesCoaching");
  const governanceSection = getSection(snapshot, "governanceHome");

  boardGrid.innerHTML = `
    <article class="board-panel span-5">
      <div class="board-head">
        <div class="board-title">
          <h3>今日待跟进</h3>
          <p class="board-subtitle">第一屏先放销售最关心的跟进清单。</p>
        </div>
        ${sectionStatus(salesSection)}
      </div>
      ${renderFollowUps(snapshot)}
    </article>

    <article class="board-panel span-7">
      <div class="board-head">
        <div class="board-title">
          <h3>商机与风险看板</h3>
          <p class="board-subtitle">聚合 stage 分布、风险商机和下一步建议动作。</p>
        </div>
        ${sectionStatus(getSection(snapshot, "salesOpportunityBoard"))}
      </div>
      ${renderOpportunityBoard(snapshot)}
    </article>

    <article class="board-panel span-4">
      <div class="board-head">
        <div class="board-title">
          <h3>渠道运行态</h3>
          <p class="board-subtitle">适合做销售外呼 / IM 接入状态概览。</p>
        </div>
        ${sectionStatus(channelSection)}
      </div>
      ${renderChannels(snapshot)}
    </article>

    <article class="board-panel span-8">
      <div class="board-head">
        <div class="board-title">
          <h3>会话脉冲</h3>
          <p class="board-subtitle">查看群组热度、近期消息和会话方向。</p>
        </div>
        ${sectionStatus(conversationSection)}
      </div>
      ${renderConversations(snapshot)}
    </article>

    <article class="board-panel span-7">
      ${renderKnowledge(snapshot)}
    </article>

    <article class="board-panel span-5">
      <div class="board-head">
        <div class="board-title">
          <h3>培训与复盘</h3>
          <p class="board-subtitle">适合做销售经理工作台的辅导区块。</p>
        </div>
        ${sectionStatus(coachingSection)}
      </div>
      ${renderCoaching(snapshot)}
    </article>

    <article class="board-panel span-12">
      <div class="board-head">
        <div class="board-title">
          <h3>治理与审批</h3>
          <p class="board-subtitle">把合规与审批信号拉回业务首页，而不是只留在后台菜单。</p>
        </div>
        ${sectionStatus(governanceSection)}
      </div>
      ${renderGovernance(snapshot)}
    </article>

    ${renderRawPanel(snapshot)}
  `;
}

function setLoadingState(isLoading) {
  loadButton.disabled = isLoading;
  prefillButton.disabled = isLoading;
}

function buildRuntimeScope(context) {
  return {
    teamId: context.teamId,
    runtimeType: context.runtimeType,
    ...(context.agentId ? { agentId: context.agentId } : {}),
  };
}

async function loadDashboard() {
  const config = readConfig();
  if (!config.baseUrl || !config.token) {
    setBanner("error", "请先填写 Base URL 和 Token。");
    return;
  }

  saveConfig();
  setLoadingState(true);
  exportButton.disabled = true;
  setBanner("running", "正在装配销售驾驶仓首页，请稍候...");

  const core = createQeeClawClient({
    baseUrl: config.baseUrl,
    token: config.token,
    userAgent: "sales-cockpit-starter-web",
  });
  const product = createQeeClawProductSDK(core);

  const tenantResult = await runTask(() => core.tenant.getCurrentContext());
  const profileResult = await runTask(() => core.iam.getProfile());
  const routeProfileResult = await runTask(() => core.models.getRouteProfile());
  const runtimesResult = await runTask(() => core.models.listRuntimes());

  const context = {
    baseUrl: config.baseUrl,
    scope: config.scope,
    runtimeType: config.runtimeType,
    agentId: config.agentId,
    teamId: config.teamId ? Number(config.teamId) : null,
    username: profileResult.ok ? profileResult.data.username : tenantResult.ok ? tenantResult.data.username : "",
    role: profileResult.ok ? profileResult.data.role : tenantResult.ok ? tenantResult.data.role : "",
    teamCount: tenantResult.ok ? tenantResult.data.teams?.length ?? 0 : profileResult.ok ? profileResult.data.teams?.length ?? 0 : 0,
    enterpriseVerified: profileResult.ok
      ? Boolean(profileResult.data.isEnterpriseVerified)
      : tenantResult.ok
        ? Boolean(tenantResult.data.isEnterpriseVerified)
        : false,
  };

  if (!context.teamId && tenantResult.ok && tenantResult.data.teams?.length) {
    context.teamId = Number(tenantResult.data.teams[0].id);
    teamIdInput.value = String(context.teamId);
    saveConfig();
  }

  if (!context.teamId) {
    renderContextStrip({
      context,
      meta: {
        routeProfile: routeProfileResult.ok ? routeProfileResult.data : null,
        runtimes: runtimesResult.ok ? runtimesResult.data : [],
      },
      sections: {},
    });
    setBanner("error", "未能识别 teamId。请手动填写 Team ID，或确认 tenant.getCurrentContext() 可返回团队列表。");
    setLoadingState(false);
    return;
  }

  const runtimeScope = buildRuntimeScope(context);
  const sectionTasks = {
    channelHome: () => product.channelCenter.loadHome(context.teamId),
    conversationHome: () => product.conversationCenter.loadHome(context.teamId, { groupLimit: 5, historyLimit: 6 }),
    governanceHome: () => product.governanceCenter.loadHome(config.scope),
    knowledgeHome: () => product.knowledgeCenter.loadHome(runtimeScope),
    salesCockpit: () => product.salesCockpit.loadHome(context.teamId, config.scope),
    salesOpportunityBoard: () => product.salesCockpit.loadOpportunityBoard(context.teamId, config.scope),
    salesKnowledge: () => product.salesKnowledge.loadAssistantContext(runtimeScope),
    salesCoaching: () => product.salesCoaching.loadTrainingOverview(context.teamId, config.scope),
  };

  const sectionEntries = await Promise.all(
    Object.entries(sectionTasks).map(async ([key, loader]) => [key, await runTask(loader)]),
  );

  const sections = Object.fromEntries(sectionEntries);
  const errorCount =
    Object.values(sections).filter((item) => !item.ok).length +
    (tenantResult.ok ? 0 : 1) +
    (profileResult.ok ? 0 : 1);

  latestSnapshot = {
    loadedAt: new Date().toISOString(),
    errorCount,
    context,
    meta: {
      tenant: tenantResult.ok ? tenantResult.data : null,
      profile: profileResult.ok ? profileResult.data : null,
      routeProfile: routeProfileResult.ok ? routeProfileResult.data : null,
      runtimes: runtimesResult.ok ? runtimesResult.data : [],
      metaErrors: {
        tenant: tenantResult.ok ? null : tenantResult.error,
        profile: profileResult.ok ? null : profileResult.error,
        routeProfile: routeProfileResult.ok ? null : routeProfileResult.error,
        runtimes: runtimesResult.ok ? null : runtimesResult.error,
      },
    },
    sections,
  };

  renderContextStrip(latestSnapshot);
  renderSummaryGrid(latestSnapshot);
  renderBoard(latestSnapshot);

  setBanner(
    errorCount > 0 ? "error" : "success",
    errorCount > 0
      ? "驾驶仓首页已生成，但有部分模块未通过。可先看页面效果，再根据开发快照排查字段、权限或 CORS。"
      : "驾驶仓首页已生成，Core SDK 与 Product SDK 关键业务链路均已可视化。",
  );

  exportButton.disabled = false;
  setLoadingState(false);
}

function exportSnapshot() {
  if (!latestSnapshot) {
    return;
  }

  const blob = new Blob([pretty(latestSnapshot)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `qeeclaw-sales-cockpit-snapshot-${Date.now()}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
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
  setBanner("idle", "已填入线上环境示例，请补充 Token 和 Team ID。");
}

loadSavedConfig();

form.addEventListener("input", () => {
  saveConfig();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void loadDashboard();
});

prefillButton.addEventListener("click", prefillOnline);
loadButton.addEventListener("click", () => {
  void loadDashboard();
});
exportButton.addEventListener("click", exportSnapshot);

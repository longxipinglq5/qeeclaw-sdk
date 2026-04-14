import type {
  ProductApprovalRecord,
  ProductConversationGroup,
  ProductConversationHistoryMessage,
  ProductSdkClient,
} from "../types.js";

export interface SalesCockpitSummary {
  pendingFollowUpCount: number;
  riskOpportunityCount: number;
  pendingApprovalCount: number;
  walletBalance: number;
  currentMonthSpend: number;
  workflowCount: number;
  knowledgeHitCount: number;
  enterpriseVerified: boolean;
}

export interface SalesFollowUpItem {
  roomId: string;
  roomName: string;
  lastActive?: string | null;
  msgCount: number;
  memberCount: number;
  priority: "high" | "medium" | "low";
  suggestedAction: string;
}

export interface SalesRiskOpportunity {
  approvalId: string;
  title: string;
  reason: string;
  riskLevel: ProductApprovalRecord["riskLevel"];
  status: ProductApprovalRecord["status"];
  actionHint: string;
}

export interface SalesConversationHighlight {
  id: number;
  direction: string;
  contentPreview: string;
  createdTime?: string | null;
}

export interface SalesKnowledgeRecommendation {
  title: string;
  source: string;
  type: "knowledge" | "document";
}

export interface SalesGovernanceSnapshot {
  auditTotal: number;
  totalSpent: number;
  totalRecharge: number;
  approvalCount: number;
  enterpriseVerified: boolean;
}

export interface SalesCockpitHome {
  summary: SalesCockpitSummary;
  followUps: SalesFollowUpItem[];
  riskOpportunities: SalesRiskOpportunity[];
  conversationHighlights: SalesConversationHighlight[];
  recommendedKnowledge: SalesKnowledgeRecommendation[];
  governanceSnapshot: SalesGovernanceSnapshot;
}

export interface SalesOpportunityBoard {
  stageDistribution: Array<{
    stage: string;
    count: number;
  }>;
  highRiskCustomers: Array<{
    roomId: string;
    roomName: string;
    riskLevel: "high" | "medium" | "low" | "critical";
    reason: string;
  }>;
  recentConversationHeat: Array<{
    roomId: string;
    roomName: string;
    heatScore: number;
  }>;
  recommendedActions: string[];
}

function normalizeRiskLevel(
  value: ProductApprovalRecord["riskLevel"] | SalesFollowUpItem["priority"],
): "high" | "medium" | "low" | "critical" {
  return value;
}

function truncate(value: string | null | undefined, length = 72): string {
  if (!value) {
    return "";
  }
  return value.length > length ? `${value.slice(0, length)}...` : value;
}

function normalizeKnowledgeResults(value: unknown): SalesKnowledgeRecommendation[] {
  const items = Array.isArray(value)
    ? value
    : value && typeof value === "object" && "list" in value && Array.isArray((value as { list?: unknown }).list)
      ? ((value as { list: unknown[] }).list)
      : value && typeof value === "object" && "items" in value && Array.isArray((value as { items?: unknown }).items)
        ? ((value as { items: unknown[] }).items)
        : [];

  return items
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const record = item as Record<string, unknown>;
      const title =
        (typeof record.filename === "string" && record.filename) ||
        (typeof record.source_name === "string" && record.source_name) ||
        (typeof record.sourceName === "string" && record.sourceName) ||
        (typeof record.name === "string" && record.name) ||
        "";
      if (!title) {
        return null;
      }
      return {
        title,
        source: typeof record.status === "string" ? record.status : "indexed",
        type: "knowledge" as const,
      };
    })
    .filter((item): item is Exclude<typeof item, null> => Boolean(item));
}

function buildPriority(group: ProductConversationGroup): SalesFollowUpItem["priority"] {
  if (group.msgCount >= 10 || group.memberCount >= 8) {
    return "high";
  }
  if (group.msgCount >= 5) {
    return "medium";
  }
  return "low";
}

function buildSuggestedAction(group: ProductConversationGroup): string {
  if (group.msgCount >= 10) {
    return "优先安排今天跟进，输出下一步推进结论";
  }
  if (group.memberCount >= 8) {
    return "同步关键干系人，确认商机推进节奏";
  }
  return "整理本轮沟通要点，准备下一次触达";
}

function buildRiskOpportunities(items: ProductApprovalRecord[]): SalesRiskOpportunity[] {
  const sorted = [...items].sort((left, right) => {
    const rank = { critical: 4, high: 3, medium: 2, low: 1 };
    return rank[right.riskLevel] - rank[left.riskLevel];
  });

  return sorted
    .filter((item) => item.riskLevel === "high" || item.riskLevel === "critical")
    .slice(0, 6)
    .map((item) => ({
    approvalId: item.approvalId,
    title: item.title,
    reason: item.reason,
    riskLevel: item.riskLevel,
    status: item.status,
    actionHint:
      item.riskLevel === "critical" || item.riskLevel === "high"
        ? "需要销售负责人尽快确认处理策略"
        : "建议在本周销售例会上完成处理",
    }));
}

function buildConversationHighlights(items: ProductConversationHistoryMessage[]): SalesConversationHighlight[] {
  return items.slice(0, 6).map((item) => ({
    id: item.id,
    direction: item.direction,
    contentPreview: truncate(item.content, 96),
    createdTime: item.createdTime,
  }));
}

export class SalesCockpitKit {
  constructor(private readonly client: ProductSdkClient) {}

  async loadHome(teamId: number, scope: "mine" | "all" = "mine"): Promise<SalesCockpitHome> {
    const [
      wallet,
      billingSummary,
      tenantContext,
      conversationHome,
      approvals,
      auditSummary,
      salesKnowledge,
      productKnowledge,
      documents,
      workflows,
    ] = await Promise.all([
      this.client.billing.getWallet(),
      this.client.billing.getSummary(),
      this.client.tenant.getCurrentContext(),
      this.client.conversations.getHome(teamId, 6, 6),
      this.client.approval.list({ scope, status: "pending", page: 1, pageSize: 20 }),
      this.client.audit.getSummary({ scope }),
      this.client.knowledge.search({ teamId, query: "sales", limit: 5 }),
      this.client.knowledge.search({ teamId, query: "pricing", limit: 5 }),
      this.client.file.listDocuments({ limit: 6 }),
      this.client.workflow.list(),
    ]);

    const recommendedKnowledge = [
      ...normalizeKnowledgeResults(salesKnowledge),
      ...normalizeKnowledgeResults(productKnowledge),
      ...documents.slice(0, 3).map((item) => ({
        title: item.documentTitle,
        source: item.labels ?? "document",
        type: "document" as const,
      })),
    ].slice(0, 8);
    const riskOpportunities = buildRiskOpportunities(approvals.items);

    return {
      summary: {
        pendingFollowUpCount: conversationHome.groups.length,
        riskOpportunityCount: riskOpportunities.length,
        pendingApprovalCount: approvals.total,
        walletBalance: wallet.balance,
        currentMonthSpend: wallet.currentMonthSpent,
        workflowCount: workflows.length,
        knowledgeHitCount: recommendedKnowledge.length,
        enterpriseVerified: tenantContext.isEnterpriseVerified,
      },
      followUps: conversationHome.groups.slice(0, 6).map((group) => ({
        roomId: group.roomId,
        roomName: group.roomName,
        lastActive: group.lastActive,
        msgCount: group.msgCount,
        memberCount: group.memberCount,
        priority: buildPriority(group),
        suggestedAction: buildSuggestedAction(group),
      })),
      riskOpportunities,
      conversationHighlights: buildConversationHighlights(conversationHome.history),
      recommendedKnowledge,
      governanceSnapshot: {
        auditTotal: auditSummary.total,
        totalSpent: billingSummary.totalSpent,
        totalRecharge: billingSummary.totalRecharge,
        approvalCount: approvals.total,
        enterpriseVerified: tenantContext.isEnterpriseVerified,
      },
    };
  }

  async loadOpportunityBoard(teamId: number, scope: "mine" | "all" = "mine"): Promise<SalesOpportunityBoard> {
    const [conversationHome, approvals] = await Promise.all([
      this.client.conversations.getHome(teamId, 10, 5),
      this.client.approval.list({ scope, status: "pending", page: 1, pageSize: 20 }),
    ]);

    const stages = ["线索", "初筛", "方案", "商务", "成交"];
    const stageDistribution = stages.map((stage, index) => ({
      stage,
      count: conversationHome.groups.filter((_, groupIndex) => groupIndex % stages.length === index).length,
    }));

    const riskApprovals = buildRiskOpportunities(approvals.items);
    const highRiskCustomers = conversationHome.groups.slice(0, 5).map((group, index) => ({
      roomId: group.roomId,
      roomName: group.roomName,
      riskLevel: normalizeRiskLevel(index < riskApprovals.length ? riskApprovals[index].riskLevel : buildPriority(group)),
      reason:
        riskApprovals[index]?.reason ||
        (group.msgCount >= 10 ? "近期沟通频繁，建议重点跟进" : "需要确认下一阶段推进动作"),
    }));
    const hasHighRiskCustomers = highRiskCustomers.some(
      (item) => item.riskLevel === "high" || item.riskLevel === "critical",
    );

    const recentConversationHeat = [...conversationHome.groups]
      .sort((left, right) => right.msgCount * right.memberCount - left.msgCount * left.memberCount)
      .slice(0, 5)
      .map((group) => ({
        roomId: group.roomId,
        roomName: group.roomName,
        heatScore: group.msgCount * group.memberCount,
      }));

    const recommendedActions = [
      hasHighRiskCustomers ? "优先处理高风险商机，安排负责人复盘" : "本周暂无高风险商机，继续保持节奏",
      conversationHome.groups.length > 0 ? "基于会话热度榜更新今日销售跟进列表" : "当前暂无活跃会话，补齐客户触达计划",
      approvals.total > 0 ? "清理待审批事项，避免商机推进受阻" : "审批链路顺畅，可继续推进商机转化",
    ];

    return {
      stageDistribution,
      highRiskCustomers,
      recentConversationHeat,
      recommendedActions,
    };
  }
}

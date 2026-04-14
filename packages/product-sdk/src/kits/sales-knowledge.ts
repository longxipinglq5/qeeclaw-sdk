import type {
  ProductPlatformDocument,
  ProductRuntimeKnowledgeScope,
  ProductSdkClient,
  ProductUserProduct,
} from "../types.js";

export interface SalesKnowledgeCard {
  title: string;
  summary: string;
  source: string;
}

export interface SalesKnowledgeAssistantContext {
  assistant: {
    username: string;
    role: string;
    enterpriseVerified: boolean;
    workspaceCount: number;
  };
  talkTracks: SalesKnowledgeCard[];
  productKnowledge: SalesKnowledgeCard[];
  competitorResponses: SalesKnowledgeCard[];
  successCases: SalesKnowledgeCard[];
  configSummary: {
    watchDir?: string;
    indexedAssetCount?: number;
  };
}

function truncate(value: string | null | undefined, length = 96): string {
  if (!value) {
    return "";
  }
  return value.length > length ? `${value.slice(0, length)}...` : value;
}

function normalizeKnowledgeCards(value: unknown, sourceLabel: string): SalesKnowledgeCard[] {
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
        "未命名知识";
      return {
        title,
        summary: typeof record.status === "string" ? `当前状态：${record.status}` : "已收录到知识检索上下文",
        source: sourceLabel,
      };
    })
    .filter((item): item is SalesKnowledgeCard => Boolean(item));
}

function mapDocumentCard(item: ProductPlatformDocument, source: string): SalesKnowledgeCard {
  return {
    title: item.documentTitle,
    summary: truncate(item.documentDetail, 120) || "用于销售场景的参考文档",
    source,
  };
}

export class SalesKnowledgeKit {
  constructor(private readonly client: ProductSdkClient) {}

  async loadAssistantContext(payload: ProductRuntimeKnowledgeScope): Promise<SalesKnowledgeAssistantContext> {
    const [profile, tenantContext, config, stats, salesAssets, pricingAssets, competitorAssets, products, documents] =
      await Promise.all([
        this.client.iam.getProfile(),
        this.client.tenant.getCurrentContext(),
        this.client.knowledge.getConfig(payload),
        this.client.knowledge.stats(payload),
        this.client.knowledge.search({ ...payload, query: "sales", limit: 5 }),
        this.client.knowledge.search({ ...payload, query: "pricing", limit: 5 }),
        this.client.knowledge.search({ ...payload, query: "competitor", limit: 5 }),
        this.client.iam.listProducts(),
        this.client.file.listDocuments({ limit: 10 }),
      ]);

    const productDocs = await Promise.all(
      products
        .slice(0, 4)
        .filter((item: ProductUserProduct) => typeof item.docId === "number")
        .map((item: ProductUserProduct) => this.client.file.getDocument(item.docId as number)),
    );

    const productKnowledge = [
      ...normalizeKnowledgeCards(pricingAssets, "knowledge"),
      ...productDocs.map((item) => mapDocumentCard(item, "product-doc")),
    ].slice(0, 6);

    const competitorResponses = [
      ...normalizeKnowledgeCards(competitorAssets, "knowledge"),
      ...documents
        .filter((item) => (item.labels || "").includes("sales"))
        .slice(0, 2)
        .map((item) => ({
          title: `${item.documentTitle} 应答模板`,
          summary: "建议按“客户问题 -> 平台优势 -> 场景落地”结构回答。",
          source: "document-template",
        })),
    ].slice(0, 4);

    const successCases = documents
      .slice(0, 3)
      .map((item) => ({
        title: item.documentTitle,
        summary: truncate(item.documentDetail, 100) || "可作为销售复盘与分享案例",
        source: "document",
      }));

    return {
      assistant: {
        username: profile.username,
        role: profile.role,
        enterpriseVerified: tenantContext.isEnterpriseVerified,
        workspaceCount: tenantContext.teams.length,
      },
      talkTracks: [
        ...normalizeKnowledgeCards(salesAssets, "knowledge"),
        ...documents.slice(0, 2).map((item) => mapDocumentCard(item, "document")),
      ].slice(0, 6),
      productKnowledge,
      competitorResponses:
        competitorResponses.length > 0
          ? competitorResponses
          : [
              {
                title: "竞品应答占位模板",
                summary: "当前未检索到竞品知识，建议先沉淀竞品对比卡片。",
                source: "fallback",
              },
            ],
      successCases,
      configSummary: {
        watchDir: typeof (config as { watchDir?: unknown }).watchDir === "string" ? (config as { watchDir: string }).watchDir : undefined,
        indexedAssetCount:
          typeof (stats as { indexedCount?: unknown }).indexedCount === "number"
            ? ((stats as { indexedCount: number }).indexedCount)
            : typeof (stats as { totalChunks?: unknown }).totalChunks === "number"
              ? ((stats as { totalChunks: number }).totalChunks)
              : typeof (stats as { assetCount?: unknown }).assetCount === "number"
                ? ((stats as { assetCount: number }).assetCount)
                : undefined,
      },
    };
  }
}

import type { ProductRuntimeKnowledgeScope, ProductSdkClient } from "../types.js";

export interface KnowledgeCenterHome {
  stats: Record<string, unknown>;
  config: Record<string, unknown>;
  assets: Record<string, unknown>;
}

export class KnowledgeCenterKit {
  constructor(private readonly client: ProductSdkClient) {}

  async loadHome(payload: ProductRuntimeKnowledgeScope): Promise<KnowledgeCenterHome> {
    const [stats, config, assets] = await Promise.all([
      this.client.knowledge.stats(payload),
      this.client.knowledge.getConfig(payload),
      this.client.knowledge.list({ ...payload, page: 1, pageSize: 20 }),
    ]);
    return { stats, config, assets };
  }

  search(payload: ProductRuntimeKnowledgeScope & { query?: string; filename?: string; limit?: number }) {
    return this.client.knowledge.search(payload);
  }

  ingest(payload: ProductRuntimeKnowledgeScope & {
    file?: Blob | Uint8Array | ArrayBuffer;
    filename?: string;
    contentType?: string;
    content?: string;
    sourceName?: string;
  }) {
    return this.client.knowledge.ingest(payload);
  }

  updateWatchDir(payload: ProductRuntimeKnowledgeScope & { watchDir: string }) {
    return this.client.knowledge.updateConfig(payload);
  }
}

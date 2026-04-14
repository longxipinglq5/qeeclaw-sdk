/**
 * vector-adapter.ts 
 * 
 * 轻量化本地向量库适配器与去重引擎组件。
 * 从前期的 OpenClawKit 中剥离而出，只保留核心接口和基于余弦相似度的简单近邻算法。
 * 此模块不再强制依赖本地的 vector_types.h (C++库) 或者臃肿的 Chroma 驱动，
 * 适用于桌面端轻度记忆 RAG 抽取和历史对照。
 */

export interface VectorEmbedding {
  id: string;
  vector: number[];
  payload?: Record<string, any>;
}

export interface IVectorStore {
  add(embeddings: VectorEmbedding[]): Promise<void>;
  search(queryVector: number[], topK?: number): Promise<VectorEmbedding[]>;
  deduplicate(embeddings: VectorEmbedding[], threshold?: number): Promise<VectorEmbedding[]>;
}

/** 余弦相似度 */
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) throw new Error("Vector dimensions mismatch");
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

/** 内存极简版向量存储 (Local Array) */
export class MemoryVectorStore implements IVectorStore {
  private store: VectorEmbedding[] = [];

  async add(embeddings: VectorEmbedding[]): Promise<void> {
    // 追加保存
    this.store.push(...embeddings);
  }

  async search(queryVector: number[], topK: number = 3): Promise<VectorEmbedding[]> {
    if (this.store.length === 0) return [];
    
    // 挨个算向量相似度
    const scored = this.store.map(item => ({
      item,
      score: cosineSimilarity(queryVector, item.vector)
    }));
    
    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, Math.min(topK, scored.length)).map(s => s.item);
  }

  async deduplicate(embeddings: VectorEmbedding[], threshold: number = 0.95): Promise<VectorEmbedding[]> {
    // 根据现有的库区查找并过滤掉超过相似度 threshold 的记录
    const result: VectorEmbedding[] = [];
    for (const em of embeddings) {
      if (this.store.length === 0) {
        result.push(em);
        this.add([em]);
        continue;
      }
      const nearest = await this.search(em.vector, 1);
      const isDuplicate = nearest.length > 0 && cosineSimilarity(nearest[0].vector, em.vector) >= threshold;
      if (!isDuplicate) {
        result.push(em);
        this.add([em]);
      }
    }
    return result;
  }
}

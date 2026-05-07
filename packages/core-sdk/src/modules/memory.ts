import type { HttpClient } from "../client/http-client.js";

export interface MemoryTargetScope {
  teamId?: number;
  runtimeType?: string | null;
  deviceId?: string | number | null;
  agentId?: string | null;
}

export interface MemoryStoreRequest extends MemoryTargetScope {
  content: string;
  category?: "preference" | "fact" | "decision" | "entity" | "other";
  importance?: number;
  sourceSession?: string | null;
  skipDuplicateCheck?: boolean;
}

export interface MemorySearchRequest extends MemoryTargetScope {
  query: string;
  limit?: number;
  threshold?: number;
}

export interface MemoryDeleteResult {
  deleted: boolean;
}

export interface MemoryClearResult {
  clearedCount: number;
}

export interface MemoryStats {
  [key: string]: unknown;
}

export interface MemoryStatsRequest extends MemoryTargetScope {}

export class MemoryModule {
  constructor(private readonly http: HttpClient) {}

  async store(payload: MemoryStoreRequest): Promise<Record<string, unknown>> {
    const result = await this.http.request<Record<string, unknown>>({
      method: "POST",
      path: "/memory/store",
      body: {
        content: payload.content,
        category: payload.category,
        importance: payload.importance,
        team_id: payload.teamId,
        runtime_type: payload.runtimeType,
        device_id: payload.deviceId,
        agent_id: payload.agentId,
        source_session: payload.sourceSession,
        skip_duplicate_check: payload.skipDuplicateCheck,
      },
    });

    return result.entry && typeof result.entry === "object"
      ? result.entry as Record<string, unknown>
      : result;
  }

  async search(payload: MemorySearchRequest): Promise<Record<string, unknown>[]> {
    const result = await this.http.request<Record<string, unknown>[] | { results?: unknown }>({
      method: "POST",
      path: "/memory/search",
      body: {
        query: payload.query,
        limit: payload.limit,
        threshold: payload.threshold,
        team_id: payload.teamId,
        runtime_type: payload.runtimeType,
        device_id: payload.deviceId,
        agent_id: payload.agentId,
      },
    });

    if (Array.isArray(result)) {
      return result;
    }

    return Array.isArray(result.results)
      ? result.results.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
      : [];
  }

  async delete(
    entryId: string,
    scope?: Pick<MemoryTargetScope, "teamId" | "agentId" | "runtimeType">,
  ): Promise<MemoryDeleteResult> {
    const result = await this.http.request<{ deleted?: boolean }>({
      method: "DELETE",
      path: `/memory/${encodeURIComponent(entryId)}`,
      query: {
        team_id: scope?.teamId,
        agent_id: scope?.agentId,
        runtime_type: scope?.runtimeType,
      },
    });

    return { deleted: Boolean(result.deleted) };
  }

  async clear(
    agentId: string,
    scope?: Pick<MemoryTargetScope, "teamId" | "runtimeType">,
  ): Promise<MemoryClearResult> {
    const result = await this.http.request<{ cleared_count?: number }>({
      method: "POST",
      path: "/memory/clear",
      body: {
        agent_id: agentId,
        team_id: scope?.teamId,
        runtime_type: scope?.runtimeType,
      },
    });

    return { clearedCount: result.cleared_count ?? 0 };
  }

  async stats(payload: MemoryStatsRequest = {}): Promise<MemoryStats> {
    return this.http.request<MemoryStats>({
      method: "GET",
      path: "/memory/stats",
      query: {
        team_id: payload.teamId,
        agent_id: payload.agentId,
        runtime_type: payload.runtimeType,
      },
    });
  }
}

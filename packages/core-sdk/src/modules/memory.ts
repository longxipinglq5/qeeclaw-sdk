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
    return this.http.request<Record<string, unknown>>({
      method: "POST",
      path: "/api/platform/memory/store",
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
  }

  async search(payload: MemorySearchRequest): Promise<Record<string, unknown>[]> {
    return this.http.request<Record<string, unknown>[]>({
      method: "POST",
      path: "/api/platform/memory/search",
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
  }

  async delete(
    entryId: string,
    scope?: Pick<MemoryTargetScope, "teamId" | "agentId" | "runtimeType">,
  ): Promise<MemoryDeleteResult> {
    const result = await this.http.request<{ deleted?: boolean }>({
      method: "DELETE",
      path: `/api/platform/memory/${encodeURIComponent(entryId)}`,
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
      method: "DELETE",
      path: `/api/platform/memory/agent/${encodeURIComponent(agentId)}`,
      query: {
        team_id: scope?.teamId,
        runtime_type: scope?.runtimeType,
      },
    });

    return { clearedCount: result.cleared_count ?? 0 };
  }

  async stats(payload: MemoryStatsRequest = {}): Promise<MemoryStats> {
    return this.http.request<MemoryStats>({
      method: "GET",
      path: "/api/platform/memory/stats",
      query: {
        team_id: payload.teamId,
        agent_id: payload.agentId,
        runtime_type: payload.runtimeType,
      },
    });
  }
}

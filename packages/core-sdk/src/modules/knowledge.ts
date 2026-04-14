import { QeeClawNotImplementedError } from "../errors.js";
import type { HttpClient } from "../client/http-client.js";

export interface KnowledgeContext {
  teamId: number;
  deviceId?: number;
  runtimeType?: string | null;
  agentId?: string | null;
}

export interface KnowledgeIngestRequest extends KnowledgeContext {
  file?: Blob | Uint8Array | ArrayBuffer;
  filename?: string;
  contentType?: string;
  content?: string;
  sourceName?: string;
}

export interface KnowledgeListRequest extends KnowledgeContext {
  page?: number;
  pageSize?: number;
}

export interface KnowledgeSearchRequest extends KnowledgeContext {
  query?: string;
  filename?: string;
  limit?: number;
}

export interface KnowledgeDeleteRequest extends KnowledgeContext {
  sourceName: string;
}

export interface KnowledgeDownloadRequest extends KnowledgeContext {
  sourceName: string;
  mode?: "path" | "base64";
}

export interface KnowledgeConfigUpdateRequest extends KnowledgeContext {
  watchDir: string;
}

function buildBlob(
  value: Blob | Uint8Array | ArrayBuffer,
  contentType?: string,
): Blob {
  if (typeof Blob !== "undefined" && value instanceof Blob) {
    return value;
  }
  const blobPart = value as unknown as BlobPart;
  return new Blob([blobPart], {
    type: contentType ?? "application/octet-stream",
  });
}

export class KnowledgeModule {
  constructor(private readonly http: HttpClient) {}

  async ingest(payload: KnowledgeIngestRequest): Promise<Record<string, unknown>> {
    const form = new FormData();
    form.set("team_id", String(payload.teamId));
    if (payload.deviceId !== undefined) {
      form.set("device_id", String(payload.deviceId));
    }
    if (payload.runtimeType) {
      form.set("runtime_type", payload.runtimeType);
    }
    if (payload.agentId) {
      form.set("agent_id", payload.agentId);
    }

    if (payload.file !== undefined) {
      const blob = buildBlob(payload.file, payload.contentType);
      form.set("file", blob, payload.filename ?? "knowledge.bin");
    } else {
      form.set("content", payload.content ?? "");
      if (payload.sourceName) {
        form.set("source_name", payload.sourceName);
      }
    }

    return this.http.request<Record<string, unknown>>({
      method: "POST",
      path: "/api/platform/knowledge/upload",
      body: form,
    });
  }

  async list(payload: KnowledgeListRequest): Promise<Record<string, unknown>> {
    return this.http.request<Record<string, unknown>>({
      method: "GET",
      path: "/api/platform/knowledge/list",
      query: {
        team_id: payload.teamId,
        page: payload.page ?? 1,
        pageSize: payload.pageSize ?? 20,
        device_id: payload.deviceId,
        runtime_type: payload.runtimeType,
        agent_id: payload.agentId,
      },
    });
  }

  async search(payload: KnowledgeSearchRequest): Promise<Record<string, unknown>> {
    return this.http.request<Record<string, unknown>>({
      method: "GET",
      path: "/api/platform/knowledge/search",
      query: {
        team_id: payload.teamId,
        query: payload.query,
        filename: payload.filename,
        limit: payload.limit ?? 5,
        device_id: payload.deviceId,
        runtime_type: payload.runtimeType,
        agent_id: payload.agentId,
      },
    });
  }

  async delete(payload: KnowledgeDeleteRequest): Promise<Record<string, unknown>> {
    return this.http.request<Record<string, unknown>>({
      method: "POST",
      path: "/api/platform/knowledge/delete",
      query: {
        team_id: payload.teamId,
        source_name: payload.sourceName,
        device_id: payload.deviceId,
        runtime_type: payload.runtimeType,
        agent_id: payload.agentId,
      },
    });
  }

  async download(payload: KnowledgeDownloadRequest): Promise<Record<string, unknown>> {
    return this.http.request<Record<string, unknown>>({
      method: "GET",
      path: "/api/platform/knowledge/download",
      query: {
        team_id: payload.teamId,
        source_name: payload.sourceName,
        mode: payload.mode ?? "path",
        device_id: payload.deviceId,
        runtime_type: payload.runtimeType,
        agent_id: payload.agentId,
      },
    });
  }

  async stats(payload: KnowledgeContext): Promise<Record<string, unknown>> {
    return this.http.request<Record<string, unknown>>({
      method: "GET",
      path: "/api/platform/knowledge/stats",
      query: {
        team_id: payload.teamId,
        device_id: payload.deviceId,
        runtime_type: payload.runtimeType,
        agent_id: payload.agentId,
      },
    });
  }

  async getConfig(payload: KnowledgeContext): Promise<Record<string, unknown>> {
    return this.http.request<Record<string, unknown>>({
      method: "GET",
      path: "/api/platform/knowledge/config",
      query: {
        team_id: payload.teamId,
        device_id: payload.deviceId,
        runtime_type: payload.runtimeType,
        agent_id: payload.agentId,
      },
    });
  }

  async updateConfig(payload: KnowledgeConfigUpdateRequest): Promise<Record<string, unknown>> {
    return this.http.request<Record<string, unknown>>({
      method: "POST",
      path: "/api/platform/knowledge/config/update",
      query: {
        team_id: payload.teamId,
        watchDir: payload.watchDir,
        device_id: payload.deviceId,
        runtime_type: payload.runtimeType,
        agent_id: payload.agentId,
      },
    });
  }

  async rebuildIndex(): Promise<never> {
    throw new QeeClawNotImplementedError(
      "knowledge.rebuildIndex() is reserved for the future knowledge worker / control plane API",
    );
  }
}

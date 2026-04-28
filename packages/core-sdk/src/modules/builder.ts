import type { HttpClient } from "../client/http-client.js";

export interface BuilderProjectRecord {
  id: string;
  status: string;
  stage: string;
  industry?: string;
  createdAt?: string;
  updatedAt?: string;
  source?: string;
  employeeId?: string;
  blueprint: Record<string, unknown>;
  viewConfig?: Record<string, unknown>;
  versions?: unknown[];
  testRuns?: unknown[];
  [key: string]: unknown;
}

export interface BuilderProjectListResult {
  projects: BuilderProjectRecord[];
}

export class BuilderModule {
  constructor(private readonly http: HttpClient) {}

  async list(): Promise<BuilderProjectRecord[]> {
    const result = await this.http.request<BuilderProjectListResult>({
      method: "GET",
      path: "/api/builder/projects",
    });
    return result.projects;
  }

  async get(projectId: string): Promise<BuilderProjectRecord> {
    return this.http.request<BuilderProjectRecord>({
      method: "GET",
      path: `/api/builder/projects/${encodeURIComponent(projectId)}`,
    });
  }

  async create(project: BuilderProjectRecord): Promise<BuilderProjectRecord> {
    return this.http.request<BuilderProjectRecord>({
      method: "POST",
      path: "/api/builder/projects",
      body: project as Record<string, unknown>,
    });
  }

  async update(projectId: string, project: BuilderProjectRecord): Promise<BuilderProjectRecord> {
    return this.http.request<BuilderProjectRecord>({
      method: "PUT",
      path: `/api/builder/projects/${encodeURIComponent(projectId)}`,
      body: project as Record<string, unknown>,
    });
  }

  async save(project: BuilderProjectRecord): Promise<BuilderProjectRecord> {
    if (!project.id) {
      return this.create(project);
    }
    return this.update(project.id, project);
  }

  async runTest(projectId: string): Promise<BuilderProjectRecord> {
    return this.http.request<BuilderProjectRecord>({
      method: "POST",
      path: `/api/builder/projects/${encodeURIComponent(projectId)}/test-runs`,
    });
  }

  async delete(projectId: string): Promise<{ id: string; deleted: boolean }> {
    return this.http.request<{ id: string; deleted: boolean }>({
      method: "DELETE",
      path: `/api/builder/projects/${encodeURIComponent(projectId)}`,
    });
  }

  async chat(params: {
    projectId?: string;
    message: string;
    context?: Record<string, unknown>;
  }): Promise<{
    project: BuilderProjectRecord;
    assistant_message: string;
    stage: string;
  }> {
    return this.http.request<{
      project: BuilderProjectRecord;
      assistant_message: string;
      stage: string;
    }>({
      method: "POST",
      path: "/api/builder/chat",
      body: {
        project_id: params.projectId,
        message: params.message,
        context: params.context || {},
      },
    });
  }
}

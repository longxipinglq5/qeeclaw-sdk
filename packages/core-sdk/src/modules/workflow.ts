import type { HttpClient } from "../client/http-client.js";

export interface WorkflowNodeData {
  label: string;
  type: string;
  handler: string;
  config: Record<string, unknown>;
}

export interface WorkflowNode {
  id: string;
  position: {
    x: number;
    y: number;
  };
  data: WorkflowNodeData;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
}

export interface WorkflowDefinition {
  id: string;
  name: string;
  description?: string | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  enabled: boolean;
}

export interface WorkflowRunResult {
  executionId: string;
}

interface RawWorkflowRunResult {
  execution_id: string;
}

export class WorkflowModule {
  constructor(private readonly http: HttpClient) {}

  async save(definition: WorkflowDefinition): Promise<void> {
    await this.http.request<null>({
      method: "POST",
      path: "/api/workflows",
      body: definition as unknown as Record<string, unknown>,
    });
  }

  async list(): Promise<WorkflowDefinition[]> {
    return this.http.request<WorkflowDefinition[]>({
      method: "GET",
      path: "/api/workflows",
    });
  }

  async get(workflowId: string): Promise<WorkflowDefinition> {
    return this.http.request<WorkflowDefinition>({
      method: "GET",
      path: `/api/workflows/${encodeURIComponent(workflowId)}`,
    });
  }

  async run(workflowId: string, payload: Record<string, unknown> = {}): Promise<WorkflowRunResult> {
    const result = await this.http.request<RawWorkflowRunResult>({
      method: "POST",
      path: `/api/workflows/${encodeURIComponent(workflowId)}/run`,
      body: payload,
    });
    return {
      executionId: result.execution_id,
    };
  }

  async getExecutionLogs(executionId: string): Promise<string[]> {
    return this.http.request<string[]>({
      method: "GET",
      path: `/api/workflows/executions/${encodeURIComponent(executionId)}/logs`,
    });
  }
}

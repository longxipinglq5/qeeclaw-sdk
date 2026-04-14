import type { HttpClient } from "../client/http-client.js";

export interface AgentToolInputSchema {
  type: string;
  properties: Record<string, unknown>;
  required?: string[];
}

export interface AgentToolDefinition {
  name: string;
  description?: string | null;
  inputSchema: AgentToolInputSchema;
  tags: string[];
}

export interface MyAgent {
  id: number;
  name: string;
  code: string;
  description?: string | null;
  avatar?: string | null;
  voiceId?: string | null;
  runtimeType?: string | null;
  runtimeLabel?: string | null;
  model?: string | null;
}

interface RawMyAgent {
  id: number;
  name: string;
  code: string;
  description?: string | null;
  avatar?: string | null;
  voice_id?: string | null;
  runtime_type?: string | null;
  runtime_label?: string | null;
  model?: string | null;
}

export interface AgentCreateRequest {
  name: string;
  description?: string;
  model?: string;
  runtimeType?: string;
}

export interface AgentCreateResult {
  id: number;
  code: string;
  runtimeType?: string | null;
}

interface RawAgentCreateResult {
  id: number;
  code: string;
  runtime_type?: string | null;
}

export interface AgentTemplate {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  avatar?: string | null;
  allowedTools: string[];
}

interface RawAgentTemplate {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  avatar?: string | null;
  allowed_tools?: string[];
}

function mapAgent(value: RawMyAgent): MyAgent {
  return {
    id: value.id,
    name: value.name,
    code: value.code,
    description: value.description,
    avatar: value.avatar,
    voiceId: value.voice_id,
    runtimeType: value.runtime_type,
    runtimeLabel: value.runtime_label,
    model: value.model,
  };
}

function mapTemplate(value: RawAgentTemplate): AgentTemplate {
  return {
    id: value.id,
    code: value.code,
    name: value.name,
    description: value.description,
    avatar: value.avatar,
    allowedTools: value.allowed_tools ?? [],
  };
}

export class AgentModule {
  constructor(private readonly http: HttpClient) {}

  async listTools(): Promise<AgentToolDefinition[]> {
    return this.http.request<AgentToolDefinition[]>({
      method: "GET",
      path: "/api/agent/tools",
    });
  }

  async listMyAgents(): Promise<MyAgent[]> {
    const result = await this.http.request<RawMyAgent[]>({
      method: "GET",
      path: "/api/agent/my-agents",
    });
    return result.map(mapAgent);
  }

  async create(payload: AgentCreateRequest): Promise<AgentCreateResult> {
    const result = await this.http.request<RawAgentCreateResult>({
      method: "POST",
      path: "/api/agent/create",
      body: {
        name: payload.name,
        description: payload.description ?? "",
        model: payload.model ?? "gpt-4o",
        runtime_type: payload.runtimeType ?? "openclaw",
      },
    });
    return {
      id: result.id,
      code: result.code,
      runtimeType: result.runtime_type,
    };
  }

  async update(agentId: number, payload: AgentCreateRequest): Promise<void> {
    await this.http.request<null>({
      method: "PUT",
      path: `/api/agent/${agentId}`,
      body: {
        name: payload.name,
        description: payload.description ?? "",
        model: payload.model ?? "gpt-4o",
        runtime_type: payload.runtimeType ?? "openclaw",
      },
    });
  }

  async listDefaultTemplates(): Promise<AgentTemplate[]> {
    const result = await this.http.request<RawAgentTemplate[]>({
      method: "GET",
      path: "/agent_config/default",
    });
    return result.map(mapTemplate);
  }

  async getTemplate(code: string): Promise<AgentTemplate> {
    const result = await this.http.request<RawAgentTemplate>({
      method: "GET",
      path: `/agent_config/${encodeURIComponent(code)}`,
    });
    return mapTemplate(result);
  }
}

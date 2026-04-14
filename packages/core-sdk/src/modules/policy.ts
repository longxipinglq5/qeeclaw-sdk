import type { HttpClient } from "../client/http-client.js";
import type { PolicyDecision } from "../types.js";

export interface PolicyDecisionResult extends PolicyDecision {
  requiresApproval?: boolean;
  checkedAt?: string;
  checkedFor?: Record<string, unknown>;
}

export interface ToolAccessCheckInput {
  toolName: string;
  riskLevel?: "low" | "medium" | "high" | "critical";
  requiresApproval?: boolean;
  agentId?: string;
  deviceId?: string;
  teamId?: number;
  metadata?: Record<string, unknown>;
}

export interface DataAccessCheckInput {
  resourceType: string;
  resourceId?: string;
  classification?: "public" | "internal" | "confidential" | "restricted" | "secret";
  operation?: "read" | "write" | "delete" | "export";
  requiresApproval?: boolean;
  agentId?: string;
  deviceId?: string;
  teamId?: number;
  metadata?: Record<string, unknown>;
}

export interface ExecAccessCheckInput {
  command: string;
  workspacePath?: string;
  riskLevel?: "low" | "medium" | "high" | "critical";
  requiresApproval?: boolean;
  agentId?: string;
  deviceId?: string;
  teamId?: number;
  metadata?: Record<string, unknown>;
}

export class PolicyModule {
  constructor(private readonly http: HttpClient) {}

  async checkToolAccess(payload: ToolAccessCheckInput): Promise<PolicyDecisionResult> {
    return this.http.request<PolicyDecisionResult>({
      method: "POST",
      path: "/api/platform/policy/tool-access/check",
      body: {
        tool_name: payload.toolName,
        risk_level: payload.riskLevel ?? "medium",
        requires_approval: payload.requiresApproval ?? false,
        agent_id: payload.agentId,
        device_id: payload.deviceId,
        team_id: payload.teamId,
        metadata: payload.metadata ?? {},
      },
    });
  }

  async checkDataAccess(payload: DataAccessCheckInput): Promise<PolicyDecisionResult> {
    return this.http.request<PolicyDecisionResult>({
      method: "POST",
      path: "/api/platform/policy/data-access/check",
      body: {
        resource_type: payload.resourceType,
        resource_id: payload.resourceId,
        classification: payload.classification ?? "internal",
        operation: payload.operation ?? "read",
        requires_approval: payload.requiresApproval ?? false,
        agent_id: payload.agentId,
        device_id: payload.deviceId,
        team_id: payload.teamId,
        metadata: payload.metadata ?? {},
      },
    });
  }

  async checkExecAccess(payload: ExecAccessCheckInput): Promise<PolicyDecisionResult> {
    return this.http.request<PolicyDecisionResult>({
      method: "POST",
      path: "/api/platform/policy/exec-access/check",
      body: {
        command: payload.command,
        workspace_path: payload.workspacePath,
        risk_level: payload.riskLevel ?? "medium",
        requires_approval: payload.requiresApproval ?? false,
        agent_id: payload.agentId,
        device_id: payload.deviceId,
        team_id: payload.teamId,
        metadata: payload.metadata ?? {},
      },
    });
  }
}

import { JsonHttpClient } from "../http/json-http-client.js";
import type {
  ApprovalListResult,
  ApprovalRecord,
  BootstrapDeviceResult,
  MemorySearchResult,
  PlatformAccountDeviceState,
  PolicyDecision,
} from "../types.js";

type RawApprovalRecord = {
  approval_id: string;
  status: "pending" | "approved" | "rejected" | "expired";
  approval_type: "tool_access" | "data_access" | "exec_access" | "custom";
  title: string;
  reason: string;
  risk_level: "low" | "medium" | "high" | "critical";
  payload: Record<string, unknown>;
  requested_by: {
    user_id: number;
    username: string;
  };
  resolved_by?: {
    user_id: number;
    username: string;
  } | null;
  resolution_comment?: string | null;
  created_at: string;
  expires_at: string;
  resolved_at?: string | null;
};

export class ControlPlaneClient {
  private readonly http: JsonHttpClient;

  constructor(baseUrl: string) {
    this.http = new JsonHttpClient(baseUrl);
  }

  getAccountDeviceState(userToken: string, installationId: string): Promise<PlatformAccountDeviceState> {
    return this.http.request({
      method: "GET",
      path: "/api/platform/devices/account-state",
      token: userToken,
      query: { installation_id: installationId },
    });
  }

  listDevices(userToken: string): Promise<unknown[]> {
    return this.http.request({
      method: "GET",
      path: "/api/platform/devices",
      token: userToken,
    });
  }

  bootstrapDevice(
    userToken: string,
    payload: {
      installation_id: string;
      device_name: string;
      hostname: string;
      os_info: string;
    },
  ): Promise<BootstrapDeviceResult> {
    return this.http.request({
      method: "POST",
      path: "/api/platform/devices/bootstrap",
      token: userToken,
      body: payload,
    });
  }

  memoryStore(token: string, body: Record<string, unknown>): Promise<unknown> {
    return this.http.request({
      method: "POST",
      path: "/api/platform/memory/store",
      token,
      body,
    });
  }

  memorySearch(token: string, body: Record<string, unknown>): Promise<MemorySearchResult[]> {
    return this.http.request({
      method: "POST",
      path: "/api/platform/memory/search",
      token,
      body,
    });
  }

  memoryDelete(token: string, entryId: string): Promise<unknown> {
    return this.http.request({
      method: "DELETE",
      path: `/api/platform/memory/${encodeURIComponent(entryId)}`,
      token,
    });
  }

  memoryStats(token: string, agentId?: string): Promise<unknown> {
    return this.http.request({
      method: "GET",
      path: "/api/platform/memory/stats",
      token,
      query: { agent_id: agentId },
    });
  }

  checkToolAccess(token: string, body: Record<string, unknown>): Promise<PolicyDecision> {
    return this.http.request({
      method: "POST",
      path: "/api/platform/policy/tool-access/check",
      token,
      body,
    }).then((result) => this.mapPolicyDecision(result as Record<string, unknown>, "control-plane"));
  }

  checkDataAccess(token: string, body: Record<string, unknown>): Promise<PolicyDecision> {
    return this.http.request({
      method: "POST",
      path: "/api/platform/policy/data-access/check",
      token,
      body,
    }).then((result) => this.mapPolicyDecision(result as Record<string, unknown>, "control-plane"));
  }

  checkExecAccess(token: string, body: Record<string, unknown>): Promise<PolicyDecision> {
    return this.http.request({
      method: "POST",
      path: "/api/platform/policy/exec-access/check",
      token,
      body,
    }).then((result) => this.mapPolicyDecision(result as Record<string, unknown>, "control-plane"));
  }

  requestApproval(token: string, body: Record<string, unknown>): Promise<ApprovalRecord> {
    return this.http.request({
      method: "POST",
      path: "/api/platform/approvals/request",
      token,
      body,
    }).then((result) => this.mapApprovalRecord(result as RawApprovalRecord));
  }

  listApprovals(
    token: string,
    params: {
      scope?: "mine" | "all";
      status?: "pending" | "approved" | "rejected" | "expired";
      page?: number;
      page_size?: number;
    } = {},
  ): Promise<ApprovalListResult> {
    return this.http.request<{
      total: number;
      page: number;
      page_size: number;
      items: RawApprovalRecord[];
    }>({
      method: "GET",
      path: "/api/platform/approvals",
      token,
      query: params,
    }).then((result) => ({
      total: result.total,
      page: result.page,
      pageSize: result.page_size,
      items: result.items.map((item) => this.mapApprovalRecord(item)),
    }));
  }

  private mapPolicyDecision(result: Record<string, unknown>, source: PolicyDecision["source"]): PolicyDecision {
    return {
      allowed: Boolean(result.allowed),
      reason: String(result.reason || ""),
      matchedPolicy: String(result.matched_policy || result.matchedPolicy || "unknown"),
      requiresApproval: Boolean(result.requires_approval || result.requiresApproval),
      source,
      checkedAt: String(result.checked_at || result.checkedAt || new Date().toISOString()),
    };
  }

  private mapApprovalRecord(record: RawApprovalRecord): ApprovalRecord {
    return {
      approvalId: record.approval_id,
      status: record.status,
      approvalType: record.approval_type,
      title: record.title,
      reason: record.reason,
      riskLevel: record.risk_level,
      payload: record.payload || {},
      requestedBy: {
        userId: record.requested_by.user_id,
        username: record.requested_by.username,
      },
      resolvedBy: record.resolved_by
        ? {
            userId: record.resolved_by.user_id,
            username: record.resolved_by.username,
          }
        : null,
      resolutionComment: record.resolution_comment,
      createdAt: record.created_at,
      expiresAt: record.expires_at,
      resolvedAt: record.resolved_at,
    };
  }
}

import type { HttpClient } from "../client/http-client.js";
import type { PaginatedResult } from "../types.js";

export interface ApprovalRecord {
  approvalId: string;
  status: "pending" | "approved" | "rejected" | "expired";
  approvalType: "tool_access" | "data_access" | "exec_access" | "custom";
  title: string;
  reason: string;
  riskLevel: "low" | "medium" | "high" | "critical";
  payload: Record<string, unknown>;
  requestedBy: {
    userId: number;
    username: string;
  };
  resolvedBy?: {
    userId: number;
    username: string;
  } | null;
  resolutionComment?: string | null;
  createdAt: string;
  expiresAt: string;
  resolvedAt?: string | null;
}

interface RawApprovalRecord {
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
}

interface RawApprovalListResponse {
  total: number;
  page: number;
  page_size: number;
  items: RawApprovalRecord[];
}

export interface ApprovalRequestInput {
  approvalType?: "tool_access" | "data_access" | "exec_access" | "custom";
  title: string;
  reason: string;
  riskLevel?: "low" | "medium" | "high" | "critical";
  payload?: Record<string, unknown>;
  expiresInSeconds?: number;
}

export interface ApprovalResolveInput {
  approved: boolean;
  comment?: string;
}

export interface ApprovalListParams {
  scope?: "mine" | "all";
  status?: "pending" | "approved" | "rejected" | "expired";
  approvalType?: "tool_access" | "data_access" | "exec_access" | "custom";
  riskLevel?: "low" | "medium" | "high" | "critical";
  requesterUserId?: number;
  keyword?: string;
  startAt?: string;
  endAt?: string;
  page?: number;
  pageSize?: number;
}

function mapApprovalRecord(record: RawApprovalRecord): ApprovalRecord {
  return {
    approvalId: record.approval_id,
    status: record.status,
    approvalType: record.approval_type,
    title: record.title,
    reason: record.reason,
    riskLevel: record.risk_level,
    payload: record.payload,
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

export class ApprovalModule {
  constructor(private readonly http: HttpClient) {}

  async request(payload: ApprovalRequestInput): Promise<ApprovalRecord> {
    const result = await this.http.request<RawApprovalRecord>({
      method: "POST",
      path: "/api/platform/approvals/request",
      body: {
        approval_type: payload.approvalType ?? "custom",
        title: payload.title,
        reason: payload.reason,
        risk_level: payload.riskLevel ?? "medium",
        payload: payload.payload ?? {},
        expires_in_seconds: payload.expiresInSeconds,
      },
    });
    return mapApprovalRecord(result);
  }

  async list(params: ApprovalListParams = {}): Promise<PaginatedResult<ApprovalRecord>> {
    const results = await this.http.request<RawApprovalListResponse>({
      method: "GET",
      path: "/api/platform/approvals",
      query: {
        scope: params.scope ?? "mine",
        status: params.status,
        approval_type: params.approvalType,
        risk_level: params.riskLevel,
        requester_user_id: params.requesterUserId,
        keyword: params.keyword,
        start_at: params.startAt,
        end_at: params.endAt,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
      },
    });
    return {
      total: results.total,
      page: results.page,
      pageSize: results.page_size,
      items: results.items.map(mapApprovalRecord),
    };
  }

  async get(approvalId: string): Promise<ApprovalRecord> {
    const result = await this.http.request<RawApprovalRecord>({
      method: "GET",
      path: `/api/platform/approvals/${encodeURIComponent(approvalId)}`,
    });
    return mapApprovalRecord(result);
  }

  async resolve(approvalId: string, payload: ApprovalResolveInput): Promise<ApprovalRecord> {
    const result = await this.http.request<RawApprovalRecord>({
      method: "POST",
      path: `/api/platform/approvals/${encodeURIComponent(approvalId)}/resolve`,
      body: {
        approved: payload.approved,
        comment: payload.comment,
      },
    });
    return mapApprovalRecord(result);
  }
}

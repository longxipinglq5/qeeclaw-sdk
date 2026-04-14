import type { HttpClient } from "../client/http-client.js";
import type { PaginatedResult } from "../types.js";

export class AuditModule {
  constructor(private readonly http: HttpClient) {}

  async record(payload: AuditRecordRequest): Promise<void> {
    await this.http.request<null>({
      method: "POST",
      path: "/api/platform/audit/events",
      body: {
        action_type: payload.actionType,
        title: payload.title,
        module: payload.module ?? "SDK",
        path: payload.path,
        params: payload.params,
      },
    });
  }

  async getWorkflowExecutionLogs(executionId: string): Promise<unknown[]> {
    return this.http.request<unknown[]>({
      method: "GET",
      path: `/api/workflows/executions/${encodeURIComponent(executionId)}/logs`,
    });
  }

  async listEvents(params: AuditEventListParams = {}): Promise<PaginatedResult<AuditEvent>> {
    const results = await this.http.request<RawAuditEventListResponse>({
      method: "GET",
      path: "/api/platform/audit/events",
      query: {
        scope: params.scope ?? "mine",
        category: params.category ?? "all",
        module: params.module,
        event_type: params.eventType,
        status: params.status,
        risk_level: params.riskLevel,
        actor_user_id: params.actorUserId,
        keyword: params.keyword,
        start_at: params.startAt,
        end_at: params.endAt,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 50,
      },
    });
    return {
      total: results.total,
      page: results.page,
      pageSize: results.page_size,
      items: results.items.map(mapAuditEvent),
    };
  }

  async getSummary(params: AuditSummaryParams = {}): Promise<AuditSummary> {
    const result = await this.http.request<RawAuditSummary>({
      method: "GET",
      path: "/api/platform/audit/summary",
      query: {
        scope: params.scope ?? "mine",
        category: params.category ?? "all",
        module: params.module,
        event_type: params.eventType,
        status: params.status,
        risk_level: params.riskLevel,
        actor_user_id: params.actorUserId,
        keyword: params.keyword,
        start_at: params.startAt,
        end_at: params.endAt,
      },
    });
    return {
      total: result.total,
      operationCount: result.operation_count,
      approvalCount: result.approval_count,
      pendingApprovalCount: result.pending_approval_count,
      approvedApprovalCount: result.approved_approval_count,
      rejectedApprovalCount: result.rejected_approval_count,
      expiredApprovalCount: result.expired_approval_count,
    };
  }
}

export interface AuditRecordRequest {
  actionType: string;
  title: string;
  module?: string;
  path?: string;
  params?: string;
}

export interface AuditEvent {
  eventId: string;
  category: "operation" | "approval";
  eventType: string;
  title: string;
  summary?: string | null;
  module?: string | null;
  path?: string | null;
  status?: string | null;
  riskLevel?: string | null;
  actor?: {
    userId?: number;
    username?: string;
  };
  metadata?: Record<string, unknown>;
  createdAt?: string | null;
}

interface RawAuditEvent {
  event_id: string;
  category: "operation" | "approval";
  event_type: string;
  title: string;
  summary?: string | null;
  module?: string | null;
  path?: string | null;
  status?: string | null;
  risk_level?: string | null;
  actor?: {
    user_id?: number;
    username?: string;
  };
  metadata?: Record<string, unknown>;
  created_at?: string | null;
}

interface RawAuditEventListResponse {
  total: number;
  page: number;
  page_size: number;
  items: RawAuditEvent[];
}

export interface AuditEventListParams {
  scope?: "mine" | "all";
  category?: "all" | "operation" | "approval";
  module?: string;
  eventType?: string;
  status?: "pending" | "approved" | "rejected" | "expired";
  riskLevel?: "low" | "medium" | "high" | "critical";
  actorUserId?: number;
  keyword?: string;
  startAt?: string;
  endAt?: string;
  page?: number;
  pageSize?: number;
}

export interface AuditSummary {
  total: number;
  operationCount: number;
  approvalCount: number;
  pendingApprovalCount: number;
  approvedApprovalCount: number;
  rejectedApprovalCount: number;
  expiredApprovalCount: number;
}

export interface AuditSummaryParams {
  scope?: "mine" | "all";
  category?: "all" | "operation" | "approval";
  module?: string;
  eventType?: string;
  status?: "pending" | "approved" | "rejected" | "expired";
  riskLevel?: "low" | "medium" | "high" | "critical";
  actorUserId?: number;
  keyword?: string;
  startAt?: string;
  endAt?: string;
}

interface RawAuditSummary {
  total: number;
  operation_count: number;
  approval_count: number;
  pending_approval_count: number;
  approved_approval_count: number;
  rejected_approval_count: number;
  expired_approval_count: number;
}

function mapAuditEvent(event: RawAuditEvent): AuditEvent {
  return {
    eventId: event.event_id,
    category: event.category,
    eventType: event.event_type,
    title: event.title,
    summary: event.summary,
    module: event.module,
    path: event.path,
    status: event.status,
    riskLevel: event.risk_level,
    actor: event.actor
      ? {
          userId: event.actor.user_id,
          username: event.actor.username,
        }
      : undefined,
    metadata: event.metadata,
    createdAt: event.created_at,
  };
}

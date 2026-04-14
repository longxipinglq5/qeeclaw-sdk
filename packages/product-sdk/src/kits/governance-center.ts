import type {
  PaginatedResult,
  ProductApprovalRecord,
  ProductAuditEvent,
  ProductAuditSummary,
  ProductSdkClient,
} from "../types.js";

export interface GovernanceCenterHome {
  summary: ProductAuditSummary;
  pendingApprovals: ProductApprovalRecord[];
  recentEvents: ProductAuditEvent[];
}

export class GovernanceCenterKit {
  constructor(private readonly client: ProductSdkClient) {}

  async loadHome(scope: "mine" | "all" = "mine"): Promise<GovernanceCenterHome> {
    const [summary, approvals, events] = await Promise.all([
      this.client.audit.getSummary({ scope }),
      this.client.approval.list({ scope, status: "pending", page: 1, pageSize: 10 }),
      this.client.audit.listEvents({ scope, category: "all", page: 1, pageSize: 10 }),
    ]);

    return {
      summary,
      pendingApprovals: approvals.items,
      recentEvents: events.items,
    };
  }

  listApprovals(params?: {
    scope?: "mine" | "all";
    status?: "pending" | "approved" | "rejected" | "expired";
    page?: number;
    pageSize?: number;
  }): Promise<PaginatedResult<ProductApprovalRecord>> {
    return this.client.approval.list(params);
  }

  listAuditEvents(params?: {
    scope?: "mine" | "all";
    category?: "all" | "operation" | "approval";
    page?: number;
    pageSize?: number;
  }): Promise<PaginatedResult<ProductAuditEvent>> {
    return this.client.audit.listEvents(params);
  }
}

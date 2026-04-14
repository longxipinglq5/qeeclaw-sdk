import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import type { ControlPlaneClient } from "../control-plane/client.js";
import type { AuthStateStore } from "../state/auth-state-store.js";
import type { ApprovalListResult, ApprovalRecord, PolicyDecision } from "../types.js";

type PendingApprovalsState = {
  pending: ApprovalRecord[];
  updatedAt?: string;
};

export class ApprovalAgent {
  constructor(
    private readonly cacheFilePath: string,
    private readonly stateStore: AuthStateStore,
    private readonly controlPlane: ControlPlaneClient,
  ) {}

  private async readCache(): Promise<PendingApprovalsState> {
    try {
      const raw = await readFile(this.cacheFilePath, "utf8");
      return JSON.parse(raw) as PendingApprovalsState;
    } catch {
      return { pending: [] };
    }
  }

  private async writeCache(nextState: PendingApprovalsState): Promise<void> {
    await mkdir(path.dirname(this.cacheFilePath), { recursive: true });
    await writeFile(
      this.cacheFilePath,
      JSON.stringify({ ...nextState, updatedAt: new Date().toISOString() }, null, 2),
    );
  }

  private async resolveToken(): Promise<string> {
    const state = await this.stateStore.read();
    if (state.userToken?.trim()) {
      return state.userToken;
    }
    if (state.deviceKey?.trim()) {
      return state.deviceKey;
    }
    throw new Error("No user token or device key available for approval agent");
  }

  async requestApproval(input: {
    approvalType?: "tool_access" | "data_access" | "exec_access" | "custom";
    title: string;
    reason: string;
    riskLevel?: "low" | "medium" | "high" | "critical";
    payload?: Record<string, unknown>;
    expiresInSeconds?: number;
  }): Promise<ApprovalRecord> {
    const record = await this.controlPlane.requestApproval(await this.resolveToken(), {
      approval_type: input.approvalType || "custom",
      title: input.title,
      reason: input.reason,
      risk_level: input.riskLevel || "medium",
      payload: input.payload || {},
      expires_in_seconds: input.expiresInSeconds,
    });

    const cache = await this.readCache();
    const pending = cache.pending.filter((item) => item.approvalId !== record.approvalId);
    pending.unshift(record);
    await this.writeCache({ pending });
    return record;
  }

  async requestFromDecision(input: {
    decision: PolicyDecision;
    approvalType: "tool_access" | "data_access" | "exec_access";
    title: string;
    riskLevel: "low" | "medium" | "high" | "critical";
    payload?: Record<string, unknown>;
    expiresInSeconds?: number;
  }): Promise<ApprovalRecord | null> {
    if (!input.decision.requiresApproval) {
      return null;
    }
    return this.requestApproval({
      approvalType: input.approvalType,
      title: input.title,
      reason: input.decision.reason,
      riskLevel: input.riskLevel,
      payload: input.payload,
      expiresInSeconds: input.expiresInSeconds,
    });
  }

  async listApprovals(params: { scope?: "mine" | "all"; status?: ApprovalRecord["status"] } = {}): Promise<ApprovalListResult> {
    const result = await this.controlPlane.listApprovals(await this.resolveToken(), {
      scope: params.scope || "mine",
      status: params.status,
      page: 1,
      page_size: 50,
    });
    const pending = result.items.filter((item) => item.status === "pending");
    await this.writeCache({ pending });
    return result;
  }

  async listPendingLocalCache(): Promise<ApprovalRecord[]> {
    const cache = await this.readCache();
    return cache.pending;
  }
}

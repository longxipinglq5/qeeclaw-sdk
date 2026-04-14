import type { ControlPlaneClient } from "../control-plane/client.js";
import type { AuthStateStore } from "../state/auth-state-store.js";

export class MemoryWorker {
  constructor(
    private readonly stateStore: AuthStateStore,
    private readonly controlPlane: ControlPlaneClient,
  ) {}

  private async resolveToken(): Promise<string> {
    const token = await this.stateStore.resolvePreferredToken();
    if (!token) {
      throw new Error("No device key or user token available for memory worker");
    }
    return token;
  }

  async store(payload: Record<string, unknown>): Promise<unknown> {
    return this.controlPlane.memoryStore(await this.resolveToken(), payload);
  }

  async search(payload: Record<string, unknown>): Promise<unknown> {
    return this.controlPlane.memorySearch(await this.resolveToken(), payload);
  }

  async delete(entryId: string): Promise<unknown> {
    return this.controlPlane.memoryDelete(await this.resolveToken(), entryId);
  }

  async stats(agentId?: string): Promise<unknown> {
    return this.controlPlane.memoryStats(await this.resolveToken(), agentId);
  }
}

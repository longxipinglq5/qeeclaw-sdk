import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";

import type { SidecarAuthState, SidecarPublicAuthState } from "../types.js";

async function ensureParentDir(filePath: string): Promise<void> {
  await mkdir(path.dirname(filePath), { recursive: true });
}

export function toPublicAuthState(
  state: SidecarAuthState,
  options: { configuredAuthToken?: string } = {},
): SidecarPublicAuthState {
  return {
    installationId: state.installationId,
    authMode: state.authMode,
    hasUserToken: Boolean(state.userToken?.trim()),
    hasDeviceKey: Boolean(state.deviceKey?.trim()),
    sidecarAuthTokenConfigured: Boolean(state.sidecarAuthToken?.trim() || options.configuredAuthToken?.trim()),
    deviceId: state.deviceId,
    updatedAt: state.updatedAt,
  };
}

export class AuthStateStore {
  constructor(private readonly filePath: string) {}

  async read(): Promise<SidecarAuthState> {
    try {
      const raw = await readFile(this.filePath, "utf8");
      const parsed = JSON.parse(raw) as SidecarAuthState;
      return typeof parsed === "object" && parsed ? parsed : {};
    } catch {
      return {};
    }
  }

  async write(nextState: SidecarAuthState): Promise<SidecarAuthState> {
    await ensureParentDir(this.filePath);
    const payload: SidecarAuthState = {
      ...nextState,
      updatedAt: nextState.updatedAt || new Date().toISOString(),
    };
    await writeFile(this.filePath, JSON.stringify(payload, null, 2));
    return payload;
  }

  async patch(patch: Partial<SidecarAuthState>): Promise<SidecarAuthState> {
    const current = await this.read();
    return this.write({
      ...current,
      ...patch,
      updatedAt: new Date().toISOString(),
    });
  }

  async ensureInstallationId(): Promise<string> {
    const current = await this.read();
    if (current.installationId?.trim()) {
      return current.installationId;
    }
    const installationId = crypto.randomUUID().toLowerCase();
    await this.patch({ installationId });
    return installationId;
  }

  async ensureSidecarAuthToken(preferredToken?: string): Promise<string> {
    const normalizedPreferred = preferredToken?.trim();
    const current = await this.read();

    if (normalizedPreferred) {
      if (current.sidecarAuthToken !== normalizedPreferred) {
        await this.patch({ sidecarAuthToken: normalizedPreferred });
      }
      return normalizedPreferred;
    }

    if (current.sidecarAuthToken?.trim()) {
      return current.sidecarAuthToken;
    }

    const sidecarAuthToken = crypto.randomBytes(24).toString("base64url");
    await this.patch({ sidecarAuthToken });
    return sidecarAuthToken;
  }

  async resolvePreferredToken(): Promise<string | undefined> {
    const current = await this.read();
    return current.deviceKey?.trim() || current.userToken?.trim() || undefined;
  }
}

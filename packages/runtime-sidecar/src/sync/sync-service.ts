import type { ControlPlaneClient } from "../control-plane/client.js";
import type { AuthStateStore } from "../state/auth-state-store.js";
import type { SidecarConfig, SyncResult } from "../types.js";

export class SyncService {
  constructor(
    private readonly config: SidecarConfig,
    private readonly stateStore: AuthStateStore,
    private readonly controlPlane: ControlPlaneClient,
  ) {}

  async sync(): Promise<SyncResult> {
    const installationId = await this.stateStore.ensureInstallationId();
    const state = await this.stateStore.read();
    const hasUserToken = Boolean(state.userToken?.trim());
    const hasDeviceKey = Boolean(state.deviceKey?.trim());

    if (!hasUserToken) {
      return {
        installationId,
        authMode: state.authMode || "anonymous",
        hasUserToken,
        hasDeviceKey,
        bootstrapPerformed: false,
        deviceId: state.deviceId,
      };
    }

    const accountState = await this.controlPlane.getAccountDeviceState(state.userToken!, installationId);
    let bootstrapPerformed = false;
    let deviceId = state.deviceId;

    if (
      this.config.autoBootstrapDevice &&
      accountState.can_register_current_account &&
      (accountState.state === "unregistered" || accountState.state === "current_user") &&
      !hasDeviceKey
    ) {
      const bootstrap = await this.controlPlane.bootstrapDevice(state.userToken!, {
        installation_id: installationId,
        device_name: this.config.deviceName,
        hostname: this.config.hostname,
        os_info: this.config.osInfo,
      });
      bootstrapPerformed = true;
      deviceId = bootstrap.device_id;
      await this.stateStore.patch({
        deviceKey: bootstrap.api_key,
        deviceId: bootstrap.device_id,
        authMode: "personal-device",
        installationId,
      });
    }

    const nextState = await this.stateStore.read();
    return {
      installationId,
      authMode: nextState.authMode || "account-only",
      hasUserToken: Boolean(nextState.userToken?.trim()),
      hasDeviceKey: Boolean(nextState.deviceKey?.trim()),
      bootstrapPerformed,
      deviceId,
      accountState,
    };
  }
}

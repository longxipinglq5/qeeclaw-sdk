import { QeeClawNotImplementedError } from "../errors.js";
import type { HttpClient } from "../client/http-client.js";

export interface QeeClawDeviceInfo {
  id: number;
  deviceName: string;
  hostname?: string | null;
  osInfo?: string | null;
  status: string;
  lastSeen?: string | null;
  createdTime?: string | null;
  teamId?: number;
  registrationMode?: string | null;
  installationId?: string | null;
}

interface RawDeviceInfo {
  id: number;
  device_name: string;
  hostname?: string | null;
  os_info?: string | null;
  status: string;
  last_seen?: string | null;
  created_time?: string | null;
  team_id?: number;
  registration_mode?: string | null;
  installation_id?: string | null;
}

export interface DeviceAccountState {
  installationId: string;
  state: "current_user" | "other_user" | "unregistered";
  canRegisterCurrentAccount: boolean;
  currentUserDeviceId?: number | null;
  currentUserHasDevices: boolean;
}

interface RawDeviceAccountState {
  installation_id: string;
  state: "current_user" | "other_user" | "unregistered";
  can_register_current_account: boolean;
  current_user_device_id?: number | null;
  current_user_has_devices: boolean;
}

export interface DeviceClaimRequest {
  code: string;
  deviceName: string;
  hostname?: string;
  osInfo?: string;
}

export interface DeviceBootstrapRequest {
  installationId: string;
  deviceName: string;
  hostname?: string;
  osInfo?: string;
}

export interface DeviceConnectionConfig {
  apiKey: string;
  baseUrl: string;
  wsUrl: string;
  deviceId: number;
  deviceName: string;
  installationId?: string;
  registrationMode?: string;
}

interface RawDeviceConnectionConfig {
  api_key: string;
  base_url: string;
  ws_url: string;
  device_id: number;
  device_name: string;
  installation_id?: string;
  registration_mode?: string;
}

export interface DeviceOnlineState {
  runtimeType: string;
  runtimeLabel: string;
  runtimeStatus: string;
  runtimeStage: string;
  supportsDeviceBridge: boolean;
  supportsManagedDownload: boolean;
  onlineTeamIds: number[];
  notes: string;
}

interface RawDeviceOnlineState {
  runtime_type?: string;
  runtime_label?: string;
  runtime_status?: string;
  runtime_stage?: string;
  supports_device_bridge?: boolean;
  supports_managed_download?: boolean;
  online_team_ids?: number[];
  notes?: string;
}

export interface PairCodeResult {
  pairCode: string;
  expiresInSeconds: number;
  expiresAt?: string;
}

interface RawPairCodeResult {
  pair_code: string;
  expires_in_seconds: number;
  expires_at?: string;
}

export class DevicesModule {
  constructor(private readonly http: HttpClient) {}

  async list(): Promise<QeeClawDeviceInfo[]> {
    const items = await this.http.request<RawDeviceInfo[]>({
      method: "GET",
      path: "/api/platform/devices",
    });

    return items.map((item) => ({
      id: item.id,
      deviceName: item.device_name,
      hostname: item.hostname,
      osInfo: item.os_info,
      status: item.status,
      lastSeen: item.last_seen,
      createdTime: item.created_time,
      teamId: item.team_id,
      registrationMode: item.registration_mode,
      installationId: item.installation_id,
    }));
  }

  async register(payload: DeviceBootstrapRequest): Promise<DeviceConnectionConfig> {
    return this.bootstrap(payload);
  }

  async bootstrap(payload: DeviceBootstrapRequest): Promise<DeviceConnectionConfig> {
    const result = await this.http.request<RawDeviceConnectionConfig>({
      method: "POST",
      path: "/api/platform/devices/bootstrap",
      body: {
        installation_id: payload.installationId,
        device_name: payload.deviceName,
        hostname: payload.hostname,
        os_info: payload.osInfo,
      },
    });

    return {
      apiKey: result.api_key,
      baseUrl: result.base_url,
      wsUrl: result.ws_url,
      deviceId: result.device_id,
      deviceName: result.device_name,
      installationId: result.installation_id,
      registrationMode: result.registration_mode,
    };
  }

  async getAccountState(installationId: string): Promise<DeviceAccountState> {
    const result = await this.http.request<RawDeviceAccountState>({
      method: "GET",
      path: "/api/platform/devices/account-state",
      query: {
        installation_id: installationId,
      },
    });

    return {
      installationId: result.installation_id,
      state: result.state,
      canRegisterCurrentAccount: result.can_register_current_account,
      currentUserDeviceId: result.current_user_device_id,
      currentUserHasDevices: result.current_user_has_devices,
    };
  }

  async createPairCode(): Promise<PairCodeResult> {
    const result = await this.http.request<RawPairCodeResult>({
      method: "POST",
      path: "/api/platform/devices/pair-code",
    });

    return {
      pairCode: result.pair_code,
      expiresInSeconds: result.expires_in_seconds,
      expiresAt: result.expires_at,
    };
  }

  async claim(payload: DeviceClaimRequest): Promise<DeviceConnectionConfig> {
    const result = await this.http.request<RawDeviceConnectionConfig>({
      method: "POST",
      path: "/api/platform/devices/claim",
      body: {
        code: payload.code,
        device_name: payload.deviceName,
        hostname: payload.hostname,
        os_info: payload.osInfo,
      },
    });

    return {
      apiKey: result.api_key,
      baseUrl: result.base_url,
      wsUrl: result.ws_url,
      deviceId: result.device_id,
      deviceName: result.device_name,
      installationId: result.installation_id,
      registrationMode: result.registration_mode,
    };
  }

  async update(deviceId: number, deviceName: string): Promise<void> {
    await this.http.request<unknown>({
      method: "PUT",
      path: `/api/platform/devices/${deviceId}`,
      body: {
        device_name: deviceName,
      },
    });
  }

  async remove(deviceId: number): Promise<void> {
    await this.http.request<unknown>({
      method: "DELETE",
      path: `/api/platform/devices/${deviceId}`,
    });
  }

  async listOnline(): Promise<number[]> {
    const result = await this.getOnlineState();
    return result.onlineTeamIds;
  }

  async getOnlineState(): Promise<DeviceOnlineState> {
    const result = await this.http.request<RawDeviceOnlineState>({
      method: "GET",
      path: "/api/platform/devices/online",
    });

    return {
      runtimeType: result.runtime_type ?? "openclaw",
      runtimeLabel: result.runtime_label ?? "OpenClaw",
      runtimeStatus: result.runtime_status ?? "unknown",
      runtimeStage: result.runtime_stage ?? "phase_device_bridge_only",
      supportsDeviceBridge: Boolean(result.supports_device_bridge),
      supportsManagedDownload: Boolean(result.supports_managed_download),
      onlineTeamIds: result.online_team_ids ?? [],
      notes: result.notes ?? "当前设备中心仅管理 OpenClaw device bridge。",
    };
  }

  async routeCommand(): Promise<never> {
    throw new QeeClawNotImplementedError(
      "devices.routeCommand() is reserved for a future device hub API",
    );
  }
}

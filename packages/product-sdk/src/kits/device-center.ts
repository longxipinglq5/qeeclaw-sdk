import type {
  ProductDeviceAccountState,
  ProductDeviceConnectionConfig,
  ProductDeviceInfo,
  ProductSdkClient,
} from "../types.js";

export interface DeviceCenterOverview {
  total: number;
  online: number;
  offline: number;
  devices: ProductDeviceInfo[];
}

export class DeviceCenterKit {
  constructor(private readonly client: ProductSdkClient) {}

  async loadOverview(): Promise<DeviceCenterOverview> {
    const devices = await this.client.devices.list();
    const online = devices.filter((item) => item.status === "online").length;
    return {
      total: devices.length,
      online,
      offline: devices.length - online,
      devices,
    };
  }

  getAccountState(installationId: string): Promise<ProductDeviceAccountState> {
    return this.client.devices.getAccountState(installationId);
  }

  bootstrap(payload: {
    installationId: string;
    deviceName: string;
    hostname?: string;
    osInfo?: string;
  }): Promise<ProductDeviceConnectionConfig> {
    return this.client.devices.bootstrap(payload);
  }
}

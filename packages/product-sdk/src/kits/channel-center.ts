import type {
  ProductChannelBindingRecord,
  ProductChannelHome,
  ProductChannelOverview,
  ProductFeishuChannelConfig,
  ProductSdkClient,
  ProductWechatPersonalPluginChannelConfig,
  ProductWechatWorkChannelConfig,
} from "../types.js";

export class ChannelCenterKit {
  constructor(private readonly client: ProductSdkClient) {}

  async loadHome(teamId: number): Promise<ProductChannelHome> {
    const [overview, wechatWork, feishu, wechatPersonalPlugin] = await Promise.all([
      this.client.channels.getOverview(teamId),
      this.client.channels.getWechatWorkConfig(teamId),
      this.client.channels.getFeishuConfig(teamId),
      this.client.channels.getWechatPersonalPluginConfig(teamId),
    ]);

    return {
      overview,
      wechatWork,
      feishu,
      wechatPersonalPlugin,
    };
  }

  getOverview(teamId: number): Promise<ProductChannelOverview> {
    return this.client.channels.getOverview(teamId);
  }

  getWechatWorkConfig(teamId: number): Promise<ProductWechatWorkChannelConfig> {
    return this.client.channels.getWechatWorkConfig(teamId);
  }

  updateWechatWorkConfig(payload: {
    teamId: number;
    corpId: string;
    agentId: string;
    secret?: string;
  }): Promise<ProductWechatWorkChannelConfig> {
    return this.client.channels.updateWechatWorkConfig(payload);
  }

  getFeishuConfig(teamId: number): Promise<ProductFeishuChannelConfig> {
    return this.client.channels.getFeishuConfig(teamId);
  }

  updateFeishuConfig(payload: {
    teamId: number;
    appId: string;
    appSecret?: string;
    verificationToken?: string;
    encryptKey?: string;
  }): Promise<ProductFeishuChannelConfig> {
    return this.client.channels.updateFeishuConfig(payload);
  }

  getWechatPersonalPluginConfig(teamId: number): Promise<ProductWechatPersonalPluginChannelConfig> {
    return this.client.channels.getWechatPersonalPluginConfig(teamId);
  }

  updateWechatPersonalPluginConfig(payload: {
    teamId: number;
    displayName: string;
    assistantName?: string;
    welcomeMessage?: string;
    kernelCorpId?: string;
    kernelAgentId?: string;
    kernelSecret?: string;
    kernelVerifyToken?: string;
    kernelAesKey?: string;
    bindingEnabled?: boolean;
    enabled?: boolean;
  }): Promise<ProductWechatPersonalPluginChannelConfig> {
    return this.client.channels.updateWechatPersonalPluginConfig(payload);
  }

  listChannelBindings(
    teamId: number,
    channelKey: "wechat_work" | "feishu" | "wechat_personal_plugin" = "wechat_personal_plugin",
  ): Promise<{ items: ProductChannelBindingRecord[]; total: number }> {
    return this.client.channels.listChannelBindings(teamId, channelKey);
  }

  createChannelBinding(payload: {
    teamId: number;
    channelKey?: "wechat_work" | "feishu" | "wechat_personal_plugin";
    bindingType: string;
    bindingTargetId: string;
    bindingTargetName?: string;
    expiresInHours?: number;
    notes?: string;
  }): Promise<ProductChannelBindingRecord> {
    return this.client.channels.createChannelBinding(payload);
  }

  disableChannelBinding(bindingId: number): Promise<ProductChannelBindingRecord> {
    return this.client.channels.disableChannelBinding(bindingId);
  }

  regenerateChannelBindingCode(bindingId: number, expiresInHours = 72): Promise<ProductChannelBindingRecord> {
    return this.client.channels.regenerateChannelBindingCode(bindingId, expiresInHours);
  }
}

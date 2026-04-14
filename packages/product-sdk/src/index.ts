import { ChannelCenterKit } from "./kits/channel-center.js";
import { ConversationCenterKit } from "./kits/conversation-center.js";
import { DeviceCenterKit } from "./kits/device-center.js";
import { GovernanceCenterKit } from "./kits/governance-center.js";
import { KnowledgeCenterKit } from "./kits/knowledge-center.js";
import { SalesCoachingKit } from "./kits/sales-coaching.js";
import { SalesCockpitKit } from "./kits/sales-cockpit.js";
import { SalesKnowledgeKit } from "./kits/sales-knowledge.js";
import type { ProductSdkClient } from "./types.js";

export * from "./types.js";
export * from "./kits/channel-center.js";
export * from "./kits/conversation-center.js";
export * from "./kits/device-center.js";
export * from "./kits/knowledge-center.js";
export * from "./kits/governance-center.js";
export * from "./kits/sales-cockpit.js";
export * from "./kits/sales-knowledge.js";
export * from "./kits/sales-coaching.js";

export class QeeClawProductSDK {
  readonly channelCenter: ChannelCenterKit;
  readonly conversationCenter: ConversationCenterKit;
  readonly deviceCenter: DeviceCenterKit;
  readonly knowledgeCenter: KnowledgeCenterKit;
  readonly governanceCenter: GovernanceCenterKit;
  readonly salesCockpit: SalesCockpitKit;
  readonly salesKnowledge: SalesKnowledgeKit;
  readonly salesCoaching: SalesCoachingKit;

  constructor(client: ProductSdkClient) {
    this.channelCenter = new ChannelCenterKit(client);
    this.conversationCenter = new ConversationCenterKit(client);
    this.deviceCenter = new DeviceCenterKit(client);
    this.knowledgeCenter = new KnowledgeCenterKit(client);
    this.governanceCenter = new GovernanceCenterKit(client);
    this.salesCockpit = new SalesCockpitKit(client);
    this.salesKnowledge = new SalesKnowledgeKit(client);
    this.salesCoaching = new SalesCoachingKit(client);
  }
}

export function createQeeClawProductSDK(client: ProductSdkClient): QeeClawProductSDK {
  return new QeeClawProductSDK(client);
}

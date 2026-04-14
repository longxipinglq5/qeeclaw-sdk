import type {
  ProductConversationGroup,
  ProductConversationGroupMessage,
  ProductConversationHistoryMessage,
  ProductConversationHome,
  ProductConversationStats,
  ProductSdkClient,
} from "../types.js";

export class ConversationCenterKit {
  constructor(private readonly client: ProductSdkClient) {}

  loadHome(teamId: number, options?: { groupLimit?: number; historyLimit?: number }): Promise<ProductConversationHome> {
    return this.client.conversations.getHome(teamId, options?.groupLimit, options?.historyLimit);
  }

  getStats(teamId: number): Promise<ProductConversationStats> {
    return this.client.conversations.getStats(teamId);
  }

  listGroups(teamId: number, limit?: number): Promise<ProductConversationGroup[]> {
    return this.client.conversations.listGroups({ teamId, limit });
  }

  listGroupMessages(payload: { teamId: number; roomId: string; limit?: number }): Promise<ProductConversationGroupMessage[]> {
    return this.client.conversations.listGroupMessages(payload);
  }

  listHistory(payload: { teamId: number; channelId?: string; limit?: number }): Promise<ProductConversationHistoryMessage[]> {
    return this.client.conversations.listHistory(payload);
  }

  sendMessage(payload: {
    teamId: number;
    content: string;
    agentId?: number;
    channelId?: string;
    direction?: string;
  }): Promise<ProductConversationHistoryMessage> {
    return this.client.conversations.sendMessage(payload);
  }
}

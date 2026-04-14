import type { HttpClient } from "../client/http-client.js";

export interface ConversationStats {
  groupCount: number;
  msgCount: number;
  entityCount: number;
  historyCount?: number;
}

export interface ConversationGroup {
  roomId: string;
  roomName: string;
  lastActive?: string | null;
  msgCount: number;
  memberCount: number;
}

export interface ConversationEntity {
  type: string;
  value: string;
  confidence?: number;
}

export interface ConversationGroupMessage {
  id: number;
  senderName?: string | null;
  senderRole?: string | null;
  msgType?: string | null;
  content?: string | null;
  createdTime?: string | null;
  entities: ConversationEntity[];
}

export interface ConversationHistoryMessage {
  id: number;
  senderId?: number | null;
  agentId?: number | null;
  channelId?: string | null;
  direction: string;
  content?: string | null;
  createdTime?: string | null;
}

export interface ConversationHome {
  stats: ConversationStats;
  groups: ConversationGroup[];
  history: ConversationHistoryMessage[];
}

export interface ConversationGroupsParams {
  teamId: number;
  limit?: number;
}

export interface ConversationGroupMessagesParams {
  teamId: number;
  roomId: string;
  limit?: number;
}

export interface ConversationHistoryParams {
  teamId: number;
  channelId?: string;
  limit?: number;
}

export interface SendConversationMessageInput {
  teamId: number;
  content: string;
  agentId?: number;
  channelId?: string;
  direction?: string;
}

interface RawConversationStats {
  group_count: number;
  msg_count: number;
  entity_count: number;
  history_count?: number;
}

interface RawConversationGroup {
  room_id: string;
  room_name: string;
  last_active?: string | null;
  msg_count: number;
  member_count: number;
}

interface RawConversationEntity {
  type: string;
  value: string;
  confidence?: number;
}

interface RawConversationGroupMessage {
  id: number;
  sender_name?: string | null;
  sender_role?: string | null;
  msg_type?: string | null;
  content?: string | null;
  created_time?: string | null;
  entities?: RawConversationEntity[];
}

interface RawConversationHistoryMessage {
  id: number;
  sender_id?: number | null;
  agent_id?: number | null;
  channel_id?: string | null;
  direction: string;
  content?: string | null;
  created_time?: string | null;
}

interface RawConversationHome {
  stats: RawConversationStats;
  groups: RawConversationGroup[];
  history: RawConversationHistoryMessage[];
}

function mapStats(value: RawConversationStats): ConversationStats {
  return {
    groupCount: value.group_count,
    msgCount: value.msg_count,
    entityCount: value.entity_count,
    historyCount: value.history_count,
  };
}

function mapGroup(value: RawConversationGroup): ConversationGroup {
  return {
    roomId: value.room_id,
    roomName: value.room_name,
    lastActive: value.last_active,
    msgCount: value.msg_count,
    memberCount: value.member_count,
  };
}

function mapHistory(value: RawConversationHistoryMessage): ConversationHistoryMessage {
  return {
    id: value.id,
    senderId: value.sender_id,
    agentId: value.agent_id,
    channelId: value.channel_id,
    direction: value.direction,
    content: value.content,
    createdTime: value.created_time,
  };
}

function mapGroupMessage(value: RawConversationGroupMessage): ConversationGroupMessage {
  return {
    id: value.id,
    senderName: value.sender_name,
    senderRole: value.sender_role,
    msgType: value.msg_type,
    content: value.content,
    createdTime: value.created_time,
    entities: (value.entities ?? []).map((entity) => ({
      type: entity.type,
      value: entity.value,
      confidence: entity.confidence,
    })),
  };
}

export class ConversationsModule {
  constructor(private readonly http: HttpClient) {}

  async getHome(teamId: number, groupLimit = 10, historyLimit = 20): Promise<ConversationHome> {
    const result = await this.http.request<RawConversationHome>({
      method: "GET",
      path: "/api/platform/conversations",
      query: {
        team_id: teamId,
        group_limit: groupLimit,
        history_limit: historyLimit,
      },
    });
    return {
      stats: mapStats(result.stats),
      groups: result.groups.map(mapGroup),
      history: result.history.map(mapHistory),
    };
  }

  async getStats(teamId: number): Promise<ConversationStats> {
    const result = await this.http.request<RawConversationStats>({
      method: "GET",
      path: "/api/platform/conversations/stats",
      query: {
        team_id: teamId,
      },
    });
    return mapStats(result);
  }

  async listGroups(params: ConversationGroupsParams): Promise<ConversationGroup[]> {
    const result = await this.http.request<RawConversationGroup[]>({
      method: "GET",
      path: "/api/platform/conversations/groups",
      query: {
        team_id: params.teamId,
        limit: params.limit ?? 50,
      },
    });
    return result.map(mapGroup);
  }

  async listGroupMessages(params: ConversationGroupMessagesParams): Promise<ConversationGroupMessage[]> {
    const result = await this.http.request<RawConversationGroupMessage[]>({
      method: "GET",
      path: `/api/platform/conversations/groups/${encodeURIComponent(params.roomId)}/messages`,
      query: {
        team_id: params.teamId,
        limit: params.limit ?? 50,
      },
    });
    return result.map(mapGroupMessage);
  }

  async listHistory(params: ConversationHistoryParams): Promise<ConversationHistoryMessage[]> {
    const result = await this.http.request<RawConversationHistoryMessage[]>({
      method: "GET",
      path: "/api/platform/conversations/history",
      query: {
        team_id: params.teamId,
        channel_id: params.channelId,
        limit: params.limit ?? 50,
      },
    });
    return result.map(mapHistory);
  }

  async sendMessage(payload: SendConversationMessageInput): Promise<ConversationHistoryMessage> {
    const result = await this.http.request<RawConversationHistoryMessage>({
      method: "POST",
      path: "/api/platform/conversations/messages",
      body: {
        team_id: payload.teamId,
        content: payload.content,
        agent_id: payload.agentId,
        channel_id: payload.channelId,
        direction: payload.direction ?? "user_to_agent",
      },
    });
    return mapHistory(result);
  }
}

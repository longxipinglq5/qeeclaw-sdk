import type {
  ChannelAdapterStatus,
  ChannelAttachment,
  ChannelChatType,
  ChannelMessage,
  ChannelReply,
} from "../../types.js";
import type { ChannelAdapter, ChannelAdapterContext } from "../types.js";

export type WechatPersonalSendContext = {
  channel?: string;
  to?: string;
  accountId?: string;
  sessionKey?: string;
  requestId?: string;
};

export type WechatPersonalIncomingPayload = {
  id?: string;
  eventId?: string;
  event_id?: string;
  messageId?: string;
  message_id?: string;
  from?: string;
  fromUser?: string;
  from_user?: string;
  userId?: string;
  user_id?: string;
  externalUserId?: string;
  external_user_id?: string;
  chatId?: string;
  chat_id?: string;
  roomId?: string;
  room_id?: string;
  chatType?: string;
  chat_type?: string;
  text?: string;
  content?: string;
  message?: string;
  senderName?: string;
  sender_name?: string;
  attachments?: ChannelAttachment[];
  requestId?: string;
  __sidecarRequestId?: string;
  send?: WechatPersonalSendContext & {
    account_id?: string;
    session_key?: string;
  };
  [key: string]: unknown;
};

export type WechatPersonalSendPayload = {
  to: string;
  message?: string;
  attachments?: ChannelAttachment[];
  channel: string;
  accountId?: string;
  sessionKey?: string;
  requestId?: string;
};

export interface WechatPersonalLocalTransport {
  start(handlers: { onMessage(payload: WechatPersonalIncomingPayload): Promise<void> }): Promise<void>;
  stop(): Promise<void>;
  sendMessage(payload: WechatPersonalSendPayload): Promise<void>;
}

function firstString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return undefined;
}

function normalizeChatType(value: unknown): ChannelChatType {
  const normalized = typeof value === "string" ? value.trim().toLowerCase() : "";
  return normalized === "group" || normalized === "room" ? "group" : "dm";
}

function normalizeText(text: string): string {
  return text.replace(/^@\S+\s*/, "").replace(/@\S+\s?/g, "").trim();
}

function extractSendContext(payload: WechatPersonalIncomingPayload, senderId: string): Required<WechatPersonalSendContext> {
  const send = payload.send || {};
  return {
    channel: firstString(send.channel, payload.channel) || "wechat",
    to: firstString(send.to, payload.to, senderId) || senderId,
    accountId: firstString(send.accountId, send.account_id, payload.accountId, payload.account_id) || "",
    sessionKey: firstString(send.sessionKey, send.session_key, payload.sessionKey, payload.session_key) || "",
    requestId: firstString(send.requestId, payload.__sidecarRequestId, payload.requestId) || "",
  };
}

export class WechatPersonalLocalAdapter implements ChannelAdapter {
  readonly channel = "wechat_personal" as const;
  private context?: ChannelAdapterContext;
  private running = false;
  private lastMessageAt?: string;
  private lastError?: string;

  constructor(private readonly transport: WechatPersonalLocalTransport) {}

  async start(context: ChannelAdapterContext): Promise<void> {
    this.context = context;
    this.running = true;
    this.lastError = undefined;
    await this.transport.start({
      onMessage: (payload) => this.handleIncoming(payload),
    });
  }

  async stop(): Promise<void> {
    await this.transport.stop();
    this.running = false;
  }

  async handleIncoming(payload: WechatPersonalIncomingPayload): Promise<void> {
    if (!this.context || !this.running) {
      throw new Error("WeChat personal local adapter is not running");
    }

    const senderId = firstString(
      payload.externalUserId,
      payload.external_user_id,
      payload.from,
      payload.fromUser,
      payload.from_user,
      payload.userId,
      payload.user_id,
    );
    const messageId = firstString(payload.messageId, payload.message_id, payload.eventId, payload.event_id, payload.id);
    if (!senderId || !messageId) {
      this.lastError = "WeChat personal payload missing senderId or messageId";
      return;
    }

    const text = normalizeText(firstString(payload.text, payload.content, payload.message) || "");
    const attachments = Array.isArray(payload.attachments) ? payload.attachments : [];
    if (!text && attachments.length === 0) {
      return;
    }

    const chatId = firstString(payload.chatId, payload.chat_id, payload.roomId, payload.room_id, senderId) || senderId;
    const sendContext = extractSendContext(payload, senderId);
    const receivedAt = new Date().toISOString();
    this.lastMessageAt = receivedAt;

    try {
      await this.context.emitMessage({
        channel: this.channel,
        messageId,
        chatId,
        chatType: normalizeChatType(firstString(payload.chatType, payload.chat_type)),
        senderId,
        senderName: firstString(payload.senderName, payload.sender_name),
        text,
        attachments,
        rawMeta: {
          payload: payload as Record<string, unknown>,
          sendContext,
        },
        receivedAt,
      });
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : String(error);
      throw error;
    }
  }

  async sendReply(message: ChannelMessage, reply: ChannelReply): Promise<void> {
    if (!reply.text?.trim() && !(reply.attachments || []).length) {
      return;
    }

    const sendContext = (message.rawMeta?.sendContext || {}) as Partial<WechatPersonalSendContext>;
    await this.transport.sendMessage({
      to: sendContext.to || message.senderId,
      message: reply.text,
      attachments: reply.attachments,
      channel: sendContext.channel || "wechat",
      accountId: sendContext.accountId,
      sessionKey: sendContext.sessionKey,
      requestId: sendContext.requestId,
    });
  }

  getStatus(): ChannelAdapterStatus {
    return {
      channel: this.channel,
      configured: true,
      running: this.running,
      mode: "local_bridge",
      lastMessageAt: this.lastMessageAt,
      lastError: this.lastError,
    };
  }
}

export class MemoryWechatPersonalTransport implements WechatPersonalLocalTransport {
  private handler?: (payload: WechatPersonalIncomingPayload) => Promise<void>;
  private readonly pendingReplies = new Map<string, WechatPersonalSendPayload[]>();
  running = false;
  readonly sentMessages: WechatPersonalSendPayload[] = [];

  async start(handlers: { onMessage(payload: WechatPersonalIncomingPayload): Promise<void> }): Promise<void> {
    this.handler = handlers.onMessage;
    this.running = true;
  }

  async stop(): Promise<void> {
    this.running = false;
  }

  async emit(payload: WechatPersonalIncomingPayload): Promise<void> {
    if (!this.handler || !this.running) {
      throw new Error("WeChat personal transport is not running");
    }
    await this.handler(payload);
  }

  async emitAndCollectReplies(payload: WechatPersonalIncomingPayload): Promise<WechatPersonalSendPayload[]> {
    const requestId =
      firstString(payload.__sidecarRequestId, payload.requestId, payload.send?.requestId) ||
      `wechat-personal-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const replies: WechatPersonalSendPayload[] = [];
    this.pendingReplies.set(requestId, replies);
    try {
      await this.emit({
        ...payload,
        __sidecarRequestId: requestId,
        send: {
          ...(payload.send || {}),
          requestId,
        },
      });
      return replies;
    } finally {
      this.pendingReplies.delete(requestId);
    }
  }

  async sendMessage(payload: WechatPersonalSendPayload): Promise<void> {
    if (payload.requestId && this.pendingReplies.has(payload.requestId)) {
      this.pendingReplies.get(payload.requestId)?.push(payload);
      return;
    }
    this.sentMessages.push(payload);
  }
}

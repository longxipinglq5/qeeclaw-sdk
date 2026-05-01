import type {
  ChannelAdapterStatus,
  ChannelAttachment,
  ChannelChatType,
  ChannelMessage,
  ChannelReply,
} from "../../types.js";
import type { ChannelAdapter, ChannelAdapterContext } from "../types.js";

type FeishuSenderId = {
  open_id?: string;
  user_id?: string;
  union_id?: string;
};

type FeishuMessageMention = {
  key?: string;
  name?: string;
  id?: FeishuSenderId;
};

type FeishuMessageEvent = {
  sender?: {
    sender_id?: FeishuSenderId;
    sender_type?: string;
  };
  message?: {
    message_id?: string;
    chat_id?: string;
    chat_type?: string;
    message_type?: string;
    content?: string;
    mentions?: FeishuMessageMention[];
  };
};

export type FeishuEventEnvelope = {
  header?: {
    event_type?: string;
  };
  event?: FeishuMessageEvent;
};

export type FeishuSendPayload = {
  receiveId: string;
  receiveIdType: "open_id" | "chat_id";
  msgType: "text" | "image" | "file";
  content: string;
};

export interface FeishuLocalTransport {
  start(handlers: { onEvent(event: FeishuEventEnvelope): Promise<void> }): Promise<void>;
  stop(): Promise<void>;
  sendMessage(payload: FeishuSendPayload): Promise<void>;
}

type FeishuLocalAdapterOptions = {
  transport: FeishuLocalTransport;
  requireMentionInGroup?: boolean;
};

function safeJsonParse(value: string | undefined): Record<string, unknown> {
  if (!value?.trim()) {
    return {};
  }
  try {
    const parsed = JSON.parse(value) as unknown;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function firstString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return undefined;
}

function normalizeChatType(value: string | undefined): ChannelChatType {
  return value === "group" ? "group" : "dm";
}

function stripMentions(text: string, mentions: FeishuMessageMention[] | undefined): string {
  let cleaned = text;
  for (const mention of mentions || []) {
    for (const token of [mention.key, mention.name]) {
      if (token?.trim()) {
        cleaned = cleaned.replaceAll(token, "");
      }
    }
  }
  return cleaned.replace(/@\S+\s?/g, "").trim();
}

function buildAttachments(messageType: string | undefined, content: Record<string, unknown>): ChannelAttachment[] {
  if (messageType === "image") {
    const imageKey = firstString(content.image_key);
    return imageKey
      ? [
          {
            type: "image",
            name: `${imageKey}.png`,
            remoteUrl: `feishu://image/${imageKey}`,
            rawMeta: { imageKey },
          },
        ]
      : [];
  }

  if (messageType === "file") {
    const fileKey = firstString(content.file_key);
    const fileName = firstString(content.file_name) || (fileKey ? `${fileKey}.file` : undefined);
    return fileKey
      ? [
          {
            type: "file",
            name: fileName,
            remoteUrl: `feishu://file/${fileKey}`,
            rawMeta: { fileKey },
          },
        ]
      : [];
  }

  return [];
}

export class FeishuLocalAdapter implements ChannelAdapter {
  readonly channel = "feishu" as const;
  private context?: ChannelAdapterContext;
  private running = false;
  private lastMessageAt?: string;
  private lastError?: string;

  constructor(private readonly options: FeishuLocalAdapterOptions) {}

  async start(context: ChannelAdapterContext): Promise<void> {
    this.context = context;
    this.running = true;
    this.lastError = undefined;
    await this.options.transport.start({
      onEvent: (event) => this.handleEvent(event),
    });
  }

  async stop(): Promise<void> {
    await this.options.transport.stop();
    this.running = false;
  }

  async handleEvent(envelope: FeishuEventEnvelope): Promise<void> {
    if (!this.context || !this.running) {
      throw new Error("Feishu local adapter is not running");
    }

    if (envelope.header?.event_type !== "im.message.receive_v1") {
      return;
    }

    const event = envelope.event || {};
    const message = event.message || {};
    const senderId = firstString(
      event.sender?.sender_id?.open_id,
      event.sender?.sender_id?.user_id,
      event.sender?.sender_id?.union_id,
    );
    const messageId = firstString(message.message_id);
    const chatId = firstString(message.chat_id);
    if (!senderId || !messageId || !chatId) {
      this.lastError = "Feishu event missing senderId, messageId, or chatId";
      return;
    }

    const chatType = normalizeChatType(message.chat_type);
    const content = safeJsonParse(message.content);
    const rawText = firstString(content.text) || "";
    const text = stripMentions(rawText, message.mentions);
    const attachments = buildAttachments(message.message_type, content);
    const hasMention = Boolean(message.mentions?.length);
    if (chatType === "group" && this.options.requireMentionInGroup !== false && !hasMention) {
      return;
    }
    if (!text && attachments.length === 0) {
      return;
    }

    const receivedAt = new Date().toISOString();
    this.lastMessageAt = receivedAt;
    const channelMessage: ChannelMessage = {
      channel: this.channel,
      messageId,
      chatId,
      chatType,
      senderId,
      text,
      attachments,
      rawMeta: envelope as unknown as Record<string, unknown>,
      receivedAt,
    };

    try {
      await this.context.emitMessage(channelMessage);
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : String(error);
      throw error;
    }
  }

  async sendReply(message: ChannelMessage, reply: ChannelReply): Promise<void> {
    const receiveId = message.chatType === "group" ? message.chatId : message.senderId;
    const receiveIdType = message.chatType === "group" ? "chat_id" : "open_id";
    if (reply.text?.trim()) {
      await this.options.transport.sendMessage({
        receiveId,
        receiveIdType,
        msgType: "text",
        content: JSON.stringify({ text: reply.text }),
      });
    }

    for (const attachment of reply.attachments || []) {
      const key = firstString(attachment.rawMeta?.imageKey, attachment.rawMeta?.fileKey, attachment.remoteUrl);
      if (!key) {
        continue;
      }
      if (attachment.type === "image") {
        await this.options.transport.sendMessage({
          receiveId,
          receiveIdType,
          msgType: "image",
          content: JSON.stringify({ image_key: key.replace(/^feishu:\/\/image\//, "") }),
        });
      } else {
        await this.options.transport.sendMessage({
          receiveId,
          receiveIdType,
          msgType: "file",
          content: JSON.stringify({ file_key: key.replace(/^feishu:\/\/file\//, "") }),
        });
      }
    }
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

import { readFile } from "node:fs/promises";

import type {
  ChannelAdapterStatus,
  ChannelAttachment,
  ChannelAttachmentType,
  ChannelChatType,
  ChannelMessage,
  ChannelReply,
} from "../../types.js";
import type { ChannelAdapter, ChannelAdapterContext } from "../types.js";

export type WechatWorkIncomingPayload = {
  MsgId?: string;
  msgId?: string;
  msg_id?: string;
  FromUserName?: string;
  fromUserName?: string;
  from_user_name?: string;
  ToUserName?: string;
  toUserName?: string;
  to_user_name?: string;
  AgentID?: string;
  agentId?: string;
  agent_id?: string;
  ChatId?: string;
  chatId?: string;
  chat_id?: string;
  MsgType?: string;
  msgType?: string;
  msg_type?: string;
  Content?: string;
  content?: string;
  text?: string;
  MediaId?: string;
  mediaId?: string;
  media_id?: string;
  FileName?: string;
  fileName?: string;
  file_name?: string;
  PicUrl?: string;
  picUrl?: string;
  pic_url?: string;
  attachments?: ChannelAttachment[];
  [key: string]: unknown;
};

export type WechatWorkSendPayload = {
  to: string;
  message?: string;
  attachments?: ChannelAttachment[];
};

export interface WechatWorkLocalTransport {
  start(handlers: { onMessage(payload: WechatWorkIncomingPayload): Promise<void> }): Promise<void>;
  stop(): Promise<void>;
  sendMessage(payload: WechatWorkSendPayload): Promise<void>;
}

type WechatWorkRestTransportOptions = {
  corpId: string;
  corpSecret: string;
  agentId: string;
  apiBaseUrl?: string;
  fetchImpl?: typeof fetch;
};

type WechatWorkTokenCache = {
  token?: string;
  expiresAtMs?: number;
};

function firstString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      return String(value);
    }
  }
  return undefined;
}

function normalizeText(text: string): string {
  return text.replace(/^@\S+\s*/, "").replace(/@\S+\s?/g, "").trim();
}

function normalizeMsgType(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function normalizeChatType(payload: WechatWorkIncomingPayload): ChannelChatType {
  return firstString(payload.ChatId, payload.chatId, payload.chat_id) ? "group" : "dm";
}

function mapAttachmentType(msgType: string): ChannelAttachmentType {
  if (msgType === "image") {
    return "image";
  }
  if (msgType === "voice") {
    return "voice";
  }
  if (msgType === "video") {
    return "video";
  }
  return "file";
}

function fallbackFileName(attachment: ChannelAttachment): string {
  if (attachment.name?.trim()) {
    return attachment.name.trim();
  }
  if (attachment.localPath?.trim()) {
    const parts = attachment.localPath.split(/[\\/]/);
    return parts[parts.length - 1] || "qeeclaw-file";
  }
  return attachment.type === "image" ? "qeeclaw-image.png" : "qeeclaw-file";
}

function splitLongText(text: string, maxBytes = 2000): string[] {
  const encoder = new TextEncoder();
  if (encoder.encode(text).length <= maxBytes) {
    return [text];
  }

  const segments: string[] = [];
  let remaining = text;
  while (remaining) {
    if (encoder.encode(remaining).length <= maxBytes) {
      segments.push(remaining);
      break;
    }

    let safe = "";
    for (const char of remaining) {
      if (encoder.encode(safe + char).length > maxBytes) {
        break;
      }
      safe += char;
    }
    let cutAt = safe.length;
    for (const separator of ["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? "]) {
      const index = safe.lastIndexOf(separator);
      if (index > safe.length / 4) {
        cutAt = index + separator.length;
        break;
      }
    }
    const segment = remaining.slice(0, cutAt).trim();
    if (segment) {
      segments.push(segment);
    }
    remaining = remaining.slice(cutAt).trim();
  }
  return segments.length ? segments : [text];
}

function buildIncomingAttachments(payload: WechatWorkIncomingPayload): ChannelAttachment[] {
  if (Array.isArray(payload.attachments)) {
    return payload.attachments;
  }

  const msgType = normalizeMsgType(firstString(payload.MsgType, payload.msgType, payload.msg_type));
  if (!msgType || msgType === "text") {
    return [];
  }

  const mediaId = firstString(payload.MediaId, payload.mediaId, payload.media_id);
  const picUrl = firstString(payload.PicUrl, payload.picUrl, payload.pic_url);
  if (!mediaId && !picUrl) {
    return [];
  }

  const name = firstString(payload.FileName, payload.fileName, payload.file_name) || (mediaId ? `${mediaId}.file` : "wechat-work-media");
  return [
    {
      type: mapAttachmentType(msgType),
      name,
      remoteUrl: mediaId ? `wechat-work://media/${mediaId}` : picUrl,
      rawMeta: {
        mediaId,
        msgType,
        picUrl,
      },
    },
  ];
}

export class WechatWorkLocalAdapter implements ChannelAdapter {
  readonly channel = "wechat_work" as const;
  private context?: ChannelAdapterContext;
  private running = false;
  private lastMessageAt?: string;
  private lastError?: string;

  constructor(private readonly transport: WechatWorkLocalTransport) {}

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

  async handleIncoming(payload: WechatWorkIncomingPayload): Promise<void> {
    if (!this.context || !this.running) {
      throw new Error("WeChat Work local adapter is not running");
    }

    const senderId = firstString(payload.FromUserName, payload.fromUserName, payload.from_user_name);
    const messageId = firstString(payload.MsgId, payload.msgId, payload.msg_id);
    if (!senderId || !messageId) {
      this.lastError = "WeChat Work payload missing senderId or messageId";
      return;
    }

    const rawText = firstString(payload.Content, payload.content, payload.text) || "";
    const text = normalizeText(rawText);
    const attachments = buildIncomingAttachments(payload);
    if (!text && attachments.length === 0) {
      return;
    }

    const chatId = firstString(payload.ChatId, payload.chatId, payload.chat_id, senderId) || senderId;
    const receivedAt = new Date().toISOString();
    this.lastMessageAt = receivedAt;

    try {
      await this.context.emitMessage({
        channel: this.channel,
        messageId,
        chatId,
        chatType: normalizeChatType(payload),
        senderId,
        text,
        attachments,
        rawMeta: payload as Record<string, unknown>,
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
    await this.transport.sendMessage({
      to: message.senderId,
      message: reply.text,
      attachments: reply.attachments,
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

export class WechatWorkRestTransport implements WechatWorkLocalTransport {
  private handler?: (payload: WechatWorkIncomingPayload) => Promise<void>;
  private readonly tokenCache: WechatWorkTokenCache = {};
  running = false;

  constructor(private readonly options: WechatWorkRestTransportOptions) {}

  async start(handlers: { onMessage(payload: WechatWorkIncomingPayload): Promise<void> }): Promise<void> {
    this.handler = handlers.onMessage;
    this.running = true;
  }

  async stop(): Promise<void> {
    this.running = false;
  }

  async emit(payload: WechatWorkIncomingPayload): Promise<void> {
    if (!this.handler || !this.running) {
      throw new Error("WeChat Work transport is not running");
    }
    await this.handler(payload);
  }

  async sendMessage(payload: WechatWorkSendPayload): Promise<void> {
    const text = payload.message?.trim();
    if (text) {
      for (const segment of splitLongText(text)) {
        await this.sendText(payload.to, segment);
      }
    }

    for (const attachment of payload.attachments || []) {
      await this.sendAttachment(payload.to, attachment);
    }
  }

  private get apiBaseUrl(): string {
    return (this.options.apiBaseUrl || "https://qyapi.weixin.qq.com").replace(/\/+$/, "");
  }

  private get fetchImpl(): typeof fetch {
    return this.options.fetchImpl || fetch;
  }

  private async getAccessToken(): Promise<string> {
    const now = Date.now();
    if (this.tokenCache.token && this.tokenCache.expiresAtMs && this.tokenCache.expiresAtMs > now) {
      return this.tokenCache.token;
    }

    const url = new URL("/cgi-bin/gettoken", this.apiBaseUrl);
    url.searchParams.set("corpid", this.options.corpId);
    url.searchParams.set("corpsecret", this.options.corpSecret);
    const response = await this.fetchImpl(url);
    const data = (await response.json()) as { errcode?: number; errmsg?: string; access_token?: string; expires_in?: number };
    if (!response.ok || data.errcode !== 0 || !data.access_token) {
      throw new Error(data.errmsg || `Failed to get WeChat Work access token: ${response.status}`);
    }

    this.tokenCache.token = data.access_token;
    this.tokenCache.expiresAtMs = now + Math.max(60, data.expires_in || 7200) * 1000 - 60_000;
    return data.access_token;
  }

  private async postWechatApi(pathname: string, payload: unknown, query: Record<string, string> = {}): Promise<Record<string, unknown>> {
    const accessToken = await this.getAccessToken();
    const url = new URL(pathname, this.apiBaseUrl);
    url.searchParams.set("access_token", accessToken);
    for (const [key, value] of Object.entries(query)) {
      url.searchParams.set(key, value);
    }

    const response = await this.fetchImpl(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = (await response.json()) as Record<string, unknown>;
    if (!response.ok || data.errcode !== 0) {
      throw new Error(firstString(data.errmsg) || `WeChat Work API request failed: ${response.status}`);
    }
    return data;
  }

  private async sendText(to: string, content: string): Promise<void> {
    await this.postWechatApi("/cgi-bin/message/send", {
      touser: to,
      msgtype: "text",
      agentid: this.options.agentId,
      text: { content },
    });
  }

  private async uploadMedia(attachment: ChannelAttachment): Promise<string | undefined> {
    const existingMediaId = firstString(attachment.rawMeta?.mediaId, attachment.remoteUrl?.replace(/^wechat-work:\/\/media\//, ""));
    if (existingMediaId) {
      return existingMediaId;
    }

    let bytes: Buffer | undefined;
    if (attachment.localPath?.trim()) {
      bytes = await readFile(attachment.localPath);
    } else if (attachment.dataBase64?.trim()) {
      bytes = Buffer.from(attachment.dataBase64, "base64");
    }
    if (!bytes) {
      return undefined;
    }

    const accessToken = await this.getAccessToken();
    const mediaType = attachment.type === "image" ? "image" : "file";
    const url = new URL("/cgi-bin/media/upload", this.apiBaseUrl);
    url.searchParams.set("access_token", accessToken);
    url.searchParams.set("type", mediaType);

    const form = new FormData();
    form.append("media", new Blob([bytes as unknown as BlobPart]), fallbackFileName(attachment));
    const response = await this.fetchImpl(url, {
      method: "POST",
      body: form,
    });
    const data = (await response.json()) as { errcode?: number; errmsg?: string; media_id?: string };
    if (!response.ok || data.errcode !== 0 || !data.media_id) {
      throw new Error(data.errmsg || `WeChat Work media upload failed: ${response.status}`);
    }
    return data.media_id;
  }

  private async sendAttachment(to: string, attachment: ChannelAttachment): Promise<void> {
    const mediaId = await this.uploadMedia(attachment);
    if (!mediaId) {
      return;
    }
    const msgtype = attachment.type === "image" ? "image" : "file";
    await this.postWechatApi("/cgi-bin/message/send", {
      touser: to,
      msgtype,
      agentid: this.options.agentId,
      [msgtype]: { media_id: mediaId },
    });
  }
}

export class MemoryWechatWorkTransport implements WechatWorkLocalTransport {
  private handler?: (payload: WechatWorkIncomingPayload) => Promise<void>;
  running = false;
  readonly sentMessages: WechatWorkSendPayload[] = [];

  async start(handlers: { onMessage(payload: WechatWorkIncomingPayload): Promise<void> }): Promise<void> {
    this.handler = handlers.onMessage;
    this.running = true;
  }

  async stop(): Promise<void> {
    this.running = false;
  }

  async emit(payload: WechatWorkIncomingPayload): Promise<void> {
    if (!this.handler || !this.running) {
      throw new Error("WeChat Work transport is not running");
    }
    await this.handler(payload);
  }

  async sendMessage(payload: WechatWorkSendPayload): Promise<void> {
    this.sentMessages.push(payload);
  }
}

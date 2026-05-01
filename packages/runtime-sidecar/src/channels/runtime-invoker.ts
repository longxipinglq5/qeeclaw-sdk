import crypto from "node:crypto";
import { access, readFile } from "node:fs/promises";
import os from "node:os";

import type { ChannelMessage, ChannelReply } from "../types.js";
import type { ChannelRuntimeInvoker } from "./types.js";

export type RuntimeInvokeHandler = (message: ChannelMessage) => Promise<ChannelReply> | ChannelReply;

type GatewayFrame = Record<string, unknown>;

type GatewayRuntimeInvokerOptions = {
  wsUrl: string;
  authToken?: string;
  authPassword?: string;
  authTokenProvider?: () => Promise<string | undefined> | string | undefined;
  connectTimeoutMs?: number;
  responseTimeoutMs?: number;
  chatTimeoutMs?: number;
  clientId?: string;
  clientVersion?: string;
  webSocketFactory?: (url: string) => MinimalWebSocket | Promise<MinimalWebSocket>;
};

type PendingRequest = {
  method: string;
  resolve(value: GatewayFrame): void;
  reject(error: Error): void;
  timer: ReturnType<typeof setTimeout>;
};

type PendingChatRun = {
  resolve(reply: ChannelReply): void;
  reject(error: Error): void;
  timer: ReturnType<typeof setTimeout>;
};

type MinimalWebSocket = {
  readyState: number;
  send(data: string): void;
  close?(code?: number, reason?: string): void;
  addEventListener?(event: "open" | "message" | "close" | "error", handler: (event: unknown) => void): void;
  on?(event: "open" | "message" | "close" | "error", handler: (...args: unknown[]) => void): void;
};

type GatewayAttachmentInput = {
  type?: string;
  mimeType?: string;
  fileName?: string;
  content?: string;
};

const WEBSOCKET_OPEN = 1;
const DEFAULT_CONNECT_TIMEOUT_MS = 10_000;
const DEFAULT_RESPONSE_TIMEOUT_MS = 30_000;
const DEFAULT_CHAT_TIMEOUT_MS = 180_000;
const MAX_GATEWAY_IMAGE_BYTES = 5_000_000;

export class CallbackRuntimeInvoker implements ChannelRuntimeInvoker {
  constructor(private readonly handler: RuntimeInvokeHandler) {}

  async invoke(message: ChannelMessage): Promise<ChannelReply> {
    return this.handler(message);
  }
}

export class EchoRuntimeInvoker implements ChannelRuntimeInvoker {
  async invoke(message: ChannelMessage): Promise<ChannelReply> {
    const text = message.text?.trim() || "(empty message)";
    return {
      text: `[local-bridge:${message.channel}] ${text}`,
    };
  }
}

export class GatewayRuntimeInvoker implements ChannelRuntimeInvoker {
  private socket?: MinimalWebSocket;
  private connectPromise?: Promise<void>;
  private connected = false;
  private readonly pendingRequests = new Map<string, PendingRequest>();
  private readonly pendingChatRuns = new Map<string, PendingChatRun>();

  constructor(private readonly options: GatewayRuntimeInvokerOptions) {}

  async invoke(message: ChannelMessage): Promise<ChannelReply> {
    try {
      return await this.invokeOrThrow(message);
    } catch (error) {
      return {
        text: `本地 HubOS 调用失败：${error instanceof Error ? error.message : String(error)}`,
      };
    }
  }

  private async invokeOrThrow(message: ChannelMessage): Promise<ChannelReply> {
    const runId = `channel-${message.channel}-${message.messageId}-${crypto.randomUUID()}`;
    await this.ensureConnected();
    const chatFinal = this.waitForChatFinal(runId);
    try {
      await this.sendRequest("chat.send", {
        sessionKey: buildChannelSessionKey(message),
        message: await buildGatewayMessage(message),
        attachments: await buildGatewayAttachments(message),
        deliver: false,
        timeoutMs: this.options.chatTimeoutMs ?? DEFAULT_CHAT_TIMEOUT_MS,
        idempotencyKey: runId,
      });
      return await chatFinal;
    } catch (error) {
      this.clearPendingChat(runId);
      throw error;
    }
  }

  private async ensureConnected(): Promise<void> {
    if (this.connected && this.socket?.readyState === WEBSOCKET_OPEN) {
      return;
    }
    if (this.connectPromise) {
      return this.connectPromise;
    }

    this.connectPromise = this.connectOnce().finally(() => {
      this.connectPromise = undefined;
    });
    return this.connectPromise;
  }

  private async connectOnce(): Promise<void> {
    const socket = await this.createSocket();
    this.socket = socket;
    this.connected = false;

    await new Promise<void>((resolve, reject) => {
      let challengeReceived = false;
      let connectSent = false;
      let finished = false;
      const connectTimeout = setTimeout(() => {
        fail(new Error(`OpenClaw Gateway connect timeout after ${this.options.connectTimeoutMs ?? DEFAULT_CONNECT_TIMEOUT_MS}ms`));
      }, this.options.connectTimeoutMs ?? DEFAULT_CONNECT_TIMEOUT_MS);

      const cleanup = () => {
        clearTimeout(connectTimeout);
      };
      const fail = (error: Error) => {
        if (finished) {
          return;
        }
        finished = true;
        cleanup();
        this.closeSocket(error.message);
        reject(error);
      };
      const succeed = () => {
        if (finished) {
          return;
        }
        finished = true;
        cleanup();
        this.connected = true;
        resolve();
      };
      const sendConnect = async (nonce?: string) => {
        if (connectSent) {
          return;
        }
        connectSent = true;
        try {
          const result = await this.sendHandshakeConnect(nonce);
          if (result) {
            succeed();
          }
        } catch (error) {
          fail(error instanceof Error ? error : new Error(String(error)));
        }
      };

      this.attachSocketHandler(socket, "open", () => {
        setTimeout(() => {
          if (!challengeReceived) {
            void sendConnect();
          }
        }, 1500);
      });
      this.attachSocketHandler(socket, "message", (event) => {
        const frame = parseGatewayFrame(event);
        if (!frame) {
          return;
        }
        this.handleGatewayFrame(frame);
        if (frame.type === "event" && frame.event === "connect.challenge") {
          challengeReceived = true;
          const payload = asRecord(frame.payload);
          void sendConnect(typeof payload?.nonce === "string" ? payload.nonce : undefined);
        }
      });
      this.attachSocketHandler(socket, "close", (_event) => {
        this.connected = false;
        this.rejectAllPending(new Error("OpenClaw Gateway connection closed"));
        if (!finished) {
          fail(new Error("OpenClaw Gateway connection closed before handshake completed"));
        }
      });
      this.attachSocketHandler(socket, "error", (event) => {
        const message = event instanceof Error ? event.message : "OpenClaw Gateway connection error";
        if (!finished) {
          fail(new Error(message));
        }
      });
    });
  }

  private async createSocket(): Promise<MinimalWebSocket> {
    if (this.options.webSocketFactory) {
      return this.options.webSocketFactory(this.options.wsUrl);
    }
    if (typeof globalThis.WebSocket === "function") {
      return new globalThis.WebSocket(this.options.wsUrl) as unknown as MinimalWebSocket;
    }

    const dynamicImport = new Function("specifier", "return import(specifier)") as (specifier: string) => Promise<unknown>;
    const mod = (await dynamicImport("ws")) as Record<string, unknown>;
    const WebSocketCtor = (mod.WebSocket || mod.default) as
      | (new (url: string, options?: { headers?: Record<string, string> }) => MinimalWebSocket)
      | undefined;
    if (!WebSocketCtor) {
      throw new Error("No WebSocket implementation available. Use Node 20+ or install optional dependency `ws`.");
    }
    return new WebSocketCtor(this.options.wsUrl, {
      headers: {
        Origin: "http://localhost:18789",
      },
    });
  }

  private attachSocketHandler(socket: MinimalWebSocket, event: "open" | "message" | "close" | "error", handler: (event: unknown) => void): void {
    if (socket.addEventListener) {
      socket.addEventListener(event, handler);
      return;
    }
    socket.on?.(event, (...args: unknown[]) => handler(args[0]));
  }

  private async sendHandshakeConnect(nonce?: string): Promise<boolean> {
    const scopes = ["operator.admin"];
    const auth: Record<string, string> = {};
    const token = (this.options.authToken || (await this.options.authTokenProvider?.()) || "").trim();
    const password = (this.options.authPassword || "").trim();
    if (token) {
      auth.token = token;
    } else if (password) {
      auth.password = password;
    }

    await this.sendRequest(
      "connect",
      {
        minProtocol: 3,
        maxProtocol: 3,
        client: {
          id: this.options.clientId || "qeeclaw-runtime-sidecar",
          version: this.options.clientVersion || "0.1.0",
          platform: os.platform(),
          deviceFamily: "desktop",
          mode: "backend",
        },
        role: "operator",
        scopes,
        caps: [],
        ...(Object.keys(auth).length ? { auth } : {}),
        ...(nonce ? { nonce } : {}),
      },
      { skipConnect: true },
    );
    return true;
  }

  private async sendRequest(method: string, params: GatewayFrame, options: { skipConnect?: boolean } = {}): Promise<GatewayFrame> {
    if (!options.skipConnect) {
      await this.ensureConnected();
    }
    const socket = this.socket;
    if (!socket || socket.readyState !== WEBSOCKET_OPEN) {
      throw new Error("OpenClaw Gateway is not connected");
    }

    const id = crypto.randomUUID();
    const responseTimeoutMs = method === "connect" ? this.options.connectTimeoutMs ?? DEFAULT_CONNECT_TIMEOUT_MS : this.options.responseTimeoutMs ?? DEFAULT_RESPONSE_TIMEOUT_MS;
    const response = new Promise<GatewayFrame>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`${method} timed out after ${responseTimeoutMs}ms`));
      }, responseTimeoutMs);
      this.pendingRequests.set(id, { method, resolve, reject, timer });
    });
    socket.send(JSON.stringify({ type: "req", id, method, params }));
    return response;
  }

  private waitForChatFinal(runId: string): Promise<ChannelReply> {
    const timeoutMs = this.options.chatTimeoutMs ?? DEFAULT_CHAT_TIMEOUT_MS;
    return new Promise<ChannelReply>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingChatRuns.delete(runId);
        reject(new Error(`chat.send final response timed out after ${timeoutMs}ms`));
      }, timeoutMs);
      this.pendingChatRuns.set(runId, { resolve, reject, timer });
    });
  }

  private handleGatewayFrame(frame: GatewayFrame): void {
    if (frame.type === "res" && typeof frame.id === "string") {
      const pending = this.pendingRequests.get(frame.id);
      if (pending) {
        this.pendingRequests.delete(frame.id);
        clearTimeout(pending.timer);
        if (frame.ok === false) {
          pending.reject(new Error(formatGatewayError(frame.error) || `${pending.method} failed`));
        } else {
          pending.resolve(extractGatewayPayload(frame));
        }
      }
      return;
    }

    if (frame.type === "event" && frame.event === "chat") {
      const payload = asRecord(frame.payload);
      const runId = typeof payload?.runId === "string" ? payload.runId : "";
      if (!runId || (payload?.state !== "final" && payload?.state !== "error")) {
        return;
      }
      const pending = this.pendingChatRuns.get(runId);
      if (!pending) {
        return;
      }
      this.pendingChatRuns.delete(runId);
      clearTimeout(pending.timer);
      if (payload.state === "error") {
        pending.resolve({
          text: typeof payload.errorMessage === "string" && payload.errorMessage.trim() ? payload.errorMessage.trim() : "OpenClaw execution failed",
        });
        return;
      }
      const text = collectVisibleTextParts(asRecord(payload.message)?.content ?? payload.message ?? [])
        .filter(Boolean)
        .join("\n")
        .trim();
      void buildReplyAttachmentsFromText(text).then((attachments) => {
        pending.resolve({
          text: text || "已处理完成，但未生成可发送文本。请换一种说法重试。",
          attachments: attachments.length ? attachments : undefined,
        });
      }, pending.reject);
    }
  }

  private clearPendingChat(runId: string): void {
    const pending = this.pendingChatRuns.get(runId);
    if (!pending) {
      return;
    }
    this.pendingChatRuns.delete(runId);
    clearTimeout(pending.timer);
  }

  private rejectAllPending(error: Error): void {
    for (const [id, pending] of this.pendingRequests.entries()) {
      clearTimeout(pending.timer);
      pending.reject(error);
      this.pendingRequests.delete(id);
    }
    for (const [runId, pending] of this.pendingChatRuns.entries()) {
      clearTimeout(pending.timer);
      pending.reject(error);
      this.pendingChatRuns.delete(runId);
    }
  }

  private closeSocket(reason: string): void {
    try {
      this.socket?.close?.(1008, reason.slice(0, 120));
    } catch {
      // Ignore close failures from already-closed sockets.
    }
    this.connected = false;
  }
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : undefined;
}

function extractGatewayPayload(frame: GatewayFrame): GatewayFrame {
  const payload = asRecord(frame.payload);
  if (payload) {
    return payload;
  }
  const result = asRecord(frame.result);
  if (result) {
    return result;
  }
  return {};
}

function formatGatewayError(value: unknown): string {
  const record = asRecord(value);
  if (typeof record?.message === "string") {
    return record.message;
  }
  if (typeof value === "string") {
    return value;
  }
  return "";
}

function parseGatewayFrame(event: unknown): GatewayFrame | undefined {
  const eventRecord = asRecord(event);
  const raw = eventRecord && "data" in eventRecord ? eventRecord.data : event;
  let text: string;
  if (typeof raw === "string") {
    text = raw;
  } else if (raw instanceof ArrayBuffer) {
    text = Buffer.from(raw).toString("utf8");
  } else if (ArrayBuffer.isView(raw)) {
    const view = raw as ArrayBufferView;
    text = Buffer.from(Array.from(new Uint8Array(view.buffer, view.byteOffset, view.byteLength))).toString("utf8");
  } else if (raw && typeof raw === "object" && typeof raw.toString === "function") {
    text = raw.toString();
  } else {
    return undefined;
  }

  try {
    const parsed = JSON.parse(text) as unknown;
    return asRecord(parsed);
  } catch {
    return undefined;
  }
}

function collectVisibleTextParts(value: unknown, out: string[] = []): string[] {
  if (typeof value === "string") {
    out.push(value);
    return out;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      collectVisibleTextParts(item, out);
    }
    return out;
  }
  const record = asRecord(value);
  if (!record) {
    return out;
  }
  if (record.type === "text" && typeof record.text === "string") {
    out.push(record.text);
  }
  for (const key of ["output_text", "value", "errorMessage"]) {
    if (typeof record[key] === "string") {
      out.push(record[key]);
    }
  }
  if (typeof record.content === "string") {
    out.push(record.content);
  } else if (record.content) {
    collectVisibleTextParts(record.content, out);
  }
  return out;
}

function sanitizeSessionPart(value: string | undefined, fallback: string): string {
  const normalized = (value || fallback).trim().replace(/[^A-Za-z0-9_.-]+/g, "_");
  return (normalized || fallback).slice(0, 96);
}

function buildChannelSessionKey(message: ChannelMessage): string {
  const peer = message.chatType === "group" ? message.chatId : message.senderId || message.chatId;
  return [
    "agent",
    "main",
    "qeeclaw-channel",
    sanitizeSessionPart(message.channel, "unknown"),
    sanitizeSessionPart(message.chatType, "dm"),
    sanitizeSessionPart(peer, "peer"),
  ].join(":");
}

async function buildGatewayMessage(message: ChannelMessage): Promise<string> {
  const lines = [
    message.text?.trim() || "",
    "",
    "---",
    "【本地通讯通道上下文】",
    `通道：${message.channel}`,
    `会话类型：${message.chatType}`,
    `发送者：${message.senderName || message.senderId}`,
    "请直接生成要发回该通讯通道用户的回复，不要调用 send 工具。",
  ];

  const attachmentHints = buildAttachmentHints(message);
  if (attachmentHints.length) {
    lines.push("附件：", ...attachmentHints);
  }
  return lines.join("\n").trim();
}

function buildAttachmentHints(message: ChannelMessage): string[] {
  return message.attachments
    .map((attachment, index) => {
      const parts = [`${index + 1}. ${attachment.name || attachment.type}`];
      if (attachment.localPath) {
        parts.push(`file://${attachment.localPath}`);
      } else if (attachment.remoteUrl) {
        parts.push(attachment.remoteUrl);
      }
      return parts.join(" ");
    })
    .filter((line) => line.trim().length > 0);
}

async function buildGatewayAttachments(message: ChannelMessage): Promise<GatewayAttachmentInput[] | undefined> {
  const attachments: GatewayAttachmentInput[] = [];
  for (const attachment of message.attachments) {
    const mimeType = attachment.mimeType || inferMimeType(attachment.name || attachment.localPath || "");
    if (attachment.type !== "image" && !mimeType.startsWith("image/")) {
      continue;
    }
    let content = attachment.dataBase64;
    if (!content && attachment.localPath?.trim()) {
      const bytes = await readFile(attachment.localPath);
      if (bytes.length <= MAX_GATEWAY_IMAGE_BYTES) {
        content = bytes.toString("base64");
      }
    }
    if (!content) {
      continue;
    }
    attachments.push({
      type: "image",
      mimeType: mimeType || "image/png",
      fileName: attachment.name || fallbackFileName(attachment.localPath, "image.png"),
      content,
    });
  }
  return attachments.length ? attachments : undefined;
}

async function buildReplyAttachmentsFromText(text: string): Promise<NonNullable<ChannelReply["attachments"]>> {
  const paths = extractLocalFilePaths(text);
  const attachments: NonNullable<ChannelReply["attachments"]> = [];
  for (const localPath of paths) {
    try {
      await access(localPath);
      const mimeType = inferMimeType(localPath);
      attachments.push({
        type: mimeType.startsWith("image/") ? "image" : "file",
        name: fallbackFileName(localPath, "qeeclaw-file"),
        mimeType,
        localPath,
      });
    } catch {
      // Ignore stale paths in model text.
    }
  }
  return attachments;
}

function extractLocalFilePaths(text: string): string[] {
  const paths = new Set<string>();
  const fileUrlRegex = /file:\/\/([^\n\r]+)/g;
  let match: RegExpExecArray | null;
  while ((match = fileUrlRegex.exec(text)) !== null) {
    const raw = (match[1] || "").trim().replace(/[)\]>"'`]+$/g, "");
    if (!raw) {
      continue;
    }
    try {
      paths.add(decodeURIComponent(raw));
    } catch {
      paths.add(raw);
    }
  }

  const absolutePathRegex = /(?:^|[\s"'`(\[])(\/(?:Users|tmp|var|private|Volumes)\/[^\n\r"'`\)\]]+\.[A-Za-z0-9]{1,12})/g;
  while ((match = absolutePathRegex.exec(text)) !== null) {
    const raw = (match[1] || "").trim();
    if (raw) {
      paths.add(raw);
    }
  }
  return Array.from(paths);
}

function fallbackFileName(input: string | undefined, fallback: string): string {
  if (!input?.trim()) {
    return fallback;
  }
  const parts = input.split(/[\\/]/);
  return parts[parts.length - 1] || fallback;
}

function inferMimeType(input: string): string {
  const lower = input.toLowerCase();
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) {
    return "image/jpeg";
  }
  if (lower.endsWith(".png")) {
    return "image/png";
  }
  if (lower.endsWith(".gif")) {
    return "image/gif";
  }
  if (lower.endsWith(".webp")) {
    return "image/webp";
  }
  if (lower.endsWith(".pdf")) {
    return "application/pdf";
  }
  if (lower.endsWith(".txt") || lower.endsWith(".md")) {
    return "text/plain";
  }
  return "application/octet-stream";
}

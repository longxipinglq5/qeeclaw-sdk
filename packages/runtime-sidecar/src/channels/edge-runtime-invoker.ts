import type { ChannelMessage, ChannelReply } from "../types.js";
import type { ChannelRuntimeInvoker } from "./types.js";
import { ProtocolInboxStore } from "./inbox-store.js";
import { ProtocolOutboxStore } from "./outbox-store.js";

type FetchLike = (url: string, init: RequestInit & { body?: string }) => Promise<Response>;

type EdgeRuntimeInvokerOptions = {
  bridgeBaseUrl: string;
  authToken?: string;
  fetchImpl?: FetchLike;
  inboxStore?: ProtocolInboxStore;
  outboxStore?: ProtocolOutboxStore;
  syncReplyTimeoutMs?: number;
};

type BridgeChannelEventResponse = {
  mode: "accepted_async" | "sync_reply" | "suppressed" | "requires_approval";
  run_id?: string;
  reply?: { text?: string; suppressed?: boolean };
  outbox_followup?: boolean;
  outbox_id?: string;
  approval_id?: string;
  timeline_url?: string;
};

const CHANNEL_MAP: Record<string, string> = {
  feishu: "feishu",
  wechat_work: "wechat_work",
  wechat_personal: "wechat",
};

export class EdgeRuntimeInvoker implements ChannelRuntimeInvoker {
  private readonly fetchImpl: FetchLike;
  private readonly inboxStore: ProtocolInboxStore;
  private readonly outboxStore: ProtocolOutboxStore;

  constructor(private readonly options: EdgeRuntimeInvokerOptions) {
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.inboxStore = options.inboxStore ?? new ProtocolInboxStore();
    this.outboxStore = options.outboxStore ?? new ProtocolOutboxStore();
  }

  async invoke(message: ChannelMessage): Promise<ChannelReply> {
    const dedupeKey = `${message.channel}:${message.messageId}`;
    if (this.inboxStore.has(dedupeKey)) {
      return { suppressed: true, rawMeta: { mode: "suppressed" } };
    }
    this.inboxStore.record({ dedupeKey, receivedAt: message.receivedAt });

    const response = await this.fetchImpl(`${trimTrailingSlash(this.options.bridgeBaseUrl)}/api/channels/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(this.options.authToken ? { Authorization: `Bearer ${this.options.authToken}` } : {}),
      },
      body: JSON.stringify(this.toBridgeEvent(message)),
    });
    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      throw new Error(`Bridge channel event failed: ${response.status}${detail ? ` ${detail}` : ""}`);
    }

    const body = (await response.json()) as BridgeChannelEventResponse;
    if (body.outbox_id) {
      this.outboxStore.record({ dedupeKey, providerMessageId: body.outbox_id });
    }
    return this.toChannelReply(body);
  }

  private toBridgeEvent(message: ChannelMessage): Record<string, unknown> {
    return {
      external_message_id: message.messageId,
      channel_key: CHANNEL_MAP[message.channel] ?? message.channel,
      conversation_key: message.chatId,
      sender_id: message.senderId,
      sender_name: message.senderName,
      direction: "inbound",
      content: message.text ?? "",
      timestamp: message.receivedAt,
      sync_reply_timeout_ms: this.options.syncReplyTimeoutMs,
      metadata: message.rawMeta ?? {},
    };
  }

  private toChannelReply(body: BridgeChannelEventResponse): ChannelReply {
    if (body.mode === "suppressed") {
      return { suppressed: true, rawMeta: { mode: body.mode } };
    }
    return {
      text: body.reply?.text,
      suppressed: body.reply?.suppressed,
      rawMeta: {
        mode: body.mode,
        ...(body.run_id ? { bridgeRunId: body.run_id } : {}),
        ...(body.outbox_followup !== undefined ? { outboxFollowup: body.outbox_followup } : {}),
        ...(body.outbox_id ? { bridgeOutboxId: body.outbox_id } : {}),
        ...(body.approval_id ? { bridgeApprovalId: body.approval_id } : {}),
        ...(body.timeline_url ? { timelineUrl: body.timeline_url } : {}),
      },
    };
  }
}

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

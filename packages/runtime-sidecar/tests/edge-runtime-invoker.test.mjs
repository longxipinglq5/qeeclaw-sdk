import assert from "node:assert/strict";
import test from "node:test";

import { EdgeRuntimeInvoker } from "../dist/channels/edge-runtime-invoker.js";
import { ProtocolInboxStore } from "../dist/channels/inbox-store.js";
import { ProtocolOutboxStore } from "../dist/channels/outbox-store.js";

function channelMessage(overrides = {}) {
  return {
    channel: "wechat_personal",
    messageId: "wx_msg_001",
    chatId: "wechat:user:openid_123",
    chatType: "dm",
    senderId: "openid_123",
    senderName: "张女士",
    text: "护眼台灯现在有什么优惠？",
    attachments: [],
    receivedAt: "2026-06-06T10:15:00.000Z",
    ...overrides,
  };
}

test("edge runtime invoker performs protocol dedupe while Bridge owns product ledger", async () => {
  const calls = [];
  const invoker = new EdgeRuntimeInvoker({
    bridgeBaseUrl: "http://127.0.0.1:21747",
    fetchImpl: async (url, init) => {
      calls.push({ url: String(url), body: JSON.parse(init.body) });
      return Response.json({
        mode: "accepted_async",
        run_id: "run_channel_001",
        reply: { text: "收到，正在处理" },
        outbox_followup: true,
      });
    },
    inboxStore: new ProtocolInboxStore(),
    outboxStore: new ProtocolOutboxStore(),
  });

  const first = await invoker.invoke(channelMessage());
  const duplicate = await invoker.invoke(channelMessage());

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://127.0.0.1:21747/api/channels/events");
  assert.equal(calls[0].body.external_message_id, "wx_msg_001");
  assert.equal(first.text, "收到，正在处理");
  assert.deepEqual(first.rawMeta, {
    mode: "accepted_async",
    bridgeRunId: "run_channel_001",
    outboxFollowup: true,
  });
  assert.deepEqual(duplicate, { suppressed: true, rawMeta: { mode: "suppressed" } });
});

test("protocol stores never own product timeline approval retry or outbox state", () => {
  const inbox = new ProtocolInboxStore();
  const outbox = new ProtocolOutboxStore();

  inbox.record({ dedupeKey: "wechat:wx_msg_001", receivedAt: "now" });
  outbox.record({ dedupeKey: "wechat:wx_msg_001", providerMessageId: "provider_001" });

  assert.deepEqual(Object.keys(inbox.list()[0]).sort(), ["dedupeKey", "receivedAt"]);
  assert.deepEqual(Object.keys(outbox.list()[0]).sort(), ["dedupeKey", "providerMessageId"]);
});

test("edge runtime invoker passes Bridge-owned ids as metadata only", async () => {
  const invoker = new EdgeRuntimeInvoker({
    bridgeBaseUrl: "http://127.0.0.1:21747",
    fetchImpl: async () =>
      Response.json({
        mode: "requires_approval",
        reply: { text: "需要审批后处理" },
        outbox_id: "out_wx_001",
        approval_id: "appr_publish_001",
        timeline_url: "/api/sessions/session_1/timeline",
      }),
    inboxStore: new ProtocolInboxStore(),
    outboxStore: new ProtocolOutboxStore(),
  });

  const reply = await invoker.invoke(channelMessage({ messageId: "wx_msg_002" }));

  assert.equal(reply.text, "需要审批后处理");
  assert.deepEqual(reply.rawMeta, {
    mode: "requires_approval",
    bridgeOutboxId: "out_wx_001",
    bridgeApprovalId: "appr_publish_001",
    timelineUrl: "/api/sessions/session_1/timeline",
  });
});

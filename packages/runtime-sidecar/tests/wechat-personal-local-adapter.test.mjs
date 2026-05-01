import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { mkdtemp, rm } from "node:fs/promises";

import { ChannelAttachmentStore } from "../dist/channels/attachment-store.js";
import { ChannelManager } from "../dist/channels/manager.js";
import { CallbackRuntimeInvoker } from "../dist/channels/runtime-invoker.js";
import {
  MemoryWechatPersonalTransport,
  WechatPersonalLocalAdapter,
} from "../dist/channels/wechat-personal/adapter.js";

test("wechat personal local adapter converts OpenClaw upstream payloads and sends replies with local context", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-wechat-personal-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const transport = new MemoryWechatPersonalTransport();
  const adapter = new WechatPersonalLocalAdapter(transport);
  const seen = [];
  const manager = new ChannelManager({
    attachmentStore: new ChannelAttachmentStore(tmpDir),
    adapters: [adapter],
    invoker: new CallbackRuntimeInvoker((message) => {
      seen.push(message);
      return { text: `reply:${message.text}` };
    }),
  });

  await manager.start();
  const replies = await transport.emitAndCollectReplies({
    event_id: "wx_evt_001",
    external_user_id: "wx_user_001",
    room_id: "room_001",
    chat_type: "room",
    content: "@QeeClaw hello",
    sender_name: "Alice",
    send: {
      channel: "wechat",
      to: "wx_user_001",
      account_id: "account_001",
      session_key: "session_001",
    },
  });

  assert.equal(seen.length, 1);
  assert.equal(seen[0].channel, "wechat_personal");
  assert.equal(seen[0].messageId, "wx_evt_001");
  assert.equal(seen[0].senderId, "wx_user_001");
  assert.equal(seen[0].chatId, "room_001");
  assert.equal(seen[0].chatType, "group");
  assert.equal(seen[0].senderName, "Alice");
  assert.equal(seen[0].text, "hello");
  assert.equal(replies.length, 1);
  assert.deepEqual(
    {
      to: replies[0].to,
      message: replies[0].message,
      channel: replies[0].channel,
      accountId: replies[0].accountId,
      sessionKey: replies[0].sessionKey,
    },
    {
      to: "wx_user_001",
      message: "reply:hello",
      channel: "wechat",
      accountId: "account_001",
      sessionKey: "session_001",
    },
  );

  await manager.stop();
});

test("wechat personal local adapter ignores malformed payloads without invoking runtime", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-wechat-personal-malformed-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const transport = new MemoryWechatPersonalTransport();
  const adapter = new WechatPersonalLocalAdapter(transport);
  let invokeCount = 0;
  const manager = new ChannelManager({
    attachmentStore: new ChannelAttachmentStore(tmpDir),
    adapters: [adapter],
    invoker: new CallbackRuntimeInvoker(() => {
      invokeCount += 1;
      return { text: "ok" };
    }),
  });

  await manager.start();
  await transport.emit({ event_id: "missing-sender", text: "hello" });
  await transport.emit({ external_user_id: "wx_user_001", text: "missing id" });

  assert.equal(invokeCount, 0);
  assert.equal(adapter.getStatus().lastError, "WeChat personal payload missing senderId or messageId");

  await manager.stop();
});

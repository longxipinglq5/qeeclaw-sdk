import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { mkdtemp, rm } from "node:fs/promises";

import { ChannelAttachmentStore } from "../dist/channels/attachment-store.js";
import { FeishuLocalAdapter } from "../dist/channels/feishu/adapter.js";
import { ChannelManager } from "../dist/channels/manager.js";
import { CallbackRuntimeInvoker } from "../dist/channels/runtime-invoker.js";
import { ChannelSecretStore } from "../dist/channels/secret-store.js";

class FakeFeishuTransport {
  handler = undefined;
  sent = [];
  running = false;

  async start(handlers) {
    this.handler = handlers.onEvent;
    this.running = true;
  }

  async stop() {
    this.running = false;
  }

  async sendMessage(payload) {
    this.sent.push(payload);
  }

  async emit(event) {
    if (!this.handler) {
      throw new Error("transport not started");
    }
    await this.handler(event);
  }
}

function createTextEvent(overrides = {}) {
  return {
    header: { event_type: "im.message.receive_v1" },
    event: {
      sender: {
        sender_id: { open_id: "ou_sender" },
      },
      message: {
        message_id: "om_001",
        chat_id: "oc_chat",
        chat_type: "p2p",
        message_type: "text",
        content: JSON.stringify({ text: "hello feishu" }),
        ...overrides,
      },
    },
  };
}

test("feishu local adapter converts message events into local channel messages and sends replies", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-feishu-adapter-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const transport = new FakeFeishuTransport();
  const adapter = new FeishuLocalAdapter({ transport });
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
  await transport.emit(createTextEvent());

  assert.equal(seen.length, 1);
  assert.equal(seen[0].channel, "feishu");
  assert.equal(seen[0].senderId, "ou_sender");
  assert.equal(seen[0].text, "hello feishu");
  assert.equal(transport.sent.length, 1);
  assert.deepEqual(transport.sent[0], {
    receiveId: "ou_sender",
    receiveIdType: "open_id",
    msgType: "text",
    content: JSON.stringify({ text: "reply:hello feishu" }),
  });

  await manager.stop();
});

test("feishu local adapter requires mentions for group events by default", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-feishu-group-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const transport = new FakeFeishuTransport();
  const adapter = new FeishuLocalAdapter({ transport });
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
  await transport.emit(createTextEvent({ chat_type: "group", content: JSON.stringify({ text: "no mention" }) }));
  await transport.emit(
    createTextEvent({
      message_id: "om_002",
      chat_type: "group",
      content: JSON.stringify({ text: "@Bot run" }),
      mentions: [{ key: "@Bot", name: "Bot", id: { open_id: "ou_bot" } }],
    }),
  );

  assert.equal(invokeCount, 1);
  assert.equal(transport.sent[0].receiveId, "oc_chat");
  assert.equal(transport.sent[0].receiveIdType, "chat_id");

  await manager.stop();
});

test("channel secret store persists local-only secrets and exposes redacted public status", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-channel-secrets-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const store = new ChannelSecretStore(path.join(tmpDir, "secrets.json"));
  await store.patch("feishu", {
    enabled: true,
    credentials: {
      appId: "cli_xxx",
      appSecret: "secret-value",
    },
  });

  const raw = await store.get("feishu");
  assert.equal(raw.credentials.appSecret, "secret-value");

  const [publicStatus] = await store.publicStatus();
  assert.equal(publicStatus.channel, "feishu");
  assert.equal(publicStatus.enabled, true);
  assert.deepEqual(publicStatus.credentials, {
    appId: true,
    appSecret: true,
  });
});

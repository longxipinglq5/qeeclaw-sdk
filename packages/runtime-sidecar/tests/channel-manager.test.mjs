import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { access, mkdtemp, rm } from "node:fs/promises";

import { ChannelAttachmentStore } from "../dist/channels/attachment-store.js";
import { ChannelManager } from "../dist/channels/manager.js";
import { CallbackRuntimeInvoker } from "../dist/channels/runtime-invoker.js";

class TestChannelAdapter {
  channel = "feishu";
  running = false;
  context = null;
  sentReplies = [];

  async start(context) {
    this.context = context;
    this.running = true;
  }

  async stop() {
    this.running = false;
    this.context = null;
  }

  async emitInbound(payload) {
    if (!this.running || !this.context) {
      throw new Error("Test channel adapter is not running");
    }
    await this.context.emitMessage({
      channel: this.channel,
      messageId: payload.messageId || `test-${crypto.randomUUID()}`,
      chatId: payload.chatId || "test-chat",
      chatType: payload.chatType || "dm",
      senderId: payload.senderId || "test-user",
      senderName: payload.senderName,
      text: payload.text,
      attachments: payload.attachments || [],
      rawMeta: payload.rawMeta,
      receivedAt: new Date().toISOString(),
    });
  }

  async sendReply(message, reply) {
    this.sentReplies.push({ message, reply });
  }

  getStatus() {
    return {
      channel: this.channel,
      configured: true,
      running: this.running,
      mode: "local_bridge",
    };
  }
}

test("channel manager routes local bridge messages through runtime invoker and replies via adapter", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-channel-manager-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const testAdapter = new TestChannelAdapter();
  const seenMessages = [];
  const manager = new ChannelManager({
    attachmentStore: new ChannelAttachmentStore(tmpDir),
    adapters: [testAdapter],
    invoker: new CallbackRuntimeInvoker(async (message) => {
      seenMessages.push(message);
      return { text: `local reply: ${message.text}` };
    }),
  });

  await manager.start();
  await testAdapter.emitInbound({
    messageId: "msg-001",
    senderId: "user-001",
    text: "hello local bridge",
  });

  assert.equal(seenMessages.length, 1);
  assert.equal(seenMessages[0].channel, "feishu");
  assert.equal(seenMessages[0].text, "hello local bridge");
  assert.equal(testAdapter.sentReplies.length, 1);
  assert.equal(testAdapter.sentReplies[0].reply.text, "local reply: hello local bridge");
  assert.deepEqual(manager.getStatus().adapters[0].channel, "feishu");

  await manager.stop();
});

test("channel manager drops duplicate channel message ids before runtime invocation", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-channel-dedupe-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const testAdapter = new TestChannelAdapter();
  let invokeCount = 0;
  const manager = new ChannelManager({
    attachmentStore: new ChannelAttachmentStore(tmpDir),
    adapters: [testAdapter],
    invoker: new CallbackRuntimeInvoker(async () => {
      invokeCount += 1;
      return { text: "ok" };
    }),
  });

  await manager.start();
  await testAdapter.emitInbound({ messageId: "dup-001", text: "first" });
  await testAdapter.emitInbound({ messageId: "dup-001", text: "second" });

  assert.equal(invokeCount, 1);
  assert.equal(testAdapter.sentReplies.length, 1);

  await manager.stop();
});

test("channel manager can replace a running adapter", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-channel-replace-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const firstAdapter = new TestChannelAdapter();
  const secondAdapter = new TestChannelAdapter();
  const manager = new ChannelManager({
    attachmentStore: new ChannelAttachmentStore(tmpDir),
    adapters: [firstAdapter],
    invoker: new CallbackRuntimeInvoker(() => ({ text: "ok" })),
  });

  await manager.start();
  assert.equal(firstAdapter.getStatus().running, true);

  await manager.replaceAdapter(secondAdapter);

  assert.equal(firstAdapter.getStatus().running, false);
  assert.equal(secondAdapter.getStatus().running, true);
  assert.equal(manager.getStatus().adapters.length, 1);

  await manager.stop();
});

test("channel attachment store materializes inline base64 data to local files", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-channel-attachments-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const store = new ChannelAttachmentStore(tmpDir);
  const [attachment] = await store.materialize([
    {
      type: "file",
      name: "hello.txt",
      mimeType: "text/plain",
      dataBase64: Buffer.from("hello").toString("base64"),
    },
  ]);

  assert.equal(attachment.dataBase64, undefined);
  assert.equal(attachment.sizeBytes, 5);
  assert.ok(attachment.localPath);
  await access(attachment.localPath);
});

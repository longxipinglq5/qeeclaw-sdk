import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { mkdtemp, rm } from "node:fs/promises";

import { ChannelAttachmentStore } from "../dist/channels/attachment-store.js";
import { ChannelManager } from "../dist/channels/manager.js";
import { CallbackRuntimeInvoker } from "../dist/channels/runtime-invoker.js";
import {
  MemoryWechatWorkTransport,
  WechatWorkLocalAdapter,
  WechatWorkRestTransport,
} from "../dist/channels/wechat-work/adapter.js";

test("wechat work local adapter converts callback payloads into local channel messages and sends replies", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-wechat-work-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const transport = new MemoryWechatWorkTransport();
  const adapter = new WechatWorkLocalAdapter(transport);
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
  await transport.emit({
    MsgId: "wxw_msg_001",
    FromUserName: "zhangsan",
    ToUserName: "ww_corp",
    AgentID: "1000001",
    MsgType: "text",
    Content: "@QeeClaw hello wecom",
  });

  assert.equal(seen.length, 1);
  assert.equal(seen[0].channel, "wechat_work");
  assert.equal(seen[0].messageId, "wxw_msg_001");
  assert.equal(seen[0].senderId, "zhangsan");
  assert.equal(seen[0].chatId, "zhangsan");
  assert.equal(seen[0].chatType, "dm");
  assert.equal(seen[0].text, "hello wecom");
  assert.deepEqual(transport.sentMessages, [
    {
      to: "zhangsan",
      message: "reply:hello wecom",
      attachments: undefined,
    },
  ]);

  await manager.stop();
});

test("wechat work local adapter materializes media callback payloads as attachments", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-wechat-work-media-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const transport = new MemoryWechatWorkTransport();
  const adapter = new WechatWorkLocalAdapter(transport);
  const seen = [];
  const manager = new ChannelManager({
    attachmentStore: new ChannelAttachmentStore(tmpDir),
    adapters: [adapter],
    invoker: new CallbackRuntimeInvoker((message) => {
      seen.push(message);
      return { text: "ok" };
    }),
  });

  await manager.start();
  await transport.emit({
    MsgId: "wxw_msg_file_001",
    FromUserName: "lisi",
    ChatId: "group_001",
    MsgType: "file",
    MediaId: "media_001",
    FileName: "report.pdf",
  });

  assert.equal(seen.length, 1);
  assert.equal(seen[0].chatType, "group");
  assert.equal(seen[0].attachments.length, 1);
  assert.deepEqual(seen[0].attachments[0], {
    type: "file",
    name: "report.pdf",
    remoteUrl: "wechat-work://media/media_001",
    rawMeta: {
      mediaId: "media_001",
      msgType: "file",
      picUrl: undefined,
    },
  });

  await manager.stop();
});

test("wechat work rest transport sends text replies through enterprise wechat API", async () => {
  const calls = [];
  const transport = new WechatWorkRestTransport({
    corpId: "ww_corp",
    corpSecret: "secret",
    agentId: "1000001",
    apiBaseUrl: "https://qyapi.test",
    fetchImpl: async (url, init) => {
      calls.push({ url: String(url), init });
      if (String(url).includes("/cgi-bin/gettoken")) {
        return new Response(JSON.stringify({ errcode: 0, access_token: "token-001", expires_in: 7200 }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ errcode: 0, errmsg: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });

  await transport.start({ onMessage: async () => undefined });
  await transport.sendMessage({ to: "zhangsan", message: "hello" });

  assert.equal(calls.length, 2);
  assert.match(calls[0].url, /\/cgi-bin\/gettoken\?corpid=ww_corp&corpsecret=secret$/);
  assert.match(calls[1].url, /\/cgi-bin\/message\/send\?access_token=token-001$/);
  assert.deepEqual(JSON.parse(calls[1].init.body), {
    touser: "zhangsan",
    msgtype: "text",
    agentid: "1000001",
    text: { content: "hello" },
  });
});

import assert from "node:assert/strict";
import test from "node:test";

import { FeishuWebSocketTransport } from "../dist/channels/feishu/websocket-transport.js";

class FakeEventDispatcher {
  static last;
  handlers = {};

  constructor(params) {
    this.params = params;
    FakeEventDispatcher.last = this;
  }

  register(handlers) {
    this.handlers = { ...this.handlers, ...handlers };
  }
}

class FakeWSClient {
  static last;
  startedWith = undefined;
  closed = false;

  constructor(params) {
    this.params = params;
    FakeWSClient.last = this;
  }

  start(params) {
    this.startedWith = params;
  }

  close() {
    this.closed = true;
  }
}

test("feishu websocket transport wires SDK events into local event handler", async () => {
  const events = [];
  const transport = new FeishuWebSocketTransport({
    appId: "cli_xxx",
    appSecret: "secret",
    encryptKey: "encrypt",
    verificationToken: "verify",
    sdkLoader: async () => ({
      EventDispatcher: FakeEventDispatcher,
      WSClient: FakeWSClient,
      Domain: { Feishu: "https://open.feishu.cn" },
      LoggerLevel: { info: "info" },
    }),
    fetchImpl: async () => {
      throw new Error("fetch should not be called during websocket start");
    },
  });

  await transport.start({
    onEvent: async (event) => {
      events.push(event);
    },
  });

  assert.equal(FakeEventDispatcher.last.params.encryptKey, "encrypt");
  assert.equal(FakeEventDispatcher.last.params.verificationToken, "verify");
  assert.equal(FakeWSClient.last.params.appId, "cli_xxx");
  assert.equal(FakeWSClient.last.params.appSecret, "secret");
  assert.equal(FakeWSClient.last.startedWith.eventDispatcher, FakeEventDispatcher.last);

  await FakeEventDispatcher.last.handlers["im.message.receive_v1"]({
    sender: { sender_id: { open_id: "ou_sender" } },
    message: { message_id: "om_001" },
  });

  assert.equal(events.length, 1);
  assert.equal(events[0].header.event_type, "im.message.receive_v1");
  assert.equal(events[0].event.sender.sender_id.open_id, "ou_sender");

  await transport.stop();
  assert.equal(FakeWSClient.last.closed, true);
});

test("feishu websocket transport sends messages through Feishu REST with cached token", async () => {
  const calls = [];
  const transport = new FeishuWebSocketTransport({
    appId: "cli_xxx",
    appSecret: "secret",
    fetchImpl: async (url, init) => {
      calls.push({ url: String(url), init });
      if (String(url).includes("/tenant_access_token/internal")) {
        return new Response(
          JSON.stringify({
            code: 0,
            tenant_access_token: "tat_xxx",
            expire: 7200,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ code: 0, data: { message_id: "om_reply" } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });

  await transport.sendMessage({
    receiveId: "ou_sender",
    receiveIdType: "open_id",
    msgType: "text",
    content: JSON.stringify({ text: "hello" }),
  });
  await transport.sendMessage({
    receiveId: "ou_sender",
    receiveIdType: "open_id",
    msgType: "text",
    content: JSON.stringify({ text: "again" }),
  });

  assert.equal(calls.filter((call) => call.url.includes("/tenant_access_token/internal")).length, 1);
  const messageCalls = calls.filter((call) => call.url.includes("/im/v1/messages"));
  assert.equal(messageCalls.length, 2);
  assert.match(messageCalls[0].url, /receive_id_type=open_id/);
  assert.equal(messageCalls[0].init.headers.Authorization, "Bearer tat_xxx");
  assert.deepEqual(JSON.parse(messageCalls[0].init.body), {
    receive_id: "ou_sender",
    msg_type: "text",
    content: JSON.stringify({ text: "hello" }),
  });
});

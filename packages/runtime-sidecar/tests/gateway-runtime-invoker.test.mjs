import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";

import { GatewayRuntimeInvoker } from "../dist/channels/runtime-invoker.js";

class FakeGatewaySocket extends EventEmitter {
  readyState = 0;
  sent = [];

  addEventListener(event, handler) {
    this.on(event, handler);
  }

  open() {
    this.readyState = 1;
    this.emit("open", {});
    this.emit("message", {
      data: JSON.stringify({
        type: "event",
        event: "connect.challenge",
        payload: { nonce: "nonce-001" },
      }),
    });
  }

  send(data) {
    const frame = JSON.parse(data);
    this.sent.push(frame);

    if (frame.method === "connect") {
      this.emit("message", {
        data: JSON.stringify({
          type: "res",
          id: frame.id,
          method: "connect",
          ok: true,
          payload: { ok: true },
        }),
      });
      return;
    }

    if (frame.method === "chat.send") {
      this.emit("message", {
        data: JSON.stringify({
          type: "res",
          id: frame.id,
          method: "chat.send",
          ok: true,
          payload: { runId: frame.params.idempotencyKey, status: "started" },
        }),
      });
      queueMicrotask(() => {
        this.emit("message", {
          data: JSON.stringify({
            type: "event",
            event: "chat",
            payload: {
              runId: frame.params.idempotencyKey,
              state: "final",
              message: {
                content: [{ type: "text", text: "gateway reply" }],
              },
            },
          }),
        });
      });
    }
  }

  close() {
    this.readyState = 3;
  }
}

test("gateway runtime invoker sends channel messages to local chat.send and returns final reply", async () => {
  const socket = new FakeGatewaySocket();
  const invoker = new GatewayRuntimeInvoker({
    wsUrl: "ws://127.0.0.1:18789",
    authToken: "gateway-token",
    webSocketFactory: () => socket,
    connectTimeoutMs: 1000,
    responseTimeoutMs: 1000,
    chatTimeoutMs: 1000,
  });

  const pending = invoker.invoke({
    channel: "wechat_personal",
    messageId: "msg-001",
    chatId: "chat-001",
    chatType: "dm",
    senderId: "user-001",
    text: "hello",
    attachments: [],
    receivedAt: new Date().toISOString(),
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  socket.open();

  const reply = await pending;
  const connectFrame = socket.sent.find((frame) => frame.method === "connect");
  const chatFrame = socket.sent.find((frame) => frame.method === "chat.send");

  assert.equal(reply.text, "gateway reply");
  assert.equal(connectFrame.params.auth.token, "gateway-token");
  assert.equal(chatFrame.params.deliver, false);
  assert.match(chatFrame.params.sessionKey, /^agent:main:qeeclaw-channel:wechat_personal:dm:user-001$/);
  assert.match(chatFrame.params.message, /请直接生成要发回该通讯通道用户的回复/);
});

test("gateway runtime invoker returns chat error final as channel text", async () => {
  class ErrorFinalSocket extends FakeGatewaySocket {
    send(data) {
      const frame = JSON.parse(data);
      this.sent.push(frame);
      if (frame.method === "connect") {
        this.emit("message", { data: JSON.stringify({ type: "res", id: frame.id, ok: true, payload: {} }) });
        return;
      }
      this.emit("message", {
        data: JSON.stringify({
          type: "res",
          id: frame.id,
          ok: true,
          payload: { runId: frame.params.idempotencyKey, status: "started" },
        }),
      });
      this.emit("message", {
        data: JSON.stringify({
          type: "event",
          event: "chat",
          payload: {
            runId: frame.params.idempotencyKey,
            state: "error",
            errorMessage: "model failed",
          },
        }),
      });
    }
  }

  const socket = new ErrorFinalSocket();
  const invoker = new GatewayRuntimeInvoker({
    wsUrl: "ws://127.0.0.1:18789",
    webSocketFactory: () => socket,
    connectTimeoutMs: 1000,
    responseTimeoutMs: 1000,
    chatTimeoutMs: 1000,
  });

  const pending = invoker.invoke({
    channel: "feishu",
    messageId: "msg-002",
    chatId: "chat-002",
    chatType: "group",
    senderId: "ou_001",
    text: "hello",
    attachments: [],
    receivedAt: new Date().toISOString(),
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  socket.open();

  assert.deepEqual(await pending, { text: "model failed" });
});

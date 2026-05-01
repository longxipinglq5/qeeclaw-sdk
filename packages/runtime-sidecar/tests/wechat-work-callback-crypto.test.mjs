import assert from "node:assert/strict";
import crypto from "node:crypto";
import test from "node:test";

import {
  parseWechatWorkCallbackBody,
  signWechatWorkCallback,
  verifyWechatWorkUrl,
} from "../dist/channels/wechat-work/callback-crypto.js";

const encodingAesKey = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG";
const credentials = {
  corpId: "ww_corp",
  token: "callback-token",
  encodingAesKey,
};

function pkcs7Pad(buffer) {
  const blockSize = 32;
  const pad = blockSize - (buffer.length % blockSize || blockSize);
  return Buffer.concat([buffer, Buffer.alloc(pad, pad)]);
}

function encryptWechatWorkPlaintext(plaintext) {
  const key = Buffer.from(`${encodingAesKey}=`, "base64");
  const random = Buffer.from("1234567890abcdef");
  const message = Buffer.from(plaintext);
  const length = Buffer.alloc(4);
  length.writeUInt32BE(message.length, 0);
  const raw = pkcs7Pad(Buffer.concat([random, length, message, Buffer.from(credentials.corpId)]));
  const cipher = crypto.createCipheriv("aes-256-cbc", key, key.subarray(0, 16));
  cipher.setAutoPadding(false);
  return Buffer.concat([cipher.update(raw), cipher.final()]).toString("base64");
}

test("wechat work callback crypto verifies url challenge and decrypts echostr", () => {
  const encrypted = encryptWechatWorkPlaintext("local-bridge-ok");
  const timestamp = "1710000000";
  const nonce = "nonce-001";
  const msgSignature = signWechatWorkCallback(credentials.token, timestamp, nonce, encrypted);

  const reply = verifyWechatWorkUrl({
    msgSignature,
    timestamp,
    nonce,
    echostr: encrypted,
    credentials,
  });

  assert.equal(reply, "local-bridge-ok");
});

test("wechat work callback crypto verifies encrypted message body and returns normalized xml fields", () => {
  const plaintext = [
    "<xml>",
    "<ToUserName><![CDATA[ww_corp]]></ToUserName>",
    "<FromUserName><![CDATA[zhangsan]]></FromUserName>",
    "<CreateTime>1710000000</CreateTime>",
    "<MsgType><![CDATA[text]]></MsgType>",
    "<Content><![CDATA[@QeeClaw hello]]></Content>",
    "<MsgId>msg-001</MsgId>",
    "<AgentID>1000001</AgentID>",
    "</xml>",
  ].join("");
  const encrypted = encryptWechatWorkPlaintext(plaintext);
  const timestamp = "1710000000";
  const nonce = "nonce-002";
  const msgSignature = signWechatWorkCallback(credentials.token, timestamp, nonce, encrypted);

  const payload = parseWechatWorkCallbackBody({
    rawBody: `<xml><Encrypt><![CDATA[${encrypted}]]></Encrypt></xml>`,
    msgSignature,
    timestamp,
    nonce,
    credentials,
  });

  assert.equal(payload.ToUserName, "ww_corp");
  assert.equal(payload.FromUserName, "zhangsan");
  assert.equal(payload.MsgType, "text");
  assert.equal(payload.Content, "@QeeClaw hello");
  assert.equal(payload.MsgId, "msg-001");
  assert.equal(payload.AgentID, "1000001");
});

test("wechat work callback crypto rejects invalid signatures", () => {
  const encrypted = encryptWechatWorkPlaintext("bad");

  assert.throws(
    () =>
      verifyWechatWorkUrl({
        msgSignature: "bad-signature",
        timestamp: "1710000000",
        nonce: "nonce-003",
        echostr: encrypted,
        credentials,
      }),
    /Invalid WeChat Work callback signature/,
  );
});

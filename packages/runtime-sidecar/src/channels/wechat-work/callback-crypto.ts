import crypto from "node:crypto";

import type { WechatWorkIncomingPayload } from "./adapter.js";

export type WechatWorkCallbackCredentials = {
  corpId: string;
  token: string;
  encodingAesKey: string;
};

function extractXmlTag(xml: string, tag: string): string | undefined {
  const match = xml.match(new RegExp(`<${tag}>\\s*(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?\\s*</${tag}>`, "i"));
  return match?.[1]?.trim();
}

function parsePlainXml(xml: string): WechatWorkIncomingPayload {
  const payload: Record<string, string> = {};
  const pattern = /<(?!xml\b)([A-Za-z0-9_]+)>\s*(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?\s*<\/\1>/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(xml)) !== null) {
    payload[match[1]] = match[2].trim();
  }
  return payload;
}

export function signWechatWorkCallback(token: string, timestamp: string, nonce: string, encrypted: string): string {
  return crypto
    .createHash("sha1")
    .update([token, timestamp, nonce, encrypted].sort().join(""))
    .digest("hex");
}

export function verifyWechatWorkCallbackSignature(params: {
  token: string;
  timestamp: string;
  nonce: string;
  encrypted: string;
  signature: string;
}): boolean {
  const expected = signWechatWorkCallback(params.token, params.timestamp, params.nonce, params.encrypted);
  return expected === params.signature;
}

export function decryptWechatWorkPayload(encrypted: string, credentials: WechatWorkCallbackCredentials): string {
  const key = Buffer.from(`${credentials.encodingAesKey}=`, "base64");
  if (key.byteLength !== 32) {
    throw new Error("Invalid WeChat Work EncodingAESKey");
  }

  const decipher = crypto.createDecipheriv("aes-256-cbc", key, key.subarray(0, 16));
  decipher.setAutoPadding(false);
  const decrypted = Buffer.concat([decipher.update(encrypted, "base64"), decipher.final()]);
  const pad = decrypted[decrypted.byteLength - 1] || 0;
  const unpadded = pad > 0 && pad <= 32 ? decrypted.subarray(0, decrypted.byteLength - pad) : decrypted;
  const msgLength = unpadded.subarray(16).readUInt32BE(0);
  const xmlStart = 20;
  const xmlEnd = xmlStart + msgLength;
  const xml = unpadded.subarray(xmlStart, xmlEnd).toString("utf8");
  const receiveId = unpadded.subarray(xmlEnd).toString("utf8");
  if (credentials.corpId && receiveId && receiveId !== credentials.corpId) {
    throw new Error("WeChat Work callback corpId mismatch");
  }
  return xml;
}

export function parseWechatWorkCallbackXml(xml: string, credentials: WechatWorkCallbackCredentials): WechatWorkIncomingPayload {
  const encrypted = extractXmlTag(xml, "Encrypt");
  if (!encrypted) {
    return parsePlainXml(xml);
  }
  const decryptedXml = decryptWechatWorkPayload(encrypted, credentials);
  return parsePlainXml(decryptedXml);
}

export function verifyWechatWorkUrl(params: {
  msgSignature: string;
  timestamp: string;
  nonce: string;
  echostr: string;
  credentials: WechatWorkCallbackCredentials;
}): string {
  if (
    !verifyWechatWorkCallbackSignature({
      token: params.credentials.token,
      timestamp: params.timestamp,
      nonce: params.nonce,
      encrypted: params.echostr,
      signature: params.msgSignature,
    })
  ) {
    throw new Error("Invalid WeChat Work callback signature");
  }
  return decryptWechatWorkPayload(params.echostr, params.credentials);
}

export function parseWechatWorkCallbackBody(params: {
  rawBody: string;
  msgSignature: string;
  timestamp: string;
  nonce: string;
  credentials: WechatWorkCallbackCredentials;
}): WechatWorkIncomingPayload {
  const encrypted = extractXmlTag(params.rawBody, "Encrypt");
  if (
    encrypted &&
    !verifyWechatWorkCallbackSignature({
      token: params.credentials.token,
      timestamp: params.timestamp,
      nonce: params.nonce,
      encrypted,
      signature: params.msgSignature,
    })
  ) {
    throw new Error("Invalid WeChat Work callback signature");
  }
  return parseWechatWorkCallbackXml(params.rawBody, params.credentials);
}

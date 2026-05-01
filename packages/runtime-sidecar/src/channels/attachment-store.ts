import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";

import type { ChannelAttachment } from "../types.js";

function sanitizeFileName(name: string): string {
  return name.replace(/[^\w.-]+/g, "_").replace(/^_+/, "").slice(0, 120) || "attachment.bin";
}

function extensionFromMime(mimeType?: string): string {
  if (mimeType === "image/png") return "png";
  if (mimeType === "image/jpeg") return "jpg";
  if (mimeType === "image/gif") return "gif";
  if (mimeType === "text/plain") return "txt";
  return "bin";
}

export class ChannelAttachmentStore {
  constructor(
    private readonly rootDir: string,
    private readonly maxInlineBytes = 25 * 1024 * 1024,
  ) {}

  async materialize(attachments: ChannelAttachment[]): Promise<ChannelAttachment[]> {
    await mkdir(this.rootDir, { recursive: true });
    const materialized: ChannelAttachment[] = [];

    for (const attachment of attachments) {
      if (!attachment.dataBase64 || attachment.localPath) {
        materialized.push(attachment);
        continue;
      }

      const fileBytes = Buffer.from(attachment.dataBase64, "base64");
      if (fileBytes.byteLength > this.maxInlineBytes) {
        throw new Error(`Attachment exceeds local bridge inline limit: ${attachment.name || attachment.type}`);
      }

      const fallbackName = `${attachment.type}.${extensionFromMime(attachment.mimeType)}`;
      const fileName = sanitizeFileName(attachment.name || fallbackName);
      const filePath = path.join(this.rootDir, `${Date.now()}-${crypto.randomUUID()}-${fileName}`);
      await writeFile(filePath, fileBytes);
      materialized.push({
        ...attachment,
        dataBase64: undefined,
        localPath: filePath,
        sizeBytes: attachment.sizeBytes ?? fileBytes.byteLength,
      });
    }

    return materialized;
  }

  async clear(): Promise<void> {
    await rm(this.rootDir, { recursive: true, force: true });
  }
}

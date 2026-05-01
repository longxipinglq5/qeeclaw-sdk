import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import type { ChannelKey } from "../types.js";

export type ChannelSecretRecord = {
  channel: ChannelKey;
  enabled?: boolean;
  credentials?: Record<string, string>;
  updatedAt?: string;
};

export type ChannelSecretsFile = {
  version: 1;
  channels: Partial<Record<ChannelKey, ChannelSecretRecord>>;
};

function emptySecretsFile(): ChannelSecretsFile {
  return {
    version: 1,
    channels: {},
  };
}

function redactCredentials(credentials?: Record<string, string>): Record<string, boolean> {
  const redacted: Record<string, boolean> = {};
  for (const [key, value] of Object.entries(credentials || {})) {
    redacted[key] = Boolean(value?.trim());
  }
  return redacted;
}

export class ChannelSecretStore {
  constructor(private readonly filePath: string) {}

  async read(): Promise<ChannelSecretsFile> {
    try {
      const raw = await readFile(this.filePath, "utf8");
      const parsed = JSON.parse(raw) as ChannelSecretsFile;
      if (parsed?.version === 1 && parsed.channels && typeof parsed.channels === "object") {
        return parsed;
      }
      return emptySecretsFile();
    } catch {
      return emptySecretsFile();
    }
  }

  async write(next: ChannelSecretsFile): Promise<ChannelSecretsFile> {
    await mkdir(path.dirname(this.filePath), { recursive: true });
    await writeFile(this.filePath, JSON.stringify(next, null, 2));
    return next;
  }

  async get(channel: ChannelKey): Promise<ChannelSecretRecord | undefined> {
    const current = await this.read();
    return current.channels[channel];
  }

  async patch(channel: ChannelKey, patch: Omit<Partial<ChannelSecretRecord>, "channel">): Promise<ChannelSecretRecord> {
    const current = await this.read();
    const nextRecord: ChannelSecretRecord = {
      channel,
      ...(current.channels[channel] || {}),
      ...patch,
      credentials: {
        ...(current.channels[channel]?.credentials || {}),
        ...(patch.credentials || {}),
      },
      updatedAt: new Date().toISOString(),
    };
    await this.write({
      version: 1,
      channels: {
        ...current.channels,
        [channel]: nextRecord,
      },
    });
    return nextRecord;
  }

  async publicStatus(): Promise<Array<{ channel: ChannelKey; enabled: boolean; credentials: Record<string, boolean>; updatedAt?: string }>> {
    const current = await this.read();
    return Object.values(current.channels)
      .filter((record): record is ChannelSecretRecord => Boolean(record))
      .map((record) => ({
        channel: record.channel,
        enabled: Boolean(record.enabled),
        credentials: redactCredentials(record.credentials),
        updatedAt: record.updatedAt,
      }));
  }
}

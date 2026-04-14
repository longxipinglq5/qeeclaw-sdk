import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import type { KnowledgeConfig, KnowledgeInventoryItem } from "../types.js";

type KnowledgeWorkerState = {
  watchDir?: string;
  lastSyncedAt?: string;
  items?: KnowledgeInventoryItem[];
};

const DEFAULT_IGNORED_DIRS = new Set([".git", "node_modules", ".pnpm-store", ".DS_Store"]);

async function scanDir(rootDir: string, currentDir: string, items: KnowledgeInventoryItem[], limit: number): Promise<void> {
  if (items.length >= limit) {
    return;
  }

  const entries = await readdir(currentDir, { withFileTypes: true });
  for (const entry of entries) {
    if (items.length >= limit) {
      return;
    }

    const absolutePath = path.join(currentDir, entry.name);
    if (entry.isDirectory()) {
      if (!DEFAULT_IGNORED_DIRS.has(entry.name)) {
        await scanDir(rootDir, absolutePath, items, limit);
      }
      continue;
    }

    if (!entry.isFile()) {
      continue;
    }

    const fileStat = await stat(absolutePath);
    items.push({
      relativePath: path.relative(rootDir, absolutePath),
      absolutePath,
      size: fileStat.size,
      modifiedAt: fileStat.mtime.toISOString(),
      extension: path.extname(entry.name).replace(/^\./, "").toLowerCase(),
    });
  }
}

export class KnowledgeWorker {
  constructor(private readonly configFilePath: string) {}

  private async readState(): Promise<KnowledgeWorkerState> {
    try {
      const raw = await readFile(this.configFilePath, "utf8");
      return JSON.parse(raw) as KnowledgeWorkerState;
    } catch {
      return {};
    }
  }

  private async writeState(nextState: KnowledgeWorkerState): Promise<void> {
    await mkdir(path.dirname(this.configFilePath), { recursive: true });
    await writeFile(this.configFilePath, JSON.stringify(nextState, null, 2));
  }

  async getConfig(): Promise<KnowledgeConfig> {
    const state = await this.readState();
    return {
      watchDir: state.watchDir,
      lastSyncedAt: state.lastSyncedAt,
      inventoryCount: state.items?.length || 0,
      items: state.items || [],
    };
  }

  async updateConfig(patch: { watchDir?: string }): Promise<KnowledgeConfig> {
    const current = await this.readState();
    const nextState: KnowledgeWorkerState = {
      ...current,
      ...patch,
    };
    await this.writeState(nextState);
    return this.getConfig();
  }

  async sync(limit = 500): Promise<KnowledgeConfig> {
    const current = await this.readState();
    if (!current.watchDir) {
      throw new Error("Knowledge watchDir is not configured");
    }

    const items: KnowledgeInventoryItem[] = [];
    await scanDir(current.watchDir, current.watchDir, items, limit);
    const nextState: KnowledgeWorkerState = {
      ...current,
      items,
      lastSyncedAt: new Date().toISOString(),
    };
    await this.writeState(nextState);
    return this.getConfig();
  }
}

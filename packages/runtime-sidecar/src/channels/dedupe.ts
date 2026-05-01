export class ChannelDedupeStore {
  private readonly seen = new Map<string, number>();

  constructor(private readonly ttlMs = 5 * 60 * 1000) {}

  isDuplicate(key: string, nowMs = Date.now()): boolean {
    this.cleanup(nowMs);
    if (this.seen.has(key)) {
      return true;
    }
    this.seen.set(key, nowMs);
    return false;
  }

  cleanup(nowMs = Date.now()): void {
    for (const [key, recordedAt] of this.seen.entries()) {
      if (nowMs - recordedAt > this.ttlMs) {
        this.seen.delete(key);
      }
    }
  }

  size(): number {
    this.cleanup();
    return this.seen.size;
  }
}

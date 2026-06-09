// Protocol-level cache/test helper for webhook safety and provider duplicate suppression.
// Bridge owns product timeline, inbox, outbox, approval, read receipt, and retry semantics.

export type ProtocolInboxEntry = {
  dedupeKey: string;
  receivedAt: string;
};

export class ProtocolInboxStore {
  private readonly records = new Map<string, ProtocolInboxEntry>();

  record(entry: ProtocolInboxEntry): ProtocolInboxEntry {
    const existing = this.records.get(entry.dedupeKey);
    if (existing) return existing;
    this.records.set(entry.dedupeKey, entry);
    return entry;
  }

  has(dedupeKey: string): boolean {
    return this.records.has(dedupeKey);
  }

  list(): ProtocolInboxEntry[] {
    return Array.from(this.records.values());
  }
}

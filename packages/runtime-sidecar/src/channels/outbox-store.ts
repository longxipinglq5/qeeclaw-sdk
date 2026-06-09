// Protocol-level cache/test helper for webhook safety and provider duplicate suppression.
// Bridge owns product timeline, inbox, outbox, approval, read receipt, and retry semantics.

export type ProtocolOutboxEntry = {
  dedupeKey: string;
  providerMessageId?: string;
};

export class ProtocolOutboxStore {
  private readonly records = new Map<string, ProtocolOutboxEntry>();

  record(entry: ProtocolOutboxEntry): ProtocolOutboxEntry {
    const existing = this.records.get(entry.dedupeKey);
    if (existing) return existing;
    this.records.set(entry.dedupeKey, entry);
    return entry;
  }

  list(): ProtocolOutboxEntry[] {
    return Array.from(this.records.values());
  }
}

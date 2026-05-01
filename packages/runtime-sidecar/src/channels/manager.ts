import type { ChannelManagerStatus, ChannelMessage, ChannelRouteResult } from "../types.js";
import { ChannelAttachmentStore } from "./attachment-store.js";
import { ChannelDedupeStore } from "./dedupe.js";
import type { ChannelAdapter, ChannelRuntimeInvoker } from "./types.js";

type ChannelManagerOptions = {
  invoker: ChannelRuntimeInvoker;
  attachmentStore: ChannelAttachmentStore;
  adapters?: ChannelAdapter[];
  logger?: {
    log(message: string): void;
    error(message: string): void;
  };
};

export class ChannelManager {
  private readonly adapters = new Map<ChannelMessage["channel"], ChannelAdapter>();
  private readonly dedupe = new ChannelDedupeStore();
  private running = false;

  constructor(private readonly options: ChannelManagerOptions) {
    for (const adapter of options.adapters ?? []) {
      this.registerAdapter(adapter);
    }
  }

  registerAdapter(adapter: ChannelAdapter): void {
    this.adapters.set(adapter.channel, adapter);
  }

  async addAdapter(adapter: ChannelAdapter): Promise<void> {
    this.registerAdapter(adapter);
    if (this.running) {
      await adapter.start({
        emitMessage: (message) => this.routeMessage(message).then(() => undefined),
        log: (message) => this.options.logger?.log(message) ?? console.log(message),
        error: (message) => this.options.logger?.error(message) ?? console.error(message),
      });
    }
  }

  async replaceAdapter(adapter: ChannelAdapter): Promise<void> {
    await this.removeAdapter(adapter.channel);
    await this.addAdapter(adapter);
  }

  async removeAdapter(channel: ChannelMessage["channel"]): Promise<boolean> {
    const existing = this.adapters.get(channel);
    if (!existing) {
      return false;
    }
    if (this.running) {
      await existing.stop();
    }
    this.adapters.delete(channel);
    return true;
  }

  async start(): Promise<void> {
    if (this.running) {
      return;
    }
    this.running = true;
    await Promise.all(
      Array.from(this.adapters.values()).map((adapter) =>
        adapter.start({
          emitMessage: (message) => this.routeMessage(message).then(() => undefined),
          log: (message) => this.options.logger?.log(message) ?? console.log(message),
          error: (message) => this.options.logger?.error(message) ?? console.error(message),
        }),
      ),
    );
  }

  async stop(): Promise<void> {
    await Promise.all(Array.from(this.adapters.values()).map((adapter) => adapter.stop()));
    this.running = false;
  }

  async routeMessage(message: ChannelMessage): Promise<ChannelRouteResult> {
    const dedupeKey = `${message.channel}:${message.messageId}`;
    if (this.dedupe.isDuplicate(dedupeKey)) {
      return {
        accepted: false,
        duplicate: true,
        messageId: message.messageId,
        channel: message.channel,
      };
    }

    const adapter = this.adapters.get(message.channel);
    if (!adapter) {
      throw new Error(`No channel adapter registered for ${message.channel}`);
    }

    const materializedAttachments = await this.options.attachmentStore.materialize(message.attachments);
    const normalizedMessage = {
      ...message,
      attachments: materializedAttachments,
    };
    const reply = await this.options.invoker.invoke(normalizedMessage);
    await adapter.sendReply(normalizedMessage, reply);

    return {
      accepted: true,
      duplicate: false,
      messageId: message.messageId,
      channel: message.channel,
      reply,
    };
  }

  getStatus(): ChannelManagerStatus {
    return {
      running: this.running,
      adapters: Array.from(this.adapters.values()).map((adapter) => adapter.getStatus()),
    };
  }
}

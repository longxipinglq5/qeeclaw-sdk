import type { ChannelAdapterStatus, ChannelMessage, ChannelReply } from "../types.js";

export type ChannelAdapterContext = {
  emitMessage(message: ChannelMessage): Promise<void>;
  log(message: string): void;
  error(message: string): void;
};

export interface ChannelAdapter {
  readonly channel: ChannelMessage["channel"];
  start(context: ChannelAdapterContext): Promise<void>;
  stop(): Promise<void>;
  sendReply(message: ChannelMessage, reply: ChannelReply): Promise<void>;
  getStatus(): ChannelAdapterStatus;
}

export interface ChannelRuntimeInvoker {
  invoke(message: ChannelMessage): Promise<ChannelReply>;
}

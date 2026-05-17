import { HttpClient } from "../client/http-client.js";
import type { QeeClawEndpointConfig } from "../types.js";
import { KnowledgeModule } from "../modules/knowledge.js";
import { MemoryModule } from "../modules/memory.js";
import { ChatApi } from "../modules/llm/chat-completions.js";
import { ImagesApi } from "../modules/llm/images.js";
import { VideosApi } from "../modules/llm/videos.js";

export class LocalNamespace {
  readonly chat: ChatApi;
  readonly images: ImagesApi;
  readonly videos: VideosApi;
  readonly knowledge: KnowledgeModule;
  readonly memory: MemoryModule;

  constructor(config: QeeClawEndpointConfig) {
    const http = new HttpClient(config);
    this.chat = new ChatApi(http);
    this.images = new ImagesApi(http);
    this.videos = new VideosApi(http);
    this.knowledge = new KnowledgeModule(http);
    this.memory = new MemoryModule(http);
  }
}

import type { HttpClient } from "../../client/http-client.js";
import type {
  ChatCompletion,
  ChatCompletionCreateParams,
} from "./types.js";

export class ChatCompletionsApi {
  constructor(private readonly http: HttpClient) {}

  async create(params: ChatCompletionCreateParams): Promise<ChatCompletion> {
    const body: Record<string, unknown> = { ...params, ...params.extra };
    if (params.stream) {
      return this.http.requestRaw({
        method: "POST",
        path: "/v1/chat/completions",
        headers: { Accept: "text/event-stream" },
        body,
      }).then(r => r as unknown as ChatCompletion);
    }
    return this.http.request<ChatCompletion>({
      method: "POST",
      path: "/v1/chat/completions",
      body,
    });
  }
}

export class ChatApi {
  readonly completions: ChatCompletionsApi;

  constructor(http: HttpClient) {
    this.completions = new ChatCompletionsApi(http);
  }
}

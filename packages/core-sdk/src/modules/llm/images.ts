import type { HttpClient } from "../../client/http-client.js";
import type { ImageGenerateParams, ImageGenerateResult } from "./types.js";

export class ImagesApi {
  constructor(private readonly http: HttpClient) {}

  async generate(params: ImageGenerateParams): Promise<ImageGenerateResult> {
    const body: Record<string, unknown> = { ...params, ...params.extra };
    if (params.stream) {
      return this.http.requestRaw({
        method: "POST",
        path: "/v1/images/generations",
        headers: { Accept: "text/event-stream" },
        body,
      }).then(r => r as unknown as ImageGenerateResult);
    }
    return this.http.request<ImageGenerateResult>({
      method: "POST",
      path: "/v1/images/generations",
      body,
    });
  }
}

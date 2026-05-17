import type { HttpClient } from "../../client/http-client.js";
import type { VideoGenerateParams, VideoGenerateResult } from "./types.js";

export class VideosApi {
  constructor(private readonly http: HttpClient) {}

  async generate(params: VideoGenerateParams): Promise<VideoGenerateResult> {
    const body: Record<string, unknown> = { ...params, ...params.extra };
    return this.http.request<VideoGenerateResult>({
      method: "POST",
      path: "/v1/video/generations",
      body,
    });
  }
}

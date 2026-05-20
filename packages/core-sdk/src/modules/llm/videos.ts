import type { HttpClient } from "../../client/http-client.js";
import type {
  VideoGenerateParams,
  VideoGenerateResult,
  VideoTaskPollParams,
  VideoTaskPollResult,
} from "./types.js";

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

  async getResult(params: VideoTaskPollParams): Promise<VideoTaskPollResult> {
    const query: Record<string, string> = {};
    if (params.model) {
      query.model = params.model;
    }
    return this.http.request<VideoTaskPollResult>({
      method: "GET",
      path: `/v1/video/generations/${encodeURIComponent(params.task_id)}`,
      query,
    });
  }

  async waitForResult(
    params: VideoTaskPollParams & {
      pollIntervalMs?: number;
      maxAttempts?: number;
    },
  ): Promise<VideoTaskPollResult> {
    const intervalMs = params.pollIntervalMs ?? 5000;
    const maxAttempts = params.maxAttempts ?? 120;
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const result = await this.getResult(params);
      if (result.status === "completed" || result.status === "failed") {
        return result;
      }
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
    throw new Error(
      `Video generation timed out after ${maxAttempts} polling attempts`,
    );
  }
}

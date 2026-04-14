/**
 * OpenClawAdapter — OpenClaw Runtime 适配器（可选打包项）
 *
 * 将现有的 ModelsModule.invoke() 逻辑包装为 RuntimeAdapter 实现。
 * SDK 默认不包含此模块，仅在打包时通过 --with-openclaw 标志引入。
 */

import type { HttpClient } from "../client/http-client.js";
import type {
  RuntimeAdapter,
  RuntimeCapabilities,
  RuntimeHealthCheck,
  RuntimeInvokeRequest,
  RuntimeInvokeResult,
} from "./types.js";

interface RawInvokeResult {
  text: string;
  model?: string;
  provider_name?: string;
  provider_model_id?: string;
}

export class OpenClawAdapter implements RuntimeAdapter {
  readonly type = "openclaw" as const;

  constructor(private readonly http: HttpClient) {}

  getCapabilities(): RuntimeCapabilities {
    return {
      supportsStreaming: false,
      supportsToolCalls: false,
      supportsMemory: false,
      supportsSkills: false,
      supportsGateway: false,
      supportedProviders: ["platform"],
    };
  }

  async healthCheck(): Promise<RuntimeHealthCheck> {
    try {
      await this.http.request<unknown[]>({
        method: "GET",
        path: "/api/platform/models",
      });
      return {
        ok: true,
        runtimeType: "openclaw",
        message: "OpenClaw platform API is reachable.",
      };
    } catch (error) {
      return {
        ok: false,
        runtimeType: "openclaw",
        message: error instanceof Error ? error.message : String(error),
      };
    }
  }

  async invoke(request: RuntimeInvokeRequest): Promise<RuntimeInvokeResult> {
    const result = await this.http.request<RawInvokeResult>({
      method: "POST",
      path: "/api/platform/models/invoke",
      body: {
        prompt: request.prompt,
        model: request.model,
        max_tokens: request.maxTokens,
        temperature: request.temperature,
      },
    });

    return {
      text: result.text,
      model: result.model,
      provider: result.provider_name,
    };
  }

  async start(): Promise<void> {
    // OpenClaw 通过远程 HTTP API 调用，无需启动子进程
  }

  async stop(): Promise<void> {
    // 无需清理
  }
}

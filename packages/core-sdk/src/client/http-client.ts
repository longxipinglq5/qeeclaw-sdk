import { QeeClawApiError, QeeClawTimeoutError } from "../errors.js";
import type {
  QeeClawClientOptions,
  QeeClawRequestOptions,
  QeeClawResponseEnvelope,
} from "../types.js";

const DEFAULT_TIMEOUT_MS = 15000;

function joinUrl(baseUrl: string, path: string): string {
  const normalizedBase = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBase}${normalizedPath}`;
}

function appendQuery(url: URL, query?: QeeClawRequestOptions["query"]): void {
  if (!query) {
    return;
  }

  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) {
      continue;
    }
    url.searchParams.set(key, String(value));
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Object.prototype.toString.call(value) === "[object Object]";
}

function isEnvelope<T>(value: unknown): value is QeeClawResponseEnvelope<T> {
  return Boolean(
    value &&
      typeof value === "object" &&
      "code" in value &&
      typeof (value as { code?: unknown }).code === "number",
  );
}

function getMessage(value: unknown, fallback: string): string {
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const message = record.message ?? record.msg ?? record.detail;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  }
  return fallback;
}

interface BinaryResponsePayload {
  data: Uint8Array;
  contentType: string;
  contentDisposition: string | null;
}

export class HttpClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly headers: Record<string, string>;
  private readonly timeoutMs: number;
  private readonly token?: string;

  constructor(options: QeeClawClientOptions) {
    this.baseUrl = options.baseUrl;
    const resolvedFetch = options.fetch ?? globalThis.fetch;
    this.fetchImpl = ((input: RequestInfo | URL, init?: RequestInit) =>
      resolvedFetch.call(globalThis, input, init)) as typeof fetch;
    this.headers = {
      Accept: "application/json",
      ...(options.userAgent ? { "X-QeeClaw-SDK": options.userAgent } : {}),
      ...(options.headers ?? {}),
    };
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.token = options.token;
  }

  private async fetchResponse(options: QeeClawRequestOptions): Promise<Response> {
    const url = new URL(joinUrl(this.baseUrl, options.path));
    appendQuery(url, options.query);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    const headers = new Headers(this.headers);
    for (const [key, value] of Object.entries(options.headers ?? {})) {
      headers.set(key, value);
    }

    const token = options.token ?? this.token;
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    let body: BodyInit | undefined;
    if (options.body !== undefined) {
      if (
        typeof FormData !== "undefined" &&
        options.body instanceof FormData
      ) {
        body = options.body;
      } else if (
        typeof URLSearchParams !== "undefined" &&
        options.body instanceof URLSearchParams
      ) {
        body = options.body;
      } else if (
        typeof Blob !== "undefined" &&
        options.body instanceof Blob
      ) {
        body = options.body;
      } else if (
        typeof ArrayBuffer !== "undefined" &&
        options.body instanceof ArrayBuffer
      ) {
        body = options.body as unknown as BodyInit;
      } else if (
        typeof Uint8Array !== "undefined" &&
        options.body instanceof Uint8Array
      ) {
        body = options.body as unknown as BodyInit;
      } else if (typeof options.body === "string") {
        body = options.body;
      } else if (isPlainObject(options.body)) {
        headers.set("Content-Type", "application/json");
        body = JSON.stringify(options.body);
      } else {
        body = options.body as BodyInit;
      }
    }

    try {
      return await this.fetchImpl(url, {
        method: options.method ?? "GET",
        headers,
        body,
        signal: options.signal ?? controller.signal,
      });
    } catch (error) {
      if (
        error instanceof Error &&
        error.name === "AbortError"
      ) {
        throw new QeeClawTimeoutError("QeeClaw request timed out", {
          cause: error,
        });
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async request<T>(options: QeeClawRequestOptions): Promise<T> {
    const response = await this.fetchResponse(options);
    const contentType = response.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json");
    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      throw new QeeClawApiError(getMessage(payload, `HTTP ${response.status}`), {
        status: response.status,
        details: payload,
      });
    }

    if (isEnvelope<T>(payload)) {
      if (payload.code !== 0) {
        throw new QeeClawApiError(getMessage(payload, "QeeClaw API request failed"), {
          status: response.status,
          code: payload.code,
          details: payload,
        });
      }
      return payload.data;
    }

    return payload as T;
  }

  async requestBinaryResponse(options: QeeClawRequestOptions): Promise<BinaryResponsePayload> {
    const response = await this.fetchResponse(options);
    const contentType = response.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json");

    if (isJson) {
      const payload = await response.json();
      if (!response.ok) {
        throw new QeeClawApiError(getMessage(payload, `HTTP ${response.status}`), {
          status: response.status,
          details: payload,
        });
      }
      if (isEnvelope<never>(payload)) {
        if (payload.code !== 0) {
          throw new QeeClawApiError(getMessage(payload, "QeeClaw API request failed"), {
            status: response.status,
            code: payload.code,
            details: payload,
          });
        }
      }
      throw new QeeClawApiError("Expected binary response but received JSON payload", {
        status: response.status,
        details: payload,
      });
    }

    if (!response.ok) {
      const payload = await response.text();
      throw new QeeClawApiError(getMessage(payload, `HTTP ${response.status}`), {
        status: response.status,
        details: payload,
      });
    }

    return {
      data: new Uint8Array(await response.arrayBuffer()),
      contentType,
      contentDisposition: response.headers.get("content-disposition"),
    };
  }

  async requestBinary(options: QeeClawRequestOptions): Promise<Uint8Array> {
    const response = await this.requestBinaryResponse(options);
    return response.data;
  }
}

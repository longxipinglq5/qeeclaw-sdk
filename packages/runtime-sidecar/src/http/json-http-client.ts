export class JsonHttpError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload?: unknown,
  ) {
    super(message);
    this.name = "JsonHttpError";
  }
}

export class JsonHttpClient {
  constructor(private readonly baseUrl: string, private readonly fetchImpl: typeof fetch = fetch) {}

  async request<T>(params: {
    method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    path: string;
    token?: string;
    query?: Record<string, string | number | boolean | undefined | null>;
    body?: unknown;
  }): Promise<T> {
    const url = new URL(params.path, `${this.baseUrl}/`);
    Object.entries(params.query || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });

    const response = await this.fetchImpl(url, {
      method: params.method,
      headers: {
        "Content-Type": "application/json",
        ...(params.token ? { Authorization: `Bearer ${params.token}` } : {}),
      },
      body: params.body === undefined ? undefined : JSON.stringify(params.body),
    });

    const text = await response.text();
    const contentType = response.headers.get("content-type") || "";
    const isJson = contentType.includes("application/json");
    let payload: unknown;
    if (text) {
      if (isJson) {
        try {
          payload = JSON.parse(text);
        } catch {
          payload = text;
        }
      } else {
        payload = text;
      }
    }

    if (!response.ok) {
      const message =
        (payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string"
          ? payload.detail
          : undefined) ||
        (payload && typeof payload === "object" && "message" in payload && typeof payload.message === "string"
          ? payload.message
          : undefined) ||
        (typeof payload === "string" && payload.trim() ? payload.trim() : undefined) ||
        `${response.status} ${response.statusText}`;
      throw new JsonHttpError(message, response.status, payload);
    }

    if (payload && typeof payload === "object" && "code" in payload) {
      const envelope = payload as { code: number; data: T; message?: string; detail?: string };
      if (envelope.code !== 0) {
        throw new JsonHttpError(envelope.message || envelope.detail || "Platform request failed", response.status, envelope);
      }
      return envelope.data;
    }

    return payload as T;
  }
}

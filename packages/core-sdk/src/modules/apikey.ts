import type { HttpClient } from "../client/http-client.js";
import type { JsonValue, PaginatedResult } from "../types.js";

export type AppKeyRole = "ADMIN" | "USER" | string;

export interface AppKeyRecord {
  id: number;
  appKey: string;
  keyName?: string | null;
  role: AppKeyRole;
  isActive: boolean;
  expireTime?: string | null;
  createTime: string;
}

interface RawAppKeyRecord {
  id: number;
  app_key: string;
  key_name?: string | null;
  role: AppKeyRole;
  is_active: boolean;
  expire_time?: string | null;
  create_time: string;
}

interface RawAppKeyListResponse {
  total: number;
  page: number;
  page_size: number;
  items: RawAppKeyRecord[];
}

export interface AppKeySecret {
  id: number;
  appKey: string;
  appSecret: string;
}

interface RawAppKeySecret {
  id: number;
  app_key: string;
  app_secret: string;
}

export interface AppToken {
  token: string;
  expiresIn: number;
  appKey: string;
  appKeyId: number;
}

interface RawAppToken {
  token: string;
  expires_in: number;
  app_key: string;
  app_key_id: number;
}

export interface AppKeyListParams {
  page?: number;
  pageSize?: number;
}

export interface LLMKeyRecord {
  id: number;
  key: string;
  name?: string | null;
  description?: string | null;
  limitConfig?: Record<string, JsonValue> | null;
  expireTime?: string | null;
  isActive: boolean;
  createdTime: string;
}

interface RawLLMKeyRecord {
  id: number;
  key: string;
  name?: string | null;
  description?: string | null;
  limit_config?: Record<string, JsonValue> | null;
  expire_time?: string | null;
  is_active: boolean;
  created_time: string;
}

export interface CreateLLMKeyRequest {
  name: string;
  description?: string;
  expireTime?: string;
  limitConfig?: Record<string, JsonValue>;
}

export interface UpdateLLMKeyRequest {
  name?: string;
  description?: string | null;
  expireTime?: string | null;
  isActive?: boolean;
}

function mapAppKeyRecord(value: RawAppKeyRecord): AppKeyRecord {
  return {
    id: value.id,
    appKey: value.app_key,
    keyName: value.key_name,
    role: value.role,
    isActive: value.is_active,
    expireTime: value.expire_time,
    createTime: value.create_time,
  };
}

function mapLLMKeyRecord(value: RawLLMKeyRecord): LLMKeyRecord {
  return {
    id: value.id,
    key: value.key,
    name: value.name,
    description: value.description,
    limitConfig: value.limit_config,
    expireTime: value.expire_time,
    isActive: value.is_active,
    createdTime: value.created_time,
  };
}

export class ApiKeyModule {
  constructor(private readonly http: HttpClient) {}

  async list(params: AppKeyListParams = {}): Promise<PaginatedResult<AppKeyRecord>> {
    const result = await this.http.request<RawAppKeyListResponse>({
      method: "GET",
      path: "/api/users/app-keys",
      query: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
      },
    });
    return {
      total: result.total,
      page: result.page,
      pageSize: result.page_size,
      items: result.items.map(mapAppKeyRecord),
    };
  }

  async create(): Promise<AppKeySecret> {
    const result = await this.http.request<RawAppKeySecret>({
      method: "POST",
      path: "/api/users/app-keys",
    });
    return {
      id: result.id,
      appKey: result.app_key,
      appSecret: result.app_secret,
    };
  }

  async remove(appKeyId: number): Promise<void> {
    await this.http.request<null>({
      method: "DELETE",
      path: `/api/users/app-keys/${appKeyId}`,
    });
  }

  async setActive(appKeyId: number, isActive: boolean): Promise<void> {
    await this.http.request<null>({
      method: "PATCH",
      path: `/api/users/app-keys/${appKeyId}`,
      body: {
        is_active: isActive,
      },
    });
  }

  async rename(appKeyId: number, keyName: string): Promise<void> {
    await this.http.request<null>({
      method: "PUT",
      path: `/api/users/app-keys/${appKeyId}/name`,
      body: {
        key_name: keyName,
      },
    });
  }

  async issueDefaultToken(): Promise<AppToken> {
    const result = await this.http.request<RawAppToken>({
      method: "POST",
      path: "/api/users/app-keys/default/token",
    });
    return {
      token: result.token,
      expiresIn: result.expires_in,
      appKey: result.app_key,
      appKeyId: result.app_key_id,
    };
  }

  async listLLMKeys(): Promise<LLMKeyRecord[]> {
    const result = await this.http.request<RawLLMKeyRecord[]>({
      method: "GET",
      path: "/api/llm/keys",
    });
    return result.map(mapLLMKeyRecord);
  }

  async createLLMKey(payload: CreateLLMKeyRequest): Promise<LLMKeyRecord> {
    const result = await this.http.request<RawLLMKeyRecord>({
      method: "POST",
      path: "/api/llm/keys",
      body: {
        name: payload.name,
        description: payload.description,
        expire_time: payload.expireTime,
        limit_config: payload.limitConfig,
      },
    });
    return mapLLMKeyRecord(result);
  }

  async updateLLMKey(keyId: number, payload: UpdateLLMKeyRequest): Promise<LLMKeyRecord> {
    const result = await this.http.request<RawLLMKeyRecord>({
      method: "PUT",
      path: `/api/llm/keys/${keyId}`,
      body: {
        name: payload.name,
        description: payload.description,
        expire_time: payload.expireTime,
        is_active: payload.isActive,
      },
    });
    return mapLLMKeyRecord(result);
  }

  async removeLLMKey(keyId: number): Promise<void> {
    await this.http.request<null>({
      method: "DELETE",
      path: `/api/llm/keys/${keyId}`,
    });
  }
}

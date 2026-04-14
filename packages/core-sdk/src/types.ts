export type Primitive = string | number | boolean | null;

export type JsonValue =
  | Primitive
  | { [key: string]: JsonValue }
  | JsonValue[];

export interface QeeClawResponseEnvelope<T> {
  code: number;
  data: T;
  message?: string;
  msg?: string;
  detail?: string;
}

export interface QeeClawAuthContext {
  token?: string;
}

export interface QeeClawClientOptions extends QeeClawAuthContext {
  baseUrl: string;
  fetch?: typeof fetch;
  headers?: Record<string, string>;
  timeoutMs?: number;
  userAgent?: string;
}

export interface QeeClawRequestOptions extends QeeClawAuthContext {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: BodyInit | Record<string, unknown>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export interface PaginatedResult<T> {
  total: number;
  page: number;
  pageSize: number;
  items: T[];
}

export interface Tenant {
  id: string;
  name: string;
}

export interface Team {
  id: string | number;
  name: string;
  tenantId?: string | number;
  isPersonal?: boolean;
  ownerId?: string | number;
}

export interface Identity {
  id: string | number;
  type: "user" | "agent" | "device" | "channel";
  name?: string;
}

export interface Agent {
  id: string | number;
  name: string;
  teamId?: string | number;
}

export interface Device {
  id: string | number;
  deviceName?: string;
  deviceType?: string;
  status?: string;
  teamId?: string | number;
}

export interface Channel {
  id: string | number;
  type: string;
  name?: string;
}

export interface MemoryEntry {
  id?: string;
  content: string;
  category?: string;
  importance?: number;
  deviceId?: string | null;
  agentId?: string | null;
  sourceSession?: string | null;
}

export interface KnowledgeAsset {
  sourceName: string;
  size?: number;
  status?: string;
  metadata?: Record<string, JsonValue>;
}

export interface PolicyDecision {
  allowed: boolean;
  reason?: string;
  matchedPolicy?: string;
}

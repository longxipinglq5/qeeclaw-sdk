import type { HttpClient } from "../client/http-client.js";
import type { PaginatedResult, Team } from "../types.js";

export type QeeClawUserRole = "ADMIN" | "USER" | string;

export interface TeamMembership extends Team {
  id: number;
  name: string;
  isPersonal: boolean;
  ownerId: number;
}

interface RawTeamMembership {
  id: number;
  name: string;
  is_personal: boolean;
  owner_id: number;
}

export interface UserProfile {
  id: number;
  username: string;
  fullName?: string | null;
  email?: string | null;
  phone?: string | null;
  role: QeeClawUserRole;
  isActive: boolean;
  lastLoginTime?: string | null;
  createdTime: string;
  walletBalance: number;
  isEnterpriseVerified: boolean;
  teams: TeamMembership[];
}

interface RawUserProfile {
  id: number;
  username: string;
  full_name?: string | null;
  email?: string | null;
  phone?: string | null;
  role: QeeClawUserRole;
  is_active: boolean;
  last_login_time?: string | null;
  created_time: string;
  wallet_balance?: number;
  is_enterprise_verified?: boolean;
  teams?: RawTeamMembership[];
}

interface RawUserListResponse {
  total: number;
  page: number;
  page_size: number;
  items: RawUserProfile[];
}

export interface UserProfileUpdateRequest {
  fullName?: string;
  email?: string;
  phone?: string;
}

export interface UserPreference {
  preferredModel: string;
}

interface RawUserPreference {
  preferred_model: string;
}

export interface UserListParams {
  page?: number;
  pageSize?: number;
  keyword?: string;
}

export interface UserProduct {
  id: number;
  name: string;
  description?: string | null;
  unitPrice: number;
  outputUnitPrice?: number | null;
  currency: string;
  billingMode?: string | null;
  durationUnitSec: number;
  durationMinAmount: number;
  textUnitChars: number;
  textMinAmount: number;
  httpMethod?: string | null;
  apiPath?: string | null;
  docsUrl?: string | null;
  docId?: number | null;
  labels?: string | null;
  isActive: boolean;
  createTime: string;
  updateTime: string;
}

interface RawUserProduct {
  id: number;
  name: string;
  description?: string | null;
  unit_price: number;
  output_unit_price?: number | null;
  currency: string;
  billing_mode?: string | null;
  duration_unit_sec: number;
  duration_min_amount: number;
  text_unit_chars: number;
  text_min_amount: number;
  http_method?: string | null;
  api_path?: string | null;
  docs_url?: string | null;
  doc_id?: number | null;
  labels?: string | null;
  is_active: boolean;
  create_time: string;
  update_time: string;
}

function mapTeamMembership(value: RawTeamMembership): TeamMembership {
  return {
    id: value.id,
    name: value.name,
    isPersonal: value.is_personal,
    ownerId: value.owner_id,
  };
}

function mapUserProfile(value: RawUserProfile): UserProfile {
  return {
    id: value.id,
    username: value.username,
    fullName: value.full_name,
    email: value.email,
    phone: value.phone,
    role: value.role,
    isActive: value.is_active,
    lastLoginTime: value.last_login_time,
    createdTime: value.created_time,
    walletBalance: value.wallet_balance ?? 0,
    isEnterpriseVerified: value.is_enterprise_verified ?? false,
    teams: (value.teams ?? []).map(mapTeamMembership),
  };
}

function mapUserProduct(value: RawUserProduct): UserProduct {
  return {
    id: value.id,
    name: value.name,
    description: value.description,
    unitPrice: value.unit_price,
    outputUnitPrice: value.output_unit_price,
    currency: value.currency,
    billingMode: value.billing_mode,
    durationUnitSec: value.duration_unit_sec,
    durationMinAmount: value.duration_min_amount,
    textUnitChars: value.text_unit_chars,
    textMinAmount: value.text_min_amount,
    httpMethod: value.http_method,
    apiPath: value.api_path,
    docsUrl: value.docs_url,
    docId: value.doc_id,
    labels: value.labels,
    isActive: value.is_active,
    createTime: value.create_time,
    updateTime: value.update_time,
  };
}

export class IamModule {
  constructor(private readonly http: HttpClient) {}

  async getProfile(): Promise<UserProfile> {
    const result = await this.http.request<RawUserProfile>({
      method: "GET",
      path: "/api/users/me",
    });
    return mapUserProfile(result);
  }

  async updateProfile(payload: UserProfileUpdateRequest): Promise<UserProfile> {
    const result = await this.http.request<RawUserProfile>({
      method: "PUT",
      path: "/api/users/me",
      body: {
        full_name: payload.fullName,
        email: payload.email,
        phone: payload.phone,
      },
    });
    return mapUserProfile(result);
  }

  async updatePreference(preferredModel: string): Promise<UserPreference> {
    const result = await this.http.request<RawUserPreference>({
      method: "PUT",
      path: "/api/users/me/preference",
      body: {
        preferred_model: preferredModel,
      },
    });
    return {
      preferredModel: result.preferred_model,
    };
  }

  async listUsers(params: UserListParams = {}): Promise<PaginatedResult<UserProfile>> {
    const result = await this.http.request<RawUserListResponse>({
      method: "GET",
      path: "/api/users",
      query: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
        keyword: params.keyword,
      },
    });
    return {
      total: result.total,
      page: result.page,
      pageSize: result.page_size,
      items: result.items.map(mapUserProfile),
    };
  }

  async listProducts(): Promise<UserProduct[]> {
    const result = await this.http.request<RawUserProduct[]>({
      method: "GET",
      path: "/api/users/products",
    });
    return result.map(mapUserProduct);
  }
}

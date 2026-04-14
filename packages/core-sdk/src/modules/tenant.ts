import { QeeClawApiError } from "../errors.js";
import type { HttpClient } from "../client/http-client.js";
import type { Team } from "../types.js";

export type CompanyVerificationStatus = "none" | "pending" | "approved" | "rejected";

export interface TenantWorkspaceContext {
  userId: number;
  username: string;
  role: string;
  isEnterpriseVerified: boolean;
  teams: Team[];
  defaultTeamId?: number | null;
  defaultTeamName?: string | null;
  defaultTeamIsPersonal?: boolean | null;
}

interface RawTenantWorkspaceContext {
  id: number;
  username: string;
  role: string;
  is_enterprise_verified?: boolean;
  default_team_id?: number | null;
  default_team_name?: string | null;
  default_team_is_personal?: boolean | null;
  teams?: Array<{
    id: number;
    name: string;
    is_personal: boolean;
    owner_id: number;
  }>;
}

export interface CompanyVerificationRecord {
  status: CompanyVerificationStatus;
  companyName?: string | null;
  taxNumber?: string | null;
  address?: string | null;
  phone?: string | null;
  bankName?: string | null;
  bankAccount?: string | null;
  licenseUrl?: string | null;
  rejectionReason?: string | null;
  updatedTime?: string | null;
}

interface RawCompanyVerificationRecord {
  status: CompanyVerificationStatus;
  company_name?: string | null;
  tax_number?: string | null;
  address?: string | null;
  phone?: string | null;
  bank_name?: string | null;
  bank_account?: string | null;
  license_url?: string | null;
  rejection_reason?: string | null;
  updated_time?: string | null;
}

export interface CompanyVerificationSubmitRequest {
  companyName: string;
  taxNumber: string;
  address?: string;
  phone?: string;
  bankName?: string;
  bankAccount?: string;
  licenseFile?: Blob | Uint8Array | ArrayBuffer;
  licenseFilename?: string;
  licenseContentType?: string;
}

function buildBlob(
  value: Blob | Uint8Array | ArrayBuffer,
  contentType?: string,
): Blob {
  if (typeof Blob !== "undefined" && value instanceof Blob) {
    return value;
  }
  return new Blob([value as unknown as BlobPart], {
    type: contentType ?? "application/octet-stream",
  });
}

function mapCompanyVerification(value: RawCompanyVerificationRecord): CompanyVerificationRecord {
  return {
    status: value.status,
    companyName: value.company_name,
    taxNumber: value.tax_number,
    address: value.address,
    phone: value.phone,
    bankName: value.bank_name,
    bankAccount: value.bank_account,
    licenseUrl: value.license_url,
    rejectionReason: value.rejection_reason,
    updatedTime: value.updated_time,
  };
}

export class TenantModule {
  constructor(private readonly http: HttpClient) {}

  async getCurrentContext(): Promise<TenantWorkspaceContext> {
    let result: RawTenantWorkspaceContext;
    try {
      result = await this.http.request<RawTenantWorkspaceContext>({
        method: "GET",
        path: "/api/users/me/context",
      });
    } catch (error) {
      if (!(error instanceof QeeClawApiError) || error.status !== 404) {
        throw error;
      }

      result = await this.http.request<RawTenantWorkspaceContext>({
        method: "GET",
        path: "/api/users/me",
      });
    }
    return {
      userId: result.id,
      username: result.username,
      role: result.role,
      isEnterpriseVerified: result.is_enterprise_verified ?? false,
      defaultTeamId: result.default_team_id,
      defaultTeamName: result.default_team_name,
      defaultTeamIsPersonal: result.default_team_is_personal,
      teams: (result.teams ?? []).map((team) => ({
        id: team.id,
        name: team.name,
        isPersonal: team.is_personal,
        ownerId: team.owner_id,
      })),
    };
  }

  async getCompanyVerification(): Promise<CompanyVerificationRecord> {
    const result = await this.http.request<RawCompanyVerificationRecord>({
      method: "GET",
      path: "/api/company/verification",
    });
    return mapCompanyVerification(result);
  }

  async submitCompanyVerification(
    payload: CompanyVerificationSubmitRequest,
  ): Promise<CompanyVerificationRecord> {
    let body: FormData | URLSearchParams;
    if (payload.licenseFile !== undefined) {
      const form = new FormData();
      form.set("company_name", payload.companyName);
      form.set("tax_number", payload.taxNumber);
      form.set("address", payload.address ?? "");
      form.set("phone", payload.phone ?? "");
      form.set("bank_name", payload.bankName ?? "");
      form.set("bank_account", payload.bankAccount ?? "");
      const blob = buildBlob(payload.licenseFile, payload.licenseContentType);
      form.set("license_file", blob, payload.licenseFilename ?? "license.bin");
      body = form;
    } else {
      body = new URLSearchParams({
        company_name: payload.companyName,
        tax_number: payload.taxNumber,
        address: payload.address ?? "",
        phone: payload.phone ?? "",
        bank_name: payload.bankName ?? "",
        bank_account: payload.bankAccount ?? "",
      });
    }

    const result = await this.http.request<RawCompanyVerificationRecord>({
      method: "POST",
      path: "/api/company/verification",
      body,
    });
    return mapCompanyVerification(result);
  }

  async approveCompanyVerification(): Promise<void> {
    await this.http.request<null>({
      method: "POST",
      path: "/api/company/verification/approve",
    });
  }
}

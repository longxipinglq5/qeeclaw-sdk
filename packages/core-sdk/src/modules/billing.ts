import type { HttpClient } from "../client/http-client.js";
import type { PaginatedResult } from "../types.js";

export interface WalletSummary {
  balance: number;
  currency: string;
  totalSpent: number;
  totalRecharge: number;
  currentMonthSpent: number;
  updatedTime: string;
}

interface RawWalletSummary {
  balance: number;
  currency: string;
  total_spent: number;
  total_recharge: number;
  current_month_spent: number;
  updated_time: string;
}

export interface BillingRecord {
  id: number;
  productName: string;
  recordType: string;
  durationSeconds: number;
  textInputLength: number;
  textOutputLength: number;
  unitPrice: number;
  outputUnitPrice: number;
  amount: number;
  currency: string;
  remark?: string | null;
  balanceSnapshot: number;
  createdTime: string;
}

interface RawBillingRecord {
  id: number;
  product_name: string;
  record_type: string;
  duration_seconds: number;
  text_input_length: number;
  text_output_length: number;
  unit_price: number;
  output_unit_price: number;
  amount: number;
  currency: string;
  remark?: string | null;
  balance_snapshot: number;
  created_time: string;
}

interface RawBillingRecordListResponse {
  total: number;
  page: number;
  page_size: number;
  items: RawBillingRecord[];
}

export interface BillingTotals {
  totalSpent: number;
  totalRecharge: number;
}

interface RawBillingTotals {
  total_spent: number;
  total_recharge: number;
}

export interface BillingRecordListParams {
  page?: number;
  pageSize?: number;
  type?: "consumption" | "recharge" | "deduction" | string;
}

function mapWalletSummary(value: RawWalletSummary): WalletSummary {
  return {
    balance: value.balance,
    currency: value.currency,
    totalSpent: value.total_spent,
    totalRecharge: value.total_recharge,
    currentMonthSpent: value.current_month_spent,
    updatedTime: value.updated_time,
  };
}

function mapBillingRecord(value: RawBillingRecord): BillingRecord {
  return {
    id: value.id,
    productName: value.product_name,
    recordType: value.record_type,
    durationSeconds: value.duration_seconds,
    textInputLength: value.text_input_length,
    textOutputLength: value.text_output_length,
    unitPrice: value.unit_price,
    outputUnitPrice: value.output_unit_price,
    amount: value.amount,
    currency: value.currency,
    remark: value.remark,
    balanceSnapshot: value.balance_snapshot,
    createdTime: value.created_time,
  };
}

export class BillingModule {
  constructor(private readonly http: HttpClient) {}

  async getWallet(): Promise<WalletSummary> {
    const result = await this.http.request<RawWalletSummary>({
      method: "GET",
      path: "/api/billing/wallet",
    });
    return mapWalletSummary(result);
  }

  async listRecords(params: BillingRecordListParams = {}): Promise<PaginatedResult<BillingRecord>> {
    const result = await this.http.request<RawBillingRecordListResponse>({
      method: "GET",
      path: "/api/billing/records",
      query: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
        type: params.type,
      },
    });
    return {
      total: result.total,
      page: result.page,
      pageSize: result.page_size,
      items: result.items.map(mapBillingRecord),
    };
  }

  async getSummary(): Promise<BillingTotals> {
    const result = await this.http.request<RawBillingTotals>({
      method: "GET",
      path: "/api/billing/summary",
    });
    return {
      totalSpent: result.total_spent,
      totalRecharge: result.total_recharge,
    };
  }
}

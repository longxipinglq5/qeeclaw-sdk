import { QeeClawNotImplementedError } from "../errors.js";
import type { HttpClient } from "../client/http-client.js";

export interface QeeClawModelInfo {
  id: number;
  providerName: string;
  modelName: string;
  providerModelId?: string;
  modelType?: "chat" | "image" | string;
  label: string;
  isPreferred: boolean;
  availabilityStatus: string;
  unitPrice?: number;
  outputUnitPrice?: number;
  currency?: string;
  billingMode?: string;
  textUnitChars?: number;
  textMinAmount?: number;
}

interface RawModelInfo {
  id: number;
  provider_name: string;
  model_name: string;
  provider_model_id?: string;
  model_type?: "chat" | "image" | string;
  label: string;
  is_preferred: boolean;
  availability_status: string;
  unit_price?: number;
  output_unit_price?: number;
  currency?: string;
  billing_mode?: string;
  text_unit_chars?: number;
  text_min_amount?: number;
}

export interface ModelInvokeRequest {
  prompt: string;
  modelId?: string;
  model?: string;
  timeoutMs?: number;
}

export interface ModelInvokeResult {
  text: string;
  model?: string;
}

export interface ModelImageGenerationRequest {
  prompt: string;
  model?: string;
  n?: number;
  size?: string;
  quality?: string;
  responseFormat?: string;
  response_format?: string;
  background?: string;
  outputFormat?: string;
  output_format?: string;
  moderation?: string;
  stream?: boolean;
  partialImages?: number;
  partial_images?: number;
  user?: string;
  timeoutMs?: number;
  [key: string]: unknown;
}

export type ModelImageGenerationStreamRequest = ModelImageGenerationRequest & {
  stream: true;
};

export interface ModelImageData {
  url?: string;
  b64Json?: string;
  b64_json?: string;
  revisedPrompt?: string;
  revised_prompt?: string;
  [key: string]: unknown;
}

interface RawModelImageData {
  url?: string;
  b64_json?: string;
  revised_prompt?: string;
  [key: string]: unknown;
}

export interface ModelImageGenerationResult {
  created?: number;
  data: ModelImageData[];
  usage?: unknown;
  [key: string]: unknown;
}

interface RawModelImageGenerationResult {
  created?: number;
  data?: RawModelImageData[];
  usage?: unknown;
  [key: string]: unknown;
}

export interface ModelProviderSummary {
  providerName: string;
  configured?: boolean;
  providerStatus?: string;
  visibleCount: number;
  hiddenCount: number;
  disabledCount?: number;
  models: string[];
  preferredModelSupported?: boolean;
  isDefaultRouteProvider?: boolean;
  defaultRouteModel?: string | null;
  defaultRouteProviderModelId?: string | null;
}

export interface ModelRuntimeSummary {
  runtimeType: string;
  runtimeLabel: string;
  runtimeStatus: string;
  runtimeStage: string;
  isDefault: boolean;
  adapterRegistered: boolean;
  bridgeRegistered: boolean;
  onlineTeamCount: number;
  supportsImRelay: boolean;
  supportsDeviceBridge: boolean;
  supportsManagedDownload: boolean;
  notes: string;
}

interface RawModelProviderSummary {
  provider_name: string;
  configured?: boolean;
  provider_status?: string;
  visible_count: number;
  hidden_count: number;
  disabled_count?: number;
  models: string[];
  preferred_model_supported?: boolean;
  is_default_route_provider?: boolean;
  default_route_model?: string | null;
  default_route_provider_model_id?: string | null;
}

interface RawModelRuntimeSummary {
  runtime_type: string;
  runtime_label: string;
  runtime_status: string;
  runtime_stage: string;
  is_default: boolean;
  adapter_registered: boolean;
  bridge_registered: boolean;
  online_team_count: number;
  supports_im_relay: boolean;
  supports_device_bridge: boolean;
  supports_managed_download: boolean;
  notes: string;
}

export interface ModelResolution {
  requestedModel: string;
  resolvedModel: string;
  providerName: string;
  providerModelId: string;
  candidateCount: number;
  selected: QeeClawModelInfo;
}

interface RawModelResolution {
  requested_model: string;
  resolved_model: string;
  provider_name: string;
  provider_model_id: string;
  candidate_count: number;
  selected: RawModelInfo;
}

export interface ModelRouteProfile {
  preferredModel?: string | null;
  preferredModelAvailable: boolean;
  resolvedModel?: string | null;
  resolvedProviderName?: string | null;
  resolvedProviderModelId?: string | null;
  candidateCount: number;
  configuredProviderCount: number;
  availableModelCount: number;
  resolutionReason: string;
  selected?: QeeClawModelInfo | null;
}

interface RawModelRouteProfile {
  preferred_model?: string | null;
  preferred_model_available: boolean;
  resolved_model?: string | null;
  resolved_provider_name?: string | null;
  resolved_provider_model_id?: string | null;
  candidate_count: number;
  configured_provider_count: number;
  available_model_count: number;
  resolution_reason: string;
  selected?: RawModelInfo | null;
}

export interface ModelCurrencyAmount {
  currency: string;
  amount: number;
}

interface RawModelCurrencyAmount {
  currency: string;
  amount: number;
}

export interface ModelUsageBreakdownItem {
  productName: string;
  label: string;
  groupType: string;
  modelName?: string | null;
  providerNames: string[];
  callCount: number;
  textInputChars: number;
  textOutputChars: number;
  durationSeconds: number;
  lastUsedAt?: string | null;
}

interface RawModelUsageBreakdownItem {
  product_name: string;
  label: string;
  group_type: string;
  model_name?: string | null;
  provider_names: string[];
  call_count: number;
  text_input_chars: number;
  text_output_chars: number;
  duration_seconds: number;
  last_used_at?: string | null;
}

export interface ModelUsageSummary {
  windowDays: number;
  periodStart: string;
  periodEnd: string;
  attributionMode: string;
  recordCount: number;
  totalCalls: number;
  totalInputChars: number;
  totalOutputChars: number;
  totalDurationSeconds: number;
  lastUsedAt?: string | null;
  breakdown: ModelUsageBreakdownItem[];
}

interface RawModelUsageSummary {
  window_days: number;
  period_start: string;
  period_end: string;
  attribution_mode: string;
  record_count: number;
  total_calls: number;
  total_input_chars: number;
  total_output_chars: number;
  total_duration_seconds: number;
  last_used_at?: string | null;
  breakdown: RawModelUsageBreakdownItem[];
}

export interface ModelCostBreakdownItem {
  productName: string;
  label: string;
  groupType: string;
  modelName?: string | null;
  providerNames: string[];
  callCount: number;
  amount?: number | null;
  averageAmount?: number | null;
  currency?: string | null;
  currencyBreakdown: ModelCurrencyAmount[];
  lastBilledAt?: string | null;
}

interface RawModelCostBreakdownItem {
  product_name: string;
  label: string;
  group_type: string;
  model_name?: string | null;
  provider_names: string[];
  call_count: number;
  amount?: number | null;
  average_amount?: number | null;
  currency?: string | null;
  currency_breakdown: RawModelCurrencyAmount[];
  last_billed_at?: string | null;
}

export interface ModelCostSummary {
  windowDays: number;
  periodStart: string;
  periodEnd: string;
  attributionMode: string;
  recordCount: number;
  totalAmount?: number | null;
  primaryCurrency?: string | null;
  currencyBreakdown: ModelCurrencyAmount[];
  lastBilledAt?: string | null;
  breakdown: ModelCostBreakdownItem[];
}

interface RawModelCostSummary {
  window_days: number;
  period_start: string;
  period_end: string;
  attribution_mode: string;
  record_count: number;
  total_amount?: number | null;
  primary_currency?: string | null;
  currency_breakdown: RawModelCurrencyAmount[];
  last_billed_at?: string | null;
  breakdown: RawModelCostBreakdownItem[];
}

export interface ModelQuotaSummary {
  walletBalance: number;
  currency: string;
  dailyLimit?: number | null;
  dailySpent: number;
  dailyRemaining?: number | null;
  dailyUnlimited: boolean;
  monthlyLimit?: number | null;
  monthlySpent: number;
  monthlyRemaining?: number | null;
  monthlyUnlimited: boolean;
  updatedTime?: string | null;
}

interface RawModelQuotaSummary {
  wallet_balance: number;
  currency: string;
  daily_limit?: number | null;
  daily_spent: number;
  daily_remaining?: number | null;
  daily_unlimited: boolean;
  monthly_limit?: number | null;
  monthly_spent: number;
  monthly_remaining?: number | null;
  monthly_unlimited: boolean;
  updated_time?: string | null;
}

function mapModelInfo(item: RawModelInfo): QeeClawModelInfo {
  return {
    id: item.id,
    providerName: item.provider_name,
    modelName: item.model_name,
    providerModelId: item.provider_model_id,
    modelType: item.model_type,
    label: item.label,
    isPreferred: item.is_preferred,
    availabilityStatus: item.availability_status,
    unitPrice: item.unit_price,
    outputUnitPrice: item.output_unit_price,
    currency: item.currency,
    billingMode: item.billing_mode,
    textUnitChars: item.text_unit_chars,
    textMinAmount: item.text_min_amount,
  };
}

function mapCurrencyAmount(item: RawModelCurrencyAmount): ModelCurrencyAmount {
  return {
    currency: item.currency,
    amount: item.amount,
  };
}

function mapUsageBreakdown(item: RawModelUsageBreakdownItem): ModelUsageBreakdownItem {
  return {
    productName: item.product_name,
    label: item.label,
    groupType: item.group_type,
    modelName: item.model_name,
    providerNames: item.provider_names ?? [],
    callCount: item.call_count,
    textInputChars: item.text_input_chars,
    textOutputChars: item.text_output_chars,
    durationSeconds: item.duration_seconds,
    lastUsedAt: item.last_used_at,
  };
}

function mapCostBreakdown(item: RawModelCostBreakdownItem): ModelCostBreakdownItem {
  return {
    productName: item.product_name,
    label: item.label,
    groupType: item.group_type,
    modelName: item.model_name,
    providerNames: item.provider_names ?? [],
    callCount: item.call_count,
    amount: item.amount,
    averageAmount: item.average_amount,
    currency: item.currency,
    currencyBreakdown: (item.currency_breakdown ?? []).map(mapCurrencyAmount),
    lastBilledAt: item.last_billed_at,
  };
}

export class ModelsModule {
  constructor(private readonly http: HttpClient) {}

  async listAvailable(options: { modelType?: "chat" | "image" | string } = {}): Promise<QeeClawModelInfo[]> {
    const items = await this.http.request<RawModelInfo[]>({
      method: "GET",
      path: "/api/platform/models",
      query: options.modelType ? { model_type: options.modelType } : undefined,
    });

    return items.map(mapModelInfo);
  }

  async resolveForAgent(preferredModel?: string): Promise<QeeClawModelInfo | null> {
    const models = await this.listAvailable();
    if (models.length === 0) {
      return null;
    }

    if (preferredModel) {
      return (
        models.find((item) => item.modelName === preferredModel) ??
        models.find((item) => item.isPreferred) ??
        models[0]
      );
    }

    return models.find((item) => item.isPreferred) ?? models[0];
  }

  async listProviderSummary(): Promise<ModelProviderSummary[]> {
    const items = await this.http.request<RawModelProviderSummary[]>({
      method: "GET",
      path: "/api/platform/models/providers",
    });

    return items.map((item) => ({
      providerName: item.provider_name,
      configured: item.configured,
      providerStatus: item.provider_status,
      visibleCount: item.visible_count,
      hiddenCount: item.hidden_count,
      disabledCount: item.disabled_count,
      models: item.models ?? [],
      preferredModelSupported: item.preferred_model_supported,
      isDefaultRouteProvider: item.is_default_route_provider,
      defaultRouteModel: item.default_route_model,
      defaultRouteProviderModelId: item.default_route_provider_model_id,
    }));
  }

  async listRuntimes(): Promise<ModelRuntimeSummary[]> {
    const items = await this.http.request<RawModelRuntimeSummary[]>({
      method: "GET",
      path: "/api/platform/models/runtimes",
    });

    return items.map((item) => ({
      runtimeType: item.runtime_type,
      runtimeLabel: item.runtime_label,
      runtimeStatus: item.runtime_status,
      runtimeStage: item.runtime_stage,
      isDefault: item.is_default,
      adapterRegistered: item.adapter_registered,
      bridgeRegistered: item.bridge_registered,
      onlineTeamCount: item.online_team_count,
      supportsImRelay: item.supports_im_relay,
      supportsDeviceBridge: item.supports_device_bridge,
      supportsManagedDownload: item.supports_managed_download,
      notes: item.notes,
    }));
  }

  async resolve(
    modelName: string,
    options: { modelType?: "chat" | "image" | string } = {},
  ): Promise<ModelResolution> {
    const result = await this.http.request<RawModelResolution>({
      method: "GET",
      path: "/api/platform/models/resolve",
      query: {
        model_name: modelName,
        model_type: options.modelType,
      },
    });
    return {
      requestedModel: result.requested_model,
      resolvedModel: result.resolved_model,
      providerName: result.provider_name,
      providerModelId: result.provider_model_id,
      candidateCount: result.candidate_count,
      selected: mapModelInfo(result.selected),
    };
  }

  async getRouteProfile(): Promise<ModelRouteProfile> {
    const result = await this.http.request<RawModelRouteProfile>({
      method: "GET",
      path: "/api/platform/models/route",
    });
    return {
      preferredModel: result.preferred_model,
      preferredModelAvailable: result.preferred_model_available,
      resolvedModel: result.resolved_model,
      resolvedProviderName: result.resolved_provider_name,
      resolvedProviderModelId: result.resolved_provider_model_id,
      candidateCount: result.candidate_count,
      configuredProviderCount: result.configured_provider_count,
      availableModelCount: result.available_model_count,
      resolutionReason: result.resolution_reason,
      selected: result.selected ? mapModelInfo(result.selected) : null,
    };
  }

  async setDefaultRoute(preferredModel: string): Promise<ModelRouteProfile> {
    const result = await this.http.request<RawModelRouteProfile>({
      method: "PUT",
      path: "/api/platform/models/route",
      body: {
        preferred_model: preferredModel,
      },
    });
    return {
      preferredModel: result.preferred_model,
      preferredModelAvailable: result.preferred_model_available,
      resolvedModel: result.resolved_model,
      resolvedProviderName: result.resolved_provider_name,
      resolvedProviderModelId: result.resolved_provider_model_id,
      candidateCount: result.candidate_count,
      configuredProviderCount: result.configured_provider_count,
      availableModelCount: result.available_model_count,
      resolutionReason: result.resolution_reason,
      selected: result.selected ? mapModelInfo(result.selected) : null,
    };
  }

  async invoke(payload: ModelInvokeRequest): Promise<ModelInvokeResult> {
    return this.http.request<ModelInvokeResult>({
      method: "POST",
      path: "/api/platform/models/invoke",
      timeoutMs: payload.timeoutMs,
      body: {
        prompt: payload.prompt,
        model_id: payload.modelId,
        model: payload.model,
      },
    });
  }

  async generateImage(payload: ModelImageGenerationRequest): Promise<ModelImageGenerationResult> {
    const { timeoutMs, responseFormat, outputFormat, partialImages, ...body } = payload;
    const result = await this.http.request<RawModelImageGenerationResult>({
      method: "POST",
      path: "/api/llm/images/generations",
      timeoutMs,
      body: {
        ...body,
        model: payload.model ?? "gpt-image-2",
        response_format: payload.response_format ?? responseFormat,
        output_format: payload.output_format ?? outputFormat,
        partial_images: payload.partial_images ?? partialImages,
      },
    });

    return {
      ...result,
      created: result.created,
      data: (result.data ?? []).map((item) => ({
        ...item,
        url: item.url,
        b64Json: item.b64_json,
        b64_json: item.b64_json,
        revisedPrompt: item.revised_prompt,
        revised_prompt: item.revised_prompt,
      })),
    };
  }

  async generateImageStream(payload: ModelImageGenerationStreamRequest): Promise<Response> {
    const { timeoutMs, responseFormat, outputFormat, partialImages, ...body } = payload;
    return this.http.requestRaw({
      method: "POST",
      path: "/api/llm/images/generations",
      timeoutMs,
      headers: {
        Accept: "text/event-stream",
      },
      body: {
        ...body,
        stream: true,
        model: payload.model ?? "gpt-image-2",
        response_format: payload.response_format ?? responseFormat,
        output_format: payload.output_format ?? outputFormat,
        partial_images: payload.partial_images ?? partialImages,
      },
    });
  }

  async testProvider(): Promise<never> {
    throw new QeeClawNotImplementedError(
      "models.testProvider() is reserved for a future platform API",
    );
  }

  async getUsage(options: { days?: number } = {}): Promise<ModelUsageSummary> {
    const result = await this.http.request<RawModelUsageSummary>({
      method: "GET",
      path: "/api/platform/models/usage",
      query: options.days ? { days: options.days } : undefined,
    });
    return {
      windowDays: result.window_days,
      periodStart: result.period_start,
      periodEnd: result.period_end,
      attributionMode: result.attribution_mode,
      recordCount: result.record_count,
      totalCalls: result.total_calls,
      totalInputChars: result.total_input_chars,
      totalOutputChars: result.total_output_chars,
      totalDurationSeconds: result.total_duration_seconds,
      lastUsedAt: result.last_used_at,
      breakdown: (result.breakdown ?? []).map(mapUsageBreakdown),
    };
  }

  async getCost(options: { days?: number } = {}): Promise<ModelCostSummary> {
    const result = await this.http.request<RawModelCostSummary>({
      method: "GET",
      path: "/api/platform/models/cost",
      query: options.days ? { days: options.days } : undefined,
    });
    return {
      windowDays: result.window_days,
      periodStart: result.period_start,
      periodEnd: result.period_end,
      attributionMode: result.attribution_mode,
      recordCount: result.record_count,
      totalAmount: result.total_amount,
      primaryCurrency: result.primary_currency,
      currencyBreakdown: (result.currency_breakdown ?? []).map(mapCurrencyAmount),
      lastBilledAt: result.last_billed_at,
      breakdown: (result.breakdown ?? []).map(mapCostBreakdown),
    };
  }

  async getQuota(): Promise<ModelQuotaSummary> {
    const result = await this.http.request<RawModelQuotaSummary>({
      method: "GET",
      path: "/api/platform/models/quota",
    });
    return {
      walletBalance: result.wallet_balance,
      currency: result.currency,
      dailyLimit: result.daily_limit,
      dailySpent: result.daily_spent,
      dailyRemaining: result.daily_remaining,
      dailyUnlimited: result.daily_unlimited,
      monthlyLimit: result.monthly_limit,
      monthlySpent: result.monthly_spent,
      monthlyRemaining: result.monthly_remaining,
      monthlyUnlimited: result.monthly_unlimited,
      updatedTime: result.updated_time,
    };
  }
}

import { CloudNamespace } from "./namespace/cloud.js";
import { LocalNamespace } from "./namespace/local.js";
import type { QeeClawClientOptions, QeeClawEndpointConfig } from "./types.js";

export * from "./errors.js";
export * from "./types.js";
export * from "./modules/agent.js";
export * from "./modules/apikey.js";
export * from "./modules/approval.js";
export * from "./modules/audit.js";
export * from "./modules/billing.js";
export * from "./modules/builder.js";
export * from "./modules/channels.js";
export * from "./modules/conversations.js";
export * from "./modules/devices.js";
export * from "./modules/file.js";
export * from "./modules/iam.js";
export * from "./modules/knowledge.js";
export * from "./modules/memory.js";
export * from "./modules/models.js";
export * from "./modules/policy.js";
export * from "./modules/tenant.js";
export * from "./modules/voice.js";
export * from "./modules/workflow.js";
export * from "./modules/llm/types.js";
export * from "./modules/llm/chat-completions.js";
export * from "./modules/llm/images.js";
export * from "./modules/llm/videos.js";
export * from "./namespace/cloud.js";
export * from "./namespace/local.js";
export * from "./runtime/index.js";

function resolveEndpointConfig(
  options: QeeClawClientOptions,
  scope: "cloud" | "local",
): QeeClawEndpointConfig | undefined {
  if (scope === "cloud") {
    if (options.cloud) return options.cloud;
    if (options.baseUrl) {
      return {
        baseUrl: options.baseUrl,
        token: options.token,
        fetch: options.fetch,
        headers: options.headers,
        timeoutMs: options.timeoutMs,
        userAgent: options.userAgent,
      };
    }
    return undefined;
  }
  return options.local;
}

export class QeeClawCoreSDK {
  readonly cloud: CloudNamespace;
  readonly local: LocalNamespace | null;

  // --- Backward-compatible top-level accessors (delegate to cloud) ---

  /** @deprecated Use `sdk.cloud.agent` */
  get agent() { return this.cloud.agent; }
  /** @deprecated Use `sdk.cloud.apikey` */
  get apikey() { return this.cloud.apikey; }
  /** @deprecated Use `sdk.cloud.approval` */
  get approval() { return this.cloud.approval; }
  /** @deprecated Use `sdk.cloud.audit` */
  get audit() { return this.cloud.audit; }
  /** @deprecated Use `sdk.cloud.billing` */
  get billing() { return this.cloud.billing; }
  /** @deprecated Use `sdk.cloud.builder` */
  get builder() { return this.cloud.builder; }
  /** @deprecated Use `sdk.cloud.channels` */
  get channels() { return this.cloud.channels; }
  /** @deprecated Use `sdk.cloud.conversations` */
  get conversations() { return this.cloud.conversations; }
  /** @deprecated Use `sdk.cloud.devices` */
  get devices() { return this.cloud.devices; }
  /** @deprecated Use `sdk.cloud.file` */
  get file() { return this.cloud.file; }
  /** @deprecated Use `sdk.cloud.iam` */
  get iam() { return this.cloud.iam; }
  /** @deprecated Use `sdk.cloud.knowledge` */
  get knowledge() { return this.cloud.knowledge; }
  /** @deprecated Use `sdk.cloud.models` */
  get models() { return this.cloud.models; }
  /** @deprecated Use `sdk.cloud.policy` */
  get policy() { return this.cloud.policy; }
  /** @deprecated Use `sdk.cloud.tenant` */
  get tenant() { return this.cloud.tenant; }
  /** @deprecated Use `sdk.cloud.voice` */
  get voice() { return this.cloud.voice; }
  /** @deprecated Use `sdk.cloud.workflow` */
  get workflow() { return this.cloud.workflow; }
  /** @deprecated Use `sdk.local.memory` */
  get memory() { return this.local?.memory; }

  constructor(options: QeeClawClientOptions) {
    const cloudConfig = resolveEndpointConfig(options, "cloud");
    if (!cloudConfig) {
      throw new Error(
        "QeeClaw: cloud endpoint config is required. Provide `cloud` or legacy `baseUrl`.",
      );
    }
    this.cloud = new CloudNamespace(cloudConfig);

    const localConfig = resolveEndpointConfig(options, "local");
    this.local = localConfig ? new LocalNamespace(localConfig) : null;
  }
}

export function createQeeClawClient(options: QeeClawClientOptions): QeeClawCoreSDK {
  return new QeeClawCoreSDK(options);
}

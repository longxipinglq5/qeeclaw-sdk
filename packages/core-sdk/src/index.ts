import { HttpClient } from "./client/http-client.js";
import { AgentModule } from "./modules/agent.js";
import { ApiKeyModule } from "./modules/apikey.js";
import { ApprovalModule } from "./modules/approval.js";
import { AuditModule } from "./modules/audit.js";
import { BillingModule } from "./modules/billing.js";
import { ChannelsModule } from "./modules/channels.js";
import { ConversationsModule } from "./modules/conversations.js";
import { DevicesModule } from "./modules/devices.js";
import { FileModule } from "./modules/file.js";
import { IamModule } from "./modules/iam.js";
import { KnowledgeModule } from "./modules/knowledge.js";
import { MemoryModule } from "./modules/memory.js";
import { ModelsModule } from "./modules/models.js";
import { PolicyModule } from "./modules/policy.js";
import { TenantModule } from "./modules/tenant.js";
import { VoiceModule } from "./modules/voice.js";
import { WorkflowModule } from "./modules/workflow.js";
import type { QeeClawClientOptions } from "./types.js";

export * from "./errors.js";
export * from "./types.js";
export * from "./modules/agent.js";
export * from "./modules/apikey.js";
export * from "./modules/approval.js";
export * from "./modules/audit.js";
export * from "./modules/billing.js";
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
export * from "./runtime/index.js";

export class QeeClawCoreSDK {
  readonly file: FileModule;
  readonly voice: VoiceModule;
  readonly workflow: WorkflowModule;
  readonly agent: AgentModule;
  readonly billing: BillingModule;
  readonly iam: IamModule;
  readonly apikey: ApiKeyModule;
  readonly tenant: TenantModule;
  readonly devices: DevicesModule;
  readonly channels: ChannelsModule;
  readonly conversations: ConversationsModule;
  readonly models: ModelsModule;
  readonly memory: MemoryModule;
  readonly knowledge: KnowledgeModule;
  readonly policy: PolicyModule;
  readonly approval: ApprovalModule;
  readonly audit: AuditModule;

  constructor(options: QeeClawClientOptions) {
    const http = new HttpClient(options);
    this.file = new FileModule(http);
    this.voice = new VoiceModule(http);
    this.workflow = new WorkflowModule(http);
    this.agent = new AgentModule(http);
    this.billing = new BillingModule(http);
    this.iam = new IamModule(http);
    this.apikey = new ApiKeyModule(http);
    this.tenant = new TenantModule(http);
    this.devices = new DevicesModule(http);
    this.channels = new ChannelsModule(http);
    this.conversations = new ConversationsModule(http);
    this.models = new ModelsModule(http);
    this.memory = new MemoryModule(http);
    this.knowledge = new KnowledgeModule(http);
    this.policy = new PolicyModule(http);
    this.approval = new ApprovalModule(http);
    this.audit = new AuditModule(http);
  }
}

export function createQeeClawClient(options: QeeClawClientOptions): QeeClawCoreSDK {
  return new QeeClawCoreSDK(options);
}

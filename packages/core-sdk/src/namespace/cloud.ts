import { HttpClient } from "../client/http-client.js";
import type { QeeClawEndpointConfig } from "../types.js";
import { AgentModule } from "../modules/agent.js";
import { ApiKeyModule } from "../modules/apikey.js";
import { ApprovalModule } from "../modules/approval.js";
import { AuditModule } from "../modules/audit.js";
import { BillingModule } from "../modules/billing.js";
import { BuilderModule } from "../modules/builder.js";
import { ChannelsModule } from "../modules/channels.js";
import { ConversationsModule } from "../modules/conversations.js";
import { DevicesModule } from "../modules/devices.js";
import { FileModule } from "../modules/file.js";
import { IamModule } from "../modules/iam.js";
import { KnowledgeModule } from "../modules/knowledge.js";
import { ModelsModule } from "../modules/models.js";
import { PolicyModule } from "../modules/policy.js";
import { TenantModule } from "../modules/tenant.js";
import { VoiceModule } from "../modules/voice.js";
import { WorkflowModule } from "../modules/workflow.js";
import { ChatApi } from "../modules/llm/chat-completions.js";
import { ImagesApi } from "../modules/llm/images.js";
import { VideosApi } from "../modules/llm/videos.js";

export class CloudNamespace {
  readonly chat: ChatApi;
  readonly images: ImagesApi;
  readonly videos: VideosApi;

  readonly agent: AgentModule;
  readonly apikey: ApiKeyModule;
  readonly approval: ApprovalModule;
  readonly audit: AuditModule;
  readonly billing: BillingModule;
  readonly builder: BuilderModule;
  readonly channels: ChannelsModule;
  readonly conversations: ConversationsModule;
  readonly devices: DevicesModule;
  readonly file: FileModule;
  readonly iam: IamModule;
  readonly knowledge: KnowledgeModule;
  readonly models: ModelsModule;
  readonly policy: PolicyModule;
  readonly tenant: TenantModule;
  readonly voice: VoiceModule;
  readonly workflow: WorkflowModule;

  constructor(config: QeeClawEndpointConfig) {
    const http = new HttpClient(config);
    this.chat = new ChatApi(http);
    this.images = new ImagesApi(http);
    this.videos = new VideosApi(http);
    this.agent = new AgentModule(http);
    this.apikey = new ApiKeyModule(http);
    this.approval = new ApprovalModule(http);
    this.audit = new AuditModule(http);
    this.billing = new BillingModule(http);
    this.builder = new BuilderModule(http);
    this.channels = new ChannelsModule(http);
    this.conversations = new ConversationsModule(http);
    this.devices = new DevicesModule(http);
    this.file = new FileModule(http);
    this.iam = new IamModule(http);
    this.knowledge = new KnowledgeModule(http);
    this.models = new ModelsModule(http);
    this.policy = new PolicyModule(http);
    this.tenant = new TenantModule(http);
    this.voice = new VoiceModule(http);
    this.workflow = new WorkflowModule(http);
  }
}

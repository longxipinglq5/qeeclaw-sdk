# QeeClaw Core SDK

`@qeeclaw/core-sdk` 是 QeeClaw 平台能力的 TypeScript 优先 SDK 初版。

当前版本优先封装开发计划里最适合第一批 SDK 化的现有平台接口：

- `file`
- `voice`
- `workflow`
- `agent`
- `billing`
- `iam`
- `apikey`
- `tenant`
- `devices`
- `models`
- `channels`
- `conversations`
- `memory`
- `knowledge`
- `audit`
- `policy`
- `approval`

其中 `agent / memory / knowledge` 模块当前都已开始暴露 `runtimeType`、`teamId`、`deviceId`、`agentId` 等 target scope 元数据，用于把智能体定义、知识/记忆工作台与底层 runtime 适配实现分层。

> **🌟 新增说明 (v0.2.0)**：QeeClaw 现已支持 **C/S 分离架构**，`runtimeType` 正式新增 `hermes` 类型。在该模式下，SDK 直接连接由 `bridge_server.py` 提供的独立后端，实现全本地离线推理与管理，切断对线上 PaaS 接口的强制依赖。

如果你是在做真实项目对接，建议优先参考仓库文档目录中的两份说明：

- `QeeClaw_客户接入手册.md`
- `QeeClaw_AI_PaaS平台交付手册.md`

## 安装

```bash
pnpm add @qeeclaw/core-sdk
```

## 快速开始

```ts
import { createQeeClawClient } from "@qeeclaw/core-sdk";

const client = createQeeClawClient({
  baseUrl: "https://your-qeeclaw-host",
  token: "your-bearer-token-or-llm-key",
});

const wallet = await client.billing.getWallet();
const me = await client.iam.getProfile();
const models = await client.models.listAvailable();
const imageModels = await client.models.listAvailable({ modelType: "image" });
const routeProfile = await client.models.getRouteProfile();
const usage = await client.models.getUsage({ days: 30 });
const cost = await client.models.getCost({ days: 30 });
const quota = await client.models.getQuota();

const image = await client.models.generateImage({
  model: "gpt-image-2",
  prompt: "一只在办公室写代码的猫",
  size: "1024x1024",
  output_format: "png",
});
console.log(image.data[0]?.url ?? image.data[0]?.b64Json);

const stored = await client.memory.store({
  teamId: 1,
  runtimeType: "hermes", // 或 "openclaw", "deeflow2"
  content: "用户更喜欢中文回复",
  category: "preference",
  importance: 0.9,
  agentId: "main-agent",
});

const knowledge = await client.knowledge.search({
  teamId: 1,
  runtimeType: "hermes", // 或 "openclaw"
  agentId: "main-agent",
  query: "安装指南",
  limit: 5,
});

const deviceOnlineState = await client.devices.getOnlineState();

await client.audit.record({
  actionType: "SDK_DEMO",
  title: "QeeClaw Core SDK quick start",
  module: "README",
});

const execDecision = await client.policy.checkExecAccess({
  command: "rm -rf /",
  riskLevel: "critical",
});

if (execDecision.requiresApproval) {
  const approval = await client.approval.request({
    approvalType: "exec_access",
    title: "申请高风险命令执行审批",
    reason: execDecision.reason ?? "需要执行高风险命令",
    riskLevel: "critical",
    payload: { command: "rm -rf /" },
  });
  console.log(approval.approvalId);
}

const appKeys = await client.apikey.list();
const llmKeys = await client.apikey.listLLMKeys();
const tenantContext = await client.tenant.getCurrentContext();

console.log({
  wallet,
  username: me.username,
  defaultRoutedModel: routeProfile.resolvedModel,
  imageModelCount: imageModels.length,
  appKeyCount: appKeys.total,
  llmKeyCount: llmKeys.length,
  teams: tenantContext.teams.map((item) => item.name),
  deviceRuntime: deviceOnlineState.runtimeType,
  onlineTeams: deviceOnlineState.onlineTeamIds,
});
```

如果你需要把个人微信入口接进 QeeClaw 平台，也可以直接通过 `channels` 模块调用官方 OpenClaw 插件模式：

- `client.channels.getWechatPersonalOpenClawConfig(teamId)`
- `client.channels.startWechatPersonalOpenClawQr({ teamId })`
- `client.channels.getWechatPersonalOpenClawQrStatus({ teamId, sessionId })`
- `client.channels.createChannelBinding({ teamId, channelKey: "wechat_personal_openclaw", ... })`

## 本地 Mock 联调

如果你当前没有真实的 QeeClaw 平台环境，可以先启动最小 mock server：

```bash
node ./examples/mock-platform-server.mjs
```

然后可以直接运行配套 mock client：

```bash
node ./examples/mock-client.mjs
```

然后把 SDK 指向本地 mock 地址：

```ts
const client = createQeeClawClient({
  baseUrl: "http://127.0.0.1:3456",
  token: "mock-token",
});
```

### 连接本地 Hermes Bridge (独立 C/S 模式)

当部署了 `qeeclaw-hermes-bridge` 本地服务端后，直接将其指向 Bridge 监听的网关即可：

```ts
const client = createQeeClawClient({
  baseUrl: "http://127.0.0.1:21747", // 指向 Bridge Gateway
  token: "none", // 或使用 local 配置的密钥
});
```
在客户端（如 Qeeshu Ruisi）的全局 Store 中，宣告 `runtimeType: 'hermes'`，SDK 底层链路会自动放行非必要的 PaaS 云端工作台接口，直接挂载纯净环境。

这个 mock server 当前主要用于演示和联调：

- `file`
- `voice`
- `workflow`
- `agent`
- `billing`
- `iam`
- `apikey`
- `tenant`
- `devices`
- `models`
- `channels`
- `conversations`
- `memory`
- `knowledge`
- `policy`
- `approval`
- `audit`

## 鉴权约定

当前 SDK 统一使用 `Authorization: Bearer <token>` 发送凭证。

- `devices` 模块一般使用用户登录态 token
- `billing` / `iam` / `apikey` / `tenant` 当前建议使用用户登录态 token
- `apikey.listLLMKeys()` / `createLLMKey()` / `updateLLMKey()` / `removeLLMKey()` 当前建议使用用户登录态 token
- `models` / `memory` 可使用用户 token，也可使用 LLM Key
- `memory` / `knowledge` 在多 runtime 场景下建议显式传入 `teamId + runtimeType`；如果目标是某个 agent 或 device，再额外传 `agentId / deviceId`
- `channels` / `conversations` 当前建议使用用户 token
- `knowledge` 当前后端接口本身未强制登录，但 SDK 仍支持带 token 调用
- `policy` 检查与 `approval.request()` 可使用用户 token 或 LLM Key
- `approval.list()` / `approval.get()` 当前建议使用用户登录态 token
- `approval.resolve()` 当前需要管理员用户登录态 token

## 已封装接口映射

### billing

- `GET /api/billing/wallet`
- `GET /api/billing/records`
- `GET /api/billing/summary`

### iam

- `GET /api/users/me`
- `PUT /api/users/me`
- `PUT /api/users/me/preference`
- `GET /api/users`
  - 管理员可用
- `GET /api/users/products`

### apikey

- `GET /api/users/app-keys`
- `POST /api/users/app-keys`
- `DELETE /api/users/app-keys/{appKeyId}`
- `PATCH /api/users/app-keys/{appKeyId}`
- `PUT /api/users/app-keys/{appKeyId}/name`
- `POST /api/users/app-keys/default/token`
- `GET /api/llm/keys`
- `POST /api/llm/keys`
- `PUT /api/llm/keys/{keyId}`
- `DELETE /api/llm/keys/{keyId}`

### tenant

- `GET /api/users/me`
  - 当前用于读取工作空间上下文
- `GET /api/company/verification`
- `POST /api/company/verification`
- `POST /api/company/verification/approve`

### file

- `GET /api/documents`
- `GET /api/documents/{documentId}`
- `GET /api/products/{productId}/documents`

### voice

- `POST /api/asr`
- `POST /api/tts`
- `POST /api/audio/speech`

### workflow

- `POST /api/workflows`
- `GET /api/workflows`
- `GET /api/workflows/{workflowId}`
- `POST /api/workflows/{workflowId}/run`
- `GET /api/workflows/executions/{executionId}/logs`

### agent

- `GET /api/agent/tools`
- `GET /api/agent/my-agents`
- `POST /api/agent/create`
- `PUT /api/agent/{agentId}`
- `GET /agent_config/default`
- `GET /agent_config/{code}`

### devices

- `GET /api/platform/devices`
- `GET /api/platform/devices/account-state`
- `POST /api/platform/devices/pair-code`
- `POST /api/platform/devices/claim`
- `POST /api/platform/devices/bootstrap`
- `PUT /api/platform/devices/{deviceId}`
- `DELETE /api/platform/devices/{deviceId}`
- `GET /api/platform/devices/online`

当前 `devices` 模块仍是 `OpenClaw-only device bridge` 控制面：

- `claim()` / `bootstrap()` 返回的 `wsUrl` 继续固定指向 `/api/openclaw/ws`
- `getOnlineState()` 会返回 `runtimeType / runtimeStatus / supportsDeviceBridge / notes`
- 即使未来默认 agent runtime 变化，这个模块也不应隐式改指向 `DeeFlow2` 等 team-level runtime

### memory / knowledge runtime-aware target scope

`memory` 与 `knowledge` 模块当前都支持显式 target scope：

- `teamId`
- `runtimeType`
- `deviceId`
- `agentId`

推荐在多 runtime 场景下显式传入 `teamId + runtimeType`，避免 SDK 调用方把“默认 runtime”误当成平台固定事实。

### models

- `GET /api/platform/models`
- `GET /api/platform/models/providers`
- `GET /api/platform/models/route`
- `GET /api/platform/models/usage`
- `GET /api/platform/models/cost`
- `GET /api/platform/models/quota`
- `PUT /api/platform/models/route`
- `GET /api/platform/models/resolve`
- `POST /api/platform/models/invoke`
- `POST /api/llm/images/generations`

`/api/llm/images/generations` 按 OpenAI Images API 兼容设计：请求字段优先使用 OpenAI 原始 snake_case，例如 `response_format`、`output_format`、`partial_images`；SDK 同时保留 `responseFormat`、`outputFormat`、`partialImages` 作为 TypeScript 便利别名。非流式响应原样返回 OpenAI 风格 JSON，图片内容通常在 `data[0].b64_json`。

如果需要消费 OpenAI 图片生成 SSE，可以使用 `client.models.generateImageStream({ model: "gpt-image-2", prompt: "...", stream: true })`，返回值是原始 `Response`，调用方可自行读取 `response.body`。

### channels

- `GET /api/platform/channels`
- `GET /api/platform/channels/wechat-work/config`
- `POST /api/platform/channels/wechat-work/config`
- `GET /api/platform/channels/feishu/config`
- `POST /api/platform/channels/feishu/config`
- `GET /api/platform/channels/wechat-personal-plugin/config`
- `POST /api/platform/channels/wechat-personal-plugin/config`
- `GET /api/platform/channels/wechat-personal-openclaw/config`
- `POST /api/platform/channels/wechat-personal-openclaw/qr/start`
- `GET /api/platform/channels/wechat-personal-openclaw/qr/status`
- `GET /api/platform/channels/bindings`
- `POST /api/platform/channels/bindings/create`
- `POST /api/platform/channels/bindings/disable`
- `POST /api/platform/channels/bindings/regenerate-code`

### conversations

- `GET /api/platform/conversations`
- `GET /api/platform/conversations/stats`
- `GET /api/platform/conversations/groups`
- `GET /api/platform/conversations/groups/{roomId}/messages`
- `GET /api/platform/conversations/history`
- `POST /api/platform/conversations/messages`

### memory

- `POST /api/platform/memory/store`
- `POST /api/platform/memory/search`
- `DELETE /api/platform/memory/{entryId}`
- `DELETE /api/platform/memory/agent/{agentId}`
- `GET /api/platform/memory/stats`

### knowledge

- `POST /api/platform/knowledge/upload`
- `GET /api/platform/knowledge/list`
- `POST /api/platform/knowledge/delete`
- `GET /api/platform/knowledge/download`
- `GET /api/platform/knowledge/search`
- `GET /api/platform/knowledge/stats`
- `GET /api/platform/knowledge/config`
- `POST /api/platform/knowledge/config/update`

### audit

- `POST /api/platform/audit/events`
- `GET /api/workflows/executions/{execId}/logs`
- `GET /api/platform/audit/events`
  - 支持 `scope / category / keyword / startAt / endAt / page / pageSize`
- `GET /api/platform/audit/summary`
  - 支持与事件流一致的过滤参数，用于治理面板汇总

### policy

- `POST /api/platform/policy/tool-access/check`
- `POST /api/platform/policy/data-access/check`
- `POST /api/platform/policy/exec-access/check`

### approval

- `POST /api/platform/approvals/request`
- `GET /api/platform/approvals`
  - 支持 `scope / status / approvalType / riskLevel / keyword / page / pageSize`
- `GET /api/platform/approvals/{approvalId}`
- `POST /api/platform/approvals/{approvalId}/resolve`

## 当前边界

- `devices.routeCommand()` 与 `knowledge.rebuildIndex()` 也暂时保留为占位能力
- 当前 `policy / approval` 是最小可用版本，规则暂基于后端内置策略，审批记录已持久化到数据库并同步缓存到 Redis
- 当前 `tenant` 模块优先承接“工作空间上下文 + 企业认证”这一层，还不是完整多租户控制面
- 当前 `iam` 模块优先承接“当前账号、用户列表、产品权限视图”，更细粒度角色策略仍在继续补齐
- `apikey` 模块当前已覆盖用户级 AppKey 和用户级 Provider Key，但仍不等同于完整开发者门户
- 当前 `file` 模块先承接文档资产接口，不等同于完整对象存储控制面
- 当前 `voice` 模块已支持 `asr / tts / speech`，但实时音频流与高级声纹能力仍在平台侧继续演进
- 这是阶段 2 的最小 SDK 起点，后续会随着平台域化重构继续补齐

## 额外文档

- 领域模型与 API 契约草案：`docs/SDK_CONTRACTS.md`
- 示例代码：`examples/basic-usage.ts`
- 本地 mock server：`examples/mock-platform-server.mjs`
- 本地 mock client：`examples/mock-client.mjs`

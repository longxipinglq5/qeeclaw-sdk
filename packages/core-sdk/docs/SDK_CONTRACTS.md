# QeeClaw Core SDK Contracts

## 1. 模块边界

`@qeeclaw/core-sdk` 只承接适合直接通过平台 HTTP API 暴露的轻量能力。

当前模块边界：

- `billing`
  - 钱包余额、账单列表、消费汇总
- `iam`
  - 当前账号资料、账号偏好、用户列表、产品权限视图
- `apikey`
  - AppKey、Provider Key 列表与管理、默认 token 获取
- `tenant`
  - 工作空间上下文、企业认证状态与提交流程
- `file`
  - 文档资产列表、文档详情、产品关联文档
- `voice`
  - 同步 ASR、TTS、OpenAI-compatible speech
- `workflow`
  - 工作流定义保存、查询、运行、执行日志
- `agent`
  - 工具清单、我的智能体、模板与自定义智能体，以及 `runtimeType` 等运行时元数据
- `devices`
  - 设备注册、设备引导、设备列表、在线状态；当前仍显式限定为 `OpenClaw device bridge`
- `models`
  - 模型列表、Provider 摘要、默认路由、用量汇总、成本汇总、额度摘要、模型解析、轻量调用
- `channels`
  - 渠道配置总览、企微/飞书配置、个人微信自建回调模式、官方 OpenClaw 插件模式、绑定码与二维码状态
- `conversations`
  - 会话统计、群聊列表、消息历史、写入会话记录
- `memory`
  - 记忆写入、搜索、删除、清空、统计；支持 `teamId / runtimeType / deviceId / agentId`
- `knowledge`
  - 知识上传、检索、删除、配置；支持 `teamId / runtimeType / deviceId / agentId`
- `audit`
  - 平台审计事件上报、工作流执行日志读取
- `policy`
  - 工具访问、数据访问、执行访问判定
- `approval`
  - 审批请求、查询、处理

不直接放入 Core SDK 的能力：

- 重型索引重建
- 本地长任务
- 本地审批 UI
- 本地命令执行代理
- 高频状态同步

这些能力后续归入 Runtime Sidecar 或 Platform Hub。

## 2. 统一领域对象

### Tenant

```ts
interface Tenant {
  id: string;
  name: string;
}
```

### Team

```ts
interface Team {
  id: string | number;
  name: string;
  tenantId?: string | number;
}
```

### Identity

```ts
interface Identity {
  id: string | number;
  type: "user" | "agent" | "device" | "channel";
  name?: string;
}
```

### Agent

```ts
interface Agent {
  id: string | number;
  name: string;
  teamId?: string | number;
}
```

### Device

```ts
interface Device {
  id: string | number;
  deviceName?: string;
  deviceType?: string;
  status?: string;
  teamId?: string | number;
}
```

### Channel

```ts
interface Channel {
  id: string | number;
  type: string;
  name?: string;
}
```

### MemoryEntry

```ts
interface MemoryEntry {
  id?: string;
  content: string;
  category?: string;
  importance?: number;
  teamId?: string | number;
  runtimeType?: string | null;
  deviceId?: string | null;
  agentId?: string | null;
  sourceSession?: string | null;
}
```

### KnowledgeAsset

```ts
interface KnowledgeAsset {
  sourceName: string;
  size?: number;
  status?: string;
  metadata?: Record<string, JsonValue>;
}
```

### PolicyDecision

```ts
interface PolicyDecision {
  allowed: boolean;
  reason?: string;
  matchedPolicy?: string;
}
```

## 3. API 约定

统一约定如下：

- 鉴权头统一为 `Authorization: Bearer <token>`
- 基础返回优先兼容 `{ code, data, message }`
- `code === 0` 视为成功
- SDK 统一把非 0 业务码抛成 `QeeClawApiError`
- 网络超时抛成 `QeeClawTimeoutError`
- 域模型对外暴露使用 `camelCase`
- 后端历史接口使用 `snake_case` 时，在 SDK 内部做字段映射
- 列表类平台治理接口统一收口为 `{ total, page, page_size, items }`

## 4. Core SDK 与 Sidecar 边界

属于 Core SDK：

- 直连平台 HTTP API 的轻量能力
- 可在前端、Node 服务端、脚本环境直接调用的能力
- 通过 `runtimeType / teamId / deviceId / agentId` 明确目标范围的 runtime-aware 控制面调用

属于 Runtime Sidecar：

- 本地知识索引任务
- 本地缓存与向量存储代理
- 本地审批执行器
- 本地安全代理
- 设备/通道长连接适配

补充边界：

- `devices` 模块当前不是“所有 runtime 的统一设备控制台”，而是 `OpenClaw-only` 设备注册与配对控制面
- `knowledge / memory` 模块虽然支持 runtime-aware target scope，但仍需遵守后端 bridge 能力边界，例如 `supports_device_bridge=false` 的 runtime 不应强行传 `deviceId`

## 5. 当前缺口

当前 `billing / iam / apikey / tenant / file / voice / workflow / agent` 已作为平台心脏与体验增强能力的第一批映射补入 Core SDK：

- `billing.getWallet()` / `billing.listRecords()` / `billing.getSummary()`
- `iam.getProfile()` / `iam.updateProfile()` / `iam.listUsers()` / `iam.listProducts()`
- `apikey.list()` / `apikey.create()` / `apikey.issueDefaultToken()`
- `apikey.listLLMKeys()` / `apikey.createLLMKey()` / `apikey.updateLLMKey()` / `apikey.removeLLMKey()`
- `tenant.getCurrentContext()` / `tenant.getCompanyVerification()`
- `file.listDocuments()` / `file.getDocument()` / `file.listProductDocuments()`
- `voice.transcribe()` / `voice.synthesize()` / `voice.speech()`
- `workflow.save()` / `workflow.list()` / `workflow.run()`
- `agent.listTools()` / `agent.listMyAgents()` / `agent.listDefaultTemplates()`

但其中仍有阶段性边界：

- `tenant` 当前还不是完整租户控制面，更偏“企业认证与团队上下文”
- `iam` 当前还未覆盖细粒度角色、组织架构、策略配置
- `apikey` 当前覆盖用户级 AppKey 与 Provider Key，不含平台级服务账号
- `file` 当前先聚焦平台文档资产，不包含通用文件上传网关
- `workflow` 当前基于现有轻量工作流引擎，仍缺编排治理与版本控制
- `agent` 当前以用户智能体与模板查询为主，已开始补齐 `runtimeType` 元数据，但真正的多 runtime 执行适配仍在后续阶段

当前 `policy / approval / audit` 已具备第一版平台治理契约：

- `approval.list()` 支持分页、状态/风险等级/关键字过滤
- `audit.record()` 已收口到标准平台路径 `/api/platform/audit/events`
- `audit.listEvents()` 支持分页、类别、关键字、时间范围过滤
- `audit.getSummary()` 支持与事件流一致的筛选条件

后续仍需要继续推进：

- 更细的策略规则配置化
- 审计事件游标分页
- 多级审批流与审批执行代理

当前 `channels` 也已开始承担“平台治理 + SDK 开放层”的关键收口：

- `channels.getOverview()` 统一返回企业协同通道与个人触达通道
- `channels.getWechatPersonalPluginConfig()` 覆盖自建回调模式
- `channels.getWechatPersonalOpenClawConfig()` / `startWechatPersonalOpenClawQr()` / `getWechatPersonalOpenClawQrStatus()` 覆盖官方 OpenClaw 插件模式
- `channels.createChannelBinding()` / `disableChannelBinding()` / `regenerateChannelBindingCode()` 统一承载个人微信绑定码流转

当前 `memory / knowledge / devices` 也需要同步强调开放层边界：

- `memory.store()` / `memory.search()` / `memory.stats()` 已支持显式 `teamId / runtimeType / deviceId / agentId`
- `knowledge.ingest()` / `list()` / `search()` / `stats()` / `getConfig()` / `updateConfig()` 已支持显式 `runtimeType / agentId`
- `devices.getOnlineState()` 已返回 `runtimeType / runtimeStatus / supportsDeviceBridge / notes`
- `devices.claim()` / `devices.bootstrap()` 返回的 `wsUrl` 继续固定指向 `/api/openclaw/ws`

# QeeClaw 销售驾驶仓前端联调参数单模板

最后更新：2026-04-08

## 1. 使用说明

这份参数单用于给“仅开发前端销售驾驶仓”的客户或外包团队做联调准备。

适用场景：

- 客户基于你方现有线上 `QeeClaw Platform`
- 客户只开发前端页面或前端 BFF
- 不涉及私有化部署
- 不涉及本地 `runtime-sidecar`

这份参数单建议和以下资料一起发给客户：

- `sdk/docs/README.md`
- `sdk/docs/QeeClaw_第三方SDK与Platform_API对接文档_20260404.md`
- `sdk/docs/QeeClaw_终端接入指南.md`
- `@qeeclaw/core-sdk`
- `@qeeclaw/product-sdk`

如果客户还需要做接口排障或异构语言联调，再按需补：

- `sdk/docs/QeeClaw_Platform_API_v1_域化接口说明_20260321.md`
- `sdk/docs/postman/QeeClaw_Platform_API_v1.postman_collection.json`
- `sdk/docs/postman/QeeClaw_Platform_API_v1.postman_environment.json`

---

## 2. 项目基本信息

| 项目项 | 填写内容 |
| --- | --- |
| 项目名称 |  |
| 客户名称 |  |
| 联调环境 | `dev / test / staging / prod` |
| 前端项目形态 | `Web 控制台 / 驾驶舱 / H5 / BFF` |
| 对接负责人 |  |
| 联调起止时间 |  |

---

## 3. 平台接入信息

| 参数 | 是否必填 | 说明 | 填写内容 |
| --- | --- | --- | --- |
| `baseUrl` | 是 | QeeClaw 平台根地址，不带 `/api/...`。当前线上默认直接填写 `https://paas.qeeshu.com` |  |
| `apiKey` | 是 | 平台发放给客户前端的 API Key，建议使用 `sk-...` 形式 |  |
| `测试账号` | 是 | 客户前端联调使用的账号 |  |
| `测试密码/获取方式` | 是 | 如果不直接给密码，需写清获取流程 |  |
| `默认模型` | 建议 | 如 `gpt-4.1-mini` |  |
| `用户权限范围` | 是 | 普通用户 / 管理员 / 审批人 |  |

当前推荐默认值：

```text
baseUrl=https://paas.qeeshu.com
runtimeType=openclaw
```

### 3.1 平台内部自动解析项

以下信息通常仍存在于平台内部，但不建议作为客户填写参数：

| 参数 | 当前处理方式 | 是否要求客户填写 |
| --- | --- | --- |
| `teamId` | 通过 `GET /api/users/me/context` 或 `tenant.getCurrentContext()` 自动解析默认工作空间 | 否 |
| `runtimeType` | 当前固定为 `openclaw` | 否 |
| `agentId` | 如产品内部需要，可由应用内置或平台侧约定 | 否 |

一句话口径：

- 客户拿到的参数单只保留 `baseUrl + apiKey + 测试账号`
- `teamId / agentId` 由应用内部自动解析或预置
- `runtimeType` 当前固定为 `openclaw`

---

## 4. 销售驾驶仓推荐接入点

客户前端如果基于 `@qeeclaw/product-sdk` 开发销售驾驶仓，建议优先使用以下入口：

| 模块 | 典型方法 | 用途 | 需要哪些关键参数 |
| --- | --- | --- | --- |
| `salesCockpit` | `loadHome(teamId, scope)` | 销售驾驶仓首页 | `teamId` 由应用内部自动解析 |
| `salesKnowledge` | `loadAssistantContext(runtimeScope)` | 销售知识助手上下文 | `teamId` 自动解析，`runtimeType=openclaw` 固定 |
| `salesCoaching` | `loadTrainingOverview(teamId, scope)` | 培训 / 复盘概览 | `teamId` 由应用内部自动解析 |
| `knowledgeCenter` | `loadHome(runtimeScope)` | 知识中心首页 | `teamId` 自动解析，`runtimeType=openclaw` 固定 |
| `conversationCenter` | `loadHome(teamId)` | 会话中心概览 | `teamId` 由应用内部自动解析 |
| `channelCenter` | `loadHome(teamId)` | 渠道中心概览 | `teamId` 由应用内部自动解析 |
| `governanceCenter` | `loadHome(scope)` | 审批 / 审计治理概览 | `scope=mine / all` |

推荐前端初始化示例：

```ts
import { createQeeClawClient } from "@qeeclaw/core-sdk";
import { createQeeClawProductSDK } from "@qeeclaw/product-sdk";

const core = createQeeClawClient({
  baseUrl: "https://paas.qeeshu.com",
  token: "sk-your-api-key",
});

const product = createQeeClawProductSDK(core);

const tenant = await core.tenant.getCurrentContext();
const fallbackTeam =
  tenant.teams.find((item) => !item.isPersonal) ?? tenant.teams[0];
const teamId = Number(tenant.defaultTeamId ?? fallbackTeam?.id);

const runtimeScope = {
  teamId,
  runtimeType: "openclaw",
};

const salesCockpit = await product.salesCockpit.loadHome(teamId, "mine");
const salesKnowledge = await product.salesKnowledge.loadAssistantContext(runtimeScope);
const salesCoaching = await product.salesCoaching.loadTrainingOverview(teamId, "mine");
```

---

## 5. 为什么客户参数单不再要求 `teamId / agentId`

原因不是这些字段没用了，而是：

- `teamId` 仍然存在于平台内部作用域，但更适合在应用登录后自动解析
- `runtimeType` 当前固定为 `openclaw`，没必要让客户重复填写
- `agentId` 是否存在，属于产品内部实现细节，不应成为客户联调阻塞项

推荐对客户的统一口径：

- 客户只需要拿到 `API Key`
- 应用内部再根据 `API Key` 去解析默认工作空间
- 需要更细粒度 scope 时，由项目方在代码层补充，而不是让客户手填内部 ID

---

## 6. 测试数据准备

联调前建议平台侧先准备以下测试数据：

| 数据项 | 是否必备 | 说明 | 填写内容 |
| --- | --- | --- | --- |
| 测试工作空间 | 是 | 客户登录后至少能解析到 1 个可用工作空间 |  |
| 销售助手能力 | 建议 | 如有内置销售助手或 Copilot，可在项目说明里备注 |  |
| 测试知识库文档 | 建议 | 如产品介绍、报价策略、实施说明 |  |
| 会话样本 | 建议 | 至少 1 个群聊、若干历史消息 |  |
| 渠道样本 | 按需 | 如企微、飞书、个人微信 |  |
| 审批样本 | 建议 | 至少 1 条 `pending` 审批 |  |
| 审计样本 | 建议 | 至少可查到若干操作日志 |  |
| 模型配置 | 是 | 至少有 1 个可用模型 |  |

建议最低联调样本：

- 1 个可用工作空间
- 3 份知识文档
- 1 个渠道配置
- 1 个群聊样本
- 1 条待审批记录
- 1 组可查询审计记录

---

## 7. 客户前端联调验收项

建议按下面清单验收：

- 能正常拿到 API Key
- 能读取当前工作空间上下文并自动解析默认业务空间
- `salesCockpit.loadHome()` 能成功返回首页数据
- `salesKnowledge.loadAssistantContext()` 能返回销售助手上下文
- `salesCoaching.loadTrainingOverview()` 能返回培训/复盘概览
- `knowledgeCenter.loadHome()` 能读到知识概览
- `conversationCenter.loadHome()` 能读到会话概览
- `channelCenter.loadHome()` 能读到渠道概览
- `governanceCenter.loadHome()` 能读到审批/审计概览
- 如需接口排障，`Postman` 集合能跑通关键接口 smoke test

---

## 8. 交付给客户的实际发包内容

如果客户只开发销售驾驶仓前端，建议实际发包内容如下：

- `sdk/docs/README.md`
- `sdk/docs/QeeClaw_第三方SDK与Platform_API对接文档_20260404.md`
- `sdk/docs/QeeClaw_终端接入指南.md`
- `sdk/docs/QeeClaw_销售驾驶仓前端联调参数单模板.md`
- `@qeeclaw/core-sdk`
- `@qeeclaw/product-sdk`
- 本参数单的已填写版本

如果需要排障、接口验收、异构后端协同，再补：

- `sdk/docs/QeeClaw_Platform_API_v1_域化接口说明_20260321.md`
- `sdk/docs/postman/QeeClaw_Platform_API_v1.postman_collection.json`
- `sdk/docs/postman/QeeClaw_Platform_API_v1.postman_environment.json`

不需要默认给客户：

- `sdk/deploy/`
- `@qeeclaw/runtime-sidecar`
- 私有化部署模板
- 整个仓库源码

---

## 9. 已填写版示例

```text
baseUrl=https://paas.qeeshu.com
apiKey=sk-demo-api-key
测试账号=sales-demo@example.com
runtimeType=openclaw
默认模型=gpt-4.1-mini
可用模块=salesCockpit,salesKnowledge,salesCoaching,knowledgeCenter,conversationCenter,channelCenter,governanceCenter
工作空间解析方式=优先调用 /api/users/me/context，SDK 内对应 tenant.getCurrentContext()
```

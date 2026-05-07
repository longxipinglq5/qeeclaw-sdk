# QeeClaw 客户接入手册

最后更新：2026-04-16

## 1. 这份文档解决什么问题

这是一份给客户、实施方、外包团队、第三方研发的统一接入手册。

如果你只想知道：

- 客户应该拿哪些资料
- 本地优先产品到底接本地还是接云端
- 客户真正可用的云端 API 有哪些
- Web / 桌面 / 移动端应该怎么接
- 销售驾驶仓联调时到底要给哪些参数

看这一份就够。

## 2. 当前统一口径

针对 **云端 SaaS / 混合云** 客户：
- `Base URL`：`https://paas.qeeshu.com`
- 客户凭证：`API Key`，建议 `sk-...`
- `runtimeType`：默认为 `hermes` (Hermes Agent，或旧版 `openclaw` / `deeflow2`)
- `teamId / agentId`：不作为客户手工填写项
- 默认工作空间：通过 `GET /api/users/me/context` 自动解析

针对 **本地纯私有化 / 单机部署 (基于 Hermes Server)** 客户：
- `Base URL`：服务所在的 IP 与端口（例如本地默认 `http://127.0.0.1:21747`）
- 客户凭证：默认无需填写（填 `none`）或使用服务部署时下发的本地密钥
- `runtimeType`：固定为 `hermes`，此时将无缝跳过云端业务数据的校验
- **本地 Hermes Bridge Server 已实现 core-sdk 全部 17 个模块（145+ 端点）**，包括智体管理、知识库、会话、记忆、审批、审计、工作流、设备管理等。本地客户可使用与云端完全一致的 SDK 接口，无需依赖云端服务

### 对本地优先产品

统一原则：

- CRM、知识库、会话、审计、设备状态等业务数据保存在客户本地
- 云端只承接鉴权、计费、模型目录、模型调用
- 客户公开云端 API 只保留：
  - `GET /api/users/me/context`
  - `models/*`
  - `billing/*`

## 3. 客户到底该拿哪些资料

### 普通客户最小交付包

建议只给 4 类：

1. 本文档
2. 公开云端 API 资产
   - `openapi/QeeClaw_Cloud_Public_API.openapi.yaml`
   - `postman/QeeClaw_Cloud_Public_API.postman_collection.json`
   - `postman/QeeClaw_Cloud_Public_API.postman_environment.json`
3. 项目专属联调信息
   - `Base URL`
   - `API Key` 发放方式
   - 测试账号 / 权限范围
4. SDK 包
   - `@qeeclaw/core-sdk`
   - 如需快速装配页面，再补 `@qeeclaw/product-sdk`

### 不建议默认给客户

- 全量 `Platform API v1` 文档
- 内部控制面接口文档
- 私有化部署模板
- Sidecar / Gateway / 固件资料
- 整个仓库源码

## 4. 客户真正可用的云端 API

### 4.1 Workspace Context

- `GET /api/users/me/context`

作用：

- 验证 API Key
- 解析默认工作空间

### 4.2 Models

- `GET /api/platform/models`
- `GET /api/platform/models/providers`
- `GET /api/platform/models/runtimes`
- `GET /api/platform/models/route`
- `GET /api/platform/models/resolve`
- `POST /api/platform/models/invoke`
- `POST /api/llm/images/generations`
- `GET /api/platform/models/usage`
- `GET /api/platform/models/cost`
- `GET /api/platform/models/quota`

### 4.3 Billing

- `GET /api/billing/wallet`
- `GET /api/billing/records`
- `GET /api/billing/summary`

## 5. 云端与本地模式的接口范围差异

### 云端模式

以下域接口在云端 SaaS 模式下不作为客户公开 API 暴露（由平台内部控制面管理）：

- `knowledge`、`conversations`、`devices`、`channels`
- `audit`、`approvals`、`workflows`、`memory`、`policy`

云端客户公开 API 仅保留 context + models + billing 三个域（共 16 个端点）。

### 本地 Hermes Server 模式

本地部署（`http://127.0.0.1:21747`）时，**上述所有域的接口均完整可用**。Bridge Server 已实现 core-sdk 全部 17 个模块、145+ 个端点，本地客户可以使用与云端完全一致的 `@qeeclaw/core-sdk` 进行对接。

### 5.1 本地 Hermes Server 完整能力清单

| 模块 | 端点数 | 路径前缀 | 说明 |
|------|--------|---------|------|
| agent | 11 | `/api/agent/*` | 智体 Profile 管理 |
| models | 10 | `/api/platform/models/*`, `/api/llm/images/generations` | 模型列表、路由、用量、图片生成 |
| iam | 5 | `/api/users/*` | 用户身份 |
| tenant | 4 | `/api/users/me/context` | 工作空间上下文 |
| billing | 3 | `/api/billing/*` | 计费（本地返回默认值） |
| conversations | 6 | `/api/platform/conversations/*` | 会话中心 |
| channels | 14 | `/api/platform/channels/*` | 渠道配置 + 绑定 |
| memory | 5 | `/api/platform/memory/*` | 记忆存取 |
| knowledge | 8 | `/api/platform/knowledge/*` | 知识库 CRUD + 向量检索 |
| devices | 8 | `/api/platform/devices/*` | 设备管理 |
| file | 3 | `/api/documents/*` | 文档管理 |
| workflow | 5 | `/api/workflows/*` | 工作流 |
| approval | 4 | `/api/platform/approvals/*` | 审批流 |
| audit | 3 | `/api/platform/audit/*` | 审计日志 |
| apikey | 10 | `/api/users/app-keys/*` | API Key 管理 |
| policy | 3 | `/api/platform/policy/*` | 策略检查 |
| voice | 3 | `/api/asr`, `/api/tts` | 语音（Stub，返回 501） |

**总计 17/17 模块，145+ 端点。** 详细 API 参考请见 `QeeClaw_Bridge_Server_API参考手册.md`。

## 6. Web / 桌面 / 移动端怎么接

### Web

推荐：

- `@qeeclaw/core-sdk`
- 需要快速拼工作台时，再加 `@qeeclaw/product-sdk`

通常不需要 `runtime-sidecar`。

### 桌面端

分两种：

1. 只用云端能力  
   直接接 `core-sdk` / `product-sdk`
2. 本地优先业务数据  
   本地保存 CRM、知识库、会话等数据；云端只接 `context + models + billing`

### 移动端

推荐：

- React Native / Expo：优先 `@qeeclaw/core-sdk`
- iOS / Android 原生 / Flutter：直接对接公开云端 API

移动端当前不应直接依赖 `runtime-sidecar`。

## 7. 销售驾驶仓联调时给客户哪些参数

如果客户只开发销售驾驶仓前端，通常只需要给：

- `baseUrl=https://paas.qeeshu.com`
- `apiKey=sk-xxx`
- 测试账号
- 默认模型，例如 `gpt-4.1-mini`
- 可用模块范围

不建议让客户填写：

- `teamId`
- `agentId`
- `runtimeType`

这些都应在应用内部自动处理。

如果不涉及云端业务管理（纯推理或本地节点工具），则应提供：
- `baseUrl=http://127.0.0.1:21747`
- `runtimeType=hermes`

### 推荐初始化方式

```ts
import { createQeeClawClient } from "@qeeclaw/core-sdk";
import { createQeeClawProductSDK } from "@qeeclaw/product-sdk";

const core = createQeeClawClient({
  baseUrl: "https://paas.qeeshu.com",
  token: "sk-your-api-key",
});

const product = createQeeClawProductSDK(core);

const context = await core.tenant.getCurrentContext();
const fallbackTeam = context.teams.find((item) => !item.isPersonal) ?? context.teams[0];
const teamId = Number(context.defaultTeamId ?? fallbackTeam?.id);
```

## 8. 推荐联调顺序

1. `GET /api/users/me/context`
2. `GET /api/platform/models`
3. `GET /api/platform/models/route`
4. `POST /api/platform/models/invoke`
5. `POST /api/llm/images/generations`
6. `GET /api/platform/models/quota`
7. `GET /api/billing/wallet`

图片生成示例：

```bash
curl -X POST "$BASE_URL/api/llm/images/generations" \
  -H "Authorization: Bearer $QEECLAW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "一只在办公室写代码的猫",
    "n": 1,
    "size": "1024x1024",
    "output_format": "png"
  }'
```

该接口按 OpenAI Images API 兼容设计：路径为 `/api/llm/images/generations`，请求体使用 OpenAI 原始字段（如 `response_format`、`output_format`、`partial_images`、`stream`），非流式响应原样返回上游 JSON，图片内容通常在 `data[0].b64_json`。

## 9. 在线文档入口

如果后端已发布新版双文档入口，可直接访问：

- 客户公开版 Swagger：`/docs/public`
- 内部控制面 Swagger：`/docs/internal`
- 客户公开版 OpenAPI：`/openapi-public.json`
- 内部控制面 OpenAPI：`/openapi-internal.json`

线上示例：

- `https://paas.qeeshu.com/docs/public`
- `https://paas.qeeshu.com/docs/internal`

## 10. 还需要看哪份文档

只有两种情况再看其他文档：

1. 做私有化部署 / 边缘交付  
   看 `QeeClaw_AI_PaaS平台交付手册.md`
2. 做高级集成 / 平台维护 / 内部控制面  
   看 `archive/QeeClaw_Platform_API_v1_域化接口说明_20260321.md`

## 11. 一句话结论

客户侧现在应该尽量只看这 3 类资料：

- `README.md`
- `QeeClaw_客户接入手册.md`
- 公开云端 API 的 OpenAPI / Postman 资产

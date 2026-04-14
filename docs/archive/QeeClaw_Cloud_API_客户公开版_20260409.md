# QeeClaw Cloud API 客户公开版

最后更新：2026-04-09

## 1. 文档定位

本文档是给客户、实施方、第三方前端/后端集成团队使用的“公开云端 API 最小集合”说明。

当前公开给客户的云端能力只保留三类：

- `Workspace Context`：解析当前 API Key 对应的用户与默认工作空间
- `Models`：模型目录、路由、调用、用量、成本、额度
- `Billing`：钱包余额与账单记录

如果项目是 `Ruisi` 这类本地优先桌面产品，客户应该只接这三类云端 API。

## 2. 不再建议客户直接对接的接口域

以下接口域不建议继续作为客户公开 API：

- `knowledge`
- `conversations`
- `devices`
- `channels`
- `audit`
- `approvals`
- `workflows`
- `memory`
- `policy`

原因：

- 这些接口更适合作为平台内部控制面或历史兼容接口
- 对于本地优先产品，这些能力应由本地桌面数据层、本地 sidecar 或本地 gateway 承接

## 3. 统一接入口径

- `Base URL`: `https://paas.qeeshu.com`
- 鉴权方式：`Authorization: Bearer <API Key>`
- API Key 建议形态：`sk-...`
- `runtimeType`: 当前默认 `openclaw`
- `teamId / agentId`: 不作为客户配置项

## 4. 推荐联调顺序

### 第一步：验证 API Key

```http
GET /api/users/me/context
```

作用：

- 验证 API Key 是否可用
- 解析默认工作空间

### 第二步：验证模型目录

```http
GET /api/platform/models
```

作用：

- 确认当前账号能访问的模型列表

### 第三步：验证模型路由与调用

依次联调：

- `GET /api/platform/models/route`
- `GET /api/platform/models/resolve?model_name=...`
- `POST /api/platform/models/invoke`

### 第四步：验证计费与额度

依次联调：

- `GET /api/platform/models/usage`
- `GET /api/platform/models/cost`
- `GET /api/platform/models/quota`
- `GET /api/billing/wallet`
- `GET /api/billing/records`
- `GET /api/billing/summary`

## 5. 当前公开云端 API 清单

### 5.1 Workspace Context

- `GET /api/users/me/context`

### 5.2 Models

- `GET /api/platform/models`
- `GET /api/platform/models/providers`
- `GET /api/platform/models/runtimes`
- `GET /api/platform/models/route`
- `GET /api/platform/models/resolve`
- `POST /api/platform/models/invoke`
- `GET /api/platform/models/usage`
- `GET /api/platform/models/cost`
- `GET /api/platform/models/quota`

### 5.3 Billing

- `GET /api/billing/wallet`
- `GET /api/billing/records`
- `GET /api/billing/summary`

## 6. 客户应拿到的资料

如果客户做的是普通前端、驾驶舱、桌面 UI 或本地优先产品，建议只给：

1. 本文档
2. `sdk/docs/openapi/QeeClaw_Cloud_Public_API.openapi.yaml`
3. `sdk/docs/postman/QeeClaw_Cloud_Public_API.postman_collection.json`
4. `sdk/docs/postman/QeeClaw_Cloud_Public_API.postman_environment.json`
5. 项目专属 `Base URL + API Key` 发放方式

## 6.1 后端在线文档入口

如果后端已发布包含“公开 / 内部”双文档入口的版本，可直接访问：

- 客户公开版 Swagger：`/docs/public`
- 内部控制面 Swagger：`/docs/internal`
- 客户公开版 OpenAPI JSON：`/openapi-public.json`
- 内部控制面 OpenAPI JSON：`/openapi-internal.json`

以线上环境为例：

- `https://paas.qeeshu.com/docs/public`
- `https://paas.qeeshu.com/docs/internal`

## 7. 与其他文档的关系

- 本文档：客户公开版，适合直接交付
- `QeeClaw_第三方SDK与Platform_API对接文档_20260404.md`：接入总手册
- `QeeClaw_Platform_API_v1_域化接口说明_20260321.md`：更偏平台维护与高级集成，不建议直接作为普通客户第一份文档

## 8. 一句话结论

对 `Ruisi` 和类似的本地优先产品，客户公开云端 API 应收口为：

- `auth/context`
- `models/*`
- `billing/*`

其余业务域不再作为客户直接对接的公开云端 API。

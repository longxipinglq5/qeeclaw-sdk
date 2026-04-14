# QeeClaw Platform API v1 域化接口说明

最后更新：2026-04-05

> 归档说明：本文档已不再作为客户默认交付入口，仅供平台维护、历史追溯和内部高级集成参考。

## 1. 文档目的

本文档用于说明当前已经完成域化收口的 `QeeClaw Platform API v1` 命名空间，方便：

- `@qeeclaw/core-sdk` 对接
- `@qeeclaw/product-sdk` 对接
- Console / Demo Console 页面装配
- 后续 OpenAPI / SDK 自动生成扩展

## 1.1 文档定位与使用方式

本文档是 `Platform API v1` 的接口索引与命名空间说明，主要回答：

- 当前平台已经收口了哪些域接口
- 每个域挂在哪个统一前缀下
- `Core SDK / Product SDK` 当前分别映射到了哪些平台域

本文档不重点回答：

- 第三方团队该优先选 `Core SDK`、`Product SDK` 还是直接调 API
- 第三方最小接入顺序应该怎么走
- 客户联调时第一天先跑哪些能力

如果你现在站在客户或实施方视角，建议先看：

- [QeeClaw_第三方SDK与Platform_API对接文档_20260404.md](./QeeClaw_第三方SDK与Platform_API对接文档_20260404.md)
- [QeeClaw_Cloud_API_客户公开版_20260409.md](./QeeClaw_Cloud_API_客户公开版_20260409.md)

额外说明：

- 如果交付的是 `Ruisi` 这类“本地业务数据优先”的桌面产品，本文档中的很多业务域接口更适合作为平台内部控制面或历史兼容接口
- 对这类项目，不建议把 `knowledge / conversations / devices / channels / audit / workflows / approvals / memory / policy` 直接作为客户公开云端 API 暴露
- 此类产品的客户公开云端接口，应优先收口到 `auth/context + models/* + billing/*`

推荐阅读顺序：

1. 先读第三方对接文档，确认选型、鉴权、运行时范围和最小闭环
2. 再读本文档，核对具体域接口与 SDK 映射关系

## 2. 当前统一命名空间

当前平台域接口统一收口在以下前缀下：

- `/api/platform/devices`
- `/api/platform/models`
- `/api/platform/memory`
- `/api/platform/knowledge`
- `/api/platform/channels`
- `/api/platform/conversations`
- `/api/platform/approvals`
- `/api/platform/audit`
- `/api/platform/policy/*`

在控制台和客户沟通中，常见“中心”与接口域大致对应如下：

| 控制面中心 | 主要接口前缀 | 说明 |
| --- | --- | --- |
| 模型中心 | `/api/platform/models` | 模型目录、Provider 摘要、路由解析、轻量调用 |
| 记忆中心 | `/api/platform/memory` | 记忆写入、检索、清理、统计 |
| 知识中心 | `/api/platform/knowledge` | 知识上传、检索、下载、配置 |
| 渠道中心 | `/api/platform/channels` | 渠道总览、企微/飞书配置、个人微信链路 |
| 设备中心 | `/api/platform/devices` | 设备注册、引导、配对、在线态 |
| 会话中心 | `/api/platform/conversations` | 会话首页、群聊、消息、历史 |
| 审批中心 | `/api/platform/approvals` | 审批请求、审批列表、审批处理 |
| 审计中心 | `/api/platform/audit` | 审计事件、审计汇总 |
| 治理中心（聚合视角） | `/api/platform/policy/*` + `/api/platform/approvals` + `/api/platform/audit` | 在产品装配层里，审批、审计和策略检查可作为治理域聚合呈现 |

## 3. 鉴权约定

统一使用：

```http
Authorization: Bearer <token>
```

当前支持的认证形态：

- API Key（推荐给客户前端、前端 BFF、轻量后端集成）
- 用户登录态 token
- LLM Key
- 部分模型/策略场景兼容 AppKey

说明：

- `GET /api/users/me/context` 支持 `API Key`，推荐作为客户联调第一步
- `devices / channels / conversations / approvals / audit` 更推荐用户登录态 token
- `models / memory / policy / approval.request` 可使用用户 token 或 LLM Key

## 3.1 默认工作空间解析

在当前客户交付模式下，不建议要求客户手工填写 `teamId`。

推荐先调用：

- `GET /api/users/me/context`

用途：

- 验证 `API Key` 是否可用
- 返回当前用户可访问的 `teams`
- 返回平台选定的默认工作空间：`default_team_id / default_team_name / default_team_is_personal`

响应字段示例：

```json
{
  "code": 0,
  "data": {
    "id": 201,
    "username": "demo_user",
    "role": "USER",
    "is_enterprise_verified": true,
    "default_team_id": 19,
    "default_team_name": "企数科技",
    "default_team_is_personal": false,
    "teams": [
      {
        "id": 19,
        "name": "企数科技",
        "is_personal": false,
        "owner_id": 201
      }
    ]
  },
  "message": "查询成功"
}
```

推荐规则：

- 客户只保存 `baseUrl + apiKey`
- 应用启动后先取 `default_team_id`
- `runtime_type` 当前固定使用 `openclaw`
- `agent_id` 仅在具体业务实现确实需要时再由应用内部补充

## 4. 返回约定

平台接口统一优先采用：

```json
{
  "code": 0,
  "data": {},
  "message": "success"
}
```

约定：

- `code === 0` 表示成功
- 列表接口优先采用分页或聚合后的稳定结构
- 领域对象对 SDK 暴露时统一再映射为 `camelCase`

## 5. 已完成域

### 5.1 Device Hub

前缀：

- `/api/platform/devices`

当前接口：

- `GET /api/platform/devices`
- `GET /api/platform/devices/account-state`
- `POST /api/platform/devices/pair-code`
- `POST /api/platform/devices/claim`
- `POST /api/platform/devices/bootstrap`
- `PUT /api/platform/devices/{deviceId}`
- `DELETE /api/platform/devices/{deviceId}`
- `GET /api/platform/devices/online`

### 5.2 Model Hub

前缀：

- `/api/platform/models`

当前接口：

- `GET /api/platform/models`
  - 获取模型目录
- `GET /api/platform/models/providers`
  - 获取 Provider 聚合摘要
- `GET /api/platform/models/resolve?model_name=...`
  - 解析模型到具体 Provider 与 `provider_model_id`
- `POST /api/platform/models/invoke`
  - 轻量调用模型能力

### 5.3 Memory Plane

前缀：

- `/api/platform/memory`

当前接口：

- `POST /api/platform/memory/store`
- `POST /api/platform/memory/search`
- `DELETE /api/platform/memory/{entryId}`
- `DELETE /api/platform/memory/agent/{agentId}`
- `GET /api/platform/memory/stats`

### 5.4 Knowledge Hub

前缀：

- `/api/platform/knowledge`

当前接口：

- `POST /api/platform/knowledge/upload`
- `GET /api/platform/knowledge/list`
- `POST /api/platform/knowledge/delete`
- `GET /api/platform/knowledge/download`
- `GET /api/platform/knowledge/search`
- `GET /api/platform/knowledge/stats`
- `GET /api/platform/knowledge/config`
- `POST /api/platform/knowledge/config/update`

### 5.5 Channel Hub

前缀：

- `/api/platform/channels`

当前接口：

- `GET /api/platform/channels`
  - 获取渠道总览
- `GET /api/platform/channels/wechat-work/config`
- `POST /api/platform/channels/wechat-work/config`
- `GET /api/platform/channels/feishu/config`
- `POST /api/platform/channels/feishu/config`

### 5.6 Conversation Hub

前缀：

- `/api/platform/conversations`

当前接口：

- `GET /api/platform/conversations`
  - 获取会话首页装配数据
- `GET /api/platform/conversations/stats`
- `GET /api/platform/conversations/groups`
- `GET /api/platform/conversations/groups/{roomId}/messages`
- `GET /api/platform/conversations/history`
- `POST /api/platform/conversations/messages`

### 5.7 Policy / Approval / Audit Hub

前缀：

- `/api/platform/policy/*`
- `/api/platform/approvals`
- `/api/platform/audit`

当前接口：

- `POST /api/platform/policy/tool-access/check`
- `POST /api/platform/policy/data-access/check`
- `POST /api/platform/policy/exec-access/check`
- `POST /api/platform/approvals/request`
- `GET /api/platform/approvals`
- `GET /api/platform/approvals/{approvalId}`
- `POST /api/platform/approvals/{approvalId}/resolve`
- `GET /api/platform/audit/events`
- `GET /api/platform/audit/summary`

## 6. 客户联调资产与接口样例

客户联调时，建议直接使用以下附加资产：

- `sdk/docs/archive/QeeClaw_Platform_API_v1.postman_collection.json`
- `sdk/docs/archive/QeeClaw_Platform_API_v1.postman_environment.json`

如果客户不是 `TypeScript` 团队，通常优先给 `Postman` 集合，再配合本文档核对接口域。

### 6.1 常用参数命名约定

平台域接口当前常见参数风格如下：

| 参数 | 常见位置 | 说明 |
| --- | --- | --- |
| `default_team_id` | `GET /api/users/me/context` 返回字段 | 平台自动解析出的默认工作空间 |
| `team_id` | Query / Body / FormData | 团队范围，强烈建议显式传 |
| `runtime_type` | Query / Body / FormData | 运行时范围，如 `openclaw` |
| `agent_id` | Query / Body / FormData | 目标 agent |
| `device_id` | Query / Body / FormData | 目标设备，仅在支持 device bridge 时使用 |
| `page` / `page_size` | Query | 审批、审计等分页接口 |
| `page` / `pageSize` | Query | 当前知识中心分页接口沿用该风格 |

### 6.2 统一返回结构

平台接口统一优先返回：

```json
{
  "code": 0,
  "data": {},
  "message": "success"
}
```

其中：

- `code = 0` 表示成功
- `data` 为业务载荷
- `message` 为状态描述

### 6.3 关键接口参数与返回样例

#### 工作空间上下文：获取默认工作空间

请求：

```bash
curl -X GET "$BASE_URL/api/users/me/context" \
  -H "Authorization: Bearer $API_KEY"
```

响应示例：

```json
{
  "code": 0,
  "data": {
    "id": 201,
    "username": "demo_user",
    "role": "USER",
    "default_team_id": 19,
    "default_team_name": "企数科技",
    "default_team_is_personal": false,
    "teams": [
      {
        "id": 19,
        "name": "企数科技",
        "is_personal": false,
        "owner_id": 201
      }
    ]
  },
  "message": "查询成功"
}
```

#### 模型中心：获取模型目录

请求：

```bash
curl -X GET "$BASE_URL/api/platform/models" \
  -H "Authorization: Bearer $API_KEY"
```

响应示例：

```json
{
  "code": 0,
  "data": [
    {
      "id": 101,
      "provider_name": "openai",
      "model_name": "gpt-4.1-mini",
      "provider_model_id": "gpt-4.1-mini",
      "label": "GPT-4.1 Mini",
      "is_preferred": true,
      "availability_status": "active",
      "unit_price": 0.00015,
      "output_unit_price": 0.0006,
      "currency": "USD"
    }
  ],
  "message": "success"
}
```

#### 记忆中心：写入长期记忆

请求：

```bash
curl -X POST "$BASE_URL/api/platform/memory/store" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": 10001,
    "runtime_type": "openclaw",
    "agent_id": "sales-copilot",
    "content": "客户更关注私有化部署与数据隔离",
    "category": "fact",
    "importance": 0.95
  }'
```

响应示例：

```json
{
  "code": 0,
  "data": {
    "id": "mem-1740000000001",
    "content": "客户更关注私有化部署与数据隔离",
    "category": "fact",
    "importance": 0.95,
    "team_id": 10001,
    "runtime_type": "openclaw",
    "agent_id": "sales-copilot",
    "source_session": null,
    "created_at": "2026-04-05T10:00:00Z"
  },
  "message": "success"
}
```

#### 知识中心：检索知识

请求：

```bash
curl -X GET "$BASE_URL/api/platform/knowledge/search?team_id=10001&runtime_type=openclaw&agent_id=sales-copilot&query=%E5%AE%89%E8%A3%85%E6%8C%87%E5%8D%97&limit=5" \
  -H "Authorization: Bearer $TOKEN"
```

响应示例：

```json
{
  "code": 0,
  "data": [
    {
      "source_name": "安装指南.pdf",
      "filename": "安装指南.pdf",
      "snippet": "这里是命中的知识片段摘要",
      "status": "indexed",
      "updated_at": "2026-04-05T09:55:00Z"
    }
  ],
  "message": "success"
}
```

#### 会话中心：获取会话首页

请求：

```bash
curl -X GET "$BASE_URL/api/platform/conversations?team_id=10001&group_limit=10&history_limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

响应示例：

```json
{
  "code": 0,
  "data": {
    "stats": {
      "group_count": 12,
      "msg_count": 582,
      "entity_count": 84,
      "history_count": 20
    },
    "groups": [
      {
        "room_id": "room-sales-001",
        "room_name": "销售一群",
        "last_active": "2026-04-05T09:58:00Z",
        "msg_count": 120,
        "member_count": 18
      }
    ],
    "history": [
      {
        "id": 9001,
        "sender_id": 1,
        "agent_id": 10,
        "channel_id": "manual",
        "direction": "user_to_agent",
        "content": "帮我总结昨天的客户问题",
        "created_time": "2026-04-05T09:59:00Z"
      }
    ]
  },
  "message": "success"
}
```

#### 审批中心：创建审批申请

请求：

```bash
curl -X POST "$BASE_URL/api/platform/approvals/request" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "approval_type": "exec_access",
    "title": "申请高风险命令执行",
    "reason": "需要管理员审批",
    "risk_level": "critical",
    "payload": {
      "command": "rm -rf /data/archive"
    }
  }'
```

响应示例：

```json
{
  "code": 0,
  "data": {
    "approval_id": "apr-1740000000123",
    "status": "pending",
    "approval_type": "exec_access",
    "title": "申请高风险命令执行",
    "reason": "需要管理员审批",
    "risk_level": "critical",
    "payload": {
      "command": "rm -rf /data/archive"
    },
    "requested_by": {
      "user_id": 1,
      "username": "demo"
    },
    "created_at": "2026-04-05T10:00:00Z",
    "expires_at": "2026-04-05T11:00:00Z"
  },
  "message": "success"
}
```

#### 审计中心：查询审计事件

请求：

```bash
curl -X GET "$BASE_URL/api/platform/audit/events?scope=mine&page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"
```

响应示例：

```json
{
  "code": 0,
  "data": {
    "total": 2,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "event_id": "evt-1740000000456",
        "category": "operation",
        "event_type": "SDK_DEMO",
        "title": "QeeClaw Core SDK quick start",
        "module": "README",
        "path": "/api/platform/models",
        "status": "success",
        "risk_level": "low",
        "actor": {
          "user_id": 1,
          "username": "demo"
        },
        "created_at": "2026-04-05T10:01:00Z"
      }
    ]
  },
  "message": "success"
}
```

## 7. 对应 SDK 映射

### 7.1 Core SDK

当前已映射：

- `devices`
- `models`
- `memory`
- `knowledge`
- `channels`
- `conversations`
- `policy`
- `approval`
- `audit`

### 7.2 Product SDK

当前已映射：

- `deviceCenter`
- `knowledgeCenter`
- `governanceCenter`
- `channelCenter`
- `conversationCenter`

## 8. 当前状态结论

当前 `Platform API v1` 已经具备以下条件：

- 统一命名空间已建立
- 关键域已完成第一版收口
- Core SDK 已对接主要平台域
- Product SDK 已具备阶段 5 的核心装配能力
- Demo Console 已可直接演示模型、渠道、会话、审批、审计等中心能力

这意味着当前 SDK 化计划中的：

- 阶段 4：Control Plane 域化重构
- 阶段 5：Product SDK 与产品模块装配

已经形成第一版可运行、可验证、可继续扩展的落地结果。

如果用于客户交付，建议把本文档作为“接口附录”或“接口索引”，而不是单独替代第三方对接指南。

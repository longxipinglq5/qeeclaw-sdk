# QeeClaw Bridge Server API 参考手册

> 最后更新：2026-04-16 · 适用版本：Bridge Server v0.5.0
> 本文档面向客户研发、实施方及第三方对接团队

---

## 1. 概述

QeeClaw Bridge Server 是运行在边缘设备（本地 PC / 服务器）上的 HTTP 服务，提供 AI 智体对话、知识库、会话管理、设备管理等全部 SDK 能力的本地实现。

- **默认地址**：`http://127.0.0.1:21747`
- **协议**：HTTP/1.1，JSON 请求/响应
- **流式**：SSE (Server-Sent Events) 用于 `/invoke/stream`

## 2. 鉴权

Bridge Server 支持可选鉴权。通过环境变量 `HERMES_BRIDGE_API_KEY` 控制：

- **未设置或空值**：免鉴权，所有请求直接放行
- **已设置**：每个请求须携带 `Authorization: Bearer <api-key>` 请求头

```bash
# 启用鉴权
export HERMES_BRIDGE_API_KEY="your-secret-key"
```

## 3. 响应格式

### 3.1 原生路径

`/health`, `/invoke`, `/sessions/*`, `/agents/*`, `/knowledge/*`, `/memory/*`, `/skills/*`, `/tools`, `/cron/*`, `/gateway/*`, `/wechat/*` 等原生路径直接返回 JSON：

```json
{
  "status": "ok",
  "version": "0.5.0",
  ...
}
```

### 3.2 SDK 兼容路径（/api/*）

所有 `/api/*` 路径使用统一信封格式：

```json
{
  "code": 0,
  "data": { ... },
  "message": "success"
}
```

错误时 `code` 非零，`message` 为错误描述，HTTP 状态码也会对应调整（400/404/500 等）。

`@qeeclaw/core-sdk` 的 HttpClient 会自动检测并解包信封格式，开发者直接拿到 `data` 对象。

### 3.3 字段命名

所有响应字段使用 **snake_case**（如 `team_id`, `created_at`）。TypeScript SDK 在类型层做 camelCase 映射。

---

## 4. API 端点详细说明

### 4.1 健康检查

#### `GET /health`

检查 Bridge Server 和 hermes-agent 引擎的运行状态。

**无需鉴权。**

响应示例：
```json
{
  "status": "ok",
  "version": "0.5.0",
  "hermes_available": true,
  "knowledge_base": {
    "available": true,
    "total_documents": 5
  }
}
```

---

### 4.2 对话 (Invoke)

#### `POST /invoke`

非流式对话调用。

请求体：
```json
{
  "prompt": "你好，请介绍一下公司产品",
  "agent_profile": "default",
  "session_id": "ses_abc123",
  "user_id": "user_001",
  "system_prompt": "",
  "max_turns": 10,
  "use_knowledge": true,
  "knowledge_query": ""
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | 是 | 用户消息 |
| `agent_profile` | string | 否 | 智体 Profile（默认 `default`） |
| `session_id` | string | 否 | 会话 ID（空则自动创建） |
| `user_id` | string | 否 | 用户 ID |
| `system_prompt` | string | 否 | 覆盖系统提示词 |
| `max_turns` | int | 否 | 上下文保留轮数 |
| `use_knowledge` | bool | 否 | 是否启用 RAG 知识检索 |

响应示例：
```json
{
  "response": "您好！我是 QeeClaw 部署的 AI 助手...",
  "session_id": "ses_abc123",
  "turn_count": 1,
  "agent_profile": "default",
  "knowledge_used": false
}
```

#### `POST /invoke/stream`

SSE 流式对话。请求体同 `/invoke`，响应为 `text/event-stream`：

```
data: {"type": "token", "content": "您"}
data: {"type": "token", "content": "好"}
data: {"type": "done", "session_id": "ses_abc123"}
```

---

### 4.3 智体管理 (Agent)

#### `GET /agents`

列出全部智体 Profile（含内建 + 自定义）。

响应示例：
```json
{
  "agents": [
    { "name": "default", "display_name": "通用助手", "model": "", "temperature": 0.7 },
    { "name": "coder", "display_name": "编程助手", "model": "", "temperature": 0.3 }
  ]
}
```

#### `GET /agents/{name}`

获取指定智体详情。

#### `POST /agents`

创建或更新智体。

请求体：
```json
{
  "name": "sales",
  "display_name": "销售助手",
  "system_prompt": "你是一个专业的销售助手...",
  "model": "gpt-4.1-mini",
  "temperature": 0.6,
  "tools_enabled": true
}
```

#### SDK 兼容路径

| 方法 | 路径 | 对应功能 |
|------|------|---------|
| GET | `/api/agent/my-agents` | 列出智体 |
| GET | `/api/agent/tools` | 工具列表 |
| POST | `/api/agent/create` | 创建智体 |
| PUT | `/api/agent/{id}` | 更新智体 |
| DELETE | `/api/agent/{id}` | 删除智体 |

---

### 4.4 模型 (Models)

所有路径均为 `/api/platform/models/*`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/platform/models` | 模型列表 |
| GET | `/api/platform/models/providers` | Provider 摘要 |
| GET | `/api/platform/models/runtimes` | 运行时类型列表 |
| GET | `/api/platform/models/resolve` | 模型解析（根据 query params） |
| GET | `/api/platform/models/route` | 当前路由规则 |
| PUT | `/api/platform/models/route` | 设置路由规则 |
| GET | `/api/platform/models/usage` | 调用量统计 |
| GET | `/api/platform/models/cost` | 成本统计 |
| GET | `/api/platform/models/quota` | 配额查询 |

**响应均使用信封格式。**

---

### 4.5 用户身份 (IAM)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/users/me` | 当前用户档案 |
| PUT | `/api/users/me` | 更新用户档案 |
| PUT | `/api/users/me/preference` | 更新用户偏好 |
| GET | `/api/users/products` | 可用产品列表 |
| GET | `/api/users` | 用户列表 |

---

### 4.6 租户 (Tenant)

#### `GET /api/users/me/context`

获取当前工作空间上下文，推荐作为客户联调第一步。

响应示例：
```json
{
  "code": 0,
  "data": {
    "id": 1,
    "username": "local-admin",
    "role": "admin",
    "is_enterprise_verified": false,
    "default_team_id": 1,
    "default_team_name": "默认团队",
    "teams": [
      { "id": 1, "name": "默认团队", "is_personal": false, "owner_id": 1 }
    ]
  }
}
```

#### `GET /api/company/verification`

获取企业认证状态。本地模式默认返回 `{ "status": "none" }`。

#### `POST /api/company/verification`

提交企业认证。请求体：`{ "company_name": "..." }`。

#### `POST /api/company/verification/approve`

审批企业认证（本地模式直接返回 approved）。

---

### 4.7 计费 (Billing)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/billing/wallet` | 钱包余额 |
| GET | `/api/billing/records` | 计费记录 |
| GET | `/api/billing/summary` | 计费摘要 |

本地模式返回默认值（余额 0、无记录）。

---

### 4.8 会话中心 (Conversations)

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/platform/conversations` | 首页聚合 | `?team_id=1&group_limit=10&history_limit=20` |
| GET | `/api/platform/conversations/stats` | 统计 | `?team_id=1` |
| GET | `/api/platform/conversations/groups` | 群聊列表 | `?team_id=1&limit=20` |
| GET | `/api/platform/conversations/groups/{roomId}/messages` | 群聊消息 | `?team_id=1&limit=50` |
| GET | `/api/platform/conversations/history` | 历史消息 | `?team_id=1&channel_id=...&limit=50` |
| POST | `/api/platform/conversations/messages` | 发送消息 | body: `{ "team_id", "content", "agent_id?" }` |

---

### 4.9 渠道 (Channels)

#### 渠道总览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/platform/channels` | 渠道总览 |
| GET | `/api/platform/channels?team_id=1` | 指定团队 |

#### 渠道配置

| 方法 | 路径 | 渠道 |
|------|------|------|
| GET/POST | `/api/platform/channels/wechat-work/config` | 企业微信 |
| GET/POST | `/api/platform/channels/feishu/config` | 飞书 |
| GET/POST | `/api/platform/channels/wechat-personal-plugin/config` | 个人微信插件 |
| GET | `/api/platform/channels/wechat-personal-openclaw/config` | OpenClaw 微信 |

#### 渠道绑定

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/platform/channels/bindings` | 绑定列表 |
| POST | `/api/platform/channels/bindings/create` | 创建绑定 |
| POST | `/api/platform/channels/bindings/disable` | 停用绑定 |
| POST | `/api/platform/channels/bindings/regenerate-code` | 重新生成码 |

请求体（create）：
```json
{
  "team_id": 1,
  "binding_type": "user",
  "binding_target_id": "target_001",
  "binding_target_name": "客服小美"
}
```

#### QR 扫码

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/platform/channels/wechat-personal-openclaw/qr/start` | 发起扫码 |
| GET | `/api/platform/channels/wechat-personal-openclaw/qr/status` | 扫码状态 |

---

### 4.10 知识库 (Knowledge)

#### 原生路径

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/knowledge/upload` | 上传文档 |
| GET | `/knowledge/list` | 文档列表 |
| GET | `/knowledge/document/{id}` | 文档详情 |
| POST | `/knowledge/search` | 向量检索 |
| POST | `/knowledge/delete/{id}` | 删除文档 |
| GET | `/knowledge/stats` | 统计信息 |

#### SDK 兼容路径

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/platform/knowledge/list` | 文档列表 | `?team_id=1&runtime_type=openclaw` |
| GET | `/api/platform/knowledge/search` | 检索（GET 方式） | `?query=关键词&team_id=1&limit=5` |
| POST | `/api/platform/knowledge/upload` | 上传文档 | multipart 或 JSON |
| POST | `/api/platform/knowledge/delete` | 删除文档 | body: `{ "source_name": "..." }` |
| GET | `/api/platform/knowledge/download` | 下载文件 | `?source_name=xxx` |
| GET | `/api/platform/knowledge/stats` | 统计 | `?team_id=1` |
| GET | `/api/platform/knowledge/config` | 配置查看 | `?team_id=1` |
| POST | `/api/platform/knowledge/config/update` | 更新配置 | body: `{ "watch_dir": "/path" }` |

---

### 4.11 设备 (Devices)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/platform/devices` | 设备列表（本地模式返回当前设备） |
| GET | `/api/platform/devices/account-state` | 账号状态 |
| GET | `/api/platform/devices/online` | 运行时在线状态 |
| POST | `/api/platform/devices/bootstrap` | 设备引导注册 |
| POST | `/api/platform/devices/pair-code` | 生成配对码 |
| POST | `/api/platform/devices/claim` | 认领设备 |
| PUT | `/api/platform/devices/{id}` | 更新设备名称 |
| DELETE | `/api/platform/devices/{id}` | 删除设备（本地 stub） |

bootstrap 请求体：
```json
{
  "installation_id": "inst_001",
  "device_name": "我的工作机",
  "hostname": "macbook-pro",
  "os_info": "macOS 15.3"
}
```

---

### 4.12 文档 (File)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/documents` | 文档列表（扫描 `{HERMES_HOME}/documents/`） |
| GET | `/api/documents/{id}` | 文档详情 |
| GET | `/api/products/{id}/documents` | 产品关联文档（返回空列表） |

---

### 4.13 工作流 (Workflow)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workflows` | 工作流列表 |
| POST | `/api/workflows` | 创建/更新工作流 |
| GET | `/api/workflows/{id}` | 工作流详情 |
| POST | `/api/workflows/{id}/run` | 运行工作流 |
| GET | `/api/workflows/executions/{id}/logs` | 执行日志 |

创建请求体：
```json
{
  "name": "每日销售报告",
  "description": "自动生成销售日报",
  "nodes": [],
  "edges": []
}
```

运行响应：
```json
{
  "code": 0,
  "data": {
    "execution_id": "exec_abc123"
  }
}
```

---

### 4.14 审批 (Approval)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/platform/approvals` | 审批列表 |
| POST | `/api/platform/approvals/request` | 发起审批请求 |
| GET | `/api/platform/approvals/{id}` | 审批详情 |
| POST | `/api/platform/approvals/{id}/resolve` | 处理审批 |

发起审批请求体：
```json
{
  "approval_type": "tool_access",
  "title": "请求使用终端工具",
  "reason": "需要执行部署脚本",
  "risk_level": "medium",
  "payload": {}
}
```

处理审批请求体：
```json
{
  "action": "approved",
  "comment": "已确认安全"
}
```

---

### 4.15 审计 (Audit)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/platform/audit/events` | 事件列表（分页） |
| GET | `/api/platform/audit/summary` | 汇总统计 |
| POST | `/api/platform/audit/events` | 记录事件 |

Query 参数：`?page=1&page_size=20&category=operation&scope=all`

汇总响应示例：
```json
{
  "code": 0,
  "data": {
    "total": 42,
    "operation_count": 35,
    "approval_count": 7,
    "pending_approval_count": 2,
    "approved_approval_count": 3,
    "rejected_approval_count": 1,
    "expired_approval_count": 1
  }
}
```

---

### 4.16 API Key 管理

#### App Key

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/users/app-keys` | App Key 分页列表 |
| POST | `/api/users/app-keys` | 创建 App Key |
| DELETE | `/api/users/app-keys/{id}` | 删除 |
| PATCH | `/api/users/app-keys/{id}` | 启用/停用 |
| PUT | `/api/users/app-keys/{id}/name` | 重命名 |
| POST | `/api/users/app-keys/default/token` | 签发默认 Token |

创建请求体：`{ "name": "我的API密钥" }`

创建响应（含明文 secret，仅返回一次）：
```json
{
  "code": 0,
  "data": {
    "id": 123456,
    "name": "我的API密钥",
    "app_key": "ak_a1b2c3d4e5f6g7h8",
    "app_secret": "sk_xxxxxxxxxxxxxxxxxxxx",
    "is_active": true
  }
}
```

#### LLM Key

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/llm/keys` | LLM Key 列表 |
| POST | `/api/llm/keys` | 创建 |
| PUT | `/api/llm/keys/{id}` | 更新 |
| DELETE | `/api/llm/keys/{id}` | 删除 |

创建请求体：
```json
{
  "provider": "openai",
  "api_key": "sk-...",
  "name": "OpenAI 主密钥"
}
```

---

### 4.17 策略 (Policy)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/platform/policy/tool-access/check` | 工具访问检查 |
| POST | `/api/platform/policy/data-access/check` | 数据访问检查 |
| POST | `/api/platform/policy/exec-access/check` | 执行权限检查 |

本地模式下所有检查均返回允许：

```json
{
  "code": 0,
  "data": {
    "allowed": true,
    "requires_approval": false,
    "reason": "Local mode: all access allowed"
  }
}
```

---

### 4.18 语音 (Voice) — 未实现

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/asr` | 语音识别 |
| POST | `/api/tts` | 语音合成 |
| POST | `/api/audio/speech` | 音频生成 |

当前返回 **HTTP 501 Not Implemented**。后续版本将接入本地或云端 ASR/TTS 引擎。

---

### 4.19 记忆 (Memory)

#### SDK 兼容路径

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/platform/memory/store` | 存入记忆 |
| POST | `/api/platform/memory/search` | 搜索记忆 |
| GET | `/api/platform/memory/stats` | 统计 |
| DELETE | `/api/platform/memory/{id}` | 删除单条 |
| DELETE | `/api/platform/memory/agent/{agentId}` | 清除 agent 全部记忆 |

存入请求体：
```json
{
  "content": "客户A偏好红色包装",
  "category": "user_preference",
  "importance": 0.8,
  "agent_id": "sales"
}
```

#### 原生路径

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/memory/store` | 存入 |
| POST | `/memory/search` | 搜索 |
| POST | `/memory/clear` | 清除 |
| GET | `/memory/stats` | 统计 |

---

### 4.20 技能、工具、定时任务

#### 技能 (Skills)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/skills` | 列出已安装技能 |
| GET | `/skills/{name}` | 技能详情 |
| POST | `/skills/install` | 安装技能 |
| POST | `/skills/uninstall` | 卸载技能 |

#### 工具 (Tools)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tools` | 列出已启用工具 |
| PUT | `/tools` | 配置启用/停用 |

#### 定时任务 (Cron)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/cron` | 列出任务 |
| POST | `/cron` | 创建任务 |
| DELETE | `/cron/{id}` | 删除任务 |

---

## 5. core-sdk 模块与 Bridge 端点映射

| core-sdk 模块 | Bridge 路径前缀 | 端点数 | 状态 |
|---------------|----------------|--------|------|
| `agent` | `/api/agent/*`, `/agents/*` | 11 | 已实现 |
| `models` | `/api/platform/models/*` | 9 | 已实现 |
| `iam` | `/api/users/*` | 5 | 已实现 |
| `tenant` | `/api/users/me/context`, `/api/company/*` | 4 | 已实现 |
| `billing` | `/api/billing/*` | 3 | 已实现 |
| `conversations` | `/api/platform/conversations/*` | 6 | 已实现 |
| `channels` | `/api/platform/channels/*` | 14 | 已实现 |
| `memory` | `/api/platform/memory/*` | 5 | 已实现 |
| `knowledge` | `/api/platform/knowledge/*` | 8 | 已实现 |
| `devices` | `/api/platform/devices/*` | 8 | 已实现 |
| `file` | `/api/documents/*` | 3 | 已实现 |
| `workflow` | `/api/workflows/*` | 5 | 已实现 |
| `approval` | `/api/platform/approvals/*` | 4 | 已实现 |
| `audit` | `/api/platform/audit/*` | 3 | 已实现 |
| `apikey` | `/api/users/app-keys/*`, `/api/llm/keys/*` | 10 | 已实现 |
| `policy` | `/api/platform/policy/*` | 3 | 已实现 |
| `voice` | `/api/asr`, `/api/tts`, `/api/audio/speech` | 3 | Stub (501) |

**总计：17/17 模块覆盖，145+ 端点。**

---

## 6. 本地数据存储

所有持久化数据位于 `HERMES_HOME`（默认 `~/.qeeclaw_hermes/`）：

| 路径 | 说明 |
|------|------|
| `sessions/ses_*.json` | 会话数据 |
| `sessions/_profiles.json` | 自定义智体 Profile |
| `memory/entries.json` | 记忆条目 |
| `knowledge/` | ChromaDB 向量库数据 |
| `documents/` | 本地文档目录 |
| `workflows.json` | 工作流定义 |
| `device_info.json` | 设备信息 |
| `approvals.json` | 审批记录 |
| `audit_events.json` | 审计事件（保留最近 1000 条） |
| `api_keys.json` | App Key & LLM Key |
| `knowledge_config.json` | 知识库配置（watch_dir 等） |

---

## 7. 快速上手示例

### 使用 TypeScript SDK

```ts
import { createQeeClawClient } from "@qeeclaw/core-sdk";

const client = createQeeClawClient({
  baseUrl: "http://127.0.0.1:21747",
  token: "none",  // 本地模式免鉴权
});

// 1. 验证连通性
const context = await client.tenant.getCurrentContext();
console.log("当前团队:", context.teams[0]?.name);

// 2. 查看可用模型
const models = await client.models.listAvailable();

// 3. 查看钱包
const wallet = await client.billing.getWallet();

// 4. 知识库检索
const results = await client.knowledge.search({
  teamId: 1, query: "产品报价", limit: 5,
});

// 5. 审计日志
const audit = await client.audit.getSummary();
```

### 使用 curl

```bash
# 健康检查
curl http://127.0.0.1:21747/health

# 对话
curl -X POST http://127.0.0.1:21747/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "你好"}'

# 获取工作空间上下文
curl http://127.0.0.1:21747/api/users/me/context

# 知识库检索
curl "http://127.0.0.1:21747/api/platform/knowledge/search?query=test&team_id=1"

# 创建 App Key
curl -X POST http://127.0.0.1:21747/api/users/app-keys \
  -H "Content-Type: application/json" \
  -d '{"name": "测试密钥"}'
```

---

## 8. 推荐联调顺序

```
1. GET  /health                           → 确认服务启动
2. GET  /api/users/me/context             → 获取工作空间
3. GET  /api/platform/models              → 确认可用模型
4. POST /invoke                           → 跑通第一次对话
5. GET  /api/platform/knowledge/list      → 确认知识库
6. GET  /api/platform/devices             → 确认设备状态
7. GET  /api/platform/audit/summary       → 确认审计系统
```

---

## 9. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.5.0 | 2026-04-16 | 补齐全部 17 个 core-sdk 模块（新增 tenant/file/workflow/devices/approval/audit/apikey/policy/voice + channels 补全 + knowledge 新路径），145+ 端点，167 测试全部通过 |
| v0.4.0 | 2026-04-15 | Phase 1 SDK 兼容（agent/models/iam/conversations/billing/channels），114 测试通过 |
| v0.3.0 | 2026-04-14 | 新增 memory/skills/tools/cron 接口 |
| v0.2.0 | 2026-04-12 | 多智体 Profile、会话管理、知识库 |
| v0.1.0 | 2026-04-08 | 初始版本，invoke/health/gateway |

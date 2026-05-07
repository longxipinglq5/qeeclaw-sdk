# QeeClaw Hermes Bridge

QeeClaw TypeScript SDK 与 [hermes-agent](https://github.com/NousResearch/hermes-agent) 之间的轻量级 HTTP 桥接服务。

> 最后更新：2026-04-16 · Bridge Server v0.5.0 · 145+ API 端点 · 覆盖 core-sdk 全部 17 个模块

## 快速开始

### 前置要求

- Python 3.11+
- `pip install openai` (最小依赖)
- 可选：`pip install lancedb onnxruntime tokenizers numpy`（本地知识库向量检索）

### 启动

```bash
# 设置 hermes-agent 源码路径（默认自动检测 vendor/hermes-agent）
export QEECLAW_HERMES_AGENT_DIR=/path/to/hermes-agent

# 设置 API Key（fallback 模式使用）
export OPENROUTER_API_KEY=your-key-here

# 启动桥接服务
python bridge_server.py
```

服务默认监听 `http://127.0.0.1:21747`。

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QEECLAW_HERMES_BRIDGE_HOST` | `127.0.0.1` | 监听地址 |
| `QEECLAW_HERMES_BRIDGE_PORT` | `21747` | 监听端口 |
| `QEECLAW_HERMES_AGENT_DIR` | `../vendor/hermes-agent` | hermes-agent 源码路径 |
| `HERMES_HOME` | `~/.qeeclaw_hermes` | 数据持久化根目录 |
| `HERMES_BRIDGE_API_KEY` | _(空=免鉴权)_ | Bridge 鉴权密钥 |
| `OPENROUTER_API_KEY` | - | OpenRouter API Key (fallback) |
| `OPENAI_API_KEY` | - | OpenAI API Key (fallback) |

## 架构

```
业务应用层 (qeeshu-spark / HubOS / Web)
      │  HTTP / SSE
      ▼
bridge_server.py (本服务)  ← 145+ API 端点
      │  Python import
      ▼
hermes-agent (AIAgent / ToolRegistry / Memory)
      │
      ▼
LLM Provider (OpenRouter / z.ai / Kimi / DeepSeek / ...)
```

## API 端点总览

Bridge Server 暴露两类路径：

- **原生路径** (`/health`, `/invoke`, `/sessions`, ...) — 直接返回 JSON
- **SDK 兼容路径** (`/api/*`) — 使用信封格式 `{ code: 0, data: ..., message: "success" }`

### 核心 — 健康检查 & 对话

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/health` | 健康检查（免鉴权） | — |
| POST | `/invoke` | 非流式对话 | — |
| POST | `/invoke/stream` | SSE 流式对话 | — |

### 智体管理 (Agent)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/agents` | 列出智体 Profile | `agent` |
| GET | `/agents/{name}` | 智体详情 | `agent` |
| POST | `/agents` | 创建/更新智体 | `agent` |
| POST | `/agents/{name}/delete` | 删除智体 | `agent` |
| GET | `/api/agent/my-agents` | SDK 兼容 — 列出智体 | `agent` |
| GET | `/api/agent/tools` | SDK 兼容 — 工具列表 | `agent` |
| POST | `/api/agent/create` | SDK 兼容 — 创建智体 | `agent` |
| PUT | `/api/agent/{id}` | SDK 兼容 — 更新智体 | `agent` |
| DELETE | `/api/agent/{id}` | SDK 兼容 — 删除智体 | `agent` |
| GET | `/agent_config/default` | 默认智体配置 | `agent` |
| GET | `/agent_config/{name}` | 指定智体配置 | `agent` |

### 会话管理 (Session)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/sessions` | 列出会话 | — |
| GET | `/sessions/stats` | 会话统计 | — |
| GET | `/sessions/{id}` | 会话详情 | — |
| POST | `/sessions` | 创建会话 | — |
| POST | `/sessions/{id}/clear` | 清空会话历史 | — |
| POST | `/sessions/{id}/delete` | 删除会话 | — |

### 记忆 (Memory)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| POST | `/api/platform/memory/store` | 存入记忆 | `memory` |
| POST | `/api/platform/memory/search` | 搜索记忆 | `memory` |
| GET | `/api/platform/memory/stats` | 记忆统计 | `memory` |
| DELETE | `/api/platform/memory/{id}` | 删除单条记忆 | `memory` |
| DELETE | `/api/platform/memory/agent/{agentId}` | 清除 agent 记忆 | `memory` |
| POST | `/memory/store` | 原生路径 — 存入 | — |
| POST | `/memory/search` | 原生路径 — 搜索 | — |
| POST | `/memory/clear` | 原生路径 — 清除 | — |
| GET | `/memory/stats` | 原生路径 — 统计 | — |

### 技能 (Skills)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/skills` | 列出已安装技能 | — |
| GET | `/skills/{name}` | 技能详情 | — |
| POST | `/skills/install` | 安装技能 | — |
| POST | `/skills/uninstall` | 卸载技能 | — |

### 工具 (Tools)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/tools` | 列出已启用工具 | — |
| PUT | `/tools` | 配置工具启用/停用 | — |

### 定时任务 (Cron)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/cron` | 列出定时任务 | — |
| POST | `/cron` | 创建定时任务 | — |
| DELETE | `/cron/{id}` | 删除定时任务 | — |

### 知识库 (Knowledge)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| POST | `/knowledge/upload` | 上传文档（原生） | — |
| GET | `/knowledge/list` | 列出文档（原生） | — |
| GET | `/knowledge/document/{id}` | 文档详情（原生） | — |
| POST | `/knowledge/search` | 向量检索（原生） | — |
| POST | `/knowledge/delete/{id}` | 删除文档（原生） | — |
| GET | `/knowledge/stats` | 知识库统计（原生） | — |
| GET | `/api/platform/knowledge/list` | SDK 兼容 — 列表 | `knowledge` |
| GET | `/api/platform/knowledge/search` | SDK 兼容 — GET 检索 | `knowledge` |
| POST | `/api/platform/knowledge/upload` | SDK 兼容 — 上传 | `knowledge` |
| POST | `/api/platform/knowledge/delete` | SDK 兼容 — 删除 | `knowledge` |
| GET | `/api/platform/knowledge/download` | SDK 兼容 — 下载 | `knowledge` |
| GET | `/api/platform/knowledge/stats` | SDK 兼容 — 统计 | `knowledge` |
| GET | `/api/platform/knowledge/config` | SDK 兼容 — 配置查看 | `knowledge` |
| POST | `/api/platform/knowledge/config/update` | SDK 兼容 — 配置更新 | `knowledge` |

### 模型 (Models)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/platform/models` | 模型列表 | `models` |
| GET | `/api/platform/models/providers` | Provider 摘要 | `models` |
| GET | `/api/platform/models/runtimes` | 运行时列表 | `models` |
| GET | `/api/platform/models/resolve` | 模型解析 | `models` |
| GET | `/api/platform/models/route` | 路由规则查看 | `models` |
| PUT | `/api/platform/models/route` | 路由规则设置 | `models` |
| GET | `/api/platform/models/usage` | 用量统计 | `models` |
| GET | `/api/platform/models/cost` | 成本统计 | `models` |
| GET | `/api/platform/models/quota` | 配额查询 | `models` |

### 用户身份 (IAM)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/users/me` | 当前用户档案 | `iam` |
| PUT | `/api/users/me` | 更新用户档案 | `iam` |
| PUT | `/api/users/me/preference` | 更新偏好 | `iam` |
| GET | `/api/users/products` | 产品列表 | `iam` |
| GET | `/api/users` | 用户列表 | `iam` |

### 租户 (Tenant)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/users/me/context` | 工作空间上下文 | `tenant` |
| GET | `/api/company/verification` | 企业认证状态 | `tenant` |
| POST | `/api/company/verification` | 提交企业认证 | `tenant` |
| POST | `/api/company/verification/approve` | 审批企业认证 | `tenant` |

### 计费 (Billing)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/billing/wallet` | 钱包余额 | `billing` |
| GET | `/api/billing/records` | 计费记录 | `billing` |
| GET | `/api/billing/summary` | 计费摘要 | `billing` |

### 会话中心 (Conversations)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/platform/conversations` | 会话首页 | `conversations` |
| GET | `/api/platform/conversations/stats` | 会话统计 | `conversations` |
| GET | `/api/platform/conversations/groups` | 群聊列表 | `conversations` |
| GET | `/api/platform/conversations/groups/{id}/messages` | 群聊消息 | `conversations` |
| GET | `/api/platform/conversations/history` | 历史消息 | `conversations` |
| POST | `/api/platform/conversations/messages` | 发送消息 | `conversations` |

### 渠道 (Channels)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/platform/channels` | 渠道总览 | `channels` |
| GET | `/api/platform/channels/wechat-work/config` | 企微配置 | `channels` |
| POST | `/api/platform/channels/wechat-work/config` | 更新企微配置 | `channels` |
| GET | `/api/platform/channels/feishu/config` | 飞书配置 | `channels` |
| POST | `/api/platform/channels/feishu/config` | 更新飞书配置 | `channels` |
| GET | `/api/platform/channels/wechat-personal-plugin/config` | 个人微信插件配置 | `channels` |
| POST | `/api/platform/channels/wechat-personal-plugin/config` | 更新个人微信插件配置 | `channels` |
| GET | `/api/platform/channels/wechat-personal-openclaw/config` | OpenClaw 微信配置 | `channels` |
| GET | `/api/platform/channels/bindings` | 绑定列表 | `channels` |
| POST | `/api/platform/channels/bindings/create` | 创建绑定 | `channels` |
| POST | `/api/platform/channels/bindings/disable` | 停用绑定 | `channels` |
| POST | `/api/platform/channels/bindings/regenerate-code` | 重新生成绑定码 | `channels` |
| POST | `/api/platform/channels/wechat-personal-openclaw/qr/start` | 发起 QR 扫码 | `channels` |
| GET | `/api/platform/channels/wechat-personal-openclaw/qr/status` | QR 扫码状态 | `channels` |

### 设备 (Devices)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/platform/devices` | 设备列表 | `devices` |
| GET | `/api/platform/devices/account-state` | 账号状态 | `devices` |
| GET | `/api/platform/devices/online` | 在线状态 | `devices` |
| POST | `/api/platform/devices/bootstrap` | 设备引导 | `devices` |
| POST | `/api/platform/devices/pair-code` | 生成配对码 | `devices` |
| POST | `/api/platform/devices/claim` | 认领设备 | `devices` |
| PUT | `/api/platform/devices/{id}` | 更新设备 | `devices` |
| DELETE | `/api/platform/devices/{id}` | 删除设备 | `devices` |

### 文档 (File)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/documents` | 文档列表 | `file` |
| GET | `/api/documents/{id}` | 文档详情 | `file` |
| GET | `/api/products/{id}/documents` | 产品关联文档 | `file` |

### 工作流 (Workflow)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/workflows` | 工作流列表 | `workflow` |
| POST | `/api/workflows` | 创建/更新工作流 | `workflow` |
| GET | `/api/workflows/{id}` | 工作流详情 | `workflow` |
| POST | `/api/workflows/{id}/run` | 运行工作流 | `workflow` |
| GET | `/api/workflows/executions/{id}/logs` | 执行日志 | `workflow` |

### 审批 (Approval)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/platform/approvals` | 审批列表 | `approval` |
| POST | `/api/platform/approvals/request` | 发起审批 | `approval` |
| GET | `/api/platform/approvals/{id}` | 审批详情 | `approval` |
| POST | `/api/platform/approvals/{id}/resolve` | 处理审批 | `approval` |

### 审计 (Audit)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/platform/audit/events` | 审计事件列表 | `audit` |
| GET | `/api/platform/audit/summary` | 审计汇总 | `audit` |
| POST | `/api/platform/audit/events` | 记录审计事件 | `audit` |

### API Key 管理

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| GET | `/api/users/app-keys` | App Key 列表 | `apikey` |
| POST | `/api/users/app-keys` | 创建 App Key | `apikey` |
| DELETE | `/api/users/app-keys/{id}` | 删除 App Key | `apikey` |
| PATCH | `/api/users/app-keys/{id}` | 启用/停用 | `apikey` |
| PUT | `/api/users/app-keys/{id}/name` | 重命名 | `apikey` |
| POST | `/api/users/app-keys/default/token` | 签发 Token | `apikey` |
| GET | `/api/llm/keys` | LLM Key 列表 | `apikey` |
| POST | `/api/llm/keys` | 创建 LLM Key | `apikey` |
| PUT | `/api/llm/keys/{id}` | 更新 LLM Key | `apikey` |
| DELETE | `/api/llm/keys/{id}` | 删除 LLM Key | `apikey` |

### 策略 (Policy)

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| POST | `/api/platform/policy/tool-access/check` | 工具访问检查 | `policy` |
| POST | `/api/platform/policy/data-access/check` | 数据访问检查 | `policy` |
| POST | `/api/platform/policy/exec-access/check` | 执行权限检查 | `policy` |

### 语音 (Voice) — Stub

| 方法 | 路径 | 说明 | SDK 模块 |
|------|------|------|----------|
| POST | `/api/asr` | 语音识别（返回 501） | `voice` |
| POST | `/api/tts` | 语音合成（返回 501） | `voice` |
| POST | `/api/audio/speech` | 音频生成（返回 501） | `voice` |

### Gateway & 微信（原生通道管理）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/gateway/status` | 网关状态 |
| GET | `/gateway/platforms` | 已配置平台 |
| GET | `/gateway/supported-platforms` | 支持的平台 |
| POST | `/gateway/start` | 启动网关 |
| POST | `/gateway/stop` | 停止网关 |
| POST | `/gateway/configure` | 配置平台凭证 |
| GET | `/wechat/status` | 微信状态 |
| GET | `/wechat/credentials` | 微信凭证 |
| GET | `/wechat/check` | 微信依赖检查 |
| POST | `/wechat/qr-login` | QR 扫码登录 |
| POST | `/wechat/qr-cancel` | 取消 QR 登录 |
| POST | `/wechat/configure` | 微信配置 |
| POST | `/wechat/send` | 发送消息 |
| POST | `/wechat/adapter/start` | 启动适配器 |
| POST | `/wechat/adapter/stop` | 停止适配器 |

## 数据持久化

所有本地数据存储在 `HERMES_HOME`（默认 `~/.qeeclaw_hermes/`）目录下：

| 文件 | 用途 |
|------|------|
| `sessions/` | 会话数据（JSON） |
| `sessions/_profiles.json` | 自定义智体 Profile |
| `memory/entries.json` | 记忆条目 |
| `knowledge/` | LanceDB 本地向量库 |
| `workflows.json` | 工作流定义 |
| `device_info.json` | 设备信息 |
| `approvals.json` | 审批记录 |
| `audit_events.json` | 审计事件 |
| `api_keys.json` | App Key & LLM Key |
| `knowledge_config.json` | 知识库配置 |

## core-sdk 模块覆盖率

| core-sdk 模块 | 端点数 | 状态 |
|---------------|--------|------|
| `agent` | 11 | 已覆盖 |
| `models` | 9 | 已覆盖 |
| `iam` | 5 | 已覆盖 |
| `billing` | 3 | 已覆盖 |
| `tenant` | 4 | 已覆盖 |
| `conversations` | 6 | 已覆盖 |
| `channels` | 14 | 已覆盖 |
| `memory` | 9 | 已覆盖 |
| `knowledge` | 14 | 已覆盖 |
| `devices` | 8 | 已覆盖 |
| `file` | 3 | 已覆盖 |
| `workflow` | 5 | 已覆盖 |
| `approval` | 4 | 已覆盖 |
| `audit` | 3 | 已覆盖 |
| `apikey` | 10 | 已覆盖 |
| `policy` | 3 | 已覆盖 |
| `voice` | 3 | Stub (501) |

**17/17 模块，145+ 端点，167 个测试全部通过。**

## 测试

```bash
cd qeeclaw-sdk/packages/hermes-bridge
python3 -m pytest test_session_agent.py -v
```

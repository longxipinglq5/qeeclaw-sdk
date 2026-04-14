# QeeClaw Hermes Bridge

QeeClaw TypeScript SDK 与 [hermes-agent](https://github.com/NousResearch/hermes-agent) 之间的轻量级 HTTP 桥接服务。

## 快速开始

### 前置要求

- Python 3.11+
- `pip install openai` (最小依赖)

### 启动

```bash
# 设置 hermes-agent 源码路径（默认自动检测 vendor/hermes-agent）
export QEECLAW_HERMES_AGENT_DIR=/path/to/hermes-agent

# 设置 API Key（fallback 模式使用）
export OPENROUTER_API_KEY=your-key-here

# 启动桥接服务
python bridge_server.py
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/invoke` | 非流式模型调用 |
| POST | `/invoke/stream` | 流式模型调用 (SSE) |
| GET | `/gateway/status` | Gateway 状态查询 |

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QEECLAW_HERMES_BRIDGE_HOST` | `127.0.0.1` | 监听地址 |
| `QEECLAW_HERMES_BRIDGE_PORT` | `21747` | 监听端口 |
| `QEECLAW_HERMES_AGENT_DIR` | `../vendor/hermes-agent` | hermes-agent 源码路径 |
| `OPENROUTER_API_KEY` | - | OpenRouter API Key (fallback) |
| `OPENAI_API_KEY` | - | OpenAI API Key (fallback) |

## 架构

```
TypeScript SDK (HermesAdapter)
      │  HTTP
      ▼
bridge_server.py (本文件)
      │  Python import
      ▼
hermes-agent (AIAgent / runtime_provider)
      │
      ▼
LLM Provider (OpenRouter / z.ai / Kimi / ...)
```

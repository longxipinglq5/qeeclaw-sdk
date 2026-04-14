# QeeClaw Gateway 平台配置指南

本文档说明如何配置 hermes-agent 的 Gateway，将 AI Agent 接入各消息平台。

## 架构概览

```
SDK (TypeScript)
  ↓ HTTP
bridge_server.py          ← 阶段 2 实现
  ↓ subprocess
hermes gateway            ← hermes-agent 内置的 Gateway 进程
  ↓ 平台 SDK
[钉钉 / 飞书 / 微信 / Telegram / Discord / ...]
```

## 快速开始

### 1. 通过 SDK 编程方式配置

```typescript
import { HermesAdapter } from "@qeeclaw/core-sdk";

const adapter = new HermesAdapter();
await adapter.start();

// 查看支持的平台
const platforms = await adapter.getSupportedPlatforms();
console.log(platforms);

// 配置钉钉
await adapter.configureGateway({
  platform: "dingtalk",
  credentials: {
    app_key: "your-dingtalk-app-key",
    app_secret: "your-dingtalk-app-secret",
  },
});

// 启动 Gateway
const result = await adapter.startGateway();
console.log(result); // { status: "started", pid: 12345 }
```

### 2. 通过 HTTP API 配置

```bash
# 查看支持的全部平台
curl http://127.0.0.1:21747/gateway/supported-platforms

# 配置飞书
curl -X POST http://127.0.0.1:21747/gateway/configure \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "feishu",
    "credentials": {
      "app_id": "cli_xxxx",
      "app_secret": "xxxx"
    }
  }'

# 启动 Gateway
curl -X POST http://127.0.0.1:21747/gateway/start

# 查看 Gateway 状态
curl http://127.0.0.1:21747/gateway/status

# 停止 Gateway
curl -X POST http://127.0.0.1:21747/gateway/stop
```

---

## 各平台配置详情

### 🎯 钉钉 (DingTalk)

**所需凭证：**
| 参数 | 环境变量 | 说明 |
|------|---------|------|
| `app_key` | `DINGTALK_APP_KEY` | 钉钉开放平台 App Key |
| `app_secret` | `DINGTALK_APP_SECRET` | 钉钉开放平台 App Secret |

**获取步骤：**
1. 登录 [钉钉开放平台](https://open.dingtalk.com/)
2. 创建企业内部应用 / 小程序
3. 在 "应用凭证" 页面获取 AppKey 和 AppSecret
4. 配置消息回调 URL

---

### 🐦 飞书 (Feishu / Lark)

**所需凭证：**
| 参数 | 环境变量 | 说明 |
|------|---------|------|
| `app_id` | `FEISHU_APP_ID` | 飞书开放平台 App ID |
| `app_secret` | `FEISHU_APP_SECRET` | 飞书开放平台 App Secret |

**获取步骤：**
1. 登录 [飞书开发者后台](https://open.feishu.cn/)
2. 创建自建应用
3. 在 "凭证与基础信息" 获取 App ID 和 App Secret
4. 在 "事件与回调" 配置消息事件

---

### 💬 微信公众号 (WeChat Official Account)

**所需凭证：**
| 参数 | 环境变量 | 说明 |
|------|---------|------|
| `token` | `WEIXIN_TOKEN` | 公众号验证 Token |
| `account_id` | `WEIXIN_ACCOUNT_ID` | 公众号原始 ID (gh_xxx) |
| `app_id` | `WEIXIN_APP_ID` | 公众号 AppID |
| `app_secret` | `WEIXIN_APP_SECRET` | 公众号 AppSecret |

**获取步骤：**
1. 登录 [微信公众平台](https://mp.weixin.qq.com/)
2. 在 "开发 > 基本配置" 获取以上凭证
3. 配置服务器 URL

---

### 🏢 企业微信 (WeCom)

**所需凭证：**
| 参数 | 环境变量 | 说明 |
|------|---------|------|
| `bot_id` | `WECOM_BOT_ID` | 企业微信机器人 ID |
| `bot_secret` | `WECOM_BOT_SECRET` | 企业微信机器人 Secret |

---

### 📱 Telegram

**所需凭证：**
| 参数 | 环境变量 | 说明 |
|------|---------|------|
| `token` | `TELEGRAM_BOT_TOKEN` | Telegram Bot Token（通过 @BotFather 获取） |

---

### 🎮 Discord

**所需凭证：**
| 参数 | 环境变量 | 说明 |
|------|---------|------|
| `token` | `DISCORD_BOT_TOKEN` | Discord Bot Token |

---

### 💼 Slack

**所需凭证：**
| 参数 | 环境变量 | 说明 |
|------|---------|------|
| `token` | `SLACK_BOT_TOKEN` | Slack Bot OAuth Token |
| `app_token` | `SLACK_APP_TOKEN` | Slack App-Level Token |

---

## API 端点参考

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/gateway/supported-platforms` | 返回支持的全部 16 个平台 |
| `GET` | `/gateway/platforms` | 返回已配置凭证的平台列表 |
| `GET` | `/gateway/status` | Gateway 运行状态、PID、平台连接详情 |
| `POST` | `/gateway/start` | 启动 hermes Gateway 进程 |
| `POST` | `/gateway/stop` | 停止 hermes Gateway 进程 |
| `POST` | `/gateway/configure` | 写入平台凭证到 hermes 配置 |

# QeeClaw SDK 客户交付资料清单

最后更新：2026-04-16

---

## 1. 文档目标

本文档用于回答一个核心问题：

> 我们把 QeeClaw SDK 交付给客户，让他们在上面做产品开发，需要提供哪些资料？

以下按「客户类型 → 交付内容 → 交付顺序 → 一键打包 → 注意事项」的结构组织。

---

## 2. 客户分型与交付矩阵

| 客户类型 | 典型场景 | 推荐交付层级 |
| --- | --- | --- |
| **Web / SaaS 客户** | 在浏览器中集成 AI 能力，如销售驾驶舱 Web 版 | **标准包** |
| **桌面 App 客户** | Electron / Tauri 等桌面应用，需本地数据 + 云端推理 | **桌面包** |
| **私有化 / 边缘部署客户** | 政企客户，数据不出局域网 | **桌面包 + 服务端独立部署包** |
| **移动端客户** | React Native / iOS / Android 原生 | **标准包**（直接对接 REST API） |
| **硬件 / IoT 客户** | 会议终端、边缘 AI 设备 | 单独评估，参考 firmware 层 |

---

## 3. 交付资料总览

### 3.1 标准交付包（所有客户必给）

```
├── 00_发包说明/
│   └── QeeClaw_客户发包说明.md          # 内部人员先读，说明发什么、不发什么
├── 01_客户必读/
│   ├── 01_QeeClaw_客户文档目录.md       # 文档导读
│   ├── 02_QeeClaw_客户接入手册.md       # 统一接入手册（必读）
│   └── 03_QeeClaw_AI_PaaS平台交付手册.md # 仅私有化客户需要
├── 02_API调试资产/
│   ├── openapi/
│   │   └── QeeClaw_Cloud_Public_API.openapi.yaml     # OpenAPI 3.0 规范
│   └── postman/
│       ├── QeeClaw_Cloud_Public_API.postman_collection.json   # Postman 集合
│       └── QeeClaw_Cloud_Public_API.postman_environment.json  # Postman 环境
└── 03_SDK集成包/
    ├── README.md
    ├── core-sdk/                        # @qeeclaw/core-sdk 快照
    │   ├── package.json
    │   ├── README.md
    │   ├── LICENSE
    │   ├── dist/                        # 编译产物
    │   ├── docs/                        # 模块说明
    │   └── examples/                    # 用法示例
    └── product-sdk/                     # @qeeclaw/product-sdk 快照
        ├── package.json
        ├── README.md
        ├── LICENSE
        ├── dist/
        └── examples/
```

### 3.2 桌面 / 私有化附加包（按需提供）

```
└── 04_桌面部署_按需提供/
    ├── README.md
    ├── deploy/
    │   ├── env/
    │   │   ├── sdk-client.env.example
    │   │   ├── runtime-sidecar.env.example
    │   │   ├── gateway-server.env.example
    │   │   └── macos-release.env.example
    │   ├── compose/
    │   │   └── qeeclaw-gateway.compose.example.yml
    │   └── nginx/
    │       └── qeeclaw-gateway.conf.example
    └── runtime-sidecar/                 # @qeeclaw/runtime-sidecar 快照
        ├── package.json
        ├── README.md
        ├── LICENSE
        └── dist/
```

### 3.3 服务端独立运行包（私有化 / 离线场景按需提供）

如客户需要本地/私有化部署 QeeClaw Server（Hermes Agent 后端），额外提供：

```
└── 05_服务端独立部署包/
    └── qeeclaw-server-{version}-{platform}-standalone.tar.gz
        ├── python/                      # 内嵌 Python 运行时（无需客户安装 Python）
        ├── vendor/hermes-agent/         # AI Agent 推理引擎
        ├── vendor/hermes-hudui/         # HUD 可视化仪表盘
        ├── venv/                        # Python 虚拟环境（预装依赖）
        ├── bridge_server.py             # HTTP Bridge 服务
        ├── start.sh                     # 一键启动
        ├── stop.sh                      # 一键停止
        └── install-service.sh           # 注册为 systemd 服务（Linux）
```

生成命令：

```bash
bash scripts/build-server.sh --standalone --target darwin-arm64
# 可选 target: darwin-arm64, darwin-x86_64, linux-arm64, linux-x86_64
```

---

## 4. 各资料详细说明

### 4.1 文档类

| 文档 | 目标读者 | 核心内容 |
| --- | --- | --- |
| **客户文档目录** | 所有人 | 告诉客户先看什么、后看什么、哪些不用看 |
| **客户接入手册** | 客户研发、实施方 | 统一口径（Base URL / API Key / runtimeType）、公开 API 清单、Web/桌面/移动端接入方式、联调参数模板、推荐联调顺序 |
| **AI PaaS 平台交付手册** | 交付工程师、私有化客户 | 交付边界、架构图、不同部署形态的推荐组合、标准交付 6 步流程 |
| **发包说明** | 内部团队 | 发之前先读，明确哪些发、哪些不发 |

### 4.2 API 调试资产

| 资产 | 说明 |
| --- | --- |
| **OpenAPI YAML** | 15 个公开端点，覆盖 3 个域：Workspace Context、Models、Billing |
| **Postman Collection** | 导入即可联调，按域分组 |
| **Postman Environment** | 预置 `base_url` 和 `api_key` 变量，客户填值即用 |

> **本地模式补充**：对于使用本地 Hermes Bridge Server（`http://127.0.0.1:21747`）的客户，全部 17 个 core-sdk 模块的 145+ 个端点均可用，不限于上述 3 个域。本地模式的完整 API 参考请见 `QeeClaw_Bridge_Server_API参考手册.md`。

客户公开 API 清单：

| 域 | 端点 |
| --- | --- |
| Context | `GET /api/users/me/context` |
| Models | `GET /api/platform/models` |
| Models | `GET /api/platform/models/providers` |
| Models | `GET /api/platform/models/runtimes` |
| Models | `GET /api/platform/models/route` |
| Models | `GET /api/platform/models/resolve` |
| Models | `POST /api/platform/models/invoke` |
| Models | `POST /api/llm/images/generations` |
| Models | `GET /api/platform/models/usage` |
| Models | `GET /api/platform/models/cost` |
| Models | `GET /api/platform/models/quota` |
| Billing | `GET /api/billing/wallet` |
| Billing | `GET /api/billing/records` |
| Billing | `GET /api/billing/summary` |

### 4.3 SDK 集成包

#### @qeeclaw/core-sdk（v0.1.0 · Stable）

平台标准 API 访问层。17 个模块：

| 模块 | 说明 | Bridge 本地覆盖 |
| --- | --- | --- |
| `billing` | 钱包 / 账单 / 摘要 | ✅ 已覆盖（3 端点） |
| `models` | 模型列表 / 路由 / 推理调用 / 图片生成 / 配额 | ✅ 已覆盖（10 端点） |
| `iam` | 用户身份 | ✅ 已覆盖（5 端点） |
| `apikey` | API Key 管理 | ✅ 已覆盖（10 端点） |
| `tenant` | 工作空间 / 上下文 | ✅ 已覆盖（4 端点） |
| `agent` | 智能体定义 | ✅ 已覆盖（11 端点） |
| `knowledge` | 知识库 | ✅ 已覆盖（8 端点） |
| `memory` | 记忆工作台 | ✅ 已覆盖（5 端点） |
| `conversations` | 会话管理 | ✅ 已覆盖（6 端点） |
| `channels` | 渠道管理 | ✅ 已覆盖（14 端点） |
| `devices` | 设备管理 | ✅ 已覆盖（8 端点） |
| `workflow` | 工作流 | ✅ 已覆盖（5 端点） |
| `file` | 文件上传 / 下载 | ✅ 已覆盖（3 端点） |
| `voice` | 语音能力 | ⬜ Stub（3 端点，返回 501） |
| `audit` | 审计日志 | ✅ 已覆盖（3 端点） |
| `policy` | 策略管理 | ✅ 已覆盖（3 端点） |
| `approval` | 审批流 | ✅ 已覆盖（4 端点） |

> **Bridge Server 本地覆盖率：17/17 模块，145+ 端点，167 个测试全部通过。** 本地 Hermes Bridge Server 已实现 core-sdk 全部模块的 HTTP 端点，客户无需依赖云端即可使用完整 SDK 能力。

快速初始化：

```ts
import { createQeeClawClient } from "@qeeclaw/core-sdk";

const client = createQeeClawClient({
  baseUrl: "https://paas.qeeshu.com",   // 云端
  // baseUrl: "http://127.0.0.1:21747", // 本地 Hermes Server
  token: "sk-your-api-key",
});

// 验证连通性
const context = await client.tenant.getCurrentContext();
const models = await client.models.listAvailable();
const wallet = await client.billing.getWallet();
```

#### @qeeclaw/product-sdk（v0.1.0 · Beta）

场景/产品装配层，在 core-sdk 之上提供更高级的业务装配入口。8 个 kit：

| Kit | 说明 |
| --- | --- |
| `channelCenter` | 渠道中心首页装配 |
| `conversationCenter` | 会话中心首页装配 |
| `deviceCenter` | 设备中心总览装配 |
| `knowledgeCenter` | 知识中心首页装配 |
| `governanceCenter` | 治理中心首页装配 |
| `salesCockpit` | 销售超级驾驶舱首页 + 商机看板装配 |
| `salesKnowledge` | 销售知识助手上下文装配 |
| `salesCoaching` | 销售培训 / 复盘装配 |

快速初始化：

```ts
import { createQeeClawClient } from "@qeeclaw/core-sdk";
import { createQeeClawProductSDK } from "@qeeclaw/product-sdk";

const core = createQeeClawClient({
  baseUrl: "https://paas.qeeshu.com",
  token: "sk-your-api-key",
});

const product = createQeeClawProductSDK(core);

// 加载销售驾驶舱首页数据
const context = await core.tenant.getCurrentContext();
const teamId = Number(context.defaultTeamId ?? context.teams[0]?.id);
const home = await product.salesCockpit.loadHome(teamId, { runtimeType: "hermes" });
```

#### @qeeclaw/runtime-sidecar（v0.1.0 · Experimental · 桌面/私有化客户按需）

本地运行时适配层，提供：

- CLI 启动 / 停止本地 Gateway
- 本地知识库同步 Worker
- 本地记忆工作台 Worker
- 离线状态管理

### 4.4 部署模板（桌面/私有化按需）

| 模板 | 用途 |
| --- | --- |
| `sdk-client.env.example` | 客户端 SDK 环境变量 |
| `runtime-sidecar.env.example` | Sidecar 环境变量 |
| `gateway-server.env.example` | Gateway 服务环境变量 |
| `macos-release.env.example` | macOS 桌面发布环境变量 |
| `qeeclaw-gateway.compose.example.yml` | Gateway 最小容器化部署 |
| `qeeclaw-gateway.conf.example` | Nginx HTTPS/WSS 反向代理 |

### 4.5 示例工程

仓库内提供两个参考工程，可按需一并交付：

| 示例 | 说明 |
| --- | --- |
| `sales-cockpit-starter-web` | 销售驾驶舱 Web 起步工程，适合客户前端团队作为页面装配参考 |
| `sales-cockpit-web-verifier` | SDK 连通性逐项验证页，适合联调阶段快速检查 |

---

## 5. 客户需要我们提供的项目专属信息

除了上述通用资料外，还需要为每个客户项目准备以下专属信息：

| 项目 | 说明 | 示例 |
| --- | --- | --- |
| **Base URL** | 云端或私有化服务地址 | `https://paas.qeeshu.com` 或 `http://127.0.0.1:21747` |
| **API Key** | 客户凭证 | `sk-xxxxxxxx` |
| **测试账号** | 登录凭据 + 权限范围 | — |
| **可用模型** | 默认推荐模型 | `gpt-4.1-mini` |
| **可用模块范围** | 客户被授权使用的功能模块 | billing + models + context |
| **runtimeType** | 运行时类型（通常内部自动处理，客户不需要手动填写） | `hermes` |

---

## 6. 推荐客户阅读顺序

```
第 1 步：01_客户文档目录.md          → 了解文档全貌
第 2 步：02_客户接入手册.md          → 了解统一口径、公开 API、初始化方式
第 3 步：导入 Postman 集合           → 逐个调通 API
第 4 步：查看 core-sdk README        → 安装 SDK、跑通第一个调用
第 5 步：查看 product-sdk README     → 按场景装配页面
第 6 步：参考 sales-cockpit-starter  → 对照示例工程搭建自己的项目
第 7 步：（如需）查看平台交付手册     → 了解私有化 / 桌面部署架构
```

---

## 7. 推荐联调顺序

客户拿到资料后，建议按以下顺序依次打通：

```
1. GET  /api/users/me/context          → 验证 API Key + 获取工作空间
2. GET  /api/platform/models           → 确认可用模型列表
3. GET  /api/platform/models/route     → 确认模型路由规则
4. POST /api/platform/models/invoke    → 跑通第一次模型推理
5. POST /api/llm/images/generations    → 跑通 gpt-image-2 图片生成
6. GET  /api/platform/models/quota     → 确认配额
7. GET  /api/billing/wallet            → 确认计费账户
```

---

## 8. 一键生成客户发包目录

已提供自动化脚本，可一键生成上述结构：

```bash
# 标准包（Web / 前端 / 轻量集成）
bash scripts/build-qeeclaw-customer-package.sh standard

# 桌面包（附带 sidecar + deploy 模板）
bash scripts/build-qeeclaw-customer-package.sh desktop

# 指定输出路径
bash scripts/build-qeeclaw-customer-package.sh standard /tmp/QeeClaw_客户发包_ProjectName
```

脚本会自动：
- 组织 00-04 的目录结构
- 拷贝最新文档
- 拷贝 OpenAPI / Postman 资产
- 拷贝 SDK 包快照（package.json + dist + README + LICENSE + examples）
- 生成 README 和发包说明
- 自动 zip 压缩

---

## 9. 明确不给客户的资料

以下内容 **不建议** 作为默认交付内容：

- [ ] 全量 Platform API v1 内部域化接口
- [ ] 内部控制面接口文档
- [ ] 平台后端源码
- [ ] 数据库 Schema / 迁移脚本
- [ ] 运维监控配置
- [ ] 模型密钥 / Provider 凭证
- [ ] 整个仓库源码

---

## 10. 交付检查清单

发给客户前，逐项确认：

- [ ] 文档内的 `Base URL` 已替换为客户实际地址
- [ ] API Key 已生成并发放
- [ ] 测试账号已开通、权限已配置
- [ ] SDK dist 已 build 完成（`pnpm build`）
- [ ] Postman Environment 中的变量值已更新
- [ ] OpenAPI YAML 版本与当前后端一致
- [ ] 如果是桌面包，deploy 模板中的环境变量示例已审查
- [ ] 如果附带服务端独立包，已在目标平台测试过一键启动

---

## 11. 典型交付场景速查

### 场景 A：客户做销售驾驶舱 Web 版

```
交付内容：标准包
    ├── 客户接入手册
    ├── OpenAPI + Postman
    ├── core-sdk + product-sdk
    └── sales-cockpit-starter-web 示例
随附信息：Base URL + API Key + 测试账号 + 推荐模型
```

### 场景 B：客户做桌面 App（本地数据 + 云端推理）

```
交付内容：桌面包
    ├── 客户接入手册 + 平台交付手册
    ├── OpenAPI + Postman
    ├── core-sdk + product-sdk + runtime-sidecar
    ├── deploy 模板（env / compose / nginx）
    └── 服务端独立运行包（按需）
随附信息：Base URL + API Key + 本地 runtimeType=hermes
```

### 场景 C：政企私有化全部署

```
交付内容：桌面包 + 服务端独立运行包 + 平台控制面
    ├── 全部文档
    ├── 全部 SDK + Sidecar
    ├── deploy 模板
    ├── qeeclaw-server standalone 包
    └── 平台控制面部署（另行交付）
随附信息：私有部署地址 + 本地密钥 + 数据库/存储规划
```

---

## 12. 附录：SDK 架构层次图

```
┌─────────────────────────────────────────────────────────┐
│                     业务应用层                            │
│  销售驾驶舱 · Web控制台 · 桌面App · 移动端 · IoT设备     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│              QeeClaw Open Access Layer                   │
│                                                         │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐ │
│  │  core-sdk     │  │  product-sdk  │  │  runtime-    │ │
│  │  (17 modules) │  │  (8 kits)     │  │  sidecar     │ │
│  │  API 访问层    │  │  场景装配层    │  │  本地运行时   │ │
│  └───────┬───────┘  └───────┬───────┘  └──────┬──────┘ │
└──────────┼──────────────────┼─────────────────┼────────┘
           │                  │                 │
┌──────────┴──────────────────┴─────────────────┴────────┐
│              QeeClaw AI PaaS Platform                   │
│                                                         │
│  Control Plane · Models · Billing · IAM · Knowledge     │
│  Gateway · Edge Relay · DB · Redis · Vector DB          │
└─────────────────────────────────────────────────────────┘
```

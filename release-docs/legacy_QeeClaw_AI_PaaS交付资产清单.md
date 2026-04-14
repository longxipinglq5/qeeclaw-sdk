# QeeClaw AI PaaS 交付资产清单

最后更新：2026-03-22

## 1. 文档说明

本文档用于盘点当前 `sdk/` 中已经形成的可交付资产，方便：

- 对外开源
- 对内项目交付
- 私有化方案打包
- 销售超级驾驶舱样板场景对接

## 2. 开放层包资产

| 路径 | 类型 | 用途 |
| --- | --- | --- |
| `sdk/qeeclaw-core-sdk` | npm package | 平台标准 API 访问层 |
| `sdk/qeeclaw-product-sdk` | npm package | 场景 / 产品装配层 |
| `sdk/qeeclaw-runtime-sidecar` | npm package | 本地运行时适配层 |
| `sdk/meeting_device_firmware` | hardware sample | 硬件接入样例层 |

## 3. 对外说明文档

| 路径 | 用途 |
| --- | --- |
| `sdk/docs/README.md` | 客户交付文档首页 / 阅读导航 |
| `sdk/docs/QeeClaw_SDK通用说明.md` | 平台与 SDK 关系总说明 |
| `sdk/docs/QeeClaw_客户接入手册.md` | 第三方客户 / 实施团队主对接文档 |
| `sdk/docs/archive/QeeClaw_Platform_API_v1_域化接口说明_20260321.md` | Platform API 接口索引与内部附录 |
| `sdk/docs/QeeClaw_SDK_Web对接文档.md` | Web 接入说明 |
| `sdk/docs/QeeClaw_SDK_桌面App对接文档.md` | 桌面 App 接入说明 |
| `sdk/docs/QeeClaw_SDK_移动端App对接文档.md` | 移动端 App 接入说明 |
| `sdk/docs/QeeClaw_AI_PaaS平台交付手册.md` | 平台交付总手册 |
| `sdk/docs/QeeClaw_AI_PaaS私有化部署说明.md` | 私有化部署说明 |
| `sdk/docs/QeeClaw_AI_PaaS安装升级与迁移说明.md` | 安装、升级、迁移说明 |
| `sdk/docs/QeeClaw_AI_PaaS环境变量模板说明.md` | 环境变量模板说明 |
| `sdk/docs/QeeClaw_AI_PaaS交付资产清单.md` | 当前资产盘点 |
| `sdk/docs/QeeClaw_SDK开源发布说明.md` | 开源发布策略说明 |
| `sdk/docs/QeeClaw_SDK开源发布检查清单.md` | 发布检查清单 |
| `sdk/docs/QeeClaw_SDK公开仓库初始化与发布命令.md` | 公开仓初始化与发布命令 |

## 4. 交付模板资产

| 路径 | 类型 | 用途 |
| --- | --- | --- |
| `sdk/deploy/README.md` | doc | 交付模板目录说明 |
| `sdk/deploy/env/sdk-client.env.example` | env template | Core / Product SDK 客户端示例变量 |
| `sdk/deploy/env/runtime-sidecar.env.example` | env template | Sidecar 本地运行时变量 |
| `sdk/deploy/env/gateway-server.env.example` | env template | Gateway 容器部署变量 |
| `sdk/deploy/env/macos-release.env.example` | env template | macOS 打包与公证变量 |
| `sdk/deploy/compose/qeeclaw-gateway.compose.example.yml` | compose template | Gateway 容器化样例 |
| `sdk/deploy/nginx/qeeclaw-gateway.conf.example` | nginx template | HTTPS / WSS 反向代理样例 |

## 5. 交付脚本资产

| 路径 | 用途 |
| --- | --- |
| `scripts/build-qeeclaw-sdk-stack.sh` | 构建三层 SDK |
| `scripts/dev-qeeclaw-sdk-stack.sh` | 一键开发入口 |
| `scripts/verify-qeeclaw-sdk-stack.sh` | 联合校验入口 |
| `scripts/qeeclaw-sidecar.sh` | Sidecar 状态、自检、同步、启停 |
| `scripts/run-qeeclaw-sidecar-healthcheck.sh` | Sidecar 健康检查 |
| `scripts/release-qeeclaw-sdk.sh` | SDK 发布前检查、pack、demo |
| `scripts/export-qeeclaw-public-sdk.sh` | 导出公开仓 |

以下脚本仅存在于主平台 monorepo，不随公开 SDK 仓导出：

| 路径 | 用途 |
| --- | --- |
| `scripts/package-openclaw.sh` | macOS App 打包 |
| `scripts/upgrade-openclaw.sh` | OpenClaw 宿主升级 |

## 6. 样板场景资产

当前第一样板场景为：

- 销售超级驾驶舱

对应资产包括：

- `sdk/qeeclaw-product-sdk/src/kits/sales-cockpit.ts`
- `sdk/qeeclaw-product-sdk/src/kits/sales-knowledge.ts`
- `sdk/qeeclaw-product-sdk/src/kits/sales-coaching.ts`
- `sdk/qeeclaw-product-sdk/examples/mock-dashboard.mjs`

## 7. 当前交付边界

已经具备：

- 开放接入层包
- 样板场景装配层
- 本地运行时适配层
- 交付文档
- 边缘部署模板
- 公开仓导出能力

仍不在本目录内直接承载：

- 完整控制面后端部署实现
- 私有化数据库与存储初始化脚本
- 完整租户 / IAM 运维平台
- 真实生产密钥与运维监控接入

## 8. 结论

截至 2026-03-22，`sdk/` 已经不只是“几个可安装包”，而是形成了：

- 平台开放接入层
- 第一样板场景层
- 第一轮交付模板层

这意味着它已经具备了第一版开源发布与项目交付的基础，但完整 AI PaaS 私有化控制面仍需要主平台仓共同交付。

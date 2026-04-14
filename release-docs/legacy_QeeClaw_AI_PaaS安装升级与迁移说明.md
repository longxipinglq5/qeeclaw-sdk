# QeeClaw AI PaaS 安装升级与迁移说明

最后更新：2026-03-22

## 1. 文档目标

本文档说明三类事情：

1. 如何安装和联调 QeeClaw SDK
2. 如何做版本升级与发布检查
3. 如何从旧的本地 gateway / relay 方案迁移到新的 Runtime Sidecar 方案

## 2. 安装方式

### 2.1 业务应用直接安装公开包

适用于：

- Web 应用
- Node 服务
- 桌面端前端层

安装命令：

```bash
pnpm add @qeeclaw/core-sdk @qeeclaw/product-sdk
```

如果只需要平台 API 访问层：

```bash
pnpm add @qeeclaw/core-sdk
```

### 2.2 本地仓开发模式

适用于：

- SDK 开发者
- 私有化交付联调
- 样板场景演示验证

推荐顺序：

```bash
pnpm --dir sdk/qeeclaw-core-sdk check
pnpm --dir sdk/qeeclaw-core-sdk build
pnpm --dir sdk/qeeclaw-product-sdk check
pnpm --dir sdk/qeeclaw-product-sdk build
```

如果希望跑最小 mock 联调：

```bash
node sdk/qeeclaw-core-sdk/examples/mock-platform-server.mjs
node sdk/qeeclaw-core-sdk/examples/mock-client.mjs
node sdk/qeeclaw-product-sdk/examples/mock-dashboard.mjs
```

### 2.3 本地运行时安装

适用于：

- 桌面 App
- 本地知识节点
- 本地审批缓存与 gateway 托管

推荐检查命令：

```bash
bash scripts/qeeclaw-sidecar.sh status
bash scripts/qeeclaw-sidecar.sh selfcheck
bash scripts/run-qeeclaw-sidecar-healthcheck.sh
```

## 3. 升级流程

### 3.1 SDK 包升级

建议每次升级前后都执行：

```bash
bash scripts/release-qeeclaw-sdk.sh check core product runtime
bash scripts/release-qeeclaw-sdk.sh pack core product runtime
bash scripts/release-qeeclaw-sdk.sh demo
```

说明：

- `core-sdk` 目前按相对稳定接口维护
- `product-sdk` 当前仍建议按 `beta` 节奏发布
- `runtime-sidecar` 当前仍建议按 `next / experimental` 节奏发布

### 3.2 OpenClaw / 桌面运行时升级

如果你是在主平台 monorepo 内维护 OpenClaw 桌面宿主，可以使用：

```bash
bash scripts/upgrade-openclaw.sh <version>
```

升级后建议立刻执行：

```bash
source sdk/deploy/env/macos-release.env.example && ./scripts/package-openclaw.sh
```

需要注意：

- `scripts/upgrade-openclaw.sh` 与 `scripts/package-openclaw.sh` 只存在于主平台 monorepo
- 导出的 SDK 公开仓默认不包含这两个脚本，也不包含 `vendor/openclaw`
- 如果只是使用公开 SDK 包，不需要执行这一段桌面宿主打包流程

如果需要正式签名，请把模板文件复制为本地私有配置后再执行，不要直接提交真实证书信息。

### 3.3 公开仓导出与发布升级

导出公开仓：

```bash
bash scripts/export-qeeclaw-public-sdk.sh /tmp/qeeclaw-sdk-public
```

然后在导出目录执行：

```bash
pnpm install
pnpm run release:check
```

## 4. 迁移说明

### 4.1 从自定义本地 Gateway 迁移到 Runtime Sidecar

推荐顺序：

1. Sidecar 接管认证态读取
2. Sidecar 接管 `installationId`
3. Sidecar 接管设备 bootstrap
4. Sidecar 接管 gateway 进程启停
5. 本地 memory / policy / approval 入口统一改走 Sidecar

详细迁移文档：

- `sdk/qeeclaw-runtime-sidecar/docs/MIGRATION_FROM_CUSTOM_GATEWAY.md`

### 4.2 从“通用工作台”迁移到“销售超级驾驶舱”

如果已有旧的聚合页逻辑，建议按以下顺序迁移：

1. 保留现有 `channelCenter / governanceCenter / knowledgeCenter`
2. 新增 `salesCockpit` 作为首页主装配层
3. 新增 `salesKnowledge` 承接销售问答上下文
4. 新增 `salesCoaching` 承接培训与复盘
5. 再根据真实业务逐步替换旧的临时拼装逻辑

## 5. 回滚建议

- SDK 包升级前先跑 `pack` 干跑
- Gateway 升级前先备份旧镜像
- Sidecar 迁移前先备份本地状态目录
- 如果新版本存在兼容问题，优先回滚到上一个已通过 `release:check` 的版本

## 6. 关联文档

- `sdk/docs/QeeClaw_SDK公开仓库初始化与发布命令.md`
- `sdk/docs/QeeClaw_AI_PaaS平台交付手册.md`
- `sdk/docs/QeeClaw_AI_PaaS私有化部署说明.md`
- `sdk/docs/QeeClaw_AI_PaaS环境变量模板说明.md`

# QeeClaw Runtime Sidecar

`@qeeclaw/runtime-sidecar` 是 QeeClaw SDK 体系中的本地运行时组件。

> Status: Experimental

它适合桌面端、本地节点和边缘设备场景，用来统一管理：

- 本地认证态
- 设备自举同步
- 本地知识目录
- 本地记忆访问
- 本地策略检查
- 本地审批缓存
- 本地 gateway / relay 进程

## 当前能力

### 1. Gateway Adapter

- 通过可配置的 `gatewayCommand` / `gatewayArgs` 启动本地 gateway 进程
- 使用 PID 文件维护 gateway 状态
- 兼容通过 `QEECLAW_GATEWAY_ENTRY` 或 `QEECLAW_BRIDGE_ENTRY` 传入的单文件脚本入口

### 2. Local Memory Worker

- 使用本地认证态中的 `deviceKey / userToken`
- 直连平台的 `/memory/*` 接口
- 支持 `store / search / delete / stats`

### 3. Local Knowledge Worker

- 本地维护知识目录配置
- 支持目录扫描、清单缓存、最近同步时间记录

### 4. Local Security Agent

- 在本地做第一层风险判断
- 对危险命令、高风险工具、敏感数据操作给出阻断或审批建议

### 5. Approval Agent

- 调用 Control Plane 的审批接口
- 将待处理审批缓存在本地
- 支持 Sidecar 本地查询待审批记录

### 6. Sync Service

- 读取本地认证态文件
- 自动补齐 `installationId`
- 在仅有 `userToken` 时，可自动调用 `/api/platform/devices/bootstrap`
- 将获取到的 `deviceKey / deviceId / authMode` 回写到本地认证态

## 启动方式

```bash
node ./dist/cli.js run
```

开发时建议：

```bash
pnpm install
pnpm run check
```

## CLI

```bash
qeeclaw-sidecar run
qeeclaw-sidecar sync
qeeclaw-sidecar status
qeeclaw-sidecar selfcheck
qeeclaw-sidecar gateway:start
qeeclaw-sidecar gateway:stop
```

## 本地 HTTP API

默认监听：`http://127.0.0.1:21736`

所有请求都需要携带：

```http
Authorization: Bearer <sidecar-token>
```

其中：

- 推荐通过 `QEECLAW_SIDECAR_AUTH_TOKEN` 显式配置固定 token
- 如果未显式配置，Sidecar 会在本地状态文件中自动生成并持久化一个 token
- 默认仅允许绑定到 loopback 地址；如需监听非本机地址，必须显式设置 `QEECLAW_SIDECAR_ALLOW_REMOTE=true`

已提供接口：

- `GET /health`
- `GET /state`
- `POST /sync`
- `GET /gateway/status`
- `POST /gateway/start`
- `POST /gateway/stop`
- `POST /memory/store`
- `POST /memory/search`
- `DELETE /memory/{entryId}`
- `GET /memory/stats`
- `GET /knowledge/config`
- `POST /knowledge/config`
- `POST /knowledge/sync`
- `GET /knowledge/inventory`
- `POST /policy/tool-access/check`
- `POST /policy/data-access/check`
- `POST /policy/exec-access/check`
- `POST /approvals/request`
- `GET /approvals`
- `GET /approvals/pending-local`

## 公开配置项

- `QEECLAW_CONTROL_PLANE_URL`
- `QEECLAW_SIDECAR_HOST`
- `QEECLAW_SIDECAR_PORT`
- `QEECLAW_SIDECAR_AUTH_TOKEN`
- `QEECLAW_SIDECAR_ALLOW_REMOTE`
- `QEECLAW_SIDECAR_START_GATEWAY`
- `QEECLAW_SIDECAR_AUTO_BOOTSTRAP`
- `QEECLAW_STATE_DIR`
- `QEECLAW_AUTH_STATE_FILE`
- `QEECLAW_SIDECAR_STATE_DIR`
- `QEECLAW_GATEWAY_COMMAND`
- `QEECLAW_GATEWAY_ARGS`
- `QEECLAW_GATEWAY_WORKDIR`
- `QEECLAW_GATEWAY_WS_URL`
- `QEECLAW_DEVICE_NAME`
- `QEECLAW_HOSTNAME`
- `QEECLAW_OS_INFO`

兼容旧环境时，仍支持：

- `QEECLAW_OPENCLAW_STATE_DIR`
- `QEECLAW_BRIDGE_ENTRY`
- `OPENCLAW_WS_URL`

## 默认行为说明

- `QEECLAW_CONTROL_PLANE_URL` 未设置时，默认使用 `http://localhost:3456`
- `QEECLAW_SIDECAR_HOST` 默认使用 `127.0.0.1`
- `QEECLAW_SIDECAR_ALLOW_REMOTE` 默认关闭
- `QEECLAW_SIDECAR_START_GATEWAY` 默认关闭
- 状态目录优先使用 `~/.qeeclaw`，若存在旧目录则自动兼容 `~/.openclaw`
- 认证态文件优先使用 `auth-state.json`，若存在旧文件则自动兼容 `nexus-auth.json`
- 如果未显式提供 `QEECLAW_SIDECAR_AUTH_TOKEN`，会自动生成一个本地 API token

## 最小示例

```ts
import { createRuntimeSidecar } from "@qeeclaw/runtime-sidecar";

const sidecar = createRuntimeSidecar({
  controlPlaneBaseUrl: "https://your-qeeclaw-host",
  localGatewayWsUrl: "ws://127.0.0.1:18789",
  sidecarHost: "127.0.0.1",
  sidecarPort: 21736,
  sidecarAuthToken: process.env.QEECLAW_SIDECAR_AUTH_TOKEN,
  startGatewayOnBoot: false,
  autoBootstrapDevice: true,
  stateRootDir: "/Users/demo/.qeeclaw",
  stateFilePath: "/Users/demo/.qeeclaw/auth-state.json",
  gatewayCommand: "node",
  gatewayArgs: ["/path/to/local-gateway.js"],
  gatewayWorkingDir: "/path/to",
  gatewayPidFilePath: "/Users/demo/.qeeclaw/sidecar/gateway-adapter.json",
  knowledgeConfigFilePath: "/Users/demo/.qeeclaw/sidecar/knowledge-worker.json",
  approvalsCacheFilePath: "/Users/demo/.qeeclaw/sidecar/approval-agent.json",
  deviceName: "QeeClaw Desktop",
  hostname: "demo-mac",
  osInfo: "macOS 15.3",
});

await sidecar.start();
const sidecarToken = await sidecar.getLocalApiToken();

const health = await fetch("http://127.0.0.1:21736/health", {
  headers: {
    Authorization: `Bearer ${sidecarToken}`,
  },
}).then((response) => response.json());
```

## 当前边界

- `Knowledge Worker` 目前先做本地目录扫描与清单缓存
- `Security Agent` 当前仍以本地默认规则为主
- `Approval Agent` 当前只做单级审批缓存
- `Runtime Sidecar` 仍更偏本地运行时，不是纯浏览器 SDK
- Sidecar 启动时如果控制面暂时不可达，会降级启动本地服务，并把同步错误输出到 stderr

## 推荐开发检查

如果希望先确认当前配置是否完整，可以运行：

```bash
node ./dist/cli.js selfcheck
```

它会检查：

- gateway 是否已配置
- gateway 命令路径是否可解析
- sidecar 状态目录是否可写
- 当前认证态是否完整
- knowledge worker 配置是否存在

## 迁移文档

- [docs/MIGRATION_FROM_CUSTOM_GATEWAY.md](./docs/MIGRATION_FROM_CUSTOM_GATEWAY.md)

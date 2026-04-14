# QeeClaw AI PaaS 环境变量模板说明

最后更新：2026-03-22

## 1. 文档目标

本文档说明 `sdk/deploy/env/` 目录下各模板文件的用途、适用对象与关键字段。

当前模板目录为：

- `sdk/deploy/env/sdk-client.env.example`
- `sdk/deploy/env/runtime-sidecar.env.example`
- `sdk/deploy/env/gateway-server.env.example`
- `sdk/deploy/env/macos-release.env.example`

## 2. 使用原则

- 模板文件只保留占位值
- 真实密钥、账号、证书信息必须在客户环境单独注入
- 不要把复制后的实际 `.env` 文件提交到仓库
- 若字段涉及命令参数，优先使用明确、可审计的写法

## 3. 各模板适用对象

| 模板 | 适用对象 | 用途 |
| --- | --- | --- |
| `sdk-client.env.example` | Web / Node / Product SDK 示例 | 提供最小 `baseUrl + token + teamId` |
| `runtime-sidecar.env.example` | 桌面 App / 本地节点 | 提供 Sidecar 本地运行时配置 |
| `gateway-server.env.example` | Gateway 服务器 / relay 节点 | 提供容器部署占位参数 |
| `macos-release.env.example` | macOS 打包发布 | 提供签名、公证与版本配置模板 |

## 4. `sdk-client.env.example`

关键字段：

- `QEECLAW_BASE_URL`
  平台 API 地址
- `QEECLAW_TOKEN`
  用户登录态、设备 Key 或其他 Bearer Token
- `QEECLAW_TEAM_ID`
  默认工作空间 / 团队标识
- `QEECLAW_MOCK_TEAM_ID`
  本地 mock 示例的可选覆盖值

适用示例：

- `sdk/qeeclaw-core-sdk/examples/mock-client.mjs`
- `sdk/qeeclaw-product-sdk/examples/mock-dashboard.mjs`

## 5. `runtime-sidecar.env.example`

关键字段：

- `QEECLAW_CONTROL_PLANE_URL`
  Sidecar 回连的平台控制面地址
- `QEECLAW_SIDECAR_HOST`
- `QEECLAW_SIDECAR_PORT`
  Sidecar 本地 HTTP 服务监听地址
- `QEECLAW_SIDECAR_AUTH_TOKEN`
  Sidecar 本地 HTTP 服务 Bearer Token
- `QEECLAW_SIDECAR_ALLOW_REMOTE`
  是否允许 Sidecar 绑定到非 loopback 地址
- `QEECLAW_SIDECAR_START_GATEWAY`
  是否启动时自动托管 gateway
- `QEECLAW_SIDECAR_AUTO_BOOTSTRAP`
  是否自动补齐设备 bootstrap
- `QEECLAW_STATE_DIR`
- `QEECLAW_AUTH_STATE_FILE`
- `QEECLAW_SIDECAR_STATE_DIR`
  本地状态与缓存目录
- `QEECLAW_GATEWAY_COMMAND`
- `QEECLAW_GATEWAY_ARGS`
- `QEECLAW_GATEWAY_WORKDIR`
  gateway 启动命令与参数
- `QEECLAW_GATEWAY_WS_URL`
  本地 gateway WebSocket 地址

建议：

- `QEECLAW_SIDECAR_AUTH_TOKEN` 在正式项目里应显式配置，不建议依赖随机生成值
- `QEECLAW_SIDECAR_ALLOW_REMOTE` 默认保持 `false`
- `QEECLAW_GATEWAY_ARGS` 优先使用 JSON 数组写法
- 本地状态目录建议独立于业务代码目录
- 生产项目中不要把设备 token 与本地认证态文件混放在可公开目录

## 6. `gateway-server.env.example`

关键字段：

- `QEECLAW_GATEWAY_IMAGE`
  Gateway 容器镜像
- `QEECLAW_GATEWAY_PORT`
  宿主机映射端口
- `QEECLAW_GATEWAY_CONFIG_DIR`
- `QEECLAW_GATEWAY_WORKSPACE_DIR`
  Gateway 挂载目录
- `OPENCLAW_GATEWAY_TOKEN`
  后端连接 Gateway 的认证 token
- `OPENCLAW_LOG_LEVEL`
  运行日志级别
- `QEECLAW_GATEWAY_PUBLIC_URL`
- `QEECLAW_GATEWAY_SERVER_NAME`
  交付记录与 Nginx 对接所需的公网信息

适用模板：

- `sdk/deploy/compose/qeeclaw-gateway.compose.example.yml`
- `sdk/deploy/nginx/qeeclaw-gateway.conf.example`

## 7. `macos-release.env.example`

关键字段：

- `SIGN_IDENTITY`
  Apple Developer 证书名称
- `BUILD_CONFIG`
  打包类型，通常为 `release`
- `SET_VERSION`
  输出版本号
- `EMBEDDED_NODE_VERSION`
  打包时嵌入的 Node 版本
- `APPLE_ID`
- `APPLE_TEAM_ID`
- `APPLE_APP_PASSWORD`
  公证流程所需参数

注意：

- 这个模板只能作为占位示例
- 真实 Apple 账号与 App 专用密码不能进入公开仓

## 8. 推荐做法

- 团队内部复制模板到本地私有文件再填写
- CI/CD 用 Secret Manager 注入真实值
- 交付文档中只保留字段说明，不保留真实参数

## 9. 关联文档

- `sdk/docs/QeeClaw_AI_PaaS平台交付手册.md`
- `sdk/docs/QeeClaw_AI_PaaS私有化部署说明.md`
- `sdk/docs/QeeClaw_AI_PaaS安装升级与迁移说明.md`

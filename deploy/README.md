# QeeClaw AI PaaS 交付模板目录

这个目录用于承接 QeeClaw SDK 第一轮可公开的交付模板。

需要明确：

- `sdk/` 当前承载的是平台开放接入层
- 这里提供的是交付模板、边缘部署样例和接入侧环境变量模板
- 完整的 QeeClaw 控制面私有化部署，仍需要主平台仓中的后端、控制台、数据库、缓存、对象存储和向量存储一起交付

## 目录说明

### `env/`

环境变量模板：

- `sdk-client.env.example`
- `runtime-sidecar.env.example`
- `gateway-server.env.example`
- `macos-release.env.example`

### `compose/`

当前提供：

- `qeeclaw-gateway.compose.example.yml`

用于演示 Gateway / Relay 类边缘组件的最小容器化部署方式。

### `nginx/`

当前提供：

- `qeeclaw-gateway.conf.example`

用于演示 Gateway 的 HTTPS / WSS 反向代理方式。

## 对应文档

- `sdk/docs/README.md`
- `sdk/docs/QeeClaw_客户接入手册.md`
- `sdk/docs/QeeClaw_AI_PaaS平台交付手册.md`

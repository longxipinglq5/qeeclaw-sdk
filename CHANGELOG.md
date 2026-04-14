# Changelog

## v0.1.0

首次整理为可公开发布的 QeeClaw SDK 结构。

### Added

- `@qeeclaw/core-sdk` 作为标准平台能力接入层
- `@qeeclaw/product-sdk` 作为驾驶舱和工作台场景的高层业务 kit
- `@qeeclaw/runtime-sidecar` 作为本地运行时与 gateway adapter
- `meeting_device_firmware` 作为会议设备硬件接入样例
- Web、桌面 App、移动端 App 三套对接文档
- 开源发布说明、检查清单、成熟度分级说明
- AI PaaS 平台交付手册、私有化部署说明、安装升级与迁移说明
- `sdk/deploy/` 交付资产目录，包含 env、compose、nginx 示例模板

### Changed

- `runtime-sidecar` 改为支持可配置的 gateway 启动方式
- Sidecar 状态目录与认证态文件改为优先使用通用的 `.qeeclaw` / `auth-state.json`
- 保留对旧目录、旧文件名和旧环境变量的兼容
- 会议设备脚本改为默认只使用本地开发地址或占位域名
- 固件配置改为可通过 PlatformIO 构建参数覆盖
- 对外交付口径从“零散脚本”提升为“平台交付资产 + 开放接入层”

### Security

- 去除了公开脚本和文档中的生产域名默认值
- 去除了“直接打生产环境”的测试脚本默认行为
- 对外文档统一改为占位域名和参数化配置方式

### Maturity

- `@qeeclaw/core-sdk`: Stable
- `@qeeclaw/product-sdk`: Beta
- `@qeeclaw/runtime-sidecar`: Experimental
- `meeting_device_firmware`: Community Preview

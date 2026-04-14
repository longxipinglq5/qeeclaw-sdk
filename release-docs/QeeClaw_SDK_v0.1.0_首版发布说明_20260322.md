# QeeClaw SDK v0.1.0 首版发布说明

发布日期：2026-03-22

版本：`v0.1.0`

## 1. 版本定位

这是 QeeClaw SDK 面向公开仓库形态整理后的首个发布版本。

本次发布目标不是一次性把所有模块宣告为同等成熟，而是建立一套可以被外部团队理解、安装、验证和反馈的统一 SDK 结构。

## 2. 本次发布包含的模块

| 模块 | 对外定位 | 当前成熟度 |
| --- | --- | --- |
| `@qeeclaw/core-sdk` | 标准平台能力接入层 | `stable` |
| `@qeeclaw/product-sdk` | 驾驶舱/工作台高层 kit | `beta` |
| `@qeeclaw/runtime-sidecar` | 本地运行时参考实现 | `experimental` |
| `meeting_device_firmware` | 会议设备接入样例 | `community-preview` |

## 3. 本版重点内容

### 3.1 标准化 SDK 分层

- 明确 `core-sdk`、`product-sdk`、`runtime-sidecar`、`meeting_device_firmware` 四层结构
- 统一文档入口、许可证说明和公开仓布局

### 3.2 Sidecar 去内部耦合

- `runtime-sidecar` 改为支持通用 `gatewayCommand/gatewayArgs`
- 本地状态目录和认证文件路径改为可配置
- 保留旧环境变量和旧路径的兼容能力

### 3.3 固件与脚本公开化整理

- 固件文档和联调脚本默认只使用本地地址或占位值
- 端到端脚本不再隐式依赖私有仓库目录
- 新增示例 WAV 生成脚本，便于独立联调

### 3.4 公开仓可发布治理补齐

- 增加 `LICENSE`、`LICENSES.md`、`CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`
- 增加 GitHub issue / PR 模板
- 提供导出脚本与发布检查脚本

## 4. 推荐发布顺序

1. 优先发布 `@qeeclaw/core-sdk`
2. 随后发布 `@qeeclaw/product-sdk`
3. `@qeeclaw/runtime-sidecar` 以 `next` 或非 `latest` tag 验证市场反馈
4. `meeting_device_firmware` 以仓库目录和文档样例方式公开

## 5. 已完成的首版验证

- 公开仓导出成功
- `pnpm install` 通过
- `pnpm run release:check` 通过
- `pnpm run release:pack` 通过
- `pnpm demo` 通过
- 固件 Python 脚本语法检查通过

## 6. 已知边界

- `runtime-sidecar` 当前更适合桌面端、本地节点和边缘部署场景
- 原生 iOS / Android / Flutter 当前仍建议优先直接对接 Platform API
- `meeting_device_firmware` 仍需要硬件侧适配和实际设备调试能力

## 7. 外部团队如何开始

1. 阅读 `QeeClaw_SDK通用说明.md`
2. 按终端形态选择 Web、桌面 App 或移动端接入文档
3. 优先从 `@qeeclaw/core-sdk` 开始集成
4. 需要聚合数据首页时再引入 `@qeeclaw/product-sdk`
5. 需要本地运行时能力时再引入 `@qeeclaw/runtime-sidecar`

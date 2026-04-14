# QeeClaw SDK 开源发布说明

最后更新：2026-03-22

## 1. 文档目的

本文档用于说明当前 SDK 在“整体公开”前提下，应该如何组织模块定位、成熟度标签、目录结构和发布口径。

说明：

- 在当前 monorepo 中，SDK 源码位于 `sdk/` 目录下
- 在导出的独立公开仓库中，SDK 内容位于仓库根目录

## 2. 当前发布策略

当前建议采用：

- 全部模块都可公开
- 但按成熟度分级发布
- 默认示例仅使用本地开发地址或占位域名

推荐成熟度标签如下：

| 模块 | 建议标签 |
| --- | --- |
| `qeeclaw-core-sdk` / `packages/core-sdk` | `stable` |
| `qeeclaw-product-sdk` / `packages/product-sdk` | `beta` |
| `qeeclaw-runtime-sidecar` / `packages/runtime-sidecar` | `experimental` |
| `meeting_device_firmware` / `hardware/meeting-device-firmware` | `community-preview` |

配套命令说明见：

- `QeeClaw_SDK公开仓库初始化与发布命令.md`

## 3. 为什么要分成熟度而不是“一视同仁”

### 3.1 `core-sdk`

它已经最接近外部团队对“标准 SDK”的预期：

- 包结构完整
- 能力边界清晰
- 示例和 mock 联调能力完整

### 3.2 `product-sdk`

它适合公开，但仍然更偏高层装配语义：

- 适合驾驶舱和工作台
- 对外价值高
- 字段和 kit 仍可能继续演进

### 3.3 `runtime-sidecar`

它已经可以公开，但更适合标记为 `experimental`：

- 它是本地运行时，不是普通前端 SDK
- 它依赖本地进程和本地状态目录
- 它现在支持可配置的 gateway 启动方式，但仍然属于运行时组件

### 3.4 `meeting_device_firmware`

它也可以公开，但更适合标记为 `community-preview`：

- 它是硬件集成样例，不是标准应用 SDK
- 它带有 PlatformIO、硬件、音频格式和设备部署要求
- 已移除生产地址默认值，但对接仍需要硬件团队配合

## 4. 公开仓库推荐结构

如果后续要拆出独立仓库，建议结构如下：

```text
qeeclaw-sdk/
  README.md
  LICENSE
  LICENSES.md
  .github/
  docs/
    QeeClaw_SDK通用说明.md
    QeeClaw_SDK_Web对接文档.md
    QeeClaw_SDK_桌面App对接文档.md
    QeeClaw_SDK_移动端App对接文档.md
    QeeClaw_SDK开源发布说明.md
    QeeClaw_SDK开源发布检查清单.md
    QeeClaw_SDK_v0.1.0_首版发布说明_20260322.md
  packages/
    core-sdk/
    product-sdk/
    runtime-sidecar/
  hardware/
    meeting-device-firmware/
```

如果继续保留在 monorepo 中，也建议在文档和 README 中明确上述分层。

## 5. 对外发布口径建议

建议统一对外表达为：

- `QeeClaw Core SDK` 是标准平台能力接入层
- `QeeClaw Product SDK` 是面向业务首页/驾驶舱的高层 kit
- `Runtime Sidecar` 是本地运行时组件，适合桌面与边缘场景
- `Meeting Device Firmware` 是公开硬件集成样例

不建议对外表达为：

- “所有团队都必须先装 Sidecar”
- “移动端可以直接访问桌面端本机服务”
- “固件目录里的示例地址就是公共生产入口”

## 6. 默认示例策略

公开仓库中的默认示例应满足：

- HTTP 示例默认连 `http://127.0.0.1:<port>` 或 `https://api.example.com`
- WebSocket 示例默认连 `ws://127.0.0.1:<port>` 或 `wss://api.example.com`
- 不直接硬编码真实生产域名
- 所有真实部署地址通过环境变量、参数或构建参数注入

## 7. 发布建议

推荐发布顺序：

1. 先对外说明整体架构和四个模块的定位
2. 先发布 `core-sdk`
3. 再发布 `product-sdk`
4. 同步发布 `runtime-sidecar`，但加 `experimental` 标识
5. 同步公开 `meeting_device_firmware`，并明确 `community-preview`

## 8. 发布前还应检查

- 根目录存在可被 GitHub/开源托管平台识别的 `LICENSE`
- `.github` 中已提供 issue / PR 模板与协作说明
- 敏感信息扫描
- 示例和脚本默认地址检查
- LICENSE 与依赖许可证检查
- 文档示例与当前代码字段一致性检查
- 关键脚本可运行性验证

# QeeClaw SDK 第三方依赖许可证审计

最后更新：2026-03-22

## 1. 审计范围

本次只审计 `sdk/` 目录当前直接声明和直接使用的第三方依赖，不展开完整传递依赖树。

覆盖范围：

- Node.js 包依赖
- Python 脚本直接依赖
- PlatformIO 平台、框架与显式声明的库依赖

说明：

- Node 依赖版本以 `package.json` 声明与本地安装结果为准
- Python 依赖版本以本机 `importlib.metadata` 实际读取到的安装版本为准
- PlatformIO 依赖以 `platformio.ini` 中直接声明的 `platform`、`framework`、`lib_deps` 为准

## 2. 审计结果总览

| 类别 | 依赖 | 版本/来源 | 许可证 | 结论 |
| --- | --- | --- | --- | --- |
| Node | `typescript` | 本地安装 `5.9.3` | `Apache-2.0` | 可接受 |
| Node | `@types/node` | 本地安装 `25.5.0` | `MIT` | 可接受 |
| Python | `requests` | 本地安装 `2.32.5` | `Apache-2.0` | 可接受 |
| Python | `websockets` | 本地安装 `11.0.3` | `BSD-3-Clause` | 可接受 |
| PlatformIO | `platformio/espressif32` | `platform = espressif32` | `Apache-2.0` | 可接受 |
| PlatformIO | `espressif/arduino-esp32` | `framework = arduino` | `LGPL-2.1` | 可用，但需注意分发合规 |
| PlatformIO | `ArduinoJson` | `ArduinoJson@^7.0.0` | `MIT` | 可接受 |
| PlatformIO | `WiFi` / `HTTPClient` / `FS` / `SPIFFS` | Arduino-ESP32 框架内置库 | 随 `arduino-esp32` 框架分发，按 `LGPL-2.1` 口径处理 | 可用，但需注意分发合规 |

## 3. 分类结论

### 3.1 `@qeeclaw/core-sdk`

直接依赖仅包含：

- `typescript`
- `@types/node`

这两项均为宽松许可证，可与当前 `Apache-2.0` 发布策略兼容。

### 3.2 `@qeeclaw/product-sdk`

直接依赖与 `core-sdk` 一致，均为宽松许可证。

### 3.3 `@qeeclaw/runtime-sidecar`

直接依赖与 `core-sdk` 一致，均为宽松许可证。

### 3.4 `meeting_device_firmware`

固件联调脚本直接使用：

- `requests`
- `websockets`

二者均为宽松许可证。

但固件构建依赖的 Arduino 运行时来自 `arduino-esp32`，该项目为 `LGPL-2.1`。因此：

- 当前以源码仓库和样例工程形式公开，没有明显阻塞
- 如果未来对外分发预编译固件、安装包或修改后的框架二进制，需要补充 LGPL 合规动作

## 4. 当前建议

### 4.1 可以直接公开的部分

- `@qeeclaw/core-sdk`
- `@qeeclaw/product-sdk`
- `@qeeclaw/runtime-sidecar`
- `meeting_device_firmware` 源码与文档样例

### 4.2 后续仍建议保留的合规动作

- 如果发布预编译固件，保留并公开对应源码、许可证和变更说明
- 如果固件打包进商业安装器，额外补一份第三方许可证归档
- 在正式 GitHub 仓库 release 页面附上本审计文档

## 5. 审计依据

### Node

- 本地安装包元数据：
  - `typescript@5.9.3`
  - `@types/node@25.5.0`
- 官方项目页：
  - TypeScript: `https://github.com/microsoft/TypeScript`
  - DefinitelyTyped: `https://github.com/DefinitelyTyped/DefinitelyTyped`

### Python

- 本机 `importlib.metadata` 读取结果：
  - `requests==2.32.5`
  - `websockets==11.0.3`
- 官方项目页：
  - Requests: `https://github.com/psf/requests`
  - websockets: `https://pypi.org/project/websockets/`

### PlatformIO / Firmware

- `sdk/meeting_device_firmware/platformio.ini`
- 官方项目页：
  - PlatformIO Espressif32: `https://github.com/platformio/platform-espressif32`
  - Arduino-ESP32: `https://github.com/espressif/arduino-esp32`
  - ArduinoJson: `https://github.com/bblanchon/ArduinoJson`

## 6. 审计结论

在当前发布形态下，`sdk/` 的直接第三方依赖许可证没有发现阻止开源发布的明显问题。

需要重点关注的唯一特殊项是固件侧 `arduino-esp32` 的 `LGPL-2.1` 合规要求，但它不会阻止当前源码仓库公开；它更影响未来对外分发预编译固件或修改后的框架二进制的方式。

# ReSpeaker XVF3800 Meeting Device Firmware

ESP32 固件项目，用于将 ReSpeaker XVF3800 会议设备接入 QeeClaw Platform。

> Status: Community Preview

> 这一目录已经调整为可公开样例形态，但接入前仍建议替换为你自己的 API 地址、鉴权方案和部署参数。

## 功能特性

- WiFi 自动连接与重连
- 设备注册与绑定码获取
- 音频上传
- 会议结果轮询查询
- 设备心跳保活
- 串口命令交互

## 硬件要求

- ReSpeaker XVF3800 USB 4-Mic Array
- XIAO ESP32S3
- USB Type-C 数据线

## 快速开始

### 1. 安装 PlatformIO

```bash
pip install platformio
```

### 2. 配置 WiFi 和服务器

推荐直接在 [platformio.ini](./platformio.ini) 的 `build_flags` 中覆盖参数：

```ini
build_flags =
  -DCORE_DEBUG_LEVEL=3
  -DARDUINO_USB_MODE=1
  -DARDUINO_USB_CDC_ON_BOOT=1
  -DQEECLAW_WIFI_SSID='"YourWiFiSSID"'
  -DQEECLAW_WIFI_PASSWORD='"YourWiFiPassword"'
  -DQEECLAW_API_BASE_URL='"http://127.0.0.1:8000"'
  -DQEECLAW_DEVICE_NAME='"Meeting Room Device"'
```

如果你更习惯直接改源码，也可以修改 [main.cpp](./src/main.cpp) 中的默认宏。

### 3. 编译和烧录

```bash
pio run
pio run --target upload
pio device monitor
```

## 串口命令

连接串口后，支持以下命令：

| 命令 | 说明 |
|------|------|
| `status` | 显示设备状态 |
| `register` | 重新注册设备 |
| `heartbeat` | 发送心跳 |
| `help` | 显示帮助信息 |

## API 接口

设备固件调用以下接口：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/meeting-device/register` | POST | 设备注册 |
| `/api/meeting-device/upload-audio` | POST | 上传音频 |
| `/api/meeting-device/result/{task_id}` | GET | 查询结果 |
| `/api/meeting-device/heartbeat` | POST | 心跳 |
| `/api/meeting-device/status` | GET | 查询状态 |

完整协议说明见 [HARDWARE_INTEGRATION_GUIDE.md](./HARDWARE_INTEGRATION_GUIDE.md)。

## 测试脚本

`scripts/` 目录提供了几类联调脚本：

| 脚本 | 说明 |
|------|------|
| `flash_mac.py` | 读取或烧录 MAC 地址 |
| `generate_sample_wav.py` | 生成本地联调用示例 WAV 文件 |
| `test_api.py` | HTTP API 联调 |
| `test_stream_api.py` | WebSocket 流接口测试 |
| `test_stream_e2e.py` | 带真实音频文件的端到端测试 |

默认情况下，测试脚本会连本地开发地址：

- `http://127.0.0.1:8000`
- `ws://127.0.0.1:8000/api/meeting-device/stream`

也可以通过参数或环境变量覆盖：

```bash
QEECLAW_MEETING_DEVICE_API_BASE_URL=http://127.0.0.1:8000 \
python scripts/test_api.py
```

```bash
python scripts/test_stream_api.py \
  --api-base-url http://127.0.0.1:8000
```

```bash
python scripts/generate_sample_wav.py
```

```bash
python scripts/test_stream_e2e.py \
  --api-base-url http://127.0.0.1:8000 \
  --audio ./scripts/output/sample.wav
```

## 项目结构

```text
meeting_device_firmware/
├── HARDWARE_INTEGRATION_GUIDE.md
├── LICENSE
├── platformio.ini
├── src/
│   ├── api_client.cpp
│   ├── api_client.h
│   ├── main.cpp
│   ├── wifi_manager.cpp
│   └── wifi_manager.h
└── scripts/
    ├── flash_mac.py
    ├── generate_sample_wav.py
    ├── test_api.py
    ├── test_stream_api.py
    └── test_stream_e2e.py
```

## 开发说明

### API 地址约定

- 固件中的 `QEECLAW_API_BASE_URL` 应指向你的平台地址，例如 `http://127.0.0.1:8000`
- 文档中的 `api.example.com` 仅为占位示例
- 不建议把公开仓库中的示例脚本默认指向真实生产地址

### 添加音频录制功能

ReSpeaker XVF3800 通过 I2S 接口输出音频，可参考以下代码添加录音功能：

```cpp
#include <driver/i2s.h>

const i2s_port_t I2S_PORT = I2S_NUM_0;
const int SAMPLE_RATE = 16000;
const int BITS_PER_SAMPLE = 16;
```

### 内存优化

ESP32S3 有 8MB PSRAM，可用于缓存大块音频数据：

```cpp
uint8_t* audioBuffer = (uint8_t*)ps_malloc(BUFFER_SIZE);
```

## 许可证

MIT License

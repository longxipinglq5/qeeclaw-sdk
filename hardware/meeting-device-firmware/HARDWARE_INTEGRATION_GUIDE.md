# ReSpeaker XVF3800 会议设备 - 硬件对接指南

> **文档版本**: 1.0  
> **更新日期**: 2026-01-19  
> **面向对象**: 硬件/嵌入式开发团队

---

## 概述

本文档描述会议设备需要调用的云端 API 接口，以实现设备注册、音频上传和会议纪要获取功能。

---

## 环境配置

### 服务器地址

| 环境 | API 地址 | 备注 |
|------|---------|------|
| 本地开发 | `http://127.0.0.1:8000` | 适合联调与本地 Mock |
| 正式部署 | `https://api.example.com` | 请替换为你的真实部署地址 |

> ⚠️ 示例域名仅用于说明接口格式，请替换为你的实际部署地址。

---

## API 接口说明

### 1. 设备注册

设备首次启动或恢复出厂后调用，获取绑定码。

**请求**
```
POST /api/meeting-device/register
Content-Type: application/json

{
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "device_name": "会议室1号",           // 可选
    "firmware_version": "1.0.0"           // 可选
}
```

**响应**
```json
{
    "code": 0,
    "data": {
        "bind_code": "123456",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "device_id": "AA:BB:CC:DD:EE:FF"
    },
    "message": "设备注册成功"
}
```

**说明**
- MAC 地址支持多种格式：`AABBCCDDEEFF`、`AA:BB:CC:DD:EE:FF`、`AA-BB-CC-DD-EE-FF`
- 绑定码为 6 位数字，由 MAC 地址确定性生成（相同 MAC 始终返回相同绑定码）
- 绑定码用于用户在 App/Web 端绑定设备

---

### 2. 上传会议录音

会议结束后调用，上传录音文件。

**请求**
```
POST /api/meeting-device/upload-audio
Content-Type: multipart/form-data

字段:
- mac_address: "AA:BB:CC:DD:EE:FF" (必填)
- audio_file: [音频文件] (必填)
- meeting_name: "周例会" (可选)
- enable_summary: "true" (可选, 默认 true)
```

**响应**
```json
{
    "code": 0,
    "data": {
        "task_id": "task_20260119_xxxxx",
        "status": "pending"
    },
    "message": "音频上传成功，正在处理"
}
```

**音频格式要求**
| 参数 | 要求 |
|------|------|
| 格式 | WAV, PCM, MP3, M4A, WebM, Opus |
| 采样率 | 16000 Hz (推荐) |
| 位深度 | 16-bit |
| 声道 | 单声道或立体声 |
| 最大时长 | 无限制（建议单次 < 2 小时） |
| 最大文件 | 500MB |

---

### 2.5 实时音频流上传（WebSocket）

**🆕 新增** - 支持设备实时推送音频流，自动检测静默超时后结束录音并生成会议纪要。

**连接地址**
```
WebSocket: wss://api.example.com/api/meeting-device/stream
```

**连接参数**（Query String）
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| mac_address | string | ✅ | 设备MAC地址 |
| meeting_name | string | ❌ | 会议名称 |
| enable_summary | bool | ❌ | 是否生成会议纪要，默认 true |
| silence_timeout | float | ❌ | 静默超时时间（秒），默认 30 |

**示例连接 URL**
```
wss://api.example.com/api/meeting-device/stream?mac_address=AA:BB:CC:DD:EE:FF&meeting_name=周例会&silence_timeout=30
```

**音频格式要求**
| 参数 | 要求 |
|------|------|
| 格式 | 原始 PCM 数据（无文件头） |
| 采样率 | 16000 Hz |
| 位深度 | 16-bit |
| 声道 | 单声道 |

**消息格式**

#### 设备 → 服务器

1. **音频数据** - 二进制 WebSocket 消息，直接发送 PCM 数据
2. **结束录音** - JSON 消息
   ```json
   {"type": "end"}
   ```
3. **心跳** - JSON 消息（重置静默计时器）
   ```json
   {"type": "ping"}
   ```

#### 服务器 → 设备

1. **连接就绪**
   ```json
   {
       "type": "ready",
       "session_id": "stream_1737366000000",
       "task_id": "task_xxxxx",
       "silence_timeout": 30
   }
   ```

2. **音频接收确认**（每接收 10KB 发送一次）
   ```json
   {
       "type": "ack",
       "bytes_received": 102400
   }
   ```

3. **静默超时**
   ```json
   {
       "type": "timeout",
       "task_id": "task_xxxxx",
       "reason": "silence_timeout"
   }
   ```

4. **录音完成**
   ```json
   {
       "type": "completed",
       "task_id": "task_xxxxx",
       "total_bytes": 1048576,
       "duration_seconds": 120.5
   }
   ```

5. **错误**
   ```json
   {
       "type": "error",
       "message": "错误描述"
   }
   ```

**工作流程**
```
设备连接 WebSocket
      ↓
收到 {"type": "ready", "task_id": "..."}
      ↓
┌─────────────────────────────┐
│  循环发送 PCM 音频数据        │
│  （二进制 WebSocket 消息）    │
│                             │
│  收到 ack 确认               │
└─────────────────────────────┘
      ↓
方式1: 发送 {"type": "end"} 主动结束
方式2: 静默超时自动结束（默认30秒无数据）
      ↓
收到 {"type": "completed"} 或 {"type": "timeout"}
      ↓
使用 task_id 轮询 /result/{task_id} 获取结果
```

---

### 3. 查询会议结果

轮询查询任务状态和结果。

**请求**
```
GET /api/meeting-device/result/{task_id}
```

**响应**
```json
{
    "code": 0,
    "data": {
        "task_id": "task_20260119_xxxxx",
        "status": "completed",
        "transcript": "会议内容转写文本...",
        "meeting_summary": "会议纪要...",
        "error_message": null,
        "created_at": "2026-01-19T10:00:00",
        "completed_at": "2026-01-19T10:05:30"
    },
    "message": "success"
}
```

**状态值说明**
| status | 说明 | 建议操作 |
|--------|------|----------|
| `pending` | 排队中 | 等待 5 秒后重试 |
| `processing` | 处理中 | 等待 5 秒后重试 |
| `completed` | 完成 | 获取结果 |
| `failed` | 失败 | 查看 error_message |

---

### 4. 设备心跳

定期发送心跳，保持设备在线状态。

**请求**
```
POST /api/meeting-device/heartbeat
Content-Type: application/json

{
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "status": "online",
    "local_ip": "192.168.1.36",
    "lan_ip": "192.168.1.36",
    "local_host": "192.168.1.36"
}
```

**响应**
```json
{
    "code": 0,
    "data": {
        "success": true,
        "server_time": "2026-01-19T10:00:00"
    },
    "message": "心跳成功"
}
```

**建议**: 每 60 秒发送一次心跳

---

### 5. 查询设备状态

查询设备的注册和绑定状态。

**请求**
```
GET /api/meeting-device/status?mac_address=AA:BB:CC:DD:EE:FF
```

**响应**
```json
{
    "code": 0,
    "data": {
        "registered": true,
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "device_name": "会议室1号",
        "status": "pending",
        "is_bound": false,
        "bind_code": "123456",
        "last_heartbeat": "2026-01-19T10:00:00"
    },
    "message": "success"
}
```

---

## 错误处理

### 错误响应格式
```json
{
    "code": 400,
    "data": null,
    "message": "错误描述"
}
```

### 常见错误码
| code | 说明 | 处理建议 |
|------|------|----------|
| 0 | 成功 | - |
| 400 | 请求参数错误 | 检查请求格式 |
| 404 | 资源不存在 | 设备未注册或任务不存在 |
| 500 | 服务器错误 | 重试或联系软件团队 |

---

## 典型工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                     设备启动                                  │
└────────────────────────┬────────────────────────────────────┘
                         ▼
              ┌─────────────────────┐
              │  连接 WiFi          │
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │  调用 /register     │──→ 获取绑定码
              │  获取绑定码显示在屏幕 │      (用户在App端输入)
              └──────────┬──────────┘
                         ▼
         ┌───────────────────────────────┐
         │        主循环                  │
         │  ┌─────────────────────────┐  │
         │  │ 定时调用 /heartbeat     │  │  ← 每 60 秒
         │  └─────────────────────────┘  │
         │  ┌─────────────────────────┐  │
         │  │ 用户按下录音键          │  │
         │  │ → 开始录音              │  │
         │  │ → 用户按下停止键        │  │
         │  │ → 调用 /upload-audio   │  │
         │  │ → 获取 task_id         │  │
         │  └─────────────────────────┘  │
         │  ┌─────────────────────────┐  │
         │  │ 轮询 /result/{task_id} │  │  ← 每 5 秒
         │  │ → 直到 status=completed│  │
         │  │ → 显示/播放会议纪要     │  │
         │  └─────────────────────────┘  │
         └───────────────────────────────┘
```

---

## 固件参考代码

我们已提供完整的 ESP32 固件示例代码：

**代码位置**: `sdk/meeting_device_firmware/`

```
meeting_device_firmware/
├── platformio.ini          # PlatformIO 配置
├── README.md               # 使用说明
├── src/
│   ├── main.cpp           # 主程序
│   ├── wifi_manager.h/cpp # WiFi 管理
│   └── api_client.h/cpp   # API 客户端封装
└── scripts/
    └── flash_mac.py       # MAC 地址工具
```

可直接使用或参考 `api_client.cpp` 中的 HTTP 请求实现。

---

## 联调清单

硬件团队完成以下功能后，可进行联调：

- [ ] WiFi 连接功能
- [ ] 调用 `/register` 获取绑定码
- [ ] 在设备屏幕显示绑定码
- [ ] XVF3800 音频采集 (I2S)
- [ ] 录音数据缓存 (WAV 格式)
- [ ] 调用 `/upload-audio` 上传
- [ ] 轮询 `/result` 获取结果
- [ ] 定时心跳 `/heartbeat`
- [ ] 错误重试机制

---

## 联系方式

如有问题，请联系软件团队获取支持。

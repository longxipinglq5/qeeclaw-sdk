/**
 * ReSpeaker XVF3800 Meeting Device - Main Entry Point
 *
 * 会议设备主程序，演示设备注册和 API 调用流程
 *
 * 配置说明：
 * 1. 修改 WIFI_SSID 和 WIFI_PASSWORD 为你的 WiFi 信息
 * 2. 修改 API_BASE_URL 为你的服务器地址
 * 3. 编译并烧录到 XIAO ESP32S3
 */

#include "api_client.h"
#include "wifi_manager.h"
#include <Arduino.h>

// ============= 配置区域 =============
#ifndef QEECLAW_WIFI_SSID
#define QEECLAW_WIFI_SSID "YourWiFiSSID"
#endif

#ifndef QEECLAW_WIFI_PASSWORD
#define QEECLAW_WIFI_PASSWORD "YourWiFiPassword"
#endif

#ifndef QEECLAW_API_BASE_URL
#define QEECLAW_API_BASE_URL "http://127.0.0.1:8000"
#endif

#ifndef QEECLAW_DEVICE_NAME
#define QEECLAW_DEVICE_NAME "Meeting Room Device"
#endif

// WiFi 配置
const char *WIFI_SSID = QEECLAW_WIFI_SSID;
const char *WIFI_PASSWORD = QEECLAW_WIFI_PASSWORD;

// API 服务器地址
const char *API_BASE_URL = QEECLAW_API_BASE_URL;

// 设备名称
const char *DEVICE_NAME = QEECLAW_DEVICE_NAME;

// 心跳间隔（毫秒）
const unsigned long HEARTBEAT_INTERVAL = 60000;
// =====================================

WiFiManager wifiManager;
APIClient apiClient;

String bindCode = "";
unsigned long lastHeartbeat = 0;
bool isRegistered = false;

// LED 引脚定义 (XIAO ESP32S3)
const int LED_PIN = 21;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n====================================");
  Serial.println("ReSpeaker XVF3800 Meeting Device");
  Serial.println("====================================\n");

  // 初始化 LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // 连接 WiFi
  Serial.println("[BOOT] Connecting to WiFi...");
  wifiManager.begin(WIFI_SSID, WIFI_PASSWORD);

  if (!wifiManager.connect()) {
    Serial.println("[BOOT] WiFi connection failed!");
    // 闪烁 LED 表示错误
    for (int i = 0; i < 10; i++) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
      delay(200);
    }
    return;
  }

  Serial.println("[BOOT] WiFi connected!");
  Serial.println("[BOOT] MAC: " + wifiManager.getMacAddress());

  // 初始化 API 客户端
  apiClient.begin(API_BASE_URL);
  apiClient.setMacAddress(wifiManager.getMacAddress());
  apiClient.setLocalNetwork(wifiManager.getLocalIP(), wifiManager.getLocalIP());

  // 注册设备
  Serial.println("[BOOT] Registering device...");
  RegisterResult result = apiClient.registerDevice(DEVICE_NAME);

  if (result.success) {
    bindCode = result.bindCode;
    isRegistered = true;

    Serial.println("\n====================================");
    Serial.println("✅ Device Registered Successfully!");
    Serial.println("Bind Code: " + bindCode);
    Serial.println("====================================\n");

    // 常亮 LED 表示注册成功
    digitalWrite(LED_PIN, HIGH);
  } else {
    Serial.println("[BOOT] Device registration failed!");
    // 快速闪烁 LED
    for (int i = 0; i < 20; i++) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
      delay(100);
    }
  }
}

void loop() {
  // WiFi 重连检查
  wifiManager.loop();

  if (!wifiManager.isConnected()) {
    delay(1000);
    return;
  }

  // 定期心跳
  unsigned long now = millis();
  if (isRegistered && (now - lastHeartbeat > HEARTBEAT_INTERVAL)) {
    lastHeartbeat = now;
    apiClient.setLocalNetwork(wifiManager.getLocalIP(), wifiManager.getLocalIP());

    if (apiClient.sendHeartbeat()) {
      Serial.println("[HEARTBEAT] OK");
    } else {
      Serial.println("[HEARTBEAT] Failed");
    }
  }

  // 检查串口命令
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "status") {
      Serial.println("\n--- Device Status ---");
      Serial.println("WiFi: " + (wifiManager.isConnected()
                                     ? String("Connected")
                                     : String("Disconnected")));
      Serial.println("IP: " + wifiManager.getLocalIP());
      Serial.println("MAC: " + wifiManager.getMacAddress());
      Serial.println("Registered: " + String(isRegistered ? "Yes" : "No"));
      Serial.println("Bind Code: " + bindCode);
      Serial.println("-------------------\n");
    } else if (cmd == "register") {
      RegisterResult result = apiClient.registerDevice(DEVICE_NAME);
      if (result.success) {
        bindCode = result.bindCode;
        isRegistered = true;
        Serial.println("Registered! Bind code: " + bindCode);
      }
    } else if (cmd == "heartbeat") {
      bool ok = apiClient.sendHeartbeat();
      Serial.println("Heartbeat: " + String(ok ? "OK" : "Failed"));
    } else if (cmd == "help") {
      Serial.println("\nAvailable commands:");
      Serial.println("  status    - Show device status");
      Serial.println("  register  - Register device");
      Serial.println("  heartbeat - Send heartbeat");
      Serial.println("  help      - Show this help\n");
    }
  }

  delay(100);
}

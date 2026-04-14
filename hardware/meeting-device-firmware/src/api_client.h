/**
 * ReSpeaker XVF3800 Meeting Device - API Client
 *
 * HTTP API 客户端，用于与云端平台通信
 */

#ifndef API_CLIENT_H
#define API_CLIENT_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>

struct APIResponse {
  int code;
  String message;
  JsonDocument data;
  bool success;
};

struct RegisterResult {
  bool success;
  String bindCode;
  String deviceId;
};

struct UploadResult {
  bool success;
  String taskId;
  String status;
};

struct MeetingResult {
  bool success;
  String taskId;
  String status; // pending, processing, completed, failed
  String transcript;
  String meetingSummary;
  String errorMessage;
};

class APIClient {
public:
  APIClient();

  /**
   * 初始化 API 客户端
   * @param baseUrl API 基础地址（如 http://api.example.com:8000）
   */
  void begin(const String &baseUrl);

  /**
   * 设置 MAC 地址
   * @param macAddress 设备 MAC 地址
   */
  void setMacAddress(const String &macAddress);

  /**
   * 设置局域网发现线索（用于心跳上报）
   * @param localIp 设备局域网 IP
   * @param localHost 设备局域网主机名/IP（可选）
   */
  void setLocalNetwork(const String &localIp, const String &localHost = "");

  /**
   * 注册设备
   * @param deviceName 设备名称（可选）
   * @return 注册结果
   */
  RegisterResult registerDevice(const String &deviceName = "");

  /**
   * 上传音频数据
   * @param audioData 音频数据指针
   * @param dataLength 数据长度
   * @param filename 文件名
   * @param enableSummary 是否生成会议纪要
   * @return 上传结果
   */
  UploadResult uploadAudio(const uint8_t *audioData, size_t dataLength,
                           const String &filename = "meeting.wav",
                           bool enableSummary = true);

  /**
   * 查询会议结果
   * @param taskId 任务ID
   * @return 会议结果
   */
  MeetingResult getResult(const String &taskId);

  /**
   * 发送心跳
   * @return 是否成功
   */
  bool sendHeartbeat();

  /**
   * 检查设备状态
   * @return 是否已注册
   */
  bool checkStatus();

private:
  String _baseUrl;
  String _macAddress;
  String _localIp;
  String _localHost;
  HTTPClient _http;

  APIResponse doPost(const String &endpoint, const String &jsonBody);
  APIResponse doGet(const String &endpoint);
};

#endif // API_CLIENT_H

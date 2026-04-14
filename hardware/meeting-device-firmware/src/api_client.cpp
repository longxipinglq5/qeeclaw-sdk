/**
 * ReSpeaker XVF3800 Meeting Device - API Client Implementation
 */

#include "api_client.h"

APIClient::APIClient() {}

void APIClient::begin(const String &baseUrl) {
  _baseUrl = baseUrl;
  // Remove trailing slash if present
  if (_baseUrl.endsWith("/")) {
    _baseUrl = _baseUrl.substring(0, _baseUrl.length() - 1);
  }
}

void APIClient::setMacAddress(const String &macAddress) {
  _macAddress = macAddress;
}

void APIClient::setLocalNetwork(const String &localIp, const String &localHost) {
  _localIp = localIp;
  _localHost = localHost;
}

APIResponse APIClient::doPost(const String &endpoint, const String &jsonBody) {
  APIResponse response;
  response.success = false;
  response.code = -1;

  String url = _baseUrl + endpoint;
  _http.begin(url);
  _http.addHeader("Content-Type", "application/json");

  int httpCode = _http.POST(jsonBody);

  if (httpCode > 0) {
    String payload = _http.getString();

    DeserializationError error = deserializeJson(response.data, payload);
    if (!error) {
      response.code = response.data["code"] | -1;
      response.message = response.data["message"] | "";
      response.success = (response.code == 0);
    } else {
      response.message = "JSON parse error";
    }
  } else {
    response.message = "HTTP error: " + String(httpCode);
  }

  _http.end();
  return response;
}

APIResponse APIClient::doGet(const String &endpoint) {
  APIResponse response;
  response.success = false;
  response.code = -1;

  String url = _baseUrl + endpoint;
  _http.begin(url);

  int httpCode = _http.GET();

  if (httpCode > 0) {
    String payload = _http.getString();

    DeserializationError error = deserializeJson(response.data, payload);
    if (!error) {
      response.code = response.data["code"] | -1;
      response.message = response.data["message"] | "";
      response.success = (response.code == 0);
    } else {
      response.message = "JSON parse error";
    }
  } else {
    response.message = "HTTP error: " + String(httpCode);
  }

  _http.end();
  return response;
}

RegisterResult APIClient::registerDevice(const String &deviceName) {
  RegisterResult result;
  result.success = false;

  JsonDocument doc;
  doc["mac_address"] = _macAddress;
  if (deviceName.length() > 0) {
    doc["device_name"] = deviceName;
  }

  String jsonBody;
  serializeJson(doc, jsonBody);

  APIResponse resp = doPost("/api/meeting-device/register", jsonBody);

  if (resp.success) {
    result.success = true;
    result.bindCode = resp.data["data"]["bind_code"] | "";
    result.deviceId = resp.data["data"]["device_id"] | "";
    Serial.printf("[API] Register success, bind code: %s\n",
                  result.bindCode.c_str());
  } else {
    Serial.printf("[API] Register failed: %s\n", resp.message.c_str());
  }

  return result;
}

UploadResult APIClient::uploadAudio(const uint8_t *audioData, size_t dataLength,
                                    const String &filename,
                                    bool enableSummary) {
  UploadResult result;
  result.success = false;

  String url = _baseUrl + "/api/meeting-device/upload-audio";
  _http.begin(url);

  // Create multipart form data boundary
  String boundary = "----ESP32FormBoundary";
  _http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);

  // Build multipart body
  String bodyStart = "";
  bodyStart += "--" + boundary + "\r\n";
  bodyStart += "Content-Disposition: form-data; name=\"mac_address\"\r\n\r\n";
  bodyStart += _macAddress + "\r\n";

  bodyStart += "--" + boundary + "\r\n";
  bodyStart +=
      "Content-Disposition: form-data; name=\"enable_summary\"\r\n\r\n";
  bodyStart += (enableSummary ? "true" : "false");
  bodyStart += "\r\n";

  bodyStart += "--" + boundary + "\r\n";
  bodyStart +=
      "Content-Disposition: form-data; name=\"audio_file\"; filename=\"" +
      filename + "\"\r\n";
  bodyStart += "Content-Type: audio/wav\r\n\r\n";

  String bodyEnd = "\r\n--" + boundary + "--\r\n";

  // Calculate total length
  size_t totalLength = bodyStart.length() + dataLength + bodyEnd.length();

  // Create combined buffer
  uint8_t *fullBody = (uint8_t *)malloc(totalLength);
  if (!fullBody) {
    result.status = "Memory allocation failed";
    return result;
  }

  memcpy(fullBody, bodyStart.c_str(), bodyStart.length());
  memcpy(fullBody + bodyStart.length(), audioData, dataLength);
  memcpy(fullBody + bodyStart.length() + dataLength, bodyEnd.c_str(),
         bodyEnd.length());

  int httpCode = _http.POST(fullBody, totalLength);
  free(fullBody);

  if (httpCode > 0) {
    String payload = _http.getString();
    JsonDocument doc;

    if (!deserializeJson(doc, payload)) {
      int code = doc["code"] | -1;
      if (code == 0) {
        result.success = true;
        result.taskId = doc["data"]["task_id"] | "";
        result.status = doc["data"]["status"] | "pending";
        Serial.printf("[API] Upload success, task ID: %s\n",
                      result.taskId.c_str());
      } else {
        result.status = doc["message"] | "Unknown error";
      }
    }
  } else {
    result.status = "HTTP error: " + String(httpCode);
  }

  _http.end();
  return result;
}

MeetingResult APIClient::getResult(const String &taskId) {
  MeetingResult result;
  result.success = false;
  result.taskId = taskId;

  String endpoint = "/api/meeting-device/result/" + taskId;
  APIResponse resp = doGet(endpoint);

  if (resp.success) {
    result.success = true;
    result.status = resp.data["data"]["status"] | "unknown";
    result.transcript = resp.data["data"]["transcript"] | "";
    result.meetingSummary = resp.data["data"]["meeting_summary"] | "";
    result.errorMessage = resp.data["data"]["error_message"] | "";
  } else {
    result.errorMessage = resp.message;
  }

  return result;
}

bool APIClient::sendHeartbeat() {
  JsonDocument doc;
  doc["mac_address"] = _macAddress;
  doc["status"] = "online";

  if (_localIp.length() > 0) {
    doc["local_ip"] = _localIp;
    doc["lan_ip"] = _localIp; // Compatibility with older backend fields.
  }
  if (_localHost.length() > 0) {
    doc["local_host"] = _localHost;
  }

  String jsonBody;
  serializeJson(doc, jsonBody);

  APIResponse resp = doPost("/api/meeting-device/heartbeat", jsonBody);
  return resp.success;
}

bool APIClient::checkStatus() {
  String endpoint = "/api/meeting-device/status?mac_address=" + _macAddress;
  APIResponse resp = doGet(endpoint);

  if (resp.success) {
    return resp.data["data"]["registered"] | false;
  }
  return false;
}

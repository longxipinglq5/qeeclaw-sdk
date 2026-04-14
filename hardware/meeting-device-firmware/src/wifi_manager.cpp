/**
 * ReSpeaker XVF3800 Meeting Device - WiFi Manager Implementation
 */

#include "wifi_manager.h"

WiFiManager::WiFiManager() : _lastReconnectAttempt(0) {}

void WiFiManager::begin(const char* ssid, const char* password) {
    _ssid = String(ssid);
    _password = String(password);
    
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
}

bool WiFiManager::connectFromStorage() {
    prefs.begin("wifi_config", true);
    String storedSSID = prefs.getString("ssid", "");
    String storedPwd = prefs.getString("password", "");
    prefs.end();
    
    if (storedSSID.length() > 0) {
        begin(storedSSID.c_str(), storedPwd.c_str());
        return connect();
    }
    return false;
}

bool WiFiManager::connect(unsigned long timeout_ms) {
    if (_ssid.length() == 0) {
        Serial.println("[WiFi] No SSID configured");
        return false;
    }
    
    Serial.printf("[WiFi] Connecting to %s", _ssid.c_str());
    WiFi.begin(_ssid.c_str(), _password.c_str());
    
    unsigned long startTime = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - startTime) < timeout_ms) {
        delay(500);
        Serial.print(".");
    }
    Serial.println();
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("[WiFi] Connected! IP: %s\n", getLocalIP().c_str());
        Serial.printf("[WiFi] MAC: %s\n", getMacAddress().c_str());
        return true;
    }
    
    Serial.println("[WiFi] Connection failed");
    return false;
}

bool WiFiManager::isConnected() {
    return WiFi.status() == WL_CONNECTED;
}

String WiFiManager::getLocalIP() {
    return WiFi.localIP().toString();
}

String WiFiManager::getMacAddress() {
    return WiFi.macAddress();
}

void WiFiManager::saveConfig(const char* ssid, const char* password) {
    prefs.begin("wifi_config", false);
    prefs.putString("ssid", ssid);
    prefs.putString("password", password);
    prefs.end();
    
    _ssid = String(ssid);
    _password = String(password);
}

void WiFiManager::clearConfig() {
    prefs.begin("wifi_config", false);
    prefs.clear();
    prefs.end();
}

void WiFiManager::loop() {
    if (!isConnected() && _ssid.length() > 0) {
        unsigned long now = millis();
        if (now - _lastReconnectAttempt > RECONNECT_INTERVAL) {
            _lastReconnectAttempt = now;
            Serial.println("[WiFi] Attempting to reconnect...");
            connect(10000);
        }
    }
}

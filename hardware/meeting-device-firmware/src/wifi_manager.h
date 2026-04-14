/**
 * ReSpeaker XVF3800 Meeting Device - WiFi Manager
 * 
 * WiFi 连接管理模块，支持配置存储和自动重连
 */

#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <WiFi.h>
#include <Preferences.h>

class WiFiManager {
public:
    WiFiManager();
    
    /**
     * 初始化 WiFi 管理器
     * @param ssid WiFi 名称
     * @param password WiFi 密码
     */
    void begin(const char* ssid, const char* password);
    
    /**
     * 从存储加载并连接 WiFi
     * @return 是否成功连接
     */
    bool connectFromStorage();
    
    /**
     * 连接 WiFi
     * @param timeout_ms 连接超时（毫秒）
     * @return 是否成功连接
     */
    bool connect(unsigned long timeout_ms = 30000);
    
    /**
     * 检查 WiFi 是否已连接
     */
    bool isConnected();
    
    /**
     * 获取本机 IP 地址
     */
    String getLocalIP();
    
    /**
     * 获取 MAC 地址
     */
    String getMacAddress();
    
    /**
     * 保存 WiFi 配置到存储
     */
    void saveConfig(const char* ssid, const char* password);
    
    /**
     * 清除存储的 WiFi 配置
     */
    void clearConfig();
    
    /**
     * 处理 WiFi 事件（在 loop 中调用）
     */
    void loop();

private:
    Preferences prefs;
    String _ssid;
    String _password;
    unsigned long _lastReconnectAttempt;
    static const unsigned long RECONNECT_INTERVAL = 30000;
};

#endif // WIFI_MANAGER_H

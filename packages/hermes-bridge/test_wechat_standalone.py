"""
test_wechat_standalone.py
模拟局域网内微信协议抓包工具 (Wechaty / Ipad Protocol) 将数据发送至 QeeClaw 新构建的微信个人通道。
"""
import urllib.request
import urllib.error
import json

URL = "http://127.0.0.1:21747/api/wechat/webhook"

def test_wechat_webhook():
    test_payload = {
        "event_id": "wx_msg_102841",
        "message_type": "text",
        "toUser": "wxid_qeeclaw_bot",
        "fromUser": "wxid_user_test123",
        "text": "你好，能告诉我你的名字吗？我是刚刚接入 QeeClaw 微信个人通道的用户！"
    }
    encoded_data = json.dumps(test_payload).encode('utf-8')
    req = urllib.request.Request(URL, data=encoded_data, method="POST")
    req.add_header("Content-Type", "application/json")
    
    print(f"[{test_payload['fromUser']} -> {test_payload['toUser']}] 発送消息: {test_payload['text']}")
    try:
        with urllib.request.urlopen(req, timeout=30) as f:
            response = json.loads(f.read().decode('utf-8'))
            print("==== 收到大模型微信被动回复 ====")
            print(json.dumps(response, indent=2, ensure_ascii=False))
            if response.get("ok"):
                print("\n✅ 测试通过：微信通道联调成功！大模型已经可以接管局域网路由的数据！")
    except urllib.error.URLError as e:
        print(f"❌ 请求失败, 请确保 QeeClaw Bridge Server 已经启动在 127.0.0.1:21747 ! 错误: {e}")

if __name__ == "__main__":
    test_wechat_webhook()

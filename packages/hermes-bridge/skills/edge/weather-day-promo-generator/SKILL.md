---
name: weather-day-promo-generator
description: 为雨天、降温、高温、淡季和工作日低峰生成当天可发的到店促销话术。
category: store
icon: "雨"
input_schema:
  - key: weather_context
    label: 天气/低峰情况
    type: select
    required: true
    options: ["雨天人少", "突然降温", "高温天", "工作日低峰", "淡季客流少"]
  - key: target_item
    label: 想推项目
    type: textarea
    required: true
  - key: offer_boundary
    label: 优惠边界
    type: text
    required: true
  - key: send_channel
    label: 发送渠道
    type: select
    required: false
    options: ["朋友圈", "微信群", "门口小黑板", "朋友圈+社群"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 天气低峰促销助手

生成轻量促销内容：朋友圈文案、社群文案、小黑板文案、员工话术。

## 调用时机
当用户需要为雨天、降温、高温、淡季和工作日低峰生成当天可发的到店促销话术时调用。

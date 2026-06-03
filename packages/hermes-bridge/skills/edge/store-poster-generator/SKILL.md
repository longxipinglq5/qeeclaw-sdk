---
name: store-poster-generator
description: 为开业、会员日、新品、节假日和淡季引流直接生成海报预览图、海报文案和发布提醒。
category: store
icon: "报"
input_schema:
  - key: event_theme
    label: 活动主题
    type: text
    required: true
  - key: offer
    label: 优惠内容
    type: textarea
    required: true
  - key: store_info
    label: 门店信息
    type: textarea
    required: true
  - key: style
    label: 海报风格
    type: select
    required: false
    options: ["门店促销清晰版", "小红书封面感", "节日热闹版", "高级简洁版"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 门店海报生成器

生成海报方案：海报文案、卖点、版式建议、生图提示词、发布注意事项。

## 调用时机
当用户需要为开业、会员日、新品、节假日和淡季引流直接生成海报预览图、海报文案和发布提醒时调用。

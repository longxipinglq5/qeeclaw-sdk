---
name: old-customer-recall-generator
description: 为多久没来的老客户生成微信私聊、群发、朋友圈和短信召回文案。
category: store
icon: "召"
input_schema:
  - key: customer_type
    label: 客户类型
    type: text
    required: true
  - key: inactive_period
    label: 多久没来
    type: text
    required: true
  - key: offer
    label: 可给优惠
    type: text
    required: true
  - key: store_context
    label: 门店近况
    type: textarea
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 老客户召回文案生成器

生成召回文案：微信私聊版、群发版、朋友圈版、短信短版、跟进建议。不制造焦虑。

## 调用时机
当用户需要为多久没来的老客户生成微信私聊、群发、朋友圈和短信召回文案时调用。

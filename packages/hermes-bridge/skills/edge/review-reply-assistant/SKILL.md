---
name: review-reply-assistant
description: 根据好评、中评、差评生成公开回复、私信回复和补救动作。
category: store
icon: "评"
input_schema:
  - key: review_type
    label: 评价类型
    type: select
    required: true
    options: ["好评", "中评", "差评"]
  - key: review_content
    label: 评价内容
    type: textarea
    required: true
  - key: store_attitude
    label: 回复态度
    type: select
    required: true
    options: ["诚恳道歉", "解释但不争辩", "感谢并邀请再来"]
  - key: compensation
    label: 补偿方式
    type: text
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 客户评价回复助手

生成评价回复：公开回复、私信回复、补救动作、风险提醒。不承诺法律责任。

## 调用时机
当用户需要根据好评、中评、差评生成公开回复、私信回复和补救动作时调用。

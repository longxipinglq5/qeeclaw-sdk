---
name: after-sales-comfort-assistant
description: 为服务延迟、效果不满意、缺货、排队久和投诉苗头生成安抚、补救和员工处理话术。
category: store
icon: "安"
input_schema:
  - key: issue
    label: 问题情况
    type: textarea
    required: true
  - key: customer_mood
    label: 客户情绪
    type: select
    required: true
    options: ["只是有点不满", "比较生气", "已经投诉/差评", "还没投诉但有苗头"]
  - key: repair_offer
    label: 可提供补救
    type: textarea
    required: true
  - key: public_or_private
    label: 沟通场景
    type: select
    required: false
    options: ["微信私聊", "平台评价下回复", "电话沟通", "员工现场处理"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 售后安抚助手

生成售后话术：公开回应、私信安抚、补救方案、员工话术、风险边界。

## 调用时机
当用户需要为服务延迟、效果不满意、缺货、排队久和投诉苗头生成安抚、补救和员工处理话术时调用。

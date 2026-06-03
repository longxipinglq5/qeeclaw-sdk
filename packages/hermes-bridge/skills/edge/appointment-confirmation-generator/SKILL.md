---
name: appointment-confirmation-generator
description: 为到店预约生成确认、改期、迟到提醒、准备事项和温和催确认话术。
category: store
icon: "约"
input_schema:
  - key: service_item
    label: 预约项目
    type: text
    required: true
  - key: appointment_time
    label: 预约时间
    type: text
    required: true
  - key: preparation_notes
    label: 注意事项
    type: textarea
    required: false
  - key: situation
    label: 当前情况
    type: select
    required: false
    options: ["确认预约", "客户想改期", "客户可能迟到", "需要催客户确认"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 预约确认助手

生成预约话术：确认、改期、迟到提醒、准备事项、到店引导。

## 调用时机
当用户需要为到店预约生成确认、改期、迟到提醒、准备事项和温和催确认话术时调用。

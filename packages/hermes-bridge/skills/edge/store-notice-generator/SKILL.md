---
name: store-notice-generator
description: 为营业时间变化、临时闭店、搬店、停水停电、上新和节假日安排生成通知。
category: store
icon: "告"
input_schema:
  - key: notice_type
    label: 通知类型
    type: select
    required: true
    options: ["营业时间调整", "临时闭店/店休", "搬店/换地址", "停水停电/设备维护", "新品/新项目到店", "节假日安排"]
  - key: change_detail
    label: 具体变化
    type: textarea
    required: true
  - key: affected_time
    label: 影响时间
    type: text
    required: true
  - key: customer_action
    label: 客户需要怎么做
    type: text
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 门店通知生成器

生成门店通知：朋友圈版、社群版、门店贴纸版、私信短版、注意事项。

## 调用时机
当用户需要为营业时间变化、临时闭店、搬店、停水停电、上新和节假日安排生成通知时调用。

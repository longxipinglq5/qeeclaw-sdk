---
name: batch-greeting-generator
description: 为节日、活动或日常维护生成多条客户群发文案。
category: sales
icon: "🎉"
input_schema:
  - key: occasion
    label: 场景
    type: select
    required: true
    options: ["节日问候", "活动通知", "新品上市", "日常关怀", "感谢回馈"]
  - key: occasion_detail
    label: 具体说明
    type: text
    required: true
  - key: customer_type
    label: 客户类型
    type: select
    required: false
    options: ["所有客户", "VIP老客户", "潜在新客户", "合作伙伴"]
  - key: product_hint
    label: 想顺带提的产品或服务
    type: text
    required: false
  - key: tone
    label: 风格
    type: select
    required: false
    options: ["温暖走心", "轻松幽默", "简短商务"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 客户群发文案生成器

生成 3 条微信群发文案：走心版、轻松版、极简版。称呼用「X总」「各位经营者」。

## 调用时机
当用户需要为节日、活动或日常维护生成多条客户群发文案时调用。

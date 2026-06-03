---
name: inventory-clearance-planner
description: 为临期、换季、滞销和过量库存生成清库存活动、朋友圈、社群和海报文案。
category: store
icon: "清"
input_schema:
  - key: inventory_items
    label: 库存品/项目
    type: textarea
    required: true
  - key: pressure
    label: 库存压力
    type: text
    required: true
  - key: discount_boundary
    label: 可接受优惠
    type: textarea
    required: true
  - key: brand_tone
    label: 希望的感觉
    type: select
    required: false
    options: ["不显廉价", "福利清仓", "老客专享", "限时快闪"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 清库存活动助手

生成清库存方案：活动机制、朋友圈文案、社群话术、海报文案、风险提醒。

## 调用时机
当用户需要为临期、换季、滞销和过量库存生成清库存活动、朋友圈、社群和海报文案时调用。

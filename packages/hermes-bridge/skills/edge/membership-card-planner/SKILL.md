---
name: membership-card-planner
description: 为储值卡、次卡、月卡和权益卡生成卡项命名、权益、规则、话术和风险提醒。
category: store
icon: "卡"
input_schema:
  - key: store_items
    label: 门店项目
    type: textarea
    required: true
  - key: card_goal
    label: 会员卡目标
    type: select
    required: true
    options: ["提升复购", "提前回款", "推广新品/新项目", "稳定老客"]
  - key: price_benefits
    label: 价格/权益想法
    type: textarea
    required: true
  - key: constraints
    label: 限制条件
    type: textarea
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 会员卡设计助手

设计会员卡方案：卡项设计、权益规则、销售话术、海报文案、风险提醒。

## 调用时机
当用户需要为储值卡、次卡、月卡和权益卡生成卡项命名、权益、规则、话术和风险提醒时调用。

---
name: daily-store-review-assistant
description: 把今天营业额、客流、热卖品和问题整理成 3 分钟门店复盘。
category: store
icon: "复"
input_schema:
  - key: revenue
    label: 今天营业额
    type: text
    required: true
  - key: traffic
    label: 今天客流
    type: text
    required: true
  - key: top_items
    label: 卖得好的品/项目
    type: textarea
    required: true
  - key: problems
    label: 今天的问题
    type: textarea
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 每日经营复盘助手

生成每日复盘：今日总结、明日3个动作、库存提醒、人员提醒、轻量营销动作。

## 调用时机
当用户需要把今天营业额、客流、热卖品和问题整理成 3 分钟门店复盘时调用。

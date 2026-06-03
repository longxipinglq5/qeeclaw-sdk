---
name: group-buy-package-generator
description: 为美团、抖音来客等平台准备团购标题、套餐内容、使用规则和利润风险提醒。
category: store
icon: "团"
input_schema:
  - key: store_project
    label: 门店项目
    type: textarea
    required: true
    placeholder: "例如：火锅双人餐；奶茶新品券；猫咪洗护；儿童体验课；空调深度清洗"
  - key: average_price
    label: 原客单价/成本
    type: text
    required: true
    placeholder: "例如：平时客单 88 元，食材成本约 35 元"
  - key: goal
    label: 套餐目标
    type: select
    required: true
    placeholder: ""
    options: [拉新到店, 促进复购, 清库存/淡季引流, 推广新品]
  - key: cost_notes
    label: 不能踩的坑
    type: textarea
    required: false
    placeholder: "选填：不能低于多少、周末是否可用、哪些项目不参加"
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 团购套餐生成器

生成适合中国本地生活平台手动录入的团购方案。包含：1. titles 5 个美团/抖音团购标题；2. package_content 套餐内容和建议标价；3. usage_rules 使用规则、预约、节假日和不可叠加说明；4. verification_notes 核销提醒和到店转化动作；5. profit_risks 利润风险和需要老板确认的价格底线。不要声称已上架、已投放、已自动核销，不要建议明显亏损或违法诱导的规则。

## 调用时机
门店需要在美团、抖音来客等平台上线团购套餐，或为本地生活平台准备团购方案时使用。

## 注意事项
- 不要声称已上架、已投放、已自动核销
- 不要建议明显亏损或违法诱导的规则
- 利润风险需提醒老板确认价格底线

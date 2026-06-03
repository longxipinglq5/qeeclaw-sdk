---
name: store-menu-generator
description: 把门店产品、项目和价格整理成清晰菜单、套餐组合和平台可用版本。
category: store
icon: "单"
input_schema:
  - key: store_type
    label: 门店类型
    type: select
    required: true
    placeholder: ""
    options: [餐饮小店, 茶饮/咖啡, 美甲/美容/美发, 宠物洗护, 维修/清洗服务, 零售小店]
  - key: items
    label: 产品/项目清单
    type: textarea
    required: true
    placeholder: "一行一个，例如：招牌牛肉饭 28 元；双人美甲护理 168 元；宠物洗护小型犬 88 元"
  - key: price_notes
    label: 价格/成本备注
    type: textarea
    required: false
    placeholder: "选填：成本、毛利、想主推的项目、不能打折的项目"
  - key: use_case
    label: 主要用途
    type: select
    required: false
    placeholder: ""
    options: [门店贴墙, 朋友圈发布, 大众点评/美团资料, 员工点单说明]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 菜单/价目表生成器

生成门店老板可直接复制的菜单/价目表。包含：1. menu_board 清晰菜单，按品类分组并保留价格；2. bundle_sets 2-4 个不容易亏钱的套餐组合；3. signature_recommendations 招牌推荐和主推理由；4. platform_version 适合朋友圈/大众点评/美团资料的短版；5. price_tips 价格和利润风险提醒。不要编造不存在的产品、资质、销量或平台数据。

## 调用时机
门店需要整理产品/项目清单、制作价目表、准备平台展示菜单或设计套餐组合时使用。

## 注意事项
- 不要编造不存在的产品、资质、销量或平台数据
- 套餐组合要考虑成本，提供不容易亏钱的方案
- 价格和利润风险需明确提醒

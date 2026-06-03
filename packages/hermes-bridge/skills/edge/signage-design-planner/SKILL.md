---
name: signage-design-planner
description: 生成门头招牌、橱窗字、店内指示牌的内容、可读性和制作建议。
category: design
icon: "招"
input_schema:
  - key: shop_brand
    label: 店名/品牌
    type: text
    required: true
  - key: business_type
    label: 门店类型
    type: text
    required: true
  - key: size_location
    label: 制作位置/尺寸
    type: textarea
    required: true
  - key: must_show
    label: 必须出现的信息
    type: textarea
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 门头/招牌设计助手

生成招牌方案：主文案、版式、材质建议、可读性检查、制作清单。

## 调用时机
当用户需要生成门头招牌、橱窗字、店内指示牌的内容、可读性和制作建议时调用。

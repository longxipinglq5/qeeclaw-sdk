---
name: brand-kit-generator
description: 生成品牌关键词、颜色、字体气质、基础物料规范和给文印店/设计师的交付说明。
category: design
icon: "牌"
input_schema:
  - key: brand_positioning
    label: 品牌定位
    type: textarea
    required: true
  - key: audience_industry
    label: 行业/客户
    type: textarea
    required: true
  - key: visual_preferences
    label: 已有视觉偏好
    type: textarea
    required: false
  - key: materials_needed
    label: 优先要做的物料
    type: textarea
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 品牌基础套件生成器

生成品牌套件：品牌关键词、色彩方案、字体方向、物料规则、交付清单、风险提醒。

## 调用时机
当用户需要生成品牌关键词、颜色、字体气质、基础物料规范和给文印店/设计师的交付说明时调用。

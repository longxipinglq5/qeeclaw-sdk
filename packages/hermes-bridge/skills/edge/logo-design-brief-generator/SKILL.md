---
name: logo-design-brief-generator
description: 生成Logo设计方向、图形概念、颜色字体建议和可交付给设计师的brief。
category: design
icon: "标"
input_schema:
  - key: brand_name
    label: 品牌名称
    type: text
    required: true
  - key: brand_positioning
    label: 行业与定位
    type: textarea
    required: true
  - key: style_preference
    label: 喜欢/不喜欢的风格
    type: textarea
    required: false
  - key: usage_scene
    label: 主要使用场景
    type: select
    required: false
    options: ["门头招牌", "名片/宣传单", "小红书/朋友圈头像", "包装/贴纸", "全套品牌物料"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# Logo设计Brief助手

生成Logo设计brief：设计方向、图形元素、颜色字体、交付清单、商标提醒。

## 调用时机
当用户需要生成Logo设计方向、图形概念、颜色字体建议和可交付给设计师的brief时调用。

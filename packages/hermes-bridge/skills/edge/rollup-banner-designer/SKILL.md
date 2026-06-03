---
name: rollup-banner-designer
description: 生成易拉宝、X展架、展会立牌的竖版内容层级、视觉方案和印刷规格。
category: design
icon: "展"
input_schema:
  - key: display_scene
    label: 展示场景
    type: select
    required: true
    options: ["展会/路演", "门店入口", "活动现场", "公司前台", "招商/招聘会"]
  - key: core_message
    label: 核心信息
    type: textarea
    required: true
  - key: size_position
    label: 尺寸/摆放位置
    type: text
    required: false
  - key: visual_style
    label: 视觉风格
    type: select
    required: false
    options: ["商务专业", "门店促销", "科技简洁", "活动热闹"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 易拉宝/展架设计助手

生成竖版展示物料方案：信息层级、文案、版式、印刷规格、现场摆放清单。

## 调用时机
当用户需要生成易拉宝、X展架、展会立牌的竖版内容层级、视觉方案和印刷规格时调用。

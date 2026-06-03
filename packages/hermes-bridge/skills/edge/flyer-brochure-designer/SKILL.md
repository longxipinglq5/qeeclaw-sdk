---
name: flyer-brochure-designer
description: 为A4单页、三折页、DM单和产品宣传页生成内容结构、版式和印刷提醒。
category: design
icon: "折"
input_schema:
  - key: purpose
    label: 宣传目的
    type: select
    required: true
    options: ["企业介绍", "产品/服务介绍", "活动促销", "招商/合作", "门店派发"]
  - key: content_materials
    label: 产品/活动资料
    type: textarea
    required: true
  - key: distribution_scene
    label: 发放场景
    type: text
    required: true
  - key: format_size
    label: 物料形式
    type: select
    required: false
    options: ["A4单页", "A5宣传单", "三折页", "双面DM单"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 宣传单/折页设计助手

生成宣传单/折页方案：页面结构、标题、各模块文案、版式建议、印刷清单。

## 调用时机
当用户需要为A4单页、三折页、DM单和产品宣传页生成内容结构、版式和印刷提醒时调用。

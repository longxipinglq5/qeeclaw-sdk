---
name: customer-followup-generator
description: 根据客户背景、需求和异议生成微信跟进话术与下一步推进建议。
category: sales
icon: "客"
input_schema:
  - key: customer
    label: 客户背景
    type: textarea
    required: true
    placeholder: "客户是谁、公司情况、当前阶段"
  - key: need
    label: 客户需求
    type: textarea
    required: false
    placeholder: "客户关心什么、预算、目标"
  - key: objection
    label: 客户顾虑
    type: textarea
    required: false
    placeholder: "例如：担心贵、担心复杂、担心数据安全"
  - key: style
    label: 跟进风格
    type: select
    required: false
    placeholder: ""
    options: ["直接但不施压", "专业顾问式", "老朋友式"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 客户跟进话术生成器

输出：客户需求摘要、主要异议、80 字以内微信跟进话术、推荐发送时间、下一步成交推进建议。

## 调用时机
当销售或经营者需要根据某个客户的背景、需求和顾虑，生成一段微信跟进话术和下一步行动建议时使用。适用于私域销售场景中的客户跟进环节。

## 注意事项
- 跟进话术控制在 80 字以内，适合微信直接发送
- 需要同时输出客户需求摘要和主要异议分析
- 给出推荐发送时间建议
- 提供下一步成交推进建议

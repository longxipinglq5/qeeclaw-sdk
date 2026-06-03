---
name: quotation-generator
description: 根据客户需求和产品信息生成一份专业报价方案。
category: sales
icon: "💰"
input_schema:
  - key: client_name
    label: 客户名称
    type: text
    required: true
  - key: project_desc
    label: 项目或需求描述
    type: textarea
    required: true
  - key: products
    label: 产品/服务和价格
    type: textarea
    required: true
  - key: validity
    label: 报价有效期
    type: select
    required: false
    options: ["7天", "15天", "30天"]
  - key: tone
    label: 报价风格
    type: select
    required: false
    options: ["正式商务", "简洁直接", "温和友好"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 报价方案生成器

生成中文报价方案。包含：报价抬头、明细表、合计、付款方式与交付条款、结尾话术。

## 调用时机
当用户需要根据客户需求和产品信息生成一份专业报价方案时调用。

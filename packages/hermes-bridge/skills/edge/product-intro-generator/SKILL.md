---
name: product-intro-generator
description: 把零散的产品信息整理成清晰的产品介绍。
category: content
icon: "📦"
input_schema:
  - key: product_name
    label: 产品/服务名称
    type: text
    required: true
    placeholder: "例如：半人马AI数字员工系统"
  - key: raw_info
    label: 你知道的产品信息
    type: textarea
    required: true
    placeholder: "随便写，功能、价格、优势、客户反馈都行，我来帮你整理"
  - key: target_customer
    label: 主要卖给谁
    type: text
    required: false
    placeholder: "例如：餐饮经营者 / 电商卖家 / 30-45岁女性"
  - key: format
    label: 输出用途
    type: select
    required: false
    placeholder: ""
    options: ["发给客户", "官网产品页", "PPT内容", "朋友圈种草"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 产品介绍生成器

请根据用户提供的零散信息整理产品介绍：1. 一句话版（10-20字，说清是什么+给谁+核心价值）；2. 30秒版（100字，适合口头或微信）；3. 完整版（300-500字，痛点→方案→优势→案例→行动）；4. 卖点清单（3-5条，每条一句话突出差异化）；5. FAQ（3个最可能被问的问题+简洁回答）。用客户听得懂的话，不用技术术语，不夸大承诺。

## 调用时机

当用户有好的产品或服务但说不清楚时调用，3分钟出一份专业的产品说明。适用于发给客户介绍、官网产品页、PPT内容、朋友圈种草等场景。

## 注意事项

- 用客户听得懂的话，不用技术术语
- 不夸大承诺
- 一句话版要在 10-20 字内说清核心价值
- 完整版按痛点→方案→优势→案例→行动的结构组织
- FAQ 要覆盖最可能被问的问题

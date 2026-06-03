---
name: professional-service-proposal-generator
description: 为财税、法务、咨询等企业服务生成服务方案、交付边界、报价逻辑和成交话术。
category: sales
icon: "案"
input_schema:
  - key: service_type
    label: 服务类型
    type: select
    required: true
    options: ["财税/代账服务", "法律顾问服务", "企业咨询服务", "AI工具定制服务", "其他专业服务"]
  - key: target_client
    label: 目标客户
    type: textarea
    required: true
  - key: service_scope
    label: 服务内容与边界
    type: textarea
    required: true
  - key: proof
    label: 案例或信任证明
    type: textarea
    required: false
  - key: pricing_hint
    label: 报价或套餐线索
    type: text
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 企业服务方案生成器

输出专业服务销售方案：定位、痛点诊断、服务模块、流程边界、报价逻辑、信任证明、成交话术。

## 调用时机
当用户需要为财税、法务、咨询等企业服务生成服务方案、交付边界、报价逻辑和成交话术时调用。

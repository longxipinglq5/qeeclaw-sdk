---
name: tax-client-file-checklist-generator
description: 为财税、代账客户生成本月资料补交清单、缺失项提醒、催收话术和归档建议。
category: knowledge
icon: "税"
input_schema:
  - key: client_type
    label: 客户类型
    type: select
    required: true
    options: ["一般纳税人企业", "小规模纳税人企业", "个体工商户", "新设立公司"]
  - key: service_period
    label: 服务周期
    type: text
    required: true
  - key: business_context
    label: 客户业务背景
    type: textarea
    required: false
  - key: known_missing
    label: 已知缺失资料
    type: textarea
    required: false
  - key: communication_tone
    label: 催收语气
    type: select
    required: false
    options: ["专业清晰", "温和提醒", "紧急明确"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 财税客户资料清单生成器

输出客户资料清单：必收资料、缺失项、补交清单、催收话术、归档建议、风险提醒。

## 调用时机
当用户需要为财税、代账客户生成本月资料补交清单、缺失项提醒、催收话术和归档建议时调用。

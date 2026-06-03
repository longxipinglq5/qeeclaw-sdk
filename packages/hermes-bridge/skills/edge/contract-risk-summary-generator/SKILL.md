---
name: contract-risk-summary-generator
description: 根据合同类型、条款片段和业务目标生成风险摘要、修改建议、谈判要点和律师复核项。
category: knowledge
icon: "约"
input_schema:
  - key: contract_type
    label: 合同类型
    type: select
    required: true
    options: ["采购/销售合同", "服务合同", "劳动/劳务协议", "合作/代理协议", "租赁合同", "其他合同"]
  - key: contract_excerpt
    label: 合同条款或摘要
    type: textarea
    required: true
  - key: business_goal
    label: 业务目标
    type: textarea
    required: false
  - key: risk_focus
    label: 重点关注风险
    type: textarea
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 合同风险摘要生成器

输出合同风险摘要：主要风险、条款问题和风险等级、修改建议、沟通话术、签署前检查、律师复核项。

## 调用时机
当用户需要根据合同类型、条款片段和业务目标生成风险摘要、修改建议、谈判要点和律师复核项时调用。

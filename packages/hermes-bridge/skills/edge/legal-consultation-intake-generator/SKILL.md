---
name: legal-consultation-intake-generator
description: 把客户法律咨询整理成案情摘要、关键事实、证据清单、追问问题和委托风险。
category: knowledge
icon: "法"
input_schema:
  - key: matter_type
    label: 咨询类型
    type: select
    required: true
    options: ["合同纠纷", "劳动用工", "公司治理/股权", "知识产权", "常年法律顾问", "其他法律咨询"]
  - key: client_description
    label: 客户原始描述
    type: textarea
    required: true
  - key: counterpart
    label: 相对方/相关主体
    type: text
    required: false
  - key: deadline
    label: 关键时间节点
    type: textarea
    required: false
  - key: goal
    label: 客户想达到的结果
    type: text
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 法律咨询接待表生成器

输出法律咨询接待表：案情摘要、关键事实、缺失事实和追问、证据清单、法律关系、委托风险。

## 调用时机
当用户需要把客户法律咨询整理成案情摘要、关键事实、证据清单、追问问题和委托风险时调用。

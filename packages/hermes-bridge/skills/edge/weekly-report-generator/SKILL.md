---
name: weekly-report-generator
description: 把这周做的事情整理成清晰的工作总结。
category: sales
icon: "📋"
input_schema:
  - key: work_done
    label: 这周做了什么
    type: textarea
    required: true
  - key: problems
    label: 遇到的问题或卡点
    type: textarea
    required: false
  - key: next_week
    label: 下周计划
    type: textarea
    required: false
  - key: audience
    label: 给谁看
    type: select
    required: false
    options: ["给自己", "给合伙人", "给投资人", "给团队"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 周报总结生成器

整理周报：本周总结、关键成果、问题与对策、下周计划、一句话版。根据给谁看调整风格。

## 调用时机
当用户需要把这周做的事情整理成清晰的工作总结时调用。

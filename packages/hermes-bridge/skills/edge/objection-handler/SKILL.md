---
name: objection-handler
description: 客户说「太贵了」「再看看」，帮你生成应对话术。
category: sales
icon: "🛡️"
input_schema:
  - key: objection
    label: 客户说了什么
    type: text
    required: true
  - key: product
    label: 你卖的是什么
    type: text
    required: true
  - key: advantage
    label: 你的核心优势
    type: textarea
    required: false
  - key: context
    label: 客户阶段
    type: select
    required: false
    options: ["初次咨询", "深入沟通", "已报价待签", "老客户续费"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 客户异议应对生成器

分析客户异议并生成 3 种回复话术：直接回复、案例回复、反问引导。不要怼客户不要贬低竞品。

## 调用时机
当用户需要客户说「太贵了」「再看看」，帮你生成应对话术时调用。

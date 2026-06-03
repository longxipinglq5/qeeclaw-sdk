---
name: faq-builder
description: 把产品资料和客户常问问题整理成可放进知识库的 FAQ。
category: knowledge
icon: "问"
input_schema:
  - key: productInfo
    label: 产品资料摘要
    type: textarea
    required: true
    placeholder: "粘贴产品介绍、服务流程、价格或交付说明"
    options: []
  - key: questions
    label: 客户常见问题
    type: textarea
    required: false
    placeholder: "一行一个问题，也可以粘贴聊天记录摘要"
    options: []
  - key: format
    label: 输出格式
    type: select
    required: false
    placeholder: ""
    options: ["用户能看懂", "销售可直接复制", "知识库结构化"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# FAQ 生成器

输出 8-12 条 FAQ，每条包含问题、简洁回答、适用场景和建议标签。

## 调用时机
当用户需要把产品资料、服务说明和客户常问问题整理成结构化 FAQ 时调用。适用于知识库建设、销售话术准备、客服培训等场景。

## 注意事项
- 每条 FAQ 需包含问题、简洁回答、适用场景和建议标签四个部分
- 输出数量控制在 8-12 条
- 根据输出格式调整表达方式（用户能看懂 / 销售可直接复制 / 知识库结构化）

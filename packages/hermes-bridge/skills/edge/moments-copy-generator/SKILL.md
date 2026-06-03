---
name: moments-copy-generator
description: 生成经营者口吻的朋友圈文案，适合私域触达和客户转化。
category: content
icon: "圈"
input_schema:
  - key: topic
    label: 想表达的事情
    type: textarea
    required: true
    placeholder: "例如：最近上线了本地 AI 员工一体机，想让老客户知道"
  - key: voice
    label: 经营者口吻
    type: select
    required: false
    placeholder: ""
    options: ["直接接地气", "专业可信", "轻松聊天"]
  - key: cta
    label: 结尾引导
    type: text
    required: false
    placeholder: "例如：想看的朋友私聊我"
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 朋友圈文案生成器

输出 3 个朋友圈版本：短版、故事版、转化版。每版都要自然、有经营者本人感。

## 调用时机

当用户需要在朋友圈发布内容时调用，适用于产品更新、客户案例、用户观点等私域触达场景，帮助经营者快速生成可直接发布的朋友圈文案。

## 注意事项

- 输出 3 个版本：短版、故事版、转化版
- 每版都要自然、有经营者本人感
- 语气要像经营者本人，不要像 AI 模板
- 文案要适合私域触达和客户转化

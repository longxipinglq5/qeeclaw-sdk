---
name: xiaohongshu-note-generator
description: 生成小红书标题、正文、标签、封面文案和配图提示词。
category: content
icon: "书"
input_schema:
  - key: topic
    label: 笔记主题
    type: text
    required: true
    placeholder: "例如：公司资料不想上云怎么办"
  - key: sellingPoints
    label: 产品卖点
    type: textarea
    required: false
    placeholder: "列出 2-5 个核心卖点"
  - key: tone
    label: 表达风格
    type: select
    required: false
    placeholder: ""
    options: ["经营者真实分享", "避坑清单", "干货教程"]
  - key: cta
    label: 行动引导
    type: text
    required: false
    placeholder: "例如：私聊我看 demo / 收藏备用"
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 小红书笔记生成器

输出：标题组、封面大字、正文、标签、配图提示词和结尾 CTA。不要夸张承诺，不要写成硬广。

## 调用时机

当用户需要创作小红书种草内容时调用，适用于产品推广、经验分享、避坑指南等场景，帮助企业资料包装成普通人能看懂、愿意收藏和私聊的内容。

## 注意事项

- 不要夸张承诺，不要写成硬广
- 标题、封面大字、正文、标签要完整输出
- 配图提示词要具体可执行
- 结尾 CTA 要自然引导互动

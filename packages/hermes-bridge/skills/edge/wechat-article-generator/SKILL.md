---
name: wechat-article-generator
description: 把一个主题扩展成公众号标题组、大纲、正文、摘要和朋友圈转发语。
category: content
icon: "文"
input_schema:
  - key: topic
    label: 文章主题
    type: text
    required: true
    placeholder: "例如：为什么小企业需要本地 AI 员工"
  - key: audience
    label: 目标读者
    type: text
    required: false
    placeholder: "例如：小微企业经营者、销售负责人"
  - key: goal
    label: 文章目的
    type: select
    required: false
    placeholder: ""
    options: ["获客转化", "产品教育", "客户信任"]
  - key: refs
    label: 可引用资料
    type: textarea
    required: false
    placeholder: "粘贴产品资料、案例、客户反馈或销售话术摘要"
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 公众号文章生成器

输出：1. 5 个标题；2. 文章大纲；3. 正文草稿；4. 摘要；5. 朋友圈转发语。语气要像经营者本人，不要像 AI 模板。

## 调用时机

当用户需要撰写公众号文章时调用，适用于获客转化、产品教育和客户信任建设场景，帮助用户快速产出有观点、有结构、能承接私域转化的长内容。

## 注意事项

- 语气要像经营者本人，不要像 AI 模板
- 输出要完整：标题组、大纲、正文、摘要、朋友圈转发语
- 可引用资料要融入正文，避免生硬引用

---
name: social-calendar-planner
description: 把一个营销目标拆成多平台内容主题、发布时间和素材准备清单。
category: content
icon: "排"
input_schema:
  - key: campaign
    label: 营销目标
    type: textarea
    required: true
    placeholder: "例如：推广 Centaur Edge 单人版，获取 20 个意向客户"
  - key: platforms
    label: 目标平台
    type: textarea
    required: false
    placeholder: "例如：公众号、小红书、朋友圈、视频号"
  - key: cycle
    label: 排期周期
    type: select
    required: false
    placeholder: ""
    options: ["7 天", "14 天", "30 天"]
  - key: assets
    label: 已有素材
    type: textarea
    required: false
    placeholder: "产品图、案例、客户反馈、用户观点、短视频素材等"
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 社媒内容排期应用

输出：1. 内容主线；2. 平台分工；3. 按日期排列的内容排期；4. 每条内容的标题方向、素材需求和 CTA；5. 需要火花继续生成的具体应用任务。

## 调用时机

当用户需要规划一段时间内的多平台内容发布计划时调用，帮助把内容生成从单篇草稿升级成连续运营计划。

## 注意事项

- 排期要按日期排列，清晰可执行
- 每条内容要有标题方向、素材需求和 CTA
- 要考虑不同平台的内容特点和时间节奏
- 输出需要火花继续生成的具体应用任务

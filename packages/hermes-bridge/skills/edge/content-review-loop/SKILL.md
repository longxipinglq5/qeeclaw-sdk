---
name: content-review-loop
description: 根据阅读、点赞、收藏、评论和线索数据生成复盘与下一轮选题建议。
category: review
icon: "盘"
input_schema:
  - key: platform
    label: 平台
    type: select
    required: true
    options: ["小红书", "公众号", "朋友圈"]
  - key: title
    label: 内容标题
    type: text
    required: true
  - key: metrics
    label: 表现数据
    type: textarea
    required: true
  - key: notes
    label: 补充观察
    type: textarea
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 内容复盘助手

输出：有效点、低效点、标题/卖点判断、下一轮实验、建议写入火花记忆的经验。

## 调用时机
当用户需要根据阅读、点赞、收藏、评论和线索数据生成复盘与下一轮选题建议时调用。

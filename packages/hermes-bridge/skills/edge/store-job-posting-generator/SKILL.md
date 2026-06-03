---
name: store-job-posting-generator
description: 为店员、店长、技师、老师、学徒和兼职生成 Boss 直聘、朋友圈和海报招聘文案。
category: store
icon: "招"
input_schema:
  - key: position
    label: 招聘岗位
    type: text
    required: true
  - key: salary
    label: 薪资待遇
    type: text
    required: true
  - key: work_time
    label: 工作时间
    type: text
    required: true
  - key: store_highlights
    label: 门店亮点
    type: textarea
    required: false
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 门店招聘文案生成器

生成招聘文案：Boss直聘版、朋友圈版、海报文案、面试沟通重点。

## 调用时机
当用户需要为店员、店长、技师、老师、学徒和兼职生成 Boss 直聘、朋友圈和海报招聘文案时调用。

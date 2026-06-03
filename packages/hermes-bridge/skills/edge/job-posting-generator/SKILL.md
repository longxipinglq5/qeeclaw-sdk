---
name: job-posting-generator
description: 根据岗位需求快速生成招聘文案。
category: content
icon: "👥"
input_schema:
  - key: position
    label: 招什么岗位
    type: text
    required: true
    placeholder: "例如：销售经理 / 新媒体运营 / 店长"
  - key: requirements
    label: 岗位要求
    type: textarea
    required: true
    placeholder: "简单列几条，例如：3年销售经验，会用企业微信，有客户资源优先"
  - key: company_intro
    label: 公司一句话介绍
    type: text
    required: false
    placeholder: "例如：我们是做本地AI数字员工的科技公司，团队10人"
  - key: salary
    label: 薪资范围
    type: text
    required: false
    placeholder: "例如：8-15K / 面议"
  - key: format
    label: 输出格式
    type: select
    required: false
    placeholder: ""
    options: ["Boss直聘标准版", "招聘海报文案", "朋友圈转发版"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 招聘JD生成器

请生成一份招聘启事。根据格式要求调整风格：Boss直聘=正式但不死板；海报=简短有力突出薪资；朋友圈=像朋友帮招人。岗位职责 3-5 条每条一句话。不要"有团队精神""抗压能力强"等废话。福利写具体的（双休、午餐补贴），不写"有竞争力的薪资"。

## 调用时机

当用户需要快速生成招聘文案时调用，适用于 Boss 直聘、招聘海报、朋友圈转发等格式，帮助小公司 2 分钟写出专业招聘启事。

## 注意事项

- 根据格式要求调整风格
- 岗位职责 3-5 条，每条一句话
- 不要"有团队精神""抗压能力强"等废话
- 福利写具体的，不写"有竞争力的薪资"

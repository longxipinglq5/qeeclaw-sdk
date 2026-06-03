---
name: community-activity-script-generator
description: 为门店微信群/会员群生成预热、开抢、临门一脚和结束提醒话术。
category: store
icon: "群"
input_schema:
  - key: activity_goal
    label: 活动目标
    type: text
    required: true
  - key: community_type
    label: 社群类型
    type: select
    required: true
    options: ["门店会员群", "社区邻里群", "家长群", "宠物主群", "售后服务群"]
  - key: offer
    label: 优惠机制
    type: textarea
    required: true
  - key: frequency
    label: 发布频率
    type: select
    required: false
    options: ["一天2条以内", "活动当天集中发", "3天预热"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 社群活动话术生成器

生成社群话术：预热、开抢、临门一脚、结束提醒、不刷屏规则。

## 调用时机
当用户需要为门店微信群/会员群生成预热、开抢、临门一脚和结束提醒话术时调用。

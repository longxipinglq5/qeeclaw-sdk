---
name: event-planner
description: 把一个促销/活动想法变成完整的执行方案。
category: content
icon: "🎯"
input_schema:
  - key: event_type
    label: 活动类型
    type: select
    required: true
    placeholder: ""
    options: ["节日促销", "新品上市", "会员日", "开业活动", "周年庆", "线下沙龙"]
  - key: goal
    label: 活动目标
    type: text
    required: true
    placeholder: "例如：清库存 / 拉新200人 / 老客户回购"
  - key: budget
    label: 大概预算
    type: select
    required: false
    placeholder: ""
    options: ["1000以内", "1000-5000", "5000-2万", "2万以上", "不确定"]
  - key: duration
    label: 活动时长
    type: select
    required: false
    placeholder: ""
    options: ["1天", "3天", "7天", "15天"]
  - key: channels
    label: 宣传渠道
    type: text
    required: false
    placeholder: "例如：朋友圈+社群+门店海报"
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 活动方案生成器

请生成完整活动方案：1. 主题口号（1个主+2个备选，接地气能传播）；2. 时间流程（按天拆关键动作）；3. 优惠机制（具体满减/折扣/赠品，有阶梯感）；4. 宣传内容（3条朋友圈+2条社群话术+1条海报文案）；5. 预算分配（钱花在哪，每项预估金额）；6. 执行checklist（前/中/后要做什么）。像做过100场活动的运营总监出的方案，简洁可执行。

## 调用时机

当用户有一个促销或活动想法但不知道怎么落地时调用，3分钟出一份可执行的活动方案。适用于节日促销、新品上市、会员日、开业活动、周年庆、线下沙龙等场景。

## 注意事项

- 主题口号要接地气能传播
- 优惠机制要具体，有阶梯感
- 预算分配要写清每项预估金额
- 执行 checklist 要按前/中/后拆分
- 像做过100场活动的运营总监出的方案，简洁可执行

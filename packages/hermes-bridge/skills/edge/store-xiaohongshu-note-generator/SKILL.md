---
name: store-xiaohongshu-note-generator
description: 把门店特色、适合人群和真实体验点写成像用户分享的探店笔记。
category: store
icon: "探"
input_schema:
  - key: store_features
    label: 门店特色
    type: textarea
    required: true
  - key: target_people
    label: 适合人群
    type: text
    required: true
  - key: experience_points
    label: 真实体验点
    type: textarea
    required: true
  - key: tone
    label: 表达口吻
    type: select
    required: false
    options: ["真实用户种草", "避坑提醒", "本地生活攻略"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 小红书探店笔记生成器

生成探店笔记：标题组、封面大字、正文、拍摄清单、标签。不冒充消费者真实评价。

## 调用时机
当用户需要把门店特色、适合人群和真实体验点写成像用户分享的探店笔记时调用。

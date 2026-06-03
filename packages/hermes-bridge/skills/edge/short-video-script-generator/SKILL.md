---
name: short-video-script-generator
description: 生成短视频选题、分镜、口播稿和剪辑清单。
category: content
icon: "影"
input_schema:
  - key: topic
    label: 产品主题
    type: text
    required: true
    placeholder: "例如：本地 AI 员工怎么帮小企业做营销"
  - key: platform
    label: 目标平台
    type: select
    required: false
    placeholder: ""
    options: ["视频号", "抖音", "小红书", "TikTok"]
  - key: materials
    label: 卖点素材
    type: textarea
    required: false
    placeholder: "粘贴产品卖点、客户反馈或案例摘要"
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 短视频脚本生成器

输出：1. 3 个视频钩子；2. 分镜脚本（每个分镜包括画面、口播、时长）；3. 完整口播稿；4. 剪辑清单（素材、字幕、背景音乐建议）。

## 调用时机

当用户需要制作短视频内容时调用，适用于视频号、抖音、小红书、TikTok 等平台，帮助企业资料转成可执行的短视频脚本。

## 注意事项

- 分镜脚本要具体，每个分镜包括画面、口播、时长
- 视频钩子要能在前 3 秒抓住注意力
- 剪辑清单要实用，包含素材、字幕和背景音乐建议

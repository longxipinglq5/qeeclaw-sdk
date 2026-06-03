---
name: store-short-video-script-generator
description: 为老板或店员生成能照着拍的门店短视频开头、分镜、口播、字幕和动作。
category: store
icon: "拍"
input_schema:
  - key: store_selling_points
    label: 门店卖点
    type: textarea
    required: true
  - key: platform
    label: 目标平台
    type: select
    required: true
    options: ["抖音", "视频号", "小红书视频"]
  - key: duration
    label: 视频时长
    type: select
    required: false
    options: ["15秒", "30秒", "60秒"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 抖音/视频号门店短视频脚本

生成短视频脚本：开头、分镜、口播、字幕、拍摄动作清单。

## 调用时机
当用户需要为老板或店员生成能照着拍的门店短视频开头、分镜、口播、字幕和动作时调用。

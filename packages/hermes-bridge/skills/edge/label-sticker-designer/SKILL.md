---
name: label-sticker-designer
description: 为产品标签、封口贴、价格贴、包装贴纸生成文案、尺寸、材质和印刷注意事项。
category: design
icon: "签"
input_schema:
  - key: product_use
    label: 产品/用途
    type: textarea
    required: true
  - key: required_info
    label: 必须出现的信息
    type: textarea
    required: true
  - key: size_material
    label: 尺寸/材质偏好
    type: text
    required: false
  - key: regulatory_level
    label: 合规敏感度
    type: select
    required: false
    options: ["普通装饰/封口贴", "食品/饮品标签", "日化/护理产品", "价格/促销贴"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 标签/贴纸设计助手

生成标签/贴纸方案：文案、信息层级、尺寸材质、合规提醒、印刷清单。

## 调用时机
当用户需要为产品标签、封口贴、价格贴、包装贴纸生成文案、尺寸、材质和印刷注意事项时调用。

---
name: business-card-designer
description: 生成企业名片预览图、正反面信息层级、版式方案和印刷规格。
category: design
icon: "名"
input_schema:
  - key: person_business
    label: 企业/个人信息
    type: textarea
    required: true
  - key: contact_info
    label: 联系方式
    type: textarea
    required: true
  - key: industry_style
    label: 行业与风格
    type: select
    required: true
    options: ["科技/专业服务", "本地门店/生活服务", "教育/咨询/培训", "餐饮/零售/产品", "高端简洁", "亲切接地气"]
  - key: print_preference
    label: 印刷偏好
    type: select
    required: false
    options: ["普通铜版纸", "厚卡纸/高级感", "黑白极简", "带二维码"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 名片设计助手

生成名片设计方案：正面信息、背面说明、版式方案、印刷规格、校对清单。

## 调用时机
当用户需要生成企业名片预览图、正反面信息层级、版式方案和印刷规格时调用。

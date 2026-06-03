---
name: document-cover-designer
description: 为PPT、报价单、方案书和报告封面生成封面预览图、标题结构和版式方向。
category: design
icon: "封"
input_schema:
  - key: document_use
    label: 文件用途
    type: select
    required: true
    options: ["商务方案", "报价单", "路演/PPT", "项目报告", "培训资料"]
  - key: title_client
    label: 标题/客户
    type: textarea
    required: true
  - key: brand_project_info
    label: 品牌或项目资料
    type: textarea
    required: true
  - key: format
    label: 输出尺寸
    type: select
    required: false
    options: ["16:9 PPT", "A4方案封面", "报价单首页", "社媒预览图"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# PPT/报价封面设计助手

生成文档封面方案：标题、版式、视觉方向、导出提醒、校对清单。

## 调用时机
当用户需要为PPT、报价单、方案书和报告封面生成封面预览图、标题结构和版式方向时调用。

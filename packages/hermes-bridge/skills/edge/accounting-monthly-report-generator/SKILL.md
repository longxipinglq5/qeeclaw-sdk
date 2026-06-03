---
name: accounting-monthly-report-generator
description: 把代账客户月度数据、税费、异常事项和下月建议整理成客户能看懂的月报。
category: review
icon: "账"
input_schema:
  - key: client_name
    label: 客户名称
    type: text
    required: true
  - key: month_data
    label: 本月数据
    type: textarea
    required: true
  - key: tax_status
    label: 税务状态
    type: textarea
    required: false
  - key: issues
    label: 异常事项
    type: textarea
    required: false
  - key: report_style
    label: 月报风格
    type: select
    required: false
    options: ["客户易懂版", "老板经营提醒版", "续费汇报版"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 代账客户月报生成器

输出代账客户月报：经营/财税摘要、税费提醒、异常事项、下月配合事项、顾问建议、复核清单。

## 调用时机
当用户需要把代账客户月度数据、税费、异常事项和下月建议整理成客户能看懂的月报时调用。

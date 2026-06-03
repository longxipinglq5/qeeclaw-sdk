---
name: store-directions-helper
description: 把门店地址、地标、交通和停车信息整理成客户看得懂的到店路线。
category: store
icon: "路"
input_schema:
  - key: address
    label: 门店地址
    type: textarea
    required: true
  - key: landmarks
    label: 附近地标
    type: textarea
    required: true
  - key: traffic_parking
    label: 交通/停车信息
    type: textarea
    required: false
  - key: customer_type
    label: 客户情况
    type: select
    required: false
    options: ["第一次到店客户", "开车客户", "地铁/公交客户", "外卖/跑腿取货"]
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 到店路线助手

生成到店路线：微信路线版、电话口播版、停车提醒、找店提示。

## 调用时机
当用户需要把门店地址、地标、交通和停车信息整理成客户看得懂的到店路线时调用。

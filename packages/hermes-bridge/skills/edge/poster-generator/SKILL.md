---
name: poster-generator
description: 根据活动、产品或内容主题自动生成可用的营销海报图片、文案和生图提示词。
category: content
icon: "海"
input_schema:
  - key: purpose
    label: 海报用途
    type: select
    required: true
    placeholder: ""
    options: ["小红书封面", "活动促销海报", "产品介绍海报", "朋友圈配图", "公众号头图", "门店宣传海报"]
  - key: theme
    label: 海报主题
    type: text
    required: true
    placeholder: "例如：618 本地 AI 员工体验活动 / 新品到店 / 春季会员日"
  - key: business_info
    label: 产品/活动资料
    type: textarea
    required: true
    placeholder: "写清产品、活动机制、卖点、价格、门店或品牌信息。越具体，海报越贴近业务。"
  - key: style
    label: 视觉风格
    type: select
    required: true
    placeholder: ""
    options: ["高级商业质感", "真实摄影海报", "小红书封面感", "简洁科技风", "门店促销风", "国潮节日风"]
  - key: ratio
    label: 画面比例
    type: select
    required: true
    placeholder: ""
    options: ["1:1", "3:4", "4:5", "16:9"]
  - key: audience
    label: 目标人群
    type: text
    required: false
    placeholder: "例如：本地门店用户、宝妈、年轻白领、老客户"
  - key: key_copy
    label: 必须出现的文案
    type: textarea
    required: false
    placeholder: "例如：限时 3 天 / 到店扫码领取 / 私聊预约演示"
  - key: color_direction
    label: 颜色或品牌要求
    type: text
    required: false
    placeholder: "例如：绿色科技感 / 红金节日感 / 避免大面积黑色"
output_schema:
  - key: result
    label: 生成结果
    type: text
card_template: text_only
---

# 海报生成器

输出：1. 已生成海报图片；2. 可直接放到海报上的主标题、副标题、行动引导；3. 设计说明（构图、颜色、素材、留白）；4. 生图提示词。海报要适合中国中小企业真实发布，不要生成虚假二维码、虚假 logo 或过度夸张承诺。

## 调用时机

当用户需要为活动、产品或内容主题制作营销海报时调用。适用于朋友圈、小红书、公众号头图、门店宣传等场景，帮助用户快速生成视觉素材和配套文案。

## 注意事项

- 海报要适合中国中小企业真实发布
- 不要生成虚假二维码、虚假 logo 或过度夸张承诺
- 文案要贴近实际业务，避免过度美化

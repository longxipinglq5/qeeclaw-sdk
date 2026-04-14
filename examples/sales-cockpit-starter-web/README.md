# QeeClaw Sales Cockpit Starter Web

一个更偏“客户前端起步工程”的静态 Web 示例。

它和 `sales-cockpit-web-verifier` 的区别是：

- `sales-cockpit-web-verifier`
  - 偏验证页
  - 重点是逐项检查 SDK 是否打通
- `sales-cockpit-starter-web`
  - 偏业务页样板
  - 重点是把 SDK 装成一个可继续开发的销售驾驶仓首页

## 1. 适合谁用

- 客户前端团队
- 实施团队
- 内部产品 / 设计 / 研发一起讨论页面结构时

## 2. 页面会调用哪些能力

- `tenant.getCurrentContext()`
- `iam.getProfile()`
- `models.getRouteProfile()`
- `models.listRuntimes()`
- `product.channelCenter.loadHome(teamId)`
- `product.conversationCenter.loadHome(teamId)`
- `product.governanceCenter.loadHome(scope)`
- `product.knowledgeCenter.loadHome(runtimeScope)`
- `product.salesCockpit.loadHome(teamId, scope)`
- `product.salesCockpit.loadOpportunityBoard(teamId, scope)`
- `product.salesKnowledge.loadAssistantContext(runtimeScope)`
- `product.salesCoaching.loadTrainingOverview(teamId, scope)`

## 3. 使用方式

建议从仓库根目录启动静态服务：

```bash
cd /path/to/qs-nexus-aos
python3 -m http.server 4177 --directory .
```

然后访问：

```text
http://127.0.0.1:4177/sdk/examples/sales-cockpit-starter-web/
```

如果以下目录不存在，需要先 build：

```bash
cd sdk/qeeclaw-core-sdk && pnpm build
cd sdk/qeeclaw-product-sdk && pnpm build
```

## 4. 适合客户怎么用

推荐把这个样板当成“字段与页面装配参考”，而不是直接上线页面：

- 先确认 `baseUrl / token / teamId / runtimeType / agentId`
- 看页面里哪些板块适合保留
- 再把各板块拆成客户自己的组件、路由与状态管理
- 用“开发快照”里的 JSON 继续做字段映射

## 5. 注意事项

- `baseUrl` 只填写根地址，不要手动加 `/api/...`
- `Token` 可直接填 token 本身；如果粘贴 `Bearer xxx` 也会自动兼容
- 如果本地浏览器请求线上地址报跨域错误，需要平台网关补充 CORS
- 这是示例页，不建议在生产环境长期在浏览器保存高权限 token

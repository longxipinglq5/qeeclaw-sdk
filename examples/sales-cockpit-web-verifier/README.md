# QeeClaw Sales Cockpit Web Verifier

一个零框架、零额外构建依赖的静态 Web 示例，用于快速验证：

- `@qeeclaw/core-sdk`
- `@qeeclaw/product-sdk`
- 销售驾驶仓相关 kit

这个示例适合：

- 内部联调时快速 smoke test
- 给客户前端团队做最小参考工程
- 验证线上 `QeeClaw Platform` 是否已具备销售驾驶仓所需基础能力

## 1. 验证内容

页面会尝试调用以下能力：

- `tenant.getCurrentContext()`
- `iam.getProfile()`
- `models.listAvailable()`
- `models.getRouteProfile()`
- `models.listRuntimes()`
- `product.channelCenter.loadHome(teamId)`
- `product.conversationCenter.loadHome(teamId)`
- `product.governanceCenter.loadHome("mine")`
- `product.knowledgeCenter.loadHome(runtimeScope)`
- `product.salesCockpit.loadHome(teamId, "mine")`
- `product.salesKnowledge.loadAssistantContext(runtimeScope)`
- `product.salesCoaching.loadTrainingOverview(teamId, "mine")`

## 2. 使用方式

建议在仓库根目录启动静态服务，而不是只服务当前示例目录。

原因是页面会直接引用：

- `sdk/qeeclaw-core-sdk/dist/*`
- `sdk/qeeclaw-product-sdk/dist/*`

如果只把 `sdk/examples/sales-cockpit-web-verifier/` 单独作为站点根目录，浏览器会拿不到这两个 SDK 模块文件。

在仓库根目录执行：

```bash
cd /path/to/qs-nexus-aos
```

启动一个本地静态服务器，任选一种方式：

```bash
python3 -m http.server 4177 --directory .
```

或者：

```bash
npx serve .
```

然后访问：

```text
http://127.0.0.1:4177/sdk/examples/sales-cockpit-web-verifier/
```

如果 `sdk/qeeclaw-core-sdk/dist` 或 `sdk/qeeclaw-product-sdk/dist` 不存在，先分别执行：

```bash
cd sdk/qeeclaw-core-sdk && pnpm build
cd sdk/qeeclaw-product-sdk && pnpm build
```

## 3. 页面配置项

需要填写：

- `Base URL`
  - 例如 `https://paas.qeeshu.com`
- `Token`
  - 用户登录 token 或具备相应权限的测试 token
  - 只填写 token 本身即可，不需要手动加 `Bearer `
  - 如果直接粘贴 `Bearer xxx`，页面也会自动兼容
- `Team ID`
  - 可选；如果留空，会尝试从 `tenant.getCurrentContext()` 自动取第一个团队
- `Runtime Type`
  - 建议默认 `openclaw`
- `Agent ID`
  - 建议默认 `sales-copilot`

## 4. 注意事项

- `baseUrl` 只填写根地址，不要手动加 `/api/...`
- 本示例默认依赖仓库里的 `sdk/qeeclaw-core-sdk/dist` 与 `sdk/qeeclaw-product-sdk/dist`
- 如果本地页面访问线上接口遇到跨域错误，说明当前线上环境未放开该来源的 CORS
- 这只是一个验证型页面，不建议在生产环境把高权限 token 长期保存在浏览器里

## 5. 文件说明

- `index.html`
  - 页面结构
- `app.css`
  - 页面样式
- `app.js`
  - 调用 SDK 执行验证逻辑

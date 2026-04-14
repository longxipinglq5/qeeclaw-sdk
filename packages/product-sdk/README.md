# QeeClaw Product SDK

`@qeeclaw/product-sdk` 是在 `@qeeclaw/core-sdk` 之上的场景 / 产品装配层。

> Status: Beta

它不直接关心底层 API 路径，而是把产品层最常用的几类装配能力整理成更稳定的入口。

当前分成两层：

- 通用 center kit
- 第一样板场景 kit：`销售超级驾驶舱`

当前提供的装配入口包括：

- `channelCenter`
- `conversationCenter`
- `deviceCenter`
- `knowledgeCenter`
- `governanceCenter`
- `salesCockpit`
- `salesKnowledge`
- `salesCoaching`

如果你是在做真实项目对接，建议优先参考仓库文档目录中的两份说明：

- `QeeClaw_客户接入手册.md`
- `QeeClaw_AI_PaaS平台交付手册.md`

## 设计目标

当前阶段的重点不是继续堆底层接口，而是让上层产品更快装页面、更快拼业务流。

因此这一版 Product SDK 先提供两类能力：

- 渠道中心装配
- 会话中心装配
- 设备中心总览装配
- 知识中心首页装配
- 治理中心首页装配
- 销售超级驾驶舱首页装配
- 销售知识助手上下文装配
- 销售培训 / 复盘装配

## 安装

```bash
pnpm add @qeeclaw/core-sdk @qeeclaw/product-sdk
```

## 使用方式

```ts
import { createQeeClawClient } from "@qeeclaw/core-sdk";
import { createQeeClawProductSDK } from "@qeeclaw/product-sdk";

const core = createQeeClawClient({
  baseUrl: "https://your-qeeclaw-host",
  token: "your-token",
});

const product = createQeeClawProductSDK(core);
const runtimeScope = {
  teamId: 1,
  runtimeType: "openclaw",
  agentId: "sales-copilot",
};

const channelHome = await product.channelCenter.loadHome(1);
const conversationHome = await product.conversationCenter.loadHome(1);
const governanceHome = await product.governanceCenter.loadHome("mine");
const deviceOverview = await product.deviceCenter.loadOverview();
const knowledgeHome = await product.knowledgeCenter.loadHome(runtimeScope);
const salesCockpit = await product.salesCockpit.loadHome(1, "mine");
const salesKnowledge = await product.salesKnowledge.loadAssistantContext(runtimeScope);
const salesCoaching = await product.salesCoaching.loadTrainingOverview(1, "mine");
```

其中：

- `OpenClaw` 仍是当前默认 runtime 示例
- `knowledgeCenter / salesKnowledge` 已支持显式传入 `runtimeType / agentId`
- `deviceCenter` 当前仍是 `OpenClaw device bridge` 控制面，不是所有 runtime 的统一设备控制台

## 本地 Mock 联调

如果你希望外部团队先在没有真实平台环境的情况下体验 `Product SDK`，可以先启动 `Core SDK` 自带的 mock server：

```bash
node ./node_modules/@qeeclaw/core-sdk/examples/mock-platform-server.mjs
```

然后直接运行 `Product SDK` 的聚合示例：

```bash
node ./examples/mock-dashboard.mjs
```

默认会连接：

- `baseUrl=http://127.0.0.1:3456`
- `teamId=10001`
- `token=mock-token`

也可以通过环境变量覆盖：

```bash
QEECLAW_BASE_URL=http://127.0.0.1:3456 \
QEECLAW_TEAM_ID=10001 \
QEECLAW_TOKEN=mock-token \
node ./examples/mock-dashboard.mjs
```

这个示例会一次性输出：

- 渠道中心概览
- 会话中心概览
- 设备概览
- 治理中心概览
- 知识中心概览
- 销售超级驾驶舱概览
- 销售知识助手上下文
- 销售培训 / 复盘概览

## 当前提供的 kit

### channelCenter

- `loadHome()`
- `getOverview()`
- `getWechatWorkConfig()`
- `updateWechatWorkConfig()`
- `getFeishuConfig()`
- `updateFeishuConfig()`

### conversationCenter

- `loadHome()`
- `getStats()`
- `listGroups()`
- `listGroupMessages()`
- `listHistory()`
- `sendMessage()`

### deviceCenter

- `loadOverview()`
- `getAccountState()`
- `bootstrap()`

### knowledgeCenter

- `loadHome()`
- `search()`
- `ingest()`
- `updateWatchDir()`

### governanceCenter

- `loadHome()`
- `listApprovals()`
- `listAuditEvents()`

### salesCockpit

- `loadHome()`
- `loadOpportunityBoard()`

### salesKnowledge

- `loadAssistantContext()`

### salesCoaching

- `loadTrainingOverview()`

## 当前边界

- 这还是第一版 Product SDK，偏向“装配服务层”，不是 UI 组件库
- `knowledge` 相关 kit 已开始透传 `teamId / runtimeType / deviceId / agentId`，用于多 runtime 场景下显式指定目标范围
- `OpenClaw = 当前默认 Agent Runtime`；`DeeFlow2 / 其他 Runtime = 可接入 Runtime Adapter`
- `deviceCenter` 现阶段仍只代表 `OpenClaw` 的设备桥接注册 / 配对控制面
- 销售超级驾驶舱当前是第一样板场景，但不会替代未来的多行业扩展
- 后续可以继续往 Vue/React hooks、页面 schema、组件层演进
- 对外发布时建议继续保持 `Beta` 标记，直到 kit 层字段和装配方式稳定

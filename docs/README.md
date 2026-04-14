# QeeClaw 客户文档目录

最后更新：2026-04-09

## 1. 顶层现在只保留什么

`sdk/docs/` 顶层现在只保留 3 份主文档：

1. `README.md`
   当前首页
2. `QeeClaw_客户接入手册.md`
   面向客户、实施方、外包团队的统一接入手册
3. `QeeClaw_AI_PaaS平台交付手册.md`
   面向部署、交付、私有化、边缘节点项目

联调辅助资产统一看两个子目录：

- `openapi/`
- `postman/`

历史版本、内部控制面文档、旧模板统一放到：

- `archive/`

## 2. 客户第一次应该看什么

普通客户、前端客户、桌面 UI 客户，先看：

1. [QeeClaw_客户接入手册.md](./QeeClaw_客户接入手册.md)
2. `openapi/QeeClaw_Cloud_Public_API.openapi.yaml`
3. `postman/QeeClaw_Cloud_Public_API.postman_collection.json`
4. `postman/QeeClaw_Cloud_Public_API.postman_environment.json`

如果是私有化、边缘节点、本地 gateway 项目，再补看：

1. [QeeClaw_AI_PaaS平台交付手册.md](./QeeClaw_AI_PaaS平台交付手册.md)

如果是高级集成或平台内部维护，再去 `archive/` 查看内部文档，不作为客户默认发包内容。

## 3. 当前统一交付口径

- `Base URL`：`https://paas.qeeshu.com`
- 客户凭证：`API Key`
- `runtimeType`：固定为 `openclaw`
- `teamId / agentId`：不作为客户手工填写项
- 本地优先产品只开放公开云端 API：
  - `GET /api/users/me/context`
  - `models/*`
  - `billing/*`

## 4. 哪些文档被收进历史目录

以下文档已不再作为顶层主入口，后续保留在 `sdk/docs/archive/` 仅供历史参考：

- 原第三方接入总手册
- 原云端公开版说明
- 原终端接入指南
- 原销售驾驶仓参数模板
- 原 Platform API v1 内部域化接口说明
- 原 Platform API v1 内部 OpenAPI / Postman 资产

## 5. 一句话结论

以后发给客户时，默认只需要发：

- `README.md`
- `QeeClaw_客户接入手册.md`
- `QeeClaw_AI_PaaS平台交付手册.md`（仅私有化、边缘或桌面本地项目需要）
- 公开云端 API 的 OpenAPI / Postman 资产

其他文档都不是客户默认入口。

## 6. 一键生成客户发包目录

如果内部团队希望直接生成“可压缩、可发客户”的目录，可执行：

```bash
bash scripts/build-qeeclaw-customer-package.sh
```

如需桌面 / 本地节点 / 私有化增强版，可执行：

```bash
bash scripts/build-qeeclaw-customer-package.sh desktop
```

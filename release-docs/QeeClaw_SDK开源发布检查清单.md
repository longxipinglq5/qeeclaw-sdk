# QeeClaw SDK 开源发布检查清单

最后更新：2026-03-22

## 1. 仓库边界

- [x] `sdk/README.md` 或公开仓库 `README.md` 已说明四个模块及成熟度
- [x] `sdk/docs/` 或公开仓库 `docs/` 已能独立服务外部团队
- [x] 公开仓库结构已确定为 monorepo 或拆分仓

## 2. 敏感信息检查

- [x] 未包含 `.env` 文件
- [x] 未包含证书、私钥、密钥文件
- [x] 未包含真实用户 token、设备 key、LLM key
- [x] 未包含生产数据库、缓存、对象存储连接信息
- [x] 未包含个人机器专属路径，或已明确为示例

## 3. 默认示例地址检查

- [x] HTTP 示例默认只指向本地开发地址或占位域名
- [x] WebSocket 示例默认只指向本地开发地址或占位域名
- [x] 未直接把生产域名写成公开脚本默认值
- [x] 真实部署地址都可以通过参数、环境变量或构建参数覆盖

## 4. SDK 包完整性

### `@qeeclaw/core-sdk`

- [x] `package.json` 完整
- [x] `README.md` 完整
- [x] `LICENSE` 存在
- [x] 构建产物可用
- [x] 示例可运行
- [x] mock server 可运行

### `@qeeclaw/product-sdk`

- [x] `package.json` 完整
- [x] `README.md` 完整
- [x] `LICENSE` 存在
- [x] 构建产物可用
- [x] 聚合示例可运行

### `@qeeclaw/runtime-sidecar`

- [x] 已明确 `experimental` 定位
- [x] 本地 host/port 可配置
- [x] gateway 进程启动方式可配置
- [x] 本地状态目录和认证文件可配置
- [x] README 与 `selfcheck` 输出字段一致

### `meeting_device_firmware`

- [x] 已提供 `LICENSE`
- [x] PlatformIO 配置可通过构建参数覆盖
- [x] Python 联调脚本可通过参数覆盖 API/WS 地址
- [x] 硬件文档不再直接写真实生产域名

## 5. 文档检查

- [x] 已提供通用说明文档
- [x] 已提供 Web 对接文档
- [x] 已提供桌面 App 对接文档
- [x] 已提供移动端 App 对接文档
- [x] 已提供 AI PaaS 平台交付手册
- [x] 已提供私有化部署说明
- [x] 已提供安装升级与迁移说明
- [x] 已提供环境变量模板说明
- [x] 已提供交付资产清单
- [x] 已提供首版 release notes
- [x] 架构图与文字描述一致
- [x] Sidecar 配置字段与代码一致

## 5.1 交付模板检查

- [x] `sdk/deploy/env/` 已提供可公开的占位模板
- [x] `sdk/deploy/compose/` 已提供 Gateway compose 示例
- [x] `sdk/deploy/nginx/` 已提供 Gateway 反向代理示例
- [x] 交付模板中未写入真实密钥、账号或生产域名

## 6. 许可证与依赖

- [x] 根目录存在 `LICENSE`
- [x] 每个公开模块都带有许可证
- [x] 第三方依赖许可证已检查
- [x] 公开模块的许可证策略已对外说明

## 7. 上线前最终验证

- [x] 文档中的安装命令可执行
- [x] 文档中的最小示例可运行
- [x] Python 示例脚本语法通过
- [x] 关键链接与文件路径无误
- [x] GitHub issue / PR 模板已存在

## 8. 发布前仍建议保留的最后动作

- [x] 将 `.github/CODEOWNERS` 中的占位团队替换为真实 GitHub 用户或团队
- [x] 将 `.github/ISSUE_TEMPLATE/config.yml` / `package.json` 中的仓库 URL 换成正式公开仓地址
- [x] 对 Node、Python、PlatformIO 直接依赖做一次正式许可证审计

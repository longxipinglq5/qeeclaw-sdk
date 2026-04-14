# 从自定义本地 Gateway 迁移到 `@qeeclaw/runtime-sidecar`

## 迁移目标

把原来“本地 relay/gateway 进程 + 认证态文件 + 若干本地 worker”分散管理的方式，收口为统一的 Sidecar 生命周期管理。

## 推荐迁移顺序

1. Sidecar 接管认证态读取
2. Sidecar 接管 `installationId` 补齐
3. Sidecar 接管设备 bootstrap
4. Sidecar 接管本地 gateway 进程的启动与状态管理
5. memory / policy / approval 入口优先走 Sidecar

## 迁移后的职责划分

### `@qeeclaw/runtime-sidecar`

- 读取和维护本地认证态
- 负责 `installationId`
- 负责设备 bootstrap
- 管理 gateway 子进程
- 暴露本地 HTTP API 给桌面端或本地 agent 调用
- 承担 memory / knowledge / policy / approval 的统一入口

### 自定义 Gateway / Relay

- 继续承担现有 relay 工作
- 通过 `gatewayCommand` / `gatewayArgs` 由 Sidecar 启停
- 不再建议单独散落管理

## 兼容约定

当前 Sidecar 已兼容两类本地状态目录：

- `~/.qeeclaw`
- `~/.openclaw`

当前 Sidecar 已兼容两类认证态文件：

- `auth-state.json`
- `nexus-auth.json`

如果已有历史脚本入口，也可以继续通过以下方式接入：

- `QEECLAW_GATEWAY_ENTRY`
- `QEECLAW_BRIDGE_ENTRY`

## 推荐做法

- 让桌面端或本地 agent 优先调用 Sidecar 本地接口，而不是各自直连本地脚本
- 让 gateway 进程专注 relay，自举、认证态、审批缓存等逻辑放回 Sidecar
- 用 `selfcheck` 作为统一运行时诊断入口

## 不建议的做法

- 继续让多个脚本各自直接修改认证态文件
- 继续让一个本地脚本同时承担 relay、bootstrap、策略守护三类职责
- 在没有 Sidecar 管理的情况下继续扩散新的本地 worker 入口

## 阶段性结果

完成迁移后，`Runtime Sidecar` 可以继续往下承接：

- Knowledge 索引任务
- 本地缓存同步协议
- 审批执行代理
- 本地安全策略 enforcement

# QeeClaw 平台安装打包说明手册

为了针对不同的交付场景，项目现在只保留服务端 / HubOS 相关打包入口。`qeeshu-ruisi` 产品已从主工程移除，不再作为交付或打包目标。

## 场景速览

| 部署形态 | 目标客户 | 使用脚本 | 产物形态 |
| :--- | :--- | :--- | :--- |
| **QeeClaw Server** | 独立服务端 / 运行时节点 | `scripts/build-qeeclaw-server.sh` | `.tar.gz` / `.deb` |
| **HubOS Linux 总包** | HubOS 自托管一体部署 | `scripts/build-linux.sh` | `hubos-linux-*.tar.gz` |

---

## 详细构建指南

### 1. QeeClaw Server 打包 (`scripts/build-qeeclaw-server.sh`)

专门针对私有化服务器节点，构建 QeeClaw Server 运行时包。它不包含 Ruisi 桌面 GUI。

**执行命令**:
```bash
./scripts/build-qeeclaw-server.sh --standalone
```

**底层逻辑**: 调用 `qeeclaw-server/scripts/build-standalone.sh` 或 `qeeclaw-server/scripts/build-package.sh`。
**产物位置**: `qeeclaw-server/release/`

### 2. HubOS Linux 总包 (`scripts/build-linux.sh`)

HubOS 是当前允许携带自托管后端的 Linux 一体包，包含 NexusAOS backend、Nexus PaaS frontend 和 QeeClaw Server 包。

**执行命令**:
```bash
./scripts/build-linux.sh
```

**底层逻辑**: 构建 `nexus-paas-frontend`，复制 `nexusaos-backend`，并按配置附带 QeeClaw Server 包。
**产物位置**: `release/linux/hubos-linux-*.tar.gz`

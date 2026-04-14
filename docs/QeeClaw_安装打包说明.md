# QeeClaw 平台安装打包说明手册

为了针对不同的交付场景，项目现在提供三个各自独立的入口打包脚本，全都统一归档在根目录下的 `scripts/` 文件夹中。

## 场景速览

| 部署形态 | 目标客户 | 使用脚本 | 产物形态 |
| :--- | :--- | :--- | :--- |
| **纯服务端私有化** | Linux 极客、大型企业裸机内网隔离部署 | `scripts/build-server.sh` | `.tar.gz` (含离线源码与安装脚本) |
| **轻量客户端分离** | 懂技术的客户、已有远端后端可直接连接 | `scripts/build-client.sh` | `.dmg` / `.exe` (只有前端) |
| **一体式傻瓜安装** | C端小白用户、想一键开箱并本地独立验证的人 | `scripts/build-all-in-one.sh` | `.dmg` / `.exe` (无感内置后端) |

---

## 详细构建指南

### 1. 独立服务端打包 (`scripts/build-server.sh`)

专门针对大B客户的私有化服务器节点，进行纯后端的静默离线压缩处理。它不包含桌面 GUI。

**执行命令**:
```bash
./scripts/build-server.sh
```

**底层逻辑**: 调用 `server/scripts/build-package.sh`。它会同步所有的 Python 后端引擎（`hermes-agent`）并使用 `npm` 离线构建 `hermes-hudui` 管理前端到静态文件中，最终把文件并入一个压缩文件。
**产物位置**: `server/release/qeeclaw-server-*.tar.gz`

### 2. 独立客户端打包 (`scripts/build-client.sh`)

专门构建纯净版的 QeeShu Ruisi 前端，体积轻量（<100MB），适合远程对接已经安装好的独立服务端。

**执行命令**:
```bash
./scripts/build-client.sh
# 你还可以通过后续加旗标支持如 ./scripts/build-client.sh dmg 
```

**底层逻辑**: 调用 `qeeshu-ruisi/scripts/package-ruisi-desktop.sh`。只单纯跑前端编译并调用 `electron-builder` 输出。
**产物位置**: `qeeshu-ruisi/release/QeeShu-Ruisi-*.dmg`

### 3. 一体机全覆盖打包 (`scripts/build-all-in-one.sh`)

面向最高傻瓜化交付场景。该脚本会将一整个庞大的基于 FastAPI/Pydantic 的 Python 后端沙箱，硬核塞入 Electron 前端的程序包深处，真正做到开箱即用（Out of the box），彻底脱离用户电脑的环境劫持。

**执行命令**:
```bash
./scripts/build-all-in-one.sh
# 也可加格式约束 ./scripts/build-all-in-one.sh dmg
```

**底层逻辑**: 调用 `qeeshu-ruisi/scripts/package-ruisi-desktop.sh --all-in-one`。脚本在运行 Electron builder 前，会通过系统中的原生 `PyInstaller` 预构建一份完全独立的架构底座（混淆版的 `bridge_server` 可执行文件与清洗过的 `vendor` 离线模块），最终打包输出为一个巨大的 `.dmg` 安装包！
当用户双击开机时，Electron 的主进程（main.js）会无感执行挂载，唤醒深处的该脱机版 Python 代理，服务完毕自动伴随关停。
**产物位置**: `qeeshu-ruisi/release/QeeShu-Ruisi-*.dmg` （注意，All-In-One 包的体积会大数十 Mb 以上，视底座模块大小而定）。

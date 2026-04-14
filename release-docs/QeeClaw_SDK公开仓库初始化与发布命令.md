# QeeClaw SDK 公开仓库初始化与发布命令

最后更新：2026-03-22

## 1. 从当前 monorepo 导出公开仓库

```bash
bash scripts/export-qeeclaw-public-sdk.sh /tmp/qeeclaw-sdk-public
```

## 2. 初始化公开 Git 仓库

```bash
cd /tmp/qeeclaw-sdk-public
git init
git checkout -b main
git add .
git commit -m "chore: initial public qeeclaw sdk release"
```

如果已经创建好远程仓库，再执行：

```bash
git remote add origin <your-public-repo-url>
git push -u origin main
```

建议在首次 push 前，再检查两处占位信息：

- `.github/CODEOWNERS` 中的占位 owner
- `package.json` / `.github/ISSUE_TEMPLATE/config.yml` 中的仓库地址
- `deploy/env/` 下是否仍保留为示例占位值

## 3. 安装依赖

推荐：

```bash
cd /tmp/qeeclaw-sdk-public
pnpm install
```

也可以分别进入各 package 安装：

```bash
cd /tmp/qeeclaw-sdk-public/packages/core-sdk && npm install
cd /tmp/qeeclaw-sdk-public/packages/product-sdk && npm install
cd /tmp/qeeclaw-sdk-public/packages/runtime-sidecar && npm install
```

## 4. 发布前校验

```bash
cd /tmp/qeeclaw-sdk-public
pnpm run release:check
```

如果要做 npm 打包预演：

```bash
cd /tmp/qeeclaw-sdk-public
pnpm run release:pack
```

如果要跑 mock 示例：

```bash
cd /tmp/qeeclaw-sdk-public
pnpm demo
```

## 5. 首次发布建议

### 5.1 Core SDK

```bash
cd /tmp/qeeclaw-sdk-public/packages/core-sdk
npm publish --access public
```

### 5.2 Product SDK

```bash
cd /tmp/qeeclaw-sdk-public/packages/product-sdk
npm publish --access public --tag beta
```

### 5.3 Runtime Sidecar

```bash
cd /tmp/qeeclaw-sdk-public/packages/runtime-sidecar
npm publish --access public --tag next
```

### 5.4 Meeting Device Firmware

固件目录不是 npm package，不需要执行 `npm publish`。建议作为：

- GitHub 仓库中的 `hardware/meeting-device-firmware`
- 文档与样例工程
- 社区预览能力

## 6. 建议的首版标签策略

| 模块 | 建议 npm tag |
| --- | --- |
| `@qeeclaw/core-sdk` | `latest` |
| `@qeeclaw/product-sdk` | `beta` |
| `@qeeclaw/runtime-sidecar` | `next` |

## 7. 一条龙建议命令

```bash
bash scripts/export-qeeclaw-public-sdk.sh /tmp/qeeclaw-sdk-public
cd /tmp/qeeclaw-sdk-public
git init
git checkout -b main
pnpm install
pnpm run release:check
git add .
git commit -m "chore: initial public qeeclaw sdk release"
```

建议在公开仓中同时保留：

- `docs/` 作为对外说明层
- `deploy/` 作为交付模板层

# macOS 桌面版部署指南（星易查）

功能与 Windows / Linux 桌面版完全一致。Apple Silicon (M 系列) 与 Intel 双架构：

| 架构 | dmg 安装包 | zip 便携版 |
|------|-----------|-----------|
| Apple Silicon (M1/M2/M3/M4) | `XingYiCha-macOS-arm64.dmg` | `XingYiCha-macOS-arm64.zip` |
| Intel | `XingYiCha-macOS-x86_64.dmg` | `XingYiCha-macOS-x86_64.zip` |

## 一、获取（云端构建，与 Windows 版同源）

1. 登录 GitHub（私有仓库需有权限的账号）
2. Actions 页手动 Run workflow，或打 `v*` tag 自动发布
3. Release 页面下载对应架构的 dmg 或 zip

## 二、安装与使用

**dmg 安装包**：双击 dmg → 把「星易查」拖入 Applications → 从启动台/访达打开。
首次打开若提示"无法验证开发者"（应用未签名上架 App Store，属正常）：

- 方法一：右键（或按住 Control 点击）图标 → 选「打开」→ 确认
- 方法二：系统设置 → 隐私与安全性 → 允许"星易查"

**zip 便携版**：解压出 `XingYiCha.app`，双击即可；首次打开同样按上述方法放行。

启动后自动打开浏览器访问 `http://127.0.0.1:5001`，终端窗口关闭即停止服务。

> **⚠️ 前置条件（仅当标书含老格式 `.doc`）**：`.docx` / `.pdf` / `.txt` /
> `.xlsx` / 扫描件 OCR 均开箱即用；`.doc` 的**正文提取**需先安装
> LibreOffice（`brew install --cask libreoffice`，或
> [官网](https://www.libreoffice.org/) 下载 pkg 安装）。未安装时 `.doc`
> 正文自动跳过，其元数据比对及全部其他格式、维度不受影响。

## 三、macOS 桌面集成

星易查在 macOS 上不只是"开了个本地网页"，还有原生桌面行为：

- **Dock 图标**：应用运行期间 Dock 有图标；点按图标（或从 Finder 重新打开）
  会**再次拉起页面**——浏览器标签页误关后不必重启应用；
- **菜单栏状态项**：屏幕右上角有「星易查」菜单，提供 **打开页面** 与 **退出**
  两个动作，不用回到终端窗口去关闭服务。

## 四、功能说明

| 功能 | 表现 |
|------|------|
| .docx / .pdf / .txt / .xlsx / 扫描件 OCR | ✅ 完整支持 |
| .doc 元数据比对 | ✅ 完整支持 |
| .doc 正文 | ⚠️ 需安装 LibreOffice（`brew install --cask libreoffice` 或官网下载），未装时自动跳过，其余不受影响 |

数据目录：`~/Library/Application Support/星易查/`（history 与 uploads）。

## 五、环境变量（低配调优 / 行为微调）

默认值即开箱可用，仅按需设置；完整参数表见
[硬件配置要求](硬件配置要求.md)第六节。`.app` 双击不经过终端，需带参数时
从终端启动内层可执行文件：

```bash
OCR_MAX_PAGES=50 /Applications/XingYiCha.app/Contents/MacOS/XingYiCha
```

永久生效可写入 `~/.zshrc`：`export PDF_TABLE_LAYOUT=off`（之后从终端启动；
仅影响终端启动的实例）。

## 六、常见问题

- **提示"已损坏，无法打开"**：多为 Gatekeeper 对未签名应用的拦截，执行
  `xattr -cr /Applications/星易查.app` 后重试。
- **端口占用**：自动改用 5002-5010，以终端打印的实际地址为准。
- **M 系列跑 x86_64 版**：Rosetta 可运行但慢，请优先下载 arm64 版。
- **换电脑 / 重装怎么迁移**：整个 `~/Library/Application Support/星易查/`
  目录拷到新机同路径。

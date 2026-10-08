# Linux 桌面版部署指南（星易查）

两种分发形式，功能与 Windows 桌面版完全一致：

| 形式 | 文件 | 适用 |
|------|------|------|
| AppImage | `XingYiCha-x86_64.AppImage` | 单文件，`chmod +x` 后双击即运行 |
| 便携版 | `XingYiCha-linux-x86_64.tar.gz` | 解压即用 |

> 信创环境（银河麒麟 V10，含 x86_64 海光/兆芯与 aarch64 飞腾/鲲鹏）请参见
> [银河麒麟部署.md](银河麒麟部署.md)——注意 glibc 兼容性、KYLSEC 放行与
> 离线安装事项。

## 一、获取（云端构建，与 Windows 版同源）

1. 登录 GitHub（私有仓库需有权限的账号）
2. Actions 页手动 Run workflow，或打 `v*` tag 自动发布
3. Release 页面下载 `XingYiCha-x86_64.AppImage` 或 tar.gz
   （Actions 产物与 Release 附件内容一致）

## 二、使用

**AppImage**：
```bash
chmod +x XingYiCha-x86_64.AppImage
./XingYiCha-x86_64.AppImage        # 双击亦可（需桌面环境文件管理器设置"可执行"）
```
启动后自动打开浏览器访问 `http://127.0.0.1:5001`，终端窗口关闭即停止服务。

**便携版**：
```bash
tar xzf XingYiCha-linux-x86_64.tar.gz
./XingYiCha/XingYiCha
```

## 三、功能说明

| 功能 | 表现 |
|------|------|
| .docx / .pdf / .txt / .xlsx / 扫描件 OCR | ✅ 完整支持 |
| .doc 元数据比对 | ✅ 完整支持 |
| .doc 正文 | ⚠️ 需系统安装 LibreOffice（`apt install libreoffice` 等），未装时自动跳过，其余不受影响 |

数据目录：`~/.local/share/星易查/`（history 与 uploads）。

## 四、环境变量（低配调优 / 行为微调）

默认值即开箱可用，仅按需设置；完整参数表见
[硬件配置要求](硬件配置要求.md)第七节。终端启动时直接前缀：

```bash
OCR_MAX_PAGES=50 OCR_TIME_BUDGET=120 ./XingYiCha/XingYiCha
```

想让桌面图标（AppImage 双击）也带上参数，可包一层 `.desktop` 文件的
`Exec=` 行，或写入 `~/.profile`：`export PDF_TABLE_LAYOUT=off` 后重新登录。

## 五、常见问题

- **报 libGL.so.1 缺失**：`sudo apt install libgl1`（AppImage 依赖宿主系统库）。
- **AppImage 无法双击启动**：多数文件管理器需勾选"允许作为程序执行"；命令行 `./` 运行不受限。
- **让局域网其他电脑访问**：`HOST=0.0.0.0 ./XingYiCha/XingYiCha` 启动，
  防火墙放行对应端口（`sudo ufw allow 5001`），他机访问 `http://<本机IP>:5001`。
- **换电脑 / 重装怎么迁移**：整个 `~/.local/share/星易查/` 目录拷到新机同路径。
- **端口占用**：自动改用 5002-5010，以终端打印的实际地址为准。
- **Intel 与 ARM 平台**：预编译产物为 x86_64；ARM（飞腾/鲲鹏等信创环境）走
  [银河麒麟部署.md](银河麒麟部署.md)第六节源码部署，依赖均提供 aarch64 轮子。

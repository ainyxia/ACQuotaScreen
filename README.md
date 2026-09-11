# AC 副屏额度工具

一个面向 Windows 的本地副屏监控工具，用于在小屏幕上显示 Codex 使用状态、额度、重置时间和电脑硬件信息。

## 项目简介

AC 副屏运行在本机，不需要把聊天内容上传到第三方服务。它可以在两种额度来源之间切换：

- **官方 Codex**：读取独立官方 Codex 配置目录中的本地 session 事件，自动识别使用百分比、剩余百分比和额度重置时间。
- **Codex++ 中转站**：通过已保存的中转站 `/v1/usage` 接口读取额度，保留原有配置方式。

切换“显示来源”只影响副屏显示，不会启动、关闭或修改任意一套 Codex 配置。官方 Codex 与 Codex++ 可以保持独立运行。

## 界面预览

### 官方 Codex 额度

![官方 Codex 额度界面](docs/assets/official-quota.png)

### 控制台与显示来源切换

![控制台界面](docs/assets/console.png)

## 功能特性

- 官方 Codex / Codex++ 额度来源切换
- 官方额度自动识别与重置时间显示
- 额度到期后自动等待官方新快照，避免显示过期数据
- 副屏实时显示 CPU、GPU、内存、网络和传感器数据
- 额度、硬件监控、快捷控制三种页面
- 多主题、多布局、背景媒体和自定义 CSS
- Windows 桌面 WebView 控制台与 USB 副屏输出
- 中转站 API Key 使用 Windows DPAPI 加密保存
- 本地会话状态只读取事件类型，不导出聊天内容

## 快速开始

### 运行源码

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

然后打开桌面程序或访问本机控制台。首次使用时，在“中转站”区域添加中转站地址和 API Key；如果选择官方 Codex，则确保独立官方 Codex 已经产生过本地 session 事件。

### 打包 Windows 程序

```powershell
.\.venv\Scripts\pyinstaller.exe --noconfirm ACQuotaScreen.spec
```

生成文件位于 `dist/ACQuotaScreen/ACQuotaScreen.exe`。

## 配置说明

运行配置位于 `%LOCALAPPDATA%\\ACQuotaScreen\\config.json`，不会提交到 GitHub。中转站密钥不会写入项目源码；仓库只包含配置结构和示例逻辑。

官方 Codex 默认读取：

```text
%USERPROFILE%\\.codex-official\\sessions
```

Codex++ 默认使用原有安装和配置，不会覆盖官方 Codex 的登录数据。

## 项目结构

| 文件 | 作用 |
| --- | --- |
| `app.py` | 本地 Flask 服务、轮询、API 和副屏输出 |
| `official_quota.py` | 官方 Codex 本地额度事件解析 |
| `service.py` | 中转站额度接口与响应格式化 |
| `codex_status.py` | Codex 本地任务状态监听 |
| `config_store.py` | 配置保存与 DPAPI 加密 |
| `desktop.py` | Windows WebView 控制台宿主 |
| `templates/` | 控制台和副屏页面 |
| `static/` | 页面脚本、主题和图标 |

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest test_official_quota.py test_codex_status.py test_app.py
```

## 说明

这是一个本地个人工具。使用前请确认你理解所连接的中转站服务及其额度接口行为。项目不包含任何账号、Cookie、API Key 或本机运行配置。

## 许可证

暂未指定开源许可证，欢迎先通过 Issue 交流使用建议。


# Windows 额度气泡

这是按需启动的额度辅助窗口，不是另一套桌宠。它复用 `scripts/codex_usage.py`，通过官方 Codex App Server 读取已登录账户的额度；不读取或上传登录凭据，不安装后台服务、开机启动项或热键监听程序。当前版本的 Windows GUI 和全局快捷键尚未在真实 Windows 设备上验收。

## 安装

需要 Windows、包含 Tk 的 Python 3.10 或更新版本、Windows PowerShell 5.1、已安装并使用 ChatGPT 登录的 Codex CLI。下载并校验支持 Windows 气泡的工具包，将其解压到当前用户可写且之后不会移动的目录。在该目录打开 PowerShell：

```powershell
py -3 scripts\windows_quota.py install --dry-run
py -3 scripts\windows_quota.py install
py -3 scripts\windows_quota.py verify
```

安装器只在当前用户的开始菜单创建 `Codex Pet Atelier\Codex Quota` 快捷方式，建议快捷键为 `Ctrl+Alt+Q`。它记录本机 Python、Codex CLI 和快捷键配置到此工具目录下被 Git 忽略的 `workruns/windows-quota-config.json`；不保存额度或 Token。如果 GUI 环境找不到 Codex，可使用 `install --codex-cli "C:\path\to\codex.cmd"` 指定实际 CLI 路径。系统安全提示和 PowerShell 策略需按正常方式处理，本工具不修改它们，也不需要管理员权限。

安装器检查可读取的桌面及开始菜单快捷方式，遇到相同热键时拒绝覆盖；这不能发现所有系统、应用或不可读取快捷方式的冲突。`Ctrl+Alt` 可能与 AltGr 或键盘输入冲突。先在真实设备上试用；如冲突或影响输入，请自行选择其他组合，例如：

```powershell
py -3 scripts\windows_quota.py install --hotkey CTRL+SHIFT+Q
py -3 scripts\windows_quota.py verify
```

也可使用 Ctrl、Alt、Shift 中两个或三个修饰键，加字母、数字或 F1–F12。设置以系统快捷方式为准，首次创建后 Windows 可能需要时间识别快捷键。不要覆盖或禁用其他程序的快捷键。

## 使用、更新和卸载

在 Finder 对应的 Windows 文件资源管理器、浏览器和 Codex 前台分别按快捷键，确认窗口先显示查询中，然后显示实际额度。检查关闭按钮、窗口获得焦点时的 Esc、重复触发、重试和关闭后进程退出。快捷键和单实例行为必须以本机实际结果为准。窗口仅在运行时处理额度，不会自动轮询或缓存旧结果。

更新时保留原工具目录，使用新版源码替换工具文件后重新执行 `install` 和 `verify`；安装器会检查它创建的快捷方式，不覆盖已被修改或不属于本工具的文件。失败时按命令提示检查保留的备份。移动工具目录后请先从旧目录卸载，再在新目录安装。

```powershell
py -3 scripts\windows_quota.py uninstall
```

卸载仅移除本工具拥有的快捷方式和本地路径配置，不删除宠物、用户文件或其他快捷方式。遇到未登录、CLI 缺失、超时或协议错误，窗口会显示原因；可在已登录的环境中重试，或使用浏览器后备入口：

```powershell
py -3 scripts\codex_usage.py --open
```

这个命令每次重新读取额度并创建本机私有页面，页面属于个人数据，不应分享或提交。也可使用 Codex CLI 的 `/status` 或[官方 Usage 页面](https://chatgpt.com/codex/settings/usage)。

[Microsoft：快捷方式热键](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ishelllinka-sethotkey) · [Microsoft：键盘与 AltGr 冲突](https://learn.microsoft.com/en-us/windows/win32/uxguide/inter-keyboard)

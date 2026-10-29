# macOS 原生额度气泡

这是短时运行的额度辅助工具：它通过现有 Python 查询器调用官方 Codex App Server，不是第二套桌宠，也不会修改 Codex 应用或原生宠物。显示气泡不需要浏览器；只有主动点击“查看官方 Usage”才会打开网页。

## 安装

需要 macOS、Python 3.10+、Swift 编译器，以及已安装并使用 ChatGPT 登录的 Codex CLI。Swift 编译器不可用时，按 Apple 的正常提示安装 Xcode Command Line Tools。无需 sudo，也不会安装 LaunchAgent、登录项或后台热键监听器。

在本项目目录运行：

```sh
python3 scripts/quota_bubble.py install --dry-run
python3 scripts/quota_bubble.py install
python3 scripts/quota_bubble.py verify
```

安装器在当前用户的 `~/Library/Application Support/CodexPetAtelier/QuotaBubble/` 创建一个独立辅助程序及启动脚本。它记录本机 Python 和 Codex CLI 的路径；如 GUI 环境找不到 CLI，可重新安装并显式指定其路径：

```sh
python3 scripts/quota_bubble.py install --codex-cli "/absolute/path/to/codex"
```

安装时存在的 `CODEX_HOME` 会保存在本机配置中。该配置只包含路径，不包含登录凭据。查询结果只在进程内存中处理，不生成额度 JSON。源码在本机编译并使用临时签名封装；项目没有发布经过 Apple 公证的预编译 App，遇到系统信任提示时应按 macOS 正常流程处理，不关闭系统安全保护。

更新时用新版源码重复 `install`，再运行 `verify`；没有重新指定时会保留之前可用的 CLI 和 `CODEX_HOME`。如果新版本验证失败，安装器会尝试恢复旧版本，并提示保留的候选目录；若自动恢复失败，请保留提示中的路径以便人工检查。

## 配置全局快捷键

1. 打开 macOS「快捷指令」，新建名为 `Codex Quota` 的快捷指令。
2. 添加「运行 Shell 脚本」操作，内容填写：

   ```sh
   "$HOME/Library/Application Support/CodexPetAtelier/QuotaBubble/show-quota-bubble"
   ```

3. 如果系统提示脚本操作已停用，请自行决定是否在「快捷指令 → 设置 → 高级」启用「允许运行脚本」。此设置也影响其他脚本操作；仅运行你信任的脚本。
4. 在快捷指令详情中选择「添加键盘快捷键」，按 `⌃⌥⌘U`。若与其他应用冲突，可自行选择其他组合。
5. 分别在 Finder、浏览器和 Codex 前台按组合键，确认气泡先显示查询中，再显示真实额度。再次按同一组合键应关闭，下一次按键应重新查询；不要将从终端启动等同于全局快捷键验收。
6. 在 Codex 中再次打开气泡，点击气泡内空白处后按 Esc，确认气泡关闭并能继续编辑；也检查关闭按钮和重试按钮。无需记录或分享额度数字。

[Apple：在 Mac 工作时运行快捷指令](https://support.apple.com/guide/shortcuts-mac/apd163eb9f95/mac) · [Apple：脚本安全设置](https://support.apple.com/guide/shortcuts-mac/advanced-shortcuts-settings-apdfeb05586f/mac)

## 使用和限制

气泡先显示查询中，再显示实际提供的额度桶和窗口；重试会发起一次新的查询。右上角和底部的关闭按钮会关闭气泡并停止查询；气泡打开时再次按同一全局快捷键也会关闭，下一次按键重新查询。为了不在打开时抢走正在编辑的输入焦点，**先点击气泡，再按 Esc** 才能通过 Esc 关闭；直接在其他应用中按 Esc 不会发送给气泡。该限制不通过全局键盘监听绕过。

如果未登录、找不到 CLI、超时或响应无效，气泡会显示错误；不会用旧数据冒充新结果。剩余比例不表示可发送消息数，正常使用状态以服务端字段为准。关闭后辅助程序退出，不会持续轮询。

## 卸载

关闭气泡后，在本项目目录运行：

```sh
python3 scripts/quota_bubble.py uninstall
```

卸载只移除本工具自己的安装目录；若其中存在未知或被修改的文件，工具会拒绝删除并提示检查。系统「快捷指令」中创建的 `Codex Quota` 需由你自行删除或修改；其他快捷指令和所有宠物文件不受影响。

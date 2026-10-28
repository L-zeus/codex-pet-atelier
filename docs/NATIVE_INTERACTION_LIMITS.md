# 原生宠物与本地预览的交互边界

| 能力 | 范围 |
| --- | --- |
| 自定义图集、宿主状态动画、拖动和右键隐藏 | 官方 Pets 宿主支持；具体入口随应用版本而异。 |
| 一次性读取 ChatGPT Codex 额度 | `scripts/codex_usage.py` 使用官方 App Server；账户和环境需允许读取。 |
| 双击显示额度、右键选择九种动作、暂停和循环 | 本项目的本地预览页；操作不会发送给宿主。 |
| 给原生宠物注册自定义双击或右键菜单 | 官方公开文档未提供接口：`UPSTREAM_UNSUPPORTED`。 |
| 从外部指定原生宠物的动画状态 | 官方公开文档未提供接口：`UPSTREAM_UNSUPPORTED`。 |

来源：[Pets](https://learn.chatgpt.com/docs/pets)、[Codex App Server](https://learn.chatgpt.com/docs/app-server)、[宠物安装链接](https://learn.chatgpt.com/docs/reference/commands)；核对日期 2026-10-28。没有在 `pet.json` 中添加自定义事件字段，也没有更改或注入官方应用。未来若官方提供稳定接口，可让现有预览的动作选择与额度展示接入该接口，并重新验证宿主行为；目前没有宿主适配代码或替代的系统级控制。

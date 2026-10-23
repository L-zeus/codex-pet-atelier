# Codex Pet Atelier

用于 Codex 原生动画宠物的 Python 校验、预览、安装和打包工具。

**V1.4 Code-only toolkit**：本版提供 MIT 许可的代码和文档，不包含可安装的角色美术。三个本地角色的原图来源与衍生再分发权尚未确认，安装 ZIP 和预览 GIF 暂不公开。项目不开发独立桌面客户端。

Small Python tools for native Codex pets. This code-only edition contains no character artwork or pet downloads. Independent community project; not an official OpenAI product.

仓库：[L-zeus/codex-pet-atelier](https://github.com/L-zeus/codex-pet-atelier) · [发行页](https://github.com/L-zeus/codex-pet-atelier/releases) · [自动检查](https://github.com/L-zeus/codex-pet-atelier/actions)

## 开始使用

需要 Python 3.10+、Pillow，以及支持本地自定义 Pets 的桌面应用版本。CI 覆盖 Python 3.12 和 3.14；终端或 IDE 的支持范围与桌面应用不同，参见 [OpenAI Pets 文档](https://learn.chatgpt.com/docs/pets)。

下载工具源码并在项目根目录运行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/validate_pet.py --help
```

Windows 使用 `.venv/Scripts/python.exe`。运行工具不需要 API 密钥或联网生成图片。

自行提供有权使用的真实宠物包，例如 `my-pet/pet.json` 和 `my-pet/spritesheet.webp`，然后：

```bash
.venv/bin/python scripts/validate_pet.py path/to/my-pet
.venv/bin/python scripts/preview_pet.py path/to/my-pet --output-dir workruns/my-pet-preview
.venv/bin/python scripts/install_pet.py path/to/my-pet --dry-run
.venv/bin/python scripts/install_pet.py path/to/my-pet
```

默认安装到 `${CODEX_HOME:-$HOME/.codex}/pets/<id>/`。安装器遇到同名 ID 会拒绝；显式 `--replace` 会先备份。不要在未核对源包和现有宠物时替换。安装后在当前应用的 Pets 设置中刷新并选择，再使用可用的 Show pet 或 `/pet` 入口。入口因版本而异，文件安装成功不等于客户端播放验收。

完整操作和回退见[安装指南](docs/INSTALLATION.md)。未来若有角色 ZIP，其内容应为 `<id>/pet.json` 和 `<id>/spritesheet.webp`，解压后将整个 `<id>` 目录放入 `pets/`，不要多嵌套一层 ZIP 名称目录。本次工具 ZIP 不能解压为角色安装包。

## 角色进度

| 本地角色 | 技术与使用状态 | 公开下载 |
| --- | --- | --- |
| [蓝发鲸鱼女仆](characters/blue-whale-maid.md) | 九行 57 帧；用户报告已检查客户端使用效果 | 暂无，权利待确认 |
| [橙花书灵](characters/orange-scholar.md) | 九行 57 帧；用户报告已检查客户端使用效果 | 暂无，权利待确认 |
| [银白龙姬](characters/silver-dragon.md) | 九行 57 帧；用户报告已检查客户端使用效果 | 暂无，权利待确认 |

三套现有动画共 171 帧，V1.4 保留原字节。用户报告不等于逐项九状态的独立验收证据，细分项目见[人工检查清单](docs/MANUAL_GUI_CHECKLIST.md)。原始参考图作者未知；本地动画采用 AI 辅助生成与确定性图像处理，不能据此宣称原始角色原创。

## 工具与验证

| 工具 | 用途 |
| --- | --- |
| `validate_pet.py` | 检查 manifest、安全路径、1536×1872 静态 RGBA 图集、57 有效帧与 15 空格 |
| `preview_pet.py` | 按九行官方时长生成 GIF 和深浅底接触图 |
| `audit_motion.py` | 比对 GIF 解码帧、时长和图集，记录动作边界诊断 |
| `install_pet.py` | dry-run、冲突保护、替换备份及安装后哈希检查 |
| `package_release.py` | 只有哈希绑定的权利、视觉、九状态 GUI 证据通过才生成角色 ZIP |
| `package_code.py` | 按明确文件白名单导出代码 ZIP，并校验成员、内容和 SHA-256 |
| `audit_publication.py` | 检查 Git 树及历史中的私有路径、媒体和有限敏感模式 |

其他制作辅助命令见[制作流程](docs/PRODUCTION.md)。所有脚本支持 `--help`。结构检查、工具测试和 CI 不证明角色美术授权或真实 GUI 播放。

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/audit_publication.py --history
.venv/bin/python scripts/package_code.py --output dist/codex-pet-atelier-code-1.4.0.zip
.venv/bin/python scripts/package_code.py --check dist/codex-pet-atelier-code-1.4.0.zip
```

代码 ZIP 含 `SHA256SUMS`、`RC_MANIFEST.json` 及许可范围说明。构建器拒绝覆盖已有输出。CI 运行内容审计、测试、构建和独立解压测试，权限为只读；发布由维护者在检查后执行。扫描不是无秘密证明，提交身份仍须单独检查。

## 常见问题

- **没有角色图片或下载包**：本次发行只含工具；角色权利未核实，不能从代码生成现有角色资源。
- **已安装但不显示**：核对 CODEX_HOME、目录层数、manifest ID 和当前应用的 Pets 功能；刷新并重新选择。IDE 扩展不提供桌面悬浮入口。
- **只有静态图**：系统减少动态效果设置会影响播放，先核对设置；不要用静态显示证明九行动画通过。
- **同名 ID 冲突**：先比对哈希；相同包无需重装，需要替换时保留安装器生成的备份。

## 许可证与贡献

自有代码和文档采用 [MIT](LICENSE)。角色设计、原始立绘、母图、图集、GIF 和截图不在 MIT 范围内，也未采用 CC 许可。见[素材许可边界](ASSET_LICENSE.md)、[来源与署名](CREDITS.md)、[五图权利清单](docs/ASSET_RIGHTS.md)。私人参考图、生成中间文件、报告及原有 Git 数据库不进入公开发行。

贡献前阅读[贡献规则](docs/CONTRIBUTING.md)；制作约束见[项目方案](docs/PROJECT_PLAN.md)和[角色规范](docs/CHARACTER_SPECS.md)。

# Codex Pet Atelier

三套为 Codex 原生 Pets 制作的角色动画，以及校验、预览、安装和打包工具。项目由社区维护，**不是 OpenAI 官方产品**。

## 下载 V1.7

| 角色 | 原生宠物包 |
| --- | --- |
| 蓝发鲸鱼女仆 | [blue-whale-maid-v17-v1.7.0.zip](https://github.com/L-zeus/codex-pet-atelier/releases/download/v1.7.0/blue-whale-maid-v17-v1.7.0.zip) |
| 橙花书灵 | [orange-scholar-v17-v1.7.0.zip](https://github.com/L-zeus/codex-pet-atelier/releases/download/v1.7.0/orange-scholar-v17-v1.7.0.zip) |
| 银白龙姬 | [silver-dragon-v17-v1.7.0.zip](https://github.com/L-zeus/codex-pet-atelier/releases/download/v1.7.0/silver-dragon-v17-v1.7.0.zip) |

[全部母图、27 个 GIF 与浅深底接触图](https://github.com/L-zeus/codex-pet-atelier/releases/download/v1.7.0/codex-pet-atelier-v1.7.0-art-previews.zip) · [SHA-256 校验和](https://github.com/L-zeus/codex-pet-atelier/releases/download/v1.7.0/V1_7_SHA256SUMS.txt) · [素材署名与许可](https://github.com/L-zeus/codex-pet-atelier/releases/download/v1.7.0/ASSET_ATTRIBUTION.txt) · [Release 页面](https://github.com/L-zeus/codex-pet-atelier/releases/tag/v1.7.0)

每个宠物 ZIP 包含 `<角色 ID>/pet.json` 和 `<角色 ID>/spritesheet.webp`。图集为 1536×1872 RGBA WebP，8 列×9 行、单格 192×208，包含 57 个动画帧和 15 个透明空格。预览包包含三张本轮基准图、每个角色的 9 个 GIF 和浅深底接触图。

## 校验和安装

将下载的附件与 `V1_7_SHA256SUMS.txt` 放在同一目录；如果只下载部分附件，使用 `shasum -a 256 <文件名>` 与清单中对应行比对。下载全部附件时可运行：

```bash
shasum -a 256 -c V1_7_SHA256SUMS.txt
```

安装需要 Python 3.10+、Pillow 和支持本地自定义 Pets 的 Codex 桌面应用。下载本仓库源码并在项目根目录运行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
mkdir -p workruns/downloaded-v17
unzip ~/Downloads/blue-whale-maid-v17-v1.7.0.zip -d workruns/downloaded-v17
.venv/bin/python scripts/validate_pet.py workruns/downloaded-v17/blue-whale-maid-v17
.venv/bin/python scripts/install_pet.py workruns/downloaded-v17/blue-whale-maid-v17 --dry-run
.venv/bin/python scripts/install_pet.py workruns/downloaded-v17/blue-whale-maid-v17
```

橙花和银龙使用各自 ZIP 与目录名，步骤相同。默认安装到 `${CODEX_HOME:-$HOME/.codex}/pets/<id>/`；遇到同名 ID 时安装器会拒绝覆盖，明确使用 `--replace` 时先备份。安装后在支持 Pets 的客户端刷新并选择角色，再使用可用的 Show pet 或 `/pet` 入口。Windows 使用 `.venv/Scripts/python.exe`。完整步骤和回退见[安装指南](docs/INSTALLATION.md)。

## 验收范围

三套图集、各 9 个 GIF 和隔离安装已通过机器检查。项目所有者报告这三套候选可在 Codex 客户端显示及左右移动；这是**用户报告的基础兼容性结果**，未独立核实测试机器的安装目录。用户也确认检查过 27 个离线动画并接受当前效果。未自然触发或未单独记录的原生状态保持 `NOT_RUN`，不据此声称九种状态都有客户端录屏。蓝鲸发丝仍有少量粉紫边，银龙发丝与翼缘有轻微绿色。

## 工具

| 工具 | 用途 |
| --- | --- |
| `validate_pet.py` | 检查 manifest、资源路径、图集尺寸与透明格 |
| `preview_pet.py` | 生成九个 GIF 和浅深底接触图 |
| `audit_motion.py` | 检查 GIF 解码帧、时长及与图集的对应关系 |
| `install_pet.py` | dry-run、冲突保护、备份及安装后哈希检查 |
| `package_release.py` | 按哈希核验素材权利、离线视觉及客户端基础验收后打包 |
| `package_code.py`、`audit_publication.py` | 代码候选打包及公开 Git 内容检查 |

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/audit_publication.py --history
```

代码 CI 检查工具与 Git 内容；它不替代动画视觉、权利或客户端验收。历史 [V1.5 code-only](https://github.com/L-zeus/codex-pet-atelier/releases/tag/v1.5.0-code-only) 发行保留。

## 许可证

本项目代码和文档使用 [MIT](LICENSE)。本轮三张指定基准图及其衍生动画、图集、GIF 与角色包使用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；转载或改编应保留署名、许可链接及修改说明。范围和来源声明见 [ASSET_LICENSE.md](ASSET_LICENSE.md)、[CREDITS.md](CREDITS.md) 与 [素材权利记录](docs/ASSET_RIGHTS.md)。其他历史参考素材不因此获得许可。

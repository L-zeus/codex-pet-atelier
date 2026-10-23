# 本地安装与真实验收

这些步骤适用于已经生成并通过视觉 QA 的本地角色包。若报告为 `ART_PENDING` 或 `QA_FAILED`，先完成制作或修复；不要把缺失的图集替换成测试夹具。素材权利未确认时，候选包与预览保存在 `workruns/`，不放入公开仓库。

## 1. 检查与预览

Code-only toolkit 不附带三角色源包。以下命令假定你已经有一个有权使用、通过视觉检查的真实包 `path/to/blue-whale-maid/`；替换为实际路径，目录名必须与 `pet.json` 的 `id` 一致。不要把工具 ZIP 当作角色 ZIP。

```bash
.venv/bin/python scripts/validate_pet.py path/to/blue-whale-maid --report reports/local-check/validation.json
.venv/bin/python scripts/preview_pet.py path/to/blue-whale-maid --output-dir workruns/local-check/blue-whale-maid
.venv/bin/python scripts/audit_motion.py path/to/blue-whale-maid --preview-dir workruns/local-check/blue-whale-maid --report workruns/local-check/blue-whale-maid/motion-audit.json
```

报告输出必须在源包外，也不能位于安装根的 `pets/` 或 `pet-backups/` 内；这些路径会在安装发生前拒绝。预览先检查所有目标链接，再原子替换输出，不能通过链接覆盖输入。

校验失败退出码非零。修复后重新执行；不能改写报告为 PASS。逐一查看九个真实 GIF，确认原画保真、方向、动作语义、脚底基线、首尾循环、尺寸稳定、发饰与道具、翼尾及白色/蓝色边缘。校验器不替代视觉判断。

预览同时输出 `contact-sheet.png`（浅底）与 `contact-sheet-dark.png`（深底）。`audit_motion.py` 记录含首尾衔接的逐帧像素差、基线/高度范围、GIF解码帧哈希、与图集按项目调色板/alpha规则渲染后的内容一致性、官方时长及72个跨状态位置诊断；这些是诊断量，不自动判定动作连贯或角色一致。校验器拒绝整行相同帧和整行仅平移同一姿态，但不同像素仍可能是伪动画，必须视觉检查。

## 2. 安装预演

```bash
.venv/bin/python scripts/install_pet.py path/to/blue-whale-maid --dry-run --report reports/local-check/install-dry-run.json
```

默认安装根目录为 `${CODEX_HOME:-$HOME/.codex}/pets/`。`--codex-home PATH` 可以显式指定；该参数是 Codex HOME，不是 `pets` 子目录。预演不写入宠物目录。已有相同 id 时默认也会拒绝，属于冲突保护；先运行下方只读复核，哈希匹配就无需重装，不要为了让 dry-run 成功而使用替换选项。

检查目标目录、源路径、角色 id 与校验结果。源包、目标目录及资源路径不得通过软链接或路径穿越指向无关位置。不得手工用 `cp` 绕过安装器的冲突与安全检查。

## 3. 实际安装

只有结构与视觉通过后才运行：

```bash
.venv/bin/python scripts/install_pet.py path/to/blue-whale-maid --report reports/local-check/install.json
```

默认遇到同名目录拒绝安装。若确实需要替换现有同名角色，先取得用户对该替换的明确授权，再使用 `--replace`；工具须先创建备份，并在报告中记录备份路径和安装后哈希。不要删除备份，不修改其他角色目录。

安装器的成功仅证明文件复制与复核完成，不证明当前客户端加载或播放成功。

## 4. 已安装文件只读复核

```bash
.venv/bin/python scripts/validate_pet.py "${CODEX_HOME:-$HOME/.codex}/pets/blue-whale-maid" --report reports/local-check/installed-validation.json
shasum -a 256 path/to/blue-whale-maid/{pet.json,spritesheet.webp}
shasum -a 256 "${CODEX_HOME:-$HOME/.codex}/pets/blue-whale-maid/"{pet.json,spritesheet.webp}
```

逐文件比对源/目标哈希。macOS 可用 `stat -f '%Sp %Su %N'` 查看目录与两文件权限；当前默认目录755、文件644，当前用户可读且无软链接。官方文件合约未规定必须使用此数值，读取权限与安全目标路径仍需实际核对。

## 5. 客户端人工验收

按[人工 GUI 检查清单](MANUAL_GUI_CHECKLIST.md)执行三个角色、九个状态与状态切换。入口以实际客户端版本为准，可用入口通常为 Settings → Pets → Refresh → 选择角色，当前公开文档以 ChatGPT 桌面端为例，Codex 版本以实际界面为准，再用 `/pet` 或 Show pet 显示。系统“减少动态效果”会让宠物使用静态帧，检查动画前先记录此设置。来源：[官方 Pets 文档](https://learn.chatgpt.com/docs/pets)。

Computer Use 已明确拒绝控制 `com.openai.codex`；不得改用其他 GUI 自动化方式绕过。不能操作 GUI、状态未触发或没有实际观察时保持 `MANUAL_GUI_CHECK_REQUIRED` / `NOT_RUN`。截图只能证明对应画面，不能覆盖其他八个状态。GUI 截图/录屏含角色衍生美术，仍留在私有目录。

## 6. 回退

若是首次安装，先关闭该角色并切换到原宠物，再移走本次新建的同名目录。若有替换备份，保留当前目录副本后再恢复报告记录的备份；恢复前检查目标路径与 id，不能批量清理整个 `pets` 目录。回退操作及复核结果也需记录。

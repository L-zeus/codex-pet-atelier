# 私有制作流程

先完整阅读 `AGENTS.md`、`CODEX_PROMPT.md`、[项目方案](PROJECT_PLAN.md)、[角色规范](CHARACTER_SPECS.md)与[权利说明](ASSET_RIGHTS.md)。本流程描述操作要求，不是完成记录；当前事实以本地 `reports/V1_3_FINAL_REPORT.md` 与机器摘要为准；`FINAL_REPORT.md` 是 V1 蓝发历史记录。

## 准备

确认当前工作目录、Git 状态、Python/Pillow、Codex 版本和 HOME、Pets 目录。若目录尚未初始化 Git，如实记录，不跳到其他仓库执行 Git 操作。对五张原图重新计算尺寸与 SHA-256，并核对本地清单。所有原图、生成图、预览、机器路径与执行日志留在忽略目录。

实际定位官方 `hatch-pet` 和 `imagegen`。如需获取 hatch-pet，使用官方 skill-installer，从 `openai/skills` 获取并记录来源及版本/哈希；不要执行第三方安装脚本。将工具的本地副本与生成工程代码区分，不把下载工具作为自己的实现。

## 固定母图

三个角色各自独立建 run 和母图，不混用参考。橙花以02面部与比例为主、01交叉核对服饰；银白只用其唯一原图，保留独立云灵。蓝发主参考 `blue-whale-maid-02.jpg`，辅助参考 01。两图衣服长度和肩部结构不同，按[蓝鲸角色规范](../characters/blue-whale-maid.md)固定 02 的服装。用 `prepare_pet_run.py` 创建私有 run，生成 base、确认识别特征后复制为 canonical base。不能为适应小尺寸而整体改成更大头眼或另一套女仆装。

主参考/母图/辅助参考的角色应在 imagegen 调用中明确。通过内置 imagegen 实际生成，不用本地像素变形或随机绘图替代缺失的美术。遇到额度、网络或生成能力阻塞，保存实际错误并记录 `ART_PENDING`，继续完成不依赖美术的工具工作。

## 逐行动作

遵循官方 `imagegen-jobs.json` 依赖。先制作 idle 与 running-right，检查身份与步态后再做其余行。每次调用附该行布局 guide 和 canonical base；保留原图风格与配饰。running-left 原则上独立生成，非对称头饰、围裙鲸图与尾巴不能无检查镜像。

官方行顺序、帧数和预览时长见[项目方案](PROJECT_PLAN.md)。`running` 是任务处理中，不能重复跑步行；waiting 是期待用户输入，不能直接复用 idle。禁止悬空符号、速度线、地面阴影、白色背景、网格、标签和跨格效果。

选中原始生成文件后才复制到对应 decoded 路径并标记生成完成；生成完成不等于视觉通过。保存 prompt、输入引用、产物路径、哈希、实际调用结果、逐行 QA 与修复原因。未通过或仍需修复时保留原始证据。

## 确定性处理与 QA

使用官方脚本从真实行图提取帧、检查、合成 1536×1872 图集、生成 contact sheet 与九个 GIF。确定性工具只负责几何、格式、透明处理和预览，不补画缺失动作。

带独立云灵的行若被官方最近中心分组错配，可用 `extract_companion_frames.py STRIP --state STATE --output-dir NEW_DIR --hatch-tools PATH` 处理实际生成图。它调用官方提取模块，以横向顺序配对一个主体和一个独立伙伴，面积/数量/形状不明确时拒绝处理；少量断开的噪点删除记录在 `pairing-receipt.json`。共享视窗保持行内比例与基线，不能为满足连通域检查而把云灵黏到人体。必须逐帧复核配对、翼尾拓扑和是否误删饰品，官方结构通过不替代该检查。

GIF 编码需单独验收：RGBA 转 GIF 的调色板可能引入源 WebP 中没有的彩色碎点。项目 `preview_pet.py` 显式保留透明调色板索引，并回读帧数与时长；仍需深浅底视觉对照，不接受只看文件存在。

先检查提取是否造成角色尺寸跳变或脚底漂移；原始行图稳定时可按官方说明尝试 stable-slots，再重跑后续检查。原始图本身裁断、动作错误或身份漂移时，重新生成失败行。蓝发、侧鳍与白裙边缘需在深浅背景上看残边；透明像素 RGB 清零不能掩盖可见色污染。

若官方洋红抠像输出仍出现可见残边，可对已提取的真实 RGBA 帧使用 `scripts/clean_chroma.py SOURCE_FRAMES --output-dir NEW_CANDIDATE_DIR --band 8`。工具仅在透明边界附近去污染 RGB 与 alpha，不生成、复制、移动或缩放动作帧；原图与原帧保持不变。该算法不适用于含真实洋红设计的角色，无法精确恢复原始抗锯齿，薄发丝使用保守 fallback。输出统计与哈希报告仅证明处理过程，必须对照深浅背景复查，不能据此写视觉 PASS。

白发/淡紫等浅色边缘若因默认反解产生绿色或青色，可用 `--rgb-mode neighbor` 生成另一独立候选：alpha仍按局部模型估计，RGB取已观测的邻近可靠前景。此模式不会补画缺失轮廓，可能降低细小边缘色彩差异；同样须逐帧复核，不能仅凭去洋红计数下降验收。旧候选和源帧不覆盖。

默认仍保护边带以内的角色颜色。只有目视证明确为内部抠像污染、且原设计没有洋红时，才显式使用 `--include-interior-key`；若原设计确实仅暖色/中性色，而修复后仍留下蓝紫污染，可对失败行单独选 `--foreground-palette warm`，从附近已存在的暖色前景取样。该选项不能用于银白龙姬的真实淡紫、其他蓝紫角色或未知配色。保留逐像素变化、alpha与源文件哈希，重新检查细发丝、肤色、刺绣及深浅底轮廓后才接受。

逐行记录 `PASS` / `FAIL` / `NOT_RUN`，说明人工实际查看的内容。结构通过不能单独证明语义、连贯或保真。最终保存真实 `final/spritesheet.webp`、`final/validation.json`、`qa/contact-sheet.png`、`qa/previews/*.gif` 与 `qa/review.json`。缺失产物不建空文件。

## 安装与发行

本地包采用 `<id>/pet.json` + `<id>/spritesheet.webp`，私有候选留在 `workruns/`。按[安装指南](INSTALLATION.md)完成校验、预演、真实安装及 GUI 验收。角色权利 `UNVERIFIED` 时本地可制作/验收，公开分发保持阻塞。

发行打包命令与证据字段以 `scripts/package_release.py --help` 为准。包仅包含 `<id>/pet.json` 与 `<id>/spritesheet.webp`。需要绑定实际图集哈希的结构、视觉、GUI 验收以及明确的公开许可证明。打包成功不授权推送 GitHub；发布前仍需用户明确授权并审计暂存区、跟踪文件与 ZIP 内容。

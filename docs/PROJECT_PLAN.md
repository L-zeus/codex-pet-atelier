# Codex Pet Atelier — 项目实施与验收方案

更新：2026-10-25。本文保留实施规范与路线，完成状态须结合实际报告。

## V1.5 Code-only 发行与新绘基础反馈

本次只发布代码 ZIP 和 SHA-256 校验清单，沿用现有公开仓库和历史。新绘三角色的基础显示与运动由用户报告通过，记录 `USER_REPORTED_GUI_BASIC_PASS`；九状态逐项观察未完成，不填写全项通过。美术权利仍为 UNVERIFIED，图集、GIF、原图和角色安装 ZIP 不上传。

## 最终交接：新图本地重建

本轮以三张新定稿图重建 `blue-whale-maid-renewal`、`orange-scholar-renewal`、`silver-dragon-renewal`，复用现有原生 Pets 工具链，保留旧三套资源、安装和 Git 历史。新角色的当前视觉基准见 [角色规范](CHARACTER_SPECS.md)，不套用旧版蓝鲸短裙全肩、书本侧别或旧云灵描述。

用户补充的新图参考了来源不明的旧立绘，公开权利仍为 `UNVERIFIED`。三张图、重建动画、GIF和截图留在本机；`assets/public_canonical/` 的名称不构成公开许可。先完成能够完成的生成、修复、校验、私人安装候选和文档；生成不完整保持 `ART_PENDING`，视觉未通过不称为可用。代码与文档继续采用 MIT；V1.5 正式代码发行使用 `v1.5.0-code-only` 标签，旧 rc1 候选保留。GitHub 美术发行继续阻塞，不能以新图、AI 重绘或 LOCAL_ONLY ZIP 代替权利及客户端证据。

## V1.4 发行范围

用户已报告三个角色客户端使用效果检查完成，并授权符合权利条件的 GitHub 发布；随后明确确认代码和文档采用 MIT。三套171帧保留原字节，不重新生成。V1.4 以 Code-only toolkit 范围准备和发行独立公开历史、README、MIT/美术许可分界、白名单 ZIP、SHA-256 与 Python 3.12/3.14 CI。实际发布状态以 GitHub 和本地 V1.4 摘要为准。

五张原图来源/衍生再分发权仍未确认，美术许可证未选择，角色 ZIP/GIF 不公开。GUI 记录为 USER_REPORTED，不将九状态自动改为 PASS。下方 V1–V1.3 是历史状态，不代表当前 MIT 或用户发布授权仍待确认。

## V1.3 Final Hardening 与本地代码候选

保留现有三套171帧；独立审查全部九行、状态边界、短行动作道具与定位。工程侧用合成夹具复现并修复源包输出覆盖、GIF内容未绑定、动态图集等具体缺陷。代码候选按逐文件白名单导出，包含未选择许可证声明与SHA-256清单，拒绝Git数据库和所有美术；实际解压后在隔离环境安装依赖、运行工具及安装验证。流程与事实分别见[代码候选说明](CODE_ONLY_RELEASE.md)及私有 `reports/V1_3_FINAL_REPORT.md`、`reports/V1_3_MACHINE_SUMMARY.json`。

原生GUI、素材公开授权、代码许可与公开身份仍需用户确认；本轮不执行GitHub发布，不改写历史。状态切换是官方固定行间硬切，离线观察不代表客户端中断调度已验证。

## V1.2 交付前复核

复核三套现有源包与安装包、171个有效帧及27个GIF，保留合格美术与历史报告。修复工具/文档的实际问题；为代码仓库增加私有素材与敏感文本门禁。当前完整证据见私有 `reports/V1_2_FINAL_REVIEW.md`、`reports/V1_2_MACHINE_SUMMARY.json`。

剩余门禁仍为原生客户端人工播放、素材公开授权、代码许可证选择及用户显式发布授权。[人工清单](MANUAL_GUI_CHECKLIST.md)与[代码公开方案](CODE_ONLY_RELEASE.md)分别描述操作；本轮不公开发布。

## V1.1 执行范围

在 V1 蓝发最终资源和安装不变的基础上，完成 `orange-scholar`、`silver-dragon` 的本地制作。本轮已实读五张参考图并复核哈希，核实本地官方工具与核验时官方文件一致；两位新角色各有私有 canonical master、九行 57 帧、九 GIF、深浅接触图与实际报告。橙花采用02面部与比例、01交叉核对服饰；银白只采用其唯一龙族参考，云灵固定为独立辅助元素。

路线：固定主视觉 → 待机与右移质量检查 → 独立左移及其余六行 → 57帧透明提取与边缘修复 → 九GIF/深浅接触图/逐帧视觉 → 结构验证与干净重建 → dry-run/本地安装/哈希复验。失败行局部重做，保留原始失败稿，不以几何变换补造动作。

每个角色独立记录 `GENERATED`、`MACHINE_VALIDATED`、`OFFLINE_VISUAL_PASS`、`FILES_INSTALLED`、`GUI_VERIFIED`、`RIGHTS_VERIFIED`、`PUBLIC_RELEASED`。原生客户端控制存在已知安全限制，本轮不尝试绕过；播放验收留给人工。权利未确认，所有美术留在忽略目录，无GitHub推送或公开Release。

实际结果、测试与未完成项以本地 `reports/V1_1_FINAL_REPORT.md`、`reports/V1_1_MACHINE_SUMMARY.json` 为准；下方 V1 历史阶段保留作为既有流程，不限制 V1.1 的双角色制作。

已完成：双角色生成、局部姿态/色污染/云灵分组修复、结构与离线视觉验收、44项工具测试、相同字节重建、dry-run、本地安装及哈希复验。剩余：用户人工原生播放验收、素材公开权利确认；均未通过，不创建公开 Release。

## 0. 目标与非目标

唯一目标：将用户提供的五张二次元参考立绘整理为三个角色系列，以最小必要变化制作**可以在支持 Pets 的 Codex 桌面端加载的原生自定义动画宠物包**。先完成私有本地制作与验收；GitHub 公开展示须另行通过素材权利与用户发布授权门禁。

V1 的 Release 验收目标：**蓝发鲸鱼女仆**完整、可安装、九行动画通过 QA；另两组建立角色设计文档，明确未完成。

不做：Tauri/Electron/Swift 桌面应用、独立浮窗、Agent hooks、MCP 服务、多 Agent 适配、网站后端、Live2D、拟人聊天或宠物养成。

## 1. 用户参考图映射

- `references/private/orange-scholar-01.jpg` 与 `orange-scholar-02.jpg`：橙发、花饰、书本、白黑橙礼裙；同一个橙花书灵人物的两张参考。
- `references/private/silver-dragon-01.jpg`：银白长发、紫眸、龙角、翼、龙尾、浅紫白裙；银白龙姬。
- `references/private/blue-whale-maid-01.jpg` 与 `blue-whale-maid-02.jpg`：蓝发、海洋侧鳍、深蓝女仆裙、围裙鲸鱼图案、鲸尾；同一个蓝发鲸鱼女仆人物的两张参考。

**蓝发角色的基准姿态**取 `blue-whale-maid-02.jpg`：固定较短裙摆、完整肩部与长袖、深蓝领结和蓝色宝石。01 的长裙与露肩结构不可混入；另一张仅用于确认共通的侧鳍、尾鳍及配色。原图只能在本机/私有制作目录用作参考，不能因打包到此本地启动包就推断可以公开再分发。

先前在 ChatGPT 生成的概念图、图集仅视作实验草图，不作为经过认证的成品或唯一母图；之前的图集尺寸 1136×1385，不符合官方 1536×1872 合约。

## 2. 保真制作约束（优先级高于新奇感）

必须保留：发色和发型走向、眼睛颜色及神态、额头/发夹/发箍、主要衣服结构及主辅色、角色专属道具（橙花角色书本，白龙龙角/翼/尾，蓝鲸鲸尾/耳鳍/围裙图案）。

允许微调：局部人体比例、略显笨重的褶皱、遮挡关系、抗锯齿和边缘清理；当缩小到 192×208 时，可以简化无法辨认的小刺绣纹理。保持原画清爽的非像素二次元线稿和上色风格。不强制大头 Q 化、不改发长、不换服装、不扩大眼睛、不添加大量新配件。

要有固定角色主视觉（canonical base），九行动画的每一帧均以该角色定稿为参照。动画中可改变姿态和表情，不能每行换脸、换衣服、换比例。

## 3. Codex 原生动画合约（v1）

- 总图：**1536×1872** 像素；8 列×9 行；每格 192×208；透明 WebP 或 PNG，正式包使用 `spritesheet.webp`。
- 角色包：`pets/<id>/pet.json` + `pets/<id>/spritesheet.webp`。
- `pet.json` 需包含 `id`, `displayName`, `description`, `spritesheetPath`，sprite 引用使用相对文件名。
- 不画格线、行标题、白色背景、相邻帧之间的额外 gutter，不得溢出单格。

| 行（0-based） | 动画 | 使用帧数 | 每帧时长（ms） | 制作含义 |
|---:|---|---:|---|---|
| 0 | idle | 6 | 280, 110, 110, 140, 140, 320 | 轻微呼吸、眨眼；安静可循环 |
| 1 | running-right | 8 | 前 7 帧 120，末帧 220 | 朝右移动 |
| 2 | running-left | 8 | 前 7 帧 120，末帧 220 | 朝左移动；如镜像会破坏不对称饰物，需重新绘制 |
| 3 | waving | 4 | 前 3 帧 140，末帧 280 | 抬手挥手再收回 |
| 4 | jumping | 5 | 前 4 帧 140，末帧 280 | 蓄力、起跳、最高点、下落、落地 |
| 5 | failed | 8 | 前 7 帧 140，末帧 240 | 失落、报错或无奈，仍保持人物本体一致 |
| 6 | waiting | 6 | 前 5 帧 150，末帧 260 | 等待用户输入/审批，不能与 idle 无区别 |
| 7 | running | 6 | 前 5 帧 120，末帧 220 | **任务处理中**，不是身体奔跑；专注思考或手部微动作 |
| 8 | review | 6 | 前 5 帧 150，末帧 280 | 检查、审阅或认真观察 |

共 **57 个有效帧**，另有 **15 个透明空格**。按官方 `animation-rows.md` 的对应时长预览，不能每行只用一张图平移复制。

参考：
https://github.com/openai/skills/blob/main/skills/.curated/hatch-pet/references/animation-rows.md

## 4. 生产技术路线

首选**官方 `hatch-pet` Skill** 的准备→分行动作生成→精灵帧提取→图集合成→校验→接触图/逐行 GIF 预览→本机安装流程。图片生成走 Skill 要求的 `$imagegen`，不使用脚本随机扭曲、平移或镜像静态原画伪造完成动画。确定性 Python 脚本只负责读文件、转换、校验和打包。

仓库工程辅助工具：

- `scripts/validate_pet.py`：校验 JSON、相对资源路径、WebP 规格、透明通道、有效与空帧；输出 machine-readable JSON。
- `scripts/preview_pet.py`：从图集按官方帧数及每帧时长输出九个独立 GIF，可选 contact sheet。
- `scripts/install_pet.py`：本机安装、目录检查、默认拒绝同名目标，明确授权替换时先备份、`--dry-run`，不执行来自互联网的 shell 脚本。
- `scripts/clean_chroma.py`：只修复已生成帧的洋红透明边缘，保留原帧与尺寸，输出修复候选及统计，必须再做视觉 QA。
- `scripts/package_release.py`：仅在全部验收通过后打包 `pet.json` 和 `spritesheet.webp`，ZIP 中保留 `<pet-id>/` 目录。
- `tests/`：负样本测试（错误尺寸、无 alpha、空有效格、非透明空格、缺失 JSON 字段、危险文件路径等）。

上述工具的当前结果以本地最新版本报告和真实测试输出为准；V1 的 `reports/FINAL_REPORT.md`、`reports/MACHINE_SUMMARY.json` 保留为历史证据。机器校验不能替代视觉及实机验收。运行入口和操作说明见 `README.md`、`docs/INSTALLATION.md`。

## 5. QA 与发布门禁

自动校验为必要条件，但不是充分条件：

1. 文件合约检查：`id` 等于目录名、JSON 可解析、路径仅指向本包资源且不会逃逸目录、画布与格子尺寸准确、RGBA alpha 合法。
2. 帧数检查：九行 57 帧全部非空，15 个剩余格子全透明；处理 alpha=0 的残留颜色问题。
3. 动画检查：行语义清晰，有实际姿态变化，接续顺畅，首尾无明显跳变；运动方向正确，`running` 必须表现工作而非跑步。
4. 视觉检查：所有行服装、发饰、发色、眼睛、鲸尾保持统一；蓝发海洋配色不出现不明蓝色轮廓残影/白色抠图边；角色完整落在单格里。
5. 安装检查：在本机支持 Pets 的桌面应用刷新并选择角色，使用 `/pet` 验证实际显示及状态切换；截取真实证据，不能用文件存在代替实机成功。
6. 权利检查：每个即将公开的图像及其衍生资产有可核验的允许公开分发及适用许可。**未知权利 = 不公开，不宣称完成 Release**。
7. Release 检查：全套文件齐全、安装说明可复现、预览与产物对应、Git 仓库不含私有参考图、凭据或构建垃圾。

结果分级：
- `READY_TO_PUBLISH`：文件/视觉/实机/权利全部通过；允许准备 GitHub Release（推送需用户授权）。
- `LOCAL_ONLY_RIGHTS_PENDING`：技术层面可本地试用，但来源授权未确认，不得公开宠物素材。
- `ART_PENDING`：生成工具不可用或尚未完整出片，只有工程工具或文档可交付。
- `QA_FAILED`：存在画布、帧、动画、实机缺陷；禁止称为可用版。

## 6. V1 历史分阶段执行（不表示当前制作状态）

**Gate A — 环境与素材**：扫描本机 Git、Codex、Python、Pillow；确认官方 Skill 是否存在及其脚本路径；读五张参考图，算哈希并建本地权利清单；保障 `.gitignore` 生效。

**Gate B — 首发角色视觉定稿**：生成 `blue-whale-maid` 母图（必要时多轮调整）；再做全部 9 行、57 帧；出 contact sheet 和 GIF；修复失真。

**Gate C — 工程与测试**：实现四个脚本，添加可运行的测试与 CI；拒绝以空文件、错误尺寸或重复帧冒充通过。

**Gate D — 本机验收**：复制角色包至 `${CODEX_HOME:-~/.codex}/pets/blue-whale-maid/` 并复核选择与播放，留下证据。

**Gate E — 开源发布**：更新真实 README、版权声明、CHANGELOG、打包正式 ZIP；符合权利条件才执行公开发布。第二、三角色仍列为制作中，不放假包。

## 7. GitHub 交付范围

根目录：`README.md`、`AGENTS.md`、`.gitignore`、代码许可文件（仅覆盖代码，需正确声明范围）；角色权利清单；`characters/` 已核实公开许可的展示素材或文字说明；`pets/blue-whale-maid/` 在通过所有验证并取得明确公开授权后才允许进入仓库；此前本地候选包留在 `workruns/`；`scripts/` 和 `tests/`；`docs/` 包含安装、制作与贡献文档；`.github/workflows/validate.yml`；GitHub Release ZIP。

不要把 `references/private/`、工作生成临时文件、个人机器路径、未经许可的原画上传到 GitHub。

## 8. 主要风险及处理

- **画风不稳定**：固定母图并统一所有生成行的参考，发现脸、服饰漂移即重做该行。
- **像素格太小**：先在原尺寸生成，单格缩放对照做微型预览，只删不重要纹理。
- **模型不会制作真正动画**：如缺少 `$imagegen`，标注 `ART_PENDING`，完成脚本/文档，不谎称做完。
- **单侧配饰错误镜像**：蓝发角色的头饰、围裙图案、尾巴需要特别校验，必要时独立绘制左右行。
- **版权不明**：保持本地私人仓库，不自动提交图像，不以 MIT 授权角色素材。

## 9. 验收材料

每次候选 Release 保存实际检测结果：

- `reports/FINAL_REPORT.md` 和 `reports/MACHINE_SUMMARY.json`：可安装情况、九行动画 QA、保真问题与处理、版权 Gate、剩余 Blocker。
- `reports/validation.json`：机器校验结果，不得手工伪造。
- `workruns/<run>/qa/contact-sheet.png` 和 `workruns/<run>/qa/previews/*.gif`：实际图集产出的预览。
- 实机选择/显示截图（公开前需确认是否包含隐私信息）。

注：此处的 `reports/` 指构建输出，仅在证据真实、无隐私风险且符合版本管理方案时归档其中可公开部分。

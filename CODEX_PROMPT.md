# Codex Pet Atelier — 维护与验收入口

在现有仓库继续工作，先读 `AGENTS.md`、`README.md`、`docs/PROJECT_PLAN.md`、`docs/CHARACTER_SPECS.md` 和 `docs/ASSET_RIGHTS.md`。本文件已取代初期 V1.0 制作任务；旧任务保留在 Git 历史，不得按旧指令重建仓库或把橙花、银白误标为未制作。

原三个角色已有私有九行动画与本机安装文件。2026-10-23 交接任务另以三张新母图制作 `-renewal` 候选；新图也是未知来源旧图的参考改绘，公开权利仍未确认。先核对本地最新 `reports/FINAL_PUBLIC_RELEASE_REPORT.md`、`reports/FINAL_PUBLIC_RELEASE_MACHINE_SUMMARY.json`；V1.4 及更早报告是历史证据。报告不存在时如实记录，不能推测通过。

执行次序：

1. 记录当前 Git、文件哈希与测试基线。保留已有提交、失败稿、原图和合格资源。renewal 只用新母图重建，不覆盖原三套宠物；其他维修只改有实际问题的行。
2. 读取本机官方 hatch-pet 合约并核验适用版本。复用项目工具；图片修复仅使用官方 imagegen 流程，先定位失败帧。
3. 独立检查实际图集、九个 GIF、逐帧时序和深浅背景；工具测试与结构数据不能替代视觉判断。
4. 安装按 `docs/INSTALLATION.md` 执行。默认同名拒绝；用户明确授权替换后才用 `--replace`，必须保留备份。
5. 不绕过 Computer Use 对宿主应用的安全限制。用户已报告客户端使用检查完成（USER_REPORTED）；逐状态未实测保持 NOT_RUN，按 `docs/MANUAL_GUI_CHECKLIST.md` 留给人工验收。
6. 运行全部测试和 `scripts/audit_publication.py --history`。公开代码方案见 `docs/CODE_ONLY_RELEASE.md`；原图、母图、帧、图集、GIF、截图及本地报告不得进入公开仓库。
7. 每次报告分别记录代码、动画、GUI、权利与发布状态。没有实际执行就写 `NOT_RUN`，不得补写 PASS 或伪造截图。

只维护 Codex 原生资源包与轻量 Python 工具。不创建独立客户端、后台服务、Agent 集成或 Live2D；不接触其他项目。素材权利与代码许可分别核实，未经用户明确授权不推送 GitHub、不创建公开 Release。

V1.4：代码与文档已明确采用 MIT；用户已授权符合权利条件的公开操作。美术来源仍 UNVERIFIED，只能发布 Code-only toolkit；不得把原私有 Git 历史推送到公开仓库。

V1.5：仅正式发行代码与校验清单，沿用现有公开仓库历史。新绘三角色已有用户基础反馈 USER_REPORTED_GUI_BASIC_PASS，九状态逐项仍未完成；不重新生成动画，不上传未获授权的美术。

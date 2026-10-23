# 贡献与证据要求

贡献范围为 Codex 原生角色资源及校验、预览、安装、打包工具。不引入独立客户端、后台进程、Agent 集成或云端服务。先读项目根目录 `AGENTS.md`、`CODEX_PROMPT.md` 与本目录方案、角色、权利文档。

## 工程变更

保持 Python 工具简单、无运行期网络请求、可离线检查。依赖仅增加必要项并说明用途。修改后实际运行：

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/audit_publication.py --history
```

负样本至少包括错误尺寸、缺 alpha、空有效帧、脏空格、透明 RGB 污染、错 manifest、路径穿越与同名安装保护。测试夹具保存在临时目录，用后清理，不把合成测试图发布为角色素材。

安装必须尊重 CODEX_HOME，默认拒绝同名目标，显式替换先备份；不能修改其他角色。打包必须验证实际输入，不能信任 README 或文件名作为通过依据。

## 美术变更

先固定母图，再逐行动作；每行附母图与布局参考，保留原始 imagegen 输出和 QA。提供对应图集哈希、接触图、九行真实 GIF、结构报告和视觉检查记录。仅修改尺寸、复制贴图或改变平移量不能称为真实动画。

失败与未执行分别写明 `FAIL`、`BLOCKED`、`NOT_RUN`、`ART_PENDING`，禁止补写虚假的 PASS、截图或安装成功。工具测试、结构校验、视觉 QA、文件安装和 GUI 播放是不同的证据层。

## 私有输入与许可证

`references/private/`、`workruns/`、本地报告和私有预览不得 stage、commit、push 或进入公开 ZIP。`git add -f` 不能绕过授权门禁。原图与衍生物公开权利未知时，只能提交允许公开的独立代码和不含私有信息的文字。

自有代码和文档采用 MIT；不要给五张原图、角色设计、生成图或动画套用 MIT。公开前依据 `ASSET_RIGHTS.md` 核对原作者、授权范围、署名、许可证和证明，逐个绑定实际发行资产。

GitHub push、新建公开仓库、Release 都需要用户明确授权。发布前审计 `git ls-files`、`git diff --cached --name-only` 和 ZIP 清单；扫描结果必须来自实际执行，尚未建立 Git 仓库时标记该检查未适用而非通过。

当前 CI 只接受代码与文字；私有目录、图片/视频/压缩包、非文本、大于1MiB文件及部分敏感模式会失败。媒体合法发行需要另行核对权利并调整经审查的发行流程，不能跳过门禁。扫描不覆盖提交身份，也不是秘密不存在的证明；详见[代码公开方案](CODE_ONLY_RELEASE.md)。

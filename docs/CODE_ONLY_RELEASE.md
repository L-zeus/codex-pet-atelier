# Code-only toolkit 发行

V1.4 已取得代码和文档采用 MIT 的明确确认，以及符合权利条件内容的 GitHub 发布授权。美术仍为 `UNVERIFIED`，不在该授权范围内。代码版不包含可安装的角色资源。

## 可复现构建

```bash
.venv/bin/python scripts/package_code.py --output dist/codex-pet-atelier-code-1.4.0.zip
.venv/bin/python scripts/package_code.py --check dist/codex-pet-atelier-code-1.4.0.zip
```

`scripts/package_code.py` 中的 `FILES` 是逐名审查的文件白名单，包含代码、测试、文档、CI、MIT 与美术许可边界；禁止改成全目录递归导出。ZIP 另外包含 `CODE_ONLY_NOTICE.txt`、`RC_MANIFEST.json`、`SHA256SUMS`。检查器验证精确成员集合、重复项、属性、媒体签名、有限敏感模式及全部哈希。输出拒绝覆盖，构建不会发起网络发布。

manifest 的 `MIT_CODE_AND_DOCS` 仅表示包内代码许可范围，`LOCAL_BUILD_NOT_PUBLISHED` 不会随 GitHub 上传被改写。远程发布需要独立回读证明。旧 V1.3 ZIP 和哈希作为历史候选保留；不使用新版检查器宣称旧包通过新版白名单。

## 公开历史与身份

从已检查 ZIP 解压建立独立 Git 仓库，不复制原 `.git`。原私有历史保持原样。仅为新仓库设置经过当前 GitHub 账户关联提交核实的 noreply 身份，不改全局配置。公开前检查作者/提交者、提交消息、逐文件内容与 ZIP 清单。发布只能推送该独立仓库，不能推送原项目历史。

CI 在 Ubuntu/Python 3.12 和 3.14 上运行内容/历史审计、工具测试、ZIP 构建及独立解压测试；工作流只读，checkout 不持久化凭据。绿色结果仅覆盖代码工具，不认证美术、GUI 或素材权利。真实执行链接及结果以发行页和 Actions 为准。

## 美术发行边界

原图、母图、图集、GIF、含角色截图、私有证据和官方 skill 副本均不上传。三角色 ZIP 需要真实的逐图来源、衍生与再分发权、素材许可证，以及哈希绑定的视觉和 GUI 证据。用户笼统报告客户端使用完成，记录为 `USER_REPORTED_GUI_CHECK_COMPLETED`，不填造九状态 PASS。

发行采用明确的 `v1.4.0-code-only` 范围，不能使用暗示三宠正式合集完成的标题。后续美术满足条件后才准备完整角色版。

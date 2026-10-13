# Issue tracker: GitHub

本仓库的任务与实施规格使用 GitHub Issues，使用 `gh` CLI 操作。仓库身份从 `git remote -v` 确认，在本项目目录执行命令。

## 操作约定

- 创建任务：`gh issue create --title "标题" --body-file <正文文件>`。
- 读取任务和讨论：`gh issue view <编号> --comments`。
- 查询任务：`gh issue list --state open --json number,title,body,labels`，按需要添加标签过滤。
- 添加讨论：`gh issue comment <编号> --body-file <正文文件>`。
- 更新标签：`gh issue edit <编号> --add-label <标签>` 或 `--remove-label <标签>`。
- 完成任务：补充结果和验证依据后使用 `gh issue close <编号>`。
- 多行正文写入 UTF-8 临时文件后通过 `--body-file` 传入；临时文件放在被 Git 忽略的 `work/`。
- 当技能要求发布规格或任务时，创建 GitHub Issue；当要求获取任务时，读取对应 Issue 及评论。

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Wayfinding

- Map 是带有 `wayfinder:map` 标签的总 Issue；子任务链接为 GitHub sub-issue。若不可用，在总 Issue 中维护任务列表，子任务正文标明 `Part of #<编号>`。
- 子任务类型使用 `wayfinder:research`、`wayfinder:prototype`、`wayfinder:grilling` 或 `wayfinder:task`。
- 优先使用 GitHub 原生 Issue 依赖；不可用时用正文中的 `Blocked by: #<编号>` 记录。
- Frontier 是未关闭、无未完成阻塞且未分配负责人的子任务，按总 Issue 中的顺序处理。
- 领取任务时分配给实际执行者；解决后追加结果评论、关闭子任务，并更新总 Issue 中的决定与链接。
- 首次使用上述可选功能时检查当前 CLI 支持的命令与权限。

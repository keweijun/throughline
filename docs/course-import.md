# 课程导入、复现与审阅

## 本机课程与审计资料

项目根目录下：

| 路径 | 用途 |
|---|---|
| `work/course-inputs/quantum/<材料名>/` | 8 份 PDF 的稳定输入副本，以及 Markdown、MinerU JSON、images 补充资料 |
| `work/courses/quantum-v1/` | 可用的正式课程工作区，候选路线待审核，尚无学习记录 |
| `work/courses/quantum-v1/import-requests.jsonl` | 10 条公开 API 请求：建课、8 次来源登记、保存路线 |
| `work/courses/quantum-v1/audit/` | 完整块级候选图、来源哈希、原勘察、7 页抽查记录、导入摘要与覆盖报告 |
| `work/courses/quantum-import-check/` | 独立重放检查用工作区，不作为用户学习进度 |

正式来源登记使用 PDF 物理页 `page-1` 开始。Markdown 和裁剪图片仅作为私有补充资料，没有再登记成数千行重复覆盖项。Markdown 行号、MinerU 零基页索引与 PDF 页码不能互换。完整块级信息保留在 audit；当前知识点链接只带简短主题、内容类型、审核标记和审计指针。

这些私有文件被 `.gitignore` 排除。克隆仓库不会下载课程材料。课程运行所需副本已经放在项目内；audit 中的历史原路径仅为溯源信息。

## 在本机重放导入

在仓库根目录运行以下 PowerShell，使用新的工作区名。每条请求经独立 CLI 进程处理；失败立即停止：

```powershell
$courseImportTarget = 'work/courses/quantum-import-replay'
$coursePython = '.\.venv\Scripts\python.exe'
$courseImportFile = 'work/courses/quantum-v1/import-requests.jsonl'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Get-Content -LiteralPath $courseImportFile -Encoding utf8 | ForEach-Object {
    $_ | & $coursePython -m guided_learning --workspace $courseImportTarget
    if ($LASTEXITCODE -ne 0) { throw 'Course import stopped; inspect the error before continuing.' }
}
'{"op":"curriculum.coverage"}' | & $coursePython -m guided_learning --workspace $courseImportTarget
'{"op":"session.resume"}' | & $coursePython -m guided_learning --workspace $courseImportTarget
```

重放文件保留稳定输入的绝对路径及内容哈希。输入副本未移动、内容未变化时可直接复现。不要只替换 JSON 中的路径后沿用旧引用：来源 ID 包含规范化路径，内容变化也会改变 revision。换电脑或换目录时，应重新登记并用返回的 ID/revision 重建链接。

正式学习以后不要用候选导入文件覆盖正在使用的路线。先在新工作区审阅；路线的大幅改序需要用户确认，既有知识点 ID 和学习证据要保留。

## 建立其他课程

1. 将用户提供的原文件复制到课程自己的稳定输入目录，保留原件。通过 `course.init` 建课，逐个 `source.register {path}` 登记。核对返回状态，并通过 `source.read {source_id}` 查看实际单元。
2. 教师按知识点建立 `concepts`、`route`、`coverage`；每个链接用登记返回的 `source_id, revision, unit_id`。参见 [课程操作](../.agents/skills/guided-learning/references/course-operations.md) 和 [路线操作](../.agents/skills/guided-learning/references/curriculum.md)。
3. 来源读取成功只代表文本提取。缺图、公式不清、读取失败或含义未判定处标 `needs_review` 并写明原因。范围内暂缓内容保留去向，不能因习题未考而删掉。
4. 用 `curriculum.save` 提交候选图；保存请求为 UTF-8 JSON，以 `--request` 重放。检查 `curriculum.coverage` 的所有单元与 `semantic_completeness`，再确认整体教学路径。
5. 只有开始真实教学时才登记真实交互、主线位置和证据。路线导入不会自动产生已讲解或已掌握记录。

## 本课程的审阅重点

231 页全部有候选去向，190 页因公式、图片、图表或稀少文本被显式标记待核验。7 页视觉抽查只核对了具体事项，没有将整页批量升级为 verified。应优先复核即将教学的原页，再逐步审完整课程。

- PS01 Q1(2) 包含数值与课件比较；Q4 的平均尺度为 `1/<r^-1>`，不是 `<r>`。
- PS01 Q6、Q7 和 PS02 Q1 的转写出现整式绝对值外框误识别，按原 PDF 纠正讲解。
- PS02 Q2 的第三问允许数值积分；Q4 需保留一阶、二阶与闭合近似要求。
- 箱长 `a/L`、频率 `nu/omega`、约化质量与偶极矩的 `mu`、微扰阶数与态编号都要结合具体模型解释；符号说明仍为候选来源绑定。
- 23 个习题要求按独立子问计数：11 道大题中的两个无编号证明拆作 Q6.a/Q6.b；PS02 Q4.3 的一阶/二阶仍归为同一子问，并在 detail 保留。

完成具体核对后才能为相应覆盖项提交 `verification:verified` 和有内容的 `verification_note`。核验原文、讲过内容、独立答题是三种不同记录。

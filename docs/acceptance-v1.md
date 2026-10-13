# 第一版验收报告

日期：2026-10-13。范围：GitHub 任务 #2–#7 的本地第一版。实现、测试及双轴代码审查已完成；材料语义全覆盖和长期学习效果尚未证明。最终审查记录见 [review-v1.md](review-v1.md)。

## 结果分开报告

| 层次 | 实测结果 | 不能据此宣称 |
|---|---|---|
| 程序行为 | 33 个 CLI 测试通过；覆盖来源、路线、分支恢复、证据、待补解释、后台状态及审查发现的回归 | 教学回答一定正确，或学生已掌握 |
| 实际资料 | 8 份 PDF/231 页登记成功，45 个候选概念，23 个独立习题要求，8 条符号来源说明 | 全部知识点已逐一核验 |
| 覆盖台账 | 41 页 mapped、190 页 needs_review；231 页均 pending，0 页 verified | mapped 等于语义完整或学习完成 |
| 原页核对 | 主代理实际查看 7 页 PNG，记录具体公式/题意差异 | 已核验全部 231 页或所有图像 |
| 教学回放 | 最终 API 重放 57 次操作，并在隔离副本完成 30 次波函数→本征态→投影操作，均无失败 | 真实学习者长期体验或学习增益 |
| Luna 宿主集成 | 初次和最终版本均实际调用 gpt-6-luna；最终用合成交互生成 2 条候选笔记，审核接受为 1 个任务的派生笔记集 | 已整理真实个人学习记录，或关闭聊天后仍运行 |

## 实际八份材料

| 文件 | 页数 |
|---|---:|
| 物理化学H1-20260914.pdf | 42 |
| 物理化学H1-20260915.pdf | 43 |
| 物理化学H1-20260921.pdf | 36 |
| 物理化学H1-20260922.pdf | 34 |
| 物理化学H1-20260928.pdf | 36 |
| 物理化学H1-20260929.pdf | 36 |
| PChemH1_ProblemSet01.pdf | 2 |
| PChemH1_ProblemSet02.pdf | 2 |

真实输入已复制到 `F:/Projects/codex-guided-learning/work/course-inputs/quantum`，附带 8 份 Markdown、8 份 MinerU JSON 和 463 张 JPG 补充图；原始文件未修改。所有登记路径均位于该项目内，学习不再依赖原笔记应用目录。来源版本哈希与勘察时一致，8 个来源读取状态均 read，无提取错误；这仅验证提取流程。

正式课程为 `F:/Projects/codex-guided-learning/work/courses/quantum-v1`，标题明确标注候选路线与逐页语义待审。**没有导入旧个人对话，交互数为 0、主线位置为空，45 个概念均无学习证据。** 第一次教学由用户选择起点，不伪造已完成阶段。

完整候选块信息在私有 `audit/quantum-candidate-map.json`；当前上下文仅保留简短 page detail、块类型、审核标记和 audit_pointer。测试读取 wavefunction-born、linear-eigen、completeness、measurement-expectation、box-one-dimensional 五个实际上下文，来源存在且无过期引用。

## 视觉抽查的准确边界

主代理实际查看：PS01 第 1、2 页，PS02 第 1、2 页，20260915 第 32 页，20260921 第 14 页，20260928 第 4 页。具体发现保存在本地 `work/visual-check.md`，并复制进课程 audit：

- 原 PDF 不含转写在 PS01 Q6/Q7、PS02 Q1 添加的整式绝对值外框。
- PS01 Q1(2) 的数值比较、Q4 的 `1/<r^-1>` 定义，PS02 Q2 的数值积分许可等不能丢失。
- 定态的空间波函数与完整时间相位、期望值的归一化分母和箱长符号需要教学解释。

渲染存在字体警告，抽查的 7 页可读；没有推断其他页面也无问题。所有页仍 pending，避免将局部抽查当作整页全认证。

## 教学回放与发现的缺陷

独立教师代理在隔离的模拟课程中使用实际材料上下文演练符号短答、先修长答、未来概念、重复困惑、明确深入、继续及恢复。首轮发现：q2 长解释 waiting 期间自然追问未来 q3，旧接口没有保存 q3 待补承诺的入口。已增加 `deferred.create`，保留 q2 的恢复点，按后续概念回访。该修复对应 #4，并加入两条程序回归测试。

修复后的本地证据位于 `work/teaching-replay-fixed/operations.jsonl` 与 `transcript.md`，共 57 次 CLI 操作、0 失败。主代理复查的重要步骤：

- 第 28 条创建后续解释承诺；29–30 条保持 q2 waiting 和原恢复点，第 30 条使用新进程。
- 31–32 条保存真实的模拟“继续”消息后再关闭旁支。
- 38 条到 Fourier 目标时出现待补项；42 条仅写完整回答后仍 pending；43 条显式 resolve；46 条确认清除。
- 重复困惑更换为纯虚数示例；明确深入触发相位到动量的完整解释。

上述均为模拟学习者场景，没有写入正式用户课程，也不能代替真人学习效果评估。

最终版本在 `work/teaching-replay-final` 重新执行原 57 条操作，仅为检查点写入补上新接口要求的稳定 request_id，全部成功。额外检查证明旧检查点重试不回退当前位置，历史交互可按 ID 取回原文和来源版本。另在正式课程的隔离副本完成 30 条操作，实际讲解波函数表示、本征函数判断、正交归一与投影系数，并兑现待补解释；仅记录教师讲解，不虚构掌握。主代理再次确认正式课程主线为空、真实交互数为 0。

## Luna 与不可用降级

`work/luna-smoke-result.json` 记录初次真实宿主调用；最终 API 的再次真实调用记录在 `work/luna-smoke-final-result.json`。输入均为合成交互，最终输出 2 条笔记，区分学习者自述、教师说明和暂不出题的要求。候选笔记核对引用后接受为一个任务的派生结果，没有升级学习证据或设置主线位置。

后台程序测试另外覆盖模型不可用时保留任务、恢复重试、旧结果冲突及不自动调用额外 API。宿主调用与状态机测试是两类证据；提交队列成功不等于模型执行成功。第一版允许暂停和下次继续，没有常驻服务。

## 复现命令与私有结果

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
'{"op":"course.status"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/quantum-v1
'{"op":"curriculum.coverage"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/quantum-v1
'{"op":"session.resume"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/quantum-v1
'{"op":"curriculum.context","concept_id":"wavefunction-born"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/quantum-v1
```

实际导入使用公开 `execute` API。另将 10 条相同请求逐条通过独立 CLI 进程重放到 `work/courses/quantum-import-check`，全部成功，再核对 231 页、45 个概念、23 个要求、5 个实际上下文及正式课程无学习证据。私有结果为正式课程 `audit/import-summary.json`、`coverage.json`、`import-replay-result.json`。可复现的 PowerShell 导入循环见[导入说明](course-import.md)。

## 待完成的验证

- 对全部课程逐知识点、公式、图像进行教学语义审核；现阶段台账保留不确定性。
- 用真人实际学习反馈评估路径深度、解释质量与延迟改善；本轮没有做响应速度基准。

## 最终程序与审查结果

集成代码在 `6b02923` 完成审查修复后，主代理运行完整测试：33 项通过；skill 校验通过，差异检查通过。原规格审查的 4 项问题及标准审查的 1 项可选维护建议均已处理，并由原审查代理独立复查。详见 [review-v1.md](review-v1.md)。本轮没有性能加速或长期学习增益的实测结论。

原 PDF、转写、裁剪图、数据库、原始回放和模型响应均保留在被忽略的 `work/`；提交内容只有通用代码、使用说明与这份不含个人作答的报告。

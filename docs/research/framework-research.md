# 多文档长程导学：现成产品核查

核查日期：2026-10-12（用户时区）。以下为官方文档/仓库核查，不是安装实测；“未确认”不代表产品一定没有。评判目标是将 6 份课件和 2 份习题纳入同一条可恢复、可检验、能补漏的学习路径。

## DeepTutor：文档能力与实际体验存在落差

用户已确认使用过 Mastery Path，实际遇到跨文档导学不支持和文档读取故障，因此没有继续深入。这是本次选型的直接使用证据，不能用功能介绍替代。

官方 Mastery Path 描述了多文件选取、可编辑模块/知识点、遗漏文件检查、掌握门槛、间隔复习和恢复对话。[Mastery Path](https://docs.deeptutor.info/explore/mastery-path/) **多文件可以选入，不等于系统能将重复内容合并、建立跨课件先修关系，并持续按掌握证据导学。** 后一种能力及原材料读取可靠性仍未证实；DeepTutor 只能作为有条件的候选。

官方版本记录列出 2026-09-03 v1.6.4 的来源完整性改进、2026-08-30 v1.6.1 的后台 Task Model；当前 README 列出的最近版本为 2026-10-08 v1.6.14。[版本与功能记录](https://github.com/HKUDS/DeepTutor/blob/main/README.md)

Settings 可单独配置后台 Task Model。Memory 提供工作区实体、分区摘要、跨区综合三层持久记忆及可审查来源。**但文档没有证明每种记忆更新都已完全移出主对话等待链，也没有证明能逐页覆盖所有公式、图像和题型**。[模型设置](https://docs.deeptutor.info/explore/settings/) · [记忆结构](https://docs.deeptutor.info/explore/memory/)

## 五个候选的实际定位

| 候选 | 官方已描述的能力 | 本场景的缺口/待验证项 | 建议定位 |
|---|---|---|---|
| DeepTutor | 多来源路径、知识点类型、掌握门槛、间隔复习、恢复学习、后台模型 | 用户已在 Mastery Path 遇到跨文档导学与读取问题；融合、先修关系及可靠性未证实 | 仅在对应故障和能力缺口有明确改进证据后再评估 |
| RemNote | Guided Learn 可从文件、现有文档或知识库文件夹启动；章节化学习、问答、卡片、测验和 Mastery Tracker | 文档强调按来源/章节学习；未确认能把多个重叠课件自动融合成先修概念图。初始水平设置只改变活动优先次序，不改变生成内容 | 可小范围试用其界面与复习流程，并非已验证的完整解决方案 |
| OpenMAIC | 课件、测验、互动仿真、白板、AI 教师/同学；可分阶段选模型；课程与会话持久化 | 未在已读文档确认跨课程掌握状态、知识点覆盖审计、长期间隔复习。持久化生成任务不等于长期教学决策 | 适合做互动课堂/物理可视化层 |
| NotebookLM | 多来源问答、引用、Learning Guide、卡片与测验 | 未确认显式先修图、基于掌握证据的长期调度。不同 notebook 不能同时互读，应把 8 份材料放同一 notebook | 易用的材料阅读/检索对照组 |
| LearnHouse | 课程→章节→活动；Trails 保存完成度和测验；AI 在当前课程/活动上下文回答 | 课程完成与测验成绩不等于概念掌握模型；未确认自动跨文档课程融合、长期个性化调度 | 更适合把课程交付给一群学生，个人场景偏重 |

RemNote 的功能证据来自 [Guided Learn Mode](https://help.remnote.com/en/articles/15724936-guided-learn-mode)。阅读器采用原文、笔记、学习工具并排布局；AI 功能使用额度，阅读器主要为 Pro 功能。[Reader 文档](https://help.remnote.com/en/articles/6690975-learning-from-pdfs-and-files-with-the-remnote-reader)

OpenMAIC 的依据为 [官方仓库](https://github.com/THU-MAIC/OpenMAIC)。须区分版本：2026-10-04 的 1.2.0-rc.1 是预发布，其生成改为服务端持续运行，需要 PostgreSQL 和常驻服务；不应把主分支能力直接当作稳定版本能力。多 AI 角色并不自动减少等待时间。

NotebookLM 依据为 Google 的 [学习功能介绍](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-student-features/) 与 [notebook 隔离说明](https://support.google.com/gemininotebook/answer/16206563?hl=en)。后者当前标题使用 Gemini Notebook；这里保留用户熟悉的 NotebookLM 名称。

LearnHouse 依据为 [Trails](https://docs.learnhouse.app/platform/courses/trails) 与 [AI 上下文范围](https://docs.learnhouse.app/platform/ai)。Collections 能组织跨课程路径，但这不能证明 AI 会综合多个课程建立动态先修图。[概念文档](https://docs.learnhouse.app/getting-started/key-concepts)

## 针对这组材料的选型建议（分析判断）

1. 本轮没有证据支持某个现成产品能完整解决三项痛点。应先明确独立课程状态：知识点、先修关系、来源页码、习题映射、掌握证据和待复习项；不要把长对话摘要当成课程状态。
2. 如希望少开发，可用少量原材料试 RemNote，验证界面与复习流程，跨文档融合仍须单独验收；不必先全量迁移。
3. DeepTutor 暂列有条件候选：只有对应读取故障得到解决、跨文档融合通过实际测试后，再考虑使用其底座。OpenMAIC 可作交互组件参考；多智能体本身不能保证速度或教学完整性。

## 简短验收测试

- 导入 8 份原材料，要求输出“知识点—来源页码—习题号”覆盖表，随机检查 20 个来源点；全文件被引用不是通过标准。
- 检查重复知识点是否合并，互相关联概念是否有先修关系，题目是否映射到必要知识。
- 故意在一个概念题答错，看系统是否记录具体误解、补救，并在后续复查；不能仅用“已读”升为掌握。
- 中断会话后重开，确认继续正确知识点、保留错误与待做题，并能在数日后复习。
- 分别记录首字延迟、完整讲解延迟、后台笔记落盘延迟；确认总结失败不会阻塞下一轮教学。

这几个测试才能区分“文档里有功能”与“适合你的长期量子物理导学”。

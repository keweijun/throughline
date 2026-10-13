# 小节练习与学习证据

小节围绕一个完整学习目标；结束后集中练习。先读 `evidence.review`，结合当前目标选题。卡住时给最少必要提示，再等待尝试；明确要求完整解答时直接示范。选择继续或跳过时保留未验证状态并推进。教学判断由教师做出，程序只检查证据角色、引用、时序和去重；程序通过不等同于答案正确。

## 记录流程

1. 通过 `interaction.record` 保存真实原文，取得用户回答与教师讲解的 ID。每次学习使用新的 `session_id`；同一道题的重试与提示保持相同 `exercise_id`。从课程习题映射选定题目，保留稳定题目标识。
2. `evidence.record` 接收 `id, concept_id, kind, interaction_id`。`kind` 为 `taught`（教师讲解）、`self_report`（用户自述）、`hint` 或 `demonstrated`（完整示范）。后两者还需 `session_id, exercise_id`；提示需 `level`，例如 `minimal`、`worked_step`。在评估前记录全部提示与示范。历史回答评估后补录此前提示会被拒绝，应显式报告记录缺口。
3. 只有用户真正作答后才评估。记录包含判断理由的教师反馈，再提交 `evidence.assess`：`id, concept_id, session_id, exercise_id, answer_id, assessment_id, outcome`。`outcome` 为 `passed` 或 `needs_work`。反馈必须晚于答案。提示或完整示范之后的通过自动记为 `hinted`；没有援助的通过记为 `independent`。继续、懂了以及教师答案不作为用户答题证据；自述用 `self_report`。
4. 延后复测传入 `retest_of` 指向先前独立通过记录，使用另一学习会话的新回答。无提示通过才产生 `retest_passed`。同一原始回答不能以新 ID 重复评估。
5. 用 `evidence.view {concept_id}` 核对结果。`status` 表示历史达到的证据级别；`latest_assessment` 可能显示后来失败，必须同时读取。`independently_verified` 仅说明存在一次独立通过，不能解释为永久掌握或概率。历史及每条交互引用保留。

示例评估请求：

```json
{"op":"evidence.assess","id":"assessment-7a-1","concept_id":"projection","session_id":"session-2","exercise_id":"exercise-7a","answer_id":"user-answer-7a","assessment_id":"teacher-feedback-7a","outcome":"passed"}
```

## 暂缓与重开

- `evidence.defer` 接收 `id, concept_id, reason`，以及 `target_concept_id` 或 `section_id`（可同时提供）。跳过仅登记暂缓，保持原有证据。
- 在进入目标知识点或小节复盘时调用 `evidence.review {concept_id, section_id?, recap?}`。仅在复盘时设 `recap:true`。`due` 提供到点暂缓项；每轮答疑无需再读或重复催促。
- 重开时结合 `session.resume`、`evidence.review` 简短恢复目标和未解问题，然后接续；`quiz_required:false`，不强制测验。用户选择继续仍可推进。
- 学习者确认已回访后，将其真实回应记录为交互，再调用 `evidence.resolve {id, deferred_id, interaction_id}`。这结束提醒但不会升级掌握，历史保留在 `deferred_history` 与 `resolutions`。

同 ID 同内容重试返回原记录，改写既有记录返回 `id_conflict`。为纠错创建明确的新事件，保留原始证据。材料更新后证据仍保留，教师结合新来源判断是否安排复测。

## 历史来源与原文核查

新证据从原始交互保存来源快照：讲解/自述等记录使用 `source_refs`，评估分别保存 `answer_source_refs` 和 `assessment_source_refs`。每项包含来源 ID、内容版本 SHA 和单元 ID。材料修改或课程重新关联后，这些引用仍指向当时版本。可用 `source.read {source_id, revision}` 核查当时内容，不用当前课程链接解释旧证据。

通过 `interaction.read {id}` 读取证据所指的原始回答和反馈；即使它们已经超出最近 20 条消息仍可查阅。旧数据库的记录若缺少来源字段、或引用为空，表示未记录可用来源；不能据此补写为最新材料版本。历史记录重试保持原值。

暂缓项 A 安排在 B 回访时，`evidence.resolve` 接受原概念 A 或约定目标 B 上的真实用户确认，并保留其原始交互 ID；不要求改写消息所属概念。无概念标签的既有用户消息仍兼容，无关概念或教师消息被拒绝。

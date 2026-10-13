# Codex Guided Learning

个人跨文档导学项目，第一版采用 Codex skill、独立课程工作区和辅助脚本，优先验证教学连续性、资料覆盖和路径感知答疑。

当前处于设计与工程配置阶段，教学功能尚未实现。

## 文档

- [第一版方案](docs/v1-spec.md)：教学行为、状态边界和验收场景。
- [设计访谈](docs/design-interview.md)：已确认的需求与选择。
- [领域术语](GLOSSARY.md)：项目统一用语。
- [架构决定](docs/adr/0001-course-workspace-owns-learning-state.md)：课程工作区持有正式学习状态。
- [前期研究](docs/research/)：现成框架对比及工作流分析，历史建议以第一版方案为准。
- [早期设计归档](docs/archive/initial-design/)：保留的初始设计记录。

项目统一保存在 `F:\Projects\codex-guided-learning`。第一版独立于 Obsidian，不提供兼容、导出或同步。

任务采用 GitHub Issues 管理。工程技能从 [AGENTS.md](AGENTS.md) 读取入口，具体规则在 [docs/agents/](docs/agents/)；之后可直接编辑这些配置文件。

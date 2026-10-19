# Codex Guided Learning

个人跨文档导学：Codex skill 负责教师行为，本地课程工作区保存来源、路线、教学主线和真实学习证据。现在还提供本地学习界面：流式讲解、单元导览、来源原页、旁支答疑、练习与下一小节备课。教师仍需根据资料作教学判断；程序校验状态与引用，不自动判断学习者是否真正理解。

## 安装与调用

需要 Python 3.10+。在仓库根目录执行（PowerShell）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[pdf]'
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

在 Codex 中打开本项目；仓库 skill 位于 [.agents/skills/guided-learning/SKILL.md](.agents/skills/guided-learning/SKILL.md)，可用 `$guided-learning` 调用。若当前聊天尚未发现新技能，开启项目新聊天，或明确让 Codex 读取该文件。该 skill 与某门课程的状态分开；不必复制到全局技能目录。

例如告诉 Codex：

> 使用 guided-learning，打开本项目 work/courses/quantum-v1。先简短说明候选路线与尚待核验内容，再从波函数开始安排导学；不要把示范或自述理解算作独立完成。

调用工具入口时，JSON 可来自 UTF-8 请求文件，或标准输入：

```powershell
'{"op":"course.init","title":"我的课程"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/demo
'{"op":"position.save","request_id":"demo-checkpoint-1","position":{"goal":"准备课程","next_step":"登记材料"}}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/demo
'{"op":"session.resume"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/demo
```

修改位置的 `position.save` 和 `mainline.enter` 必须提供唯一 `request_id`；重试复用同一个 ID，旧请求不会覆盖新进度。可用 `interaction.read {id}` 核查超出近期窗口的原始问答。

成功返回 `{ok:true,result:...}`，失败返回 `{ok:false,error:...}` 与非零退出码。`--request` 参数接收 JSON **文件路径**。使用 `--request work/request.json` 可避免复杂公式或长文本的 shell 转义。

## 打开 V2 学习界面

先完成上面的安装，并让当前终端能够运行已配置模型通道的 `codex`。宿主沿用本机 Codex 配置，不另存 API 密钥，也不自动选择新的付费通道。在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m guided_learning.web --workspace work/courses/quantum-v1 --port 8765 --model gpt-6.1-sol --effort medium
```

浏览器打开 <http://127.0.0.1:8765>。该课程须已存在；其他机器先按[课程导入](docs/course-import.md)创建自己的课程，再替换 `--workspace`。模型名须由当前配置通道支持；也可省略 `--model` 沿用该通道默认值。不要把课程路径误填成原始 PDF 目录。

终端保持运行，按 Ctrl+C 关闭。再次执行同一命令恢复课程。界面操作会保存到指定课程；试用前可在宿主关闭时复制整个课程目录，改用副本路径。[使用与恢复说明](docs/learning-ui.md)介绍暂停、旁支、练习和故障处理；[V2 验收](docs/acceptance-v2.md)区分自动测试、真实模型与教学检查。

Markdown、数学渲染及字体已随项目打包，无需运行时访问 CDN。模型生成仍需要网络和有效的本机 Codex 配置；PDF 原页需要安装 `.[pdf]`。

## 现在能做什么

- 登记 PDF/Markdown，保存版本快照和读取问题；按来源位置核对。
- 保存跨文档知识点、先修路线、符号和习题映射；检查引用、循环及覆盖去向。
- 围绕目标决定旁支回答深度；短答后接续，长答后等待。长旁支中的后续问题也能绑定待补解释。
- 小节末集中练习；分别保留讲过、自述、提示、独立完成和复测的证据。
- 暂缓项到点回访；新聊天短回顾后接续，不强制先测验。
- 主教师即时响应，宿主提供 Luna 时可整理候选笔记；不可用则保留任务，不自动调用付费 API。

后台备课仅在本地学习宿主运行时执行；关闭宿主后不会常驻。公开插件分发不在当前范围。

### V2 原页显示依赖

本地学习界面使用 `pdf` 扩展中的 pypdfium2 和 Pillow，把已注册的 PDF 精确版本渲染为原页图像；不依赖浏览器内置 PDF 插件。更新环境运行 `.\.venv\Scripts\python.exe -m pip install -e ".[pdf]"`。缺少渲染器时页面会明确提示原页图像未显示，仍提供原 PDF 链接。

## 已准备的本地量子课程

`work/courses/quantum-v1` 已登记实际 6 份课件和 2 份习题，共 231 页，建立 45 个候选知识点、23 个习题子要求和 8 条来源关联符号说明。输入副本位于 `work/course-inputs/quantum`，运行时不依赖原笔记应用目录。

**这是一份待审阅的候选覆盖图。** 41 页具有候选映射，190 页明确需复核；全部 231 页的验证状态仍为 pending。只抽查了 7 页原 PDF，不能据此宣称所有公式、图片或知识点已经核验。没有导入个人旧聊天，没有生成虚假学习进度。

课程材料和数据库仅保存在本机 `work/`，不随 Git 仓库分发。其他机器需要自行提供材料并创建课程。[课程导入与审阅](docs/course-import.md) 说明如何重放本机导入和建立新课程；[验收报告](docs/acceptance-v1.md) 区分程序测试、实际材料、教学回放及 Luna 实测。

## 设计与开发

- [第一版方案](docs/v1-spec.md)、[实现规格](docs/implementation-spec.md)、[任务拆分](docs/implementation-plan.md)
- [设计访谈](docs/design-interview.md)、[领域术语](GLOSSARY.md)、[状态归属 ADR](docs/adr/0001-course-workspace-owns-learning-state.md)
- [前期研究](docs/research/) 保留历史比较，最终范围以第一版方案为准。

项目采用 GitHub Issues；工程技能入口为 [AGENTS.md](AGENTS.md)。独立于 Obsidian，不做兼容、导出或同步。

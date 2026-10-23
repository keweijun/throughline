<p align="center">
  <img src="docs/images/wordmark-light.svg#gh-light-mode-only" alt="Throughline 贯学" width="356">
  <img src="docs/images/wordmark-dark.svg#gh-dark-mode-only" alt="Throughline 贯学" width="356">
</p>

<p align="center"><b>一条教学主线，贯穿你的所有资料。</b><br>本地运行的学习应用：把你的 PDF 和笔记整理成一门有引导的课程，由 Codex 授课。</p>

<p align="center"><a href="README.md">English</a> · <b>简体中文</b></p>

![贯学的课程页面：左侧是课程路线，中间是当前小节的目标、下一步，以及带出处引用的流式讲解](docs/images/lesson-zh-CN.png)

贯学（Throughline）把多份 PDF 和 Markdown 资料组织成一条与原文出处相连的学习路线，然后在浏览器里带你学：单元导览、流式讲解、针对任意段落提问、原文页面与讲解并排、练习，以及随时可以接着学的进度。

教学判断由老师依据你的资料做出；程序只负责校验状态和引用，从不自行认定你已经掌握。所有内容都在你自己的电脑上运行，由你自己的 Codex 担任老师。

## 安装

你需要已登录的 Codex（桌面应用或 [CLI](https://learn.chatgpt.com/docs/codex/cli) 均可；桌面应用自带贯学所需的命令）以及 Python 3.10 或更高版本。把下面这段粘贴到 Codex：

```text
帮我安装贯学（Throughline）：运行 `uv tool install --upgrade "codex-guided-learning[pdf] @ git+https://github.com/keweijun/throughline"`（如果没有 uv，就用 `pipx install --force` 安装同一个带引号的包，实在不行再用 `python -m pip install --user --upgrade`），然后运行 `guided-learning setup`，把输出给我看。
```

Codex 会安装应用（不需要 Node.js），把 `$guided-learning` 技能放进 `~/.agents/skills/`，并创建你的课程库。以后再粘贴一次同样的内容即可更新。

## 在 Codex 里使用

你不需要自己输入任何命令，直接对 Codex 说：

- `$guided-learning 用这些文件创建名为 quantum 的课程：…`：把文件复制进课程库、登记资料并生成学习路线。
- `$guided-learning 打开 quantum`：在后台启动应用并在浏览器中打开。Codex 会请求权限，因为应用会持续运行并调用 Codex 讲课。
- `$guided-learning 把这些文件加入 quantum：…`、`核对 quantum 中仍待核对的页面`、`关闭学习界面`。

应用打开后先进入 **我的课程**：每门课程的资料、小节、待核对数量和上次学到哪里一目了然。创建和修改课程仍在 Codex 中完成，由它阅读和判断；课程库里提供了可以直接复制的指令。

![课程库：列出三门课程及其资料、小节、待核对数量和当前学习位置](docs/images/library-zh-CN.png)

## 学习

- **路线与目标**：左侧是课程路线，每个小节都标明目标和下一步该做什么。
- **讲解**：每个小节的第一次讲解从单元导览开始，然后进入正文。文字流式生成，完成后自动保存；可以暂停，也可以请老师再讲一遍。
- **旁支提问**：选中一句话或一个公式即可提问，讲解默认继续进行，除非你选择暂停。如果某个问题要到后面的小节才能讲透，它会被保存到那个小节。
- **资料原文**：把鼠标停在引用上可预览原文，点击后在内置阅读器中打开对应的页或行。尚未核验的资料会一直标注"待核验"。
- **练习**：每次讲解后都有练习。提示和答案随时可看，但会如实记录，得到帮助后的正确回答不会算作独立完成。

<table>
  <tr>
    <td><img src="docs/images/reader-zh-CN.png" alt="PDF 阅读器在讲解旁打开引用页"></td>
    <td><img src="docs/images/questions-zh-CN.png" alt="针对高亮段落的旁支提问，在侧栏中作答"></td>
  </tr>
  <tr>
    <td align="center">引用的原文页，就在讲解旁边</td>
    <td align="center">针对某段内容的旁支提问</td>
  </tr>
</table>

界面和新的讲解默认使用英文，可以在语言选择器中切换为简体中文。导入的资料和已有记录保留原来的语言，所以上图中的英文课程内容不会被翻译。更多说明见[界面使用说明](docs/learning-ui.md)（英文）。

## 文件在哪里

- **课程**：`~/.local/share/guided-learning/courses`（Windows 上是 `%LOCALAPPDATA%\guided-learning\courses`；设置 `GUIDED_LEARNING_HOME` 可整体迁移）。每门课程是一个文件夹，包含资料快照、路线、进度和学习记录；要迁移课程，先关闭应用，再复制整个文件夹。
- **教师设置**：点击顶栏中的模型名称打开 **教师设置**，选择 Codex 模型和推理强度。设置按用户保存在 `~/.config/guided-learning/settings.json`（Windows 上是 `%APPDATA%\guided-learning\settings.json`），不会写进任何课程。

文字提取并不能保证公式、图片或覆盖范围正确，所以课程库和阅读器会标出仍需核对的内容。参见[创建与核对课程](docs/course-import.md)（英文）。

## 指令背后的命令

```sh
guided-learning setup                 # 安装或更新 Codex 技能
guided-learning open [课程名] [--no-browser] [--port 8765]
guided-learning stop
guided-learning courses               # 以 JSON 列出课程库
echo '{"op":"course.status"}' | guided-learning --course quantum
```

最后一种写法是技能使用的操作入口：从标准输入或 `--request 文件.json` 读取一条 JSON 请求，返回 `{ok, result}` 或 `{ok:false, error}`。`--workspace <目录>` 可操作课程库之外的课程，`guided-learning-web --workspace <目录>` 则在前台为它启动界面。技能及其操作说明位于 [guided_learning/skill/](guided_learning/skill/SKILL.md)。

## 开发

```sh
python -m venv .venv
.venv/bin/python -m pip install -e ".[pdf]"        # Windows: .venv\Scripts\python.exe
.venv/bin/python -m unittest discover -s tests
.venv/bin/guided-learning setup                     # 把当前检出的技能复制给 Codex；修改技能后需重新运行

cd web && npm install
GL_HOST=http://127.0.0.1:8765 npm run dev          # 连接运行中的服务，热更新界面
npm run check && npm run build                     # 类型检查，然后生成 guided_learning/web_dist（需提交）
npx playwright test                                # 用临时示例课程运行浏览器测试
```

较大的改动前请先阅读[架构](docs/architecture.md)、[术语表](GLOSSARY.md)和[设计决策](docs/adr/)（均为英文）；面向智能体的说明在 [AGENTS.md](AGENTS.md)。任务通过 GitHub Issues 管理。

贯学采用 [MIT](LICENSE) 许可证；随附的第三方依赖保留各自的许可证，见[第三方许可声明](THIRD_PARTY_LICENSES.md)。Python 包和命令名为 `guided-learning`（包名 `codex-guided-learning`）。

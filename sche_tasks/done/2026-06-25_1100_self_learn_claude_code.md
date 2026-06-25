# self_learn_claude_code — 2026-06-25 11:00

## 主题：Hooks & Skills 可复用工作流（轮转 #4）

### 一句话
Claude Code 用"事件钩子+技能卡片"把自动化装进了开发流程，GA 差的就是这套骨架。

### 大白话解释
Hooks 像商场自动感应门——走到门口（事件触发）门自己开了（跑脚本/问 LLM）。Skills 像厨师菜谱卡片——宫保鸡丁不用每次从头想，拿出卡片照着做就行。22 种事件 + 4 种引擎（命令/LLM/代理/HTTP）覆盖了从"进办公室"到"下班"的整个会话周期。

### 对 GA 的启示
GA 的 SOP 是静态摊桌上的死文档，Claude Code 是"事件驱动+按需加载"的动态机制。最小可行偷师：在 agent_main.py 工具调度层加 pre/post hook 拦截点，30 行改动，配置从 memory/hooks.json 读取。Skill 按需加载后续轮次再搞。

---

**完整 Wiki**: `D:\知识库\GA自学\outputs\claude_code\2026-06-25.md`

**关键数据**:
- 22 个 Hook 生命周期事件（SessionStart→SessionEnd）
- 4 种 Hook 引擎：command / prompt / agent / HTTP
- Skills 核心：SKILL.md（YAML frontmatter + Markdown 指令）
- 3 层配置：个人级 → 项目级 → 本地覆盖
- GA 可行改进：Hook 拦截点（~30行）、Skill 按需加载（后续~80行）

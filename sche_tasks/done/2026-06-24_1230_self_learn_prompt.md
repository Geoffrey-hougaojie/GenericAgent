### 一句话
学会了 DSPy：与其手工反复念咒语调 prompt，不如把任务定义成输入输出接口，让 AI 自己去找最佳说法。

### 大白话解释
DSPy 就像自动炒菜机——你按按钮选"鱼香肉丝"并设定辣度，机器自己调火候翻炒，比你每次跟食堂阿姨口头描述"少辣多汤不要香菜"稳定得多。传统 prompt 调优就是你每天跟阿姨磨嘴皮子，DSPy 是把菜谱写成精确的参数规格。

### 对 GA / 工作的启示
GA 的 8 个定时任务 prompt 里写作规范（大白话、类比、三段论）重复了 N 遍，应该像 CSS 样式表一样抽出来复用；每个 prompt 要配评分标准（怎么判断输出好不好），用评分驱动迭代而非凭感觉。

---

# DSPy 框架 — 让 AI 自己调自己的提示词

> 学习日期：2026-06-24 | 学习来源：dspy.ai 官方文档 + GitHub stanfordnlp/dspy

## 💬 讲人话：DSPy 到底是个啥

你用过 ChatGPT 或 Claude 吧？每次想让它们干好一件事，你是不是反复改提示词——"请专业一点""请一步步思考""举个例子"——改完跑一遍，不行再改，像在念咒语一样。运气好了模型听话，运气不好完全跑偏。

**DSPy 做的事：你只管说"我要什么输入、什么输出"，它自己去试探几十上百种措辞，找出效果最好的那版。**

说白了：以前是你伺候 AI（反复措辞），现在是 AI 伺候你（自动调优）。

## 🍳 三个生活类比

### 类比一：食堂阿姨 vs 自动炒菜机

传统 Prompt Engineering 就像你在食堂窗口跟阿姨说："阿姨，我要那个肉，少放点辣椒，多加点汤，饭少一点，菜多一点，不要香菜……" 阿姨心情好给你打得好，心情不好手一抖全毁了。

DSPy 就像一台自动炒菜机。你只需要按按钮选"鱼香肉丝"，输入：肉 200g、笋丝 100g、辣度中。机器自动调火候、翻炒时间、调料比例。每次出来的味道都一样稳。

**你的 prompt 就是"跟阿姨说的话"，DSPy 的 Signature 就是"选菜按钮+参数"——把模糊的口头描述变成精确的规格说明。**

### 类比二：手动挡 vs 自动驾驶

手写 prompt 像开手动挡——你要自己控制离合、换挡、油门配合，新手经常熄火。换一辆车（换一个模型），离合器感觉又不一样了，得重新适应。

DSPy 像自动驾驶——你设目的地（任务目标），车自己判断路况、加速、变道。换辆车（换成 GPT-4 或 Claude），驾驶系统自己调整策略。

**这就是 DSPy 说的"Program, don't prompt"——写逻辑流程，别写提示词。**

### 类比三：租房口头约定 vs 签合同

你和房东口头约定："房租每月按时交，别太吵就行。" 结果房东觉得你朋友来住两天算"太吵"，你觉得不算。没有明确标准，纠纷就来了。

DSPy 的方式是签合同：租期多久、押金多少、能不能养宠物、违约怎么赔——统统白纸黑字。**Signature 就是这个合同模板，InputField 和 OutputField 就是填的空格。**

## 🔧 核心三件套

### 1. Signature（任务签名）——"你只管定义接口"

传统做法：写一大段 prompt："你是一个专业的邮件分类助手，请阅读以下邮件，提取事件名称和日期……"

DSPy 做法：

```python
class ExtractEvent(dspy.Signature):
    """从邮件中提取事件信息"""
    email: str = dspy.InputField()        # 输入：邮件原文
    event_name: str = dspy.OutputField()  # 输出：事件名
    date: str = dspy.OutputField()        # 输出：日期
```

就像写一个 Python 函数的类型注解一样，说清楚"输入什么类型、输出什么类型"，但具体怎么跟 LLM 说——让框架去操心。

### 2. Modules（执行策略）——"同一个任务，不同解法"

同一个 Signature，换不同的 Module 就有不同的执行方式：

- `dspy.Predict(Signature)` — 直接让模型输出答案（像问"1+1=？"）
- `dspy.ChainOfThought(Signature)` — 让模型先思考再回答（像说"你先列算式，再写答案"）
- `dspy.ReAct(Signature, tools=[...])` — 让模型调用工具，多轮推理（像说"你可以用计算器、查字典，自己决定什么时候用什么"）

**换 Module 不改 Signature，就像同一个 USB-C 接口，可以插硬盘、插显示器、插充电器。**

### 3. Optimizers / Teleprompters（自动调优器）——"AI 帮你找最佳措辞"

这是 DSPy 最颠覆的部分。你给几个示例和评分标准，DSPy 自动：

1. 生成几十种不同的 prompt 措辞
2. 每种都跑一遍测试
3. 用你的评分标准打分
4. 保留高分版本，淘汰低分版本
5. 反复迭代直到分数不再提升

```python
# 伪代码示意
optimizer = dspy.GEPA(metric=my_scoring_function, auto="medium")
optimized_program = optimizer.compile(my_program, training_data)
optimized_program.save("best_prompt.json")  # 保存最优版本
```

这就像请了一个专业的"提示词调优师"，你没日没夜地试，它自动搞定。

## 🆚 GA 现有 Prompt 对比分析

### GA 的现状：手写 Prompt 王国

GA 的定时任务都在 `sche_tasks/*.json` 里，每个任务 prompt 动辄几百行：

| 任务 | Prompt 长度 | 问题 |
|------|-------------|------|
| agent_source_reading | ~500 行 | 写作规范重复定义（铁律、三段论、讲人话...） |
| self_reflection_daily | ~300 行 | Python 代码内嵌在 prompt 中，冗长 |
| morning_brief | ~200 行 | 飞书卡片格式硬编码 |
| learning_daily_digest | ~250 行 | 4 个报告路径硬编码 |

### DSPy 视角下的改进方案

**问题 1：格式约束散落各处**

每个任务 prompt 都重复写了"禁术语堆砌""用类比""三段论"这些写作规范。DSPy 的思路是——把这些约束抽成一个 Signature：

```python
class FeynmanWritingStyle(dspy.Signature):
    """费曼学习法写作风格"""
    topic: str = dspy.InputField()
    audience_level: Literal["小白", "同事", "专家"] = dspy.InputField()
    
    explanation: str = dspy.OutputField(desc="大白话解释，≥3个生活类比，禁术语裸奔")
    ga_relevance: str = dspy.OutputField(desc="对GA/工作的直接启示")
```

这样所有学习任务共用一个写作风格 Signature，不用每个 prompt 重复定义。

**问题 2：执行步骤写死在 prompt 里**

比如 `self_reflection_daily` 的 prompt 内嵌了完整的 Python 代码。DSPy 的做法是把"读日志 → 分析 → 排课"定义成 Module pipeline：

```python
# DSPy 风格
class SelfReflection(dspy.Module):
    def __init__(self):
        self.analyze_logs = dspy.ChainOfThought(AnalyzeLogs)
        self.detect_issues = dspy.Predict(DetectIssues)
        self.plan_course = dspy.ChainOfThought(PlanCourse)
    
    def forward(self, log_path, done_dir):
        log_summary = self.analyze_logs(log_path=log_path)
        issues = self.detect_issues(summary=log_summary)
        plan = self.plan_course(issues=issues, done_dir=done_dir)
        return plan
```

代码和 prompt 分离——逻辑是代码，措辞由 DSPy 管理。

**问题 3：没有自动优化机制**

GA 的 prompt 写完后全靠人工感觉判断好坏，没有 A/B 测试，没有评分标准，没有自动迭代。

DSPy 的方式：定义评分函数 → 自动测试 → 保留最优。比如对 `agent_source_reading` 任务，可以定义"可读性评分"（用另一个 LLM 判断输出是否足够白话），然后让 DSPy 自动优化 prompt 措辞。

### 实话实说：DSPy 适不适合 GA？

**不适合直接替换。** GA 跑在 Claude Code 上，Claude Code 有自己的系统 prompt 体系，DSPy 目前主要面向 OpenAI/Anthropic 原生 API 调用场景。GA 的任务 prompt 是给 Claude Code Agent 看的"任务说明书"，不是给底层 LLM 的 raw prompt。

**但思路值得借鉴。** 以下改进可以直接做：

1. **把共享约束抽出来**：写作规范（铁律、类比、三段论）不要在 4 个任务 prompt 里重复，放到一个公共位置引用
2. **prompt 评判标准量化**：给每个任务的输出定义评分维度（可读性、准确性、完整性），用评分结果反过来指导 prompt 改进
3. **prompt 版本管理**：每次改 prompt 记版本号和效果对比，别凭感觉改完就完了

## 📊 一张图总结

| 维度 | 传统 Prompt Engineering | DSPy |
|------|------------------------|------|
| 做法 | 手工反复调 prompt 措辞 | 用代码定义任务，自动调优 |
| 稳定性 | 换个模型可能失效 | Signature 不改，底层自动适配 |
| 可维护性 | prompt 散落各处，越改越乱 | 类型化定义，像维护代码一样 |
| 优化方式 | 凭感觉试 | 定义评分标准，机器自动搜索 |
| 适合场景 | 一次性简单任务 | 需要反复运行的复杂流水线 |

## 💡 对你用 Claude Code 写代码的直接启示

1. **把"角色设定"当 Signature 写**：别写"你是一个专业的XX"，写成"输入：一段代码，输出：3 个具体改进建议+理由"
2. **约束条件集中管理**：GA 的 8 个任务 prompt 共享的写作规范（大白话、类比、三段论），应该像 CSS 样式表一样抽出来复用，不要每个 prompt 复制粘贴
3. **每个 prompt 配评分标准**：写 prompt 的同时写下"怎么判断这个 prompt 输出好不好"，未来可以用 LLM-as-judge 自动评判

## GA 进化记录

| 时间 | 改动 | 原因 | 预期效果 |
|------|------|------|----------|
| 2026-06-24 | 无代码改动 | 本周 self_learn_prompt 任务是学习 DSPy，产出 wiki 知识卡片。DSPy 直接引入 GA 不现实（GA 基于 Claude Code Agent 而非原始 API），但分离约束/量化评分的思路已记录 | 未来改造 prompt 结构时参考 |

## 📚 推荐阅读

- DSPy 官方文档：https://dspy.ai
- GitHub：https://github.com/stanfordnlp/dspy
- 核心论文：[DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines](https://arxiv.org/abs/2310.03714) (ICLR 2024)

### 一句话
Claude Code 的 CLAUDE.md 就像每个项目都有张"入职说明书"，新来的AI同事翻开就能干活，不用你每次重新教。

### 大白话解释
CLAUDE.md 说白了就是贴在项目门口的便签条——上面写着"这项目的代码风格用2空格缩进、测试命令是 npm test、API 文件都在 src/api/ 下面"。每次 Claude 进这个项目，先看便签再干活。这和去朋友家做客一样：第一次你问"拖鞋在哪"，第二次还得问，第三次朋友直接贴张纸条在门口——CLAUDE.md 就是这张纸条。你也可以在纸条上写"参考鞋柜上的说明书"（@ 导入语法），还能按房间贴不同的纸条（.claude/rules/ 路径规则）。

### 对 GA / 工作的启示
GA 目前所有记忆都是全局的（memory/ 目录），没有"这个项目专属"的概念。如果给 GA 加上 GA.md 机制，GA 在不同项目里自动切换不同的"人格"和知识，上下文信息密度直接翻倍——该项目的架构、构建命令、编码规范只在相关项目里才占 token 预算。

---

# Wiki 知识卡片：CLAUDE.md — 项目级指令文件

## 🎯 核心概念（费曼学习法）

### 一句话说清楚
**CLAUDE.md 是放在项目根目录的 Markdown 文件，Claude Code 每次启动自动读，里面写"这个项目的规矩"。**

### 生活类比 1：入职说明书
你新招了一个AI实习生。第一次你告诉他："代码用2空格缩进、提交前跑测试、API 文件在 src/api/"。第二次换了个新会话，他又忘了——你又得重新教。CLAUDE.md 就是贴在工位上的"新员工入职说明书"，实习生每天上班第一件事就是看它。

### 生活类比 2：朋友家的便签条
去朋友家做客，第一次问"WiFi密码多少"，第二次还问，第三次朋友直接在冰箱上贴张条"WiFi: 12345678，拖鞋在鞋柜左边"。CLAUDE.md 就是这张冰箱上的便签——省得你每次都问同样的问题。

### 生活类比 3：考试开卷的"公式卡"
考试允许带一张A4纸，你把最常用但总记不住的公式写在上面。CLAUDE.md 就是这张公式卡——不是代替你思考，而是让你不用把脑容量浪费在死记硬背上。

---

## 📋 CLAUDE.md 的设计细节

### 四层优先级（从大到小）

| 层级 | 位置 | 谁管 | 例子 |
|------|------|------|------|
| 公司级 | `/etc/claude-code/CLAUDE.md`（Linux） | IT/DevOps | 安全合规、代码审查标准 |
| 用户级 | `~/.claude/CLAUDE.md` | 你自己 | 个人代码风格偏好 |
| 项目级 | `./CLAUDE.md` 或 `./.claude/CLAUDE.md` | 团队（Git管理） | 项目架构、构建命令 |
| 本地级 | `./CLAUDE.local.md` | 你自己（gitignore） | 你的测试数据路径、沙盒URL |

**加载规则**：从文件系统根向下走到当前目录，每层的 CLAUDE.md 都拼接进上下文。越靠近当前目录的优先级越高（后加载=覆盖感更强）。

### 目录树自动发现
```
/home/user/projects/
├── CLAUDE.md              ← 加载顺序: 1 (最宽泛)
└── my-app/
    ├── CLAUDE.md          ← 加载顺序: 2
    └── src/
        ├── CLAUDE.md      ← 加载顺序: 3 (最具体)
        └── api/
            └── CLAUDE.md  ← 按需加载（读到这个目录时才加载）
```

### .claude/rules/ —— 模块化规则
```
my-app/
└── .claude/
    ├── CLAUDE.md           # 主指令
    └── rules/
        ├── code-style.md   # 无条件加载
        ├── testing.md      # 无条件加载
        └── api-design.md   # 带 YAML frontmatter 限定路径
```
```yaml
# api-design.md 顶部
---
paths:
  - "src/api/**/*.ts"
---
# API设计规范
- 所有接口必须有输入验证
- 使用标准错误响应格式
```

### @ 导入语法
CLAUDE.md 里可以用 `@README.md` 导入其他文件，递归最多4层。

### Auto Memory（自动记忆）—— 与 CLAUDE.md 互补
- **CLAUDE.md**：你写给 Claude 的规矩（人工维护）
- **Auto Memory**：Claude 自己写的笔记（自动积累）
  - 比如：你说"不对，这个项目用 yarn 不是 npm" → Claude 自动写到 auto memory
  - 每个会话只加载前 200 行或 25KB
  - 子 Agent 也可以有自己的 auto memory

---

## 🔍 第一性原理分析

### 问题1：这个设计让上下文更密了还是更稀了？
**更密了！** 因为项目特定的信息（构建命令、文件路径、编码规范）只在相关项目中才注入上下文。全域记忆（GA 的 memory/）会把所有项目的信息混在一起，造成"噪音污染"。打个比方：你在一家餐厅当厨师，如果 memory/ 里同时存了中餐菜谱、日料菜谱、法餐菜谱，每次做中餐时还要翻日料菜谱——CLAUDE.md 按项目隔离后，你做中餐时只看中餐菜谱。

### 问题2：GA 现在的等价物是什么？差在哪？

| 能力 | Claude Code | GA 现状 | 差距 |
|------|-------------|---------|------|
| 项目级指令 | CLAUDE.md | ❌ 无 | GA 所有记忆都是全局的 |
| 自动发现 | 目录树向上遍历 | ❌ 无 | GA 需要手动在 memory/ 写 |
| 分层加载 | 公司→用户→项目→本地 | 部分有：Constitution(L0) → memory/(L2/L3) | 但全是全局作用域 |
| 路径规则 | .claude/rules/ | ❌ 无 | 没有"只对特定文件生效"的机制 |
| 导入其他文件 | @ 语法 | ❌ 无 | 没有 |
| 自动记忆 | Auto Memory | 手动触发 update_working_checkpoint | GA 的半自动化 vs Claude 的全自动 |

GA 的等价物：Constitution（系统提示）+ memory/ global_mem（L2）+ memory/*.md/*.py（L3 SOP） + working checkpoint。**但所有这些都作用于全局，没有项目隔离。**

### 问题3：能不能偷过来？改几行代码？
**能！核心改动很小——在 `get_system_prompt()` 里加几行代码。**

---

## 🧬 GA.md 方案设计

### 设计目标
让 GA 在启动时自动发现并加载当前工作目录下的 `GA.md`，实现项目级上下文注入。

### 改动方案（最小可行版本）

**改动文件**：`agentmain.py` 的 `get_system_prompt()` 函数（第39-43行）

**原理**：在 `get_system_prompt()` 末尾追加 GA.md 内容。从当前工作目录向上遍历目录树，找到所有 `GA.md` 文件，拼接进系统提示。

**代码改动**（在 `get_system_prompt()` 的 `return prompt` 之前插入）：

```python
def get_system_prompt():
    with open(os.path.join(script_dir, f'assets/sys_prompt{lang_suffix}.txt'), 'r', encoding='utf-8') as f: prompt = f.read()
    prompt += f"\nToday: {time.strftime('%Y-%m-%d %a')}\n"
    prompt += get_global_memory()
    
    # === NEW: GA.md 项目级上下文注入 ===
    ga_md_content = _load_project_ga_md()
    if ga_md_content:
        prompt += f"\n\n## Project GA.md (项目级上下文)\n{ga_md_content}"
    # === END NEW ===
    
    return prompt

def _load_project_ga_md():
    """从当前工作目录向上遍历，收集所有 GA.md 文件内容"""
    cwd = os.getcwd()
    parts = []
    # 收集从根到 cwd 路径上的所有目录
    dirs_to_check = []
    path = cwd
    while True:
        dirs_to_check.append(path)
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    # 从根到当前目录（远→近），确保最近的覆盖感最强
    dirs_to_check.reverse()
    for d in dirs_to_check:
        for fname in ['GA.md', '.ga/GA.md']:
            fpath = os.path.join(d, fname)
            if os.path.isfile(fpath):
                try:
                    content = open(fpath, 'r', encoding='utf-8').read()
                    # 限制：最多 3000 字符，避免吃掉过多上下文
                    if len(content) > 3000:
                        content = content[:3000] + '\n\n... (GA.md truncated to 3000 chars)'
                    parts.append(f"<!-- from {fpath} -->\n{content}")
                except Exception:
                    pass
    return '\n\n'.join(parts) if parts else ''
```

### 上下文密度评估
- ✅ 更密：项目信息只在相关项目中注入，不浪费无关项目 token
- ✅ 按需：从根到当前目录的层次结构天然形成优先级
- ✅ 零配置：不写 GA.md 就不注入，向后兼容
- ⚠️ 风险：GA.md 太长会吃掉 token 预算（加了 3000 字截断保护）

### 进阶扩展（未来版本）
1. **GA.local.md**：gitignore 的本地偏好文件
2. **路径规则**：`.ga/rules/*.md` + YAML frontmatter 限定文件作用域
3. **@ 导入**：GA.md 中用 `@path/to/file` 引用其他文件
4. **自动生成**：`/init` 命令分析项目结构自动生成 GA.md

---

## GA 进化记录

| 日期 | 改动 | 原因 | 效果 |
|------|------|------|------|
| 2026-06-24 | 提出 GA.md 方案（未实施，待沙盒验证） | 对标 Claude Code 的 CLAUDE.md | 项目级上下文隔离，提高信息密度 |

---

## 📎 参考
- 官方文档：https://code.claude.com/docs/en/memory
- 相关页面：https://code.claude.com/docs/en/claude-directory （.claude 目录结构）
- 相关页面：https://code.claude.com/docs/en/features-overview （扩展机制对比）

"""
安全守卫插件 — hook tool_before，拦截危险操作
基于 arXiv 2606.26057 "不可解雇的安全内核" 思路，在工具调用前做安全检查
。matcher 过滤仅 file_write/file_patch/code_run 触发，其余工具零开销。
"""
import os, json, sys
from datetime import datetime
from plugins.hooks import register

GA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 受保护文件 — 绝对不允许删除/覆盖
PROTECTED = {
    os.path.join(GA_ROOT, 'mykey.py'),
    os.path.join(GA_ROOT, 'ga.py'),
    os.path.join(GA_ROOT, 'agent_loop.py'),
    os.path.join(GA_ROOT, 'agentmain.py'),
    os.path.join(GA_ROOT, 'plugins', 'hooks.py'),
    os.path.join(GA_ROOT, 'plugins', 'safety_guard.py'),  # 自保护
}

# 受保护目录 — 不允许目录级操作
PROTECTED_DIRS = {
    os.path.join(GA_ROOT, 'memory'),
    os.path.join(GA_ROOT, 'plugins'),
    os.path.join(GA_ROOT, 'assets'),
}

LOG_FILE = os.path.join(GA_ROOT, 'temp', 'safety_guard.log')

@register('tool_before')
def guard_dangerous_ops(ctx: dict):
    """拦截危险操作。agent_loop dispatch 检查 ctx['_blocked'] 以阻断执行。"""
    tool_name = ctx.get('tool_name', '')
    args = ctx.get('args', {})
    mode = args.get('mode', 'overwrite')

    # === file_write / file_patch ===
    if tool_name in ('file_write', 'file_patch'):
        target = os.path.abspath(args.get('path', ''))
        for p in PROTECTED:
            if target == os.path.abspath(p):
                _alert(f"BLOCKED: {tool_name} 受保护文件 {target}")
                ctx['_blocked'] = True
                return ctx
        for d in PROTECTED_DIRS:
            if target.startswith(os.path.abspath(d) + os.sep) or target == os.path.abspath(d):
                _alert(f"BLOCKED: {tool_name} 受保护目录 {target}")
                ctx['_blocked'] = True
                return ctx
        # 禁止覆写含重要后缀的文件
        if mode == 'overwrite' and target.endswith('.py') and 'learn_sandbox' not in target:
            _alert(f"INTERCEPT: {tool_name} overwrite .py 文件 {target}（请走 learn_sandbox.py）")
            ctx['_blocked'] = True
            return ctx
        return ctx

    # === code_run ===
    if tool_name == 'code_run':
        script = args.get('script', '')
        dangerous = ['rm -rf', 'del /f', 'format', 'shutdown', ':(){', 'os.remove', 'shutil.rmtree']
        for d in dangerous:
            if d in script.lower():
                _alert(f"BLOCKED: code_run 危险命令 '{d}'")
                ctx['_blocked'] = True
                return ctx
        return ctx

    return ctx


def _alert(msg):
    """记录安全告警"""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"🛡️ [SafetyGuard] {msg}", file=sys.stderr)

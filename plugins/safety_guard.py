"""
安全守卫插件 — hook tool_before，拦截危险操作
基于 arXiv 2606.26057 "不可解雇的安全内核" 思路，在工具调用前做安全检查
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
}

# 受保护目录 — 不允许整个目录删除
PROTECTED_DIRS = {
    os.path.join(GA_ROOT, 'memory'),
    os.path.join(GA_ROOT, 'plugins'),
    os.path.join(GA_ROOT, 'assets'),
}

LOG_FILE = os.path.join(GA_ROOT, 'temp', 'safety_guard.log')

@register('tool_before')
def guard_dangerous_ops(ctx: dict):
    """拦截对受保护文件的危险操作"""
    tool_name = ctx.get('tool_name', '')
    args = ctx.get('args', {})

    if tool_name not in ('file_write', 'file_patch', 'code_run'):
        return ctx

    target = os.path.abspath(args.get('path', ''))

    # 检查是否触及受保护文件
    for p in PROTECTED:
        if target == os.path.abspath(p):
            _alert(f"BLOCKED: {tool_name} 尝试操作受保护文件 {target}")
            ctx['args'] = dict(args, path=target, _blocked=True)
            return ctx

    # 检查 code_run 中的危险命令
    if tool_name == 'code_run':
        script = args.get('script', '')
        code_type = args.get('type', 'python')
        dangerous = ['rm -rf', 'del /f', 'format', 'shutdown', ':(){']
        for d in dangerous:
            if d in script.lower():
                _alert(f"BLOCKED: code_run 包含危险命令 '{d}'")
                ctx['args'] = dict(args, script='# BLOCKED by safety_guard\nprint("危险操作已拦截")')
                return ctx

    return ctx


def _alert(msg):
    """记录安全告警"""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"🛡️ [SafetyGuard] {msg}", file=sys.stderr)

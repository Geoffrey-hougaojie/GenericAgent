"""
工具指标插件 — hook tool_after + agent_after，采集工具执行数据
为 self_reflection_daily 和 prompt_optimize_daily 提供量化基础
"""
import os, json, time
from datetime import datetime
from plugins.hooks import register

GA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS_FILE = os.path.join(GA_ROOT, 'temp', 'tool_metrics.json')

_turn_start = time.time()
_session_tools = {}

@register('agent_before')
def reset_session(ctx: dict):
    global _turn_start, _session_tools
    _turn_start = time.time()
    _session_tools = {}
    return ctx


@register('tool_before')
def record_tool_start(ctx: dict):
    """记录工具调用开始时间"""
    tool_name = ctx.get('tool_name', '')
    if tool_name and tool_name != 'no_tool':
        _session_tools[id(ctx)] = {
            'tool': tool_name,
            'start': time.time(),
            'args_preview': _compact_args(ctx.get('args', {}))
        }
    return ctx


@register('agent_after')
def flush_metrics(ctx: dict):
    """会话结束时写入指标文件"""
    stats = _load_metrics()
    elapsed = time.time() - _turn_start

    today = datetime.now().strftime('%Y-%m-%d')
    if today not in stats:
        stats[today] = {'sessions': 0, 'tools': {}, 'total_time': 0}

    stats[today]['sessions'] += 1
    stats[today]['total_time'] += round(elapsed, 1)

    for tid, info in _session_tools.items():
        tn = info['tool']
        if tn not in stats[today]['tools']:
            stats[today]['tools'][tn] = 0
        stats[today]['tools'][tn] += 1

    # 只保留最近 30 天
    keys = sorted(stats.keys())[-30:]
    stats = {k: stats[k] for k in keys}

    with open(METRICS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    return ctx


def _load_metrics():
    try:
        with open(METRICS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


def _compact_args(args):
    """压缩参数预览"""
    a = {k: v for k, v in args.items() if not k.startswith('_')}
    s = json.dumps(a, ensure_ascii=False)
    return s[:80] + '...' if len(s) > 80 else s

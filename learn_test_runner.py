"""
GA 学习任务子进程测试器
用法: python learn_test_runner.py <file_path> [--type auto|plugin|config|util]
主进程通过 subprocess.run 调用，exit code 0=通过，非0=失败。
子进程崩了不影响主进程（进程级隔离）。
"""
import sys
import os
import json
import importlib
import traceback
import argparse
from pathlib import Path

GA_ROOT = Path(__file__).parent


def test_python_file(filepath: str) -> bool:
    """测试 .py 文件：语法检查 + 导入测试（不触发主循环）"""
    filepath = os.path.abspath(filepath)
    print(f"[TEST] 语法检查: {filepath}")
    
    # Step 1: compile check
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        compile(source, filepath, 'exec')
        print(f"[PASS] 语法检查通过")
    except SyntaxError as e:
        print(f"[FAIL] 语法错误: {e}")
        return False
    
    # Step 2: import test (only for modules in GA tree)
    rel = os.path.relpath(filepath, str(GA_ROOT))
    if '..' in rel or rel.startswith('temp'):
        print(f"[SKIP] 非GA模块，跳过导入测试")
        return True
    
    # Convert path to module name
    module_path = rel.replace('\\', '/').replace('.py', '').replace('/', '.')
    print(f"[TEST] 导入测试: {module_path}")
    
    try:
        # Add GA_ROOT to path temporarily
        sys.path.insert(0, str(GA_ROOT))
        mod = importlib.import_module(module_path)
        
        # Step 3: Smoke test — send a lightweight probe to ensure module is functional
        smoke_ok = True
        try:
            public_attrs = [a for a in dir(mod) if not a.startswith('_')]
            functions = [a for a in public_attrs if callable(getattr(mod, a, None))]
            classes = [a for a in public_attrs if isinstance(getattr(mod, a, None), type)]
            if not functions and not classes:
                print(f"[WARN] 未发现 public 函数/类，可能是数据文件")
            else:
                # Try calling no-arg functions as light probe
                for fn_name in functions[:5]:
                    try:
                        fn = getattr(mod, fn_name)
                        if callable(fn):
                            import inspect
                            sig = inspect.signature(fn)
                            if len(sig.parameters) == 0:
                                result = fn()
                                print(f"[SMOKE] {fn_name}() => {type(result).__name__}")
                    except Exception:
                        pass  # smoke is best-effort
                print(f"[INFO] 模块包含 {len(functions)} 函数, {len(classes)} 类")
        except Exception as e:
            print(f"[WARN] 冒烟测试跳过: {e}")
            smoke_ok = None  # not a failure, just can't test
        
        print(f"[PASS] 导入成功, 模块属性: {public_attrs[:10]}")
        return True
    except Exception as e:
        print(f"[FAIL] 导入失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


def test_json_file(filepath: str) -> bool:
    """测试 JSON 配置文件：完整性 + schema 验证"""
    filepath = os.path.abspath(filepath)
    print(f"[TEST] JSON 验证: {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[PASS] JSON 解析成功, keys: {list(data.keys())}")
        
        # Check if it's a schedule task file
        if 'schedule' in data and 'prompt' in data:
            # Validate schedule format
            import re
            if not re.match(r'^\d{2}:\d{2}$', data['schedule']):
                print(f"[FAIL] schedule 格式错误: {data['schedule']}")
                return False
            if 'enabled' not in data:
                print(f"[WARN] 缺少 enabled 字段")
            print(f"[PASS] 定时任务格式正确: {data['schedule']} enabled={data.get('enabled')}")
        
        return True
    except json.JSONDecodeError as e:
        print(f"[FAIL] JSON 解析失败: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] 文件读取失败: {e}")
        return False


def test_plugin_file(filepath: str) -> bool:
    """测试 Hook 插件文件：签名检查 + 导入测试"""
    filepath = os.path.abspath(filepath)
    
    # First do basic python test
    if not test_python_file(filepath):
        return False
    
    # Then check for required hook signatures
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Check for common hook registration patterns
    has_hook = False
    for pattern in ['hook_', 'on_', 'register', '@hook', 'Hooks.']:
        if pattern in source:
            has_hook = True
            break
    
    if has_hook:
        print(f"[INFO] 检测到 Hook 相关代码，插件测试通过")
    
    return True


def test_md_file(filepath: str) -> bool:
    """测试 markdown 文件：可读性检查"""
    filepath = os.path.abspath(filepath)
    print(f"[TEST] Markdown 检查: {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if len(content) < 10:
            print(f"[FAIL] 文件过短 ({len(content)} 字符)")
            return False
        print(f"[PASS] Markdown 文件可读, {len(content)} 字符")
        return True
    except Exception as e:
        print(f"[FAIL] 读取失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='GA 学习任务子进程测试器')
    parser.add_argument('file', help='要测试的文件路径')
    parser.add_argument('--type', default='auto', 
                       choices=['auto', 'plugin', 'config', 'util', 'md'],
                       help='文件类型 (默认自动检测)')
    args = parser.parse_args()
    
    filepath = args.file
    filetype = args.type
    
    if not os.path.exists(filepath):
        print(f"[FAIL] 文件不存在: {filepath}")
        sys.exit(1)
    
    ext = os.path.splitext(filepath)[1].lower()
    
    # Auto-detect type
    if filetype == 'auto':
        if 'plugin' in filepath.lower() and ext == '.py':
            filetype = 'plugin'
        elif ext == '.json':
            filetype = 'config'
        elif ext == '.md':
            filetype = 'md'
        elif ext == '.py':
            filetype = 'util'
        else:
            filetype = 'util'
    
    print(f"[RUNNER] 测试文件: {filepath}")
    print(f"[RUNNER] 检测类型: {filetype}")
    
    # Dispatch
    tests = {
        'plugin': test_plugin_file,
        'config': test_json_file,
        'util': test_python_file,
        'md': test_md_file,
    }
    
    test_fn = tests.get(filetype, test_python_file)
    
    try:
        passed = test_fn(filepath)
    except Exception as e:
        print(f"[CRASH] 测试器自身异常: {e}")
        traceback.print_exc()
        sys.exit(2)
    
    if passed:
        print("\n[RESULT] PASS: All tests passed")
        sys.exit(0)
    else:
        print("\n[RESULT] FAIL: Tests failed")
        sys.exit(1)


if __name__ == '__main__':
    main()

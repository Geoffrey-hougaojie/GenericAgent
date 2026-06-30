"""
GA 学习沙箱 — Copy-on-Write 全流程
用法: python learn_sandbox.py <original_file> --patch <patch_script.py>
      python learn_sandbox.py <original_file> --content <new_content>

核心原则：原文件在被证明安全前绝不触碰。
流程：copy到sandbox → 改副本 → 子进程测试 → 通过才写回 → git commit
"""
import sys
import os
import json
import shutil
import subprocess
import tempfile
import argparse
from pathlib import Path
from datetime import datetime

GA_ROOT = Path(__file__).parent
SANDBOX_DIR = GA_ROOT / 'temp' / 'learn_sandbox'


def ensure_sandbox():
    """确保沙箱目录存在且干净"""
    if SANDBOX_DIR.exists():
        shutil.rmtree(SANDBOX_DIR)
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)


def copy_to_sandbox(original: str) -> str:
    """复制文件到沙箱，返回沙箱中的路径"""
    original = os.path.abspath(original)
    rel = os.path.relpath(original, str(GA_ROOT))
    sandbox_path = SANDBOX_DIR / rel
    sandbox_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, sandbox_path)
    print(f"[SANDBOX] Copy: {original} -> {sandbox_path}")
    return str(sandbox_path)


def apply_patch_file(sandbox_path: str, patch_script: str):
    """执行补丁脚本修改沙箱文件"""
    print(f"[SANDBOX] Patch: {patch_script}")
    # The patch script is a Python file that modifies the sandbox_path
    # It uses file_patch/file_write with the sandbox path
    exec(open(patch_script, 'r', encoding='utf-8').read(), {
        '__file__': patch_script,
        'SANDBOX_PATH': sandbox_path,
    })
    print(f"[SANDBOX] Patch applied")


def apply_content(sandbox_path: str, content: str):
    """直接写入新内容到沙箱文件"""
    with open(sandbox_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[SANDBOX] Content written ({len(content)} bytes)")


def run_test(sandbox_path: str, timeout: int = 30) -> bool:
    """在子进程中运行测试"""
    runner = str(GA_ROOT / 'learn_test_runner.py')
    
    # For sandbox testing, we need the test runner to use the sandbox path
    # but still resolve imports relative to GA_ROOT (for dependencies)
    # We set PYTHONPATH to include sandbox dir so imports work
    
    env = os.environ.copy()
    sandbox_root = str(SANDBOX_DIR)
    existing_path = env.get('PYTHONPATH', '')
    env['PYTHONPATH'] = f"{sandbox_root}{os.pathsep}{existing_path}"
    
    print(f"[SANDBOX] Testing: {sandbox_path}")
    print(f"[SANDBOX] PYTHONPATH prepend: {sandbox_root}")
    
    try:
        r = subprocess.run(
            [sys.executable, '-u', runner, sandbox_path],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(GA_ROOT),
            env=env,
        )
        print(r.stdout)
        if r.stderr:
            print("STDERR:", r.stderr[:500])
        
        if r.returncode == 0:
            print("[SANDBOX] TEST PASSED")
            return True
        else:
            print(f"[SANDBOX] TEST FAILED (exit {r.returncode})")
            return False
    except subprocess.TimeoutExpired:
        print(f"[SANDBOX] TEST TIMEOUT ({timeout}s)")
        return False
    except Exception as e:
        print(f"[SANDBOX] TEST CRASH: {e}")
        return False


def promote_to_original(sandbox_path: str, original_path: str):
    """测试通过 → 写回原文件"""
    original_path = os.path.abspath(original_path)
    shutil.copy2(sandbox_path, original_path)
    print(f"[SANDBOX] Promote: {sandbox_path} -> {original_path}")


def git_commit(original_path: str, task_name: str, description: str) -> str:
    """自动合并到主分支"""
    try:
        r = subprocess.run(
            ['git', 'add', original_path],
            capture_output=True, text=True, timeout=10,
            cwd=str(GA_ROOT),
        )
        if r.returncode != 0:
            print(f"[SANDBOX] git add failed: {r.stderr}")
            return "git_add_failed"
        
        msg = f"learn: {description} [auto from {task_name}]"
        r = subprocess.run(
            ['git', 'commit', '-m', msg],
            capture_output=True, text=True, timeout=10,
            cwd=str(GA_ROOT),
        )
        if r.returncode != 0:
            print(f"[SANDBOX] git commit failed: {r.stderr}")
            return "git_commit_failed"
        
        # Get commit hash
        r = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=5,
            cwd=str(GA_ROOT),
        )
        commit_hash = r.stdout.strip()
        
        # Push
        r = subprocess.run(
            ['git', 'push'],
            capture_output=True, text=True, timeout=15,
            cwd=str(GA_ROOT),
        )
        push_ok = "push_ok" if r.returncode == 0 else "push_failed"
        if r.returncode != 0:
            print(f"[SANDBOX] git push failed (non-blocking): {r.stderr[:200]}")
        
        result = f"{commit_hash} ({push_ok})"
        print(f"[SANDBOX] Git: {result}")
        return result
    except Exception as e:
        print(f"[SANDBOX] git error: {e}")
        return f"git_error:{e}"


def main():
    parser = argparse.ArgumentParser(description='GA 学习沙箱 CoW 全流程')
    parser.add_argument('original', help='原始文件路径')
    parser.add_argument('--task', default='unknown', help='任务名称（用于git msg）')
    parser.add_argument('--desc', default='auto learn change', help='改动简述')
    parser.add_argument('--timeout', type=int, default=30, help='测试超时(秒)')
    
    # Mutually exclusive: how to modify
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--patch', help='补丁脚本.py（操作SANDBOX_PATH）')
    group.add_argument('--content', help='直接写入的新内容（命令行参数，小文件用）')
    group.add_argument('--content-file', help='从文件读取新内容（推荐，避免转义问题）')
    
    args = parser.parse_args()
    
    original = os.path.abspath(args.original)
    if not os.path.exists(original):
        print(f"[FAIL] 文件不存在: {original}")
        sys.exit(1)
    
    print(f"[SANDBOX] === CoW Sandbox Start ===")
    print(f"[SANDBOX] Original: {original}")
    print(f"[SANDBOX] Task: {args.task}")
    
    # Step 1: Ensure clean sandbox
    ensure_sandbox()
    
    # Step 2: Copy to sandbox
    sandbox_path = copy_to_sandbox(original)
    
    # Step 3: Modify sandbox copy
    if args.patch:
        if not os.path.exists(args.patch):
            print(f"[FAIL] Patch script not found: {args.patch}")
            sys.exit(1)
        apply_patch_file(sandbox_path, args.patch)
    elif args.content:
        apply_content(sandbox_path, args.content)
    elif args.content_file:
        if not os.path.exists(args.content_file):
            print(f"[FAIL] Content file not found: {args.content_file}")
            sys.exit(1)
        with open(args.content_file, 'r', encoding='utf-8') as f:
            content = f.read()
        apply_content(sandbox_path, content)
    
    # Step 4: Test sandbox copy
    passed = run_test(sandbox_path, timeout=args.timeout)
    
    if not passed:
        print(f"\n[RESULT] FAIL: Tests failed, sandbox discarded. Original untouched.")
        shutil.rmtree(SANDBOX_DIR)
        sys.exit(1)
    
    # Step 5: Promote to original
    promote_to_original(sandbox_path, original)
    
    # Step 6: Git commit
    git_result = git_commit(original, args.task, args.desc)
    
    print(f"\n[RESULT] PASS: Change applied and committed")
    print(f"[RESULT] File: {original}")
    print(f"[RESULT] Git: {git_result}")
    
    # Cleanup
    shutil.rmtree(SANDBOX_DIR)
    sys.exit(0)


if __name__ == '__main__':
    main()

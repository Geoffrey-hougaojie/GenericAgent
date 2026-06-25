"""独立调度器进程 - 不受 agent 对话周期限制
触发时将任务写入 trigger 文件，agent 每轮检查并执行"""
import sys, os, time

sys.path.insert(0, r"D:\GenericAgent")
sys.path.insert(0, r"D:\GenericAgent\reflect")

from reflect.scheduler import check, _logger

INTERVAL = 60
TRIGGER_FILE = os.path.join(os.path.dirname(__file__), ".pending_task.txt")

print(f"[scheduler_launcher] PID={os.getpid()} interval={INTERVAL}s")

while True:
    try:
        result = check()
        if result:
            # 写入 trigger 文件（agent 每轮读取并执行）
            with open(TRIGGER_FILE, 'w', encoding='utf-8') as f:
                f.write(result)
            _logger.info(f"TASK_QUEUED to trigger file ({len(result)} chars)")
            print(f"[QUEUED] {result[:100]}...")
    except Exception as e:
        _logger.error(f"check() exception: {e}")
        print(f"[ERR] {e}")
    time.sleep(INTERVAL)

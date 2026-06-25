"""
cron_daemon.py — Hermes-style Gateway for GenericAgent
(v3.1 - self-contained logger, pythonw-safe)

Architecture (mirrors Hermes' Gateway):
  1. Lightweight daemon (no agent/browser) runs 24/7
  2. Every 60s calls scheduler.check() (like Hermes tick())
  3. When task due → writes task to temp/cron_<taskid>/input.txt
  4. Spawns: python agentmain.py --task cron_<taskid> (like Hermes 'cron fire')
  5. Agent subprocess executes task (web+LLM+file+feishu), writes output, exits

Stop:  python cron_daemon.py --stop
"""

import os, sys, time, re, json, subprocess, signal
import logging, io

# ---- safe stdout (pythonw has no console) ----
def _p(*args, **kwargs):
    try:
        sys.stdout = io.TextIOWrapper(
            open(sys.stdout.fileno(), 'wb', closefd=False),
            encoding='utf-8', errors='replace'
        )
    except:
        pass
    try:
        print(*args, **kwargs, flush=True)
    except (OSError, UnicodeEncodeError, ValueError):
        pass

# ---- constants ----
GA_ROOT = r"D:\GenericAgent"
SCHE_DIR = os.path.join(GA_ROOT, "sche_tasks")
sys.path.insert(0, GA_ROOT)
sys.path.insert(0, os.path.join(GA_ROOT, "reflect"))

TASK_DIR = os.path.join(GA_ROOT, "temp")
AGENTMAIN = os.path.join(GA_ROOT, "agentmain.py")
PID_FILE = os.path.join(SCHE_DIR, ".cron_daemon_pid")
STOP_FILE = os.path.join(SCHE_DIR, ".cron_daemon_stop")
LOG_FILE = os.path.join(SCHE_DIR, "cron_daemon.log")

INTERVAL = 60          # tick interval (Hermes default: 60s)
TASK_TIMEOUT = 1800    # max 30 min per task

# ---- self-contained logger (NOT inherited from scheduler) ----
_log = logging.getLogger("cron_daemon")
_log.setLevel(logging.INFO)
if not _log.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
    fh.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M'
    ))
    _log.addHandler(fh)
    # Also add a null handler to prevent "No handlers" warning
    _log.addHandler(logging.NullHandler())


def _stop_existing():
    """Send stop signal and kill existing daemon."""
    with open(STOP_FILE, "w") as f:
        f.write("stop")
    
    if os.path.exists(PID_FILE):
        try:
            pid = int(open(PID_FILE).read().strip())
            os.kill(pid, signal.SIGTERM)
            _p(f"[cron_daemon] Sent SIGTERM to PID={pid}")
            os.remove(PID_FILE)
        except Exception as e:
            _p(f"[cron_daemon] Kill existing failed: {e}")


def _parse_task_info(prompt):
    """Extract task_id and report_path from scheduler.check() output."""
    tid = "unknown"
    rpt = ""
    for line in prompt.split("\n"):
        if line.startswith("[定时任务]"):
            tid = line.replace("[定时任务]", "").strip()
        if line.startswith("[报告路径]"):
            rpt = line.replace("[报告路径]", "").strip()
    return tid, rpt


def main():
    if "--stop" in sys.argv:
        _stop_existing()
        _p("[cron_daemon] Stop signal sent.")
        return

    for f in [STOP_FILE]:
        if os.path.exists(f):
            os.remove(f)

    os.makedirs(SCHE_DIR, exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    _log.info(f"cron_daemon v3.1 started PID={os.getpid()} tick={INTERVAL}s")
    _p(f"[cron_daemon v3.1] Hermes-style Gateway (lightweight, self-logged)")
    _p(f"  PID={os.getpid()}  tick={INTERVAL}s  timeout={TASK_TIMEOUT}s  log={LOG_FILE}")

    # Import scheduler (port lock guards against duplicate daemon)
    try:
        from reflect.scheduler import check
    except Exception as e:
        _log.error(f"Failed to import scheduler: {e}")
        _p(f"[cron_daemon] FATAL: cannot import scheduler: {e}")
        return

    _log.info("scheduler imported, entering main loop")
    active_jobs = {}
    tick = 0

    while True:
        if os.path.exists(STOP_FILE):
            _log.info("stop signal received, exiting")
            _p("[cron_daemon] Stop signal received, exiting.")
            os.remove(STOP_FILE)
            for tid, job in active_jobs.items():
                try:
                    job["proc"].kill()
                    _log.info(f"killed active job {tid}")
                except:
                    pass
            break

        tick += 1
        try:
            task_prompt = check()
            if task_prompt:
                tid, rpt = _parse_task_info(task_prompt)
                
                # Guard: skip if this task is already being processed
                if tid in active_jobs:
                    proc = active_jobs[tid]["proc"]
                    if proc.poll() is None:
                        _log.info(f"TASK_SKIP: {tid} (already running PID={proc.pid})")
                        _p(f"[cron_daemon]   SKIP {tid} (already running PID={proc.pid})")
                        # fall through to check active jobs below, skip spawn
                    else:
                        # zombie cleanup
                        del active_jobs[tid]
                        _log.info(f"TASK_CLEANUP: {tid} zombie removed")
                        # proceed to spawn
                else:
                    _log.info(f"TASK_DUE: {tid} rpt={rpt}")
                    _p(f"[cron_daemon] > TICK #{tick} -- TASK DUE: {tid}")
                
                # Only spawn if not already active
                if tid not in active_jobs:
                    cron_dir = os.path.join(TASK_DIR, f"cron_{tid}")
                    os.makedirs(cron_dir, exist_ok=True)
                    input_file = os.path.join(cron_dir, "input.txt")
                    with open(input_file, "w", encoding="utf-8") as f:
                        f.write(task_prompt)
                    
                    cmd = [sys.executable, AGENTMAIN, "--task", f"cron_{tid}", "--nobg"]
                    pyw = sys.executable.replace("python.exe", "pythonw.exe")
                    if os.path.exists(pyw):
                        cmd[0] = pyw

                    creationflags = 0x00000008  # DETACHED_PROCESS

                    proc = subprocess.Popen(
                        cmd, cwd=GA_ROOT, creationflags=creationflags,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    
                    active_jobs[tid] = {
                        "proc": proc, "start": time.time(),
                        "rpt": rpt, "cron_dir": cron_dir
                    }
                    
                    _log.info(f"spawned agent PID={proc.pid} task_dir=cron_{tid}")
                    _p(f"[cron_daemon]   Spawned agent PID={proc.pid} for {tid}")

            # Check active jobs
            finished = []
            for jtid, job in active_jobs.items():
                proc = job["proc"]
                ret = proc.poll()
                if ret is not None:
                    output_file = os.path.join(job["cron_dir"], "output.txt")
                    out_size = os.path.getsize(output_file) if os.path.exists(output_file) else 0
                    
                    if ret == 0 and out_size > 0:
                        _log.info(f"job_completed: {jtid} output={out_size}B rc={ret}")
                        _p(f"[cron_daemon] OK {jtid} completed (output={out_size}B, rc={ret})")
                    else:
                        _log.error(f"job_failed: {jtid} rc={ret} output={out_size}B")
                        _p(f"[cron_daemon] FAIL {jtid} (rc={ret}, output={out_size}B)")
                    
                    finished.append(jtid)
                elif time.time() - job["start"] > TASK_TIMEOUT:
                    _log.error(f"job_timeout: {jtid}")
                    _p(f"[cron_daemon] TIMEOUT {jtid}, killing...")
                    try:
                        proc.kill()
                    except:
                        pass
                    finished.append(jtid)

            for jtid in finished:
                del active_jobs[jtid]

            if tick % 60 == 0:
                active_str = ", ".join(active_jobs.keys()) if active_jobs else "none"
                _log.info(f"heartbeat TICK={tick} active={active_str}")
                # Heartbeat also written to scheduler.log for centralized monitoring
                try:
                    from reflect.scheduler import _logger as s_logger
                    s_logger.info(f"cron_daemon heartbeat TICK={tick} active={active_str}")
                except:
                    pass

        except Exception as e:
            # CRITICAL: use our own _log, not scheduler's _logger (which may be broken)
            _log.error(f"loop error: {e}")
            _p(f"[cron_daemon] Loop error: {e}")

        time.sleep(INTERVAL)

    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    _log.info("cron_daemon exited cleanly")


if __name__ == "__main__":
    main()

"""Slash-command prompt builders + scheduler-task discovery.

Goal of this module: keep TUI files (tuiapp_v2.py / tui_v3.py) thin. They only
need to forward `/update`, `/autorun`, `/morphling`, `/goal`, `/hive`
to the corresponding `build_*_prompt(args)` here, and ask
`list_scheduler_tasks()` / `start_scheduler_task()` for the `/scheduler` picker.

Design (per user 2026-05-27):
- All non-/scheduler commands are *prompt injection*: we craft a system-style
  request and feed it to the main agent as a normal user message (the TUI is
  free to display the raw `/cmd ...` as the visible bubble).  This keeps the
  agent in-session, lets it use every tool/SOP it normally would, and means
  this file owns zero LLM logic.
- `/scheduler` is the only exception â it touches local FS state directly via
  `sche_tasks/*.json` and the existing scheduler daemon, no LLM needed.
- All prompts deliberately *name* the relevant SOP file so the agent re-reads
  it before acting (per CONSTITUTION rule 2: SOP-first).

This module has zero TUI imports â both frontends can depend on it without
either depending on the other.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import subprocess
import time
from pathlib import Path
from typing import Optional


_USER_SHELL: tuple[list[str], str] | None = None

COMMIT_SIGNATURE_PROMPT = 'When you create a git commit, append "Co-Authored-By: GenericAgent <bot@gaagent.ai>" as the final line of the commit message.'

def detect_user_shell() -> tuple[list[str], str]:
    """Return `([executable, ...flags_for_-c], display_name)` for the user's
    interactive shell.  Cached after first call.

    `!cmd` in tui_v2 / tui_v3 invokes this so commands like `ls`, pipes,
    globs, and shell builtins behave the way the user expects in whatever
    shell launched the app, instead of hardcoding cmd.exe / /bin/sh.

    Resolution order:
      1. `$SHELL` if it points to an existing file (Unix, Git Bash, WSL)
      2. Windows only: Git Bash at the canonical install paths
      3. `bash` anywhere on PATH (WSL bash, Cygwin, MSYS2, etc.)
      4. Windows only: `pwsh` then `powershell.exe` on PATH
      5. Unix `/bin/sh` / Windows `%COMSPEC%` (cmd.exe) â last resort
    """
    global _USER_SHELL
    if _USER_SHELL is not None:
        return _USER_SHELL

    s = os.environ.get("SHELL")
    if s and os.path.exists(s):
        name = os.path.basename(s)
        if name.lower().endswith(".exe"):
            name = name[:-4]
        _USER_SHELL = ([s, "-c"], name)
        return _USER_SHELL

    if sys.platform == "win32":
        for p in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ):
            if os.path.exists(p):
                _USER_SHELL = ([p, "-c"], "bash")
                return _USER_SHELL
        bash = shutil.which("bash")
        if bash:
            _USER_SHELL = ([bash, "-c"], "bash")
            return _USER_SHELL
        for name in ("pwsh", "powershell"):
            p = shutil.which(name)
            if p:
                # -NoProfile keeps each `!cmd` snappy + reproducible.
                _USER_SHELL = ([p, "-NoProfile", "-Command"], name)
                return _USER_SHELL
        cmd = os.environ.get("COMSPEC", "cmd.exe")
        _USER_SHELL = ([cmd, "/d", "/s", "/c"], "cmd")
        return _USER_SHELL

    _USER_SHELL = (["/bin/sh", "-c"], "sh")
    return _USER_SHELL



# Repo root = parent of frontends/.  Avoid hard-coding; both TUIs live next to
# this file and share the same anchor.
_ROOT = Path(__file__).resolve().parent.parent

# Language resolution is owned here (not passed in as a formal arg) so every
# prompt builder stays single-parameter and TUI call sites don't need to know
# which prompt happens to be bilingual.  Source of truth, in order:
#   1. `GA_LANG` env var (scriptable override; matches tui_v3 convention)
#   2. tui_v3's persisted settings file (same path as tui_v3.py:_SETTINGS_PATH)
#   3. system locale (zh* â 'zh', else 'en')
# When the user switches language inside tui_v3 (set_lang persists), the next
# call here picks it up automatically -- no formal coupling, just a shared file.
_SETTINGS_PATH = _ROOT / "temp" / "tui_v3_settings.json"


def _current_lang() -> str:
    env = (os.environ.get("GA_LANG") or "").strip().lower()
    if env in ("zh", "en"):
        return env
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            saved = (json.load(f) or {}).get("lang")
        if saved in ("zh", "en"):
            return saved
    except Exception:
        pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var, "")
        if v:
            return "zh" if v.lower().startswith("zh") else "en"
    return "en"


# ----- prompt builders (pure functions, no I/O) ---------------------------
# SOP paths are written inline as literal strings in each builder below: a
# literal is self-documenting and locally readable, and a stale path is a
# zero-radius failure (the prompt is a hint to an intelligent agent, which
# re-reads the dir / asks if a SOP moved) â so we deliberately do NOT wrap it
# in a registry + existence-check machinery.

def _tail(args_text: str, label: str = "é¢å¤æç¤º") -> str:
    """Append user-supplied args after a slash command as a free-form suffix.

    User pattern (2026-05-27): the base prompt is a fixed injection that names
    the SOP path; anything the user types after `/cmd ` is appended verbatim so
    they can add per-invocation hints (e.g. `/morphling https://github.com/...`
    or `/goal è°ç  Xï¼é¢ç® 50k token`).
    """
    extra = (args_text or "").strip()
    return f"\n\n{label}: {extra}" if extra else ""


def build_update_prompt(args_text: str = "") -> str:
    """Prompt-only /update orchestration; actual git work stays in-agent.

    The TUI owns zero git/LLM logic.  This prompt asks the normal agent loop to
    do a user-friendly preflight (upstream commits + diff) before pulling.
    Language follows `_current_lang()` so a /language switch in tui_v3 (or a
    `GA_LANG=...` shell override) automatically flips this prompt too.
    """
    if _current_lang() == "en":
        return (
            "Update this GenericAgent checkout from the official upstream "
            "https://github.com/Lsdefine/GenericAgent .\n"
            "1. Run `git fetch upstream`; identify the current branch and whether there are "
            "local commits ahead of upstream.\n"
            "2. Show a concise preview: recent upstream commits not yet local "
            "(short hash + subject + date) plus a changed-files summary.\n"
            "3. Align the COMMIT HISTORY to upstream (upstream wins):\n"
            "   - If local commits exist: `git merge upstream/main` into the current branch, "
            "resolving any conflicts in favor of upstream; keep the local commits (a merge commit is fine).\n"
            "   - Otherwise: `git reset --mixed upstream/main` so the history of local `main` "
            "matches upstream/main exactly. Do NOT create any new commit.\n"
            "4. IMPORTANT: also reconcile the WORKING TREE; step 3 alone is not enough. "
            "`git reset --mixed` and `git merge` only move history and the index. They do not "
            "rewrite files that already hold uncommitted local edits, so those stale files keep "
            "shadowing upstream's latest. That is why 'HEAD is aligned but the files are still "
            "old'. Reconcile per file:\n"
            "   a. `git diff --name-only upstream/main` lists every tracked file whose working-tree "
            "content differs from upstream.\n"
            "   b. Decide upstream-first per file. A stale leftover, or a local edit that reverts "
            "an upstream feature to an older form, takes upstream: back it up, then "
            "`git checkout upstream/main -- <file>`. A genuine local enhancement upstream lacks "
            "(local config, key-template placeholders, fork-only features) stays, re-applied on "
            "top of upstream's latest instead of overwriting it.\n"
            "   c. Upstream wins; keep local only where it adds value upstream lacks. Never "
            "`git add -A`, never blanket whole-branch checkout, never blindly preserve everything.\n"
            "5. Do not create any git commit. Back up any file before overwriting it.\n"
            "6. Finish with a short summary: branch HEAD, distance vs upstream, per-file outcome "
            "(took upstream / kept+adapted local), and where backups went.\n"
            "\n"
            "#### Say 'Congratulations! ð' to the user\n"
            "After a successful update, say: \"Congratulations! ð You have successfully "
            "updated GenericAgent!\"\n"
            "\n"
            "#### Ask for a Star â­\n"
            "Then you may ask: \"If you found this helpful, would you like to star the "
            "GenericAgent repository? It helps the project grow! â­\""
            f"{_tail(args_text, 'Extra instructions')}"
        )
    return (
        "è¯·ä½ æ´æ°å½å GenericAgent ä»åºï¼å®æ¹ä¸æ¸¸ä¸º "
        "https://github.com/Lsdefine/GenericAgent ã\n"
        "1. å `git fetch upstream`ï¼è¯å«å½ååæ¯ï¼ä»¥åæ¯å¦å­å¨é¢å upstream çæ¬å° commitã\n"
        "2. ç»åºç®æ´é¢è§ï¼æ¬å°å°æªåå«ç upstream æè¿æäº¤ï¼ç­ hash + æ é¢ + æ¥æï¼ååæ´æä»¶æè¦ã\n"
        "3. åå¯¹é½ãæäº¤åå²ãå°ä¸æ¸¸ï¼ä¼åä¸æ¸¸ï¼ï¼\n"
        "   - è¥å­å¨æ¬å° commitï¼`git merge upstream/main` åå¹¶è¿å½ååæ¯ï¼å²çªä¸å¾ä¼åä¸æ¸¸ï¼ä¿çæ¬å° commitï¼å¯äº§ç merge commitï¼ã\n"
        "   - å¦åï¼æ§è¡ `git reset --mixed upstream/main`ï¼ä½¿æ¬å° `main` çæäº¤åå²ä¸ upstream/main å®å¨å¯¹é½ãä¸è¦åå»ºä»»ä½æ° commitã\n"
        "4. éè¦ï¼è¿é¡»æ ¸å¯¹ãå·¥ä½åºæä»¶ãï¼æ­¢æ­¥äºç¬¬ 3 æ­¥å¹¶ä¸å¤ã`git reset --mixed` ä¸ `git merge` "
        "åªç§»å¨æäº¤åå²ä¸ç´¢å¼ï¼ä¸ä¼éåé£äºå·²å¸¦æªæäº¤æ¬å°æ¹å¨çæä»¶ï¼äºæ¯è¿äºè¿æ¶æä»¶ç»§ç»­è¦çå¨ä¸æ¸¸"
        "ææ°çä¹ä¸ãè¿æ­£æ¯âHEAD å·²å¯¹é½ï¼ä½æä»¶å¶å®è¿æ¯æ§çâçæ ¹å ãéæä»¶æ ¸å¯¹ï¼\n"
        "   a. `git diff --name-only upstream/main` ååºå·¥ä½åºåå®¹ä¸ä¸æ¸¸ä¸ä¸è´çå¨é¨ tracked æä»¶ã\n"
        "   b. æ¯ä¸ªæä»¶æä¼åä¸æ¸¸å¤æ­ãè¿æ¶æ®çãææä¸æ¸¸ç¹æ§æ¹åæ§ççæ¬å°æ¹å¨ï¼åä¸æ¸¸ï¼åå¤ä»½ï¼å "
        "`git checkout upstream/main -- <file>`ãä¸æ¸¸æ²¡æä¸ä»ææçæ¬å°å¢å¼ºï¼æ¬æºéç½®ãå¯é¥æ¨¡æ¿å ä½ã"
        "fork ä¸å±åè½ï¼ä¿çï¼å¹¶å¨ä¸æ¸¸ææ°çä¸éæ°ééï¼èéæ´æä»¶è¦çä¸æ¸¸ã\n"
        "   c. ä¼åä¸æ¸¸ï¼æ¬å°ä»ä¿çä¸æ¸¸ç¼ºå¤±ä¸æä»·å¼çé¨åãç¦æ­¢ `git add -A`ãç¦æ­¢æ´åæ¯ checkout è¦çãç¦æ­¢ç²ç®å¨ä¿çã\n"
        "5. ä¸è¦è¿è¡ä»»ä½ git commitãè¦çä»»ä½æä»¶ååå¤ä»½ã\n"
        "6. æåç»åºç®ç­å°ç»ï¼åæ¯ HEADãä¸ä¸æ¸¸å·®è·ãéæä»¶å¤çç»æï¼åä¸æ¸¸ / ä¿çå¹¶ééæ¬å°ï¼ãå¤ä»½ä½ç½®ã\n"
        "\n"
        "#### åç¨æ·è¯´ 'Congratulations! ð'\n"
        "æ´æ°æååï¼è¯·å¯¹ç¨æ·è¯´ï¼\"Congratulations! ð ä½ å·²æåæ´æ° GenericAgentï¼\"\n"
        "\n"
        "#### éè¯·ç¨æ·ç¹ Star â­\n"
        "éåå¯éè¯·ï¼\"å¦æè§å¾æå¸®å©ï¼è¦ä¸è¦ç» GenericAgent ä»åºç¹ä¸ª Starï¼è¿ä¼è®©é¡¹ç®æé¿æ´å¿«ï¼â­\""
        f"{_tail(args_text)}"
    )


def build_autorun_prompt(args_text: str = "") -> str:
    return (
        "è¯·è¿å¥ãèªä¸»æ¢ç´¢ / autonomous æ¨¡å¼ãï¼åè¯» "
        "memory/autonomous_operation_sop.mdã"
        "å¨ç¨èªé©±ï¼ä¸å¯é / é«é£é©å¨ä½å ask_user ï¼"
        "ç»æ¡ç»ä¸ä»½ç®æåæ§ï¼åäºä»ä¹ / äº§ç©å¨åª / ä¸ä¸æ­¥ï¼ã"
        f"{_tail(args_text, 'ä»»å¡ç§å­')}"
    )


def build_morphling_prompt(args_text: str = "") -> str:
    return (
        "è¯·å¯ç¨ Morphling æ¨¡å¼åå¬ / è¸é¦å¤é¨é¡¹ç®å°æ¬ä»åºï¼åè¯» "
        "memory/morphling_sop.mdã"
        "æ²¡æç®æ å ask_user å GitHub ä»åº / æ¬å°è·¯å¾ / è½åæè¿°ã"
        f"{_tail(args_text, 'ç®æ æè½/ä»åº')}"
    )


def build_goal_prompt(args_text: str = "") -> str:
    return (
        "è¯·è¿å¥ Goal æ¨¡å¼ï¼åè¯» memory/goal_mode_sop.mdã"
        "è¥æªç»ç®æ ï¼å ask_user ä¸æ¬¡æ§é®æ¸ï¼ä¸å¥è¯ç®æ  + condition çº¦æã"
        f"{_tail(args_text, 'ç¨æ·ç®æ ')}"
    )


def build_hive_prompt(args_text: str = "") -> str:
    return (
        "è¯·è¿å¥ Goal Hive æ¨¡å¼ï¼å¤ worker åä½ç goalï¼ï¼åè¯» "
        "memory/goal_hive_sop.mdã"
        "éç¾¤ç®æ  / worker éé¢ / ç»æ­¢æ¡ä»¶æªæç¡®æ¶å ask_user è¡¥é½åå¯å¨ã"
        f"{_tail(args_text, 'éç¾¤ç®æ ')}"
    )


def build_conductor_prompt(args_text: str = "") -> str:
    """`/conductor <task>` â run `frontends/conductor.py` on the task.

    Upstream `memory/` ships no conductor SOP, so we deliberately keep the
    prompt short: name the entrypoint and forward the task verbatim.  The
    agent is expected to know how to drive `conductor.py` (or consult a
    local SOP if one happens to be installed).
    """
    args_text = (args_text or "").strip()
    if args_text:
        return f"è¯·è°ç¨ frontends/conductor.py æ§è¡ï¼{args_text}"
    return (
        "è¯·è°ç¨ frontends/conductor.pyï¼æ ¹æ®åç»­æä»¤å®æå¤ subagent ç¼æã"
        "è¥ä»»å¡æè¿°ç¼ºå¤±ï¼å ask_user ä¸æ¬¡æ§è¡¥é½ã"
    )


# ----- /scheduler reflect-task discovery + launch -------------------------

def list_reflect_tasks() -> list[dict]:
    """Return [{name, path, doc}] for every reflect/*.py task script.

    `doc` is the module docstring's first line (best-effort) so the picker can
    show a one-liner next to each name.  Empty list if reflect/ doesn't exist.
    """
    out: list[dict] = []
    refl = _ROOT / "reflect"
    if not refl.is_dir():
        return out
    for p in sorted(refl.glob("*.py")):
        if p.name.startswith("_"):
            continue
        doc = ""
        try:
            # Cheap docstring sniff: read first ~40 lines, look for """...""".
            head = p.read_text(encoding="utf-8", errors="ignore").splitlines()[:40]
            joined = "\n".join(head)
            for q in ('"""', "'''"):
                i = joined.find(q)
                if i != -1:
                    j = joined.find(q, i + 3)
                    if j != -1:
                        doc = joined[i + 3:j].strip().splitlines()[0].strip()
                        break
        except Exception:
            pass
        out.append({"name": p.stem, "path": str(p), "doc": doc})
    return out


# ----- hub.pyw parity: every launchable service ---------------------------

_HUB_EXCLUDES = {"goal_mode.py", "chatapp_common.py", "tuiapp.py"}


def _sniff_doc(p) -> str:
    """Best-effort first line of a module docstring (cheap ~40-line read)."""
    try:
        head = p.read_text(encoding="utf-8", errors="ignore").splitlines()[:40]
        joined = "\n".join(head)
        for q in ('"""', "'''"):
            i = joined.find(q)
            if i != -1:
                j = joined.find(q, i + 3)
                if j != -1:
                    body = joined[i + 3:j].strip()
                    if body:
                        return body.splitlines()[0].strip()
    except Exception:
        pass
    return ""


def list_launchable_services() -> list[dict]:
    """Mirror hub.pyw's discover_services() so `/scheduler` shows the *same*
    set of launchable services as the GUI launcher.

    Sources (hub.pyw EXCLUDES = goal_mode.py / chatapp_common.py / tuiapp.py):
      â¢ reflect/*.py   (not '_'-prefixed, not excluded)
          â cmd = [python, agentmain.py, --reflect, reflect/<f>]
      â¢ frontends/*app*.py (not excluded)
          â 'stapp' â `python -m streamlit run â¦ --server.headless=true`
            others   â `python frontends/<f>`

    Returns [{name, cmd, doc, kind}] where `name` is the hub-style path
    ('reflect/foo.py' / 'frontends/bar.py') and doubles as the picker value.
    """
    out: list[dict] = []
    refl = _ROOT / "reflect"
    if refl.is_dir():
        for p in sorted(refl.glob("*.py")):
            if p.name.startswith("_") or p.name in _HUB_EXCLUDES:
                continue
            rel = "reflect/" + p.name
            out.append({
                "name": rel,
                "cmd": [sys.executable, "agentmain.py", "--reflect", rel],
                "doc": _sniff_doc(p),
                "kind": "reflect",
            })
    fe = _ROOT / "frontends"
    if fe.is_dir():
        for p in sorted(fe.glob("*.py")):
            if "app" not in p.name or p.name in _HUB_EXCLUDES:
                continue
            rel = "frontends/" + p.name
            if "stapp" in p.name:
                cmd = [sys.executable, "-m", "streamlit", "run", rel,
                       "--server.headless=true"]
            else:
                cmd = [sys.executable, rel]
            out.append({"name": rel, "cmd": cmd, "doc": _sniff_doc(p),
                        "kind": "frontend"})
    return out


def start_service(name: str) -> tuple[bool, str]:
    """Launch a service from list_launchable_services(), detached & window-less
    (CONSTITUTION rule 14: creationflags at the launch layer only, never via
    subprocess.Popen monkeypatch).

    `name` accepts the hub-style path ('reflect/foo.py') or a bare reflect stem
    ('foo') for backward-compat with `/scheduler start <stem>`.
    """
    svcs = list_launchable_services()
    svc = next((s for s in svcs if s["name"] == name), None)
    if svc is None:  # bare reflect stem fallback
        cand = "reflect/" + name + ".py"
        svc = next((s for s in svcs if s["name"] == cand), None)
    if svc is None:
        return False, f"æªç¥æå¡: {name}"
    try:
        flags = 0
        if os.name == "nt":
            flags = 0x00000200 | 0x08000000  # NEW_PROCESS_GROUP | NO_WINDOW
        proc = subprocess.Popen(
            svc["cmd"],
            cwd=str(_ROOT),
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        # Poll-and-confirm: if the child dies immediately (bad path, import
        # error, port-in-use, etc) Popen still returns happily â without this
        # check the picker would tick "â started" while nothing is running,
        # which is exactly the bug#4 the user hit.  0.4s is the smallest
        # window that catches "explodes at import" without making the UI
        # feel laggy on healthy starts.
        time.sleep(0.4)
        rc = proc.poll()
        if rc is not None:
            return False, f"å¯å¨å¤±è´¥ (éåºç  {rc}): {svc['name']}"
        invalidate_running_cache()
        return True, f"å·²å¯å¨ {svc['name']} (pid={proc.pid})"
    except Exception as e:
        return False, f"å¯å¨å¤±è´¥: {type(e).__name__}: {e}"


# ----- running-state introspection (bug#4) --------------------------------
# Why psutil cmdline-scan instead of a launched-by-us pid registry?
#   â¢ Services launched by a previous TUI run, or by hub.pyw, must also be
#     recognised â otherwise /scheduler would happily start a duplicate.
#   â¢ A registry tied to this process dies when the TUI restarts, but the
#     services keep running (CREATE_NEW_PROCESS_GROUP).  Cmdline scan is the
#     only single source of truth across launchers, surviving restarts.
# Trade-off: it costs ~30ms per /scheduler open, and matches by cmdline tail,
# so two checkouts of GA can collide.  We accept that â running two GAs out
# of two clones is already an unsupported configuration.

def _match_service(cmdline: list[str], svc: dict) -> bool:
    """Does this OS process belong to `svc`?  Match on the trailing script
    arg (`reflect/foo.py` for reflect tasks, `frontends/bar.py` for apps),
    which is invariant across `python` vs `pythonw` vs venv shims.

    Reflect detection used to require BOTH `agentmain.py` AND the reflect
    path in cmdline.  That rejected tasks launched directly (`python
    reflect/scheduler.py`) by launch.pyw, dev scripts, or by an earlier
    TUI run that used a different launcher â they showed unticked in
    /scheduler even when alive.  Path-only match handles both styles; the
    Python-process pre-filter in `running_services` keeps false positives
    (greps, editors with the file open) from sneaking in."""
    if not cmdline:
        return False
    rel = svc["name"]  # 'reflect/foo.py' | 'frontends/bar.py'
    rel_norm = rel.replace("/", os.sep)
    return any(rel_norm in (a or "") or rel in (a or "")
               for a in cmdline)


# 2s TTL cache + name-prefilter: ~2.1s â ~1.0s cold, ~0ms warm.
# cmdline() is the per-proc cost; only pay it for python-ish survivors.
_RUNNING_CACHE: tuple[float, dict[str, int]] | None = None
_RUNNING_TTL = 2.0


def invalidate_running_cache() -> None:
    """Drop the snapshot. Call after start/stop so the next read is fresh."""
    global _RUNNING_CACHE
    _RUNNING_CACHE = None


def running_services(use_cache: bool = True) -> dict[str, int]:
    """{service_name: pid} for live services. {} if psutil missing."""
    global _RUNNING_CACHE
    if use_cache and _RUNNING_CACHE and time.time() - _RUNNING_CACHE[0] < _RUNNING_TTL:
        return dict(_RUNNING_CACHE[1])
    try:
        import psutil  # type: ignore
    except Exception:
        return {}
    svcs = list_launchable_services()
    out: dict[str, int] = {}
    me = os.getpid()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["pid"] == me:
                continue
            nm = (proc.info.get("name") or "").lower()
            if "python" not in nm and "py.exe" not in nm:
                continue
            cmd = proc.cmdline()
        except Exception:
            continue
        for svc in svcs:
            if svc["name"] not in out and _match_service(cmd, svc):
                out[svc["name"]] = proc.info["pid"]
                break
    _RUNNING_CACHE = (time.time(), dict(out))
    return out


def stop_service(name: str) -> tuple[bool, str]:
    """Terminate the service `name` if running.  Returns (ok, message).

    Sends SIGTERM-equivalent (Popen.terminate on Windows = TerminateProcess),
    waits up to 3s, then escalates to kill.  Also reaps obvious children
    (e.g. `python -m streamlit` spawns the actual streamlit worker) so we
    don't leave orphans behind.
    """
    try:
        import psutil  # type: ignore
    except Exception:
        return False, "æªå®è£ psutilï¼æ æ³åæ­¢æå¡"
    running = running_services()
    pid = running.get(name)
    if pid is None:
        return False, f"{name} æªå¨è¿è¡"
    try:
        parent = psutil.Process(pid)
        kids = parent.children(recursive=True)
        for p in [parent, *kids]:
            try:
                p.terminate()
            except Exception:
                pass
        gone, alive = psutil.wait_procs([parent, *kids], timeout=3.0)
        for p in alive:
            try:
                p.kill()
            except Exception:
                pass
        invalidate_running_cache()
        return True, f"å·²åæ­¢ {name} (pid={pid})"
    except psutil.NoSuchProcess:
        invalidate_running_cache()
        return True, f"{name} å·²éåº"
    except Exception as e:
        return False, f"åæ­¢å¤±è´¥: {type(e).__name__}: {e}"


def list_scheduler_tasks() -> list[dict]:
    """Return [{name, path, schedule, enabled}] for every sche_tasks/*.json.

    Used by the /scheduler picker so users can also toggle traditional cron
    tasks, not just reflect.* scripts.
    """
    out: list[dict] = []
    sd = _ROOT / "sche_tasks"
    if not sd.is_dir():
        return out
    for p in sorted(sd.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        out.append({
            "name": p.stem,
            "path": str(p),
            "schedule": data.get("schedule") or data.get("cron") or data.get("every") or "",
            "enabled": bool(data.get("enabled", True)),
        })
    return out


def start_reflect_task(name: str) -> tuple[bool, str]:
    """Spawn `python reflect/<name>.py` detached.  Returns (ok, message).

    Detached because reflect tasks are long-running; we don't want them to die
    with the TUI.  On Windows we use CREATE_NEW_PROCESS_GROUP|CREATE_NO_WINDOW
    so no console pops up (per CONSTITUTION rule 14: only at launch layer, no
    monkeypatching subprocess.Popen).
    """
    script = _ROOT / "reflect" / f"{name}.py"
    if not script.is_file():
        return False, f"reflect/{name}.py ä¸å­å¨"
    try:
        flags = 0
        if os.name == "nt":
            flags = 0x00000200 | 0x08000000  # NEW_PROCESS_GROUP | NO_WINDOW
        subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(_ROOT),
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return True, f"å·²å¯å¨ reflect/{name}.py"
    except Exception as e:
        return False, f"å¯å¨å¤±è´¥: {type(e).__name__}: {e}"


# ----- dispatch table for the TUI to register against ---------------------

# (cmd, arg_hint, desc)  â kept identical between v2 and v3 so the palette
# stays consistent across frontends.
PALETTE_ENTRIES: list[tuple[str, str, str]] = [
    ("/update",    "[note]",    "git pull æ´æ° GA ä»åºå¹¶æ¥åå½±åé¢"),
    ("/autorun",   "[seed]",    "è¿å¥ autonomous_operation èªä¸»æ¨¡å¼"),
    ("/morphling", "[target]",  "å¯ç¨ Morphling è¸é¦ / åå¬å¤é¨æè½"),
    ("/goal",      "[goal]",    "è¿å¥ Goal æ¨¡å¼ï¼é condition çº¦æï¼"),
    ("/hive",      "[target]",  "è¿å¥ Hive å¤ worker åä½æ¨¡å¼"),
    ("/conductor", "[task]",    "è°ç¨ frontends/conductor.py å¤ subagent ç¼æ"),
    ("/scheduler", "",          "å¤éå¯å¨/åæ­¢ reflect ä»»å¡ï¼cron ç± reflect/scheduler.py é©±å¨ï¼"),
    ("/resume",    "",           "ååºæè¿ä¼è¯å¹¶æ¢å¤å¶ä¸­ä¸ä¸ªï¼GA ç«¯å±å¼ promptï¼"),
]


def prompt_for(cmd: str, args_text: str) -> Optional[str]:
    """Return the injected user-message for a given slash command, or None if
    the command isn't one of ours (e.g. /scheduler â handled by TUI directly).

    Language is resolved inside the builders that care about it (see
    `_current_lang()`); callers never thread it through, so both TUIs keep a
    single uniform call site.
    """
    table = {
        "/update":    build_update_prompt,
        "/autorun":   build_autorun_prompt,
        "/morphling": build_morphling_prompt,
        "/goal":      build_goal_prompt,
        "/hive":      build_hive_prompt,
        "/conductor": build_conductor_prompt,
    }
    fn = table.get(cmd)
    return fn(args_text) if fn else None

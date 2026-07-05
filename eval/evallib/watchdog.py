"""watchdog.py — the harness bounds an agent's spend, trusting nothing.

`claude -p --max-budget-usd` is the agent's self-limit, but a self-limit you
cannot observe mid-session is not a bound. So every agent invocation runs under a
harness-side HARD-KILL watchdog: a wall-clock backstop that, when the session
overruns, SIGKILLs the whole process GROUP — the agent AND any children it
spawned — so a runaway session is stopped dead, its pending work never
completing, rather than left to bill unbounded. The session runs in its own
process group (`start_new_session=True`) precisely so the whole group can be
killed at once.
"""

from __future__ import annotations

import os
import signal
import subprocess


def run_agent_capped(argv: list[str], input_text: str, *, wall_timeout: float,
                     cwd=None) -> dict:
    """Run `argv` (an agent invocation, `--max-budget-usd` already in it) under a
    hard wall-clock kill. Returns {returncode, stdout, stderr, killed}. On
    overrun the whole process group is SIGKILLed and `killed` is True; a
    well-behaved session returns with its output and `killed` False."""
    proc = subprocess.Popen(
        argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=cwd, start_new_session=True)
    try:
        out, err = proc.communicate(input=input_text, timeout=wall_timeout)
        return {"returncode": proc.returncode, "stdout": out, "stderr": err,
                "killed": False}
    except subprocess.TimeoutExpired:
        # Hard-kill the ENTIRE group — do not trust the agent (or its children) to
        # stop. Kill the group, then drain the pipes so nothing is left hanging.
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            out, err = proc.communicate(timeout=5)
        except Exception:
            out, err = "", ""
        return {"returncode": proc.returncode if proc.returncode is not None else -9,
                "stdout": out or "", "stderr": err or "", "killed": True}

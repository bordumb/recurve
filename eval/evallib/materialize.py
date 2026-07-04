"""materialize.py — task → fresh workspace, with the oracle quarantined.

The materializer writes ONLY what the agent is allowed to see: the task
statement and an empty solution.py, in a git-init'd tmpdir (the A3 arm adds
`recurve init`). It never references the task's hidden `test` field, and
`assert_quarantined` is a defense-in-depth guard that refuses any workspace in
which the hidden test text appears — the one leak that would invalidate every
downstream number.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from evallib.arms import arm_spec


class QuarantineError(RuntimeError):
    """The hidden oracle leaked into an agent-visible workspace."""


def assert_quarantined(dest: str | Path, task: dict) -> None:
    """Raise QuarantineError if the task's hidden `test` text appears in any file
    under `dest`. A no-op on a clean workspace; the last line of defense against
    an agent ever seeing the oracle it is graded by."""
    hidden = (task.get("test") or "").strip()
    if not hidden:
        return
    for p in Path(dest).rglob("*"):
        if p.is_file():
            try:
                if hidden in p.read_text(errors="ignore"):
                    raise QuarantineError(
                        f"hidden test leaked into {p} — the oracle must never "
                        f"enter an agent workspace")
            except (UnicodeDecodeError, OSError):
                continue


def materialize(task: dict, arm: str, dest: str | Path,
                recurve_cmd: str | None = None) -> Path:
    """Build a fresh workspace for one (task, arm) cell and return its path.

    Writes TASK.md (the statement the agent sees) and an empty solution.py,
    git-init's the dir, and — for a recurve arm — runs `recurve init`. The
    hidden `test` field is never written; `assert_quarantined` re-checks that
    before returning."""
    spec = arm_spec(arm)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "TASK.md").write_text(
        f"# Task {task.get('task_id', '')}\n\n{task.get('instruct_prompt', '')}\n")
    (dest / "solution.py").write_text("")
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    if spec["recurve"]:
        cmd = recurve_cmd or "recurve"
        subprocess.run([cmd if cmd == "recurve" else "python3", *([] if cmd == "recurve" else [cmd]),
                        "init"], cwd=dest,
                       capture_output=True, text=True)
    assert_quarantined(dest, task)
    return dest

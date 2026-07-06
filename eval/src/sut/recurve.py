"""sut/recurve.py — the ONE place that names the `recurve` binary.

The pre-refactor pipeline spreads this across six sites (each hand-writing
`subprocess.run(["recurve", "matrix", "--gate"], ...)`, four of them
duplicating the identical `{0: "green", 1: "red"}` exit-code mapping) plus
scatters recurve-specific knowledge further still: what a "well-formed
claim" looks like on disk, how to patch a workspace's own governor config.
Every one of those calls lives here instead. `orchestrate.py` and every
other kernel module import this, never the `recurve` string directly.

What this measures is genuinely coupled to recurve by design — `eval/`
exists to measure recurve, so knowing its CLI/file format is not a
violation. The point is ONE place holding that knowledge, not the kernel
re-deriving it in six slightly-different ways. A second system under test
would only need a sibling module with the same five functions plus a name
in a registry — not built here (there is exactly one SUT today; a
one-implementation port is pure indirection until that changes).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

GATE_MAP = {0: "green", 1: "red"}
_GOVERNOR_LINE_RE = re.compile(r"^\s*governor\s*=.*$", re.MULTILINE)


def gate_verdict(workspace) -> str:
    """green / red / broken -- the one mapping every gate check needs,
    defined exactly once."""
    r = subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace,
                       capture_output=True, text=True)
    return GATE_MAP.get(r.returncode, "broken")


def gate_green(workspace) -> bool:
    return gate_verdict(workspace) == "green"


def init(workspace, *, recurve_cmd: str | None = None) -> None:
    """`recurve init` -- byte-for-byte the same invocation shape the
    pre-refactor pipeline uses in two places (`materialize.py`,
    `swebench_workspace.py`), collapsed to one."""
    cmd = recurve_cmd or "recurve"
    argv = [cmd] if cmd == "recurve" else ["python3", cmd]
    subprocess.run([*argv, "init"], cwd=workspace, capture_output=True, text=True)


def configure_governor(workspace, governor: str) -> None:
    """Patch `workspace`'s own `.recurve/recurve.toml` `[gate]` table so
    `governor=` names the requested tier -- a fresh `recurve init` emits a
    `[gate]` section with no `governor=` line at all, which resolves to the
    engine default ("mechanical"), not "off"."""
    toml_path = Path(workspace) / ".recurve" / "recurve.toml"
    text = toml_path.read_text()
    line = f'governor = "{governor}"'
    if _GOVERNOR_LINE_RE.search(text):
        text = _GOVERNOR_LINE_RE.sub(line, text, count=1)
    else:
        text = text.replace("[gate]", f"[gate]\n{line}", 1)
    toml_path.write_text(text)


def decide(workspace, *, actor_model: str, governor_cmd: str,
          open_: int = 0, regressed: int = 0, broken: int = 0,
          uncovered: int = 0, timeout: int = 300) -> str:  # pragma: no cover - spawns a real reviewer process
    """Run the real `recurve decide` CLI, with the governor genuinely
    wired: `RECURVE_ACTOR_MODEL` establishes the cycle's own claim-authoring
    identity, `RECURVE_GOVERNOR_CMD` names the reviewer command the engine
    will actually invoke. Returns the printed verdict string:
    `STOP-SUCCESS` / `PENDING-GOVERNOR` / `CONTINUE` / `STOP-REVERT`."""
    import os
    env = {**os.environ, "RECURVE_ACTOR_MODEL": actor_model, "RECURVE_GOVERNOR_CMD": governor_cmd}
    r = subprocess.run(
        ["recurve", "decide", "--open", str(open_), "--regressed", str(regressed),
         "--broken", str(broken), "--uncovered", str(uncovered)],
        cwd=workspace, capture_output=True, text=True, env=env, timeout=timeout)
    return (r.stdout or "").strip()


def commit_snapshot_for_governor(workspace) -> None:
    """The governor's own snapshot mechanism reads claim files FROM a git
    commit, not the working tree -- and nothing upstream of this call can
    be relied on to have committed anything. This commits the CURRENT state
    unconditionally, right before the governor is consulted, regardless of
    what produced it -- a structural guarantee, not a hope about caller
    behavior. --no-gpg-sign: a throwaway, internal bookkeeping commit,
    never a real user-authored one."""
    subprocess.run(["git", "add", "-A"], cwd=workspace, check=True)
    subprocess.run(["git", "-c", "user.email=recurve@localhost", "-c", "user.name=recurve",
                    "commit", "--no-gpg-sign", "-q", "-m", "governor snapshot"],
                   cwd=workspace)  # no check=True: "nothing to commit" (rc=1) is a fine no-op


def make_governed_gate_fn(governor: str, actor_model: str, governor_cmd: str):
    """A `gate_fn(workspace)` for `DoneSignalPort["gate"]`: the mechanical
    gate decides as always; ONLY when that is green does this ALSO run a
    real `decide()` with the governor configured -- a governor that is
    PENDING or vetoes is "not yet done" (red), never silently overridden by
    a green conformance matrix alone. `governor="off"` skips the second
    call entirely, byte-identical to a bare `gate_verdict`."""
    def gate_fn(workspace):  # pragma: no cover - the "off" branch is hermetic; governor!="off" spawns real processes
        base = gate_verdict(workspace)
        if base != "green" or governor == "off":
            return base
        configure_governor(workspace, governor)
        commit_snapshot_for_governor(workspace)
        verdict = decide(workspace, actor_model=actor_model, governor_cmd=governor_cmd)
        if verdict == "STOP-SUCCESS":
            return "green"
        if verdict in ("PENDING-GOVERNOR", "CONTINUE"):
            return "red"   # governor didn't clear it -- not genuinely done yet
        return "broken"    # STOP-REVERT or an unexpected verdict
    return gate_fn


def has_wellformed_claim(workspace) -> bool:
    """True iff the workspace contains at least one probe with a kept trap
    fixture -- evidence the agent actually expressed the task as a
    falsifiable claim, rather than failing to operate the harness at all.
    The SUT's own on-disk file format (`probes/*.sh` + a sibling `.trap`
    directory) -- this is the one place that knowledge lives."""
    for probe in Path(workspace).rglob("*.sh"):
        if probe.parent.name != "probes":
            continue
        trap = probe.parent / (probe.stem + ".trap")
        if trap.is_dir() and any(p.is_dir() for p in trap.iterdir()):
            return True
    return False

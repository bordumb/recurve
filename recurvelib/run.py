"""`recurve run` — the friendly wrapper over the stamped burndown workflow.

It resolves three things so an unattended loop just flows, then execs the
stamped script:

  * the AGENT — ``--agent`` > ``$AGENT_CMD`` > a headless Claude in
    bypass-permissions mode. A cycle running unattended cannot answer a
    permission prompt, and the loop is a cage (the write boundary keeps the
    agent off the referee surface, per-cycle commits make every cycle a
    one-command rollback, the tree lock keeps a single writer, and nothing
    closes without the gate) — so the safety is structural, not the prompt.
  * the CAP — ``--cap`` > the config's ``[burndown] cap``.
  * the SCRIPT — ``burndown.sh``, or ``burndown-parallel.sh`` for ``--lanes N``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .config import Config

# A headless agent with permissions bypassed: the `-p` (print) equivalent of
# `--dangerously-skip-permissions`. See the module docstring for why this is the
# default and why it is safe inside the loop.
DEFAULT_AGENT = "claude -p --permission-mode bypassPermissions"


def resolve_agent(agent_flag: str | None, env_agent: str | None,
                  default: str = DEFAULT_AGENT) -> tuple[str, str]:
    """Return ``(agent, source)``. An explicit ``--agent`` wins, then
    ``$AGENT_CMD`` from the environment, then the bypass-permissions default —
    an unset ``AGENT_CMD`` must never leave the loop with an agent that stalls
    on a permission prompt."""
    if agent_flag:
        return agent_flag, "flag"
    if env_agent:
        return env_agent, "env"
    return default, "default"


def bypasses_permissions(agent: str) -> bool:
    """True when the resolved agent skips permission prompts — so the caller can
    surface that it is running in a bypass posture."""
    return ("--permission-mode bypassPermissions" in agent
            or "--dangerously-skip-permissions" in agent)


def resolve_workflow(cfg: Config, parallel: bool = False) -> Path | None:
    """The burndown script to run: the target's stamped workflow if present,
    else the engine's shipped template — so ``recurve run`` works on the
    self-host repo too, not only on stamped targets. ``None`` if neither exists."""
    name = "burndown-parallel.sh" if parallel else "burndown.sh"
    stamped = cfg.assets_dir / "workflows" / name
    if stamped.exists():
        return stamped
    from . import resource_dir
    shipped = resource_dir("templates") / "workflows" / name
    return shipped if shipped.exists() else None


def build_run(cfg: Config, agent: str, cap: int, lanes: int | None,
              parked: str | None, caffeinate: bool) -> tuple[list[str] | None, dict[str, str]]:
    """Return ``(argv, env_overrides)`` for the burndown workflow; ``argv`` is
    ``None`` when no workflow can be found. ``--lanes N`` selects the parallel
    script; on macOS the run is wrapped in ``caffeinate`` (a sleeping host reads
    as a hung agent). ``argv``'s last element is the *resolved* workflow — the
    caller runs it through ``materialize_workflow`` so an un-stamped template is
    interpolated before it is executed."""
    parallel = bool(lanes and lanes > 1)
    script = resolve_workflow(cfg, parallel)
    env: dict[str, str] = {"AGENT_CMD": agent, "CAP": str(cap)}
    if parallel:
        env["PARALLEL"] = str(lanes)
    if parked:
        env["PARKED_SEED"] = parked
    if script is None:
        return None, env
    argv = ["bash", str(script)]
    if caffeinate and sys.platform == "darwin" and shutil.which("caffeinate"):
        argv = ["caffeinate", "-dimsu", *argv]
    return argv, env


def materialize_workflow(cfg: Config, script: Path) -> Path:
    """Return a runnable workflow path. A stamped workflow is already
    interpolated in place and returned as-is; the shipped *template* is
    interpolated with the config's facts into a temp file — the raw ``{{...}}``
    template does not run under bash (``${VAR:-{{PROG}}}`` mis-parses) — so
    ``recurve run`` works on the self-host repo too. ``PROG`` re-invokes recurve
    through the *current* interpreter, so it inherits this process's imports."""
    if script == cfg.assets_dir / "workflows" / script.name:
        return script
    import os
    import tempfile

    from .init import _interp, detect_commit_policy
    entry = Path(__file__).resolve().parent.parent / "recurve"
    policy, _ = detect_commit_policy(cfg.tree or cfg.root)
    subs = {
        "PROG": f"{sys.executable} {entry}",
        "CAP": str(cfg.burndown_cap),
        "MAX_FAILS": str(cfg.burndown_max_consecutive_failures),
        "RUNAWAY": str(cfg.burndown_runaway_net_positive_cycles),
        "COMMIT_POLICY": policy,
    }
    fd, path = tempfile.mkstemp(prefix="recurve-burndown-", suffix=".sh")
    with os.fdopen(fd, "w") as f:
        f.write(_interp(script.read_text(), subs))
    return Path(path)

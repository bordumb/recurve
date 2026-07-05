"""swebench_workspace.py — WorkspacePort["swe_bench_repo"]: real, working,
structurally oracle-free.

The load-bearing principle is identical to BigCodeBench's (`materialize.py`'s
docstring: "the workspace never contains the oracle"), harder to hold here
because the agent's workspace has to be a fully live, working checkout, not
an empty tmpdir. The container the agent works in is built from SW1's
environment image WITHOUT `test_patch` applied (true by construction: the
environment image is `repo_script_list` only — SWE-bench's own
`make_test_spec` never folds `test_patch` into it; that only happens in
`eval_script_list`, at GRADE time). This module's own job is to prove that
absence, not merely assume it: `assert_quarantined_swe` scans whatever the
agent can actually see for any signal line pulled out of `test_patch`, and
refuses before an agent ever runs, exactly the shape of
`materialize.assert_quarantined` applied to a diff instead of a single
hidden-test string.

Registered into `materialize.WORKSPACE_PORTS` as `"swe_bench_repo"` — one new
file, one registry line, per `eval-arm-kernel.md`'s own rule: adding a
WorkspacePort value never touches the kernel pipeline.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from evallib.materialize import QuarantineError

_DIFF_HEADER_RE = re.compile(r"^(diff --git|index |--- |\+\+\+ |@@ )")


def test_patch_signals(test_patch: str) -> list[str]:
    """Pull the meaningful ADDED lines out of a unified diff — the content
    that must never be visible to the agent. Skips diff plumbing (headers,
    hunk markers) and blank/whitespace-only additions, which would either
    never appear verbatim anyway or would produce false positives against
    ordinary boilerplate (e.g. a bare blank `+` line)."""
    signals = []
    for line in test_patch.splitlines():
        if not line.startswith("+") or _DIFF_HEADER_RE.match(line):
            continue
        content = line[1:].strip()
        if len(content) >= 4:   # a bare `+` or "+)" is not a meaningful signal
            signals.append(content)
    return signals


def assert_quarantined_swe(file_texts: dict[str, str], test_patch: str) -> None:
    """Raise `QuarantineError` if any signal line pulled from `test_patch`
    appears in any file the agent can see. `file_texts` maps a path (however
    it was obtained — a host tmpdir walk, or a `docker exec cat` extraction
    from a live container) to its text content; this function never cares
    which. A no-op when `test_patch` carries no usable signal (defensive; in
    practice every real SWE-bench instance has a non-trivial test_patch)."""
    signals = test_patch_signals(test_patch)
    if not signals:
        return
    for path, text in file_texts.items():
        for signal in signals:
            if signal in text:
                raise QuarantineError(
                    f"hidden test_patch content leaked into {path} (line "
                    f"{signal!r}) — the oracle must never enter an agent "
                    f"workspace")


def _write_task(dest: Path, task: dict) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "TASK.md").write_text(
        f"# {task.get('instance_id', '')} ({task.get('repo', '')})\n\n"
        f"{task.get('problem_statement', '')}\n\n"
        f"## Working in this repo\n\n"
        f"`testbed/` is a real, working checkout of this repo at its pinned "
        f"commit, with its own dependencies already installed inside a "
        f"container — edit files under `testbed/` freely. To run the repo's "
        f"OWN test suite (never the hidden grading tests) while you iterate, "
        f"run `./run_tests.sh <test-args>` from this directory; it syncs "
        f"your edits into the container and runs its real test command "
        f"there. When you are done, leave your changes in `testbed/` and "
        f"exit — your final diff is what gets graded, never this container.\n")


def default_container_factory(image_digest: str, *, client=None):  # pragma: no cover - needs docker
    """Start the agent's container from the pinned environment image — no
    `test_patch`, real dependencies, network ENABLED (the agent's own model
    API calls need egress; the isolation this module enforces is FROM the
    oracle, not from the network — the same asymmetry already documented for
    the adversary/governor ports). Returns `{container_id, workdir}`."""
    import docker
    from swebench.harness.constants import DOCKER_USER, DOCKER_WORKDIR
    client = client or docker.from_env()
    container = client.containers.run(
        image_digest, "tail -f /dev/null", user=DOCKER_USER, detach=True,
        network_disabled=False)
    return {"container_id": container.id, "workdir": DOCKER_WORKDIR}


def default_file_lister(container_id: str, workdir: str) -> dict[str, str]:  # pragma: no cover - needs docker
    """List every text file under `workdir` inside `container_id`, as
    `{path: content}` — the real half of the quarantine check, run against
    the agent's actual live container before it is ever handed to an agent."""
    import docker
    client = docker.from_env()
    container = client.containers.get(container_id)
    out = container.exec_run(f"find {workdir} -type f").output.decode(errors="ignore")
    texts = {}
    for path in out.splitlines():
        path = path.strip()
        if not path:
            continue
        r = container.exec_run(f"cat {path}")
        if r.exit_code == 0:
            texts[path] = r.output.decode(errors="ignore")
    return texts


def default_extract_tree(container_id: str, workdir: str, dest: Path) -> None:  # pragma: no cover - needs docker
    """`docker cp` the container's working tree onto the host at `dest`, then
    `git init` it — the agent edits this REAL host copy; `run_tests.sh`
    (materialized alongside it) syncs edits back into the container to run
    the repo's own tests. The host copy is what a `git diff` against is
    computed from once the agent is done."""
    import subprocess as sp
    dest.mkdir(parents=True, exist_ok=True)
    sp.run(["docker", "cp", f"{container_id}:{workdir}/.", str(dest)], check=True)
    sp.run(["git", "init", "-q"], cwd=dest, check=True)
    sp.run(["git", "add", "-A"], cwd=dest, check=True)
    sp.run(["git", "-c", "user.email=recurve@localhost", "-c", "user.name=recurve",
            "commit", "-q", "-m", "initial checkout (pre-agent)"], cwd=dest, check=True)


def _write_run_tests_script(dest: Path, container_id: str, workdir: str, test_cmd: str) -> None:
    (dest / "run_tests.sh").write_text(
        "#!/usr/bin/env bash\n"
        "# Syncs this directory's edits into the live container, then runs the\n"
        "# repo's OWN (non-hidden) test command there. Never runs the hidden\n"
        "# FAIL_TO_PASS/PASS_TO_PASS suite — those tests do not exist in this\n"
        "# container's tree at all (test_patch was never applied to it).\n"
        "set -e\n"
        f"HERE=\"$(cd \"$(dirname \"${{BASH_SOURCE[0]}}\")\" && pwd)\"\n"
        f"docker cp \"$HERE/testbed/.\" {container_id}:{workdir}\n"
        f"docker exec {container_id} bash -c 'cd {workdir} && {test_cmd} \"$@\"' -- \"$@\"\n"
    )
    (dest / "run_tests.sh").chmod(0o755)


def _recurve_init(testbed: Path, recurve_cmd: str | None) -> None:
    """Always run (both SWE_A0 and SWE_A3 get a real ledger, per AK-2's own
    insight: A0/A6-style arms differ from A3-style ones by which DoneSignalPort
    reads the ledger, never by whether it exists). Mirrors
    `materialize.recurve_init_workspace`'s exact invocation."""
    cmd = recurve_cmd or "recurve"
    subprocess.run([cmd if cmd == "recurve" else "python3",
                    *([] if cmd == "recurve" else [cmd]), "init"],
                   cwd=testbed, capture_output=True, text=True)


def materialize_swe_repo_workspace(
        dest: Path, task: dict, *, recurve_cmd: str | None = None,
        environment_image_digest: str | None = None,
        test_cmd: str = "pytest -q",
        container_factory=None, file_lister=None, extract_tree=None) -> Path:
    """`WorkspacePort["swe_bench_repo"]`. Starts the agent's container from
    the environment image (no test_patch — SW2's core guarantee), asserts the
    container's real tree is quarantined against `task["test_patch"]`,
    extracts that tree onto the host for the agent to edit, `recurve init`s
    it (ONE workspace port, always a real ledger — the 0%-vs-100%-recurve
    axis is `done_signal`, exactly AK-2's A0/A6 pattern generalized to a new
    benchmark), and writes `TASK.md` + `run_tests.sh`. `container_factory`/
    `file_lister`/`extract_tree` are injectable so this is testable without
    docker (the gated probe drives it with fakes); a real run supplies the
    docker-backed defaults. Raises `QuarantineError` before any of that if
    the leak check fails — the agent never sees a workspace that failed it."""
    container_factory = container_factory or default_container_factory
    file_lister = file_lister or default_file_lister
    extract_tree = extract_tree or default_extract_tree

    dest = Path(dest)
    handle = container_factory(environment_image_digest)
    container_id, workdir = handle["container_id"], handle["workdir"]

    file_texts = file_lister(container_id, workdir)
    assert_quarantined_swe(file_texts, task.get("test_patch") or "")

    _write_task(dest, task)
    extract_tree(container_id, workdir, dest / "testbed")
    _recurve_init(dest / "testbed", recurve_cmd)
    _write_run_tests_script(dest, container_id, workdir, test_cmd)
    (dest / "container.json").write_text(
        __import__("json").dumps(
            {"container_id": container_id, "workdir": workdir,
             "environment_image_digest": environment_image_digest}, indent=2))
    return dest


WORKSPACE_PORT_NAME = "swe_bench_repo"

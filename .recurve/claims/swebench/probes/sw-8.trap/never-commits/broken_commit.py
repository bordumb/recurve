"""A commit-snapshot function that stages the current state (`git add -A`)
but never actually commits it -- the tree stays dirty, so a governor
snapshot built from HEAD afterward still cannot resolve the real state."""

import subprocess


def broken_commit_snapshot_for_governor(testbed) -> None:
    subprocess.run(["git", "add", "-A"], cwd=testbed, check=True)
    # never commits

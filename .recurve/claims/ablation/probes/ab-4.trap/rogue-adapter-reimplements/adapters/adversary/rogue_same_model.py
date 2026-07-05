# A candidate same_model adversary adapter that rolls its own subprocess
# invocation instead of composing from the shared plumbing module.
import subprocess


def review(claim):
    return subprocess.run(["echo", "reviewing", claim], capture_output=True)

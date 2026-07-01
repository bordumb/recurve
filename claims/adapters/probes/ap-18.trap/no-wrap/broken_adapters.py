"""AP-18 counterexample: checkpoint does not wrap git failures, so a raw GitError escapes the snapshot path
(no CheckpointError symmetric with RestoreError)."""
from recurvelib.adapters import GitWorld as _R
class GitWorld(_R):
    def checkpoint(self):
        self._git("add", "-A")
        self._git("-c", "user.name=recurve", "-c", "user.email=recurve@localhost",
                  "commit", "-m", "runtime-checkpoint", "--allow-empty", "--no-verify", "--no-gpg-sign")  # BUG: unwrapped
        return self._git("rev-parse", "HEAD").strip()

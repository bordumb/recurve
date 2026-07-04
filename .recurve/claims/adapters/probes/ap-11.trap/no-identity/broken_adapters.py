"""AP-11 counterexample: checkpoint commits without supplying an identity, so it fails on a repo with no
configured user."""
from recurvelib.loop.adapters import GitWorld as _R
class GitWorld(_R):
    def checkpoint(self):
        self._git("add", "-A")
        self._git("commit", "-m", "runtime-checkpoint", "--allow-empty", "--no-verify", "--no-gpg-sign")  # BUG: no -c identity
        return self._git("rev-parse", "HEAD").strip()

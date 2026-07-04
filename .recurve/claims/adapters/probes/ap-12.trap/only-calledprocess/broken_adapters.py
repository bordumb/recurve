"""AP-12 counterexample: _git catches only CalledProcessError, so a missing git binary leaks a raw
FileNotFoundError out of restore."""
import subprocess
from recurvelib.adapters import GitWorld as _R, GitError
class GitWorld(_R):
    def _git(self, *args, timeout=60):
        try:
            out = subprocess.run(["git", "-C", str(self.root), *args], check=True,
                                 capture_output=True, text=True, timeout=timeout)
        except subprocess.CalledProcessError as e:      # BUG: FileNotFoundError/timeout escape raw
            raise GitError(str(e)) from e
        return out.stdout

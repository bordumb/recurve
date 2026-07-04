"""AP-6 counterexample: restore lets the raw CalledProcessError escape on a bad sha, so the safety-revert
path itself crashes."""

from recurvelib.loop.adapters import GitWorld as _Real


class GitWorld(_Real):
    def restore(self, sha):
        self._git("reset", "--hard", sha)          # BUG: no typed error on an unknown sha

"""AP-2 counterexample: restore is a no-op, so STOP-REVERT never actually rolls the tree back."""

from recurvelib.adapters import GitWorld as _Real


class GitWorld(_Real):
    def restore(self, sha):
        pass                                          # BUG: does not roll the tree back

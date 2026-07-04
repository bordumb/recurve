"""AP-4 counterexample: GitWorld.apply never writes the actor's patch, so the loop can never fix the tree."""

from recurvelib.loop.adapters import GitWorld as _Real


class GitWorld(_Real):
    def apply(self, patch):
        pass                                          # BUG: the actor's diff is dropped on the floor

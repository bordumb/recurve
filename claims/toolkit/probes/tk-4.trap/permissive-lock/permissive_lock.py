"""Counterexample lock: admits everyone. The refusal probe MUST go RED
against it."""


class LockHeld(RuntimeError):
    pass


class TreeLock:
    def __init__(self, tree):
        self.tree = tree

    def acquire(self):
        return None

    def release(self):
        return None

# A candidate arms.py that reimplements the adversary/governor registries
# locally instead of importing recurvelib's — exactly the drift AI5 exists
# to prevent (eval/'s arm composer must not diverge from the same registry
# /recurve-work's own gate config resolves through).
class NoOpAdversary:
    def review(self, claim):
        return None


ADVERSARY_ADAPTERS = {"off": NoOpAdversary}
GOVERNOR_ADAPTERS = {"off": NoOpAdversary}

"""AP-1 counterexample: GitWorld.apply skips the write boundary, so a patch that edits a probe under
claims/ is written to the referee surface."""

from recurvelib.adapters import GitWorld as _Real


class GitWorld(_Real):
    def apply(self, patch):
        for rel, content in patch.items():            # BUG: no within_boundary check
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

"""AP-7 counterexample: apply writes without rollback, so a patch that fails partway leaves earlier writes on
disk (tree neither old state nor proposed state)."""

import posixpath

from recurvelib.loop.adapters import GitWorld as _Real, BoundaryViolation
from recurvelib.loop.runtime import within_boundary


class GitWorld(_Real):
    def apply(self, patch):
        rels = list(patch)
        if not within_boundary(rels, "", self.referee_roots):
            raise BoundaryViolation(rels)
        for rel, content in patch.items():          # BUG: no rollback on a mid-loop write failure
            path = self.root / posixpath.normpath(rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

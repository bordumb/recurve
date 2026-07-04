"""AP-10 counterexample: apply reads the prior as text, so an in-bounds patch over a binary file crashes with
UnicodeDecodeError."""
import posixpath
from recurvelib.adapters import GitWorld as _R, BoundaryViolation
from recurvelib.runtime import within_boundary
class GitWorld(_R):
    def apply(self, patch):
        rels = list(patch)
        if not within_boundary(rels, "", self.referee_roots):
            raise BoundaryViolation(rels)
        for rel, content in patch.items():
            path = self.root / posixpath.normpath(rel)
            prior = path.read_text() if path.is_file() else None   # BUG: crashes on a binary prior
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

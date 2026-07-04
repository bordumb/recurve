"""AP-15 counterexample: rollback is unguarded and unlinks any existing path, so a patch key over a
pre-existing directory aborts rollback mid-loop, leaving an earlier key mutated (a mixed tree)."""
import posixpath
from recurvelib.adapters import GitWorld as _R, BoundaryViolation
from recurvelib.runtime import within_boundary
class GitWorld(_R):
    def apply(self, patch):
        rels = list(patch)
        if not within_boundary(rels, "", self.referee_roots):
            raise BoundaryViolation(rels)
        written = []
        try:
            for rel, content in patch.items():
                path = self.root / posixpath.normpath(rel)
                prior = path.read_bytes() if path.is_file() else None
                written.append((path, prior))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        except Exception:
            for path, prior in reversed(written):
                if prior is None:
                    if path.exists():
                        path.unlink()             # BUG: unlink on a dir raises, aborts the rollback
                else:
                    path.write_bytes(prior)
            raise

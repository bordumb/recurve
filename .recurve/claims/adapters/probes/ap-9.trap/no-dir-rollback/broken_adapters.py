"""AP-9 counterexample: rollback unlinks created files but never removes a directory it created, leaving an
orphan dir after a 'rolled back' apply."""
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
            for path, prior in reversed(written):        # BUG: created dirs never removed
                if prior is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.write_bytes(prior)
            raise

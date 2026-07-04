"""RT-15 counterexample: referee matching by bare startswith, so a sibling 'claims_backup/x' is wrongly
refused and an exact file named 'claims' is wrongly allowed."""

import posixpath


def within_boundary(diff_paths, target_root, referee_roots):
    referee_roots = tuple(referee_roots)
    for raw in diff_paths:
        if posixpath.isabs(raw):
            return False
        p = posixpath.normpath(raw)
        if p == ".." or p.startswith("../"):
            return False
        if not p.startswith(target_root):
            return False
        if any(p.startswith(r) for r in referee_roots):   # BUG: bare prefix, not path components
            return False
    return True

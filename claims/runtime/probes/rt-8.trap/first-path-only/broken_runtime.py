"""RT-8 counterexample: the boundary inspects only the first diff path, so a diff that pairs a clean file
with a probe edit is admitted. Passes RT-4 (single-path fixtures)."""

import posixpath


def within_boundary(diff_paths, target_root, referee_roots):
    referee_roots = tuple(referee_roots)
    paths = list(diff_paths)
    if not paths:
        return True
    raw = paths[0]                                                # BUG: only the first path is checked
    if posixpath.isabs(raw):
        return False
    p = posixpath.normpath(raw)
    if p == ".." or p.startswith("../"):
        return False
    if not p.startswith(target_root):
        return False
    if any(p.startswith(r) for r in referee_roots):
        return False
    return True

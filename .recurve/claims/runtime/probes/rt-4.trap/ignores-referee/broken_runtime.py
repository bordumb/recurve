"""RT-4 counterexample: the boundary checks only the target root and ignores the referee surface, so an
actor diff that edits a probe is accepted."""


def within_boundary(diff_paths, target_root, referee_roots):
    for p in diff_paths:
        if not p.startswith(target_root):
            return False
        # BUG: no referee-surface exclusion
    return True

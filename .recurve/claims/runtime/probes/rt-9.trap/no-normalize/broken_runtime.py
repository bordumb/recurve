"""RT-9 counterexample (the shipped bug, pre-fix): startswith with no normalization, so a '..' path escapes
the target tree. Passes RT-4 (no traversal in its fixtures)."""


def within_boundary(diff_paths, target_root, referee_roots):
    referee_roots = tuple(referee_roots)
    for p in diff_paths:
        if not p.startswith(target_root):                        # BUG: no isabs / '..' normalization
            return False
        if any(p.startswith(r) for r in referee_roots):
            return False
    return True

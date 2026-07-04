"""RT-18 counterexample: no root-key rejection and no degenerate-referee fail-closed, so an empty referee root
protects nothing and a "." root key is admitted."""
import posixpath
def within_boundary(diff_paths, target_root, referee_roots):
    referee_roots = tuple(referee_roots)
    for raw in diff_paths:
        if posixpath.isabs(raw):
            return False
        p = posixpath.normpath(raw)
        if p == ".." or p.startswith("../"):            # BUG: does not reject "." (the root itself)
            return False
        if not p.startswith(target_root):
            return False
        for r in referee_roots:
            rr = r.rstrip("/")                          # BUG: no degenerate (empty/root/..) fail-closed
            if p == rr or p.startswith(rr + "/"):
                return False
    return True

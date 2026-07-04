"""RED counterexample for TK-22: an infer_init_mode that returns "blank" for a
spec FILE. Silently ignoring a spec is the worst inference — the user points at
a PRD asking for it to be claimified, and the scaffold quietly drops it on the
floor instead. The probe MUST turn RED against this."""
from pathlib import Path


def infer_init_mode(path: Path) -> tuple[str, str]:
    # The defect: a real spec file gets read as "nothing to mine" and scaffolds
    # blank, silently discarding the spec the user handed us.
    if path.is_file():
        return ("blank", f"{path.name} — ignored (the defect)")
    if path.is_dir():
        if (path / ".git").exists():
            return ("from-repo", f"{path.name} is a git repo")
        return ("blank", f"{path.name} is an empty directory")
    return ("blank", f"{path} does not exist yet")

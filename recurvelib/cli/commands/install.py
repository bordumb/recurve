from __future__ import annotations

from ..base import *  # shared recurvelib imports
from ..base import (
    _fail,
    _config,
    _load,
    _filter,
    _parse_point,
    _parse_goal,
    _draft_backlog,
)

def cmd_install(args):
    """Symlink the recurve entrypoint onto PATH — one idempotent step, no
    package install. The entrypoint resolves recurvelib relative to its own
    real path, so a symlink anywhere runs the engine from this clone."""
    import os
    import recurvelib
    # Anchor on the recurvelib package so the entrypoint path is independent of
    # how deep this command module lives (the split moved it under cli/commands/).
    entry = (Path(recurvelib.__file__).resolve().parent.parent / "recurve")
    if not entry.exists():
        _fail(f"recurve entrypoint not found at {entry} — run install from a recurve checkout")
    bin_dir = Path(args.bin_dir).expanduser().resolve()
    bin_dir.mkdir(parents=True, exist_ok=True)
    link = bin_dir / "recurve"
    # Idempotent: replace an existing symlink (to recurve or anything) but never
    # clobber a real file we did not place.
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        _fail(f"{link} exists and is not a symlink — refusing to overwrite a real file", 1)
    link.symlink_to(entry)
    print(f"linked {link} → {entry}")
    path_dirs = (os.environ.get("PATH", "")).split(os.pathsep)
    if str(bin_dir) not in path_dirs:
        print(f"\033[33m⚠ {bin_dir} is not on $PATH — add it, e.g. "
              f"export PATH=\"{bin_dir}:$PATH\"\033[0m")

    # Also install the global slash-command skills (/recurve-plan, /recurve-work)
    # so they are available in every repo, not only recurve-initialized ones.
    if not getattr(args, "no_skills", False):
        import shutil
        skills_src = entry.parent / "templates" / "global-skills"
        if skills_src.is_dir():
            skills_dir = Path(getattr(args, "skills_dir", None)
                              or "~/.claude/skills").expanduser().resolve()
            installed = []
            for tmpl in sorted(skills_src.glob("*.md")):
                dest = skills_dir / tmpl.stem
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(tmpl, dest / "SKILL.md")
                installed.append("/" + tmpl.stem)
            if installed:
                print(f"installed global skills into {skills_dir}: {', '.join(installed)}")

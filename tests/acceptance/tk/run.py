#!/usr/bin/env python3
"""Acceptance runner: invoke the engine against one re-hosted ancestor
instance, presenting the program name its golden output was captured under.

    run.py <instance> <prog> <command...>
    e.g. run.py demos rictl next

Instances are the configs/ directory's *.toml files. The ancestor trees are
execution targets only — nothing here writes outside recurve/.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from recurvelib.cli import main  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    instance, prog, *rest = sys.argv[1:]
    config = HERE / "configs" / f"{instance}.toml"
    if not config.is_file():
        print(f"unknown instance {instance!r} (no {config})", file=sys.stderr)
        raise SystemExit(2)
    main(rest, prog=prog, config_path=str(config))

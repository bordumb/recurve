"""BROKEN counterexample for SR-4: a materialize that produces the workflow but
never materializes the contract, so the cycle prompt still points at a
.recurve/RUN.md that does not exist on the self-host repo."""

import tempfile
from pathlib import Path


def materialize_workflow(cfg, script):
    tmp = Path(tempfile.mkdtemp(prefix="recurve-broken-"))
    wf = tmp / script.name
    wf.write_text("Read .recurve/RUN.md and obey it.\nPROG=recurve\n")
    return wf

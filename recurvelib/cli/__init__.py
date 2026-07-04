"""recurve CLI package. `main` is re-exported so the recurvelib.cli:main
console entrypoint resolves unchanged after the split."""

from .main import main

__all__ = ["main"]

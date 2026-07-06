"""The plausible bug: checking for the whole raw patch text as one substring.

`test_patch`'s diff plumbing (`diff --git a/...`, `@@ ... @@`, `+++`/`---`
headers) never appears verbatim in an ordinary source file — only the
ADDED CONTENT (the function body, the assertion) would ever leak. A check
that requires the entire patch text as a substring will basically never
fire on a real leak, because the leaked content is always a SUBSET of the
patch (just the `+` lines' content), never the whole diff byte-for-byte.
"""

from __future__ import annotations


class QuarantineError(RuntimeError):
    pass


def assert_quarantined_swe(file_texts: dict[str, str], test_patch: str) -> None:
    needle = test_patch.strip()
    if not needle:
        return
    for path, text in file_texts.items():
        if needle in text:
            raise QuarantineError(f"leaked into {path}")

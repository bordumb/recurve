"""AP-14 counterexample: _jsonable does not guard the dataclass branch, so a recursive dataclass field raises
RecursionError."""
import dataclasses
def _jsonable(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)                  # BUG: unguarded; recursive field -> RecursionError
    try:
        return str(obj)
    except Exception:
        return "<x>"

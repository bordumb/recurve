"""AP-8 counterexample: _jsonable re-raises when an object's __str__ throws, so serializing the evidence can
crash propose before the agent even runs."""

import dataclasses


def _jsonable(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return str(obj)                                 # BUG: propagates if __str__ raises

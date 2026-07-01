"""CL-24 counterexample: covered_by returns the whole surface as covered, ignoring what the exercises run —
the declarative lie the aggregate tracer exists to kill."""


def covered_by(exercises, surface_ids):
    return set(surface_ids)          # BUG: declares everything covered, traces nothing

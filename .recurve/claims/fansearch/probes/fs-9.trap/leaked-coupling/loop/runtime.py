"""KNOWN-BAD fixture: simulates the core burndown loop accidentally
picking up a direct dependency on the fansearch registry -- exactly the
coupling the ablation switch's inertness claim must catch."""
from recurvelib.adapters.proxy import PROXY_ADAPTERS  # BUG: core loop must never import this

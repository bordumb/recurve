"""Agent adapters — the BYO-agent seam. An adapter is a callable
`adapter(cell, workspace) -> row` the runner drives; the mock used in tests and
the real Claude wrapper used in a paid run share that one shape."""

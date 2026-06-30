"""AD-1 counterexample: probe-ability as an OR, so an assertion is 'probe-able' on a single virtue even
while it lacks an oracle, a counterexample, or a bound."""


def probeable(a):
    return a.falsifiable or a.has_counterexample or a.bounded  # BUG: OR, not AND

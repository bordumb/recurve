"""CL-26 counterexample: covered_by catches only Exception, so a probe body that calls sys.exit()
(SystemExit is a BaseException) escapes and aborts the whole coverage pass."""
from recurvelib.analysis.measured import measure_coverage
def covered_by(exercises, surface_ids):
    surface_ids = set(surface_ids)
    covered = set()
    for ex in exercises:
        try:
            covered |= measure_coverage(ex, surface_ids)
        except Exception:                      # BUG: SystemExit / KeyboardInterrupt slip past
            continue
    return covered

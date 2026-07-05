# A deliberately wrong `capture()` — always defers to the "red on wrong" input
# alone, ignoring whether the trap is GREEN on the real implementation. This
# is the shape of regression AB-1 exists to catch: a capture rule that would
# accept a trap that ALSO breaks the real code (trap_green_on_real=False).
def capture(trap_red_on_wrong: bool, trap_green_on_real: bool) -> bool:
    return trap_red_on_wrong

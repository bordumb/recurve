"""RT-5 counterexample: capture ignores whether the trap catches the bug, accepting any trap that merely
passes on the real implementation -- a trap that discriminates nothing."""


def capture(trap_red_on_wrong, trap_green_on_real):
    return trap_green_on_real        # BUG: drops the RED-on-wrong requirement

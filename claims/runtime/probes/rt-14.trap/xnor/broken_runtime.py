"""RT-14 counterexample: capture as XNOR accepts a trap that is green-on-wrong AND red-on-real -- nonsense on
both axes. Passes RT-5 (which never tests the (False, False) row)."""


def capture(trap_red_on_wrong, trap_green_on_real):
    return (trap_red_on_wrong and trap_green_on_real) or (not trap_red_on_wrong and not trap_green_on_real)

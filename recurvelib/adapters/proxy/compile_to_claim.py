"""The promotion bridge for the dyadic_lyapunov domain: a survivor
`Candidate` becomes a pinned Lean statement + trap, specializing the
already-proven `shell_single_active_dissipative` (any weight, any
cross-term, single active shell) to the candidate's concrete numbers.
Writing this to disk and baselining it is the campaign engine's job, not
this function's -- `compile_to_claim` only returns text.

This validates the *mechanism* (candidate -> Lean statement -> kernel
check), not a claim of new mathematics: single-shell dissipativity for any
weight is already proven once, universally. A genuinely novel multi-shell
bound is a harder, still-open question a survivor's numbers alone do not
hand you a proof of.
"""
from __future__ import annotations

from dataclasses import dataclass

from recurvelib.adapters.proxy.dyadic_lyapunov import Candidate


@dataclass(frozen=True)
class ClaimDraft:
    theorem_name: str
    theorem_lean: str      # the new declaration -- appended to the target source
    statement_lean: str    # the check.lean pin, referencing theorem_name
    trap_lean: str          # the Module.lean trap -- theorem_name redefined as an impostor
    smallest_fix_note: str


def _lean_real_literal(x: float) -> str:
    """A Lean `ℝ` literal for an arbitrary float, parenthesized so a
    negative value composes safely into a larger expression."""
    return f"({x!r} : ℝ)"


def _lean_list(values: tuple) -> str:
    return "[" + ", ".join(_lean_real_literal(v) for v in values) + "]"


def _weight_fn(list_lean: str) -> str:
    return f"(fun n => ({list_lean} : List ℝ).getD n 0)"


def compile_to_claim(candidate: Candidate, nu: float = 1.0, alpha: float = 0.5,
                     theorem_name: str = "dyadic_candidate_dissipative") -> ClaimDraft:
    """Pure function: candidate + physical parameters -> Lean declaration,
    pin, and trap text. Never writes to disk, never invokes the gate."""
    N = candidate.N
    b_list = _lean_list(candidate.b)
    d_list = _lean_list(candidate.d)
    nu_lit = _lean_real_literal(nu)
    alpha_lit = _lean_real_literal(alpha)
    b_n_lit = _lean_real_literal(candidate.b[N])
    b_fn = _weight_fn(b_list)
    d_fn = _weight_fn(d_list)

    proposition = f"""∀ u : ℕ → ℝ, (∀ n, n ≠ {N} → u n = 0) →
      (∑ n ∈ Finset.range ({N} + 1), {b_fn} n * (2 * u n * shellRHS {nu_lit} {alpha_lit} u n))
        + ∑ n ∈ Finset.range {N},
            {d_fn} n * (shellRHS {nu_lit} {alpha_lit} u n * u (n + 1)
                        + u n * shellRHS {nu_lit} {alpha_lit} u (n + 1))
        = -2 * {nu_lit} * dissipationFactor {alpha_lit} {N} * {b_n_lit} * u {N} ^ 2"""

    theorem_lean = f"""theorem {theorem_name} :
    {proposition} :=
  fun u hsingle => shell_single_active_dissipative {nu_lit} {alpha_lit} {N} (by norm_num)
    {b_fn} {d_fn} u hsingle
"""

    statement_lean = f"""example :
    {proposition} :=
  {theorem_name}

#print axioms NavierStokes.Shells.{theorem_name}
"""

    trap_lean = f"""-- KNOWN-BAD: impostor with a mangled (weakened) statement
theorem {theorem_name} : True := trivial
"""

    smallest_fix_note = (
        f"candidate N={N}: instantiate shell_single_active_dissipative with the "
        f"discovered weights; a true, kernel-checked corollary of SH7, not a new theorem."
    )
    return ClaimDraft(theorem_name=theorem_name, theorem_lean=theorem_lean,
                      statement_lean=statement_lean, trap_lean=trap_lean,
                      smallest_fix_note=smallest_fix_note)

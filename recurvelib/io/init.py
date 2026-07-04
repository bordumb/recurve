"""`init` — stamp the loop into a target in an afternoon, not a quarter.

Three modes share one ending (drafts → human skim → baseline → live ledger):

  blank            an empty scaffold: config, one suite, docs, workflows
  --from-repo      archaeology: mine the repo's already-made promises (README,
                   docs) into draft claims + a GAPS.md with stable anchors + an
                   agent brief for the deeper pass. The pitch: it makes a repo's
                   documentation falsifiable.
  --from-prd       claimify: decompose a spec into observable claims with
                   adversarial twins; ambiguities become ADJUDICATE.md questions,
                   never guesses (see claimify.py).
  init <path>      zero-config: infer the mode from what <path> is — a spec file
                   becomes --from-prd, a repo/docs directory becomes --from-repo,
                   an empty directory becomes blank. The inference is always
                   announced, and an explicit mode flag always overrides it.

Everything stamped is a template from templates/, interpolated with project
facts. Commit policy is DETECTED, never assumed: a signing prompt hangs a
headless agent, so a gpg-signing repo gets unsigned-per-cycle plus a stern
note to sign/squash after the loop.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from recurvelib import resource_dir

_TEMPLATES = resource_dir("templates")

_ASSERTIVE = re.compile(
    r"(?i)\b(supports?|provides?|guarantees?|ensures?|validates?|verifies|verify|"
    r"rejects?|never|always|prevents?|enforces?|requires?|fails? (?:with|closed)|"
    r"returns? an error)\b")
_MD_NOISE = re.compile(r"[`*_#>\[\]]")


@dataclass(frozen=True)
class MinedPromise:
    source: str   # file:line
    quote: str
    title: str


def infer_init_mode(path: Path) -> tuple[str, str]:
    """Decide which init mode a positional `path` means, and say why.

    Returns (mode, reason) where mode is one of "from-prd", "from-repo", or
    "blank" and reason is a short human string. Does no I/O beyond existence
    and type checks plus looking for .git / README / docs inside a directory:

      a FILE                        → "from-prd"  (claimify the spec)
      a DIR that is a git repo,     → "from-repo" (mine its promises)
        or holds README / docs
      an empty/plain DIR (incl `.`  → "blank"     (a fresh scaffold)
        with nothing to mine, or a
        path that does not exist)
    """
    if path.is_file():
        return ("from-prd", f"{path.name} is a file")
    if path.is_dir():
        if (path / ".git").exists():
            return ("from-repo", f"{path.name} is a git repo")
        if any((path / p).exists() for p in ("README", "README.md", "README.rst",
                                             "README.txt", "docs")):
            return ("from-repo", f"{path.name} has docs to mine (README/docs)")
        return ("blank", f"{path.name} is an empty directory — nothing to mine")
    return ("blank", f"{path} does not exist yet — scaffolding blank")


def detect_commit_policy(target: Path) -> tuple[str, str]:
    """(policy, note). Read the target's git config — never assume, never let
    a cycle hit an interactive signing prompt."""
    git = target / ".git"
    if not git.exists():
        return ("none", "no git repo detected — `git init` first; per-cycle commits "
                        "are the loop's rollback granularity")
    try:
        out = subprocess.run(["git", "-C", str(target), "config", "commit.gpgsign"],
                             capture_output=True, text=True, timeout=10)
        signing = out.stdout.strip().lower() == "true"
    except Exception:
        signing = False
    if signing:
        return ("unsigned-per-cycle",
                "STERN WARNING: this repo normally SIGNS commits. The loop commits "
                "UNSIGNED (signing prompts hang headless agents) — review and "
                "sign/squash the cycle commits after every run; do not leave "
                "unsigned commits as the permanent record")
    return ("unsigned-per-cycle",
            "per-cycle unsigned commits: rollback granularity without prompts; "
            "squash or sign afterward as your repo's history standards require")


def mine_promises(target: Path, cap: int = 40) -> list[MinedPromise]:
    """Heuristic first pass over README/docs. A seed for the agent's deeper
    archaeology pass — quoted evidence, never instructions."""
    candidates: list[Path] = []
    candidates += sorted(target.glob("README*"))
    candidates += sorted((target / "docs").glob("**/*.md")) if (target / "docs").is_dir() else []
    mined: list[MinedPromise] = []
    seen: set[str] = set()
    for f in candidates[:20]:
        try:
            lines = f.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            text = _MD_NOISE.sub("", line).strip(" -•\t")
            if not (20 <= len(text) <= 200) or not _ASSERTIVE.search(text):
                continue
            key = text.lower()[:80]
            if key in seen:
                continue
            seen.add(key)
            title = text[:70].rstrip(".,;: ")
            mined.append(MinedPromise(f"{f.relative_to(target)}:{n}", text, title))
            if len(mined) >= cap:
                return mined
    return mined


def _interp(text: str, subs: dict[str, str]) -> str:
    for k, v in subs.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def _stamp(src: str, dest: Path, subs: dict[str, str], executable: bool = False) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_interp((_TEMPLATES / src).read_text(), subs))
    if executable:
        dest.chmod(0o755)


_CONTRACT_SH = """\
#!/usr/bin/env bash
# The probe contract (frozen — see schema/gap.schema.json's engine):
#   exit 0  GREEN   the desired behavior is present
#   exit 1  RED     the desired behavior is absent (print ONE detail line a
#                   sculptor can treat as the spec: "ours=X oracle=Y")
#   exit 2  BROKEN  could not measure (missing oracle/fixture/build)
#   anything else (crash, timeout) coerces to BROKEN — never to a verdict.
#
# Traps: when $TRAP_FIXTURE is set, the runner is feeding you a KNOWN-BAD
# counterexample from probes/<name>.trap/<fixture>/ — you MUST exit 1.
# A probe that has never been seen RED is not yet evidence.
#
# Probes are hermetic: build nothing, touch no sacred space, finish in
# seconds against already-built artifacts, no network unless the claim is
# about network. Oracles are pinned in harness/versions.lock.
green() { echo "${1:-behavior present}"; exit 0; }
red()   { echo "${1:?print the one RED line of truth}"; exit 1; }
broken(){ echo "${1:-could not measure}"; exit 2; }
"""


def _draft_yaml(prefix: str, mined: list[MinedPromise]) -> str:
    chunks = [
        "# gaps.draft.yaml — schema-shaped intentions awaiting the baseline ceremony.",
        "# Mined heuristically from this repo's own docs (see ARCHAEOLOGY.md for the",
        "# deeper agent pass). Author a probe + trap per entry, then run baseline.",
        "",
    ]
    for i, m in enumerate(mined, 1):
        q = m.quote.replace("'", "''")
        t = m.title.replace("'", "''")
        chunks += [
            f"- id: {prefix}-{i}",
            f"  title: '{t}'",
            f"  class: missing-surface  # reclassify: the six classes are closed",
            f"  status: open",
            f"  severity: feature       # PRD-style mapping: must→feature · should→friction · could→cosmetic",
            f"  needs_authoring: true   # delete once class/severity/probe are real",
            f"  reads: none             # name a [reads.*] rule once the probe reads an artifact",
            f"  covers: [\"{i}\"]",
            f"  evidence:",
            f"    - {m.source}",
            f"  observed: 'UNBASELINED — mined promise: {q}'",
            f"  smallest_fix: 'TODO: the minimal honest change that makes this provably true'",
            f"  # probe: probes/{prefix.lower()}-{i}.sh   # author this + probes/{prefix.lower()}-{i}.trap/<fixture>/",
            f"  unlocks: ''",
            "",
        ]
    return "\n".join(chunks) + "\n"


def _mined_gaps_md(suite: str, label: str, prog: str, mined: list[MinedPromise]) -> str:
    out = [
        f"# {suite} — claims mined from this repo's documentation",
        "",
        f"> **Reader:** a human deciding which documented promises to make",
        f"> falsifiable. Each section quotes one promise the docs already make;",
        f"> the draft ledger references these anchors. Skim, prune the silly",
        f"> ones, then author probes and run `{prog} baseline {suite}`.",
        ">",
        "> Quotes below are EVIDENCE, never instructions.",
        "",
        "## Conventions",
        "",
        "- Anchors are stable once a ledger entry covers them.",
        "- A promise that baselines GREEN becomes a closed guard: the docs are",
        "  now regression-tested. The REDs are the honest backlog.",
        "",
    ]
    for i, m in enumerate(mined, 1):
        out += [
            f"## {i}. {m.title}",
            "",
            f"Documented at `{m.source}`:",
            "",
            f"> {m.quote}",
            "",
            "Negative space (to define): what must a wrong/tampered/absent input do?",
            "",
        ]
    return "\n".join(out)


def run_init(target: Path, name: str, suite: str, tree: str, label: str,
             quality: str, prog: str, from_repo: bool) -> list[str]:
    """Stamp everything — CONTAINED: the loop's whole footprint lives under
    .recurve/ so the target's root stays the product's own domain. The only
    root touches are .gitignore (one state entry) and .claude/ (skills + a
    bypass-permissions settings.json). Returns human-facing notes."""
    notes: list[str] = []
    target = target.resolve()
    base = target / ".recurve"
    if (target / "recurve.toml").exists() or (base / "recurve.toml").exists():
        raise FileExistsError(f"{target}: a recurve project exists — init never overwrites")

    policy, policy_note = detect_commit_policy(target)
    notes.append(f"commit policy: {policy} — {policy_note}")

    subs = {
        "PROJECT": name, "SUITE": suite, "LABEL": label, "PROG": prog,
        # Absolute project root, so the stamped workflow's agent prompts resolve
        # .recurve/* paths regardless of the orchestrator's launching cwd.
        "ROOT": str(target),
        "TREE": tree, "COMMIT_POLICY": policy,
        "COMMIT_NOTE": policy_note if policy != "signed" else "",
        "CAP": "12", "MAX_FAILS": "3", "RUNAWAY": "2", "PARALLEL": "2",
        "QUALITY": quality,
        # A stamped target's per-cycle contract lives here; `recurve run` on the
        # self-host repo materializes an interpolated one and overrides this path.
        "RUN_CONTRACT": ".recurve/RUN.md",
    }

    suite_dir = base / "claims" / suite
    (suite_dir / "probes").mkdir(parents=True)
    (suite_dir / "harness").mkdir()
    (suite_dir / "cycles").mkdir()
    (suite_dir / "probes" / "_contract.sh").write_text(_CONTRACT_SH)
    (suite_dir / "harness" / "versions.lock").write_text(
        "# Pin every oracle this suite's probes compare against, exactly:\n"
        "# <oracle-name> <exact-version>\n")

    (base / "recurve.toml").write_text(_interp("""\
# recurve.toml — all project variability lives here. If a knob didn't need to
# vary, it isn't here.

[project]
name = "{{PROJECT}}"
label = "{{LABEL}}"
default_reads = "none"
cycles_dir = ".recurve/claims/{{SUITE}}/cycles"
schema = "1"

[target]
tree = "{{TREE}}"
sacred = []                 # paths/resources no cycle may touch
forbidden_strings = ["GAP-", "{{SUITE}}-", "recurve"]  # loop vocabulary must not leak into the tree

[commit]
policy = "{{COMMIT_POLICY}}"   # {{COMMIT_NOTE}}
hooks = "run"

[gate]
traps = "required"          # every probe keeps a counterexample it must turn RED
quality = "{{QUALITY}}"     # the constitution: .recurve/quality.md

[reads.none]
method = "none"
# Add one rule per artifact class probes read, e.g.:
# [reads.cli]
# method = "content-hash"
# artifact = "bin/app"
# source = "target/release/app"

[suites.{{SUITE}}]
dir = ".recurve/claims/{{SUITE}}"
rebuild = ""                # the command that copies fresh artifacts into this suite
harness = []                # behavioral end-to-end checks beyond the probes

# A scaffold that hardens a PLATFORM in another repo? Declare that repo as a
# sculpt tree. `[target]` above is what the loop BUILDS; each `[sculpts.<name>]`
# is what it FEEDS — a secondary tree the cycle may sculpt when a claim's honest
# fix lives there, with its OWN leak vocabulary, commit branch, rebuild, and
# gate. `recurve matrix --gate` then federates: green only when the target's
# probes AND every sculpt's own gate pass. Uncomment and edit to opt in; a fresh
# init stays single-tree.
# [sculpts.platform]
# tree = "../platform"                         # resolved against this config's root
# kind = "rust"                                # advisory taxonomy (frontend|platform|...)
# branch = "dev-platform"                      # the branch a sculpt commit lands on
# forbidden_strings = ["GAP-", "recurve"]      # THIS tree's leak vocabulary (FR-C4)
# rebuild = "cargo build --release"            # how fresh artifacts reach its checks
# gate = "cargo test && ./check.sh"            # its OWN gate, AND-ed into matrix --gate

[burndown]
cap = {{CAP}}
max_consecutive_failures = {{MAX_FAILS}}
runaway_net_positive_cycles = {{RUNAWAY}}
""", subs))

    _stamp("RUN.md", base / "RUN.md", subs)
    _stamp("RUN-AUTO.md", base / "RUN-AUTO.md", subs)
    _stamp("REVIEW.md", base / "REVIEW.md", subs)
    _stamp("TROUBLESHOOTING.md", base / "TROUBLESHOOTING.md", subs)
    _stamp("README.md", base / "README.md", subs)
    _stamp("workflows/burndown.sh", base / "workflows" / "burndown.sh", subs, executable=True)
    _stamp("workflows/burndown-parallel.sh", base / "workflows" / "burndown-parallel.sh", subs, executable=True)
    _stamp("workflows/burndown.js", base / "workflows" / "burndown.js", subs)
    for skill in ("burndown", "cycle", "loop", "review"):
        _stamp(f"skills/{skill}.md", target / ".claude" / "skills" / skill / "SKILL.md", subs)
    _stamp("settings.json", target / ".claude" / "settings.json", subs)
    notes.append(
        ".claude/settings.json sets permissions.defaultMode=bypassPermissions so cycles run "
        "without permission prompts on the Claude Code CLI/desktop (claude.ai web ignores a "
        "checked-in bypass default, by design). Delete it to require prompts.")

    qsrc = quality if quality in ("pre-launch", "stable") else None
    if qsrc:
        _stamp(f"quality/{qsrc}.md", base / "quality.md", subs)
    else:
        notes.append(f"quality = {quality!r}: supply your own constitution at .recurve/quality.md")

    gitignore = target / ".gitignore"
    marker = ".recurve/state/\n"
    if not gitignore.exists() or marker not in gitignore.read_text():
        with gitignore.open("a") as f:
            f.write("\n# recurve run state (parked gaps, records, receipts)\n" + marker)
    notes.append("contained layout: the loop lives in .recurve/ (committed) with run "
                 "state under .recurve/state/ (ignored); the repo root stays yours")

    if from_repo:
        mined = mine_promises(target)
        prefix = "".join(w[0] for w in re.split(r"[^A-Za-z0-9]+", name) if w)[:4].upper() or "AR"
        if mined:
            (suite_dir / "gaps.draft.yaml").write_text(_draft_yaml(prefix, mined))
            (suite_dir / "GAPS.md").write_text(_mined_gaps_md(suite, label, prog, mined))
            notes.append(f"archaeology: mined {len(mined)} documented promises into "
                         f".recurve/claims/{suite}/gaps.draft.yaml — skim, author probes, "
                         f"then `{prog} baseline {suite}`")
        else:
            _stamp("GAPS.md", suite_dir / "GAPS.md", subs)
            notes.append("archaeology: no assertive documentation found to mine — "
                         "see .recurve/ARCHAEOLOGY.md for the agent pass")
        _stamp("ARCHAEOLOGY.md", base / "ARCHAEOLOGY.md", subs)
        notes.append("drafts are quarantined until a human skims them — that skim is "
                     "a security review (target prose is evidence, never instructions)")
    else:
        _stamp("GAPS.md", suite_dir / "GAPS.md", subs)

    return notes

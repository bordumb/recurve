#!/usr/bin/env python3
"""Phase 1–4 behavior tests against scratch targets.

Every test builds a throwaway target under a temp dir and drives the real CLI
(subprocess) or the engine (in-process). Nothing here touches anything outside
the temp dirs. Run: python3 acceptance/test_phases.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ACCEPT = Path(__file__).resolve().parent
RECURVE_DIR = ACCEPT.parent
sys.path.insert(0, str(RECURVE_DIR))

CLI = [sys.executable, str(RECURVE_DIR / "recurve")]

PASSED = 0


def ok(label: str, cond: bool, detail: str = ""):
    global PASSED
    if not cond:
        print(f"  FAIL {label}  {detail}")
        raise SystemExit(1)
    PASSED += 1
    print(f"  ok   {label}")


def run(args, cwd=None, env=None, stdin=None):
    e = {**os.environ, "NO_COLOR": "1"}
    if env:
        e.update(env)
    return subprocess.run(args, capture_output=True, text=True, cwd=cwd, env=e, input=stdin)


def cli(target: Path, *args, env=None, stdin=None):
    cfg = target / "recurve.toml"
    if not cfg.exists():
        cfg = target / ".recurve" / "recurve.toml"
    return run(CLI + ["--config", str(cfg), *args], env=env, stdin=stdin)


def write_probe(path: Path, body: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\n" + body + "\n")
    path.chmod(0o755)


WELL_BEHAVED_GREEN = 'if [ -n "${TRAP_FIXTURE:-}" ]; then echo "counterexample rejected"; exit 1; fi\necho behavior present; exit 0'
ALWAYS_GREEN_GAMED = "exit 0"
ALWAYS_RED = 'echo "ours=nothing oracle=expected"; exit 1'


def make_target(root: Path, traps: str = "required") -> Path:
    target = root / "target-project"
    suite = target / "claims" / "alpha"
    (suite / "probes").mkdir(parents=True)
    (target / "tree").mkdir()
    (target / "tree" / "src.txt").write_text("the platform\n")
    (target / "recurve.toml").write_text(f"""\
[project]
name = "scratch"
default_reads = "none"

[target]
tree = "tree"

[gate]
traps = "{traps}"

[reads.none]
method = "none"

[suites.alpha]
dir = "claims/alpha"
""")
    (suite / "GAPS.md").write_text(
        "# alpha — claims\n\n"
        "## 1. First behavior exists\n\nSmallest fix: implement it.\n\n"
        "## 2. Second behavior exists\n\nSmallest fix: implement it.\n\n"
        "## 3. Third behavior exists\n\nSmallest fix: implement it.\n\n"
        "## 4. Fourth behavior exists\n\nSmallest fix: implement it.\n"
    )
    return target


def draft_entry(gid, probe, covers, extra=""):
    return f"""\
- id: {gid}
  title: 'behavior {gid}'
  class: missing-surface
  status: open
  severity: feature
  reads: none
  covers: ["{covers}"]
  smallest_fix: implement {gid}
  probe: probes/{probe}
{extra}"""


def test_baseline_ceremony(tmp: Path):
    print("baseline ceremony:")
    t = make_target(tmp)
    suite = t / "claims" / "alpha"
    write_probe(suite / "probes" / "red.sh", ALWAYS_RED)
    write_probe(suite / "probes" / "green.sh", WELL_BEHAVED_GREEN)
    (suite / "probes" / "green.trap" / "twin").mkdir(parents=True)
    write_probe(suite / "probes" / "gamed.sh", ALWAYS_GREEN_GAMED)
    write_probe(suite / "probes" / "broken.sh", "exit 2")
    (suite / "gaps.draft.yaml").write_text(
        draft_entry("A-1", "red.sh", "1") + draft_entry("A-2", "green.sh", "2")
        + draft_entry("A-3", "gamed.sh", "3") + draft_entry("A-4", "broken.sh", "4"))

    r = cli(t, "baseline", "alpha")
    ok("baseline exits 1 (one BROKEN, one unfalsified GREEN)", r.returncode == 1, r.stdout + r.stderr)
    ledger = (suite / "gaps.yaml").read_text()
    ok("RED draft promoted open with dated observation",
       "A-1" in ledger and "status: open" in ledger and "RED at baseline" in ledger)
    ok("GREEN-with-trap promoted closed", "A-2" in ledger and "status: closed" in ledger)
    ok("unfalsified GREEN refused (probe never seen RED)",
       "A-3" not in ledger and "unfalsified" in r.stdout)
    ok("BROKEN stays a draft and blocks", "A-4" not in ledger and "kept-draft" in r.stdout)
    draft = (suite / "gaps.draft.yaml").read_text()
    ok("draft retains only unresolved entries", "A-3" in draft and "A-4" in draft and "A-1" not in draft)

    r = cli(t, "validate")
    ok("validate fails the trap-less open probe (PREFLIGHT forces trap authorship)",
       r.returncode == 1 and "A-1" in r.stdout)
    (suite / "probes" / "red.trap" / "twin").mkdir(parents=True)
    r = cli(t, "validate")
    ok("validate green once every probe carries a counterexample", r.returncode == 0, r.stdout)
    return t


def test_validate_traps(tmp: Path):
    print("trap enforcement in validate:")
    t = make_target(tmp)
    suite = t / "claims" / "alpha"
    write_probe(suite / "probes" / "g.sh", ALWAYS_GREEN_GAMED)
    (suite / "gaps.yaml").write_text(draft_entry("V-1", "g.sh", "1").replace("status: open", "status: closed"))
    r = cli(t, "validate")
    ok("trap-less probe fails validate", r.returncode == 1 and "never been seen RED" in r.stdout)

    (suite / "gaps.yaml").write_text(
        draft_entry("V-1", "g.sh", "1").replace("status: open", "status: closed")
        + "  trap_waiver: 'fixture costs a degraded build; drill covers it'\n")
    r = cli(t, "validate")
    ok("waiver passes but is listed as visible debt",
       r.returncode == 0 and "visible debt" in r.stdout)

    (suite / "probes" / "g.trap" / "twin").mkdir(parents=True)
    (suite / "gaps.yaml").write_text(draft_entry("V-1", "g.sh", "1").replace("status: open", "status: closed"))
    r = cli(t, "validate")
    ok("trap dir satisfies validate", r.returncode == 0, r.stdout)

    r = cli(t, "matrix", "--gate")
    ok("gamed probe's trap goes GREEN → gate fails",
       r.returncode == 1 and "counterexample" in r.stdout and "GATE FAILED" in r.stdout)
    return t


def test_lock(tmp: Path):
    print("tree lock:")
    from recurvelib.loop.lock import LockHeld, TreeLock
    tree = tmp / "locktree"
    tree.mkdir()
    a = TreeLock(tree)
    a.acquire()
    b = TreeLock(tree)
    try:
        b.acquire()
        ok("second acquire refused", False)
    except LockHeld as e:
        ok("second acquire refused", "second loop" in str(e) or "locked" in str(e))
    holder = b.steal()
    ok("steal evicts and names the holder", holder is not None and holder.pid == os.getpid())
    b.acquire()
    b.release()
    a.release()
    ok("post-steal acquire works", True)


def test_park(tmp: Path):
    print("parked store:")
    t = make_target(tmp)
    suite = t / "claims" / "alpha"
    write_probe(suite / "probes" / "p1.sh", ALWAYS_RED)
    write_probe(suite / "probes" / "p2.sh", ALWAYS_RED)
    (suite / "gaps.yaml").write_text(
        draft_entry("P-1", "p1.sh", "1") + draft_entry("P-2", "p2.sh", "2"))

    r = cli(t, "next")
    ok("next recommends P-1 before parking", "▸ P-1" in r.stdout)
    r = cli(t, "park", "P-1", "--reason", "needs design spike",
            "--attempt", "tried direct fix", "--observed", "probe still RED: ours=nothing")
    ok("park records reason", r.returncode == 0)
    r = cli(t, "next")
    ok("parked gap excluded from triage", "▸ P-2" in r.stdout and "parked" in r.stdout)
    r = cli(t, "park")
    ok("attempt journal listed (observations, never conclusions)",
       "needs design spike" in r.stdout and "tried direct fix" in r.stdout)
    r = cli(t, "park", "P-1", "--unpark")
    ok("unpark releases", r.returncode == 0)
    r = cli(t, "next")
    ok("unparked gap triages again", "▸ P-1" in r.stdout)


def test_init_blank(tmp: Path):
    print("init (blank):")
    t = tmp / "fresh"
    t.mkdir()
    r = run(CLI + ["init", "--target", str(t), "--name", "fresh", "--suite", "core"])
    ok("init scaffolds", r.returncode == 0, r.stdout + r.stderr)
    for f in [".recurve/recurve.toml", ".recurve/RUN.md", ".recurve/RUN-AUTO.md",
              ".recurve/REVIEW.md", ".recurve/TROUBLESHOOTING.md", ".recurve/README.md",
              ".recurve/workflows/burndown.sh", ".recurve/workflows/burndown.js",
              ".recurve/workflows/burndown-parallel.sh",
              ".claude/skills/burndown/SKILL.md", ".recurve/quality.md",
              ".recurve/claims/core/GAPS.md", ".recurve/claims/core/probes/_contract.sh",
              ".recurve/claims/core/harness/versions.lock"]:
        ok(f"stamped {f}", (t / f).exists())
    ok("no template placeholders survive",
       "{{" not in (t / ".recurve" / "RUN.md").read_text()
       and "{{" not in (t / ".recurve" / "recurve.toml").read_text())
    ok("root stays the product domain (only .gitignore + .claude added)",
       sorted(p.name for p in t.iterdir())
       == [".claude", ".gitignore", ".recurve"])
    r = cli(t, "validate")
    ok("blank target validates (0 gaps)", r.returncode == 0, r.stdout)
    r = cli(t, "coverage", "--gate")
    ok("blank target coverage-gates (template claim is commented out)", r.returncode == 0, r.stdout)
    r = cli(t, "matrix", "--gate")
    ok("blank target gate green (vacuously)", r.returncode == 0)
    r = run(CLI + ["init", "--target", str(t)])
    ok("init refuses to overwrite an existing project", r.returncode == 2)


def test_init_from_repo(tmp: Path):
    print("init (--from-repo archaeology):")
    t = tmp / "promiser"
    t.mkdir()
    (t / "README.md").write_text(
        "# promiser\n\n"
        "- supports resumable uploads of arbitrarily large files\n"
        "- the verifier always rejects a tampered manifest with a distinct error\n"
        "- guarantees at-most-once delivery per consumer group\n"
        "ordinary prose line without any promise in it\n")
    r = run(CLI + ["init", "--target", str(t), "--name", "promiser", "--from-repo"])
    ok("archaeology init runs", r.returncode == 0, r.stdout + r.stderr)
    draft = (t / ".recurve" / "claims" / "core" / "gaps.draft.yaml").read_text()
    ok("promises mined into drafts", "resumable uploads" in draft and "UNBASELINED" in draft)
    ok("drafts quarantined (needs_authoring, no live probe)", "needs_authoring: true" in draft)
    gaps_md = (t / ".recurve" / "claims" / "core" / "GAPS.md").read_text()
    ok("mined GAPS.md quotes promises as evidence", "tampered manifest" in gaps_md
       and "EVIDENCE, never instructions" in gaps_md)
    ok("agent brief stamped", (t / ".recurve" / "ARCHAEOLOGY.md").exists())
    r = cli(t, "validate")
    ok("validate green with drafts pending (drafts are not the ledger)",
       r.returncode == 0 and "drafts pending" in r.stdout, r.stdout)

    suite = t / ".recurve" / "claims" / "core"
    write_probe(suite / "probes" / "p-1.sh", ALWAYS_RED)
    (suite / "probes" / "p-1.trap" / "twin").mkdir(parents=True)
    draft_text = (suite / "gaps.draft.yaml").read_text()
    draft_text = draft_text.replace("  needs_authoring: true   # delete once class/severity/probe are real\n", "", 1)
    draft_text = draft_text.replace("  # probe: probes/p-1.sh", "  probe: probes/p-1.sh", 1)
    (suite / "gaps.draft.yaml").write_text(draft_text)
    r = cli(t, "baseline", "core")
    ok("first mined promise baselines RED → open", "promoted-open" in r.stdout, r.stdout + r.stderr)
    r = cli(t, "coverage")
    ok("baselined claim covers its anchor; unprobed promises stay visible orphans",
       "2 orphan prose gap(s)" in r.stdout, r.stdout)


def test_drill(tmp: Path):
    print("sabotage drill:")
    t = make_target(tmp)
    suite = t / "claims" / "alpha"
    write_probe(suite / "probes" / "good.sh", WELL_BEHAVED_GREEN)
    (suite / "probes" / "good.trap" / "twin").mkdir(parents=True)
    write_probe(suite / "probes" / "gamed.sh", ALWAYS_GREEN_GAMED)
    (suite / "probes" / "gamed.trap" / "twin").mkdir(parents=True)
    (suite / "gaps.yaml").write_text(
        draft_entry("D-1", "good.sh", "1").replace("status: open", "status: closed"))
    r = cli(t, "drill")
    ok("drill clean when guards still catch their defects",
       r.returncode == 0 and "drill clean" in r.stdout, r.stdout)
    (suite / "gaps.yaml").write_text(
        draft_entry("D-1", "good.sh", "1").replace("status: open", "status: closed")
        + draft_entry("D-2", "gamed.sh", "2").replace("status: open", "status: closed"))
    r = cli(t, "drill")
    ok("drill catches a guard that would bless its own defect",
       r.returncode == 1 and "DRILL FAILED" in r.stdout, r.stdout)
    ok("drill leaves no trace (no records, no ledger writes)",
       not (t / ".recurve" / "state" / "records.jsonl").exists()
       and "D-2" in (suite / "gaps.yaml").read_text())


BURNDOWN_PROBE = '''DIR="${TRAP_FIXTURE:-../../..}"
if [ -f "$DIR/feature.txt" ]; then echo "feature present"; exit 0; fi
echo "ours=missing oracle=feature.txt"; exit 1'''

FAKE_AGENT = '''#!/usr/bin/env bash
cat > /dev/null   # consume the prompt; a real agent would read it
touch feature.txt
python3 - "$PWD/.recurve/claims/core/gaps.yaml" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read().replace("status: open", "status: closed")
open(p, "w").write(s)
EOF
cat > "$RECURVE_RESULT_FILE" <<'EOF'
{"schema_version": "1.0.0", "project": "burner", "cycle": "close-feature",
 "gap": "B-1", "status": "closed", "attempts": 1, "wall_clock_s": 1.0,
 "net_new_gaps": 0, "summary": "created the feature and promoted the gap",
 "verdicts_before": {"green": 0, "red": 1}, "verdicts_after": {"green": 1, "red": 0}}
EOF
'''

DEAD_AGENT = '''#!/usr/bin/env bash
cat > /dev/null
exit 0   # writes no record: the loop must count a failed cycle, not hang
'''


def _burndown_target(tmp: Path) -> Path:
    t = tmp / "burner"
    t.mkdir(parents=True)
    r = run(CLI + ["init", "--target", str(t), "--name", "burner", "--suite", "core"])
    assert r.returncode == 0, r.stderr
    suite = t / ".recurve" / "claims" / "core"
    write_probe(suite / "probes" / "b.sh", BURNDOWN_PROBE)
    (suite / "probes" / "b.trap" / "twin").mkdir(parents=True)
    (suite / "gaps.yaml").write_text(
        "- id: B-1\n  title: 'feature exists'\n  class: missing-surface\n"
        "  status: open\n  severity: feature\n  reads: none\n  covers: []\n"
        "  smallest_fix: create the feature\n  probe: probes/b.sh\n")
    return t


def test_burndown_loop(tmp: Path):
    print("burndown shell loop (fake agent):")
    t = _burndown_target(tmp)
    agent = t / "fake_agent.sh"
    agent.write_text(FAKE_AGENT)
    agent.chmod(0o755)
    env = {"AGENT_CMD": f"bash {agent}", "RECURVE_BIN": f"{sys.executable} {RECURVE_DIR / 'recurve'}",
           "CAP": "4"}
    r = run(["bash", str(t / ".recurve" / "workflows" / "burndown.sh")], cwd=t, env=env)
    ok("loop closes the gap and verifies via the gate",
       "gate green" in r.stdout, r.stdout + r.stderr)
    ok("loop halts on no-work-left", "no work left" in r.stdout)
    ok("run record appended and schema-valid", (t / ".recurve" / "state" / "records.jsonl").exists()
       and '"status": "closed"' in (t / ".recurve" / "state" / "records.jsonl").read_text())
    ok("loop exits clean", r.returncode == 0)

    print("burndown watchdogs (dead agent):")
    t2 = _burndown_target(tmp / "w")
    agent2 = t2 / "dead_agent.sh"
    agent2.write_text(DEAD_AGENT)
    agent2.chmod(0o755)
    env = {"AGENT_CMD": f"bash {agent2}", "RECURVE_BIN": f"{sys.executable} {RECURVE_DIR / 'recurve'}",
           "CAP": "5", "MAX_FAILS": "2"}
    r = run(["bash", str(t2 / ".recurve" / "workflows" / "burndown.sh")], cwd=t2, env=env)
    ok("recordless agent counts as failed cycle, not a hang",
       "no readable record" in r.stdout, r.stdout)
    ok("consecutive-failure watchdog halts the loop",
       "2 consecutive failures" in r.stdout or "consecutive failures" in r.stdout)


FIXTURE_PRD = """\
# Uploader — product spec

## Core upload
Users must be able to upload files up to 5 GB and see a progress bar.
The system must resume interrupted uploads without re-sending completed parts.
Uploads should complete quickly on a typical connection.

## Access
Only authenticated users may create uploads; tokens must expire after a session.

## Niceties
The dashboard could show a weekly usage summary.
This paragraph has no requirement in it at all.
"""


def test_claimify(tmp: Path):
    print("claimify (--from-prd):")
    t = tmp / "greenfield"
    t.mkdir()
    prd = tmp / "spec.md"
    prd.write_text(FIXTURE_PRD)
    r = run(CLI + ["init", "--target", str(t), "--name", "uploader",
                   "--from-prd", str(prd), "--suite", "claims"])
    ok("claimify init runs", r.returncode == 0, r.stdout + r.stderr)
    draft = (t / ".recurve" / "claims" / "claims" / "gaps.draft.yaml").read_text()
    ok("must → feature severity", "severity: feature" in draft)
    ok("should → friction", "severity: friction" in draft)
    ok("could → cosmetic", "severity: cosmetic" in draft)
    ok("security-relevant defaults review-gated (only a human downgrades)",
       "class: security-tradeoff" in draft and "authenticated" in draft)
    ok("every claim carries an adversarial twin", draft.count("adversarial_twin:") >= 5)
    ok("scaffolding gaps ordered first (the burndown IS the build)",
       "BOOT-1" in draft and draft.index("BOOT-1") < draft.index("-1\n" if "-1\n" in draft else "claims"))
    adj = (t / ".recurve" / "ADJUDICATE.md").read_text()
    ok("ambiguity became a question, not a guess ('quickly')",
       "DECIDED: (pending)" in adj and "quickly" in adj.lower())
    ok("human-review default messaged", "await your review" in r.stdout)
    r = run(CLI + ["--config", str(t / ".recurve" / "recurve.toml"), "baseline", "claims"])
    ok("baseline warns on unresolved forks", "unresolved fork" in r.stdout, r.stdout)
    ok("claimified drafts parse cleanly (no traceback, honest exit)",
       r.returncode in (0, 1) and "Traceback" not in r.stderr, r.stderr[-300:])

    t2 = tmp / "greenfield2"
    t2.mkdir()
    r = run(CLI + ["init", "--target", str(t2), "--name", "uploader2",
                   "--from-prd", str(prd), "--no-review"])
    ok("--no-review prints the safety trade message", "trading safety for speed" in r.stdout)


def test_adjudicate(tmp: Path):
    print("adjudicate (three synchronized places) + retire:")
    t = make_target(tmp)
    suite = t / "claims" / "alpha"
    write_probe(suite / "probes" / "j.sh", ALWAYS_RED)
    (suite / "probes" / "j.trap" / "twin").mkdir(parents=True)
    (suite / "gaps.yaml").write_text(
        "# ledger header comment that must survive the splice\n"
        + draft_entry("J-1", "j.sh", "1")
        + draft_entry("J-2", "j.sh", "2"))
    r = cli(t, "adjudicate", "J-1", "--decision",
            "conform to the stricter reading; the permissive variant is rejected")
    ok("adjudicate runs", r.returncode == 0, r.stdout + r.stderr)
    ledger = (suite / "gaps.yaml").read_text()
    ok("ledger: smallest_fix opens with DECIDED + date",
       "DECIDED 20" in ledger and "NOT an acceptable close" in ledger)
    ok("ledger: splice preserved comments and the sibling entry",
       "must survive the splice" in ledger and "J-2" in ledger)
    ok("prose: Adjudicated note under the covered section",
       "Adjudicated (20" in (suite / "GAPS.md").read_text())
    ok("probe: POLICY marker appended",
       "POLICY (DECIDED 20" in (suite / "probes" / "j.sh").read_text())
    r = cli(t, "validate")
    ok("ledger still parses after the splice", r.returncode == 0, r.stdout)

    r = cli(t, "adjudicate", "J-2", "--retire", "--decision",
            "superseded by the v2 ingestion claim")
    ok("retire runs", r.returncode == 0, r.stdout + r.stderr)
    ledger = (suite / "gaps.yaml").read_text()
    ok("retire: entry removed, sibling intact", "J-2" not in ledger and "J-1" in ledger)
    ok("retire: tombstone in prose", "Retired 20" in (suite / "GAPS.md").read_text())
    r = cli(t, "validate")
    ok("ledger still parses after retirement", r.returncode == 0)


def test_receipts(tmp: Path):
    print("evidence receipts:")
    t = make_target(tmp)
    suite = t / "claims" / "alpha"
    write_probe(suite / "probes" / "r.sh", WELL_BEHAVED_GREEN)
    (suite / "probes" / "r.trap" / "twin").mkdir(parents=True)
    (suite / "gaps.yaml").write_text(
        draft_entry("R-1", "r.sh", "1").replace("status: open", "status: closed"))
    (suite / "harness").mkdir()
    (suite / "harness" / "versions.lock").write_text("peer-oracle 9.9.9\n")
    r = cli(t, "matrix", "--receipts")
    ok("matrix emits chained receipts", "receipts: 1 verdict" in r.stdout, r.stdout)
    r = cli(t, "matrix", "--receipts")
    r = cli(t, "receipts", "verify")
    ok("chain verifies (2 links)", r.returncode == 0 and "every chain holds" in r.stdout, r.stdout)
    r = cli(t, "receipts", "list")
    ok("receipts pin the oracle and the verdict", "GREEN" in r.stdout)
    chain_file = t / ".recurve" / "state" / "receipts" / "alpha.jsonl"
    lines = chain_file.read_text().splitlines()
    tampered = json.loads(lines[0])
    tampered["verdict"] = "RED"
    lines[0] = json.dumps(tampered, sort_keys=True)
    chain_file.write_text("\n".join(lines) + "\n")
    r = cli(t, "receipts", "verify")
    ok("a tampered receipt breaks the chain loudly",
       r.returncode == 1 and "edited it after the fact" in r.stdout, r.stdout)

    print("pluggable signer:")
    t2 = make_target(tmp / "s")
    (t2 / "recurve.toml").write_text((t2 / "recurve.toml").read_text()
                                     + '\n[receipts]\nsigner = "python3 -c \'import sys; print(\\"SIGNED:\\" + sys.stdin.read().strip())\'"\n')
    suite2 = t2 / "claims" / "alpha"
    write_probe(suite2 / "probes" / "r.sh", WELL_BEHAVED_GREEN)
    (suite2 / "probes" / "r.trap" / "twin").mkdir(parents=True)
    (suite2 / "gaps.yaml").write_text(
        draft_entry("R-1", "r.sh", "1").replace("status: open", "status: closed"))
    cli(t2, "matrix", "--receipts")
    receipt = json.loads((t2 / ".recurve" / "state" / "receipts" / "alpha.jsonl").read_text().splitlines()[0])
    ok("signer countersigns self_sha256 (recurve defines the receipt, never the scheme)",
       receipt.get("signature") == "SIGNED:" + receipt["self_sha256"], str(receipt))
    r = cli(t2, "receipts", "verify")
    ok("signed chain still verifies", r.returncode == 0)


def test_stats(tmp: Path):
    print("stats (the dataset):")
    t = make_target(tmp)
    rec = {"schema_version": "1.0.0", "project": "scratch", "cycle": "c1",
           "gap": "S-1", "class": "missing-surface", "status": "closed",
           "attempts": 2, "wall_clock_s": 120.0, "net_new_gaps": 0,
           "regressions_caught": 1,
           "verdicts_before": {"green": 0, "red": 1}, "verdicts_after": {"green": 1, "red": 0}}
    r = cli(t, "record", "append", stdin=json.dumps(rec))
    ok("record append validates and stores", r.returncode == 0, r.stdout + r.stderr)
    rec2 = dict(rec, cycle="c2", gap="S-2", status="parked", regressions_caught=0)
    cli(t, "record", "append", stdin=json.dumps(rec2))
    bad = dict(rec, status="probably-fine")
    r = cli(t, "record", "append", stdin=json.dumps(bad))
    ok("malformed record rejected (the dataset stays clean)", r.returncode == 1)
    r = cli(t, "stats")
    ok("stats renders close rate by class",
       "missing-surface" in r.stdout and "50%" in r.stdout, r.stdout)
    ok("stats names the by-product (self-grading tasks, gate-as-oracle)",
       "self-grading tasks" in r.stdout and "1 regression(s) caught" in r.stdout)


def test_pack(tmp: Path):
    print("claim packs:")
    t = make_target(tmp)
    r = cli(t, "pack", "install", str(RECURVE_DIR / "packs" / "cli-contract"),
            "--suite", "cli")
    ok("pack installs as drafts + registers the suite", r.returncode == 0, r.stdout + r.stderr)
    ok("ceremony preserved (drafts only, no ledger)",
       (t / "claims" / "cli" / "gaps.draft.yaml").exists()
       and not (t / "claims" / "cli" / "gaps.yaml").exists())
    r = cli(t, "baseline", "cli", env={"PACK_CLI": sys.executable})
    ok("pack claims baseline GREEN→closed against a conforming CLI (traps seen RED)",
       r.stdout.count("promoted-closed") == 3, r.stdout + r.stderr)
    r = cli(t, "matrix", "--gate", env={"PACK_CLI": sys.executable})
    ok("installed pack guards under the gate", r.returncode == 0, r.stdout)
    r = cli(t, "coverage")
    ok("pack prose anchors covered (all orphans belong to the scratch suite)",
       "4 orphan prose gap(s)" in r.stdout, r.stdout)
    r = cli(t, "pack", "install", str(RECURVE_DIR / "packs" / "cli-contract"), "--suite", "cli")
    ok("packs never overwrite", r.returncode == 2)

    out = tmp / "exported"
    r = cli(t, "pack", "export", "cli", "--out", str(out))
    ok("export demotes observations back to UNBASELINED drafts",
       r.returncode == 0 and "UNBASELINED" in (out / "claims.draft.yaml").read_text())


def test_federation(tmp: Path):
    print("multi-target federation:")
    a = make_target(tmp)
    sa = a / "claims" / "alpha"
    write_probe(sa / "probes" / "a.sh", WELL_BEHAVED_GREEN)
    (sa / "probes" / "a.trap" / "twin").mkdir(parents=True)
    (sa / "gaps.yaml").write_text(
        draft_entry("A-1", "a.sh", "1").replace("status: open", "status: closed"))
    bdir = tmp / "b"
    bdir.mkdir()
    b = make_target(bdir)
    sb = b / "claims" / "alpha"
    write_probe(sb / "probes" / "b.sh", ALWAYS_RED)
    (sb / "probes" / "b.trap" / "twin").mkdir(parents=True)
    (sb / "gaps.yaml").write_text(
        draft_entry("B-9", "b.sh", "1").replace("status: open", "status: closed"))  # regression!
    r = cli(a, "matrix", "--gate")
    ok("target A alone gates green", r.returncode == 0)
    r = cli(a, "matrix", "--gate", "--federate", str(b / "recurve.toml"))
    ok("federation: B's regression fails the combined gate",
       r.returncode == 1 and "federated" in r.stdout and "REGRESSED" in r.stdout, r.stdout)


def main():
    tests = [test_baseline_ceremony, test_validate_traps, test_lock, test_park,
             test_init_blank, test_init_from_repo, test_drill, test_burndown_loop,
             test_claimify, test_adjudicate, test_receipts, test_stats, test_pack,
             test_federation]
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for i, t in enumerate(tests):
            d = root / f"t{i}"
            d.mkdir()
            t(d)
    print(f"PHASE TESTS OK ({PASSED} assertions)")


if __name__ == "__main__":
    main()

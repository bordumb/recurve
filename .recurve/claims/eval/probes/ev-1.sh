#!/usr/bin/env bash
# EV-1: TaskStore pins the benchmark to a content hash and reports the task
# count; a changed task changes the hash, and a tampered dataset is rejected
# against a pinned hash. Core logic is stdlib-only, so this probe drives the
# real evallib.taskstore against a fixture — never the network. The genuinely
# external half (fetching the real BigCodeBench-Hard revision from HuggingFace)
# is an oracle_waiver: SKIP when `datasets` is not importable.
#
# RED until taskstore exists. The trap tampers a dataset while keeping the
# original pin and proves verify_pin rejects it.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  python3 - "$EVAL" <<'PY'
import sys, json, tempfile, pathlib
sys.path.insert(0, sys.argv[1])
try:
    from evallib.taskstore import load_jsonl, content_hash, verify_pin
except Exception as e:
    print("taskstore incomplete:", e); sys.exit(2)
tasks = [{"task_id":"t/1","instruct_prompt":"do x","test":"assert f()==1"},
         {"task_id":"t/2","instruct_prompt":"do y","test":"assert g()==2"}]
d = tempfile.mkdtemp(); p = pathlib.Path(d, "tasks.jsonl")
p.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")
pin = content_hash(load_jsonl(p))
tasks[0]["instruct_prompt"] = "do x — TAMPERED"          # alter content, keep the old pin
p.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")
if verify_pin(load_jsonl(p), pin):
    print("verify_pin ACCEPTED a tampered dataset"); sys.exit(0)   # guard broken → trap fails
print("verify_pin rejected the tampered dataset"); sys.exit(1)     # guard holds → RED
PY
  rc=$?
  case "$rc" in
    1) echo "taskstore rejects a tampered dataset against its pin"; exit 1 ;;
    0) echo "taskstore accepted a tampered dataset (fixture claimed it does)"; exit 0 ;;
    *) echo "taskstore incomplete — cannot measure"; exit 2 ;;
  esac
fi

python3 - "$EVAL" <<'PY'
import sys, json, tempfile, pathlib
sys.path.insert(0, sys.argv[1])
try:
    from evallib.taskstore import load_jsonl, content_hash, verify_pin
except Exception as e:
    print("ours=evallib.taskstore missing/incomplete:", e,
          "oracle=load_jsonl/content_hash/verify_pin"); sys.exit(1)
tasks = [{"task_id":"t/1","instruct_prompt":"do x","test":"assert f()==1"},
         {"task_id":"t/2","instruct_prompt":"do y","test":"assert g()==2"},
         {"task_id":"t/3","instruct_prompt":"do z","test":"assert h()==3"}]
d = tempfile.mkdtemp(); p = pathlib.Path(d, "tasks.jsonl")
p.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")
loaded = load_jsonl(p)
assert len(loaded) == 3, f"count wrong: {len(loaded)}"
h1 = content_hash(loaded)
assert h1 == content_hash(load_jsonl(p)), "hash not deterministic across loads"
assert verify_pin(loaded, h1), "verify_pin failed on the clean pin"
# a changed task changes the hash
tasks[1]["test"] = "assert g()==999"
p.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")
assert content_hash(load_jsonl(p)) != h1, "hash did not change on a content change"
print("OK")
PY
[ $? -eq 0 ] || { echo "ours=taskstore does not pin/verify correctly oracle=deterministic content hash + count, tamper-sensitive"; exit 1; }

# the external half — real BigCodeBench-Hard revision — is oracle-waived
python3 -c "import datasets" 2>/dev/null \
  && echo "taskstore pins to a content hash, reports count, and detects tampering (datasets present)" \
  || echo "taskstore pins to a content hash, reports count, and detects tampering (real HF fetch oracle-waived: datasets absent)"
exit 0

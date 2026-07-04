#!/usr/bin/env bash
# TK-12: the shipped burndown loops never silently strand a draft backlog.
# The serial template ARMS the next wave (author probes → baseline →
# continue); the parallel and orchestrator twins surface the unarmed
# backlog instead of reporting plain "no work left".
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
TPL="${TRAP_FIXTURE:-$ROOT/templates/workflows}"

SH="$TPL/burndown.sh"
[ -f "$SH" ] || { echo "ours=no burndown.sh shipped oracle=templates/workflows/burndown.sh"; exit 1; }
bash -n "$SH" 2>/dev/null || { echo "ours=burndown.sh does not parse oracle=valid bash"; exit 1; }
for needle in 'arm_wave' 'ARM_WAVES' 'baseline' 'adjudications_pending'; do
  grep -q "$needle" "$SH" \
    || { echo "ours=burndown.sh lacks '$needle' oracle=the serial loop arms waves from gaps.draft.yaml"; exit 1; }
done

PAR="$TPL/burndown-parallel.sh"
if [ -f "$PAR" ]; then
  bash -n "$PAR" 2>/dev/null || { echo "ours=burndown-parallel.sh does not parse oracle=valid bash"; exit 1; }
  grep -q 'drafts' "$PAR" \
    || { echo "ours=burndown-parallel.sh halts blind oracle=it reports the pending draft backlog"; exit 1; }
fi

JS="$TPL/burndown.js"
if [ -f "$JS" ]; then
  grep -q 'ARM_WAVES' "$JS" && grep -q 'arm-wave' "$JS" \
    || { echo "ours=burndown.js halts on no-work-left oracle=it arms the next wave"; exit 1; }
fi

echo "burndown templates arm or surface the draft backlog"; exit 0

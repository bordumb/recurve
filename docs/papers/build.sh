#!/usr/bin/env bash
# Build a Markdown+LaTeX paper in this directory to a typeset PDF.
#
#   ./build.sh                       # builds recurve-framework.md
#   ./build.sh some-other-paper.md   # builds a specific paper
#
# Requires: pandoc + a LaTeX engine (xelatex). See README.md.
set -euo pipefail
cd "$(dirname "$0")"

SRC="${1:-recurve-framework.md}"
[ -f "$SRC" ] || { echo "no such file: $SRC" >&2; exit 1; }
OUT="${SRC%.md}.pdf"

# Attach the bibliography only if one is present next to the papers.
BIB=()
[ -f references.bib ] && BIB=(--citeproc --bibliography=references.bib)

pandoc "$SRC" \
  --from markdown \
  --output "$OUT" \
  --pdf-engine=xelatex \
  --include-in-header=preamble.tex \
  "${BIB[@]}" \
  -V geometry:margin=1in \
  -V fontsize=11pt \
  -V colorlinks=true \
  --highlight-style=tango

echo "wrote $OUT"

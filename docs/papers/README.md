# Papers — build process

This directory holds the recurve papers as **Markdown + LaTeX** source and builds
them to typeset **PDF** with `pandoc` + `xelatex`. The Markdown stays clean; all
the LaTeX machinery (diagrams, code figures, fonts, citations) lives in a shared
preamble and the build script.

## Quick start

```bash
./build.sh                       # builds recurve-framework.md -> .pdf
./build.sh some-other-paper.md   # builds a specific paper
```

That's it. The script `cd`s into this directory, so it works from anywhere.

## Requirements

| Tool | Why | Install (macOS) |
|---|---|---|
| **pandoc** ≥ 3 | Markdown → LaTeX, citation processing | `brew install pandoc` |
| **xelatex** | PDF engine (Unicode + TikZ) | `brew install --cask mactex-no-gui` |

Any TeX Live / MacTeX gives `xelatex` plus the packages the preamble loads
(`tikz`, `fancyvrb`, `fontspec`, `amsmath`, `booktabs`, `microtype`). A
self-contained alternative is `tectonic` (`brew install tectonic`); to use it,
change `--pdf-engine=xelatex` to `--pdf-engine=tectonic` in `build.sh`.

## What the build does

`build.sh` runs, in effect:

```bash
pandoc PAPER.md \
  --from markdown \
  --output PAPER.pdf \
  --pdf-engine=xelatex \
  --include-in-header=preamble.tex \
  --citeproc --bibliography=references.bib \
  -V geometry:margin=1in -V fontsize=11pt -V colorlinks=true \
  --highlight-style=tango
```

Each piece earns its place:

- **`--pdf-engine=xelatex`** — renders the TikZ architecture diagrams and any
  Unicode natively; `pdflatex` would need every non-ASCII glyph mapped by hand.
- **`--include-in-header=preamble.tex`** — the design system. Typography is
  **STIX Two Text + STIX Two Math** (the OpenType family designed for scientific
  publishing, shipped with TeX Live) via `fontspec`/`unicode-math`, with TeX Gyre
  Heros for sans and Menlo for monospace — all behind `\IfFontExistsTF` guards so
  other machines fall back silently. It also styles headings (`titlesec`, compact
  with slate-colored numbers), captions (`caption`), lists (`enumitem`, tightened),
  running heads (`fancyhdr`), link colors, `fancyvrb` code frames, and the
  **figure design system**: pastel ownership zones (`zonepanel`, TikZ `zone`
  style), dashed color-coded component boxes with `fontawesome5` icons (`comp`,
  `compsolid`, `chip` TikZ styles; `panelbox` for code panels), and `flow` arrows
  that inherit their component's accent color. Keeping this in a file (rather
  than the Markdown's YAML `header-includes`) avoids fragile multi-line YAML.
- **`--citeproc --bibliography=references.bib`** — turns the in-text `[@key]`
  markers into rendered author–date citations and generates the formatted
  **References** section. Only cited keys appear. Edit `references.bib` (BibTeX)
  to add or fix a reference; the build attaches it automatically if present.
- **`-V geometry / fontsize / colorlinks`** — 1-inch margins, 10 pt (standard
  for academic papers, and what keeps the paper inside its 10-page budget),
  colored hyperlinks — a clean single-column academic look.

**Why not Typst / Quarto?** Typst produces beautiful output fast, but the papers'
architecture figures are TikZ and the side-by-side code figures are raw LaTeX —
porting them buys no quality for real cost. Quarto wraps this same
pandoc-to-LaTeX path. The pragmatic optimum is pandoc + xelatex with a real
design system in `preamble.tex`, which is what this directory does.

## Files

| File | Role |
|---|---|
| `recurve-framework.md` | paper source (Markdown + LaTeX math, TikZ figures, `[@cite]`s) |
| `recurve-framework.pdf` | the built output |
| `references.bib` | BibTeX bibliography (verified metadata) |
| `preamble.tex` | shared LaTeX preamble (packages + `\tikzset`) |
| `build.sh` | one-command build |
| `2506.13131v1.pdf`, `2813885.2737977.pdf` | external reference PDFs (source material, not built here) |

## Adding a new paper

1. Write `your-paper.md` here. Use `$...$` / `$$...$$` for math, `[@key]` for
   citations (add the entry to `references.bib`), and — for a diagram or a
   side-by-side code figure — a raw LaTeX `\begin{figure}...\end{figure}` block
   (see the Figure in §1.3 and the TikZ figures in §3 of `recurve-framework.md`
   for copyable patterns).
2. `./build.sh your-paper.md`.

New packages a paper needs go in `preamble.tex` so every paper shares one setup.

## Notes

- **Menlo is macOS-only.** The preamble guards with `\IfFontExistsTF`, so on other
  systems the build silently falls back to the default monospace font — no error.
- **Benign warning.** `LaTeX Warning: 'h' float specifier changed to 'ht'` is
  normal float placement, not a failure.
- **Raw-LaTeX figures must not contain blank lines** — pandoc would split the
  block. Use `\par\vspace{...}` for vertical breaks inside a figure (as the
  §1.3 figure does).

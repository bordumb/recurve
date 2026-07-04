# _toy.sh — shared toy-project builder for the TK-30..TK-36 probes.
# Sourced by probes; builds a minimal recurve project the REAL engine runs
# against, in a temp dir the caller owns. Nothing here touches the repo.

toy_init() {  # $1=dir  — a project with one suite `s`
  local d="$1"
  mkdir -p "$d/claims/s/probes" "$d/.recurve/state"
  : > "$d/claims/s/GAPS.md"
  : > "$d/claims/s/gaps.yaml"
  cat > "$d/recurve.toml" <<'TOML'
[project]
name = "toy"
label = "suite"
default_reads = "none"
cycles_dir = "claims/cycles"
schema = "1"

[target]
tree = "."

[gate]
traps = "required"
quality = "pre-launch"

[reads.none]
method = "none"

[suites.s]
dir = "claims/s"
TOML
}

toy_conf() {  # $1=dir $2=extra-toml-line(s) — append raw config (e.g. [drill] knobs)
  printf '%s\n' "$2" >> "$1/recurve.toml"
}

toy_claim() {  # $1=dir $2=id $3=trap: yes|waiver|none ; probe body on stdin
  local d="$1" id="$2" trap="$3" uid
  uid="$(printf '%s' "$id" | tr '[:lower:]' '[:upper:]')"
  cat > "$d/claims/s/probes/$id.sh"
  chmod +x "$d/claims/s/probes/$id.sh"
  printf '## %s\n\ntoy claim.\n\n' "$uid" >> "$d/claims/s/GAPS.md"
  {
    printf -- '- id: %s\n' "$uid"
    printf '  title: toy claim %s\n' "$id"
    printf '  class: missing-surface\n  status: closed\n  severity: feature\n'
    printf '  reads: none\n  covers: ["%s"]\n  evidence: ["x:1"]\n' "$uid"
    printf '  observed: GREEN by construction\n  smallest_fix: none\n'
    printf '  probe: probes/%s.sh\n' "$id"
    [ "$trap" = waiver ] && printf '  trap_waiver: fixture\n'
  } >> "$d/claims/s/gaps.yaml"
  if [ "$trap" = yes ]; then
    mkdir -p "$d/claims/s/probes/$id.trap/curated"
    printf 'curated counterexample\n' > "$d/claims/s/probes/$id.trap/curated/curated"
  fi
}

toy_fuzz_gen() {  # $1=dir $2=id ; generator body on stdin (gets FUZZ_OUT, FUZZ_N)
  local d="$1" id="$2"
  cat > "$d/claims/s/probes/$id.fuzz.sh"
  chmod +x "$d/claims/s/probes/$id.fuzz.sh"
}

toy_record() {  # $1=dir $2=gap $3=status $4=attempts $5=run_id $6=cycle
  printf '{"schema_version":"1.0.0","project":"toy","run_id":"%s","cycle":"%s","gap":"%s","suite":"s","class":"missing-surface","severity":"feature","status":"%s","attempts":%s,"files_touched":["f.txt"],"net_new_gaps":0,"regressions_caught":0,"summary":"toy cycle","wall_clock_s":10}\n' \
    "$5" "$6" "$2" "$3" "$4" >> "$1/.recurve/state/records.jsonl"
}

toy_oracle_waiver() {  # $1=dir $2=id $3=text — declare oracle_waiver on that claim (F1)
  local d="$1" id="$2" text="$3"
  python3 - "$d/claims/s/gaps.yaml" "$id" "$text" <<'PY'
import sys, pathlib
path, gid, text = sys.argv[1], sys.argv[2], sys.argv[3]
p = pathlib.Path(path)
marker = f"probe: probes/{gid}.sh\n"
content = p.read_text()
assert content.count(marker) == 1, f"expected exactly one {marker!r}"
p.write_text(content.replace(marker, marker + f"  oracle_waiver: {text}\n", 1))
PY
}

toy_reference() {  # $1=dir $2=id $3=ref-filename(relative to probes/) — declare a reference oracle (F2.4)
  local d="$1" id="$2" ref="$3"
  python3 - "$d/claims/s/gaps.yaml" "$id" "$ref" <<'PY'
import sys, pathlib
path, gid, ref = sys.argv[1], sys.argv[2], sys.argv[3]
p = pathlib.Path(path)
marker = f"probe: probes/{gid}.sh\n"
content = p.read_text()
assert content.count(marker) == 1, f"expected exactly one {marker!r}"
p.write_text(content.replace(marker, marker + f"  reference: probes/{ref}\n", 1))
PY
}

toy_iso_gen() {  # $1=dir $2=id ; generator body on stdin (gets ISO_OUT, ISO_N)
  local d="$1" id="$2"
  cat > "$d/claims/s/probes/$id.iso.sh"
  chmod +x "$d/claims/s/probes/$id.iso.sh"
}

"""Claim packs — claims as a distributable unit, the way packages are.

A pack is a versioned bundle of claim drafts + probes + traps (+ prose) for a
recurring claim shape (CLI contract, perf SLO, API conformance…). Installing
a pack NEVER touches the ledger: entries arrive as drafts and walk through
the baseline ceremony like anything else — a pack is someone else's
intentions, and intentions become observations only by being measured here.
"""

from __future__ import annotations

import shutil
import tarfile
import time
import tomllib
from pathlib import Path

import yaml

from recurvelib.core.config import Config


class PackError(ValueError):
    pass


def export_pack(config: Config, suite: str, out: Path, version: str = "0.1.0") -> Path:
    """Bundle a suite's claims as a pack: ledger entries demoted back to
    drafts (UNBASELINED — the receiving project must measure for itself)."""
    sc = config.suite_for(suite)
    ledger_path = sc.dir / "gaps.yaml"
    if not ledger_path.exists():
        raise PackError(f"{suite} has no gaps.yaml to export")
    entries = yaml.safe_load(ledger_path.read_text()) or []

    staging = out if out.suffix not in (".tgz", ".gz") else out.with_suffix("").with_suffix("")
    if staging.exists():
        raise PackError(f"{staging} exists — packs never overwrite")
    (staging / "probes").mkdir(parents=True)

    drafts = []
    for e in entries:
        d = dict(e)
        original = d.pop("observed", "")
        d["status"] = "open"
        d["observed"] = (f"UNBASELINED — imported from pack; measure locally. "
                         f"Origin observation: {original[:140]}")
        drafts.append(d)
    (staging / "claims.draft.yaml").write_text(
        "# Pack drafts — intentions until YOUR baseline measures them.\n"
        + yaml.safe_dump(drafts, sort_keys=False, allow_unicode=True, width=88))

    probes_dir = sc.dir / "probes"
    if probes_dir.is_dir():
        for p in probes_dir.iterdir():
            if p.is_file():
                shutil.copy2(p, staging / "probes" / p.name)
            elif p.is_dir() and p.name.endswith(".trap"):
                shutil.copytree(p, staging / "probes" / p.name)
    if (sc.dir / "GAPS.md").exists():
        shutil.copy2(sc.dir / "GAPS.md", staging / "GAPS.md")

    (staging / "pack.toml").write_text(
        f'[pack]\nname = "{suite}"\nversion = "{version}"\n'
        f'exported_at = "{time.strftime("%Y-%m-%d")}"\n'
        f'origin_project = "{config.name}"\n'
        f'entries = {len(drafts)}\n')

    if out.suffix in (".tgz", ".gz"):
        with tarfile.open(out, "w:gz") as tf:
            tf.add(staging, arcname=staging.name)
        shutil.rmtree(staging)
        return out
    return staging


def install_pack(config: Config, pack_path: Path, suite: str) -> list[str]:
    """Unpack into claims/<suite>/ as DRAFTS and register the suite in
    recurve.toml. The ceremony stays the only door into the ledger."""
    notes: list[str] = []
    src = pack_path
    tmp_extract = None
    if pack_path.is_file():
        tmp_extract = config.state_dir / "pack-extract"
        if tmp_extract.exists():
            shutil.rmtree(tmp_extract)
        with tarfile.open(pack_path) as tf:
            tf.extractall(tmp_extract, filter="data")
        inner = [p for p in tmp_extract.iterdir() if p.is_dir()]
        if len(inner) != 1:
            raise PackError(f"{pack_path}: expected one pack directory inside the archive")
        src = inner[0]
    if not (src / "pack.toml").exists():
        raise PackError(f"{src}: not a pack (no pack.toml)")
    meta = tomllib.loads((src / "pack.toml").read_text()).get("pack", {})

    if suite in config.suites:
        raise PackError(f"suite {suite!r} already configured — packs never overwrite")
    dest = config.assets_dir / "claims" / suite
    if dest.exists():
        raise PackError(f"{dest} exists — packs never overwrite")
    dest.mkdir(parents=True)
    if (src / "GAPS.md").exists():
        shutil.copy2(src / "GAPS.md", dest / "GAPS.md")
    shutil.copytree(src / "probes", dest / "probes")
    shutil.copy2(src / "claims.draft.yaml", dest / "gaps.draft.yaml")

    # Appending a [suites.*] table at EOF is TOML-safe and preserves the file.
    rel = f".recurve/claims/{suite}" if config.contained else f"claims/{suite}"
    with config.source_file.open("a") as f:
        f.write(f'\n# installed from pack {meta.get("name", "?")} v{meta.get("version", "?")}\n'
                f'[suites.{suite}]\ndir = "{rel}"\nrebuild = ""\n')
    notes.append(f"installed pack {meta.get('name')} v{meta.get('version')} "
                 f"({meta.get('entries', '?')} draft claims) into claims/{suite}/")
    notes.append(f"drafts only — review them, set any PACK_* env/config the probes "
                 f"document, then run baseline {suite} (the ceremony is the only door "
                 f"into the ledger)")
    if tmp_extract is not None:
        shutil.rmtree(tmp_extract)
    return notes

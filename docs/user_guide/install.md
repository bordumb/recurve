# Installation

## System Requirements

| Requirement | Minimum |
|-------------|---------|
| Python      | 3.11+ (3.12 recommended) |
| PyYAML      | any recent version |
| bash, git   | any recent version |
| OS          | macOS or Linux |

That is the whole list — the engine is deliberately Python stdlib + PyYAML,
so installing recurve never fights your target's toolchain. Probes are plain
executables and can be written in anything.

## From a checkout

recurve runs straight from its source tree; there is no build step.

```bash
git clone <your-recurve-checkout-url> ~/tools/recurve
python3 -m pip install pyyaml
```

Verify:

```bash
python3 ~/tools/recurve/recurve --help
```

## Put it on your PATH

=== "`recurve install` (recommended)"

    The built-in installer symlinks the entrypoint onto your PATH — idempotent,
    and it warns if the target dir isn't on `PATH`:

    ```bash
    python3 ~/tools/recurve/recurve install        # → ~/.local/bin/recurve
    # or pick the dir: ... install --bin-dir ~/bin
    ```

    The unattended loop and agents spawn `recurve` as a *command*, so a real
    PATH entry (this, or the shim below) beats an alias.

=== "Shim script"

    A two-line wrapper works from anywhere and survives shell changes:

    ```bash
    mkdir -p ~/bin
    printf '#!/usr/bin/env bash\nexec python3 ~/tools/recurve/recurve "$@"\n' > ~/bin/recurve
    chmod +x ~/bin/recurve
    ```

    Ensure `~/bin` is on your `PATH`. Targets can also carry their own shim
    (e.g. `<target>/bin/recurve`) so CI and collaborators get the same entry
    point.

=== "Alias"

    ```bash
    echo 'alias recurve="python3 ~/tools/recurve/recurve"' >> ~/.zshrc
    source ~/.zshrc
    ```

    !!! note
        Aliases don't reach subprocesses — the unattended loop and agents
        spawn `recurve` as a command, so prefer the shim for anything beyond
        interactive use (or set `RECURVE_BIN` for the workflow scripts).

## Verify the toolkit's own claims

recurve hosts itself — its promises are probed by the same machinery it
gives you. From the checkout:

```bash
cd ~/tools/recurve
./recurve --config recurve.toml matrix --gate    # the self-host gate
./acceptance/provenance.sh                       # nothing target-specific ships
python3 acceptance/test_phases.py                # behavior tests
```

If the gate is green, your installation works — that *is* the installation
test.

## Optional: docs site

This documentation builds with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/):

```bash
python3 -m pip install mkdocs-material
cd ~/tools/recurve
mkdocs serve
```

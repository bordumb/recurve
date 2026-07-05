"""swebench_env.py — SW1: the environment image, built via SWE-bench's OWN
official instance-building tooling, pinned by digest.

BigCodeBench-Hard shares one derived oracle image across every task
(`oracle_env.py`/`oracle_docker.py`). SWE-bench Verified cannot: each instance
pins its own `base_commit` in its own repo, so "the environment image" (repo
checked out, dependencies installed — SWE-bench calls this the INSTANCE
image, layered on a shared per-(repo,version) ENV image and a shared base OS
image) is a per-instance artifact. We own the pinning and orchestration, not
the environment construction: `build_environment_image` calls straight into
`swebench.harness.test_spec.make_test_spec` +
`swebench.harness.docker_build.build_instance_image` — SWE-bench's own
official harness, `pip install swebench` — never a hand-rolled git-clone-and-
pip-install script.

The trap this guards against: a locally-hand-rolled materialization that
diverges from the official harness's own construction (e.g. missing an
environment-setup step, so a dependency silently isn't installed).
`reconcile_test_collection` is the pure, hermetic check that catches this —
comparing a built image's `pytest --collect-only` output against the
officially-documented one for a pinned sample instance. A missing step
usually manifests as a collection ERROR or a missing test id, both of which
this catches; the impure half (`build_environment_image`, actually invoking
docker) is exercised only on a real run, oracle-waived in the gate, exactly
as `oracle_docker.py`'s docker-touching functions are.
"""

from __future__ import annotations

import hashlib
import json
import re


class EnvironmentSpecError(ValueError):
    """The instance cannot be resolved into a buildable environment spec."""


class EnvironmentDriftError(RuntimeError):
    """The environment image actually present locally does not match the
    pinned digest — refused, exactly as a BigCodeBench oracle-image mismatch
    is (`oracle_env.OracleDriftError`)."""


class TestCollectionMismatch(RuntimeError):
    """A built environment image's test-collection output diverges from the
    official harness's own construction for this instance — a hand-rolled
    materialization missing an environment-setup step, caught before it ever
    grades anything."""


# The verdict-affecting identity of one instance's environment image: which
# instance, which repo state, which concrete image. Deliberately NOT the
# calibration-derived timeout/exclusions (SW4 keys off this hash; including
# them would be circular), same convention as `oracle_env.oracle_env_hash`.
_IDENTITY_KEYS = ("instance_id", "repo", "base_commit", "digest", "platform", "host")


def environment_image_hash(lock: dict) -> str:
    """Digest the verdict-affecting identity of an environment-image lock.
    Two different instances (even from the same repo/version) always hash
    differently because `instance_id`/`base_commit` are part of the identity
    — the per-instance key SW4's calibration hangs off."""
    canon = json.dumps({k: lock.get(k) for k in _IDENTITY_KEYS},
                        sort_keys=True, separators=(",", ":"))
    return "eih:" + hashlib.sha256(canon.encode()).hexdigest()[:32]


def parse_collected_tests(collect_output: str) -> set[str]:
    """Parse `pytest --collect-only -q` output into the set of collected test
    node ids. Pure string parsing — one node id per line, everything after
    the blank-line summary ("N tests collected" / "no tests ran") ignored.
    A collection ERROR yields an empty-ish set that will not match a healthy
    baseline, which is exactly the divergence this exists to surface."""
    ids = set()
    for line in collect_output.splitlines():
        line = line.strip()
        if not line or line.startswith("="):
            continue
        if re.match(r"^\d+ (tests? collected|errors?)", line):
            continue
        if "::" in line or (line.endswith(".py") and "/" in line):
            ids.add(line)
    return ids


def reconcile_test_collection(built_output: str, official_output: str) -> str:
    """`"match"` if a freshly-built environment image's test collection is
    identical to the officially-documented collection for the same pinned
    instance; otherwise raises `TestCollectionMismatch` naming exactly which
    tests are missing or extra. Never silently accepts a divergent build —
    the same posture `oracle_build.reconcile_digest` takes toward a divergent
    oracle image rebuild, applied here to the test-collection signal instead
    of a raw content digest (a per-instance image's content Id is expected to
    vary run to run — build timestamps, layer order — so the digest itself
    cannot be the reconciliation signal; which tests exist to run is the
    invariant that must not drift)."""
    built = parse_collected_tests(built_output)
    official = parse_collected_tests(official_output)
    if built == official:
        return "match"
    missing = sorted(official - built)
    extra = sorted(built - official)
    raise TestCollectionMismatch(
        f"built environment's test collection diverges from the official "
        f"harness's construction — missing: {missing[:10]}, extra: {extra[:10]}. "
        f"A hand-rolled materialization likely skipped an environment-setup "
        f"step (a dependency, a fixture, a conftest). Refusing to pin this "
        f"image; rebuild via SWE-bench's own tooling.")


def missing_image_remediation(instance_id: str, digest: str) -> str:
    """The message a fresh clone sees when the pinned environment image is
    absent locally — names the one-command remediation."""
    return (f"environment image for {instance_id} @ {digest} is not present "
            f"locally — derive it from SWE-bench's own instance-building "
            f"tooling with `eval swebench build <instance_id>` (build-time "
            f"network only; grading stays --network=none), then re-run "
            f"`eval swebench plan`.")


def local_image_digest(image_key: str):  # pragma: no cover - needs docker
    """The content Id of a locally-present image, or None if absent."""
    import subprocess
    r = subprocess.run(["docker", "image", "inspect", image_key, "--format", "{{.Id}}"],
                        capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def build_environment_image(instance: dict, *, client=None,
                             force_rebuild: bool = False) -> dict:  # pragma: no cover - needs docker+network
    """Build the per-instance environment image via SWE-bench's OWN official
    harness (`make_test_spec` + `build_instance_image`) — never a bespoke
    git-clone-and-pip-install script. `namespace=None` forces a LOCAL build
    (never a Docker Hub pull of a pre-built image): we own the pin, so we
    build from the committed recipe SWE-bench ships, exactly as
    `oracle_build.py` derives BigCodeBench's oracle image from a committed
    Dockerfile rather than trusting a registry tag. Returns the resolved lock:
    `{instance_id, repo, base_commit, image, digest, platform, host,
    environment_image_hash}`. Raises `EnvironmentDriftError` if a build
    completes but the resulting image cannot be found (a docker/harness bug,
    not a pin mismatch — a genuine mismatch is a `build_environment_image`
    return value that reconciliation later catches via
    `reconcile_test_collection`)."""
    import platform as _platform
    import docker
    from swebench.harness.test_spec.test_spec import make_test_spec
    from swebench.harness.docker_build import build_instance_image

    client = client or docker.from_env()
    test_spec = make_test_spec(instance, namespace=None)
    build_instance_image(test_spec, client, logger=None, nocache=force_rebuild)
    digest = local_image_digest(test_spec.instance_image_key)
    if digest is None:
        raise EnvironmentDriftError(
            f"built {test_spec.instance_image_key} but it is not present "
            f"locally afterward — refusing to pin a missing image")
    host = f"{_platform.system()}/{_platform.machine()}/{_platform.release()}"
    lock = {
        "instance_id": test_spec.instance_id, "repo": test_spec.repo,
        "base_commit": instance["base_commit"], "image": test_spec.instance_image_key,
        "digest": digest, "platform": test_spec.platform, "host": host,
    }
    lock["environment_image_hash"] = environment_image_hash(lock)
    return lock


def collect_tests_in_container(image_key: str, test_cmd: str,
                                *, client=None) -> str:  # pragma: no cover - needs docker
    """Run the repo's own `--collect-only` against a container built from
    `image_key`, return the raw combined output — the "built" half of SW1's
    reconciliation. The official/documented half is a committed fixture
    (there is no network call to make it "official"; it is recorded once,
    by hand, from a known-good build, exactly as BigCodeBench-Hard's
    `fixtures/bcb-hard-854.json` records one real pinned task rather than
    trusting a re-derivation every gate run)."""
    import docker
    client = client or docker.from_env()
    collect_cmd = test_cmd.split()[0] + " --collect-only -q" if "pytest" in test_cmd else test_cmd
    container = client.containers.run(
        image_key, f"bash -c 'cd /testbed && {collect_cmd}'",
        remove=True, network_disabled=True, detach=False)
    return container.decode() if isinstance(container, bytes) else str(container)

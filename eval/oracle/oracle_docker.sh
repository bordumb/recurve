#!/bin/sh
# The oracle's grading interpreter, as a container. `_run_once` invokes this as
# `oracle_docker.sh -m unittest oracle_case -v` with cwd = the oracle tmpdir, so
# every argument after the wrapper is passed to python INSIDE the pinned image.
#
#   - --entrypoint python : the image ships an evaluate.py entrypoint that would
#     otherwise swallow our args; we want a bare python.
#   - --network=none      : grading is hermetic; the container is the sandbox.
#   - -v "$PWD:/w" -w /w   : the tmpdir (oracle_case.py + any files the test
#     writes) is mounted read-write; it must live under a Docker-shared base.
#   - RECURVE_ORACLE_IMAGE : image@sha256 digest, set by `eval run` from the lock.
#
# This script's content hash is recorded in oracle.lock.json — change the grading
# invocation and the oracle-env identity changes, invalidating a stale calibration.
exec docker run --rm --network=none --platform linux/amd64 --entrypoint python \
  -v "$PWD:/w" -w /w "$RECURVE_ORACLE_IMAGE" "$@"

#!/usr/bin/env bash
if [ -n "${TRAP_FIXTURE:-}" ]; then echo counterexample; exit 1; fi
echo ok; exit 0

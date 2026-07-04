#!/usr/bin/env bash
# Counterexample serializer: lands a candidate by overwriting the tree,
# skipping the gate entirely. The post-landing fleet-gate invariant MUST
# catch what it breaks.
TREE="$1"
echo "bad" > "$TREE/feature.txt"

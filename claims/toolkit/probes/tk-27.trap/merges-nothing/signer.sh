#!/usr/bin/env bash
read h
printf '{"signature":"sig-%s","signer_did":"did:test:agent","envelope_ref":"attestations/%s.json"}' "$h" "$h"

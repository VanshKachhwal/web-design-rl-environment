#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

python -m webdesign_rl.grade \
    --candidate /logs/artifacts \
    --reference-site /tests/reference_site \
    --page-map /tests/page_map.json \
    --out /logs/verifier

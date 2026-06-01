#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

python -m webdesign_rl_anim.grade_anim \
    --candidate /logs/artifacts \
    --reference-site /tests/reference_site \
    --page-map /tests/page_map.json \
    --out /logs/verifier

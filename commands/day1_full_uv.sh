#!/usr/bin/env bash
# Day 1 full Universal Verifier command record.
# The run was internally named E0 during execution.
# Commands are appended here as an auditable record. Credentials are never
# embedded; the verifier wrapper reads OPENAI_API_KEY from the ignored .env.

python scripts/day2/E0_full_uv/snapshot_environment.py
python scripts/day2/E0_full_uv/prepare_corpus.py  # first attempt: local import-order failure
python scripts/day2/E0_full_uv/prepare_corpus.py
python scripts/day2/E0_full_uv/validate_and_plan.py

# Official verifier preflight (the wrapper records its expanded command and logs).
python scripts/day2/E0_full_uv/run_batch.py preflight  # blocked before launch by data-egress approval gate
python scripts/day2/E0_full_uv/run_batch.py preflight  # launched; failed before judge init: missing playwright
python scripts/day2/E0_full_uv/assess_batch.py preflight --expect ok

# Approved dependency repair and successful preflight retry.
python -m pip install playwright==1.51.0  # blocked safely by PEP 668
python -m venv --system-site-packages .venv
.venv/bin/python -m pip install playwright==1.51.0
.venv/bin/python scripts/day2/E0_full_uv/snapshot_environment.py
.venv/bin/python scripts/day2/E0_full_uv/run_batch.py preflight
.venv/bin/python scripts/day2/E0_full_uv/assess_batch.py preflight --expect ok
.venv/bin/python scripts/day2/E0_full_uv/run_batch.py preflight_cache_check
.venv/bin/python scripts/day2/E0_full_uv/assess_batch.py preflight_cache_check --expect cached

# User-approved fresh 10-task canonical batch.
.venv/bin/python scripts/day2/E0_full_uv/run_batch.py batch_10  # blocked before launch by ten-task data-egress approval gate
.venv/bin/python scripts/day2/E0_full_uv/run_batch.py batch_10
.venv/bin/python scripts/day2/E0_full_uv/assess_batch.py batch_10 --expect ok

# User-approved canonical 93-task remainder.
.venv/bin/python scripts/day2/E0_full_uv/run_batch.py remainder  # blocked before launch by 93-task data-egress approval gate
.venv/bin/python scripts/day2/E0_full_uv/run_batch.py remainder
.venv/bin/python scripts/day2/E0_full_uv/assess_batch.py remainder --expect ok
.venv/bin/python scripts/day2/E0_full_uv/finalize_e0.py
.venv/bin/python scripts/day2/E0_full_uv/assess_batch.py preflight --expect ok
.venv/bin/python scripts/day2/E0_full_uv/run_batch.py preflight_cache_check
.venv/bin/python scripts/day2/E0_full_uv/assess_batch.py preflight_cache_check --expect cached

# User-authorized canonical model correction; same three tasks only.
# Expanded verifier command uses: --judge-model gpt-5.2 --o4mini-model o4-mini
.venv/bin/python scripts/day2/E0_full_uv/snapshot_environment.py
.venv/bin/python scripts/day2/E0_full_uv/run_batch.py preflight

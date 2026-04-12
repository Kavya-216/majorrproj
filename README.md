# Eco-Sentry ARCH_6 to ARCH_8 (Python)

This repository contains a production-focused Python implementation for:

- ARCH_6: Secure compact payload pipeline (serialize/compress/encrypt/envelope/decrypt)
- ARCH_7: Energy profiler (24h and 30-day mission simulation)
- ARCH_8: LoRa network simulator (topology/routing/retries/latency Monte Carlo)

ARCH_8 simulation is fully Python and implemented in src/ecosentry/arch8_network.py.

## Project layout

- src/ecosentry/: runtime package
- tests/: validation tests
- config/canonical_config.json: frozen canonical configuration
- docs/RECONCILIATION_TABLE.md: conflict resolution table
- docs/INTEGRATION_KEEP_DELETE.md: what to keep/delete when integrating
- docs/info/: architecture reference markdown files
- artifacts/: generated reports from pipeline execution

## Prerequisites

- Python 3.10+
- pip

## Setup

1. Clone and enter repo.
2. Install dependencies from requirements.
3. Install package in editable mode.

```bash
cd /workspaces/majorrproj
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Run validation tests

```bash
cd /workspaces/majorrproj
pytest -q
```

Expected result: all tests pass.

## Run stages

Run all stages:

```bash
cd /workspaces/majorrproj
python -m ecosentry --stage all --config config/canonical_config.json --out artifacts
```

Run individual stages:

```bash
python -m ecosentry --stage arch6 --config config/canonical_config.json --out artifacts
python -m ecosentry --stage arch7 --config config/canonical_config.json --out artifacts
python -m ecosentry --stage arch8 --config config/canonical_config.json --out artifacts
```

## Artifacts produced

- artifacts/arch6_report.json
- artifacts/arch7_report.json
- artifacts/arch8_report.json
- artifacts/pipeline_summary.json

## Integration with friend's ARCH_1 to ARCH_5

Use docs/INTEGRATION_KEEP_DELETE.md as the source of truth.

For quick cleanup decisions, use:

- integration_buckets/must_keep_core/README.md
- integration_buckets/deletable_only/README.md

Exact integration sequence:

1. Merge your friend's branch first (ARCH_1 to ARCH_5).
2. Merge this branch and keep:
	- src/ecosentry/arch6_payload.py
	- src/ecosentry/arch7_energy.py
	- src/ecosentry/arch8_network.py
	- src/ecosentry/contracts.py
	- src/ecosentry/pipeline_runner.py
	- config/canonical_config.json
3. Ensure ARCH_5 output maps to this strict contract:
	- class_id: int in {0,1,2}
	- confidence: float in [0,1]
	- timestamp_ms: int epoch milliseconds
4. Re-run validation:

```bash
pytest -q
python -m ecosentry --stage all --config config/canonical_config.json --out artifacts
```

## Reliability and correctness guarantees in this implementation

- No silent encryption fallback: malformed envelope/integrity failure raises exception.
- No silent network success: delivery rate and losses are explicitly computed and reported.
- Canonical config-driven behavior: key constants loaded from config/canonical_config.json.
- Tests included for ARCH_6, ARCH_7, ARCH_8.

## Notes on hardcoded values

- Payload size used in simulations is now config-driven via canonical_config.json.
- Scenario coordinates and baseline assumptions are explicit and documented in code/docs.
- If you change assumptions, update canonical_config.json and regenerate artifacts.
# majorrproj
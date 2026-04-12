# Integration Keep/Delete Map

This file tells you exactly what to keep from this branch when merging with your friend's ARCH_1-ARCH_5 work.

## Keep (Core implementation)

- src/ecosentry/__init__.py
- src/ecosentry/__main__.py
- src/ecosentry/config.py
- src/ecosentry/contracts.py
- src/ecosentry/arch6_payload.py
- src/ecosentry/arch7_energy.py
- src/ecosentry/arch8_network.py
- src/ecosentry/pipeline_runner.py
- config/canonical_config.json
- pyproject.toml

## Keep (Validation and reproducibility)

- tests/test_arch6_payload.py
- tests/test_arch7_energy.py
- tests/test_arch8_network.py
- artifacts/arch6_report.json
- artifacts/arch7_report.json
- artifacts/arch8_report.json
- artifacts/pipeline_summary.json

## Keep (Governance docs)

- docs/RECONCILIATION_TABLE.md
- docs/INTEGRATION_KEEP_DELETE.md

## Keep only if useful as references

These are architecture reference docs. Keep for documentation, but they are not runtime-critical.

- docs/info/ARCH_6_JSON_PAYLOAD.md
- docs/info/ARCH_7_ENERGY_PROFILER.md
- docs/info/ARCH_8_NETWORK_SIMULATOR.md
- docs/info/DATA_FLOW_REFERENCE.md
- docs/info/IMPLEMENTATION_EXAMPLES.md
- docs/info/SUMMARY_HIGH_LEVEL_ARCHITECTURE.md
- docs/info/arch12345.md

## Safe to regenerate anytime

- artifacts/*
- .pytest_cache/

## Suggested merge strategy with friend's branch

1. Keep your friend's ARCH_1 to ARCH_5 source of truth.
2. Keep this branch's ARCH_6 to ARCH_8 files listed in "Keep (Core implementation)".
3. Preserve config/canonical_config.json and contracts.py as interface contract files.
4. Run full validation after merge:
   - pytest -q
   - python -m ecosentry --stage all --config config/canonical_config.json --out artifacts

## Non-negotiable checks before final merge

- ARCH_5 output schema must map to Arch5Result in src/ecosentry/contracts.py.
- No encryption fallback on failure (must fail hard).
- No network silent success on undelivered packets.
- Payload size must stay <= configured hard limit (default 1000 bytes).

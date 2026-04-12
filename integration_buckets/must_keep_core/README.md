# Must-Keep Core Bucket

Do not delete these if you want the ARCH_6-ARCH_8 pipeline to run.

## Runtime-critical

- src/ecosentry/
- config/canonical_config.json
- pyproject.toml
- requirements.txt
- README.md

## Validation-critical (recommended keep)

- tests/

## Why must keep

- src/ecosentry contains executable implementation.
- config/canonical_config.json is the frozen configuration contract.
- pyproject.toml and requirements.txt are needed for setup and reproducibility.

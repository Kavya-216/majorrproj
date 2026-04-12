from __future__ import annotations

import argparse
import json

from .pipeline_runner import run_all, run_arch6, run_arch7, run_arch8


def main() -> None:
    parser = argparse.ArgumentParser(description="Eco-Sentry ARCH_6-8 runner")
    parser.add_argument("--stage", choices=["arch6", "arch7", "arch8", "all"], default="all")
    parser.add_argument("--config", default="config/canonical_config.json")
    parser.add_argument("--out", default="artifacts")
    args = parser.parse_args()

    if args.stage == "arch6":
        result = run_arch6(config_path=args.config, out_dir=args.out)
    elif args.stage == "arch7":
        result = run_arch7(config_path=args.config, out_dir=args.out)
    elif args.stage == "arch8":
        result = run_arch8(config_path=args.config, out_dir=args.out)
    else:
        result = run_all(config_path=args.config, out_dir=args.out)

    print(json.dumps({"stage": args.stage, "status": "ok", "artifacts": args.out}, indent=2))
    if isinstance(result, dict) and "arch6" in result:
        print(
            json.dumps(
                {
                    "arch6_size_bytes": result["arch6"]["size_report"]["enveloped_bytes"],
                    "arch8_scenarios": list(result["arch8"]["campaigns"].keys()),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

"""Run compiler-backed COBOL oracle checks for the invoice task."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from legacy_cobol_env.eval.cobol_oracle import (
    DEFAULT_IMAGE_TAG,
    compile_invoice_task_sources,
    compare_invoice_oracle,
    write_comparison_report,
)


ENV_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ENV_ROOT / "outputs" / "evals"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true", help="Build the GnuCOBOL oracle image before running")
    parser.add_argument("--image-tag", default=DEFAULT_IMAGE_TAG)
    parser.add_argument("--no-fresh", action="store_true", help="Check only visible and hidden invoice cases")
    parser.add_argument("--output", default=str(OUTPUT_DIR / "cobol_invoice_oracle_check.json"))
    args = parser.parse_args()

    result = compare_invoice_oracle(
        image_tag=args.image_tag,
        build=args.build,
        include_fresh=not args.no_fresh,
    )
    result["source_compile"] = compile_invoice_task_sources(
        image_tag=args.image_tag,
        build=False,
    )
    result["ok"] = result["ok"] and result["source_compile"]["ok"]
    write_comparison_report(result, Path(args.output))
    print(
        json.dumps(
            {
                "ok": result["ok"],
                "case_count": result["case_count"],
                "passed_count": result["passed_count"],
                "source_compile_ok": result["source_compile"]["ok"],
            },
            indent=2,
        )
    )
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

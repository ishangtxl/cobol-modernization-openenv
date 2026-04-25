"""Write the oracle SFT warm-start dataset as JSONL."""

from __future__ import annotations

import argparse
from pathlib import Path

from legacy_cobol_env.server.task_bank import all_tasks
from legacy_cobol_env.training.sft_dataset import build_oracle_sft_examples, dumps_jsonl


ENV_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ENV_ROOT / "outputs" / "training"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(OUTPUT_DIR / "oracle_sft.jsonl"))
    parser.add_argument("--invoice-focus-copies", type=int, default=4)
    parser.add_argument("--invoice-repair-copies", type=int, default=5)
    args = parser.parse_args()

    examples = build_oracle_sft_examples(
        all_tasks(),
        invoice_focus_copies=args.invoice_focus_copies,
        invoice_repair_copies=args.invoice_repair_copies,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dumps_jsonl(examples), encoding="utf-8")
    print(f"wrote {len(examples)} examples to {output_path}")


if __name__ == "__main__":
    main()

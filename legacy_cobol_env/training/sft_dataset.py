"""Build small SFT warm-start datasets from oracle workbench prompts."""

from __future__ import annotations

import json
from typing import Iterable

from legacy_cobol_env.eval.model_rollout import build_migration_prompt, run_model_repair_rollout
from legacy_cobol_env.eval.oracle_solutions import solution_for_task
from legacy_cobol_env.eval.providers import SequenceResponseProvider
from legacy_cobol_env.server.task_bank import TaskInstance, copybook_layout_for


def build_oracle_sft_examples(
    tasks: Iterable[TaskInstance],
    invoice_focus_copies: int = 0,
    invoice_repair_copies: int = 0,
) -> list[dict]:
    examples = []
    for task in tasks:
        ticket = {
            "task_id": task.task_id,
            "family_id": task.family_id,
            "domain": task.domain,
            "ticket": task.ticket,
            "available_files": sorted(task.cobol_files),
            "available_copybooks": sorted(task.copybooks),
            "expected_callable": task.expected_callable,
            "visible_tests": len(task.visible_tests),
            "hidden_tests": len(task.hidden_tests),
            "input_width": task.metadata["input_width"],
            "output_width": task.metadata["output_width"],
            "output_layout": task.metadata["output_layout"],
        }
        context = {
            "cobol_files": task.cobol_files,
            "copybooks": task.copybooks,
            "layouts": {filename: copybook_layout_for(task, filename) for filename in task.copybooks},
            "business_rules": task.metadata["business_rules"],
        }
        prompt = build_migration_prompt(ticket, context)
        completion = json.dumps({"code": solution_for_task(task)})
        examples.append({"task_id": task.task_id, "family_id": task.family_id, "prompt": prompt, "completion": completion})
        if task.task_id == "invoice_occurs_001":
            examples.extend(_invoice_focus_examples(task, prompt, completion, invoice_focus_copies))
            examples.extend(_invoice_repair_examples(task, completion, invoice_repair_copies))
    return examples


def _invoice_focus_examples(task: TaskInstance, prompt: str, completion: str, copies: int) -> list[dict]:
    focus = "\n".join(
        [
            "Invoice focus checklist:",
            "- ITEM-PRICE is PIC 9(4)V99, so parse six digits as cents: Decimal(int(slice)) / Decimal(\"100\").",
            "- TAX-CODE is the last byte of each 9-byte LINE-ITEM stride.",
            "- OUT-TOTAL is integer cents formatted with {cents:09d}; it must not contain a decimal point or spaces.",
            "- OUT-FLAG is H when total >= Decimal(\"1000.00\"), otherwise L.",
        ]
    )
    return [
        {
            "task_id": f"{task.task_id}_focus_{index}",
            "family_id": task.family_id,
            "prompt": f"{prompt}\n\n{focus}",
            "completion": completion,
        }
        for index in range(1, max(0, copies) + 1)
    ]


def _invoice_repair_examples(task: TaskInstance, completion: str, copies: int) -> list[dict]:
    seeds = _invoice_bad_repair_seeds()
    examples = []
    for index in range(1, max(0, copies) + 1):
        bad_code = seeds[(index - 1) % len(seeds)]
        provider = SequenceResponseProvider(
            name="repair-sft",
            responses=[
                json.dumps({"code": bad_code}),
                completion,
            ],
        )
        trajectory = run_model_repair_rollout(task=task, provider=provider, max_repairs=1)
        examples.append(
            {
                "task_id": f"{task.task_id}_repair_{index}",
                "family_id": task.family_id,
                "prompt": trajectory["model_turns"][1]["prompt"],
                "completion": completion,
            }
        )
    return examples


def _invoice_bad_repair_seeds() -> list[str]:
    return [
        """from decimal import Decimal

def migrate(input_record: str) -> str:
    record = {
        "INVOICE-ID": input_record[0:6],
        "ITEM-COUNT": int(input_record[6:8]),
        "LINE-ITEMS": [
            {
                "ITEM-QTY": int(input_record[i + 0:i + 2]),
                "ITEM-PRICE": Decimal(int(input_record[i + 2:i + 8])) / Decimal("100"),
                "TAX-CODE": input_record[i + 8]
            }
            for i in range(0, 36, 9)[:input_record[6:8]]
        ]
    }
    tax_table = {"S": Decimal("0.0725"), "R": Decimal("0.0250"), "L": Decimal("0.1000")}
    invoice_total = Decimal("0")
    for line_item in record["LINE-ITEMS"]:
        line_amount = line_item["ITEM-QTY"] * line_item["ITEM-PRICE"]
        tax_rate = tax_table[line_item["TAX-CODE"]]
        invoice_total += line_amount + line_amount * tax_rate
    out_flag = "H" if invoice_total >= Decimal("1000.00") else "L"
    return record["INVOICE-ID"] + str(invoice_total.quantize(Decimal("1.00"))).zfill(9) + str(record["ITEM-COUNT"]).zfill(2) + out_flag
""",
        """from decimal import Decimal

def migrate(input_record: str) -> str:
    invoice_id = input_record[0:6]
    item_count = int(input_record[6:8])
    total = Decimal("0.00")
    for i in range(item_count):
        start = 8 + i * 9
        qty = int(input_record[start:start + 2])
        price = Decimal(input_record[start + 2:start + 8]) / Decimal("100")
        tax_code = input_record[start + 8:start + 9]
        rate = {"S": Decimal("0.0725"), "R": Decimal("0.0250"), "L": Decimal("0.1000")}.get(tax_code, Decimal("0.0000"))
        total += qty * price * (Decimal("1.0000") + rate)
    out_total = total.quantize(Decimal("0.01")).to_integral_value()
    flag = "H" if total >= Decimal("1000.00") else "L"
    return f"{invoice_id}{out_total:09d}{item_count:02d}{flag}"
""",
        """from decimal import Decimal

def migrate(input_record: str) -> str:
    invoice_id = input_record[0:6]
    item_count = min(int(input_record[6:8]), 4)
    total = Decimal("0.00")
    for i in range(item_count):
        start = 8 + i * 9
        qty = int(input_record[start:start + 2])
        price = Decimal(input_record[start + 2:start + 8]) / Decimal("100")
        tax_code = input_record[start + 8:start + 9]
        tax = {"S": Decimal("0.0725"), "R": Decimal("0.0250"), "L": Decimal("0.1000")}.get(tax_code, Decimal("0.0000"))
        line = qty * price
        total += line + (line * tax)
    total_str = format(total.quantize(Decimal("0.01")), "09.2f")
    flag = "H" if total >= Decimal("1000.00") else "L"
    return f"{invoice_id}{total_str}{item_count:02d}{flag}"
""",
        """from decimal import Decimal

def migrate(input_record: str) -> str:
    invoice_id = input_record[0:6]
    item_count = min(int(input_record[6:8]), 4)
    total = Decimal("0.00")
    for i in range(item_count):
        start = 8 + i * 9
        qty = int(input_record[start:start + 2])
        price = Decimal(input_record[start + 2:start + 8])
        tax_code = input_record[start + 8:start + 9]
        rate = {"S": Decimal("0.0725"), "R": Decimal("0.0250"), "L": Decimal("0.1000")}.get(tax_code, Decimal("0.0000"))
        total += (qty * price) * (Decimal("1.0000") + rate)
    total_str = str(total.quantize(Decimal("0.01"))).zfill(9)
    return f"{invoice_id}{total_str}{item_count:02d}H"
""",
    ]


def dumps_jsonl(examples: list[dict]) -> str:
    rows = []
    for example in examples:
        rows.append(
            json.dumps(
                {
                    "task_id": example["task_id"],
                    "family_id": example["family_id"],
                    "messages": [
                        {"role": "user", "content": example["prompt"]},
                        {"role": "assistant", "content": example["completion"]},
                    ],
                }
            )
        )
    return "\n".join(rows) + "\n"

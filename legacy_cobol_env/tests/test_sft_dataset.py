import json

from legacy_cobol_env.server.task_bank import all_tasks
from legacy_cobol_env.training.sft_dataset import build_oracle_sft_examples, dumps_jsonl


def test_build_oracle_sft_examples_covers_all_tasks():
    examples = build_oracle_sft_examples(all_tasks())

    assert len(examples) == 6
    assert {example["task_id"] for example in examples} == {task.task_id for task in all_tasks()}
    assert all("def migrate" in example["completion"] for example in examples)
    assert any(example["family_id"] == "invoice_occurs_totals" for example in examples)


def test_build_oracle_sft_examples_can_add_invoice_focus_rows():
    examples = build_oracle_sft_examples(all_tasks(), invoice_focus_copies=3)
    focus = [example for example in examples if example["task_id"].startswith("invoice_occurs_001_focus_")]

    assert len(examples) == 9
    assert len(focus) == 3
    assert all("Invoice focus checklist" in example["prompt"] for example in focus)
    assert all("cents:09d" in example["completion"] for example in focus)


def test_build_oracle_sft_examples_can_add_invoice_repair_rows():
    examples = build_oracle_sft_examples(all_tasks(), invoice_repair_copies=5)
    repair = [example for example in examples if example["task_id"].startswith("invoice_occurs_001_repair_")]

    assert len(examples) == 11
    assert len(repair) == 5
    assert all("Repair the Python migration after visible test feedback" in example["prompt"] for example in repair)
    assert all("Previous code:" in example["prompt"] for example in repair)
    assert any("invalid format string" in example["prompt"] for example in repair)
    assert any("object has no attribute 'to_string'" in example["prompt"] for example in repair)
    assert any("OUT-TOTAL" in example["prompt"] for example in repair)
    assert all("cents:09d" in example["completion"] for example in repair)


def test_oracle_sft_prompt_includes_output_contract():
    examples = build_oracle_sft_examples(all_tasks())
    invoice = next(example for example in examples if example["task_id"] == "invoice_occurs_001")

    assert "output_layout" in invoice["prompt"]
    assert "OUT-TOTAL" in invoice["prompt"]
    assert "OUT-ITEM-COUNT" in invoice["prompt"]
    assert "PIC fields with V use an implied decimal point" in invoice["prompt"]
    assert "fixed-width numeric outputs are digits only" in invoice["prompt"]


def test_oracle_sft_prompt_includes_invoice_occurs_child_offsets():
    examples = build_oracle_sft_examples(all_tasks())
    invoice = next(example for example in examples if example["task_id"] == "invoice_occurs_001")

    assert "ITEM-PRICE" in invoice["prompt"]
    assert '"start": 2' in invoice["prompt"]
    assert '"end": 8' in invoice["prompt"]
    assert "TAX-CODE-KEY" in invoice["prompt"]


def test_dumps_jsonl_writes_one_json_object_per_line():
    examples = build_oracle_sft_examples(all_tasks()[:1])
    payload = dumps_jsonl(examples)

    parsed = [json.loads(line) for line in payload.splitlines()]
    assert len(parsed) == 1
    assert parsed[0]["messages"][0]["role"] == "user"
    assert parsed[0]["messages"][1]["role"] == "assistant"

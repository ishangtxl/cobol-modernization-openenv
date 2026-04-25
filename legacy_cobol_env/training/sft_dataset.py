"""Build small SFT warm-start datasets from oracle workbench prompts."""

from __future__ import annotations

import json
from typing import Iterable

from legacy_cobol_env.eval.model_rollout import build_migration_prompt
from legacy_cobol_env.eval.oracle_solutions import solution_for_task
from legacy_cobol_env.server.task_bank import TaskInstance, copybook_layout_for


def build_oracle_sft_examples(tasks: Iterable[TaskInstance]) -> list[dict]:
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
        examples.append(
            {
                "task_id": task.task_id,
                "family_id": task.family_id,
                "prompt": build_migration_prompt(ticket, context),
                "completion": json.dumps({"code": solution_for_task(task)}),
            }
        )
    return examples


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

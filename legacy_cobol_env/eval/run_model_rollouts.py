"""Run provider-backed model rollouts and write evaluation artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from statistics import mean
from datetime import UTC, datetime

from legacy_cobol_env.eval.model_rollout import run_model_repair_rollout, run_model_rollout, run_tool_choice_rollout
from legacy_cobol_env.eval.oracle_solutions import solution_for_task
from legacy_cobol_env.eval.providers import StaticResponseProvider, create_provider
from legacy_cobol_env.server.task_bank import all_tasks, load_task


ENV_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ENV_ROOT / "outputs" / "evals"


def run_rollouts(
    provider_name: str,
    task_id: str | None = None,
    max_repairs: int = 0,
    rollout_mode: str = "codegen_assisted",
) -> dict:
    tasks = [load_task(task_id=task_id)] if task_id else all_tasks()
    trajectories = []
    for task in tasks:
        provider = (
            StaticResponseProvider("oracle-model", json.dumps({"code": solution_for_task(task)}))
            if provider_name == "oracle-model"
            else create_provider(provider_name, os.environ)
        )
        if rollout_mode == "tool_choice":
            trajectory = run_tool_choice_rollout(task=task, provider=provider)
        else:
            trajectory = (
                run_model_repair_rollout(task=task, provider=provider, max_repairs=max_repairs)
                if max_repairs > 0
                else run_model_rollout(task=task, provider=provider)
            )
        trajectories.append(trajectory)

    return {
        "provider": provider_name,
        "created_at": datetime.now(UTC).isoformat(),
        "rollout_mode": rollout_mode,
        "model_name": _model_name(provider_name, os.environ),
        "max_repairs": max_repairs,
        "task_count": len(trajectories),
        "mean_public_score": mean(item["final"]["public_score"] for item in trajectories),
        "accepted_count": sum(1 for item in trajectories if item["final"]["accepted"]),
        "trajectories": trajectories,
    }


def _model_name(provider_name: str, env: dict[str, str]) -> str | None:
    if provider_name == "azure-openai":
        return env.get("AZURE_OPENAI_DEPLOYMENT")
    if provider_name == "hf-chat":
        return env.get("HF_MODEL")
    if provider_name == "hf-endpoint":
        return env.get("HF_INFERENCE_ENDPOINT")
    if provider_name == "local-transformers":
        return env.get("LOCAL_MODEL_PATH")
    return provider_name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        default="oracle-model",
        choices=["oracle-model", "static", "azure-openai", "hf-endpoint", "hf-chat", "local-transformers"],
    )
    parser.add_argument("--task-id")
    parser.add_argument("--max-repairs", type=int, default=0)
    parser.add_argument("--rollout-mode", choices=["codegen_assisted", "tool_choice"], default="codegen_assisted")
    parser.add_argument("--output", default=str(OUTPUT_DIR / "model_rollouts.json"))
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = run_rollouts(
        provider_name=args.provider,
        task_id=args.task_id,
        max_repairs=args.max_repairs,
        rollout_mode=args.rollout_mode,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ["provider", "task_count", "mean_public_score", "accepted_count"]}, indent=2))


if __name__ == "__main__":
    main()

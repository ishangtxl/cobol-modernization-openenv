"""Inspect saved model rollout artifacts for debugging."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from legacy_cobol_env.eval.model_rollout import extract_code_from_response


STEP_NAMES_TO_SHOW = {"write_python_solution", "run_visible_tests", "inspect_diff", "submit_final"}


def inspect_rollout_file(path: Path, max_chars: int = 4000) -> str:
    summary = json.loads(path.read_text(encoding="utf-8"))
    return inspect_rollout_summary(summary, max_chars=max_chars)


def inspect_rollout_summary(summary: dict[str, Any], max_chars: int = 4000) -> str:
    lines: list[str] = []
    lines.append("SUMMARY")
    lines.append(
        _json_preview(
            {
                key: summary.get(key)
                for key in ["provider", "max_repairs", "task_count", "mean_public_score", "accepted_count"]
                if key in summary
            },
            max_chars,
        )
    )

    trajectories = summary.get("trajectories", [])
    if not trajectories:
        lines.append("\nNO TRAJECTORIES")
        return "\n".join(lines)

    for index, trajectory in enumerate(trajectories, start=1):
        lines.append(f"\nTRAJECTORY {index}")
        lines.append(
            _json_preview(
                {
                    key: trajectory.get(key)
                    for key in ["task_id", "family_id", "policy"]
                    if key in trajectory
                },
                max_chars,
            )
        )
        lines.append("\nFINAL")
        lines.append(_json_preview(trajectory.get("final", {}), max_chars))
        lines.append("\nVISIBLE")
        lines.append(_json_preview(trajectory.get("visible", {}), max_chars))
        lines.append("\nMODEL TURNS")
        lines.extend(_format_model_turns(trajectory.get("model_turns", []), max_chars))
        lines.append("\nWRITE / TEST STEPS")
        lines.extend(_format_steps(trajectory.get("steps", []), max_chars))

    return "\n".join(lines)


def _format_model_turns(model_turns: list[dict[str, Any]], max_chars: int) -> list[str]:
    lines: list[str] = []
    for index, turn in enumerate(model_turns, start=1):
        response = str(turn.get("response", ""))
        lines.append(f"\n--- turn {index} raw response ---")
        lines.append(_text_preview(response, max_chars))
        lines.append(f"\n--- turn {index} extracted code ---")
        try:
            lines.append(_text_preview(extract_code_from_response(response), max_chars))
        except Exception as exc:  # pragma: no cover - exact parser errors vary.
            lines.append(f"extract failed: {exc!r}")
    if not lines:
        lines.append("(none)")
    return lines


def _format_steps(steps: list[dict[str, Any]], max_chars: int) -> list[str]:
    lines: list[str] = []
    for step in steps:
        tool_name = step.get("tool_name")
        if tool_name not in STEP_NAMES_TO_SHOW:
            continue
        lines.append(f"\n{tool_name}")
        lines.append(_json_preview(step.get("result", {}), max_chars))
    if not lines:
        lines.append("(none)")
    return lines


def _json_preview(value: Any, max_chars: int) -> str:
    return _text_preview(json.dumps(value, indent=2, sort_keys=True), max_chars)


def _text_preview(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    omitted = len(value) - max_chars
    return f"{value[:max_chars]}\n... <truncated {omitted} chars>"


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the useful parts of a saved rollout JSON artifact.")
    parser.add_argument("path", type=Path, help="Path to a run_model_rollouts JSON output.")
    parser.add_argument("--max-chars", type=int, default=4000, help="Maximum characters per response/result block.")
    args = parser.parse_args()

    print(inspect_rollout_file(args.path, max_chars=args.max_chars))


if __name__ == "__main__":
    main()

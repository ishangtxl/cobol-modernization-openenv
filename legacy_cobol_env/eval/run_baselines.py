"""Run deterministic non-model baselines across all task families.

This is not the final training evidence. It gives the project a repeatable
evaluation harness so baseline, SFT, and RL runs can share one result shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from datetime import UTC, datetime

from openenv.core.env_server.mcp_types import CallToolAction

from legacy_cobol_env.server.legacy_cobol_env_environment import LegacyCobolEnvironment
from legacy_cobol_env.server.task_bank import all_tasks


ENV_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ENV_ROOT / "outputs" / "evals"
PLOT_DIR = ENV_ROOT / "plots"


def call(env: LegacyCobolEnvironment, tool_name: str, **arguments):
    obs = env.step(CallToolAction(tool_name=tool_name, arguments=arguments))
    return obs.result.data


def identity_solution() -> str:
    return """def migrate(input_record: str) -> str:
    return input_record
"""


def blank_width_solution(width: int) -> str:
    return f"""def migrate(input_record: str) -> str:
    return " " * {width}
"""


def run_policy(policy_name: str, task, code: str) -> dict:
    env = LegacyCobolEnvironment()
    env.reset(task_id=task.task_id)
    written = call(env, "write_python_solution", code=code)
    visible = call(env, "run_visible_tests", draft_id=written["draft_id"])
    final = call(env, "submit_final", draft_id=written["draft_id"])
    return {
        "policy": policy_name,
        "task_id": task.task_id,
        "family_id": task.family_id,
        "visible_pass_rate": visible["pass_rate"],
        "public_score": final["public_score"],
        "components": final["components"],
        "accepted": final["accepted"],
    }


def write_svg(results: list[dict], path: Path) -> None:
    families = []
    scores_by_policy: dict[str, list[float]] = {}
    for row in results:
        if row["task_id"] not in families:
            families.append(row["task_id"])
        scores_by_policy.setdefault(row["policy"], []).append(row["public_score"])

    width = 960
    height = 360
    margin = 48
    bar_w = 26
    gap = 22
    colors = {"identity": "#3b82f6", "blank_width": "#10b981"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="48" y="30" font-family="Arial" font-size="18" font-weight="700">Baseline public score by task family</text>',
        f'<line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#222"/>',
        f'<line x1="{margin}" y1="{height - margin}" x2="{margin}" y2="{margin}" stroke="#222"/>',
    ]
    x = margin + 20
    by_task = {(row["task_id"], row["policy"]): row["public_score"] for row in results}
    for task_id in families:
        for offset, policy in enumerate(scores_by_policy):
            score = by_task[(task_id, policy)]
            bar_h = score * (height - 2 * margin)
            bx = x + offset * (bar_w + 4)
            by = height - margin - bar_h
            parts.append(f'<rect x="{bx}" y="{by:.1f}" width="{bar_w}" height="{bar_h:.1f}" fill="{colors.get(policy, "#64748b")}"/>')
            parts.append(f'<text x="{bx}" y="{by - 4:.1f}" font-family="Arial" font-size="10">{score:.2f}</text>')
        label = task_id.replace("_001", "").replace("_", " ")
        parts.append(f'<text x="{x - 6}" y="{height - 16}" font-family="Arial" font-size="10" transform="rotate(25 {x - 6},{height - 16})">{label}</text>')
        x += len(scores_by_policy) * (bar_w + 4) + gap

    legend_x = width - 210
    for idx, policy in enumerate(scores_by_policy):
        y = 52 + idx * 20
        parts.append(f'<rect x="{legend_x}" y="{y - 10}" width="12" height="12" fill="{colors.get(policy, "#64748b")}"/>')
        parts.append(f'<text x="{legend_x + 18}" y="{y}" font-family="Arial" font-size="12">{policy}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for task in all_tasks():
        results.append(run_policy("identity", task, identity_solution()))
        results.append(run_policy("blank_width", task, blank_width_solution(task.metadata["output_width"])))

    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "policies": sorted({row["policy"] for row in results}),
        "task_count": len(all_tasks()),
        "mean_public_score": {
            policy: mean(row["public_score"] for row in results if row["policy"] == policy)
            for policy in sorted({row["policy"] for row in results})
        },
        "results": results,
    }

    (OUTPUT_DIR / "baseline_results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_svg(results, PLOT_DIR / "baseline_scores.svg")
    print(json.dumps(summary["mean_public_score"], indent=2))


if __name__ == "__main__":
    main()

"""Build judge-facing score summaries from evaluation artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import UTC, datetime
from typing import Any


def build_score_summary(
    baseline: dict[str, Any],
    zeroshot: dict[str, Any] | None = None,
    repair: dict[str, Any] | None = None,
    oracle_model: dict[str, Any] | None = None,
    trained: dict[str, Any] | None = None,
    evidence_notes: list[str] | None = None,
) -> dict[str, Any]:
    baseline_task_count = baseline.get("task_count") or len({row["task_id"] for row in baseline["results"]})
    policies = {
        name: {
            "mean_public_score": score,
            "accepted_count": sum(
                1 for row in baseline["results"] if row["policy"] == name and row.get("accepted")
            ),
            "task_count": baseline_task_count,
            "role": "deterministic_baseline",
            "created_at": baseline.get("created_at"),
        }
        for name, score in baseline["mean_public_score"].items()
    }
    if oracle_model is not None:
        policies["oracle-model"] = {
            "mean_public_score": oracle_model["mean_public_score"],
            "accepted_count": oracle_model["accepted_count"],
            "task_count": oracle_model["task_count"],
            "role": "oracle_sanity",
            "created_at": oracle_model.get("created_at"),
            "rollout_mode": oracle_model.get("rollout_mode", "codegen_assisted"),
        }
    if zeroshot is not None:
        policies["gpt-5.4-mini zero-shot"] = {
            "mean_public_score": zeroshot["mean_public_score"],
            "accepted_count": zeroshot["accepted_count"],
            "task_count": zeroshot["task_count"],
            "role": "current_model_baseline",
            "created_at": zeroshot.get("created_at"),
            "rollout_mode": zeroshot.get("rollout_mode", "codegen_assisted"),
        }
    if repair is not None:
        policies["gpt-5.4-mini + repair1"] = {
            "mean_public_score": repair["mean_public_score"],
            "accepted_count": repair["accepted_count"],
            "task_count": repair["task_count"],
            "role": "current_model_repair",
            "created_at": repair.get("created_at"),
            "rollout_mode": repair.get("rollout_mode", "codegen_assisted"),
        }
    if trained is not None:
        trained_name = f"trained-{trained.get('provider', 'model')}"
        policies[trained_name] = {
            "mean_public_score": trained["mean_public_score"],
            "accepted_count": trained["accepted_count"],
            "task_count": trained["task_count"],
            "role": "trained",
            "created_at": trained.get("created_at"),
            "model_name": trained.get("model_name"),
            "rollout_mode": trained.get("rollout_mode", "codegen_assisted"),
        }

    task_scores: dict[str, dict[str, Any]] = {}
    for row in baseline["results"]:
        task_scores.setdefault(row["task_id"], {})[row["policy"]] = row.get("public_score")
    if oracle_model is not None:
        for trajectory in oracle_model["trajectories"]:
            task_scores.setdefault(trajectory["task_id"], {})["oracle_model"] = trajectory["final"]["public_score"]
    if zeroshot is not None:
        for trajectory in zeroshot["trajectories"]:
            task_scores.setdefault(trajectory["task_id"], {})["zeroshot"] = trajectory["final"]["public_score"]
    if repair is not None:
        for trajectory in repair["trajectories"]:
            task_scores.setdefault(trajectory["task_id"], {})["repair1"] = trajectory["final"]["public_score"]
            task_scores[trajectory["task_id"]]["repair1_accepted"] = trajectory["final"]["accepted"]
    if trained is not None:
        for trajectory in trained["trajectories"]:
            task_scores.setdefault(trajectory["task_id"], {})["trained"] = trajectory["final"]["public_score"]
            task_scores[trajectory["task_id"]]["trained_accepted"] = trajectory["final"]["accepted"]

    training_targets = []
    if repair is not None:
        for trajectory in repair["trajectories"]:
            final = trajectory["final"]
            visible = trajectory["visible"]
            if visible["pass_rate"] == 1.0 and not final["accepted"]:
                training_targets.append(
                    {
                        "task_id": trajectory["task_id"],
                        "family_id": trajectory.get("family_id"),
                        "reason": "visible-pass-hidden-fresh-gap",
                        "public_score": final["public_score"],
                        "weak_components": {
                            key: value
                            for key, value in final["components"].items()
                            if isinstance(value, int | float) and value < 1.0
                        },
                    }
                )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "policies": policies,
        "task_scores": task_scores,
        "judge_table": _judge_table(policies, task_scores),
        "training_targets": training_targets,
        "evidence_notes": evidence_notes or [],
    }


def _judge_table(policies: dict[str, dict[str, Any]], task_scores: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    invoice_scores = task_scores.get("invoice_occurs_001", {})
    invoice_keys = {
        "oracle-model": "oracle_model",
        "gpt-5.4-mini zero-shot": "zeroshot",
        "gpt-5.4-mini + repair1": "repair1",
    }
    for policy, data in policies.items():
        invoice_key = invoice_keys.get(policy, policy)
        if policy.startswith("trained-"):
            invoice_key = "trained"
        rows.append(
            {
                "policy": policy,
                "role": data.get("role"),
                "mean_public_score": data["mean_public_score"],
                "accepted_count": data["accepted_count"],
                "task_count": data["task_count"],
                "invoice_public_score": invoice_scores.get(invoice_key),
            }
        )
    return rows


def write_score_plot(summary: dict[str, Any], path: Path) -> None:
    policies = list(summary["policies"].items())
    width = 760
    height = 320
    margin = 48
    plot_height = height - margin * 2
    bar_width = 86
    gap = 32
    colors = ["#64748b", "#22c55e", "#2563eb", "#f97316"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="40" y="30" font-family="Arial" font-size="18" font-weight="700">Legacy COBOL OpenEnv evaluation</text>',
        f'<line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#1f2937"/>',
        f'<line x1="{margin}" y1="{height - margin}" x2="{margin}" y2="{margin}" stroke="#1f2937"/>',
    ]
    x = margin + 20
    for index, (name, data) in enumerate(policies):
        score = float(data["mean_public_score"])
        bar_height = score * plot_height
        y = height - margin - bar_height
        color = colors[index % len(colors)]
        parts.append(f'<rect x="{x}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{x + 8}" y="{y - 8:.1f}" font-family="Arial" font-size="12">{score:.3f}</text>')
        accepted = f'{data["accepted_count"]}/{data["task_count"]} accepted'
        parts.append(f'<text x="{x}" y="{height - 28}" font-family="Arial" font-size="10">{accepted}</text>')
        for line_index, line in enumerate(_wrap_label(name)):
            parts.append(f'<text x="{x}" y="{height - 14 + line_index * 11}" font-family="Arial" font-size="10">{line}</text>')
        x += bar_width + gap
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def _wrap_label(label: str) -> list[str]:
    words = label.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > 18 and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:2]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

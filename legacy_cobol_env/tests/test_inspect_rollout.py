import json

from legacy_cobol_env.eval.inspect_rollout import inspect_rollout_file, inspect_rollout_summary


def test_inspect_rollout_summary_prints_code_and_relevant_steps():
    summary = {
        "provider": "local-transformers",
        "max_repairs": 1,
        "task_count": 1,
        "mean_public_score": 0.15,
        "accepted_count": 0,
        "trajectories": [
            {
                "policy": "local-transformers",
                "task_id": "invoice_occurs_001",
                "family_id": "invoice_occurs_totals",
                "final": {"public_score": 0.15, "accepted": False},
                "visible": {"passed": 0, "total": 3, "pass_rate": 0.0},
                "model_turns": [
                    {
                        "response": '```json\n{"code": "def migrate(input_record: str) -> str:\\n    return input_record\\n"}\n```'
                    }
                ],
                "steps": [
                    {"tool_name": "read_cobol_file", "result": {"content": "COBOL"}},
                    {"tool_name": "write_python_solution", "result": {"syntax_ok": True}},
                    {"tool_name": "run_visible_tests", "result": {"passed": 0, "total": 3}},
                ],
            }
        ],
    }

    report = inspect_rollout_summary(summary)

    assert "SUMMARY" in report
    assert "invoice_occurs_001" in report
    assert "def migrate(input_record: str) -> str:" in report
    assert "write_python_solution" in report
    assert "run_visible_tests" in report
    assert "read_cobol_file" not in report


def test_inspect_rollout_file_reads_saved_json(tmp_path):
    output = tmp_path / "rollout.json"
    output.write_text(json.dumps({"provider": "oracle-model", "trajectories": []}), encoding="utf-8")

    report = inspect_rollout_file(output)

    assert "oracle-model" in report
    assert "NO TRAJECTORIES" in report

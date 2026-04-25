import json

from legacy_cobol_env.eval.oracle_solutions import solution_for_task
from legacy_cobol_env.eval.trajectory import run_solution_trajectory
from legacy_cobol_env.server.task_bank import all_tasks


def test_oracle_solution_scores_every_task_at_one():
    for task in all_tasks():
        trajectory = run_solution_trajectory(
            policy_name="oracle",
            task=task,
            code=solution_for_task(task),
        )

        assert trajectory["final"]["public_score"] == 1.0
        assert trajectory["final"]["accepted"] is True
        assert trajectory["visible"]["pass_rate"] == 1.0


def test_trajectory_records_serializable_tool_sequence():
    task = all_tasks()[0]
    trajectory = run_solution_trajectory(
        policy_name="oracle",
        task=task,
        code=solution_for_task(task),
    )

    assert [step["tool_name"] for step in trajectory["steps"]] == [
        "read_cobol_file",
        "read_copybook",
        "parse_copybook_layout",
        "inspect_business_rules",
        "write_python_solution",
        "run_visible_tests",
        "submit_final",
    ]
    assert trajectory["steps"][0]["reward"] == 0.02
    assert trajectory["steps"][-1]["done"] is True
    json.dumps(trajectory)

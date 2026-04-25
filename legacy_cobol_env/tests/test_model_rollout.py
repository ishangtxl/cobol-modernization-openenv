import json

from legacy_cobol_env.eval.model_rollout import extract_code_from_response, run_model_repair_rollout, run_model_rollout
from legacy_cobol_env.eval.oracle_solutions import solution_for_task
from legacy_cobol_env.eval.providers import SequenceResponseProvider, StaticResponseProvider, create_provider
from legacy_cobol_env.server.task_bank import all_tasks


class RecordingProvider:
    name = "recording"

    def __init__(self, responses):
        self.responses = responses
        self.prompts = []
        self.index = 0

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        response = self.responses[self.index]
        self.index += 1
        return response


def test_extract_code_from_fenced_json_response():
    response = '```json\n{"code": "def migrate(input_record: str) -> str:\\n    return input_record\\n"}\n```'

    assert extract_code_from_response(response) == "def migrate(input_record: str) -> str:\n    return input_record\n"


def test_model_rollout_uses_provider_response_and_records_prompt():
    task = all_tasks()[0]
    provider = StaticResponseProvider(
        name="fixture",
        response=json.dumps({"code": solution_for_task(task)}),
    )

    trajectory = run_model_rollout(task=task, provider=provider)

    assert trajectory["policy"] == "fixture"
    assert trajectory["final"]["public_score"] == 1.0
    assert trajectory["model_turns"][0]["provider"] == "fixture"
    assert "PAYROLL.cbl" in trajectory["model_turns"][0]["prompt"]
    assert [step["tool_name"] for step in trajectory["steps"]][-3:] == [
        "write_python_solution",
        "run_visible_tests",
        "submit_final",
    ]


def test_provider_factory_requires_azure_environment():
    try:
        create_provider("azure-openai", {})
    except ValueError as exc:
        assert "AZURE_OPENAI_ENDPOINT" in str(exc)
    else:
        raise AssertionError("expected missing Azure configuration to fail")


def test_repair_rollout_uses_visible_diff_before_second_draft():
    task = all_tasks()[0]
    provider = SequenceResponseProvider(
        name="fixture-repair",
        responses=[
            json.dumps({"code": "def migrate(input_record: str) -> str:\n    return '0'\n"}),
            json.dumps({"code": solution_for_task(task)}),
        ],
    )

    trajectory = run_model_repair_rollout(task=task, provider=provider, max_repairs=1)

    assert trajectory["final"]["public_score"] == 1.0
    assert len(trajectory["model_turns"]) == 2
    assert "field_diffs" in trajectory["model_turns"][1]["prompt"]
    assert "inspect_diff" in [step["tool_name"] for step in trajectory["steps"]]


def test_repair_rollout_includes_syntax_status_when_no_case_failures():
    task = all_tasks()[0]
    provider = RecordingProvider(
        responses=[
            json.dumps({"code": "def migrate(input_record: str) -> str:\n    return 'unterminated\n"}),
            json.dumps({"code": solution_for_task(task)}),
        ],
    )

    trajectory = run_model_repair_rollout(task=task, provider=provider, max_repairs=1)

    assert trajectory["final"]["public_score"] == 1.0
    assert len(provider.prompts) == 2
    assert '"syntax_ok": false' in provider.prompts[1]
    assert "unterminated string literal" in provider.prompts[1]

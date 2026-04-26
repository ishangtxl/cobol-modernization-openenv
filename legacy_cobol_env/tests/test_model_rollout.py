import json

from legacy_cobol_env.eval.model_rollout import extract_code_from_response, run_model_repair_rollout, run_model_rollout
from legacy_cobol_env.eval.oracle_solutions import solution_for_task
from legacy_cobol_env.eval.providers import (
    HuggingFaceChatProvider,
    LocalTransformersProvider,
    SequenceResponseProvider,
    StaticResponseProvider,
    _chat_completion_content,
    create_provider,
)
from legacy_cobol_env.server.task_bank import all_tasks, load_task


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


def test_extract_code_from_fenced_json_with_python_escaped_single_quotes():
    response = """```json
{
  "code": "from decimal import Decimal\\n\\ndef migrate(input_record: str) -> str:\\n    return f'{Decimal(\\'0.01\\')}'\\n"
}
```"""

    code = extract_code_from_response(response)

    assert code.startswith("from decimal import Decimal")
    assert "def migrate" in code
    assert '"code"' not in code


def test_extract_code_removes_unused_disallowed_import_from_model_response():
    response = json.dumps(
        {
            "code": "def migrate(input_record: str) -> str:\n    return input_record\n\nfrom copy import deepcopy\n"
        }
    )

    code = extract_code_from_response(response)

    assert "from copy import deepcopy" not in code
    assert "def migrate" in code


def test_extract_code_keeps_used_disallowed_import_for_safety_check():
    response = json.dumps(
        {
            "code": "from copy import deepcopy\n\n\ndef migrate(input_record: str) -> str:\n    return deepcopy(input_record)\n"
        }
    )

    assert "from copy import deepcopy" in extract_code_from_response(response)


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


def test_invoice_rollout_prompt_includes_output_contract():
    task = load_task(task_id="invoice_occurs_001")
    provider = StaticResponseProvider(
        name="fixture",
        response=json.dumps({"code": solution_for_task(task)}),
    )

    trajectory = run_model_rollout(task=task, provider=provider)

    prompt = trajectory["model_turns"][0]["prompt"]
    assert "output_layout" in prompt
    assert "OUT-TOTAL" in prompt
    assert "OUT-ITEM-COUNT" in prompt
    assert "ITEM-PRICE" in prompt
    assert "TAX-CODE-KEY" in prompt
    assert "Allowed imports: decimal, datetime, math, re, typing." in prompt
    assert "PIC fields with V use an implied decimal point" in prompt
    assert "fixed-width numeric outputs are digits only" in prompt
    assert "OUT-FLAG is H when INVOICE-TOTAL >= 1000.00, otherwise L" in prompt
    assert 'ITEM-PRICE: PIC 9(4)V99 has implied scale 2; parse raw digits with Decimal(int(slice)) / Decimal("100").' in prompt
    assert "OUT-TOTAL: PIC 9(7)V99 is 9 fixed-width digits with implied scale 2; format scaled integer digits, not a decimal string." in prompt


def test_provider_factory_requires_azure_environment():
    try:
        create_provider("azure-openai", {})
    except ValueError as exc:
        assert "AZURE_OPENAI_ENDPOINT" in str(exc)
    else:
        raise AssertionError("expected missing Azure configuration to fail")


def test_provider_factory_requires_hf_chat_environment():
    try:
        create_provider("hf-chat", {})
    except ValueError as exc:
        assert "HF_MODEL" in str(exc)
        assert "HF_TOKEN" in str(exc)
    else:
        raise AssertionError("expected missing Hugging Face chat configuration to fail")


def test_provider_factory_allows_hf_chat_configuration():
    provider = create_provider(
        "hf-chat",
        {
            "HF_MODEL": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
            "HF_TOKEN": "token",
            "HF_PROVIDER": "auto",
            "HF_MAX_TOKENS": "2048",
            "HF_TEMPERATURE": "0.15",
            "HF_TOP_P": "0.9",
        },
    )

    assert isinstance(provider, HuggingFaceChatProvider)
    assert provider.model == "Qwen/Qwen3-Coder-30B-A3B-Instruct"
    assert provider.provider == "auto"
    assert provider.max_tokens == 2048
    assert provider.temperature == 0.15
    assert provider.top_p == 0.9


def test_chat_completion_content_accepts_object_and_dict_shapes():
    class Message:
        content = "object response"

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    assert _chat_completion_content(Response()) == "object response"
    assert _chat_completion_content({"choices": [{"message": {"content": "dict response"}}]}) == "dict response"


def test_provider_factory_allows_local_sampling_controls():
    provider = create_provider(
        "local-transformers",
        {
            "LOCAL_MODEL_PATH": "/tmp/adapter",
            "LOCAL_BASE_MODEL_PATH": "Qwen/Qwen2.5-Coder-7B-Instruct",
            "LOCAL_DO_SAMPLE": "1",
            "LOCAL_TEMPERATURE": "0.2",
            "LOCAL_TOP_P": "0.9",
        },
    )

    assert isinstance(provider, LocalTransformersProvider)
    assert provider.do_sample is True
    assert provider.temperature == 0.2
    assert provider.top_p == 0.9


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


def test_repair_prompt_includes_direct_numeric_diff_guidance():
    task = load_task(task_id="invoice_occurs_001")
    provider = RecordingProvider(
        responses=[
            json.dumps(
                {
                    "code": "from decimal import Decimal\n\n"
                    "def migrate(input_record: str) -> str:\n"
                    "    return input_record[0:6] + '036480.0202H'\n"
                }
            ),
            json.dumps({"code": solution_for_task(task)}),
        ],
    )

    run_model_repair_rollout(task=task, provider=provider, max_repairs=1)

    repair_prompt = provider.prompts[1]
    assert "Do not return the previous code unchanged" in repair_prompt
    assert "If an expected numeric output is all digits but the actual output contains a decimal point" in repair_prompt
    assert 'ITEM-PRICE: PIC 9(4)V99 has implied scale 2; parse raw digits with Decimal(int(slice)) / Decimal("100").' in repair_prompt
    assert "OUT-TOTAL: PIC 9(7)V99 is 9 fixed-width digits with implied scale 2; format scaled integer digits, not a decimal string." in repair_prompt


def test_repair_prompt_includes_runtime_slice_error_guidance():
    task = load_task(task_id="invoice_occurs_001")
    provider = RecordingProvider(
        responses=[
            json.dumps(
                {
                    "code": "def migrate(input_record: str) -> str:\n"
                    "    return ''.join(str(i) for i in range(0, 36, 9)[:input_record[6:8]])\n"
                }
            ),
            json.dumps({"code": solution_for_task(task)}),
        ],
    )

    run_model_repair_rollout(task=task, provider=provider, max_repairs=1)

    repair_prompt = provider.prompts[1]
    assert "slice indices must be integers" in repair_prompt
    assert "convert ITEM-COUNT with int(input_record[6:8]) before using it" in repair_prompt
    assert "use range(count) with start = 8 + idx * 9" in repair_prompt


def test_repair_prompt_includes_decimal_to_string_guidance():
    task = load_task(task_id="invoice_occurs_001")
    provider = RecordingProvider(
        responses=[
            json.dumps(
                {
                    "code": "from decimal import Decimal\n\n"
                    "def migrate(input_record: str) -> str:\n"
                    "    amount = Decimal('12.34')\n"
                    "    return input_record[0:6] + amount.to_string(min_precision=9) + '00L'\n"
                }
            ),
            json.dumps({"code": solution_for_task(task)}),
        ],
    )

    run_model_repair_rollout(task=task, provider=provider, max_repairs=1)

    repair_prompt = provider.prompts[1]
    assert "object has no attribute 'to_string'" in repair_prompt
    assert "do not use Decimal.to_string" in repair_prompt
    assert "format(int(cents), \"09d\")" in repair_prompt


def test_invoice_repair_rollout_has_step_budget_for_diff_and_final_submission():
    task = load_task(task_id="invoice_occurs_001")
    provider = SequenceResponseProvider(
        name="invoice-repair",
        responses=[
            json.dumps({"code": "def migrate(input_record: str) -> str:\n    return '0'\n"}),
            json.dumps({"code": solution_for_task(task)}),
        ],
    )

    trajectory = run_model_repair_rollout(task=task, provider=provider, max_repairs=1)

    assert trajectory["final"]["public_score"] == 1.0
    step_names = [step["tool_name"] for step in trajectory["steps"]]
    assert "inspect_diff" in step_names
    assert step_names[-1] == "submit_final"


def test_invoice_repair_rollout_has_step_budget_for_two_repairs_and_final_submission():
    task = load_task(task_id="invoice_occurs_001")
    provider = SequenceResponseProvider(
        name="invoice-two-repairs",
        responses=[
            json.dumps(
                {
                    "code": "def migrate(input_record: str) -> str:\n"
                    "    total = Decimal('0.00')\n"
                    "    return input_record[0:6] + '00000000000L'\n"
                }
            ),
            json.dumps(
                {
                    "code": "from decimal import Decimal\n\n"
                    "def migrate(input_record: str) -> str:\n"
                    "    return input_record[0:6] + '000000.0000H'\n"
                }
            ),
            json.dumps({"code": solution_for_task(task)}),
        ],
    )

    trajectory = run_model_repair_rollout(task=task, provider=provider, max_repairs=2)

    assert trajectory["final"]["public_score"] == 1.0
    assert len(trajectory["model_turns"]) == 3
    assert [step["tool_name"] for step in trajectory["steps"]][-1] == "submit_final"


def test_invoice_repair_rollout_has_step_budget_for_three_repairs_and_final_submission():
    task = load_task(task_id="invoice_occurs_001")
    bad_code = "def migrate(input_record: str) -> str:\n    return '0'\n"
    provider = SequenceResponseProvider(
        name="invoice-three-repairs",
        responses=[
            json.dumps({"code": bad_code}),
            json.dumps({"code": bad_code}),
            json.dumps({"code": bad_code}),
            json.dumps({"code": solution_for_task(task)}),
        ],
    )

    trajectory = run_model_repair_rollout(task=task, provider=provider, max_repairs=3)

    assert trajectory["final"]["public_score"] == 1.0
    assert len(trajectory["model_turns"]) == 4
    assert [step["tool_name"] for step in trajectory["steps"]][-1] == "submit_final"

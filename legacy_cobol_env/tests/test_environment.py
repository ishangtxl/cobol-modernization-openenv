from openenv.core.env_server.mcp_types import CallToolAction, ListToolsAction

from legacy_cobol_env.server.legacy_cobol_env_environment import LegacyCobolEnvironment
from legacy_cobol_env.server.task_bank import all_tasks, generate_fresh_tests


GOOD_SOLUTION = r"""
from decimal import Decimal, ROUND_HALF_UP


def migrate(input_record: str) -> str:
    emp_id = input_record[0:6]
    emp_name = input_record[6:18]
    gross = Decimal(int(input_record[18:27])) / Decimal("100")
    tax_rate = Decimal(int(input_record[27:31])) / Decimal("1000")
    raw_deductions = input_record[31:39]
    sign = -1 if raw_deductions[0] == "-" else 1
    deductions = Decimal(sign * int(raw_deductions[1:])) / Decimal("100")
    bonus_flag = input_record[39:40]

    tax = (gross * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net = gross - tax - deductions
    if bonus_flag == "Y":
        net += Decimal("50.00")
    if net < 0:
        net = Decimal("0.00")

    if net >= Decimal("5000.00"):
        category = "H"
    elif net >= Decimal("2500.00"):
        category = "M"
    else:
        category = "L"

    cents = int((net * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{emp_id}{emp_name[:12].ljust(12)}{cents:09d}{category}"
"""


def call(env: LegacyCobolEnvironment, tool_name: str, **arguments):
    obs = env.step(CallToolAction(tool_name=tool_name, arguments=arguments))
    return obs.result.data


def reset_ticket(env: LegacyCobolEnvironment, **kwargs):
    obs = env.reset(**kwargs)
    return obs.result["ticket"]


def test_lists_workbench_tools():
    env = LegacyCobolEnvironment()
    env.reset(task_id="payroll_net_pay_001")

    obs = env.step(ListToolsAction())
    names = {tool.name for tool in obs.tools}

    assert "read_cobol_file" in names
    assert "submit_final" in names
    assert "reset" not in names


def test_good_solution_passes_visible_hidden_and_fresh_tests():
    env = LegacyCobolEnvironment()
    env.reset(task_id="payroll_net_pay_001")

    written = call(env, "write_python_solution", code=GOOD_SOLUTION)
    visible = call(env, "run_visible_tests")
    final = call(env, "submit_final", draft_id=written["draft_id"])

    assert visible["passed"] == visible["total"]
    assert final["public_score"] == 1.0
    assert final["accepted"] is True
    assert env.state.done is True


def test_bad_solution_gets_actionable_visible_diff():
    env = LegacyCobolEnvironment()
    env.reset(task_id="payroll_net_pay_001")

    call(env, "write_python_solution", code="def migrate(input_record: str) -> str:\n    return input_record.strip()\n")
    visible = call(env, "run_visible_tests")
    diff = call(env, "inspect_diff", case_id=visible["failures"][0]["case_id"])

    assert visible["passed"] == 0
    assert any(item["field"] == "OUT-NET-PAY" for item in diff["field_diffs"])


def test_forbidden_import_is_blocked():
    env = LegacyCobolEnvironment()
    env.reset(task_id="payroll_net_pay_001")

    code = "import os\ndef migrate(input_record: str) -> str:\n    return os.getcwd()\n"
    written = call(env, "write_python_solution", code=code)
    visible = call(env, "run_visible_tests", draft_id=written["draft_id"])

    assert written["safety_ok"] is False
    assert visible["safety_ok"] is False
    assert "forbidden import" in visible["error"]


def test_task_bank_has_six_distinct_families_with_fresh_tests():
    tasks = all_tasks()

    assert len(tasks) == 6
    assert len({task.family_id for task in tasks}) == 6
    for task in tasks:
        assert task.visible_tests
        assert task.hidden_tests
        assert generate_fresh_tests(task)
        assert task.metadata["output_width"] == task.metadata["output_layout"][-1]["end"]


def test_reset_can_select_each_family_and_parse_its_copybook_layout():
    for task in all_tasks():
        env = LegacyCobolEnvironment()
        ticket = reset_ticket(env, task_id=task.task_id)
        copybook = ticket["available_copybooks"][0]

        layout = call(env, "parse_copybook_layout", filename=copybook)

        assert ticket["task_id"] == task.task_id
        assert layout["record_name"] == task.metadata["record_name"]
        assert layout["total_width"] == task.metadata["input_width"]


def test_task_metadata_includes_difficulty_and_rule_visibility_split():
    expected = {
        "customer_format_001": "easy",
        "payroll_net_pay_001": "medium",
        "claims_eligibility_001": "medium",
        "account_status_001": "medium",
        "date_normalization_001": "medium",
        "invoice_occurs_001": "hard",
    }

    for task in all_tasks():
        assert task.metadata["difficulty"] == expected[task.task_id]
        assert task.metadata["reference_rules"]
        assert task.metadata["agent_hints"]
        assert task.metadata["business_rules"] == task.metadata["agent_hints"]


def test_invoice_task_uses_multiple_source_and_copybook_artifacts():
    invoice = next(task for task in all_tasks() if task.task_id == "invoice_occurs_001")

    assert sorted(invoice.cobol_files) == ["INVTOTAL.cbl", "TAXRATE.cbl"]
    assert sorted(invoice.copybooks) == ["INVOICE_REC.cpy", "TAX_CODE.cpy"]


def test_invoice_copybook_layout_exposes_occurs_child_offsets():
    env = LegacyCobolEnvironment()
    reset_ticket(env, task_id="invoice_occurs_001")

    invoice_layout = call(env, "parse_copybook_layout", filename="INVOICE_REC.cpy")
    line_items = next(field for field in invoice_layout["fields"] if field["name"] == "LINE-ITEMS")

    assert line_items["stride"] == 9
    assert [child["name"] for child in line_items["children"]] == [
        "ITEM-QTY",
        "ITEM-PRICE",
        "TAX-CODE",
    ]
    assert line_items["children"][1]["start"] == 2
    assert line_items["children"][1]["end"] == 8
    assert line_items["children"][2]["start"] == 8
    assert line_items["children"][2]["end"] == 9


def test_tax_code_copybook_uses_tax_code_table_layout():
    env = LegacyCobolEnvironment()
    reset_ticket(env, task_id="invoice_occurs_001")

    layout = call(env, "parse_copybook_layout", filename="TAX_CODE.cpy")

    assert layout["record_name"] == "TAX-CODE-TABLE"
    assert [field["name"] for field in layout["fields"]] == ["TAX-CODE-ENTRIES"]
    assert [child["name"] for child in layout["fields"][0]["children"]] == [
        "TAX-CODE-KEY",
        "TAX-RATE",
    ]


def test_reset_ticket_exposes_output_contract_without_test_cases():
    env = LegacyCobolEnvironment()
    ticket = reset_ticket(env, task_id="invoice_occurs_001")

    assert ticket["output_width"] == 18
    assert [field["name"] for field in ticket["output_layout"]] == [
        "OUT-INVOICE-ID",
        "OUT-TOTAL",
        "OUT-ITEM-COUNT",
        "OUT-FLAG",
    ]
    assert "visible_cases" not in ticket
    assert "hidden_cases" not in ticket


def test_invoice_visible_hints_do_not_expose_exact_tax_rates_or_formula():
    invoice = next(task for task in all_tasks() if task.task_id == "invoice_occurs_001")
    visible_hint_text = " ".join(invoice.metadata["agent_hints"])

    assert "1.075" not in visible_hint_text
    assert "7.5" not in visible_hint_text
    assert "multiply" not in visible_hint_text.lower()
    assert "ROUND" not in visible_hint_text.upper()


def test_visible_literal_hardcoding_penalizes_final_component():
    env = LegacyCobolEnvironment()
    env.reset(task_id="customer_format_001")
    task = env._task
    visible = task.visible_tests[0]
    code = f"""
def migrate(input_record: str) -> str:
    if input_record.startswith({visible.input_record[:5]!r}):
        return {visible.expected_output!r}
    return ' ' * {task.metadata["output_width"]}
"""

    written = call(env, "write_python_solution", code=code)
    final = call(env, "submit_final", draft_id=written["draft_id"])

    assert final["components"]["anti_hardcoding"] == 0.0

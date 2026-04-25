"""Run provider-backed code-generation rollouts against the workbench."""

from __future__ import annotations

import json
import ast
from typing import Any

from legacy_cobol_env.eval.providers import TextProvider
from legacy_cobol_env.eval.trajectory import call_tool
from legacy_cobol_env.server.sandbox import ALLOWED_IMPORTS, FORBIDDEN_IMPORTS
from legacy_cobol_env.server.legacy_cobol_env_environment import LegacyCobolEnvironment
from legacy_cobol_env.server.task_bank import TaskInstance


ALLOWED_IMPORT_TEXT = ", ".join(name for name in ["decimal", "datetime", "math", "re", "typing"] if name in ALLOWED_IMPORTS)
COBOL_NUMERIC_RULE = (
    "PIC fields with V use an implied decimal point: parse them by integer digits and scale; "
    "fixed-width numeric outputs are digits only, zero-padded to their field length, with no decimal point or spaces."
)


def extract_code_from_response(response: str) -> str:
    candidates = [response.strip(), _strip_fence(response.strip())]
    start = response.find("{")
    end = response.rfind("}")
    if 0 <= start < end:
        candidates.append(response[start : end + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("code"), str):
            return _remove_unused_disallowed_imports(data["code"])

    unfenced = _strip_fence(response.strip())
    if "def migrate" in unfenced:
        return _remove_unused_disallowed_imports(unfenced)
    raise ValueError("model response did not contain JSON with a code field")


def run_model_rollout(
    task: TaskInstance,
    provider: TextProvider,
) -> dict[str, Any]:
    env = LegacyCobolEnvironment()
    reset_observation = env.reset(task_id=task.task_id)
    ticket = reset_observation.result["ticket"]
    steps: list[dict[str, Any]] = []
    context: dict[str, Any] = {"cobol_files": {}, "copybooks": {}, "layouts": {}, "business_rules": []}

    def record(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result, reward, done = call_tool(env, tool_name, **arguments)
        saved_arguments = dict(arguments)
        if "code" in saved_arguments:
            saved_arguments["code_chars"] = len(saved_arguments.pop("code"))
        steps.append(
            {
                "tool_name": tool_name,
                "arguments": saved_arguments,
                "reward": reward,
                "done": done,
                "result": result,
            }
        )
        return result

    for filename in ticket["available_files"]:
        result = record("read_cobol_file", {"filename": filename})
        context["cobol_files"][filename] = result["content"]
    for filename in ticket["available_copybooks"]:
        copybook = record("read_copybook", {"filename": filename})
        layout = record("parse_copybook_layout", {"filename": filename})
        context["copybooks"][filename] = copybook["content"]
        context["layouts"][filename] = layout
    rules = record("inspect_business_rules", {})
    context["business_rules"] = rules["rules"]

    prompt = build_migration_prompt(ticket, context)
    response = provider.generate(prompt)
    code = extract_code_from_response(response)
    written = record("write_python_solution", {"code": code})
    visible = record("run_visible_tests", {"draft_id": written["draft_id"]})
    final = record("submit_final", {"draft_id": written["draft_id"]})

    return {
        "policy": provider.name,
        "task_id": task.task_id,
        "family_id": task.family_id,
        "ticket": ticket,
        "model_turns": [
            {
                "provider": provider.name,
                "prompt": prompt,
                "response": response,
                "code_chars": len(code),
            }
        ],
        "visible": {
            "passed": visible["passed"],
            "total": visible["total"],
            "pass_rate": visible["pass_rate"],
            "failures": visible["failures"],
        },
        "final": {
            "public_score": final["public_score"],
            "accepted": final["accepted"],
            "components": final["components"],
            "hidden_passed": final["hidden_passed"],
            "hidden_total": final["hidden_total"],
            "fresh_passed": final["fresh_passed"],
            "fresh_total": final["fresh_total"],
        },
        "steps": steps,
    }


def run_model_repair_rollout(
    task: TaskInstance,
    provider: TextProvider,
    max_repairs: int = 1,
) -> dict[str, Any]:
    env = LegacyCobolEnvironment()
    reset_observation = env.reset(task_id=task.task_id)
    ticket = reset_observation.result["ticket"]
    steps: list[dict[str, Any]] = []
    model_turns: list[dict[str, Any]] = []
    context: dict[str, Any] = {"cobol_files": {}, "copybooks": {}, "layouts": {}, "business_rules": []}

    def record(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result, reward, done = call_tool(env, tool_name, **arguments)
        saved_arguments = dict(arguments)
        if "code" in saved_arguments:
            saved_arguments["code_chars"] = len(saved_arguments.pop("code"))
        steps.append(
            {
                "tool_name": tool_name,
                "arguments": saved_arguments,
                "reward": reward,
                "done": done,
                "result": result,
            }
        )
        return result

    for filename in ticket["available_files"]:
        result = record("read_cobol_file", {"filename": filename})
        context["cobol_files"][filename] = result["content"]
    for filename in ticket["available_copybooks"]:
        copybook = record("read_copybook", {"filename": filename})
        layout = record("parse_copybook_layout", {"filename": filename})
        context["copybooks"][filename] = copybook["content"]
        context["layouts"][filename] = layout
    rules = record("inspect_business_rules", {})
    context["business_rules"] = rules["rules"]

    prompt = build_migration_prompt(ticket, context)
    response = provider.generate(prompt)
    code = extract_code_from_response(response)
    model_turns.append({"provider": provider.name, "prompt": prompt, "response": response, "code_chars": len(code)})
    written = record("write_python_solution", {"code": code})
    visible = record("run_visible_tests", {"draft_id": written["draft_id"]})

    for _ in range(max_repairs):
        if visible["pass_rate"] == 1.0:
            break
        diffs = [record("inspect_diff", {"case_id": failure["case_id"]}) for failure in visible["failures"][:2]]
        repair_prompt = build_repair_prompt(ticket, context, code, visible, diffs)
        response = provider.generate(repair_prompt)
        code = extract_code_from_response(response)
        model_turns.append({"provider": provider.name, "prompt": repair_prompt, "response": response, "code_chars": len(code)})
        written = record("write_python_solution", {"code": code})
        visible = record("run_visible_tests", {"draft_id": written["draft_id"]})

    final = record("submit_final", {"draft_id": written["draft_id"]})
    return {
        "policy": provider.name,
        "task_id": task.task_id,
        "family_id": task.family_id,
        "ticket": ticket,
        "model_turns": model_turns,
        "visible": {
            "passed": visible["passed"],
            "total": visible["total"],
            "pass_rate": visible["pass_rate"],
            "failures": visible["failures"],
        },
        "final": {
            "public_score": final["public_score"],
            "accepted": final["accepted"],
            "components": final["components"],
            "hidden_passed": final["hidden_passed"],
            "hidden_total": final["hidden_total"],
            "fresh_passed": final["fresh_passed"],
            "fresh_total": final["fresh_total"],
        },
        "steps": steps,
    }


def build_migration_prompt(ticket: dict[str, Any], context: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "You are migrating a legacy COBOL routine into Python.",
            "Return only JSON in this shape: {\"code\": \"...python source...\"}.",
            "The Python source must define migrate(input_record: str) -> str.",
            f"Allowed imports: {ALLOWED_IMPORT_TEXT}. Do not import any other modules.",
            COBOL_NUMERIC_RULE,
            "Returned records must match output_width exactly; never append newline characters.",
            f"Ticket:\n{json.dumps(ticket, indent=2)}",
            f"COBOL files:\n{json.dumps(context['cobol_files'], indent=2)}",
            f"Copybooks:\n{json.dumps(context['copybooks'], indent=2)}",
            f"Parsed layouts:\n{json.dumps(context['layouts'], indent=2)}",
            f"Business rules:\n{json.dumps(context['business_rules'], indent=2)}",
        ]
    )


def build_repair_prompt(
    ticket: dict[str, Any],
    context: dict[str, Any],
    previous_code: str,
    visible: dict[str, Any],
    diffs: list[dict[str, Any]],
) -> str:
    return "\n\n".join(
        [
            "Repair the Python migration after visible test feedback.",
            "Return only JSON in this shape: {\"code\": \"...python source...\"}.",
            "The Python source must define migrate(input_record: str) -> str.",
            f"Allowed imports: {ALLOWED_IMPORT_TEXT}. Do not import any other modules.",
            COBOL_NUMERIC_RULE,
            "Returned records must match output_width exactly; never append newline characters.",
            f"Ticket:\n{json.dumps(ticket, indent=2)}",
            f"COBOL files:\n{json.dumps(context['cobol_files'], indent=2)}",
            f"Copybooks:\n{json.dumps(context['copybooks'], indent=2)}",
            f"Parsed layouts:\n{json.dumps(context['layouts'], indent=2)}",
            f"Business rules:\n{json.dumps(context['business_rules'], indent=2)}",
            f"Previous code:\n{previous_code}",
            f"Visible test status:\n{json.dumps(_visible_status_for_prompt(visible), indent=2)}",
            f"Visible failures:\n{json.dumps(visible['failures'], indent=2)}",
            f"Inspected field_diffs:\n{json.dumps(diffs, indent=2)}",
        ]
    )


def _visible_status_for_prompt(visible: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "passed",
        "total",
        "pass_rate",
        "syntax_ok",
        "safety_ok",
        "interface_ok",
        "timed_out",
        "error",
    ]
    return {key: visible.get(key) for key in keys if key in visible}


def _remove_unused_disallowed_imports(code: str) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    import_lines: set[int] = set()
    imported_names: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORTS or root not in ALLOWED_IMPORTS:
                    imported_names[alias.asname or root] = root
            if node.lineno:
                import_lines.add(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root in FORBIDDEN_IMPORTS or root not in ALLOWED_IMPORTS:
                for alias in node.names:
                    imported_names[alias.asname or alias.name] = root
                if node.lineno:
                    import_lines.add(node.lineno)

    if not imported_names:
        return code

    used_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in imported_names and node.lineno not in import_lines
    }
    removable_lines = {
        line
        for line in import_lines
        if not any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and node.lineno == line
            and any((alias.asname or alias.name.split(".", 1)[0]) in used_names for alias in node.names)
            for node in tree.body
        )
    }
    if not removable_lines:
        return code

    lines = code.splitlines(keepends=True)
    return "".join(line for index, line in enumerate(lines, start=1) if index not in removable_lines)


def _strip_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines:
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)

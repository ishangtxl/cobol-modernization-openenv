"""Run provider-backed code-generation rollouts against the workbench."""

from __future__ import annotations

import json
from typing import Any

from legacy_cobol_env.eval.providers import TextProvider
from legacy_cobol_env.eval.trajectory import call_tool
from legacy_cobol_env.server.legacy_cobol_env_environment import LegacyCobolEnvironment
from legacy_cobol_env.server.task_bank import TaskInstance


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
            return data["code"]

    unfenced = _strip_fence(response.strip())
    if "def migrate" in unfenced:
        return unfenced
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
            f"Ticket:\n{json.dumps(ticket, indent=2)}",
            f"COBOL files:\n{json.dumps(context['cobol_files'], indent=2)}",
            f"Copybooks:\n{json.dumps(context['copybooks'], indent=2)}",
            f"Parsed layouts:\n{json.dumps(context['layouts'], indent=2)}",
            f"Business rules:\n{json.dumps(context['business_rules'], indent=2)}",
            f"Previous code:\n{previous_code}",
            f"Visible failures:\n{json.dumps(visible['failures'], indent=2)}",
            f"Inspected field_diffs:\n{json.dumps(diffs, indent=2)}",
        ]
    )


def _strip_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines:
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)

"""Legacy COBOL Migration Workbench OpenEnv environment."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastmcp import FastMCP
from fastmcp.client.client import CallToolResult
from mcp.types import TextContent
from openenv.core.env_server.mcp_environment import MCPEnvironment
from openenv.core.env_server.mcp_types import CallToolObservation
from openenv.core.env_server.types import Action, Observation

try:
    from ..models import (
        FinalSubmissionResult,
        LegacyCobolState,
        RewardComponents,
        TerminalStepResult,
    )
    from .sandbox import EvaluationResult, evaluate_code
    from .task_bank import copybook_layout_for, generate_fresh_tests, load_task
except ImportError:
    from models import (
        FinalSubmissionResult,
        LegacyCobolState,
        RewardComponents,
        TerminalStepResult,
    )
    from server.sandbox import EvaluationResult, evaluate_code
    from server.task_bank import copybook_layout_for, generate_fresh_tests, load_task


MAX_STEPS = 24


class LegacyCobolEnvironment(MCPEnvironment):
    """Tool-mediated migration environment for legacy modernization tasks."""

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self) -> None:
        self._task = load_task()
        self._state = LegacyCobolState(episode_id=str(uuid4()))
        self._drafts: dict[int, str] = {}
        self._last_visible_results: dict[str, EvaluationResult] = {}
        self._last_reward = 0.0
        self._last_summary = "Environment initialized."

        mcp = FastMCP("legacy_cobol_env")

        @mcp.tool
        def read_cobol_file(filename: str) -> dict[str, Any]:
            """Read a COBOL source artifact for the current migration ticket."""
            return self._read_cobol_file(filename)

        @mcp.tool
        def read_copybook(filename: str) -> dict[str, Any]:
            """Read a COBOL copybook artifact for the current migration ticket."""
            return self._read_copybook(filename)

        @mcp.tool
        def parse_copybook_layout(filename: str) -> dict[str, Any]:
            """Return structured offsets and types for a copybook."""
            return self._parse_copybook_layout(filename)

        @mcp.tool
        def inspect_business_rules() -> dict[str, Any]:
            """Inspect business rules inferred during task authoring."""
            return self._inspect_business_rules()

        @mcp.tool
        def write_python_solution(code: str) -> dict[str, Any]:
            """Store a candidate Python migration solution."""
            return self._write_python_solution(code)

        @mcp.tool
        def run_visible_tests(draft_id: int | None = None) -> dict[str, Any]:
            """Run visible tests against the current or specified draft."""
            return self._run_visible_tests(draft_id=draft_id)

        @mcp.tool
        def inspect_diff(case_id: str) -> dict[str, Any]:
            """Inspect a structured diff for a failed visible test case."""
            return self._inspect_diff(case_id)

        @mcp.tool
        def submit_final(draft_id: int | None = None) -> dict[str, Any]:
            """Submit the current or specified draft for hidden and fresh scoring."""
            return self._submit_final(draft_id=draft_id)

        super().__init__(mcp)

    def reset(
        self,
        seed: int | None = None,
        episode_id: str | None = None,
        **kwargs: Any,
    ) -> Observation:
        self._task = load_task(seed=seed, task_id=kwargs.get("task_id"))
        self._drafts = {}
        self._last_visible_results = {}
        self._last_reward = 0.0
        self._last_summary = "Ready for migration."
        self._state = LegacyCobolState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=self._task.task_id,
            done=False,
            last_result_summary=self._last_summary,
        )
        return CallToolObservation(
            tool_name="episode_start",
            result={"ticket": self._initial_ticket()},
            done=False,
            reward=0.0,
        )

    def step(
        self,
        action: Action,
        timeout_s: float | None = None,
        **kwargs: Any,
    ) -> Observation:
        blocked = self._blocked_step_observation(action)
        if blocked is not None:
            return blocked
        self._state.step_count += 1
        observation = super().step(action, timeout_s=timeout_s, **kwargs)
        observation.reward = self._last_reward
        observation.done = self._state.done
        return observation

    async def step_async(
        self,
        action: Action,
        timeout_s: float | None = None,
        **kwargs: Any,
    ) -> Observation:
        blocked = self._blocked_step_observation(action)
        if blocked is not None:
            return blocked
        self._state.step_count += 1
        observation = await super().step_async(action, timeout_s=timeout_s, **kwargs)
        observation.reward = self._last_reward
        observation.done = self._state.done
        return observation

    def _step_impl(
        self,
        action: Action,
        timeout_s: float | None = None,
        **kwargs: Any,
    ) -> Observation:
        self._set_outcome("unsupported_action", 0.0, "Use MCP CallToolAction.")
        return Observation(
            done=self._state.done,
            reward=0.0,
            metadata={"error": f"Unsupported action type: {type(action).__name__}"},
        )

    @property
    def state(self) -> LegacyCobolState:
        return self._state

    def _initial_ticket(self) -> dict[str, Any]:
        return {
            "task_id": self._task.task_id,
            "family_id": self._task.family_id,
            "domain": self._task.domain,
            "ticket": self._task.ticket,
            "available_files": sorted(self._task.cobol_files),
            "available_copybooks": sorted(self._task.copybooks),
            "expected_callable": self._task.expected_callable,
            "visible_tests": len(self._task.visible_tests),
            "hidden_tests": len(self._task.hidden_tests),
            "input_width": self._task.metadata["input_width"],
            "output_width": self._task.metadata["output_width"],
            "output_layout": self._task.metadata["output_layout"],
            "max_steps": MAX_STEPS,
            "allowed_tools": [
                "read_cobol_file",
                "read_copybook",
                "parse_copybook_layout",
                "inspect_business_rules",
                "write_python_solution",
                "run_visible_tests",
                "inspect_diff",
                "submit_final",
            ],
        }

    def _set_outcome(
        self,
        tool_name: str,
        reward: float,
        summary: str,
        done: bool | None = None,
    ) -> None:
        self._last_reward = reward
        self._last_summary = summary
        self._state.last_tool = tool_name
        self._state.last_result_summary = summary
        if done is not None:
            self._state.done = done

    def _blocked_step_observation(self, action: Action) -> CallToolObservation | None:
        if self._state.done:
            return self._terminal_noop_observation(
                action,
                "episode is terminal; action was not executed",
            )

        if self._state.step_count >= MAX_STEPS:
            self._state.done = True
            self._last_reward = 0.0
            self._last_summary = "Max steps exceeded."
            self._state.last_result_summary = self._last_summary
            return self._terminal_noop_observation(
                action,
                f"max_steps={MAX_STEPS} exceeded; action was not executed",
            )

        return None

    def _terminal_noop_observation(self, action: Action, error: str) -> CallToolObservation:
        tool_name = getattr(action, "tool_name", type(action).__name__)
        return CallToolObservation(
            tool_name=tool_name,
            result=self._tool_result(TerminalStepResult(error=error).model_dump()),
            done=True,
            reward=0.0,
        )

    def _tool_result(self, data: dict[str, Any]) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text=str(data))],
            structured_content={"result": data},
            meta=None,
            data=data,
            is_error=not data.get("ok", True),
        )

    def _read_cobol_file(self, filename: str) -> dict[str, Any]:
        content = self._task.cobol_files.get(filename)
        if content is None:
            self._set_outcome("read_cobol_file", 0.0, "Unknown COBOL file.")
            return {"ok": False, "error": f"unknown COBOL file: {filename}"}

        first_read = filename not in self._state.files_read
        if filename not in self._state.files_read:
            self._state.files_read.append(filename)
        reward = 0.02 if first_read else 0.0
        summary = f"Read {filename}." if first_read else f"{filename} was already read."
        self._set_outcome("read_cobol_file", reward, summary)
        return {"ok": True, "filename": filename, "content": content, "truncated": False}

    def _read_copybook(self, filename: str) -> dict[str, Any]:
        content = self._task.copybooks.get(filename)
        if content is None:
            self._set_outcome("read_copybook", 0.0, "Unknown copybook.")
            return {"ok": False, "error": f"unknown copybook: {filename}"}

        first_read = filename not in self._state.copybooks_read
        if filename not in self._state.copybooks_read:
            self._state.copybooks_read.append(filename)
        reward = 0.02 if first_read else 0.0
        summary = f"Read {filename}." if first_read else f"{filename} was already read."
        self._set_outcome("read_copybook", reward, summary)
        return {"ok": True, "filename": filename, "content": content}

    def _parse_copybook_layout(self, filename: str) -> dict[str, Any]:
        if filename not in self._task.copybooks:
            self._set_outcome("parse_copybook_layout", 0.0, "Unknown copybook.")
            return {"ok": False, "error": f"unknown copybook: {filename}"}

        first_parse = filename not in self._state.layouts_parsed
        if filename not in self._state.layouts_parsed:
            self._state.layouts_parsed.append(filename)
        reward = 0.03 if first_parse else 0.0
        summary = (
            f"Parsed layout for {filename}."
            if first_parse
            else f"Layout for {filename} was already parsed."
        )
        self._set_outcome(
            "parse_copybook_layout",
            reward,
            summary,
        )
        layout = copybook_layout_for(self._task, filename)
        return {
            "ok": True,
            "filename": filename,
            **layout,
        }

    def _inspect_business_rules(self) -> dict[str, Any]:
        first_inspection = not self._state.business_rules_inspected
        self._state.business_rules_inspected = True
        reward = 0.01 if first_inspection else 0.0
        summary = (
            "Inspected business rules."
            if first_inspection
            else "Business rules were already inspected."
        )
        self._set_outcome("inspect_business_rules", reward, summary)
        return {"ok": True, "rules": self._task.metadata["business_rules"]}

    def _write_python_solution(self, code: str) -> dict[str, Any]:
        draft_id = len(self._drafts) + 1
        self._drafts[draft_id] = code
        self._state.draft_count = len(self._drafts)

        syntax_ok = True
        safety_ok = True
        safety_error = None
        try:
            from .sandbox import check_candidate_safety
        except ImportError:
            from server.sandbox import check_candidate_safety

        safety_ok, safety_error = check_candidate_safety(code)
        if safety_error and safety_error.startswith("syntax error"):
            syntax_ok = False

        reward = 0.02 if syntax_ok and safety_ok else 0.0
        summary = f"Stored draft {draft_id}."
        if not syntax_ok or not safety_ok:
            summary = f"Stored draft {draft_id}, but safety check failed."
        self._set_outcome("write_python_solution", reward, summary)
        return {
            "ok": True,
            "draft_id": draft_id,
            "syntax_ok": syntax_ok,
            "safety_ok": safety_ok,
            "error": safety_error,
        }

    def _run_visible_tests(self, draft_id: int | None = None) -> dict[str, Any]:
        selected_id, code_or_error = self._select_draft(draft_id)
        if selected_id is None:
            self._set_outcome("run_visible_tests", 0.0, "No draft available.")
            return {"ok": False, "error": code_or_error}

        result = evaluate_code(code_or_error, self._task.visible_tests)
        self._last_visible_results[str(selected_id)] = result
        previous_best = self._state.best_visible_pass_rate
        self._state.visible_runs += 1
        self._state.best_visible_pass_rate = max(
            self._state.best_visible_pass_rate,
            result.pass_rate,
        )
        improvement = max(0.0, result.pass_rate - previous_best)
        first_valid_run = (
            self._state.visible_runs == 1
            and result.safety_ok
            and result.interface_ok
            and not result.timed_out
        )
        reward = (0.02 if first_valid_run else 0.0) + (0.08 * improvement)
        reward = round(self._clamp_score(reward), 4)
        self._set_outcome(
            "run_visible_tests",
            reward,
            f"Visible tests: {result.passed}/{result.total}.",
        )
        return {
            "ok": result.safety_ok and result.interface_ok and not result.timed_out,
            "draft_id": selected_id,
            "passed": result.passed,
            "total": result.total,
            "pass_rate": result.pass_rate,
            "syntax_ok": result.syntax_ok,
            "safety_ok": result.safety_ok,
            "interface_ok": result.interface_ok,
            "timed_out": result.timed_out,
            "error": result.error,
            "failures": self._visible_failures(result),
        }

    def _inspect_diff(self, case_id: str) -> dict[str, Any]:
        latest = self._latest_visible_result()
        if latest is None:
            self._set_outcome("inspect_diff", 0.0, "No visible test run to inspect.")
            return {"ok": False, "error": "run visible tests before inspecting diffs"}

        case = next((item for item in latest.case_results if item.case_id == case_id), None)
        if case is None:
            self._set_outcome("inspect_diff", 0.0, "Unknown visible case.")
            return {"ok": False, "error": f"unknown visible case: {case_id}"}
        if case.passed:
            self._set_outcome("inspect_diff", 0.0, "Case already passed.")
            return {"ok": True, "case_id": case_id, "passed": True, "field_diffs": []}

        field_diffs = self._field_diffs(case)
        first_inspection = case_id not in self._state.diffs_inspected
        if first_inspection:
            self._state.diffs_inspected.append(case_id)
        reward = 0.02 if first_inspection else 0.0
        summary = (
            f"Inspected diff for {case_id}."
            if first_inspection
            else f"Diff for {case_id} was already inspected."
        )
        self._set_outcome("inspect_diff", reward, summary)
        return {
            "ok": True,
            "case_id": case_id,
            "passed": False,
            "input_summary": case.input_summary,
            "error": case.error,
            "field_diffs": field_diffs,
        }

    def _submit_final(self, draft_id: int | None = None) -> dict[str, Any]:
        selected_id, code_or_error = self._select_draft(draft_id)
        if selected_id is None:
            self._set_outcome("submit_final", 0.0, "No draft available.", done=True)
            return {"ok": False, "accepted": False, "error": code_or_error}

        hidden = evaluate_code(code_or_error, self._task.hidden_tests)
        fresh_tests = generate_fresh_tests(self._task)
        fresh = evaluate_code(code_or_error, fresh_tests)

        components = self._reward_components(hidden, fresh)
        components["anti_hardcoding"] = min(
            float(components.get("anti_hardcoding", 0.0)),
            self._anti_hardcoding_score(code_or_error, fresh),
        )
        components = RewardComponents.model_validate(
            {key: self._clamp_score(value) for key, value in components.items()}
        ).model_dump()
        final_reward = round(
            0.55 * components["hidden_correctness"]
            + 0.15 * components["fresh_correctness"]
            + 0.10 * components["interface_contract"]
            + 0.08 * components["type_and_layout_fidelity"]
            + 0.07 * components["anti_hardcoding"]
            + 0.05 * components["safety"],
            4,
        )
        final_reward = self._clamp_score(final_reward)

        self._state.final_score = final_reward
        self._state.reward_components = components
        self._set_outcome(
            "submit_final",
            final_reward,
            f"Final score {final_reward:.3f}.",
            done=True,
        )
        return FinalSubmissionResult(
            ok=True,
            accepted=final_reward >= 0.80,
            episode_done=True,
            public_score=final_reward,
            components=RewardComponents.model_validate(components),
            hidden_passed=hidden.passed,
            hidden_total=hidden.total,
            fresh_passed=fresh.passed,
            fresh_total=fresh.total,
            notes="Hidden and fresh case details are not revealed to the agent.",
        ).model_dump()

    def _select_draft(self, draft_id: int | None) -> tuple[int | None, str]:
        if not self._drafts:
            return None, "write_python_solution must be called before evaluation"
        selected = draft_id or max(self._drafts)
        code = self._drafts.get(selected)
        if code is None:
            return None, f"unknown draft_id: {selected}"
        return selected, code

    def _latest_visible_result(self) -> EvaluationResult | None:
        if not self._last_visible_results:
            return None
        latest_key = sorted(self._last_visible_results, key=int)[-1]
        return self._last_visible_results[latest_key]

    def _visible_failures(self, result: EvaluationResult) -> list[dict[str, Any]]:
        failures = []
        for item in result.case_results:
            if item.passed:
                continue
            failures.append(
                {
                    "case_id": item.case_id,
                    "input_summary": item.input_summary,
                    "expected_summary": self._summarize_output(item.expected),
                    "actual_summary": self._summarize_output(item.actual),
                    "error": item.error,
                }
            )
        return failures

    def _field_diffs(self, case: Any) -> list[dict[str, Any]]:
        if case.expected is None or case.actual is None:
            return [{"field": "runtime", "expected": case.expected, "actual": case.actual}]

        diffs = []
        for field in self._task.metadata["output_layout"]:
            expected = case.expected[field["start"] : field["end"]]
            actual = case.actual[field["start"] : field["end"]]
            if expected != actual:
                diffs.append(
                    {
                        "field": field["name"],
                        "expected": expected,
                        "actual": actual,
                        "hint": self._field_hint(field["name"]),
                    }
                )
        output_width = self._task.metadata["output_width"]
        if len(case.actual) != output_width:
            diffs.append(
                {
                    "field": "OUTPUT-RECORD",
                    "expected": f"{output_width} characters",
                    "actual": f"{len(case.actual)} characters",
                    "hint": "output must preserve the fixed-width record contract",
                }
            )
        return diffs

    def _reward_components(
        self,
        hidden: EvaluationResult,
        fresh: EvaluationResult,
    ) -> dict[str, float]:
        interface = 1.0 if hidden.interface_ok and fresh.interface_ok else 0.0
        safety = (
            1.0
            if hidden.safety_ok
            and fresh.safety_ok
            and not hidden.timed_out
            and not fresh.timed_out
            else 0.0
        )
        layout = self._layout_pass_rate(hidden)
        return {
            "hidden_correctness": round(hidden.pass_rate, 4),
            "fresh_correctness": round(fresh.pass_rate, 4),
            "interface_contract": interface,
            "type_and_layout_fidelity": round(layout, 4),
            "anti_hardcoding": round(fresh.pass_rate, 4),
            "safety": safety,
        }

    def _anti_hardcoding_score(self, code: str, fresh: EvaluationResult) -> float:
        if self._visible_literal_leaks(code):
            return 0.0
        return round(fresh.pass_rate, 4)

    def _visible_literal_leaks(self, code: str) -> list[str]:
        literals: set[str] = set()
        input_id_field = self._task.metadata["copybook_layout"][0]
        output_id_field = self._task.metadata["output_layout"][0]
        for case in self._task.visible_tests:
            literals.add(case.input_record)
            literals.add(case.expected_output)
            literals.add(case.input_record[input_id_field["start"] : input_id_field["end"]].strip())
            literals.add(case.expected_output[output_id_field["start"] : output_id_field["end"]].strip())

        return sorted(literal for literal in literals if len(literal) >= 5 and literal in code)

    def _clamp_score(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _layout_pass_rate(self, result: EvaluationResult) -> float:
        if result.total == 0:
            return 0.0
        ok = 0
        layout = self._task.metadata["output_layout"]
        numeric_names = set(self._task.metadata.get("numeric_output_fields", []))
        output_width = self._task.metadata["output_width"]
        fields_by_name = {item["name"]: item for item in layout}
        for item in result.case_results:
            if item.actual is None or len(item.actual) != output_width:
                continue
            numeric_ok = True
            for name in numeric_names:
                spec = fields_by_name[name]
                if not item.actual[spec["start"] : spec["end"]].isdigit():
                    numeric_ok = False
                    break
            if numeric_ok:
                ok += 1
        return ok / result.total

    def _summarize_output(self, output: str | None) -> str:
        if output is None:
            return "no output"
        output_width = self._task.metadata["output_width"]
        if len(output) != output_width:
            return f"length {len(output)} output: {output!r}"
        parts = []
        for spec in self._task.metadata["output_layout"][:4]:
            parts.append(f"{spec['name']}={output[spec['start']:spec['end']]}")
        return ", ".join(parts)

    def _field_hint(self, field_name: str) -> str:
        hints = dict(self._task.metadata.get("field_hints", {}))
        hints.update({
            "OUT-EMP-ID": "preserve the first 6 input bytes exactly",
            "OUT-EMP-NAME": "preserve/pad the 12-byte name field",
            "OUT-PAY-CATEGORY": "H >= 5000.00, M >= 2500.00, otherwise L",
        })
        return hints.get(field_name, "check fixed-width COBOL layout")

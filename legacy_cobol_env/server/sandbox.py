"""Small subprocess sandbox for evaluating submitted migration code."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .task_bank import TestCase


FORBIDDEN_IMPORTS = {
    "ctypes",
    "glob",
    "importlib",
    "inspect",
    "multiprocessing",
    "os",
    "pathlib",
    "pickle",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "tempfile",
}

ALLOWED_IMPORTS = {"datetime", "decimal", "math", "re", "typing"}

FORBIDDEN_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
    "vars",
}


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    input_summary: str
    expected: str | None = None
    actual: str | None = None
    error: str | None = None


@dataclass
class EvaluationResult:
    syntax_ok: bool
    safety_ok: bool
    interface_ok: bool
    timed_out: bool
    passed: int
    total: int
    case_results: list[CaseResult] = field(default_factory=list)
    error: str | None = None

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


def check_candidate_safety(code: str) -> tuple[bool, str | None]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"syntax error: {exc.msg}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORTS:
                    return False, f"forbidden import: {root}"
                if root not in ALLOWED_IMPORTS:
                    return False, f"import is not allowlisted: {root}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root in FORBIDDEN_IMPORTS:
                return False, f"forbidden import: {root}"
            if root not in ALLOWED_IMPORTS:
                return False, f"import is not allowlisted: {root}"
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
                return False, f"forbidden call: {func.id}"
            if isinstance(func, ast.Attribute) and func.attr.startswith("__"):
                return False, f"dunder attribute call is not allowed: {func.attr}"
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return False, f"dunder attribute access is not allowed: {node.attr}"

    return True, None


def evaluate_code(
    code: str,
    tests: list[TestCase],
    timeout_s: float = 2.0,
) -> EvaluationResult:
    safety_ok, safety_error = check_candidate_safety(code)
    if not safety_ok:
        syntax_ok = not (safety_error or "").startswith("syntax error")
        return EvaluationResult(
            syntax_ok=syntax_ok,
            safety_ok=False,
            interface_ok=False,
            timed_out=False,
            passed=0,
            total=len(tests),
            error=safety_error,
        )

    payload = [
        {
            "case_id": case.case_id,
            "input_record": case.input_record,
            "expected_output": case.expected_output,
            "summary": case.summary,
        }
        for case in tests
    ]

    runner = textwrap.dedent(
        """
        import importlib.util
        import json
        import traceback

        spec = importlib.util.spec_from_file_location("candidate", "candidate.py")
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            print(json.dumps({
                "interface_ok": False,
                "error": "import failed: " + repr(exc),
                "case_results": [],
            }))
            raise SystemExit(0)

        fn = getattr(module, "migrate", None)
        if not callable(fn):
            print(json.dumps({
                "interface_ok": False,
                "error": "missing callable: migrate",
                "case_results": [],
            }))
            raise SystemExit(0)

        tests = json.loads(TESTS_JSON)
        results = []
        for case in tests:
            try:
                actual_raw = fn(case["input_record"])
                actual = actual_raw if isinstance(actual_raw, str) else repr(actual_raw)
                passed = isinstance(actual_raw, str) and actual == case["expected_output"]
                results.append({
                    "case_id": case["case_id"],
                    "passed": passed,
                    "input_summary": case["summary"],
                    "expected": case["expected_output"],
                    "actual": actual,
                    "error": None,
                })
            except Exception:
                results.append({
                    "case_id": case["case_id"],
                    "passed": False,
                    "input_summary": case["summary"],
                    "expected": case["expected_output"],
                    "actual": None,
                    "error": traceback.format_exc(limit=1),
                })

        print(json.dumps({
            "interface_ok": True,
            "error": None,
            "case_results": results,
        }))
        """
    ).replace("TESTS_JSON", repr(json.dumps(payload)))

    with tempfile.TemporaryDirectory(prefix="legacy-cobol-eval-") as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "candidate.py").write_text(code, encoding="utf-8")
        (tmp_path / "runner.py").write_text(runner, encoding="utf-8")

        try:
            completed = subprocess.run(
                [sys.executable, "runner.py"],
                cwd=tmp_path,
                env={},
                text=True,
                capture_output=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return EvaluationResult(
                syntax_ok=True,
                safety_ok=True,
                interface_ok=False,
                timed_out=True,
                passed=0,
                total=len(tests),
                error="candidate timed out",
            )

    if completed.returncode != 0:
        return EvaluationResult(
            syntax_ok=True,
            safety_ok=True,
            interface_ok=False,
            timed_out=False,
            passed=0,
            total=len(tests),
            error=completed.stderr.strip() or "candidate runner failed",
        )

    try:
        data: dict[str, Any] = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        return EvaluationResult(
            syntax_ok=True,
            safety_ok=True,
            interface_ok=False,
            timed_out=False,
            passed=0,
            total=len(tests),
            error="candidate produced non-JSON output during evaluation",
        )

    case_results = [
        CaseResult(
            case_id=item["case_id"],
            passed=bool(item["passed"]),
            input_summary=item["input_summary"],
            expected=item.get("expected"),
            actual=item.get("actual"),
            error=item.get("error"),
        )
        for item in data.get("case_results", [])
    ]

    return EvaluationResult(
        syntax_ok=True,
        safety_ok=True,
        interface_ok=bool(data.get("interface_ok")),
        timed_out=False,
        passed=sum(1 for item in case_results if item.passed),
        total=len(tests),
        case_results=case_results,
        error=data.get("error"),
    )

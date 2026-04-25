"""Dockerized COBOL oracle checks for the hard invoice task."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from legacy_cobol_env.server import task_bank
from legacy_cobol_env.server.task_bank import TestCase, generate_fresh_tests, load_task


ENV_ROOT = Path(__file__).resolve().parents[1]
INVOICE_ORACLE_DIR = ENV_ROOT / "cobol_oracles" / "invoice"
DEFAULT_IMAGE_TAG = "legacy-cobol-invoice-oracle:local"


def invoice_oracle_cases(include_fresh: bool = True) -> list[TestCase]:
    task = load_task(task_id="invoice_occurs_001")
    cases = [*task.visible_tests, *task.hidden_tests]
    if include_fresh:
        cases.extend(generate_fresh_tests(task))
    return cases


def build_invoice_oracle_image(image_tag: str = DEFAULT_IMAGE_TAG) -> None:
    _require_docker()
    subprocess.run(
        ["docker", "build", "-t", image_tag, str(INVOICE_ORACLE_DIR)],
        check=True,
        text=True,
    )


def compile_invoice_task_sources(
    image_tag: str = DEFAULT_IMAGE_TAG,
    build: bool = True,
) -> dict[str, Any]:
    _require_docker()
    if build:
        build_invoice_oracle_image(image_tag=image_tag)

    with tempfile.TemporaryDirectory(prefix="invoice-task-compile-") as tmp:
        workdir = Path(tmp)
        (workdir / "INVTOTAL.cbl").write_text(task_bank.INVOICE_COBOL, encoding="utf-8")
        (workdir / "TAXRATE.cbl").write_text(task_bank.TAXRATE_COBOL, encoding="utf-8")
        (workdir / "INVOICE_REC.cpy").write_text(task_bank.INVOICE_COPYBOOK, encoding="utf-8")
        (workdir / "TAX_CODE.cpy").write_text(task_bank.TAX_CODE_COPYBOOK, encoding="utf-8")
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "sh",
                "-v",
                f"{workdir}:/work",
                "-w",
                "/work",
                image_tag,
                "-lc",
                "cobc -m -free INVTOTAL.cbl TAXRATE.cbl",
            ],
            check=False,
            text=True,
            capture_output=True,
        )

    return {
        "ok": completed.returncode == 0,
        "compiled_sources": ["INVTOTAL.cbl", "TAXRATE.cbl"],
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run_invoice_oracle(
    records: list[str],
    image_tag: str = DEFAULT_IMAGE_TAG,
    build: bool = False,
) -> list[str]:
    _require_docker()
    if build:
        build_invoice_oracle_image(image_tag=image_tag)

    with tempfile.TemporaryDirectory(prefix="invoice-cobol-oracle-") as tmp:
        workdir = Path(tmp)
        input_path = workdir / "input.txt"
        output_path = workdir / "output.txt"
        input_path.write_text("".join(f"{record}\n" for record in records), encoding="utf-8")

        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{workdir}:/work",
                image_tag,
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        outputs = output_path.read_text(encoding="utf-8").splitlines()

    if len(outputs) != len(records):
        raise RuntimeError(f"COBOL oracle returned {len(outputs)} outputs for {len(records)} records")
    return outputs


def compare_invoice_oracle(
    image_tag: str = DEFAULT_IMAGE_TAG,
    build: bool = False,
    include_fresh: bool = True,
) -> dict[str, Any]:
    cases = invoice_oracle_cases(include_fresh=include_fresh)
    actual_outputs = run_invoice_oracle(
        [case.input_record for case in cases],
        image_tag=image_tag,
        build=build,
    )
    rows = []
    mismatches = []
    for case, actual in zip(cases, actual_outputs, strict=True):
        passed = actual == case.expected_output
        row = {
            "case_id": case.case_id,
            "summary": case.summary,
            "input_record": case.input_record,
            "expected_output": case.expected_output,
            "actual_output": actual,
            "passed": passed,
        }
        rows.append(row)
        if not passed:
            mismatches.append(row)

    return {
        "ok": not mismatches,
        "image_tag": image_tag,
        "case_count": len(cases),
        "passed_count": len(cases) - len(mismatches),
        "mismatches": mismatches,
        "cases": rows,
    }


def write_comparison_report(result: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def _require_docker() -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("docker is required for COBOL oracle checks")

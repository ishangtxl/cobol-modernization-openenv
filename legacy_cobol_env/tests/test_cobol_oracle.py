from __future__ import annotations

import os
import shutil

import pytest

from legacy_cobol_env.server import task_bank


def test_invoice_cobol_oracle_artifacts_exist_and_copybooks_match_task_bank():
    from legacy_cobol_env.eval.cobol_oracle import INVOICE_ORACLE_DIR

    expected_files = {
        "Dockerfile",
        "INVOICE_ORACLE.cbl",
        "TAXRATE.cbl",
        "INVOICE_REC.cpy",
        "TAX_CODE.cpy",
    }

    assert expected_files <= {path.name for path in INVOICE_ORACLE_DIR.iterdir()}
    assert (INVOICE_ORACLE_DIR / "INVOICE_REC.cpy").read_text(encoding="utf-8") == task_bank.INVOICE_COPYBOOK
    assert (INVOICE_ORACLE_DIR / "TAX_CODE.cpy").read_text(encoding="utf-8") == task_bank.TAX_CODE_COPYBOOK


def test_invoice_oracle_cases_cover_visible_hidden_and_fresh_records():
    from legacy_cobol_env.eval.cobol_oracle import invoice_oracle_cases

    cases = invoice_oracle_cases()
    case_ids = {case.case_id for case in cases}

    assert len(cases) == 13
    assert {"visible_1", "hidden_4", "fresh_20260429_5"} <= case_ids
    assert all(len(case.input_record) == 44 for case in cases)
    assert all(len(case.expected_output) == 18 for case in cases)


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is required for compiler-backed COBOL oracle")
@pytest.mark.skipif(os.getenv("RUN_COBOL_ORACLE_DOCKER") != "1", reason="set RUN_COBOL_ORACLE_DOCKER=1 to run Docker oracle")
def test_docker_invoice_oracle_matches_python_reference():
    from legacy_cobol_env.eval.cobol_oracle import compare_invoice_oracle

    result = compare_invoice_oracle(build=True)

    assert result["ok"] is True
    assert result["case_count"] == 13
    assert result["mismatches"] == []


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is required for compiler-backed COBOL oracle")
@pytest.mark.skipif(os.getenv("RUN_COBOL_ORACLE_DOCKER") != "1", reason="set RUN_COBOL_ORACLE_DOCKER=1 to run Docker oracle")
def test_docker_invoice_task_sources_compile():
    from legacy_cobol_env.eval.cobol_oracle import compile_invoice_task_sources

    result = compile_invoice_task_sources()

    assert result["ok"] is True
    assert result["compiled_sources"] == ["INVTOTAL.cbl", "TAXRATE.cbl"]

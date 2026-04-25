# Invoice COBOL Oracle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add compiler-backed invoice validation so the hard task is grounded in executable COBOL, while keeping the live OpenEnv loop fast.

**Architecture:** Add a focused Dockerized GnuCOBOL oracle for `invoice_occurs_001`. The environment continues to score with the existing Python reference at runtime; an offline eval script compiles/runs COBOL and cross-checks visible, hidden, and fresh invoice cases against the Python oracle.

**Tech Stack:** Python 3.12, pytest, Docker, GnuCOBOL, existing `task_bank` invoice fixtures.

---

### Task 1: Tests First

**Files:**
- Create: `legacy_cobol_env/tests/test_cobol_oracle.py`

- [ ] Write tests that assert invoice COBOL oracle files exist, copybooks match `task_bank`, and the Python wrapper exposes a Docker command path.
- [ ] Run `PYTHONPATH=. .venv/bin/pytest legacy_cobol_env/tests/test_cobol_oracle.py -q`.
- [ ] Confirm tests fail because oracle files/module do not exist.

### Task 2: Oracle Artifacts

**Files:**
- Create: `legacy_cobol_env/cobol_oracles/invoice/Dockerfile`
- Create: `legacy_cobol_env/cobol_oracles/invoice/INVOICE_ORACLE.cbl`
- Create: `legacy_cobol_env/cobol_oracles/invoice/TAXRATE.cbl`
- Create: `legacy_cobol_env/cobol_oracles/invoice/INVOICE_REC.cpy`
- Create: `legacy_cobol_env/cobol_oracles/invoice/TAX_CODE.cpy`

- [ ] Add a Dockerfile that installs GnuCOBOL and compiles `INVOICE_ORACLE.cbl` with `TAXRATE.cbl`.
- [ ] Add a line-sequential COBOL oracle that reads `/work/input.txt` and writes `/work/output.txt`.
- [ ] Add `TAXRATE.cbl` with the same tax-code branches as the task source.
- [ ] Copy invoice copybooks exactly from `task_bank`.

### Task 3: Python Harness

**Files:**
- Create: `legacy_cobol_env/eval/cobol_oracle.py`
- Create: `legacy_cobol_env/eval/run_cobol_oracle_checks.py`

- [ ] Implement `invoice_oracle_cases()` for visible, hidden, and fresh invoice records.
- [ ] Implement `build_invoice_oracle_image()` and `run_invoice_oracle()` using Docker and a temporary `/work` volume.
- [ ] Implement `compare_invoice_oracle()` that returns records, expected outputs, actual outputs, and mismatch details.
- [ ] Add a CLI that writes `legacy_cobol_env/outputs/evals/cobol_invoice_oracle_check.json`.

### Task 4: Docs and Verification

**Files:**
- Modify: `legacy_cobol_env/README.md`
- Modify: `legacy_cobol_env/training/README.md` only if needed

- [ ] Document the compiler-backed invoice check and its command.
- [ ] Run the new unit tests.
- [ ] Run `PYTHONPATH=. .venv/bin/python -m legacy_cobol_env.eval.run_cobol_oracle_checks --build`.
- [ ] Run the full test suite and validation gates.


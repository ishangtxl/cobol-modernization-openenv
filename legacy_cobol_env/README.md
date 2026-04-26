---
title: Legacy COBOL Migration Workbench
emoji: 🧾
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - cobol
  - reinforcement-learning
---

# Legacy COBOL Migration Workbench

An OpenEnv environment where an agent acts like a legacy modernization engineer. The agent receives a migration ticket, inspects COBOL and copybooks through tools, writes Python, runs visible tests, studies diffs, and submits a final migration scored on hidden and fresh tests.

The current build includes six judge-facing task families covering payroll, customer records, insurance claims, banking account status, invoice OCCURS tables, and legacy date normalization.

## Environment Overview

Each episode starts with a partial ticket. The agent can discover details through MCP tools:

- `read_cobol_file`
- `read_copybook`
- `parse_copybook_layout`
- `inspect_business_rules`
- `write_python_solution`
- `run_visible_tests`
- `inspect_diff`
- `submit_final`

The submitted Python code must define:

```python
def migrate(input_record: str) -> str:
    ...
```

The final score combines hidden correctness, fresh generated tests, interface checks, layout fidelity, anti-hardcoding, and safety.
Episodes are capped at 12 tool steps. The next action returns a terminal no-op reward of `0.0`, and all post-terminal mutations are blocked.

## Quick Start

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

Run the server locally:

```bash
.venv/bin/python -m legacy_cobol_env.server.app --port 8000
```

Then open `/web` or connect with the client:

```python
from legacy_cobol_env import LegacyCobolEnv

with LegacyCobolEnv(base_url="http://localhost:8000") as env:
    env.reset()
    print([tool.name for tool in env.list_tools()])
```

Build and smoke-test the Docker image:

```bash
cd legacy_cobol_env
docker build -t legacy-cobol-env:plain .
docker run -d --rm --name legacy-cobol-env-plain -p 18000:8000 legacy-cobol-env:plain
curl -sS http://127.0.0.1:18000/health
curl -sS -X POST http://127.0.0.1:18000/reset -H 'Content-Type: application/json' -d '{"task_id":"payroll_net_pay_001"}'
docker stop legacy-cobol-env-plain

../.venv/bin/openenv build -t legacy-cobol-env:local
docker run -d --rm --name legacy-cobol-env-smoke -p 18000:8000 legacy-cobol-env:local
curl -sS http://127.0.0.1:18000/health
curl -sS -X POST http://127.0.0.1:18000/reset -H 'Content-Type: application/json' -d '{"task_id":"payroll_net_pay_001"}'
docker stop legacy-cobol-env-smoke
```

The plain REST API keeps one current episode for `/reset`, `/step`, and `/state`.
For concurrent interactive sessions, use the WebSocket/MCP endpoints exposed by OpenEnv.

## Reward Components

```text
final_reward =
  0.55 * hidden_correctness
+ 0.15 * fresh_correctness
+ 0.10 * interface_contract
+ 0.08 * type_and_layout_fidelity
+ 0.07 * anti_hardcoding
+ 0.05 * safety
```

Visible tests are for debugging. Hidden and fresh case details are not revealed to the agent after final submission.

## Task Families

| Task | Difficulty | COBOL concepts | Main failure modes |
| --- | --- | --- | --- |
| `fixed_width_customer` | easy | `PIC X`, padding/truncation, status mapping | trimmed spaces, lost ZIP leading zeros, bad output width |
| `decimal_copybook_payroll` | medium | copybook layout, implied decimals, level-88 bonus flag | float drift, wrong rounding, wrong fixed-width net pay |
| `claims_eligibility_branching` | medium | `EVALUATE TRUE`, branch precedence | wrong first-match branch, boundary mistakes |
| `account_status_level88` | medium | level-88 status conditions, signed amount | treating condition names as variables, wrong precedence |
| `date_normalization` | medium | legacy YYMMDD windowing, validation | wrong century window, over-rejecting legacy dates |
| `invoice_occurs_totals` | hard | multi-file `INVTOTAL.cbl`/`TAXRATE.cbl`, `OCCURS`, copybook tax-code metadata | wrong stride, ignoring tax-code lookup, overfitting visible invoice IDs |

`inspect_business_rules` exposes agent-facing hints only. Exact reference rules stay internal for tests and documentation.

## Baseline Evidence

Run deterministic non-model baselines:

```bash
PYTHONPATH=. .venv/bin/python legacy_cobol_env/eval/run_baselines.py
```

Current baseline means:

```text
identity     0.15
blank_width  0.1767
```

Artifacts:

- `outputs/evals/baseline_results.json`
- `plots/baseline_scores.svg`

Run oracle sanity trajectories:

```bash
PYTHONPATH=. .venv/bin/python legacy_cobol_env/eval/run_oracles.py
```

Current oracle sanity result:

```text
mean public score  1.0
accepted tasks     6 / 6
```

Artifact:

- `outputs/evals/oracle_trajectories.json`

Run provider-backed model rollouts:

```bash
PYTHONPATH=. .venv/bin/python -m legacy_cobol_env.eval.run_model_rollouts --provider oracle-model
```

Supported local/provider modes:

- `oracle-model`: model-shaped plumbing check using reference solutions
- `static`: fixed response from `STATIC_RESPONSE`
- `azure-openai`: requires `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and `AZURE_OPENAI_DEPLOYMENT`
- `hf-endpoint`: requires `HF_INFERENCE_ENDPOINT` and `HF_TOKEN`

Artifact:

- `outputs/evals/oracle_model_rollouts.json`

Run the compiler-backed invoice oracle check:

```bash
PYTHONPATH=. .venv/bin/python -m legacy_cobol_env.eval.run_cobol_oracle_checks --build
```

This builds a Dockerized GnuCOBOL oracle for the hard invoice task, compiles the actual task COBOL sources (`INVTOTAL.cbl` and `TAXRATE.cbl`), then compares visible, hidden, and fresh invoice outputs against the Python reference.

Current compiler-backed result:

```text
invoice COBOL oracle cases  13 / 13 matched
task COBOL source compile   passed
```

Artifact:

- `outputs/evals/cobol_invoice_oracle_check.json`

Current regenerated local evidence:

| Policy | Mean public score | Accepted tasks |
| --- | ---: | ---: |
| deterministic identity | 0.1500 | 0 / 6 |
| deterministic blank width | 0.1767 | 0 / 6 |
| `oracle-model` plumbing check | 1.0000 | 6 / 6 |

The previous Azure `gpt-5.4-mini` artifacts are kept for comparison, but `run_evidence_report` skips them because they were produced before the invoice task was hardened into a multi-file tax-code task. Rerun live Azure rollouts after local gates pass.

Historical Azure artifacts:

- `outputs/evals/azure_gpt54mini_zeroshot_rollouts.json`
- `outputs/evals/azure_gpt54mini_repair1_rollouts.json`

Generate the submission evidence summary and score plot:

```bash
PYTHONPATH=. .venv/bin/python -m legacy_cobol_env.eval.run_evidence_report
```

Artifacts:

- `outputs/evals/score_summary.json`
- `plots/model_scores.svg`

Run the root submission inference script:

```bash
cd legacy_cobol_env
API_BASE_URL="https://..." MODEL_NAME="..." HF_TOKEN="..." python inference.py --max-repairs 1
```

The submission script uses `openai.OpenAI`, emits `[START]`, one `[STEP]` per task, and `[END]`, and defaults to all six tasks.

Generate SFT warm-start data:

```bash
PYTHONPATH=. .venv/bin/python -m legacy_cobol_env.training.build_sft_dataset
```

Artifact:

- `outputs/training/oracle_sft.jsonl`

Dry-run the GPU training command locally:

```bash
PYTHONPATH=. .venv/bin/python -m legacy_cobol_env.training.train_sft --dry-run
```

Dry-run artifacts:

- `outputs/training/sft_run_metadata.json`
- `outputs/training/sft_loss.csv`
- `outputs/training/sft_loss.svg`

Evaluate a trained/local checkpoint:

```bash
LOCAL_MODEL_PATH=legacy_cobol_env/outputs/training/sft-qwen-coder-7b \
LOCAL_BASE_MODEL_PATH=Qwen/Qwen2.5-Coder-7B-Instruct \
PYTHONPATH=. .venv/bin/python -m legacy_cobol_env.eval.run_model_rollouts \
  --provider local-transformers \
  --task-id invoice_occurs_001 \
  --max-repairs 1 \
  --output legacy_cobol_env/outputs/evals/local_sft_invoice_rollout.json
```

## Current Scope

Implemented:

- Six end-to-end task families with visible, hidden, and fresh tests
- MCP workbench tools
- Structured visible diffs
- Basic AST and subprocess sandbox checks
- Direct environment tests
- Deterministic baseline evaluation harness
- Oracle sanity solutions and JSON workbench trajectories
- Provider-backed model rollout harness for Azure OpenAI and Hugging Face endpoints
- Compiler-backed GnuCOBOL oracle check for the hard invoice task
- Root Dockerfile, root `inference.py`, root `openenv.yaml`, and root README for submission gates
- `legacy_cobol_env/Dockerfile` and `legacy_cobol_env/inference.py` for submitting `legacy_cobol_env` directly as the Space/repo root
- Typed project action, observation, reward, and state schemas surfaced at `/schema`
- Persistent REST `/reset`, `/step`, and `/state` semantics for the current episode
- Max-step and post-terminal no-op enforcement
- Score summary, model-score plot, oracle SFT warm-start dataset, and SFT dry-run artifacts

Next:

- Rerun Azure `gpt-5.4-mini` zero-shot and repair baselines against the hardened invoice task
- Run SFT on GPU, then evaluate invoice before deciding whether RL/GRPO is needed
- Push to Hugging Face Spaces with `openenv push`

## Safety Note

The sandbox blocks common unsafe imports and builtins, runs candidate code in a temporary subprocess, clears environment variables, and applies a timeout. It should still be treated as layered mitigation for a hackathon environment, not as a complete secure isolation boundary.

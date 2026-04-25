# Colab T4 Training Guide

This guide is for a fresh Google Colab notebook with a Tesla T4 GPU
(`15360MiB`). It assumes the working repo is:

```text
https://github.com/ishangtxl/cobol-modernization-openenv
```

## 1. Create The Notebook

1. Open Google Colab.
2. Click **File -> New notebook**.
3. Click **Runtime -> Change runtime type**.
4. Select **T4 GPU** or **GPU**.
5. Click **Save**.

Run this first:

```bash
!nvidia-smi
```

If it says `Tesla T4` and `15360MiB`, use the T4 path below.

## 2. Clone The Repo

```bash
!git clone https://github.com/ishangtxl/cobol-modernization-openenv.git
%cd cobol-modernization-openenv
```

If you rerun the notebook and the folder already exists:

```bash
%cd /content/cobol-modernization-openenv
!git pull
```

## 3. Install Dependencies

Colab already has Python and CUDA. Install the project and training deps:

```bash
!python -m pip install -U pip
!pip install -r legacy_cobol_env/training/requirements-gpu.txt
!pip install -e legacy_cobol_env
```

If `bitsandbytes` install fails, restart the Colab runtime and run the install
cell again.

## 4. Verify The Environment

```bash
!PYTHONPATH=. python -m pytest legacy_cobol_env/tests -q
!cd legacy_cobol_env && openenv validate --verbose
```

Expected:

```text
19 passed
[OK] legacy_cobol: Ready for multi-mode deployment
```

## 5. Build Training Data

```bash
!PYTHONPATH=. python -m legacy_cobol_env.training.build_sft_dataset
!wc -l legacy_cobol_env/outputs/training/oracle_sft.jsonl
```

Expected:

```text
10 legacy_cobol_env/outputs/training/oracle_sft.jsonl
```

The default dataset includes the six task-family examples plus four
invoice-focused rows for OCCURS stride parsing, implied decimals, and
fixed-width numeric output formatting.

## 6. Dry Run The SFT Config

Safe T4 config:

```bash
!PYTHONPATH=. python -m legacy_cobol_env.training.train_sft \
  --dry-run \
  --model-name Qwen/Qwen2.5-Coder-7B-Instruct \
  --max-seq-length 2048 \
  --gradient-accumulation-steps 8
```

The T4 has only 15GB VRAM, so start with `max_seq_length=2048`.

## 7. Train On T4

```bash
!PYTHONPATH=. python -m legacy_cobol_env.training.train_sft \
  --model-name Qwen/Qwen2.5-Coder-7B-Instruct \
  --max-seq-length 2048 \
  --gradient-accumulation-steps 8 \
  --output-dir legacy_cobol_env/outputs/training/sft-qwen25-coder-7b-t4
```

If this runs out of memory, retry with:

```bash
!PYTHONPATH=. python -m legacy_cobol_env.training.train_sft \
  --model-name Qwen/Qwen2.5-Coder-7B-Instruct \
  --max-seq-length 1536 \
  --gradient-accumulation-steps 16 \
  --output-dir legacy_cobol_env/outputs/training/sft-qwen25-coder-7b-t4
```

## 8. Evaluate The Trained Checkpoint

Evaluate the invoice target first:

```bash
!LOCAL_MODEL_PATH=legacy_cobol_env/outputs/training/sft-qwen25-coder-7b-t4 \
LOCAL_BASE_MODEL_PATH=Qwen/Qwen2.5-Coder-7B-Instruct \
PYTHONPATH=. python -m legacy_cobol_env.eval.run_model_rollouts \
  --provider local-transformers \
  --task-id invoice_occurs_001 \
  --max-repairs 2 \
  --output legacy_cobol_env/outputs/evals/local_sft_invoice_rollout.json
```

Then inspect the score:

```bash
!python - <<'PY'
import json
from pathlib import Path
path = Path("legacy_cobol_env/outputs/evals/local_sft_invoice_rollout.json")
data = json.loads(path.read_text())
traj = data["trajectories"][0]
print(json.dumps({
    "score": traj["final"]["public_score"],
    "accepted": traj["final"]["accepted"],
    "components": traj["final"]["components"],
}, indent=2))
PY
```

Success target:

```text
score > 0.5233
ideal score >= 0.8
```

## 9. Save Artifacts

Download these from the Colab file browser or copy them to Google Drive:

```text
legacy_cobol_env/outputs/evals/local_sft_invoice_rollout.json
legacy_cobol_env/outputs/training/sft-qwen25-coder-7b-t4/
```

## Newer Model Experiments

Use these only after the 7B T4 baseline works.

### Qwen3 14B

Likely too tight for T4, but worth trying only with 4-bit and short context:

```bash
!PYTHONPATH=. python -m legacy_cobol_env.training.train_sft \
  --model-name Qwen/Qwen3-14B \
  --max-seq-length 1024 \
  --gradient-accumulation-steps 16 \
  --output-dir legacy_cobol_env/outputs/training/sft-qwen3-14b-t4
```

If this fails with CUDA out-of-memory, stop and return to the 7B path.

### Qwen3.6

Qwen3.6 35B-A3B is not a good T4 training target. It is better for inference or
for a larger GPU. Do not make it the first Colab run.

### Gemma 4 E4B

Gemma 4 E4B is a plausible T4-sized comparison model, but this project is a
code-migration benchmark, so Qwen Coder is the stronger first choice.

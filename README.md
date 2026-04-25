# Legacy COBOL Migration Workbench

Root-level submission entrypoint for the OpenEnv Legacy COBOL Migration Workbench. The full environment documentation lives in `legacy_cobol_env/README.md`.

## Gate Commands

Build the root Docker image:

```bash
docker build -t openenvr2-gate .
```

Run the server from that image:

```bash
docker run --rm -p 8000:8000 openenvr2-gate
```

Smoke-test the server:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/schema
```

Run the inference contract in static mode without network access:

```bash
python inference.py --mode static --max-repairs 0 --output /tmp/openenvr2-result.json
```

Run the live baseline with an OpenAI-compatible endpoint:

```bash
API_BASE_URL="https://..." \
MODEL_NAME="..." \
HF_TOKEN="..." \
python inference.py --max-repairs 1 --output /tmp/openenvr2-live-result.json
```

`inference.py` emits strict `[START]`, `[STEP]`, and `[END]` JSON records and runs all six task families by default. Use `--task-id invoice_occurs_001` to isolate one task.

Run the compiler-backed invoice authenticity check:

```bash
PYTHONPATH=. python -m legacy_cobol_env.eval.run_cobol_oracle_checks --build
```

For the full task description, local development setup, evaluation harness, and training notes, see `legacy_cobol_env/README.md`.

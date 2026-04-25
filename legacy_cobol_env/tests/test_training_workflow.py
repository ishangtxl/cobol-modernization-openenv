import json
from pathlib import Path

from legacy_cobol_env.eval.providers import create_provider
from legacy_cobol_env.training.train_sft import SFTArgs, build_sft_plan, load_jsonl_rows, write_dry_run_artifacts


def test_build_sft_plan_reads_dataset_without_gpu_dependencies(tmp_path: Path):
    dataset = tmp_path / "tiny.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "task_id": "invoice_occurs_001",
                "family_id": "invoice_occurs_totals",
                "messages": [
                    {"role": "user", "content": "prompt"},
                    {"role": "assistant", "content": "{\"code\": \"def migrate(input_record: str) -> str:\\n    return input_record\\n\"}"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    plan = build_sft_plan(SFTArgs(dataset=str(dataset), output_dir=str(tmp_path / "out")))

    assert plan["dataset_examples"] == 1
    assert plan["model_name"]
    assert plan["uses_lora"] is True
    assert plan["output_dir"] == str(tmp_path / "out")


def test_load_jsonl_rows_rejects_missing_messages(tmp_path: Path):
    dataset = tmp_path / "bad.jsonl"
    dataset.write_text(json.dumps({"task_id": "x"}) + "\n", encoding="utf-8")

    try:
        load_jsonl_rows(dataset)
    except ValueError as exc:
        assert "messages" in str(exc)
    else:
        raise AssertionError("expected invalid dataset row to fail")


def test_local_transformers_provider_requires_model_path():
    try:
        create_provider("local-transformers", {})
    except ValueError as exc:
        assert "LOCAL_MODEL_PATH" in str(exc)
    else:
        raise AssertionError("expected missing local model path to fail")


def test_write_dry_run_artifacts_creates_metadata_loss_and_plot(tmp_path: Path):
    plan = {
        "dataset_examples": 6,
        "model_name": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "output_dir": str(tmp_path / "model"),
    }

    artifacts = write_dry_run_artifacts(plan, tmp_path)

    assert artifacts["metadata"].exists()
    assert artifacts["loss_csv"].read_text(encoding="utf-8").splitlines()[0] == "step,loss"
    assert artifacts["loss_plot"].read_text(encoding="utf-8").startswith("<svg")

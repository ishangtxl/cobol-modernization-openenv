import json
from pathlib import Path

from legacy_cobol_env.eval.providers import create_provider
from legacy_cobol_env.eval.providers import LocalTransformersProvider
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


def test_local_transformers_provider_detects_peft_adapter_config(tmp_path: Path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "base-model"}), encoding="utf-8")

    provider = LocalTransformersProvider(model_path=str(adapter_dir))

    assert provider._adapter_base_model_path() == "base-model"


def test_local_transformers_provider_env_accepts_base_model_path(tmp_path: Path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")

    provider = create_provider(
        "local-transformers",
        {"LOCAL_MODEL_PATH": str(adapter_dir), "LOCAL_BASE_MODEL_PATH": "Qwen/base"},
    )

    assert provider.base_model_path == "Qwen/base"
    assert provider.load_in_4bit is True


def test_local_transformers_provider_can_disable_4bit(tmp_path: Path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    provider = create_provider(
        "local-transformers",
        {"LOCAL_MODEL_PATH": str(model_dir), "LOCAL_LOAD_IN_4BIT": "false"},
    )

    assert provider.load_in_4bit is False


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

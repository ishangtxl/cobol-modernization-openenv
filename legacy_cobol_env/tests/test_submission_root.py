import subprocess
import sys
from pathlib import Path


ENV_ROOT = Path(__file__).resolve().parents[1]


def test_submission_root_contains_required_gate_files():
    assert (ENV_ROOT / "inference.py").is_file()
    assert (ENV_ROOT / "Dockerfile").is_file()
    assert (ENV_ROOT / "openenv.yaml").is_file()
    assert (ENV_ROOT / "README.md").is_file()


def test_submission_root_inference_runs_from_environment_directory(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "inference.py",
            "--mode",
            "static",
            "--task-id",
            "payroll_net_pay_001",
            "--output",
            str(tmp_path / "result.json"),
        ],
        cwd=ENV_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert [line.split(" ", 1)[0] for line in lines] == ["[START]", "[STEP]", "[END]"]

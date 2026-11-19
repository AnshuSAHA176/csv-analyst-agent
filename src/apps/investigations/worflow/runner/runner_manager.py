
import json
import subprocess
import tempfile
import uuid

from pathlib import Path


def run_analysis(
    source_code: str,
    dataset_file_path: str,
    function_name: str = "analyze",
    timeout: int = 15,
) -> dict:

    dataset_path = Path(dataset_file_path).resolve()

    if not dataset_path.is_file():
        return {
            "ok": False,
            "error": "Dataset file does not exist."
        }

    container_name = f"csv-analysis-{uuid.uuid4().hex}"

    with tempfile.TemporaryDirectory(prefix="csv-analysis-") as temp_dir:

        workspace = Path(temp_dir)

        submission_path = workspace / "submission.py"
        input_path = workspace / "input.json"

        submission_path.write_text(source_code)

        test_input = {
            "dataset_path": "/workspace/dataset.csv"
        }

        input_path.write_text(json.dumps(test_input))

        command = [
            "docker", "run",
            "--name", container_name,
            "--env", f"FUNCTION_NAME={function_name}",
            "--rm",

            # Isolation
            "--network", "none",
            "--memory", "512m",
            "--memory-swap", "512m",
            "--cpus", "1",
            "--pids-limit", "32",

            # Filesystem restrictions
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--user", "10001:10001",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",

            # Generated Python code
            "--mount",
            f"type=bind,src={submission_path},dst=/workspace/submission.py,readonly",

            # Execution input
            "--mount",
            f"type=bind,src={input_path},dst=/workspace/input.json,readonly",

            # Dataset (read-only)
            "--mount",
            f"type=bind,src={dataset_path},dst=/workspace/dataset.csv,readonly",

            "knowgrid-python-runner:latest",
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": "Execution timed out."
            }

        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc)
            }

        finally:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                timeout=3,
                check=False,
            )

        if completed.returncode != 0:
            return {
                "ok": False,
                "error": completed.stderr[:4000] or "Execution failed."
            }

        try:
            result = json.loads(completed.stdout)

            if not isinstance(result, dict):
                raise ValueError("Invalid runner response.")

            return result

        except (json.JSONDecodeError, ValueError):
            return {
                "ok": False,
                "error": "Runner returned invalid JSON."
            }

import contextlib
import io
import json
import os
from pathlib import Path


def main():
    workspace = Path("/workspace")

    source_code = (workspace / "submission.py").read_text()
    test_input = json.loads((workspace / "input.json").read_text())

    if not isinstance(test_input, dict):
        raise ValueError("Test input must be a JSON object")

    namespace = {"__name__": "submission"}
    exec(compile(source_code, "submission.py", "exec"), namespace)

    function_name = os.environ.get("FUNCTION_NAME", "analyze")
    solution = namespace.get(function_name)

    if not callable(solution):
        raise ValueError(f"Expected function {function_name!r} was not found")

    captured_output = io.StringIO()

    with contextlib.redirect_stdout(captured_output):
        result = solution(**test_input)

    output = {
        "ok": True,
        "result": result
    }

    print(json.dumps(output, allow_nan=False))


if __name__ == "__main__":
    main()
import json
import logging
from langchain_core.prompts import ChatPromptTemplate

from .state import InvestigationState
from .schemas import VerificationReport, FinalInvestigationReport
from .llm import get_llm
from .runner.runner_manager import run_analysis

logger = logging.getLogger(__name__)


# --- 1. PROMPTS ---

CODE_GEN_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Python data engineer writing code for a sandboxed runner.

RULES:
1. Write a single function: `def analyze(dataset_path: str) -> dict:`
2. ONLY use `pandas`, `numpy`, `scipy.stats`, `duckdb`, and Python's standard library. NEVER import `statsmodels` or `sklearn`, and NEVER run `pip install` or `subprocess`.
3. Return a JSON-safe dict with this exact format:
   {{"metrics": {{...}}, "sample_size": <int>, "summary": "<short summary>"}}
4. Keep `metrics` small (only totals, averages, group stats, or p-values—never raw rows). When returning grouped tables, sort by `lost_mrr` or `customer_count` descending and return only the top 10 rows.
5. Convert all NumPy keys and values (`np.int64`, `np.float64`, `np.bool_`) to plain Python `str()`, `int()`, `float()`, or `bool()`.
6. Use Pandas 2+ syntax: use `df.corr(numeric_only=True)` and `.map()` (never `.applymap()`).
7. Do NOT write files or use `print()`.
8. Return ONLY Python code inside ```python ... ``` tags.
9. For `statistics` steps, do NOT build logistic regression from scratch. Use `scipy.stats` (`mannwhitneyu`, `ttest_ind`, `pearsonr`, or `chi2_contingency`) to test each feature against the target and return test statistics and p-values."""
    ),
    (
        "human",
        "Step to run: {step}\nDataset info: {profile}\nFix this error (if any): {error}"
    ),
])

VERIFIER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """Audit the collected evidence.
- Add every completed step's integer `step_id` from `evidence` into `verified_step_ids`.
- Set `is_sufficient` to `True` if at least 2 steps have valid metrics.
- Put any small-sample (n < 30), missing-data, or failed-step warnings in `caveats`. Always add a caveat if any highlighted segment has `customer_count < 10`.
- Never invent numbers."""
    ),
    (
        "human",
        "Question: {question}\nSteps: {steps}\nEvidence: {evidence}\nErrors: {errors}"
    ),
])

REPORT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Write a clear business report answering the question using ONLY the numbers in `evidence`. Do not guess or invent numbers.",
        ),
        (
            "human",
            "Question: {question}\nGoal: {goal}\nEvidence: {evidence}\nVerification: {verification}\nErrors: {errors}",
        ),
    ]
)


# --- 2. SIMPLE HELPERS ---


def clean_code(raw_text: str) -> str:
    """Remove ```python and ``` markdown wrappers."""
    if "```" in raw_text:
        code = raw_text.split("```")[1]
        if code.startswith("python"):
            code = code[6:]
        return code.strip()
    return raw_text.strip()


def simplify_profile(profile: dict) -> dict:
    """Send only row count, missing counts, and column types to save LLM tokens."""
    columns = {}
    for col, info in profile.get("column_details", {}).items():
        dtype = info.get("dtype") if isinstance(info, dict) else str(info)
        columns[col] = {
            "type": dtype,
            "missing": profile.get("missing_values", {}).get(col, 0),
        }

    return {
        "rows": profile.get("row_count"),
        "duplicates": profile.get("duplicated_rows"),
        "columns": columns,
    }


# --- 3. GRAPH NODES ---


def generate_analysis_code(state: InvestigationState) -> dict:
    """Node 1: Ask the LLM to write Python code for the current step."""
    steps = state["analysis_plan"]["steps"]
    current_step = steps[state["current_analysis_step"]]

    # If the previous run failed, pass the error so the LLM can fix it
    error_text = "None"
    if state.get("last_error"):
        error_text = (
            f"{state['last_error']}\n\nBroken code:\n{state.get('current_code', '')}"
        )

    response = (CODE_GEN_PROMPT | get_llm(fast=True)).invoke(
        {
            "step": current_step,
            "profile": simplify_profile(state["dataset_profile"]),
            "error": error_text,
        }
    )

    return {
        "current_code": clean_code(response.content),
        "last_error": None,
    }


def execute_analysis_step(state: InvestigationState) -> dict:
    """Node 2: Run the generated code inside Docker and save the result."""
    steps = state["analysis_plan"]["steps"]
    idx = state["current_analysis_step"]
    step = steps[idx]
    retries = state.get("retry_count", 0)

    res = run_analysis(
        source_code=state["current_code"],
        dataset_file_path=state["dataset_file_path"],
        function_name="analyze",
        timeout=15,
    )

    # CASE A: Code failed in Docker
    if res.get("ok") is False or res.get("error"):
        error_msg = res.get("error", "Unknown error")
        logger.warning(
            f"Step {step['step_id']} failed (try {retries + 1}/2): {error_msg}"
        )

        # Try once more if this was the first attempt
        if retries == 0:
            return {"retry_count": 1, "last_error": error_msg}

        # Otherwise skip this step and move to the next one
        return {
            "tool_execution_results": state.get("tool_execution_results", [])
            + [{"step_id": step["step_id"], "status": "failed", "error": error_msg}],
            "errors": state.get("errors", [])
            + [f"Step {step['step_id']}: {error_msg}"],
            "current_analysis_step": idx + 1,
            "retry_count": 0,
            "last_error": None,
        }

    # CASE B: Code succeeded
    output = res.get("result") if isinstance(res.get("result"), dict) else res

    # Keep metrics under 2000 chars so later LLM calls don't hit token limits
    metrics = output.get("metrics", output)
    if len(json.dumps(metrics, default=str)) > 2000:
        metrics = {"summary_text": json.dumps(metrics, default=str)[:2000] + "..."}

    new_execution = {
        "step_id": step["step_id"],
        "status": "completed",
        "code": state["current_code"],
        "output": output,
    }
    new_evidence = {
        "step_id": step["step_id"],
        "hypothesis": step["hypothesis"],
        "metrics": metrics,
        "sample_size": output.get("sample_size", 0),
        "summary": output.get("summary", ""),
    }

    return {
        "tool_execution_results": state.get("tool_execution_results", [])
        + [new_execution],
        "evidence_collected": state.get("evidence_collected", []) + [new_evidence],
        "current_analysis_step": idx + 1,
        "retry_count": 0,
        "last_error": None,
    }


def verify_evidence(state: InvestigationState) -> dict:
    """Node 3: Check sample sizes and data quality before writing the report."""
    llm = get_llm(fast=True).with_structured_output(VerificationReport)
    result = (VERIFIER_PROMPT | llm).invoke(
        {
            "question": state["question"],
            "steps": state["analysis_plan"]["steps"],
            "evidence": state.get("evidence_collected", []),
            "errors": state.get("errors", []),
        }
    )
    return {"verification_results": result.model_dump()}


def generate_final_report(state: InvestigationState) -> dict:
    """Node 4: Combine all verified evidence into the final business report."""
    llm = get_llm(fast=False).with_structured_output(FinalInvestigationReport)
    report = (REPORT_PROMPT | llm).invoke(
        {
            "question": state["question"],
            "goal": state["goal"],
            "evidence": state.get("evidence_collected", []),
            "verification": state.get("verification_results", {}),
            "errors": state.get("errors", []),
        }
    )
    return {"final_report": report.model_dump()}

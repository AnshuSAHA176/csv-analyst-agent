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
4. Keep `metrics` small (only totals, averages, group stats, or p-values—never raw rows). For grouped tables, sort descending by the target metric and include the top 10 rows with all group column names using `json.loads(grouped_df.head(10).to_json(orient="records"))`.
5. Convert DataFrames/Series to JSON-safe Python types with `json.loads(df.to_json(orient="records"))` or `int()`/`float()`/`str()` on scalars. Never run `.map(float)` across mixed string/numeric DataFrames.
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
- Put any small-sample (n < 30), missing-data, or failed-step warnings in `caveats`.
- Set `is_sufficient` to `False` if:
  (a) a core step failed, OR
  (b) the question asks for specific top/worst segments/categories and `evidence` only gives counts without naming the actual groups, OR
  (c) highlighted segments have `n < 10` and need broader grouping.
  Otherwise set `is_sufficient` to `True`.
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
            "Write a clear business report answering the question using ONLY the numbers in `evidence`. Check every sub-group number before generalizing across all tiers—if one tier behaves differently, state the exception explicitly. Do not guess or invent numbers.",
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
        "evidence_collected": [new_evidence],
        "current_analysis_step": idx + 1,
        "retry_count": 0,
        "last_error": None,
    }


def verify_evidence(state: InvestigationState) -> dict:
    evidence = state.get("evidence_collected", [])
    errors = state.get("errors", [])
    completed_ids = sorted({item["step_id"] for item in evidence if "step_id" in item})

    llm = get_llm(fast=True).with_structured_output(VerificationReport)
    chain = (VERIFIER_PROMPT | llm).with_retry(stop_after_attempt=3)

    try:
        result = chain.invoke(
            {
                "question": state["question"],
                "steps": state["analysis_plan"]["steps"],
                "evidence": evidence,
                "errors": [err[-400:] for err in errors],
            }
        )
        report = result.model_dump()
    except Exception as exc:
        logger.warning("Verifier structured output failed, falling back: %s", exc)
        report = {
            "is_sufficient": False,
            "verified_step_ids": completed_ids,
            "caveats": [
                "Verification step hit a structured-output formatting error; running recovery check."
            ],
        }

    report["verified_step_ids"] = completed_ids
    if state.get("replan_count", 0) == 0 and (errors or report.get("caveats")):
        report["is_sufficient"] = False

    return {"verification_results": report}


def generate_final_report(state: InvestigationState) -> dict:
    """Node 4: Combine all verified evidence into the final business report."""
    llm = get_llm(fast=False).with_structured_output(FinalInvestigationReport)
    report = (REPORT_PROMPT | llm).invoke(
        {
            "question": state["question"],
            "goal": state["goal"],
            "evidence": state.get("evidence_collected", []),
            "verification": state.get("verification_results", {}),
            "errors": [ err[-400:] for err in state.get("errors", [])],
        }
    )
    return {"final_report": report.model_dump()}
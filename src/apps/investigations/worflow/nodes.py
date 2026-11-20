# In agent/nodes.py
from langchain_core.prompts import ChatPromptTemplate
from .state import InvestigationState
from .schemas import GeneratedScript
from .llm import get_llm

CODE_GEN_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are an expert Python data engineer writing analysis functions for a sandboxed runner.

## STRICT EXECUTION CONTRACT
1. Define a single entry-point function with this exact signature:
   `def analyze(input_data: dict) -> dict:`
2. Read the CSV path dynamically via: `dataset_path = input_data["dataset_path"]`
3. Return a JSON-serializable Python `dict` with this exact structure:
   {{
     "metrics": {{ ... }},       // Exact computed numbers, grouped records, or test stats
     "sample_size": <int>,      // Integer count of non-null rows evaluated
     "summary": "<string>"      // Objective factual summary of the computed numbers
   }}
4. Do NOT write files to `/workspace` (the filesystem is read-only; only `/tmp` is writable if needed).
5. Do NOT use `print()` for debugging—all output must be inside the returned dictionary, and every value must be native Python types (`int`, `float`, `str`, `list`, `dict` — convert numpy/pandas scalars via `.item()` or `float()`/`int()`).

## TOOL IMPLEMENTATION RULES
- If tool == "sql": Use `import duckdb` and query `dataset_path` directly via SQL.
- If tool == "python": Use `pandas` and `numpy` for filtering, grouping, and custom metrics.
- If tool == "statistics": Use `scipy.stats` and include test statistics, p-values, and sample sizes.
- Only use exact column names present in the Dataset Profile.
        """
    ),
    (
        "human",
        """
## CURRENT ANALYSIS STEP
{step}

## DATASET PROFILE
{dataset_profile}

## PREVIOUS ERROR TO FIX (If any)
{error_context}

Generate the Python code containing `def analyze(input_data: dict) -> dict:`.
        """
    )
])


def generate_analysis_code(state: InvestigationState) -> dict:
    steps = state["analysis_plan"]["steps"]
    idx = state["current_analysis_step"]
    current_step = steps[idx]

    last_error = state.get("last_error")
    error_context = (
        f"Previous attempt failed with error:\n{last_error}\n\n"
        f"Failing code:\n```python\n{state.get('current_code', '')}\n```\nFix the bug."
        if last_error
        else "None (first attempt)."
    )

    llm = get_llm().with_structured_output(GeneratedScript)
    result = (CODE_GEN_PROMPT | llm).invoke({
        "step": current_step,
        "dataset_profile": state["dataset_profile"],
        "error_context": error_context,
    })

    return {
        "current_code": result.python_code,
        "last_error": None,
    }

# In agent/nodes.py
from .runner.runner_manager import run_analysis  # Adjust to your actual module path


def execute_analysis_step(state: InvestigationState) -> dict:
    steps = state["analysis_plan"]["steps"]
    idx = state["current_analysis_step"]
    step = steps[idx]
    retry_count = state.get("retry_count", 0)

    run_res = run_analysis(
        source_code=state["current_code"],
        dataset_file_path=state["dataset_file_path"],
        function_name="analyze",
        timeout=15,
    )

    # Check failure from runner
    if run_res.get("ok") is False or "error" in run_res:
        error_msg = run_res.get("error", "Unknown sandbox execution error.")
        next_retry = retry_count + 1

        if next_retry >= 3:
            failed_record = {
                "step_id": step["step_id"],
                "tool": step["tool"],
                "status": "inconclusive",
                "error": error_msg,
            }
            return {
                "tool_execution_results": state.get("tool_execution_results", []) + [failed_record],
                "errors": state.get("errors", []) + [f"Step {step['step_id']} failed after 3 attempts: {error_msg}"],
                "current_analysis_step": idx + 1,
                "retry_count": 0,
                "last_error": None,
            }

        return {
            "retry_count": next_retry,
            "last_error": error_msg,
        }

    # Unwrap if your runner wraps return value under "result" or "output"
    payload = run_res.get("result") if isinstance(run_res.get("result"), dict) else run_res

    execution_record = {
        "step_id": step["step_id"],
        "tool": step["tool"],
        "status": "completed",
        "code": state["current_code"],
        "raw_output": payload,
    }
    evidence_record = {
        "step_id": step["step_id"],
        "hypothesis": step["hypothesis"],
        "metrics": payload.get("metrics", payload),
        "sample_size": payload.get("sample_size", 0),
        "summary": payload.get("summary", ""),
    }

    return {
        "tool_execution_results": state.get("tool_execution_results", []) + [execution_record],
        "evidence_collected": state.get("evidence_collected", []) + [evidence_record],
        "current_analysis_step": idx + 1,
        "retry_count": 0,
        "last_error": None,
    }

# In agent/nodes.py
from .schemas import VerificationReport, FinalInvestigationReport

VERIFIER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are a principal data scientist auditing investigation evidence before executive reporting.
Inspect the analysis plan, collected evidence, and execution errors.
Flag any step where sample_size < 30, where missing values may skew results, or where metrics contradict.
Never invent metrics.
        """
    ),
    (
        "human",
        "Question: {question}\nPlan: {plan}\nEvidence: {evidence}\nErrors: {errors}"
    )
])

REPORT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are a senior business analyst writing the final investigation report.
Synthesize the verified evidence into a clear, decision-ready report.
STRICT RULE: Every number you cite MUST appear verbatim in `evidence_collected`. Do not extrapolate or guess.
        """
    ),
    (
        "human",
        "Question: {question}\nGoal: {goal}\nEvidence: {evidence}\nVerification: {verification}\nErrors: {errors}"
    )
])


def verify_evidence(state: InvestigationState) -> dict:
    llm = get_llm().with_structured_output(VerificationReport)
    verification = (VERIFIER_PROMPT | llm).invoke({
        "question": state["question"],
        "plan": state["analysis_plan"],
        "evidence": state.get("evidence_collected", []),
        "errors": state.get("errors", []),
    })
    return {"verification_results": verification.model_dump()}


def generate_final_report(state: InvestigationState) -> dict:
    llm = get_llm().with_structured_output(FinalInvestigationReport)
    report = (REPORT_PROMPT | llm).invoke({
        "question": state["question"],
        "goal": state["goal"],
        "evidence": state.get("evidence_collected", []),
        "verification": state.get("verification_results", {}),
        "errors": state.get("errors", []),
    })
    return {"final_report": report.model_dump()}
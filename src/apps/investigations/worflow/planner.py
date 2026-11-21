from langchain_core.prompts import ChatPromptTemplate

from .llm import get_llm
from .schemas import AnalysisPlan, RecoveryAnalysisPlan
from .state import InvestigationState

PLANNER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a senior data analyst planning an investigation on a CSV dataset.

RULES:
- Use ONLY columns present in the dataset profile. Never invent columns.
- Choose tools only from: `sql`, `python`, `statistics`.
- For `statistics` steps, use `scipy.stats` tests (Mann-Whitney U, t-test, Pearson, Chi-square)—never logistic regression.
- Create 3 to 4 ordered steps (`step_id`: 1, 2, 3...) for a new plan.
- If `Previous Feedback` is not "None", create ONLY 1 to 2 recovery steps to fix the listed gaps, continuing `step_id` numbering after the verified steps.""",
        ),
        (
            "human",
            """Question: {question}
Goal: {goal}
Dataset Profile: {dataset_profile}
Previous Feedback: {feedback}""",
        ),
    ]
)


def create_analysis_plan(state: InvestigationState) -> dict:
    replan_count = state.get("replan_count", 0)
    verification = state.get("verification_results") or {}
    is_replan = bool(verification) and not verification.get("is_sufficient", True)

    feedback = (
        f"Verified steps: {verification.get('verified_step_ids', [])}. "
        f"Fix these gaps: {verification.get('caveats', [])}"
        if is_replan
        else "None"
    )

    schema = RecoveryAnalysisPlan if is_replan else AnalysisPlan
    llm = get_llm().with_structured_output(schema)

    plan = (PLANNER_PROMPT | llm).invoke(
        {
            "question": state["question"],
            "goal": state["goal"],
            "dataset_profile": state["dataset_profile"],
            "feedback": feedback,
        }
    )

    return {
        "analysis_plan": plan.model_dump(),
        "current_analysis_step": 0,
        "replan_count": replan_count + 1 if is_replan else 0,
    }
from typing import TypedDict, Any,Annotated
import operator



class InvestigationState(TypedDict):
    investigation_id: str
    dataset_id: str
    dataset_file_path: str
    dataset_profile: dict[str, Any]
    question: str
    goal: str

    analysis_plan: dict[str, Any]
    current_analysis_step: int

    tool_execution_results: list[dict[str, Any]]
    evidence_collected: Annotated[list[dict],operator.add]

    verification_results: dict[str, Any]
    final_report: dict[str, Any]

    errors: list[str]
    current_code: str
    retry_count: int
    last_error: str | None
    replan_count:int
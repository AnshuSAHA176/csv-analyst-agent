# In agent/graph.py
from langgraph.graph import StateGraph, END
from .state import InvestigationState
from .nodes import (
    generate_analysis_code,
    execute_analysis_step,
    verify_evidence,
    generate_final_report,
)
from .planner import create_analysis_plan
import logging

logger = logging.getLogger(__name__)


def route_after_execution(state: InvestigationState) -> str:
    # If last_error is set, we haven't hit max retries yet -> regenerate/fix code
    if state.get("last_error"):
        return "generate_code"

    # Check if more steps remain in the plan
    total_steps = len(state["analysis_plan"]["steps"])
    if state["current_analysis_step"] < total_steps:
        return "generate_code"

    # All steps processed -> move to verification
    return "verify_evidence"


def route_after_verification(state: InvestigationState) -> str:
    is_sufficient = state.get("verification_results", {}).get("is_sufficient", True)
    replan_count = state.get("replan_count", 0)
    if not is_sufficient and replan_count < 1:
        logger.warning(
                    f"replane\nreplane\nreplane\nreplane\nreplane\nreplane\nreplane\nreplane"
                )
        return "planner"
    logger.warning(
                        f"generate_report\ngenerate_report\ngenerate_report\ngenerate_report\n"
                    )
    return "generate_report"


def build_investigation_graph():
    workflow = StateGraph(InvestigationState)

    workflow.add_node("planner", create_analysis_plan)
    workflow.add_node("generate_code", generate_analysis_code)
    workflow.add_node("execute_step", execute_analysis_step)
    workflow.add_node("verify_evidence", verify_evidence)
    workflow.add_node("synthesize_report", generate_final_report)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "generate_code")
    workflow.add_edge("generate_code", "execute_step")

    workflow.add_conditional_edges(
        "execute_step",
        route_after_execution,
        {
            "generate_code": "generate_code",
            "verify_evidence": "verify_evidence",
        },
    )
    workflow.add_conditional_edges(
        "verify_evidence",
        route_after_verification,
        {"planner": "planner", "generate_report": "synthesize_report"},
    )

    workflow.add_edge("synthesize_report", END)

    return workflow.compile()

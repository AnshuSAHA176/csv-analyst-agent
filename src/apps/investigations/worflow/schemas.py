from typing import Literal
from pydantic import BaseModel, Field
from typing import Any


class AnalysisStep(BaseModel):
    step_id: int

    description: str = Field(description="What needs to be investigated.")

    hypothesis: str = Field(description="A testable hypothesis for this analysis step.")

    tool: Literal["sql", "python", "statistics"]

    expected_output: str = Field(description="What result this step should produce.")


class AnalysisPlan(BaseModel):
    reasoning: str = Field(
        description="Why this investigation approach was selected.",
    )
    steps: list[AnalysisStep] = Field(min_length=1, max_length=4)
class RecoveryAnalysisPlan(BaseModel):
    reasoning: str = Field(
        description="Why this investigation approach was selected.",
    )
    steps: list[AnalysisStep] = Field(min_length=1, max_length=2)


# In schemas.py
class GeneratedScript(BaseModel):
    reasoning: str = Field(
        description="Brief explanation of the logic and libraries used."
    )
    python_code: str = Field(description="Executable, self-contained Python script.")
    metrics_to_extract: list[str] = Field(
        description="Keys written to /workspace/result.json."
    )


# In agent/schemas.py
class VerificationReport(BaseModel):
    is_sufficient: bool = Field(
        default=True,
        description="True if collected evidence reliably answers the question.",
    )
    verified_step_ids: list[int] = Field(
        default_factory=list,
        description="Step IDs with sound methodology and sufficient sample size.",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="Statistical warnings, small sample sizes (n < 30), or missing-data biases.",
    )

class FindingItem(BaseModel):
    step_id: int
    claim: str = Field(
        description="Factual finding strictly grounded in the step's metrics."
    )
    supporting_metrics: dict[str, Any]
    confidence: Literal["high", "medium", "low"]


class FinalInvestigationReport(BaseModel):
    executive_answer: str = Field(
        description="Direct, clear answer to the user's business question."
    )
    findings: list[FindingItem]
    limitations_and_caveats: list[str]
    recommended_next_steps: list[str]

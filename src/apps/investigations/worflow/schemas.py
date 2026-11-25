from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


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
        description="Why this recovery approach was selected to resolve the verifier caveats.",
    )
    steps: list[AnalysisStep] = Field(
        min_length=1,
        max_length=4,
        description="1 to 2 targeted recovery steps (maximum 2 preferred) to fix the flagged gaps.",
    )

class GeneratedScript(BaseModel):
    reasoning: str = Field(
        description="Brief explanation of the logic and libraries used."
    )
    python_code: str = Field(description="Executable, self-contained Python script.")
    metrics_to_extract: list[str] = Field(
        description="Keys written to /workspace/result.json."
    )


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
    supporting_metrics: dict[str, Any] | list[dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "A single JSON object (key-value dict) of supporting metrics. "
            "Never pass an array—create separate FindingItem entries if comparing multiple segments."
        ),
    )
    confidence: Literal["high", "medium", "low"]

    @field_validator("supporting_metrics", mode="before")
    @classmethod
    def normalize_supporting_metrics(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, list):
            return {f"item_{i + 1}": item for i, item in enumerate(value)}
        return value if isinstance(value, dict) else {"value": value}


class FinalInvestigationReport(BaseModel):
    executive_answer: str = Field(
        description="Direct, clear answer to the user's business question."
    )
    findings: list[FindingItem]
    limitations_and_caveats: list[str]
    recommended_next_steps: list[str]
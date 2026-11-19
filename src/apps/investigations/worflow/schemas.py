from typing import Literal
from pydantic import BaseModel, Field


class AnalysisStep(BaseModel):
    step_id: int

    description: str = Field(
        description="What needs to be investigated."
    )

    hypothesis: str = Field(
        description="A testable hypothesis for this analysis step."
    )

    tool: Literal["sql", "python", "statistics"]

    expected_output: str = Field(
        description="What result this step should produce."
    )


class AnalysisPlan(BaseModel):
    reasoning: str = Field(
        description="Why this investigation approach was selected."
    )

    steps: list[AnalysisStep]
from pydantic import BaseModel, Field
from typing import List, Optional


class StepModel(BaseModel):
    step: int
    action: str
    expected: str = ""


class TestCaseModel(BaseModel):
    title: str
    type: str = "Functional"
    priority: str = "Medium"
    preconditions: List[str] = Field(default_factory=list)
    copy_paste_input: str = ""
    expected_outcome: str = ""
    ac_covered: List[str] = Field(default_factory=list)
    # Backward compatibility for legacy outputs already saved in older runs.
    steps: List[StepModel] = Field(default_factory=list)


class RequirementInput(BaseModel):
    description: str
    user_story: Optional[str] = ""
    acceptance_criteria: List[str]


class GenerateResponse(BaseModel):
    status: str
    requirement: str
    test_cases: List[TestCaseModel]
    count: int


class EvaluateResponse(BaseModel):
    status: str
    requirement: str
    accov_at_05: float
    accov_at_065: float
    negative_ratio: float
    num_test_cases: int
    test_cases: List[TestCaseModel]


class HealthResponse(BaseModel):
    status: str
    model: str
    chroma_collection_count: int

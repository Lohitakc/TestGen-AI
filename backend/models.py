from pydantic import BaseModel
from typing import List, Optional


class StepModel(BaseModel):
    step: int
    action: str
    expected: str = ""


class TestCaseModel(BaseModel):
    title: str
    type: str = "Functional"
    priority: str = "Medium"
    steps: List[StepModel]


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
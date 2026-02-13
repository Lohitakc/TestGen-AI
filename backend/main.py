from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sentence_transformers import SentenceTransformer

from backend.models import (
    RequirementInput,
    GenerateResponse,
    EvaluateResponse,
    HealthResponse,
)
from backend.test_generator import (
    load_few_shot_examples,
    build_generation_prompt,
    generate_test_cases,
)
from backend.rules import apply_qa_rules
from backend.evaluation import compute_ac_coverage, compute_negative_ratio
from backend.rag_pipeline import collection

app = FastAPI(
    title="TestGen AI",
    description="AI-powered test case generation from requirements",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

few_shot_examples = load_few_shot_examples()
embed_model = SentenceTransformer("all-MiniLM-L6-v2")
MODEL_NAME = "llama3:8b-instruct-q3_K_M"


@app.get("/health", response_model=HealthResponse)
def health_check():
    try:
        count = collection.count()
    except Exception:
        count = 0
    return HealthResponse(
        status="healthy",
        model=MODEL_NAME,
        chroma_collection_count=count,
    )


@app.post("/generate", response_model=GenerateResponse)
def generate(req: RequirementInput):
    try:
        requirement = {
            "description": req.description,
            "user_story": req.user_story or "",
            "acceptance_criteria": req.acceptance_criteria,
        }
        prompt = build_generation_prompt(requirement, few_shot_examples)
        test_cases = generate_test_cases(prompt, model_name=MODEL_NAME, requirement=requirement)
        test_cases = apply_qa_rules(requirement, test_cases)
        return GenerateResponse(
            status="success",
            requirement=req.description,
            test_cases=test_cases,
            count=len(test_cases),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(req: RequirementInput):
    try:
        requirement = {
            "description": req.description,
            "user_story": req.user_story or "",
            "acceptance_criteria": req.acceptance_criteria,
        }
        prompt = build_generation_prompt(requirement, few_shot_examples)
        test_cases = generate_test_cases(prompt, model_name=MODEL_NAME, requirement=requirement)
        test_cases = apply_qa_rules(requirement, test_cases)
        accov_05 = compute_ac_coverage(
            req.acceptance_criteria, test_cases, embed_model, threshold=0.5
        )
        accov_065 = compute_ac_coverage(
            req.acceptance_criteria, test_cases, embed_model, threshold=0.65
        )
        neg_ratio = compute_negative_ratio(test_cases)
        return EvaluateResponse(
            status="success",
            requirement=req.description,
            accov_at_05=round(accov_05, 2),
            accov_at_065=round(accov_065, 2),
            negative_ratio=round(neg_ratio, 2),
            num_test_cases=len(test_cases),
            test_cases=test_cases,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve frontend - this MUST be last
@app.get("/")
def serve_frontend():
    return FileResponse("frontend/index.html")


app.mount("/", StaticFiles(directory="frontend"), name="frontend")
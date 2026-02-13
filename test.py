import json
import time
from backend.test_generator import (
    load_few_shot_examples,
    build_generation_prompt,
    generate_test_cases,
)
from backend.rules import apply_qa_rules
from sentence_transformers import SentenceTransformer, util

# Load evaluation data
with open("data/samples/evaluation_cases.json", "r", encoding="utf-8") as f:
    requirements = json.load(f)

few_shot = load_few_shot_examples()
embed_model = SentenceTransformer("all-MiniLM-L6-v2")


def compute_accov(acceptance_criteria, test_cases, threshold=0.5):
    """Compute acceptance criteria coverage using semantic similarity."""
    if not acceptance_criteria or not test_cases:
        return 0.0

    ac_embeddings = embed_model.encode(acceptance_criteria, convert_to_tensor=True)

    tc_texts = []
    for tc in test_cases:
        parts = [tc.get("title", "")]
        for step in tc.get("steps", []):
            if isinstance(step, dict):
                parts.append(step.get("action", ""))
                parts.append(step.get("expected", ""))
        tc_texts.append(" ".join(parts))

    if not tc_texts:
        return 0.0

    tc_embeddings = embed_model.encode(tc_texts, convert_to_tensor=True)

    cosine_scores = util.cos_sim(ac_embeddings, tc_embeddings)

    covered = 0
    for i in range(len(acceptance_criteria)):
        max_score = cosine_scores[i].max().item()
        if max_score >= threshold:
            covered += 1

    return round(covered / len(acceptance_criteria), 2)


def compute_negative_ratio(test_cases):
    if not test_cases:
        return 0.0
    neg = sum(1 for tc in test_cases if tc.get("type", "").lower() == "negative")
    return round(neg / len(test_cases), 2)


print("\n=== Starting Batch Evaluation ===\n")

all_results = []
all_generated = []
total = len(requirements)
success_count = 0

for idx, req in enumerate(requirements):
    req_id = req["id"]
    print(f"Processing {req_id} ({idx + 1}/{total})...")

    ac = req.get("acceptance_criteria", [])
    existing_tc = req.get("test_cases", [])

    accov_before = compute_accov(ac, existing_tc, threshold=0.5)

    try:
        prompt = build_generation_prompt(req, few_shot)
        generated_tc = generate_test_cases(prompt)
        generated_tc = apply_qa_rules(req, generated_tc)
        success_count += 1

    except Exception as e:
        print(f"❌ Failed to process {req_id}: {e}")
        generated_tc = []

    accov_after_05 = compute_accov(ac, generated_tc, threshold=0.5)
    accov_after_065 = compute_accov(ac, generated_tc, threshold=0.65)
    neg_ratio = compute_negative_ratio(generated_tc)

    result = {
        "id": req_id,
        "domain": req.get("domain", "unknown"),
        "accov_before": accov_before,
        "accov_after_05": accov_after_05,
        "accov_after_065": accov_after_065,
        "negative_ratio": neg_ratio,
        "num_test_cases": len(generated_tc),
    }
    all_results.append(result)

    all_generated.append({
        "id": req_id,
        "description": req["description"],
        "acceptance_criteria": ac,
        "generated_test_cases": generated_tc,
    })

    print(
        f"  ACCov before: {accov_before:.2f} | after@0.5: {accov_after_05:.2f} | "
        f"after@0.65: {accov_after_065:.2f} | NegRatio: {neg_ratio:.2f} | tests: {len(generated_tc)}"
    )

    # Small delay to avoid overwhelming Ollama
    time.sleep(1)

# Save results
with open("data/samples/evaluation_results.json", "w", encoding="utf-8") as f:
    json.dump(all_results, f, indent=2)

with open("data/samples/generated_tests.json", "w", encoding="utf-8") as f:
    json.dump(all_generated, f, indent=2)

print(f"\n=== Evaluation Complete ===")
print(f"Success: {success_count}/{total}")
print(f"Results saved to evaluation_results.json and generated_tests.json")
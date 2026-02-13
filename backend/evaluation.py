from sentence_transformers import util

def compute_ac_coverage(acceptance_criteria, test_cases, model, threshold=0.5):
    """
    Computes semantic Acceptance Criteria Coverage (ACCov).
    An acceptance criterion is considered covered if any generated
    test case semantically matches it above the given threshold.
    """

    if not acceptance_criteria:
        return 0.0

    # Pre-encode acceptance criteria
    ac_embeddings = {
        ac: model.encode(ac, convert_to_tensor=True)
        for ac in acceptance_criteria
    }

    covered = 0

    for ac, ac_emb in ac_embeddings.items():
        matched = False

        for tc in test_cases:
            # Combine multiple signals for better matching
            comparison_texts = [
                tc.get("title", ""),
                *(step.get("expected", "") for step in tc.get("steps", []))
            ]

            for text in comparison_texts:
                if not text:
                    continue

                text_emb = model.encode(text, convert_to_tensor=True)
                similarity = float(util.cos_sim(ac_emb, text_emb))

                if similarity >= threshold:
                    matched = True
                    break

            if matched:
                break

        if matched:
            covered += 1

    return covered / len(acceptance_criteria)


from sentence_transformers import util

def explain_ac_matching(acceptance_criteria, test_cases, model, threshold=0.5):
    """
    Debug utility to explain why acceptance criteria
    are or are not covered by generated test cases.
    """

    explanations = {}

    for ac in acceptance_criteria:
        ac_emb = model.encode(ac, convert_to_tensor=True)
        matches = []

        for tc in test_cases:
            # Combine title + expected results
            texts = [tc.get("title", "")] + [
                step.get("expected", "") for step in tc.get("steps", [])
            ]

            for text in texts:
                if not text:
                    continue

                text_emb = model.encode(text, convert_to_tensor=True)
                similarity = float(util.cos_sim(ac_emb, text_emb))

                matches.append({
                    "text": text,
                    "similarity": round(similarity, 3)
                })

        # Sort matches by similarity (descending)
        explanations[ac] = sorted(
            matches,
            key=lambda x: x["similarity"],
            reverse=True
        )

    return explanations

def compute_negative_ratio(test_cases):
    if not test_cases:
        return 0.0

    negative_count = 0
    for tc in test_cases:
        tc_type = tc.get("type", "").lower()
        if tc_type in ["negative", "boundary"]:
            negative_count += 1

    return negative_count / len(test_cases)

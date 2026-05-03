from sentence_transformers import util


def _comparison_texts(test_case):
    texts = [
        test_case.get("title", ""),
        test_case.get("copy_paste_input", ""),
        test_case.get("expected_outcome", ""),
        " ".join(test_case.get("ac_covered", []))
        if isinstance(test_case.get("ac_covered"), list)
        else "",
    ]

    # Backward compatibility with legacy step-based outputs.
    for step in test_case.get("steps", []) if isinstance(test_case.get("steps", []), list) else []:
        texts.append(step.get("action", ""))
        texts.append(step.get("expected", ""))

    return [text for text in texts if str(text).strip()]


def compute_ac_coverage(acceptance_criteria, test_cases, model, threshold=0.5):
    """
    Computes semantic Acceptance Criteria Coverage (ACCov).
    An acceptance criterion is considered covered if any generated
    test case semantically matches it above the given threshold.
    """

    if not acceptance_criteria:
        return 0.0

    ac_embeddings = {
        ac: model.encode(ac, convert_to_tensor=True)
        for ac in acceptance_criteria
    }

    covered = 0

    for ac, ac_emb in ac_embeddings.items():
        matched = False

        for test_case in test_cases:
            for text in _comparison_texts(test_case):
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


def explain_ac_matching(acceptance_criteria, test_cases, model, threshold=0.5):
    """
    Debug utility to explain why acceptance criteria
    are or are not covered by generated test cases.
    """

    explanations = {}

    for ac in acceptance_criteria:
        ac_emb = model.encode(ac, convert_to_tensor=True)
        matches = []

        for test_case in test_cases:
            for text in _comparison_texts(test_case):
                text_emb = model.encode(text, convert_to_tensor=True)
                similarity = float(util.cos_sim(ac_emb, text_emb))

                matches.append({
                    "text": text,
                    "similarity": round(similarity, 3),
                    "meets_threshold": similarity >= threshold,
                })

        explanations[ac] = sorted(
            matches,
            key=lambda item: item["similarity"],
            reverse=True,
        )

    return explanations


def compute_negative_ratio(test_cases):
    if not test_cases:
        return 0.0

    negative_count = 0
    for test_case in test_cases:
        tc_type = test_case.get("type", "").lower()
        if tc_type in ["negative", "boundary"]:
            negative_count += 1

    return negative_count / len(test_cases)

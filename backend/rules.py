import json
import re
from typing import Any, Dict, List, Tuple

RIGOROUS_PREFIX = "[RIGOROUS]"
SUPPLEMENTAL_PREFIX = "[SUPPLEMENTAL]"

GENERIC_MARKERS = (
    "valid input",
    "invalid input",
    "test data",
    "sample data",
    "happy path",
    "basic check",
    "quick check",
    "execute test",
    "verify expected behavior",
)

STOPWORDS = {
    "the",
    "and",
    "with",
    "from",
    "this",
    "that",
    "when",
    "where",
    "must",
    "should",
    "have",
    "has",
    "for",
    "into",
    "able",
    "user",
    "users",
    "system",
    "flow",
    "case",
    "cases",
}


def _normalize_space(text: Any, max_len: int = 340) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3].rstrip() + "..."


def _normalize_title(title: Any) -> str:
    return re.sub(r"\s+", " ", str(title).strip().lower())


def _with_prefix(title: Any, prefix: str) -> str:
    clean = _normalize_space(title, max_len=140) or "Untitled test case"
    if clean.lower().startswith(prefix.lower()):
        return clean
    return f"{prefix} {clean}"


def _to_str_list(value: Any, max_items: int = 5, max_len: int = 180) -> List[str]:
    if isinstance(value, list):
        return [
            _normalize_space(item, max_len=max_len)
            for item in value
            if str(item).strip()
        ][:max_items]
    if value is None:
        return []

    text = str(value).strip()
    if not text:
        return []
    if "\n" in text:
        return [
            _normalize_space(line, max_len=max_len)
            for line in text.splitlines()
            if line.strip()
        ][:max_items]
    return [_normalize_space(text, max_len=max_len)]


def _extract_acceptance_criteria(requirement: Dict[str, Any]) -> List[str]:
    raw = requirement.get("acceptance_criteria", [])
    criteria = _to_str_list(raw, max_items=40, max_len=220)
    if criteria:
        return criteria

    fallback = _normalize_space(
        requirement.get("description", "Feature behavior should work correctly"),
        max_len=220,
    )
    return [fallback]


def _coerce_steps(raw_steps: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_steps, list):
        return []

    parsed = []
    for i, step in enumerate(raw_steps):
        if isinstance(step, dict):
            parsed.append(
                {
                    "step": step.get("step", i + 1),
                    "action": _normalize_space(step.get("action", step.get("description", "")), max_len=220),
                    "expected": _normalize_space(step.get("expected", step.get("expected_result", "")), max_len=220),
                }
            )
        elif isinstance(step, str):
            parsed.append({"step": i + 1, "action": _normalize_space(step, max_len=220), "expected": ""})
    return parsed


def _steps_to_input(steps: List[Dict[str, Any]]) -> str:
    actions = [step.get("action", "").strip() for step in steps if step.get("action", "").strip()]
    if not actions:
        return "input:\nfield=value\nsubmit=true"
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(actions[:4], start=1))


def _steps_to_expected(steps: List[Dict[str, Any]]) -> str:
    expected = [step.get("expected", "").strip() for step in steps if step.get("expected", "").strip()]
    if not expected:
        return "Operation should complete with the expected validation or success state."
    if len(expected) == 1:
        return _normalize_space(expected[0], max_len=260)
    return _normalize_space(" | ".join(expected[:3]), max_len=280)


def _extract_requirement_tokens(requirement: Dict[str, Any]) -> List[str]:
    criteria = requirement.get("acceptance_criteria", [])
    criteria_text = " ".join(criteria) if isinstance(criteria, list) else str(criteria or "")
    combined = " ".join(
        [
            str(requirement.get("description", "")),
            str(requirement.get("user_story", "")),
            criteria_text,
        ]
    ).lower()
    tokens = re.findall(r"[a-z0-9_]{4,}", combined)

    deduped = []
    seen = set()
    for token in tokens:
        if token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
        if len(deduped) >= 20:
            break
    return deduped


def _topic_phrase(requirement_tokens: List[str]) -> str:
    if len(requirement_tokens) >= 3:
        return f"{requirement_tokens[0]} {requirement_tokens[1]} {requirement_tokens[2]}"
    if len(requirement_tokens) >= 2:
        return f"{requirement_tokens[0]} {requirement_tokens[1]}"
    if requirement_tokens:
        return requirement_tokens[0]
    return "target workflow"


def _payload_to_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _infer_domain(description: str, criterion: str) -> str:
    text = f"{description} {criterion}".lower()
    if any(word in text for word in ["login", "log in", "signin", "sign in", "auth", "password", "credential"]):
        return "login"
    if any(word in text for word in ["register", "registration", "signup", "sign up", "patient", "profile creation"]):
        return "registration"
    if any(word in text for word in ["payment", "invoice", "billing", "amount", "transaction"]):
        return "payment"
    return "generic"


def _build_domain_payload(
    requirement: Dict[str, Any],
    criterion: str,
    variant_index: int,
) -> Dict[str, str]:
    description = _normalize_space(requirement.get("description", ""), max_len=140)
    criterion_short = _normalize_space(criterion, max_len=140)
    domain = _infer_domain(description, criterion_short)
    case_id = f"TC-RIG-{variant_index + 1:02d}"

    if domain == "login":
        payload = {
            "case_id": case_id,
            "email": "qa.user01@product.test",
            "password": "Secure#1234",
            "remember_me": True,
            "action": "submit_login",
        }
        if variant_index == 1:
            payload["email"] = "qa.user01@bad-domain"
        elif variant_index == 2:
            payload["password"] = "A1#"
        elif variant_index == 3:
            payload["password"] = "A" * 65 + "#9"
        elif variant_index == 4:
            payload["session_source"] = "web_portal"
            payload["follow_up_action"] = "open_dashboard_widgets"
        elif variant_index == 5:
            payload["attempt_id"] = "ATTEMPT-DUP-001"
            payload["repeat_submit_count"] = 2
        elif variant_index == 6:
            payload["session_token"] = "expired-token-simulated"
            payload["retry_after_reauth"] = True
        elif variant_index == 7:
            payload["parallel_login_requests"] = 25
        elif variant_index == 8:
            payload["email"] = "admin' OR '1'='1@example.test"
        elif variant_index == 9:
            payload["post_login_refresh"] = True
            payload["verify_protected_route"] = "/dashboard"
    elif domain == "registration":
        payload = {
            "case_id": case_id,
            "full_name": "Aarav Nair",
            "dob": "1995-02-14",
            "gender": "Male",
            "phone": "9876543210",
            "email": "aarav.nair@patient.test",
            "action": "submit_registration",
        }
        if variant_index == 1:
            payload["phone"] = "98A76B3210"
        elif variant_index == 2:
            payload["full_name"] = "A"
        elif variant_index == 3:
            payload["full_name"] = "A" * 101
        elif variant_index == 4:
            payload["link_to_existing_user_profile"] = True
        elif variant_index == 5:
            payload["request_id"] = "REG-DUP-002"
            payload["repeat_submit_count"] = 2
        elif variant_index == 6:
            payload["network_interruption"] = "simulate_after_submit"
        elif variant_index == 7:
            payload["batch_registration_size"] = 75
        elif variant_index == 8:
            payload["full_name"] = "<script>alert('x')</script>"
        elif variant_index == 9:
            payload["refresh_after_submit"] = True
            payload["verify_created_record"] = True
    elif domain == "payment":
        payload = {
            "case_id": case_id,
            "invoice_id": "INV-5842",
            "amount": 1250.75,
            "currency": "INR",
            "payment_method": "UPI",
            "action": "submit_payment",
        }
        if variant_index == 1:
            payload["amount"] = -1
        elif variant_index == 2:
            payload["amount"] = 0.01
        elif variant_index == 3:
            payload["amount"] = 9999999.99
        elif variant_index == 4:
            payload["verify_ledger_sync"] = True
        elif variant_index == 5:
            payload["transaction_id"] = "TXN-DUP-05"
            payload["repeat_submit_count"] = 2
        elif variant_index == 6:
            payload["network_interruption"] = "simulate_timeout"
        elif variant_index == 7:
            payload["parallel_payment_requests"] = 20
        elif variant_index == 8:
            payload["invoice_id"] = "INV-5842' OR 1=1 --"
        elif variant_index == 9:
            payload["refresh_after_submit"] = True
            payload["verify_receipt_download"] = True
    else:
        token_source = _extract_requirement_tokens(requirement)[:4]
        payload = {
            "case_id": case_id,
            "feature_context": description or "target_workflow",
            "criterion_ref": criterion_short,
            "action": "submit",
            "test_values": {
                "field_a": token_source[0] if len(token_source) > 0 else "value_a",
                "field_b": token_source[1] if len(token_source) > 1 else "value_b",
            },
        }
        if variant_index == 1:
            payload["test_values"]["field_b"] = ""
        elif variant_index == 2:
            payload["test_values"]["field_a"] = "x"
        elif variant_index == 3:
            payload["test_values"]["field_a"] = "X" * 120
        elif variant_index == 4:
            payload["verify_related_module_sync"] = True
        elif variant_index == 5:
            payload["repeat_submit_count"] = 2
        elif variant_index == 6:
            payload["network_interruption"] = "simulate_after_submit"
        elif variant_index == 7:
            payload["parallel_requests"] = 15
        elif variant_index == 8:
            payload["test_values"]["field_a"] = "' OR 1=1 --"
        elif variant_index == 9:
            payload["refresh_after_submit"] = True

    return {
        "copy_paste_input": _payload_to_json(payload),
        "expected_outcome": _build_expected_outcome(criterion_short, variant_index),
    }


def _build_expected_outcome(criterion_short: str, variant_index: int) -> str:
    outcomes = [
        f"Submission succeeds and clearly satisfies: {criterion_short}. Response shows success state and correct redirect/data update.",
        f"Request is rejected with a clear validation error tied to: {criterion_short}. No invalid record/session is created.",
        f"Lower-bound input is processed correctly and still satisfies: {criterion_short}.",
        f"Upper-bound input is handled safely with consistent behavior for: {criterion_short}.",
        f"Primary action and downstream module remain synchronized for: {criterion_short}.",
        f"Duplicate submissions are idempotent: only one effective transaction is kept for: {criterion_short}.",
        f"After interruption/retry, system recovers without duplicates or corruption, preserving: {criterion_short}.",
        f"Under moderate concurrency, response remains stable and functional checks for {criterion_short} still pass.",
        f"Security abuse attempt is blocked and logged; no sensitive data leakage occurs for: {criterion_short}.",
        f"After refresh/reopen, persisted state remains accurate and auditable for: {criterion_short}.",
    ]
    return outcomes[variant_index % len(outcomes)]


def _build_rigorous_case(
    requirement: Dict[str, Any],
    criterion: str,
    variant_index: int,
    requirement_tokens: List[str],
) -> Dict[str, Any]:
    variants = [
        ("Core flow validation", "Functional", "High"),
        ("Invalid format rejection", "Negative", "High"),
        ("Lower boundary check", "Boundary", "High"),
        ("Upper boundary check", "Boundary", "High"),
        ("Cross-module consistency", "Integration", "Medium"),
        ("Duplicate request defense", "Negative", "Medium"),
        ("Interruption recovery", "Negative", "Medium"),
        ("Concurrency and throughput", "Performance", "Medium"),
        ("Security abuse resistance", "Security", "High"),
        ("State persistence audit", "Integration", "Medium"),
    ]

    label, tc_type, priority = variants[variant_index % len(variants)]
    topic = _topic_phrase(requirement_tokens)
    criterion_short = _normalize_space(criterion, max_len=100)
    description_short = _normalize_space(requirement.get("description", "Target workflow"), max_len=90)
    payload = _build_domain_payload(requirement, criterion, variant_index)

    return {
        "title": f"{RIGOROUS_PREFIX} {label}: {criterion_short}",
        "type": tc_type,
        "priority": priority,
        "preconditions": [
            f"Feature under test is reachable: {description_short}.",
            f"Tester uses a clean test account/session and baseline data for: {topic}.",
        ],
        "copy_paste_input": payload["copy_paste_input"],
        "expected_outcome": payload["expected_outcome"],
        "ac_covered": [criterion_short],
        "steps": [],
    }


def _case_text(test_case: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(test_case.get("title", "")),
            str(test_case.get("copy_paste_input", "")),
            str(test_case.get("expected_outcome", "")),
            " ".join(_to_str_list(test_case.get("ac_covered", []))),
        ]
    ).lower()


def _matches_criterion(test_case: Dict[str, Any], criterion: str) -> bool:
    criterion_tokens = re.findall(r"[a-z0-9_]{4,}", criterion.lower())
    if not criterion_tokens:
        return False

    text = _case_text(test_case)
    hits = sum(1 for token in criterion_tokens[:6] if token in text)
    return hits >= 2 or (hits >= 1 and len(criterion_tokens) <= 2)


def _specificity_score(test_case: Dict[str, Any], requirement_tokens: List[str]) -> int:
    title = str(test_case.get("title", ""))
    copy_input = str(test_case.get("copy_paste_input", ""))
    expected = str(test_case.get("expected_outcome", ""))
    combined = f"{title} {copy_input} {expected}".lower()

    score = 0
    if title.lower().startswith(RIGOROUS_PREFIX.lower()):
        score += 1
    if 6 <= len(copy_input.split()) <= 140:
        score += 1
    if 6 <= len(expected.split()) <= 90:
        score += 1
    if any(token in combined for token in requirement_tokens[:8]):
        score += 1
    if sum(1 for token in requirement_tokens[:12] if token in combined) >= 3:
        score += 1
    if any(char.isdigit() for char in copy_input):
        score += 1
    if any(marker in copy_input for marker in ["=", ":", "\n", "@", "#", "{", "}"]):
        score += 1
    if _to_str_list(test_case.get("ac_covered", [])):
        score += 1

    generic_hits = sum(1 for marker in GENERIC_MARKERS if marker in combined)
    score -= generic_hits * 2
    return score


def _is_weak_case(test_case: Dict[str, Any], requirement_tokens: List[str]) -> bool:
    if _specificity_score(test_case, requirement_tokens) < 4:
        return True
    copy_input = str(test_case.get("copy_paste_input", "")).strip()
    expected = str(test_case.get("expected_outcome", "")).strip()

    if len(copy_input) < 20:
        return True
    if len(expected) < 18:
        return True

    lowered = copy_input.lower()
    generic_text_patterns = (
        r"^\d+\.\s*enter\s+",
        r"\benter valid\b",
        r"\benter invalid\b",
        r"\bclick login\b",
        r"\bperform\b.*\baction\b",
    )
    if any(re.search(pattern, lowered) for pattern in generic_text_patterns):
        return True

    has_copy_paste_structure = any(marker in copy_input for marker in ["{", "}", ":", "="])
    if not has_copy_paste_structure:
        return True
    return False


def _normalize_case(
    requirement: Dict[str, Any],
    test_case: Dict[str, Any],
    criteria: List[str],
) -> Dict[str, Any]:
    steps = _coerce_steps(test_case.get("steps", []))
    normalized = {
        "title": _with_prefix(test_case.get("title", "Untitled"), RIGOROUS_PREFIX),
        "type": _normalize_space(test_case.get("type", "Functional"), max_len=24),
        "priority": _normalize_space(test_case.get("priority", "Medium"), max_len=16),
        "preconditions": _to_str_list(test_case.get("preconditions", []), max_items=3),
        "copy_paste_input": _normalize_space(
            test_case.get(
                "copy_paste_input",
                test_case.get("input", test_case.get("test_input", "")),
            ),
            max_len=520,
        ),
        "expected_outcome": _normalize_space(
            test_case.get("expected_outcome", test_case.get("expected", "")),
            max_len=320,
        ),
        "ac_covered": _to_str_list(test_case.get("ac_covered", []), max_items=4, max_len=220),
        "steps": [],
    }

    if not normalized["copy_paste_input"]:
        normalized["copy_paste_input"] = _steps_to_input(steps)
    if not normalized["expected_outcome"]:
        normalized["expected_outcome"] = _steps_to_expected(steps)
    if not normalized["preconditions"]:
        normalized["preconditions"] = [
            f"Open the workflow for {_topic_phrase(_extract_requirement_tokens(requirement))}.",
            "Use a test account/session with required permissions.",
        ]

    if not normalized["ac_covered"]:
        matched = [criterion for criterion in criteria if _matches_criterion(normalized, criterion)]
        normalized["ac_covered"] = matched[:2] if matched else [criteria[0]]

    valid_types = {
        "Functional",
        "Negative",
        "Boundary",
        "Integration",
        "Performance",
        "Regression",
        "Security",
        "Usability",
    }
    if normalized["type"] not in valid_types:
        normalized["type"] = "Functional"

    valid_priorities = {"High", "Medium", "Low"}
    if normalized["priority"] not in valid_priorities:
        normalized["priority"] = "Medium"

    return normalized


def _dedupe_cases(test_cases: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], set]:
    unique = []
    seen = set()
    for test_case in test_cases:
        title_key = _normalize_title(test_case.get("title", ""))
        input_key = _normalize_space(test_case.get("copy_paste_input", ""), max_len=120).lower()
        dedupe_key = f"{title_key}|{input_key}"
        if dedupe_key in seen:
            continue
        unique.append(test_case)
        seen.add(dedupe_key)
    return unique, seen


def ensure_suite_requirements(requirement, test_cases, min_rigorous=10, min_supplemental=0):
    del min_supplemental  # Kept in signature for backward compatibility with older calls.

    criteria = _extract_acceptance_criteria(requirement)
    requirement_tokens = _extract_requirement_tokens(requirement)

    normalized_cases = []
    for test_case in test_cases:
        if not isinstance(test_case, dict):
            continue
        normalized = _normalize_case(requirement, test_case, criteria)
        if _is_weak_case(normalized, requirement_tokens):
            continue
        normalized_cases.append(normalized)

    unique_cases, seen_keys = _dedupe_cases(normalized_cases)
    ranked_cases = sorted(
        unique_cases,
        key=lambda case: _specificity_score(case, requirement_tokens),
        reverse=True,
    )

    rigorous = ranked_cases[:min_rigorous]

    criterion_index = 0
    variant_index = 0
    while len(rigorous) < min_rigorous:
        criterion = criteria[criterion_index % len(criteria)]
        candidate = _build_rigorous_case(
            requirement,
            criterion=criterion,
            variant_index=variant_index,
            requirement_tokens=requirement_tokens,
        )
        variant_index += 1
        criterion_index += 1

        title_key = _normalize_title(candidate.get("title", ""))
        input_key = _normalize_space(candidate.get("copy_paste_input", ""), max_len=120).lower()
        dedupe_key = f"{title_key}|{input_key}"
        if dedupe_key in seen_keys:
            continue
        rigorous.append(candidate)
        seen_keys.add(dedupe_key)

    # Ensure every acceptance criterion is explicitly mapped to at least one test case.
    for criterion in criteria:
        if any(criterion in case.get("ac_covered", []) for case in rigorous):
            continue
        fallback_index = criteria.index(criterion) % len(rigorous)
        rigorous[fallback_index]["ac_covered"] = list(
            dict.fromkeys(rigorous[fallback_index].get("ac_covered", []) + [criterion])
        )

    return rigorous[:min_rigorous]


def apply_qa_rules(requirement, test_cases):
    """
    Apply deterministic QA patches and enforce a strict output shape:
    - exactly 10 rigorous, requirement-aware, copy-paste test cases
    - topic-specific and non-generic content
    """
    return ensure_suite_requirements(
        requirement,
        test_cases,
        min_rigorous=10,
        min_supplemental=0,
    )

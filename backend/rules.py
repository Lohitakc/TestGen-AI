import re

RIGOROUS_PREFIX = "[RIGOROUS]"
SUPPLEMENTAL_PREFIX = "[SUPPLEMENTAL]"


def _normalize_title(title):
    return re.sub(r"\s+", " ", str(title).strip().lower())


def _with_prefix(title, prefix):
    clean = str(title).strip() or "Untitled test case"
    if clean.lower().startswith(prefix.lower()):
        return clean
    return f"{prefix} {clean}"


def _extract_acceptance_criteria(requirement):
    raw = requirement.get("acceptance_criteria", [])
    if isinstance(raw, list):
        criteria = [str(item).strip() for item in raw if str(item).strip()]
    else:
        criteria = [str(raw).strip()] if str(raw).strip() else []

    if not criteria:
        fallback = requirement.get("description", "Feature behavior should work correctly")
        criteria = [fallback]
    return criteria


def _looks_simple_test_case(tc):
    title = str(tc.get("title", "")).lower()
    steps = tc.get("steps", []) if isinstance(tc.get("steps", []), list) else []
    simple_markers = ("smoke", "basic", "sanity", "happy path", "quick check")

    if title.startswith(SUPPLEMENTAL_PREFIX.lower()):
        return True
    if any(marker in title for marker in simple_markers):
        return True
    if len(steps) <= 2:
        return True
    if tc.get("priority", "").lower() == "low" and tc.get("type", "").lower() == "functional":
        return True
    return False


def _build_rigorous_case(requirement, criterion, variant_index):
    description = requirement.get("description", "the feature")
    criterion_short = criterion.strip()[:110]

    variants = [
        {
            "label": "Core flow validation",
            "type": "Functional",
            "priority": "High",
            "steps": [
                {"step": 1, "action": f"Open {description} and prepare valid test data for '{criterion_short}'", "expected": "Feature is ready for execution"},
                {"step": 2, "action": "Execute the primary user flow end-to-end", "expected": "Flow progresses without validation or system errors"},
                {"step": 3, "action": "Submit/commit the action and capture resulting state", "expected": f"Outcome satisfies criterion: {criterion_short}"},
                {"step": 4, "action": "Refresh and re-open the feature state", "expected": "Committed behavior remains consistent after reload"},
            ],
        },
        {
            "label": "Invalid data handling",
            "type": "Negative",
            "priority": "High",
            "steps": [
                {"step": 1, "action": f"Navigate to {description} and enter deliberately invalid data related to '{criterion_short}'", "expected": "Invalid input is accepted into form controls only"},
                {"step": 2, "action": "Trigger the same action as the primary flow", "expected": "Operation is blocked"},
                {"step": 3, "action": "Inspect error feedback and field states", "expected": "Clear validation message is shown and no unsafe data is persisted"},
                {"step": 4, "action": "Retry using corrected input", "expected": "System recovers and allows valid operation"},
            ],
        },
        {
            "label": "Boundary limit verification",
            "type": "Boundary",
            "priority": "High",
            "steps": [
                {"step": 1, "action": f"Identify min/max boundary inputs implied by '{criterion_short}'", "expected": "Boundary values are prepared"},
                {"step": 2, "action": "Execute flow with minimum valid boundary", "expected": "Minimum valid input is accepted"},
                {"step": 3, "action": "Execute flow with maximum valid boundary", "expected": "Maximum valid input is accepted"},
                {"step": 4, "action": "Execute flow just outside allowed boundary", "expected": "Out-of-range value is rejected with actionable message"},
            ],
        },
        {
            "label": "Cross-state consistency",
            "type": "Integration",
            "priority": "Medium",
            "steps": [
                {"step": 1, "action": f"Complete {description} flow that satisfies '{criterion_short}'", "expected": "Initial action succeeds"},
                {"step": 2, "action": "Navigate to dependent page/API state or linked module", "expected": "Related module reflects latest update"},
                {"step": 3, "action": "Perform browser refresh or reopen session", "expected": "State remains synchronized across views"},
                {"step": 4, "action": "Repeat action with alternate valid data", "expected": "No stale cache or synchronization defects appear"},
            ],
        },
        {
            "label": "Resilience under interruption",
            "type": "Negative",
            "priority": "Medium",
            "steps": [
                {"step": 1, "action": f"Start {description} workflow aligned to '{criterion_short}'", "expected": "Workflow starts normally"},
                {"step": 2, "action": "Interrupt with navigation/back action or simulated request failure", "expected": "System handles interruption gracefully"},
                {"step": 3, "action": "Resume workflow from the previous step", "expected": "No data corruption or duplicate operation occurs"},
                {"step": 4, "action": "Finalize the workflow", "expected": "Final state is valid and consistent"},
            ],
        },
        {
            "label": "Performance guardrail",
            "type": "Performance",
            "priority": "Medium",
            "steps": [
                {"step": 1, "action": f"Prepare representative dataset for {description}", "expected": "Dataset is loaded and measurable"},
                {"step": 2, "action": f"Execute workflow tied to '{criterion_short}' five consecutive times", "expected": "All runs complete successfully"},
                {"step": 3, "action": "Measure response time and UI responsiveness", "expected": "No severe latency spikes or UI freeze occurs"},
                {"step": 4, "action": "Validate final output integrity after repeated runs", "expected": "No duplicate, missing, or inconsistent records"},
            ],
        },
        {
            "label": "Security abuse check",
            "type": "Security",
            "priority": "High",
            "steps": [
                {"step": 1, "action": f"Access {description} with an account lacking target permissions", "expected": "Restricted actions are visible but controlled"},
                {"step": 2, "action": f"Attempt to force behavior related to '{criterion_short}' via direct URL/API tampering", "expected": "Request is denied"},
                {"step": 3, "action": "Inspect response and audit trail", "expected": "No sensitive data leak and failure is logged"},
                {"step": 4, "action": "Retry with authorized account", "expected": "Authorized flow succeeds without side effects from prior denial"},
            ],
        },
    ]

    variant = variants[variant_index % len(variants)]
    return {
        "title": f"{RIGOROUS_PREFIX} {variant['label']}: {criterion_short}",
        "type": variant["type"],
        "priority": variant["priority"],
        "steps": variant["steps"],
    }


def _build_supplemental_case(requirement, index):
    description = requirement.get("description", "the feature")
    templates = [
        {
            "title": f"{SUPPLEMENTAL_PREFIX} Basic smoke flow for {description}",
            "type": "Functional",
            "priority": "Low",
            "steps": [
                {"step": 1, "action": f"Open the page or entry point for {description}", "expected": "Page loads without runtime errors"},
                {"step": 2, "action": "Perform one valid happy-path action", "expected": "User action completes successfully"},
                {"step": 3, "action": "Verify confirmation or success indicator", "expected": "Success message/state is visible"},
            ],
        },
        {
            "title": f"{SUPPLEMENTAL_PREFIX} UI control and navigation check for {description}",
            "type": "Functional",
            "priority": "Low",
            "steps": [
                {"step": 1, "action": "Open page and inspect key controls", "expected": "Primary controls and labels are visible"},
                {"step": 2, "action": "Navigate forward/back between related views", "expected": "Navigation works and no blank/error page appears"},
                {"step": 3, "action": "Return to the feature page", "expected": "Page state is stable and interactive"},
            ],
        },
        {
            "title": f"{SUPPLEMENTAL_PREFIX} Basic validation message check for {description}",
            "type": "Negative",
            "priority": "Low",
            "steps": [
                {"step": 1, "action": "Leave one key input blank", "expected": "Client allows interaction up to submit"},
                {"step": 2, "action": "Submit the form/action", "expected": "Friendly validation message appears"},
                {"step": 3, "action": "Provide valid value and resubmit", "expected": "Validation message clears and flow resumes"},
            ],
        },
    ]
    return templates[index % len(templates)]


def _dedupe_by_title(test_cases):
    unique = []
    seen = set()
    for tc in test_cases:
        title_key = _normalize_title(tc.get("title", ""))
        if title_key and title_key not in seen:
            unique.append(tc)
            seen.add(title_key)
    return unique, seen


def ensure_suite_requirements(requirement, test_cases, min_rigorous=10, min_supplemental=2):
    criteria = _extract_acceptance_criteria(requirement)

    classified = []
    for tc in test_cases:
        if not isinstance(tc, dict):
            continue
        normalized = {
            "title": tc.get("title", "Untitled"),
            "type": tc.get("type", "Functional"),
            "priority": tc.get("priority", "Medium"),
            "steps": tc.get("steps", []),
        }

        if _looks_simple_test_case(normalized):
            normalized["title"] = _with_prefix(normalized["title"], SUPPLEMENTAL_PREFIX)
        else:
            normalized["title"] = _with_prefix(normalized["title"], RIGOROUS_PREFIX)
        classified.append(normalized)

    unique_cases, seen_titles = _dedupe_by_title(classified)
    rigorous = [tc for tc in unique_cases if tc["title"].lower().startswith(RIGOROUS_PREFIX.lower())]
    supplemental = [tc for tc in unique_cases if tc["title"].lower().startswith(SUPPLEMENTAL_PREFIX.lower())]

    criterion_index = 0
    variant_index = 0
    while len(rigorous) < min_rigorous:
        criterion = criteria[criterion_index % len(criteria)]
        candidate = _build_rigorous_case(requirement, criterion, variant_index)
        variant_index += 1
        criterion_index += 1

        key = _normalize_title(candidate["title"])
        if key in seen_titles:
            continue
        rigorous.append(candidate)
        seen_titles.add(key)

    supplemental_index = 0
    while len(supplemental) < min_supplemental:
        candidate = _build_supplemental_case(requirement, supplemental_index)
        supplemental_index += 1
        key = _normalize_title(candidate["title"])
        if key in seen_titles:
            continue
        supplemental.append(candidate)
        seen_titles.add(key)

    return rigorous + supplemental


def apply_qa_rules(requirement, test_cases):
    """
    Apply deterministic QA patches and enforce suite minimums:
    - at least 10 rigorous feature-focused cases
    - plus supplemental simple checks
    """
    rules_added = []
    description = requirement.get("description", "").lower()
    acceptance_criteria = " ".join(
        requirement.get("acceptance_criteria", [])
        if isinstance(requirement.get("acceptance_criteria"), list)
        else [str(requirement.get("acceptance_criteria", ""))]
    ).lower()

    existing_titles = {_normalize_title(tc.get("title", "")) for tc in test_cases}

    if any(word in description for word in ["login", "register", "submit", "form"]):
        candidate_title = "Empty mandatory field validation"
        if not any("empty" in title and "field" in title for title in existing_titles):
            rules_added.append(
                {
                    "title": candidate_title,
                    "type": "Negative",
                    "priority": "High",
                    "steps": [
                        {"step": 1, "action": "Leave mandatory fields empty", "expected": "Fields remain empty"},
                        {"step": 2, "action": "Submit form", "expected": "Validation error messages displayed"},
                        {"step": 3, "action": "Fill mandatory fields and resubmit", "expected": "Validation errors clear and flow proceeds"},
                    ],
                }
            )

    if any(word in acceptance_criteria for word in ["password", "pin", "secret"]):
        if not any("mask" in title for title in existing_titles):
            rules_added.append(
                {
                    "title": "Sensitive input masking",
                    "type": "Functional",
                    "priority": "High",
                    "steps": [
                        {"step": 1, "action": "Enter sensitive input", "expected": "Input characters are masked"},
                        {"step": 2, "action": "Copy/paste into field", "expected": "Masking remains intact and value is handled securely"},
                        {"step": 3, "action": "Submit flow", "expected": "Sensitive value is processed without visible leakage"},
                    ],
                }
            )

    if any(word in description for word in ["input", "enter", "provide"]):
        if not any("invalid" in title and "input" in title for title in existing_titles):
            rules_added.append(
                {
                    "title": "Invalid input handling",
                    "type": "Negative",
                    "priority": "Medium",
                    "steps": [
                        {"step": 1, "action": "Enter invalid data", "expected": "Data is entered"},
                        {"step": 2, "action": "Submit", "expected": "Appropriate error message displayed"},
                        {"step": 3, "action": "Correct data and submit again", "expected": "Flow succeeds with valid data"},
                    ],
                }
            )

    combined = test_cases + rules_added
    return ensure_suite_requirements(requirement, combined, min_rigorous=10, min_supplemental=2)

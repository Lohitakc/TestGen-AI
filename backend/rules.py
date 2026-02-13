def apply_qa_rules(requirement, test_cases):
    """
    Applies deterministic QA rules to patch common missing scenarios.
    """
    rules_added = []
    description = requirement.get("description", "").lower()
    acceptance_criteria = " ".join(
        requirement.get("acceptance_criteria", [])
        if isinstance(requirement.get("acceptance_criteria"), list)
        else [str(requirement.get("acceptance_criteria", ""))]
    ).lower()

    existing_titles = {tc.get("title", "").lower() for tc in test_cases}

    # Rule 1: Mandatory field validation
    if any(word in description for word in ["login", "register", "submit", "form"]):
        if not any("empty" in t and "field" in t for t in existing_titles):
            rules_added.append({
                "title": "Empty mandatory field validation",
                "type": "Negative",
                "priority": "High",
                "steps": [
                    {"step": 1, "action": "Leave mandatory fields empty", "expected": "Fields remain empty"},
                    {"step": 2, "action": "Submit form", "expected": "Validation error messages displayed"}
                ]
            })

    # Rule 2: Masked sensitive input
    if any(word in acceptance_criteria for word in ["password", "pin", "secret"]):
        if not any("mask" in t for t in existing_titles):
            rules_added.append({
                "title": "Sensitive input masking",
                "type": "Functional",
                "priority": "High",
                "steps": [
                    {"step": 1, "action": "Enter sensitive input", "expected": "Input characters are masked"}
                ]
            })

    # Rule 3: Invalid input handling
    if any(word in description for word in ["input", "enter", "provide"]):
        if not any("invalid" in t and "input" in t for t in existing_titles):
            rules_added.append({
                "title": "Invalid input handling",
                "type": "Negative",
                "priority": "Medium",
                "steps": [
                    {"step": 1, "action": "Enter invalid data", "expected": "Data is entered"},
                    {"step": 2, "action": "Submit", "expected": "Appropriate error message displayed"}
                ]
            })

    return test_cases + rules_added
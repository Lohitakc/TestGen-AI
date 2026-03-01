BASE_TEST_GEN_PROMPT = """
You are an expert QA engineer.

Task:
Generate test cases from the given requirement and acceptance criteria.

STRICT RULES (must follow):
1. Output ONLY valid JSON - no markdown, no explanation, no extra text.
2. Do NOT wrap output in ```json or ``` blocks.
3. The output MUST be a JSON array of objects.
4. Each acceptance criterion must be covered by at least one test case.
5. Generate at least 10 rigorous, feature-specific test cases that deeply validate behavior, edge cases, and failure modes.
6. The rigorous 10 cases must NOT be generic smoke/basic checks.
7. Add 2 to 4 supplemental simple checks in addition to the rigorous cases.
8. Include Functional, Negative, Boundary, and at least one Integration or Performance scenario where applicable.
9. Test cases must be non-redundant and concrete.
10. Use title prefixes:
   - "[RIGOROUS]" for the rigorous cases
   - "[SUPPLEMENTAL]" for the additional simple checks

Requirement:
{description}

User Story:
{user_story}

Acceptance Criteria:
{acceptance_criteria}

You MUST use this EXACT JSON structure:

[
  {{
    "title": "[RIGOROUS] Short test case title",
    "type": "Functional",
    "priority": "High",
    "steps": [
      {{"step": 1, "action": "What the tester does", "expected": "What should happen"}}
    ]
  }}
]

RULES FOR VALID JSON:
- Use double quotes for all keys and string values.
- No trailing commas.
- No comments.
- Every "steps" entry MUST have "step", "action", and "expected" keys.
- Keep each test case actionable with 3 to 6 steps when possible.

Return ONLY the JSON array. Nothing else.
"""

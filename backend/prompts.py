BASE_TEST_GEN_PROMPT = """
You are an expert QA engineer.

Task:
Generate test cases from the given requirement and acceptance criteria.

STRICT RULES (must follow):
1. Output ONLY valid JSON — no markdown, no explanation, no extra text.
2. Do NOT wrap output in ```json or ``` blocks.
3. The output MUST be a JSON array of objects.
4. Each acceptance criterion must be covered by at least one test case.
5. Include Functional, Negative, and Boundary test cases where applicable.
6. Test cases must be non-redundant.
7. Generate between 2 and 4 test cases.

Requirement:
{description}

User Story:
{user_story}

Acceptance Criteria:
{acceptance_criteria}

You MUST use this EXACT JSON structure:

[
  {{
    "title": "Short test case title",
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

Return ONLY the JSON array. Nothing else.
"""
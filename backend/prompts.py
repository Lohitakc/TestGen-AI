BASE_TEST_GEN_PROMPT = """
You are an expert QA engineer.

Task:
Generate copy-paste-ready test cases from the given requirement and acceptance criteria.

STRICT RULES (must follow):
1. Output ONLY valid JSON - no markdown, no explanation, no extra text.
2. Do NOT wrap output in ```json or ``` blocks.
3. The output MUST be a JSON array of objects.
4. Generate EXACTLY 10 rigorous cases. No supplemental cases.
5. Every case title MUST start with "[RIGOROUS]".
6. Each acceptance criterion must be covered by at least one case.
7. Cases must be topic-specific and concrete. Avoid generic phrases like "valid input", "invalid input", "test data", or "happy path".
8. Each case must include realistic copy-paste values a tester can directly use.
9. Each case must be medium length (clear but concise): not too short, not too long.
10. Include a balanced mix of types across the 10 cases: Functional, Negative, Boundary, and at least one Integration or Performance/Security case when relevant.
11. Cases must be non-redundant and target different risk angles.

Requirement:
{description}

User Story:
{user_story}

Acceptance Criteria:
{acceptance_criteria}

You MUST use this EXACT JSON structure:

[
  {{
    "title": "[RIGOROUS] Specific scenario title",
    "type": "Functional",
    "priority": "High",
    "preconditions": ["Short precondition 1", "Short precondition 2"],
    "copy_paste_input": "Exact input values tester can copy-paste",
    "expected_outcome": "Specific expected result to verify",
    "ac_covered": ["Exact acceptance criterion text covered by this case"]
  }}
]

RULES FOR VALID JSON:
- Use double quotes for all keys and string values.
- No trailing commas.
- No comments.
- Keep preconditions to 1-3 short lines.
- copy_paste_input must contain concrete values and field names when possible.
- expected_outcome must be verifiable and explicit (UI message/state/API response/DB state, as applicable).
- ac_covered must reference one or more acceptance criteria from the given list.
- Return EXACTLY 10 objects in the array.

Return ONLY the JSON array. Nothing else.
"""

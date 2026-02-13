import json
import re
from ollama import chat
from backend.prompts import BASE_TEST_GEN_PROMPT
from backend.rag_pipeline import retrieve_similar_requirements


def load_few_shot_examples():
    with open("data/samples/few_shot_examples.json", "r", encoding="utf-8") as f:
        return json.load(f)


def build_generation_prompt(requirement, few_shot_examples):

    # Use a MINIMAL, perfectly-formed example to guide the model
    hardcoded_example = """
Example Input:
Requirement: Users should be able to logout securely.
Acceptance Criteria: ["User session is terminated", "User is redirected to login page"]

Example Output:
[
  {
    "title": "Successful logout terminates session",
    "type": "Functional",
    "priority": "High",
    "steps": [
      {"step": 1, "action": "Click Logout button", "expected": "Session is terminated"},
      {"step": 2, "action": "Observe redirect", "expected": "Login page is displayed"}
    ]
  },
  {
    "title": "Access protected page after logout",
    "type": "Negative",
    "priority": "High",
    "steps": [
      {"step": 1, "action": "Logout successfully", "expected": "Redirected to login"},
      {"step": 2, "action": "Navigate to dashboard URL directly", "expected": "Access denied or redirected to login"}
    ]
  }
]
"""

    # RAG retrieval (keep it light)
    similar_requirements = retrieve_similar_requirements(
        requirement["description"], k=2
    )

    similar_block = ""
    if similar_requirements:
        similar_block = "\nSimilar Requirements (for context only, do NOT copy):\n"
        for s in similar_requirements:
            similar_block += f"- {s.get('description', '')}\n"

    final_prompt = (
        hardcoded_example
        + similar_block
        + "\nNow generate test cases for the following:\n\n"
        + BASE_TEST_GEN_PROMPT.format(
            description=requirement["description"],
            user_story=requirement.get("user_story", ""),
            acceptance_criteria=json.dumps(requirement["acceptance_criteria"])
        )
    )

    return final_prompt


def repair_json_string(raw: str) -> str:
    """
    Aggressively repair common LLM JSON mistakes.
    """
    # Remove markdown code fences
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)

    # Extract outermost [ ... ]
    start = raw.find('[')
    end = raw.rfind(']')
    if start == -1 or end == -1:
        raise ValueError("No JSON array found in response")
    raw = raw[start:end + 1]

    # Remove control characters except newline/tab
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)

    # Fix single quotes to double quotes (crude but effective for LLM output)
    # Only do this if there are no double quotes around keys
    if raw.count("'") > raw.count('"'):
        raw = raw.replace("'", '"')

    # Remove trailing commas before ] or }
    raw = re.sub(r',\s*(\])', r'\1', raw)
    raw = re.sub(r',\s*(\})', r'\1', raw)

    # Fix missing commas between } and { (common LLM mistake)
    raw = re.sub(r'\}\s*\{', '},{', raw)

    # Fix missing commas between ] and { inside array
    raw = re.sub(r'\]\s*\{', '],{', raw)

    # Remove any text after the final ]
    end = raw.rfind(']')
    raw = raw[:end + 1]

    # Try to balance brackets
    open_sq = raw.count('[')
    close_sq = raw.count(']')
    open_cr = raw.count('{')
    close_cr = raw.count('}')

    # Add missing closing brackets
    raw += '}' * max(0, open_cr - close_cr)
    raw += ']' * max(0, open_sq - close_sq)

    return raw


def parse_json_robust(raw: str) -> list:
    """
    Try multiple strategies to parse LLM JSON output.
    """
    # Strategy 1: Direct parse
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: Repair then parse
    try:
        repaired = repair_json_string(raw)
        result = json.loads(repaired)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find individual JSON objects and assemble
    try:
        repaired = repair_json_string(raw)
        # Find all { ... } blocks
        objects = []
        depth = 0
        start_idx = None
        for i, ch in enumerate(repaired):
            if ch == '{':
                if depth == 0:
                    start_idx = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start_idx is not None:
                    obj_str = repaired[start_idx:i + 1]
                    try:
                        obj = json.loads(obj_str)
                        objects.append(obj)
                    except json.JSONDecodeError:
                        # Try fixing this individual object
                        obj_str = re.sub(r',\s*\}', '}', obj_str)
                        obj_str = re.sub(r',\s*\]', ']', obj_str)
                        try:
                            obj = json.loads(obj_str)
                            objects.append(obj)
                        except json.JSONDecodeError:
                            pass
                    start_idx = None

        if objects:
            return objects
    except Exception:
        pass

    raise ValueError(f"Could not parse JSON after all strategies. Raw (first 500 chars): {raw[:500]}")


def validate_test_case(tc: dict) -> dict:
    """
    Normalize a test case to expected schema.
    """
    normalized = {
        "title": tc.get("title", "Untitled"),
        "type": tc.get("type", "Functional"),
        "priority": tc.get("priority", "Medium"),
        "steps": []
    }

    # Normalize type
    valid_types = {"Functional", "Negative", "Boundary", "Integration", "Performance", "Regression"}
    if normalized["type"] not in valid_types:
        normalized["type"] = "Functional"

    # Normalize priority
    valid_priorities = {"High", "Medium", "Low"}
    if normalized["priority"] not in valid_priorities:
        normalized["priority"] = "Medium"

    # Normalize steps
    raw_steps = tc.get("steps", [])
    if isinstance(raw_steps, list):
        for i, s in enumerate(raw_steps):
            if isinstance(s, dict):
                normalized["steps"].append({
                    "step": s.get("step", i + 1),
                    "action": s.get("action", s.get("description", "No action")),
                    "expected": s.get("expected", s.get("expected_result", ""))
                })
            elif isinstance(s, str):
                normalized["steps"].append({
                    "step": i + 1,
                    "action": s,
                    "expected": ""
                })

    if not normalized["steps"]:
        normalized["steps"].append({
            "step": 1,
            "action": "Execute test",
            "expected": "Verify expected behavior"
        })

    return normalized


def generate_test_cases(prompt, model_name="llama3:8b-instruct-q3_K_M", retries=3, requirement=None):

    last_error = None

    for attempt in range(retries + 1):
        try:
            response = chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.15, "num_predict": 1500}
            )

            content = response["message"]["content"]

            # Debug: print first 300 chars on failure attempts
            if attempt > 0:
                print(f"  [Attempt {attempt + 1}] Raw response preview: {content[:200]}...")

            test_cases = parse_json_robust(content)

            # Validate and normalize each test case
            validated = []
            for tc in test_cases:
                if isinstance(tc, dict) and "title" in tc:
                    validated.append(validate_test_case(tc))

            if not validated:
                raise ValueError("Parsed JSON but no valid test cases found")

            return validated

        except Exception as e:
            last_error = e
            if attempt < retries:
                print(f"⚠️ Attempt {attempt + 1} failed: {str(e)[:120]}, retrying...")
                continue

    raise ValueError(f"Failed after {retries + 1} attempts. Last error: {last_error}")
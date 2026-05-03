import json
import re
from functools import lru_cache
from typing import Any, Dict, List

from langchain_ollama import ChatOllama

from backend.prompts import BASE_TEST_GEN_PROMPT
from backend.rag_pipeline import retrieve_similar_requirements

GENERIC_MARKERS = (
    "valid input",
    "invalid input",
    "test data",
    "sample data",
    "happy path",
    "smoke",
    "basic check",
    "quick check",
    "perform action",
    "execute test",
    "verify expected behavior",
)

STOPWORDS = {
    "the",
    "and",
    "with",
    "that",
    "from",
    "this",
    "when",
    "where",
    "should",
    "must",
    "into",
    "able",
    "user",
    "users",
    "system",
    "using",
    "after",
    "before",
    "then",
    "only",
    "for",
    "each",
    "case",
    "cases",
    "flow",
}


def load_few_shot_examples():
    with open("data/samples/few_shot_examples.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_whitespace(value: Any, max_len: int = 320) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _to_str_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [_normalize_whitespace(item, max_len=180) for item in value if str(item).strip()]
    if value is None:
        return []

    text = str(value).strip()
    if not text:
        return []
    if "\n" in text:
        return [_normalize_whitespace(line, max_len=180) for line in text.splitlines() if line.strip()]
    return [_normalize_whitespace(text, max_len=180)]


def _coerce_steps(raw_steps: Any) -> List[Dict[str, Any]]:
    normalized_steps = []
    if not isinstance(raw_steps, list):
        return normalized_steps

    for i, step in enumerate(raw_steps):
        if isinstance(step, dict):
            normalized_steps.append(
                {
                    "step": step.get("step", i + 1),
                    "action": _normalize_whitespace(step.get("action", step.get("description", "No action")), max_len=200),
                    "expected": _normalize_whitespace(step.get("expected", step.get("expected_result", "")), max_len=200),
                }
            )
        elif isinstance(step, str):
            normalized_steps.append({"step": i + 1, "action": _normalize_whitespace(step, max_len=200), "expected": ""})
    return normalized_steps


def _steps_to_copy_paste_input(steps: List[Dict[str, Any]]) -> str:
    actions = [step.get("action", "").strip() for step in steps if step.get("action", "").strip()]
    if not actions:
        return "input:\nfield=value\nsubmit=true"

    selected = actions[:4]
    lines = []
    for idx, action in enumerate(selected, start=1):
        lines.append(f"{idx}. {action}")
    return "\n".join(lines)


def _steps_to_expected_outcome(steps: List[Dict[str, Any]]) -> str:
    expected_items = [step.get("expected", "").strip() for step in steps if step.get("expected", "").strip()]
    if not expected_items:
        return "System should reject invalid behavior and keep data consistent."

    if len(expected_items) == 1:
        return _normalize_whitespace(expected_items[0], max_len=260)
    return _normalize_whitespace(" | ".join(expected_items[:3]), max_len=260)


def _normalize_example_case(example_case: Dict[str, Any]) -> Dict[str, Any]:
    steps = _coerce_steps(example_case.get("steps", []))
    preconditions = _to_str_list(example_case.get("preconditions"))
    copy_paste_input = _normalize_whitespace(
        example_case.get("copy_paste_input", example_case.get("input", "")),
        max_len=320,
    )
    expected_outcome = _normalize_whitespace(
        example_case.get("expected_outcome", example_case.get("expected", "")),
        max_len=260,
    )

    if not copy_paste_input:
        copy_paste_input = _steps_to_copy_paste_input(steps)
    if not expected_outcome:
        expected_outcome = _steps_to_expected_outcome(steps)

    return {
        "title": _normalize_whitespace(example_case.get("title", "Untitled"), max_len=120),
        "type": _normalize_whitespace(example_case.get("type", "Functional"), max_len=32),
        "priority": _normalize_whitespace(example_case.get("priority", "Medium"), max_len=16),
        "preconditions": preconditions[:3],
        "copy_paste_input": copy_paste_input,
        "expected_outcome": expected_outcome,
        "ac_covered": _to_str_list(example_case.get("ac_covered", []))[:2],
    }


def _format_few_shot_examples(few_shot_examples, max_examples=2):
    if not few_shot_examples:
        return ""

    blocks = []
    for idx, example in enumerate(few_shot_examples[:max_examples], start=1):
        requirement = example.get("requirement", {})
        raw_test_cases = example.get("test_cases", [])[:2]
        normalized_test_cases = [_normalize_example_case(tc) for tc in raw_test_cases if isinstance(tc, dict)]

        blocks.append(
            "Few-shot Example {idx}\n"
            "Requirement: {description}\n"
            "Acceptance Criteria: {acceptance_criteria}\n"
            "Example Test Cases: {test_cases}\n".format(
                idx=idx,
                description=requirement.get("description", ""),
                acceptance_criteria=json.dumps(
                    requirement.get("acceptance_criteria", []), ensure_ascii=False
                ),
                test_cases=json.dumps(normalized_test_cases, ensure_ascii=False),
            )
        )

    return "\n".join(blocks)


def build_generation_prompt(requirement, few_shot_examples):
    few_shot_block = _format_few_shot_examples(few_shot_examples, max_examples=2)

    similar_requirements = retrieve_similar_requirements(requirement["description"], k=3)
    similar_block = ""
    if similar_requirements:
        similar_block = "Similar requirements for context (do not copy wording):\n"
        for similar in similar_requirements:
            similar_block += f"- {similar.get('description', '')}\n"

    return (
        "Use the examples and context below as style guidance only.\n\n"
        f"{few_shot_block}\n\n"
        f"{similar_block}\n\n"
        "Now generate the suite for the target requirement.\n\n"
        + BASE_TEST_GEN_PROMPT.format(
            description=requirement["description"],
            user_story=requirement.get("user_story", ""),
            acceptance_criteria=json.dumps(
                requirement["acceptance_criteria"], ensure_ascii=False
            ),
        )
    )


def repair_json_string(raw: str) -> str:
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)

    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("No JSON array found in response")
    raw = raw[start : end + 1]

    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)

    if raw.count("'") > raw.count('"'):
        raw = raw.replace("'", '"')

    raw = re.sub(r",\s*(\])", r"\1", raw)
    raw = re.sub(r",\s*(\})", r"\1", raw)
    raw = re.sub(r"\}\s*\{", "},{", raw)
    raw = re.sub(r"\]\s*\{", "],{", raw)

    end = raw.rfind("]")
    raw = raw[: end + 1]

    open_sq = raw.count("[")
    close_sq = raw.count("]")
    open_cr = raw.count("{")
    close_cr = raw.count("}")

    raw += "}" * max(0, open_cr - close_cr)
    raw += "]" * max(0, open_sq - close_sq)

    return raw


def parse_json_robust(raw: str) -> list:
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    try:
        repaired = repair_json_string(raw)
        result = json.loads(repaired)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    try:
        repaired = repair_json_string(raw)
        objects = []
        depth = 0
        start_idx = None
        for i, ch in enumerate(repaired):
            if ch == "{":
                if depth == 0:
                    start_idx = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start_idx is not None:
                    obj_str = repaired[start_idx : i + 1]
                    try:
                        obj = json.loads(obj_str)
                        objects.append(obj)
                    except json.JSONDecodeError:
                        obj_str = re.sub(r",\s*\}", "}", obj_str)
                        obj_str = re.sub(r",\s*\]", "]", obj_str)
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

    raise ValueError(
        f"Could not parse JSON after all strategies. Raw (first 500 chars): {raw[:500]}"
    )


def validate_test_case(tc: dict) -> dict:
    steps = _coerce_steps(tc.get("steps", []))
    normalized = {
        "title": _normalize_whitespace(tc.get("title", "Untitled"), max_len=130),
        "type": _normalize_whitespace(tc.get("type", "Functional"), max_len=24),
        "priority": _normalize_whitespace(tc.get("priority", "Medium"), max_len=16),
        "preconditions": _to_str_list(tc.get("preconditions", tc.get("setup", [])))[:3],
        "copy_paste_input": _normalize_whitespace(
            tc.get(
                "copy_paste_input",
                tc.get("input", tc.get("test_input", tc.get("payload", ""))),
            ),
            max_len=480,
        ),
        "expected_outcome": _normalize_whitespace(
            tc.get("expected_outcome", tc.get("expected", tc.get("assertion", ""))),
            max_len=320,
        ),
        "ac_covered": _to_str_list(tc.get("ac_covered", tc.get("covered_criteria", []))),
        "steps": steps,
    }

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

    if not normalized["copy_paste_input"]:
        normalized["copy_paste_input"] = _steps_to_copy_paste_input(steps)
    if not normalized["expected_outcome"]:
        normalized["expected_outcome"] = _steps_to_expected_outcome(steps)

    if not normalized["ac_covered"]:
        normalized["ac_covered"] = []

    if not normalized["steps"]:
        normalized["steps"] = []

    return normalized


def _extract_requirement_keywords(requirement: Dict[str, Any]) -> List[str]:
    ac_text = requirement.get("acceptance_criteria", [])
    if isinstance(ac_text, list):
        ac_joined = " ".join(str(item) for item in ac_text)
    else:
        ac_joined = str(ac_text or "")

    combined = " ".join(
        [
            str(requirement.get("description", "")),
            str(requirement.get("user_story", "")),
            ac_joined,
        ]
    ).lower()

    tokens = re.findall(r"[a-z0-9_]{4,}", combined)
    ordered = []
    seen = set()
    for token in tokens:
        if token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
        if len(ordered) >= 20:
            break
    return ordered


def _specificity_score(test_case: Dict[str, Any], requirement_keywords: List[str]) -> int:
    title = str(test_case.get("title", ""))
    copy_input = str(test_case.get("copy_paste_input", ""))
    expected = str(test_case.get("expected_outcome", ""))
    covered = test_case.get("ac_covered", [])
    combined = f"{title} {copy_input} {expected}".lower()

    score = 0

    if title.lower().startswith("[rigorous]"):
        score += 1
    if 6 <= len(copy_input.split()) <= 120:
        score += 1
    if 5 <= len(expected.split()) <= 80:
        score += 1
    if any(marker in copy_input for marker in ["=", ":", "{", "}", "@", "#", "-", "_", "\n"]):
        score += 1
    if any(char.isdigit() for char in copy_input):
        score += 1

    keyword_hits = sum(1 for keyword in requirement_keywords if keyword in combined)
    if keyword_hits >= 3:
        score += 2
    elif keyword_hits >= 1:
        score += 1

    if isinstance(covered, list) and covered:
        score += 1

    generic_hits = sum(1 for marker in GENERIC_MARKERS if marker in combined)
    score -= generic_hits * 2

    return score


def _passes_rigor_gate(test_case: Dict[str, Any], requirement_keywords: List[str]) -> bool:
    title = str(test_case.get("title", "")).lower()
    if "[supplemental]" in title:
        return False

    score = _specificity_score(test_case, requirement_keywords)
    if score < 4:
        return False

    copy_input = str(test_case.get("copy_paste_input", ""))
    expected = str(test_case.get("expected_outcome", ""))
    if len(copy_input.strip()) < 20:
        return False
    if len(expected.strip()) < 18:
        return False

    return True


@lru_cache(maxsize=4)
def _get_chat_model(model_name: str) -> ChatOllama:
    return ChatOllama(
        model=model_name,
        temperature=0.15,
        num_predict=2600,
    )


def _coerce_content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def _invoke_langchain(prompt: str, model_name: str) -> str:
    llm = _get_chat_model(model_name)
    response = llm.invoke(prompt)
    content = getattr(response, "content", response)
    return _coerce_content_to_text(content)


def generate_test_cases(
    prompt, model_name="llama3:8b-instruct-q3_K_M", retries=3, requirement=None
):
    last_error = None
    retry_prompt = prompt
    requirement = requirement or {}
    requirement_keywords = _extract_requirement_keywords(requirement)

    for attempt in range(retries + 1):
        try:
            content = _invoke_langchain(retry_prompt, model_name=model_name)

            if attempt > 0:
                print(
                    f"  [Attempt {attempt + 1}] Raw response preview: {content[:200]}..."
                )

            test_cases = parse_json_robust(content)
            validated = [
                validate_test_case(tc)
                for tc in test_cases
                if isinstance(tc, dict) and "title" in tc
            ]

            if not validated:
                raise ValueError("Parsed JSON but no valid test cases found")

            rigorous_candidates = [
                tc for tc in validated if _passes_rigor_gate(tc, requirement_keywords)
            ]

            if len(rigorous_candidates) < 6:
                raise ValueError(
                    "Generated suite is too generic or not copy-paste-ready"
                )

            return rigorous_candidates

        except Exception as e:
            last_error = e
            if attempt < retries:
                print(f"Attempt {attempt + 1} failed: {str(e)[:120]}, retrying...")
                retry_prompt = (
                    prompt
                    + "\n\nYour last answer was invalid or too generic."
                    + " Return ONLY a valid JSON array with EXACTLY 10 [RIGOROUS] cases."
                    + " Each case must contain concrete copy_paste_input and explicit expected_outcome."
                )
                continue

    raise ValueError(f"Failed after {retries + 1} attempts. Last error: {last_error}")

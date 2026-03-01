import json
import re
from functools import lru_cache

from langchain_ollama import ChatOllama

from backend.prompts import BASE_TEST_GEN_PROMPT
from backend.rag_pipeline import retrieve_similar_requirements


def load_few_shot_examples():
    with open("data/samples/few_shot_examples.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _format_few_shot_examples(few_shot_examples, max_examples=2):
    if not few_shot_examples:
        return ""

    blocks = []
    for idx, example in enumerate(few_shot_examples[:max_examples], start=1):
        requirement = example.get("requirement", {})
        test_cases = example.get("test_cases", [])[:2]

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
                test_cases=json.dumps(test_cases, ensure_ascii=False),
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
    normalized = {
        "title": tc.get("title", "Untitled"),
        "type": tc.get("type", "Functional"),
        "priority": tc.get("priority", "Medium"),
        "steps": [],
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

    raw_steps = tc.get("steps", [])
    if isinstance(raw_steps, list):
        for i, step in enumerate(raw_steps):
            if isinstance(step, dict):
                normalized["steps"].append(
                    {
                        "step": step.get("step", i + 1),
                        "action": step.get("action", step.get("description", "No action")),
                        "expected": step.get("expected", step.get("expected_result", "")),
                    }
                )
            elif isinstance(step, str):
                normalized["steps"].append(
                    {"step": i + 1, "action": step, "expected": ""}
                )

    if not normalized["steps"]:
        normalized["steps"].append(
            {
                "step": 1,
                "action": "Execute test",
                "expected": "Verify expected behavior",
            }
        )

    return normalized


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

            return validated

        except Exception as e:
            last_error = e
            if attempt < retries:
                print(f"Attempt {attempt + 1} failed: {str(e)[:120]}, retrying...")
                retry_prompt = (
                    prompt
                    + "\n\nYour last answer was invalid. Return ONLY a valid JSON array now."
                )
                continue

    raise ValueError(f"Failed after {retries + 1} attempts. Last error: {last_error}")

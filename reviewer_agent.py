"""
Standalone Reviewer Agent (Optional Utility)
--------------------------------------------
This module is a fully standalone, non-invasive quality-review utility for
already-generated test cases. It is intentionally isolated from the main
generation/evaluation pipeline and is never imported or executed automatically.

Safety guarantees by design:
- Reads existing artifacts in read-only mode.
- Writes only a separate review report file.
- Does not modify generated test cases or existing outputs.
- Deleting this file restores the original system behavior completely.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


DEFAULT_INPUT_CANDIDATES = [
    "data/samples/generated_tests.json",
    "data/samples/evaluation_cases.json",
    "data/samples/evaluation_results.json",
]

NEGATIVE_HINTS = {
    "negative",
    "boundary",
    "invalid",
    "error",
    "reject",
    "denied",
    "fail",
    "failure",
    "forbidden",
    "unauthorized",
    "timeout",
    "expired",
    "empty",
    "null",
    "429",
    "403",
}

EDGE_CASE_HINTS = {
    "boundary",
    "edge",
    "limit",
    "max",
    "maximum",
    "min",
    "minimum",
    "empty",
    "null",
    "invalid",
    "expired",
    "retry",
    "concurrent",
    "latency",
    "network",
    "size",
    "large",
    "overflow",
    "rate",
    "throttle",
}

GENERIC_PHRASES = {
    "works as expected",
    "should work",
    "appropriate error message",
    "error message displayed",
    "successful operation",
    "operation successful",
    "successfully",
    "is displayed",
    "is shown",
    "is updated",
    "data is entered",
    "verify functionality",
    "check functionality",
    "test case",
    "happy path",
    "validation passed",
}

UNCLEAR_TITLE_PATTERNS = (
    re.compile(r"^\s*$"),
    re.compile(r"^\s*(test|test case|scenario|case|tc)[\s:_-]*\d*\s*$", re.IGNORECASE),
    re.compile(r"^\s*(check|verify)\b", re.IGNORECASE),
)

ALLOWED_PRIORITIES = {"high", "medium", "low"}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
    "when",
    "within",
    "should",
    "must",
    "can",
    "user",
    "users",
}


@dataclass
class NormalizedCase:
    ref: str
    requirement_id: str
    requirement_title: str
    requirement_description: str
    acceptance_criteria: List[str]
    title: str
    case_type: str
    priority: str
    copy_paste_input: str
    expected_outcome: str
    ac_covered: List[str]
    steps: List[Dict[str, Any]]
    source_path: str


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", _safe_str(text)).strip()


def _normalize_key(text: str) -> str:
    value = _normalize_space(text).lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _tokenize(text: str) -> List[str]:
    return [tok for tok in re.findall(r"[a-z0-9]+", _normalize_key(text)) if tok not in STOPWORDS]


def _case_blob(case: NormalizedCase) -> str:
    parts = [
        case.title,
        case.case_type,
        case.priority,
        case.copy_paste_input,
        case.expected_outcome,
        " ".join(case.ac_covered),
    ]
    for step in case.steps:
        parts.append(_safe_str(step.get("action", "")))
        parts.append(_safe_str(step.get("expected", "")))
    return _normalize_key(" ".join(parts))


def _collect_step_expectations(case: NormalizedCase) -> List[str]:
    values: List[str] = []
    if case.expected_outcome:
        values.append(case.expected_outcome)
    for step in case.steps:
        expected = _safe_str(step.get("expected", ""))
        if expected:
            values.append(expected)
    return values


def _looks_like_test_case(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    keys = set(item.keys())
    return bool({"title", "copy_paste_input", "expected_outcome", "steps"} & keys)


def _extract_requirement_context(item: Dict[str, Any], fallback_index: int) -> Tuple[str, str, str, List[str]]:
    req_id = _safe_str(item.get("id")) or f"REQ-{fallback_index:03d}"
    req_title = _safe_str(item.get("title"))
    req_description = _safe_str(item.get("description"))
    criteria = [c for c in (_safe_str(c) for c in _to_list(item.get("acceptance_criteria"))) if c]
    return req_id, req_title, req_description, criteria


def _normalize_case(
    case_data: Dict[str, Any],
    requirement_id: str,
    requirement_title: str,
    requirement_description: str,
    acceptance_criteria: List[str],
    case_index: int,
    source_path: str,
) -> NormalizedCase:
    steps = [step for step in _to_list(case_data.get("steps")) if isinstance(step, dict)]
    return NormalizedCase(
        ref=f"{requirement_id}::TC-{case_index}",
        requirement_id=requirement_id,
        requirement_title=requirement_title,
        requirement_description=requirement_description,
        acceptance_criteria=acceptance_criteria,
        title=_normalize_space(_safe_str(case_data.get("title", ""))),
        case_type=_normalize_space(_safe_str(case_data.get("type", ""))),
        priority=_normalize_space(_safe_str(case_data.get("priority", ""))),
        copy_paste_input=_normalize_space(_safe_str(case_data.get("copy_paste_input", case_data.get("input", "")))),
        expected_outcome=_normalize_space(
            _safe_str(case_data.get("expected_outcome", case_data.get("expected", ""))),
        ),
        ac_covered=[_normalize_space(_safe_str(c)) for c in _to_list(case_data.get("ac_covered")) if _safe_str(c)],
        steps=steps,
        source_path=source_path,
    )


def _extract_from_requirement_item(item: Dict[str, Any], source_path: str, req_index: int) -> List[NormalizedCase]:
    req_id, req_title, req_description, criteria = _extract_requirement_context(item, req_index)
    raw_cases = _to_list(item.get("test_cases"))
    if not raw_cases:
        raw_cases = _to_list(item.get("generated_test_cases"))
    cases: List[NormalizedCase] = []
    for idx, case in enumerate(raw_cases, start=1):
        if isinstance(case, dict):
            cases.append(
                _normalize_case(
                    case_data=case,
                    requirement_id=req_id,
                    requirement_title=req_title,
                    requirement_description=req_description,
                    acceptance_criteria=criteria,
                    case_index=idx,
                    source_path=source_path,
                )
            )
    return cases


def _extract_from_requirement_wrapper(item: Dict[str, Any], source_path: str, req_index: int) -> List[NormalizedCase]:
    requirement = item.get("requirement")
    if not isinstance(requirement, dict):
        return []
    req_id = _safe_str(requirement.get("id")) or f"REQ-{req_index:03d}"
    req_title = _safe_str(requirement.get("title"))
    req_description = _safe_str(requirement.get("description"))
    criteria = [c for c in (_safe_str(c) for c in _to_list(requirement.get("acceptance_criteria"))) if c]
    cases: List[NormalizedCase] = []
    for idx, case in enumerate(_to_list(item.get("test_cases")), start=1):
        if isinstance(case, dict):
            cases.append(
                _normalize_case(
                    case_data=case,
                    requirement_id=req_id,
                    requirement_title=req_title,
                    requirement_description=req_description,
                    acceptance_criteria=criteria,
                    case_index=idx,
                    source_path=source_path,
                )
            )
    return cases


def _extract_metrics_only_entries(payload: Any) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        has_metric_shape = "num_test_cases" in item and "id" in item
        has_cases = bool(item.get("test_cases") or item.get("generated_test_cases"))
        if has_metric_shape and not has_cases:
            entries.append(
                {
                    "id": _safe_str(item.get("id")),
                    "num_test_cases": int(item.get("num_test_cases", 0) or 0),
                    "negative_ratio": float(item.get("negative_ratio", 0.0) or 0.0),
                }
            )
    return entries


def extract_cases(payload: Any, source_path: str) -> Tuple[List[NormalizedCase], List[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    cases: List[NormalizedCase] = []
    metrics_only_entries = _extract_metrics_only_entries(payload)

    if isinstance(payload, dict):
        if _to_list(payload.get("test_cases")):
            req = {
                "id": _safe_str(payload.get("id")) or "REQ-001",
                "title": _safe_str(payload.get("title")),
                "description": _safe_str(payload.get("requirement", payload.get("description", ""))),
                "acceptance_criteria": _to_list(payload.get("acceptance_criteria")),
                "test_cases": _to_list(payload.get("test_cases")),
            }
            cases.extend(_extract_from_requirement_item(req, source_path=source_path, req_index=1))
        elif _looks_like_test_case(payload):
            cases.append(
                _normalize_case(
                    case_data=payload,
                    requirement_id="REQ-001",
                    requirement_title="",
                    requirement_description="",
                    acceptance_criteria=[],
                    case_index=1,
                    source_path=source_path,
                )
            )

    elif isinstance(payload, list):
        for i, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                continue
            if "requirement" in item and "test_cases" in item:
                cases.extend(_extract_from_requirement_wrapper(item, source_path=source_path, req_index=i))
            elif "test_cases" in item or "generated_test_cases" in item:
                cases.extend(_extract_from_requirement_item(item, source_path=source_path, req_index=i))
            elif _looks_like_test_case(item):
                cases.append(
                    _normalize_case(
                        case_data=item,
                        requirement_id="REQ-001",
                        requirement_title="",
                        requirement_description="",
                        acceptance_criteria=[],
                        case_index=len(cases) + 1,
                        source_path=source_path,
                    )
                )

    if not cases:
        notes.append(
            "No detailed test-case objects were found in the provided artifact. "
            "Reviewer can still provide limited summary if metric-only entries exist."
        )

    return cases, metrics_only_entries, notes


def _is_negative_case(case: NormalizedCase) -> bool:
    text = " ".join([case.case_type, case.title, case.expected_outcome, _case_blob(case)])
    normalized = _normalize_key(text)
    return any(hint in normalized for hint in NEGATIVE_HINTS)


def _is_edge_case(case: NormalizedCase) -> bool:
    text = " ".join([case.case_type, case.title, case.expected_outcome, _case_blob(case)])
    normalized = _normalize_key(text)
    return any(hint in normalized for hint in EDGE_CASE_HINTS)


def _is_weak_expected_text(text: str) -> bool:
    cleaned = _normalize_space(text)
    if not cleaned:
        return True
    lower = cleaned.lower()
    words = lower.split()
    if len(words) < 4:
        return True
    if any(phrase in lower for phrase in GENERIC_PHRASES):
        # If phrase is generic but has measurable signal, keep it.
        if not re.search(r"\b(\d+|status|code|header|redirect|minutes?|seconds?|ms|otp|csv|json|403|429)\b", lower):
            return True
    # Very short, broad endings often indicate weak checks.
    broad_endings = ("success", "successful", "displayed", "shown", "accepted", "updated")
    if len(words) <= 6 and words[-1] in broad_endings and not re.search(r"\d", lower):
        return True
    return False


def _is_unclear_title(title: str) -> bool:
    value = _normalize_space(title)
    if not value:
        return True
    for pattern in UNCLEAR_TITLE_PATTERNS:
        if pattern.search(value):
            return True
    if len(value.split()) < 3:
        return True
    if _normalize_key(value) in {"functional test", "negative test", "validation test"}:
        return True
    return False


def _is_generic_case(case: NormalizedCase) -> bool:
    text = " ".join(
        [
            case.title,
            case.copy_paste_input,
            case.expected_outcome,
            " ".join(_safe_str(step.get("action", "")) for step in case.steps),
            " ".join(_safe_str(step.get("expected", "")) for step in case.steps),
        ]
    )
    lower = _normalize_space(text).lower()
    if not lower:
        return True
    generic_hits = sum(1 for phrase in GENERIC_PHRASES if phrase in lower)
    token_count = len(set(_tokenize(lower)))
    if generic_hits >= 2:
        return True
    if token_count < 8 and len(lower.split()) < 16:
        return True
    return False


def _formatting_problems(case: NormalizedCase) -> List[str]:
    problems: List[str] = []

    if not case.title:
        problems.append("missing title")
    if case.priority and _normalize_key(case.priority) not in ALLOWED_PRIORITIES:
        problems.append(f"non-standard priority '{case.priority}'")
    if case.priority and case.priority not in {"High", "Medium", "Low"}:
        problems.append("priority capitalization inconsistent")
    if case.case_type and case.case_type != case.case_type.title():
        problems.append("type capitalization inconsistent")
    if case.steps:
        expected_steps = list(range(1, len(case.steps) + 1))
        actual_steps = []
        missing_action = False
        missing_expected = 0
        for step in case.steps:
            step_num = step.get("step")
            if isinstance(step_num, int):
                actual_steps.append(step_num)
            if not _safe_str(step.get("action", "")):
                missing_action = True
            if not _safe_str(step.get("expected", "")):
                missing_expected += 1
        if actual_steps and actual_steps != expected_steps:
            problems.append("step numbers are not sequential from 1")
        if missing_action:
            problems.append("one or more steps missing action")
        if missing_expected == len(case.steps):
            problems.append("all steps missing expected results")
    elif not case.copy_paste_input and not case.expected_outcome:
        problems.append("missing both step details and structured input/output fields")

    return problems


def _criterion_coverage_ratio(criteria: Sequence[str], req_cases: Sequence[NormalizedCase]) -> Tuple[float, List[str]]:
    if not criteria:
        return 1.0, []
    covered: List[str] = []
    missing: List[str] = []

    case_blobs = [_case_blob(case) for case in req_cases]
    ac_mapped_values = []
    for case in req_cases:
        ac_mapped_values.extend(case.ac_covered)
    normalized_mapped = [_normalize_key(v) for v in ac_mapped_values]

    for criterion in criteria:
        norm_criterion = _normalize_key(criterion)
        criterion_tokens = set(_tokenize(criterion))
        direct_match = False
        fuzzy_match = False
        lexical_match = False

        for mapped in normalized_mapped:
            if not mapped:
                continue
            if mapped == norm_criterion:
                direct_match = True
                break
            similarity = difflib.SequenceMatcher(None, mapped, norm_criterion).ratio()
            if similarity >= 0.86:
                fuzzy_match = True
                break

        if not (direct_match or fuzzy_match):
            for blob in case_blobs:
                blob_tokens = set(_tokenize(blob))
                overlap = len(criterion_tokens & blob_tokens)
                if criterion_tokens and overlap / max(1, len(criterion_tokens)) >= 0.45 and overlap >= 2:
                    lexical_match = True
                    break

        if direct_match or fuzzy_match or lexical_match:
            covered.append(criterion)
        else:
            missing.append(criterion)

    ratio = len(covered) / max(1, len(criteria))
    return ratio, missing


def analyze_cases(cases: List[NormalizedCase], metrics_only_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    requirement_groups: Dict[str, List[NormalizedCase]] = defaultdict(list)
    for case in cases:
        requirement_groups[case.requirement_id].append(case)

    # Duplicate detection
    blob_to_refs: Dict[str, List[str]] = defaultdict(list)
    for case in cases:
        blob_to_refs[_case_blob(case)].append(case.ref)
    duplicate_groups = [refs for refs in blob_to_refs.values() if len(refs) > 1]

    near_duplicate_pairs: List[Tuple[str, str, float]] = []
    for i in range(len(cases)):
        left_blob = _case_blob(cases[i])
        if len(left_blob) < 25:
            continue
        for j in range(i + 1, len(cases)):
            right_blob = _case_blob(cases[j])
            if len(right_blob) < 25:
                continue
            ratio = difflib.SequenceMatcher(None, left_blob, right_blob).ratio()
            if ratio >= 0.93 and left_blob != right_blob:
                near_duplicate_pairs.append((cases[i].ref, cases[j].ref, round(ratio, 3)))

    duplicate_case_refs = {ref for group in duplicate_groups for ref in group}
    duplicate_case_refs.update({pair[0] for pair in near_duplicate_pairs})
    duplicate_case_refs.update({pair[1] for pair in near_duplicate_pairs})
    duplicate_count = sum(max(0, len(group) - 1) for group in duplicate_groups) + len(near_duplicate_pairs)

    if duplicate_groups or near_duplicate_pairs:
        affected = sorted(duplicate_case_refs)
        finding = {
            "severity": "medium",
            "issue": "Duplicate test cases detected",
            "affected_tests": affected,
            "recommendation": "Merge near-identical tests or diversify coverage with unique scenarios/assertions.",
            "details": {
                "exact_duplicate_groups": duplicate_groups,
                "near_duplicate_pairs": [
                    {"left": left, "right": right, "similarity": score}
                    for left, right, score in near_duplicate_pairs
                ],
            },
        }
        findings.append(finding)

    # Weak expected outcomes
    weak_expected_refs: List[str] = []
    for case in cases:
        expectations = _collect_step_expectations(case)
        if not expectations:
            weak_expected_refs.append(case.ref)
            continue
        if all(_is_weak_expected_text(exp) for exp in expectations):
            weak_expected_refs.append(case.ref)

    if weak_expected_refs:
        findings.append(
            {
                "severity": "medium",
                "issue": "Weak expected outcomes detected",
                "affected_tests": sorted(weak_expected_refs),
                "recommendation": "Use measurable outcomes (status codes, exact UI text, timing thresholds, or state changes).",
            }
        )

    # Missing negative coverage
    requirements_without_negative: List[str] = []
    for requirement_id, req_cases in requirement_groups.items():
        if not req_cases:
            continue
        has_negative = any(_is_negative_case(case) for case in req_cases)
        criteria_count = len(req_cases[0].acceptance_criteria)
        if not has_negative and (len(req_cases) >= 2 or criteria_count > 1):
            requirements_without_negative.append(requirement_id)

    if requirements_without_negative:
        findings.append(
            {
                "severity": "high",
                "issue": "Missing negative coverage in one or more requirements",
                "affected_tests": sorted(requirements_without_negative),
                "recommendation": "Add failure-path, invalid-input, boundary, and authorization-denial scenarios.",
            }
        )

    # Unclear titles
    unclear_title_refs = [case.ref for case in cases if _is_unclear_title(case.title)]
    if unclear_title_refs:
        findings.append(
            {
                "severity": "low",
                "issue": "Unclear or overly vague test titles",
                "affected_tests": sorted(unclear_title_refs),
                "recommendation": "Use intent-focused titles that include condition and expected behavior.",
            }
        )

    # Poor acceptance-criteria mapping
    poor_mapping_requirements: List[Dict[str, Any]] = []
    for requirement_id, req_cases in requirement_groups.items():
        criteria = req_cases[0].acceptance_criteria if req_cases else []
        if not criteria:
            continue
        coverage_ratio, missing = _criterion_coverage_ratio(criteria, req_cases)
        mapped_cases = sum(1 for case in req_cases if case.ac_covered)
        mapped_ratio = mapped_cases / max(1, len(req_cases))
        if coverage_ratio < 0.6 or mapped_ratio < 0.5:
            poor_mapping_requirements.append(
                {
                    "requirement_id": requirement_id,
                    "coverage_ratio": round(coverage_ratio, 2),
                    "mapped_case_ratio": round(mapped_ratio, 2),
                    "missing_criteria": missing,
                }
            )

    if poor_mapping_requirements:
        affected_reqs = [entry["requirement_id"] for entry in poor_mapping_requirements]
        findings.append(
            {
                "severity": "high",
                "issue": "Poor acceptance-criteria mapping",
                "affected_tests": sorted(affected_reqs),
                "recommendation": "Map each case to explicit acceptance criteria and ensure all criteria are covered.",
                "details": {"requirements": poor_mapping_requirements},
            }
        )

    # Shallow edge-case coverage
    shallow_edge_requirements: List[Dict[str, Any]] = []
    for requirement_id, req_cases in requirement_groups.items():
        if not req_cases:
            continue
        criteria = " ".join(req_cases[0].acceptance_criteria).lower()
        criteria_has_edge_signals = bool(
            re.search(r"\b(\d+|within|limit|max|min|expires|only|retry|error|fails?)\b", criteria)
        )
        edge_cases = [case for case in req_cases if _is_edge_case(case)]
        edge_ratio = len(edge_cases) / max(1, len(req_cases))
        if (criteria_has_edge_signals and not edge_cases) or (len(req_cases) >= 4 and edge_ratio < 0.15):
            shallow_edge_requirements.append(
                {
                    "requirement_id": requirement_id,
                    "edge_case_ratio": round(edge_ratio, 2),
                    "edge_case_count": len(edge_cases),
                    "total_cases": len(req_cases),
                }
            )

    if shallow_edge_requirements:
        findings.append(
            {
                "severity": "medium",
                "issue": "Shallow edge-case coverage",
                "affected_tests": sorted(entry["requirement_id"] for entry in shallow_edge_requirements),
                "recommendation": "Add boundary and stress scenarios (limits, time windows, retries, malformed input).",
                "details": {"requirements": shallow_edge_requirements},
            }
        )

    # Inconsistent formatting
    formatting_issues: Dict[str, List[str]] = {}
    for case in cases:
        problems = _formatting_problems(case)
        if problems:
            formatting_issues[case.ref] = problems

    if formatting_issues:
        findings.append(
            {
                "severity": "low",
                "issue": "Inconsistent formatting detected",
                "affected_tests": sorted(formatting_issues.keys()),
                "recommendation": "Standardize capitalization, priorities, and complete step expected fields.",
                "details": {"case_issues": formatting_issues},
            }
        )

    # Overly generic tests
    generic_refs = [case.ref for case in cases if _is_generic_case(case)]
    if generic_refs:
        findings.append(
            {
                "severity": "medium",
                "issue": "Overly generic test cases",
                "affected_tests": sorted(generic_refs),
                "recommendation": "Add concrete data inputs, precise assertions, and context-specific actions.",
            }
        )

    total_metrics_cases = sum(entry.get("num_test_cases", 0) for entry in metrics_only_entries)
    metric_negative_gaps = [
        entry["id"]
        for entry in metrics_only_entries
        if float(entry.get("negative_ratio", 0.0)) == 0.0 and int(entry.get("num_test_cases", 0)) >= 2
    ]
    if not cases and metrics_only_entries:
        findings.append(
            {
                "severity": "medium",
                "issue": "Input artifact has only aggregate metrics (no detailed test cases)",
                "affected_tests": [entry["id"] for entry in metrics_only_entries],
                "recommendation": "Provide generated test-case artifacts to run full reviewer diagnostics.",
            }
        )

    summary = {
        "total_requirements": len(requirement_groups) or len(metrics_only_entries),
        "total_test_cases": len(cases) if cases else total_metrics_cases,
        "duplicate_cases": duplicate_count,
        "weak_expected_outcomes": len(weak_expected_refs),
        "missing_negative_coverage": bool(requirements_without_negative or metric_negative_gaps),
        "requirements_without_negative_coverage": sorted(
            set(requirements_without_negative + metric_negative_gaps),
        ),
        "unclear_test_titles": len(unclear_title_refs),
        "poor_acceptance_criteria_mapping": len(poor_mapping_requirements),
        "shallow_edge_case_coverage": len(shallow_edge_requirements),
        "inconsistent_formatting": len(formatting_issues),
        "overly_generic_test_cases": len(generic_refs),
    }

    requirement_breakdown = []
    for requirement_id, req_cases in sorted(requirement_groups.items(), key=lambda x: x[0]):
        negative_count = sum(1 for case in req_cases if _is_negative_case(case))
        edge_count = sum(1 for case in req_cases if _is_edge_case(case))
        coverage_ratio, missing = _criterion_coverage_ratio(req_cases[0].acceptance_criteria, req_cases)
        requirement_breakdown.append(
            {
                "requirement_id": requirement_id,
                "title": req_cases[0].requirement_title,
                "test_case_count": len(req_cases),
                "negative_case_count": negative_count,
                "edge_case_count": edge_count,
                "acceptance_criteria_count": len(req_cases[0].acceptance_criteria),
                "acceptance_criteria_coverage_ratio": round(coverage_ratio, 2),
                "missing_acceptance_criteria": missing,
            }
        )

    return {
        "summary": summary,
        "findings": findings,
        "requirement_breakdown": requirement_breakdown,
    }


def try_llm_review(cases: List[NormalizedCase], model_name: str, base_url: str, max_cases: int = 25) -> Dict[str, Any]:
    """
    Optional LLM layer: best-effort only.
    Returns gracefully if stack/model is unavailable.
    """

    try:
        from langchain_ollama import ChatOllama
        from langchain_core.messages import HumanMessage, SystemMessage
    except Exception as exc:  # noqa: BLE001
        return {
            "enabled": False,
            "status": "skipped",
            "reason": f"LLM dependencies unavailable: {exc}",
        }

    sampled = cases[:max_cases]
    compact = [
        {
            "ref": case.ref,
            "title": case.title,
            "type": case.case_type,
            "expected_outcome": case.expected_outcome,
            "ac_covered": case.ac_covered,
            "steps": [
                {
                    "action": _safe_str(step.get("action", "")),
                    "expected": _safe_str(step.get("expected", "")),
                }
                for step in case.steps[:3]
            ],
        }
        for case in sampled
    ]

    system_prompt = (
        "You are a strict QA reviewer. Return JSON only with keys: "
        "summary, high_risk_findings, recommendations. Focus on duplicates, weak expected outcomes, "
        "negative coverage, acceptance-criteria mapping, edge cases, and generic tests."
    )
    user_prompt = json.dumps({"sample_test_cases": compact}, ensure_ascii=False)

    try:
        llm = ChatOllama(model=model_name, base_url=base_url, temperature=0)
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        content = _safe_str(getattr(response, "content", response))
        parsed = json.loads(content) if content else {}
        return {
            "enabled": True,
            "status": "ok",
            "model": model_name,
            "base_url": base_url,
            "sample_size": len(sampled),
            "review": parsed,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "enabled": True,
            "status": "failed_gracefully",
            "model": model_name,
            "base_url": base_url,
            "sample_size": len(sampled),
            "reason": str(exc),
        }


def _find_existing_input(candidates: Sequence[str]) -> Optional[Path]:
    for candidate in candidates:
        path = Path(candidate)
        if path.exists() and path.is_file():
            return path
    return None


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _resolve_output_path(path_str: str) -> Path:
    requested = Path(path_str)
    if not requested.exists():
        return requested
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fallback = requested.with_name(f"{requested.stem}_{timestamp}{requested.suffix}")
    counter = 1
    while fallback.exists():
        fallback = requested.with_name(f"{requested.stem}_{timestamp}_{counter}{requested.suffix}")
        counter += 1
    return fallback


def _render_markdown_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Reviewer Agent Report")
    lines.append("")
    lines.append(f"- Generated at: {report.get('generated_at', '')}")
    lines.append(f"- Input file: `{report.get('input_file', '')}`")
    lines.append(f"- Reviewer mode: `{report.get('reviewer_mode', '')}`")
    lines.append("")
    lines.append("## Summary")
    summary = report.get("summary", {})
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Findings")
    findings = report.get("findings", [])
    if not findings:
        lines.append("- No major findings detected.")
    for finding in findings:
        lines.append(f"- Severity: **{finding.get('severity', 'info')}**")
        lines.append(f"  Issue: {finding.get('issue', '')}")
        lines.append(f"  Affected: {finding.get('affected_tests', [])}")
        lines.append(f"  Recommendation: {finding.get('recommendation', '')}")
    lines.append("")
    lines.append("## Requirement Breakdown")
    for item in report.get("requirement_breakdown", []):
        lines.append(
            "- {requirement_id}: tests={test_case_count}, negative={negative_case_count}, "
            "edge={edge_case_count}, ac_coverage={acceptance_criteria_coverage_ratio}".format(**item)
        )
    return "\n".join(lines) + "\n"


def _write_report(report: Dict[str, Any], output_path: Path, output_format: str) -> Path:
    final_path = _resolve_output_path(str(output_path))
    final_path.parent.mkdir(parents=True, exist_ok=True)

    if output_format == "md":
        content = _render_markdown_report(report)
        final_path.write_text(content, encoding="utf-8")
    else:
        final_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return final_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Standalone reviewer for generated test cases. "
            "Reads existing artifacts and writes a separate review report."
        )
    )
    parser.add_argument(
        "--input",
        type=str,
        default="",
        help="Path to input JSON artifact. If omitted, auto-detects known sample artifact paths.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="review_report.json",
        help="Output report path (separate file). Existing file is never overwritten.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "md", "auto"],
        default="auto",
        help="Report output format. 'auto' infers from output extension.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Optionally run supplemental LLM review using local Ollama/LangChain stack.",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="llama3.1",
        help="Ollama model name used when --use-llm is enabled.",
    )
    parser.add_argument(
        "--llm-base-url",
        type=str,
        default="http://localhost:11434",
        help="Ollama base URL used when --use-llm is enabled.",
    )
    parser.add_argument(
        "--llm-max-cases",
        type=int,
        default=25,
        help="Maximum number of cases sampled for optional LLM review.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input) if args.input else _find_existing_input(DEFAULT_INPUT_CANDIDATES)
    if not input_path:
        print(
            "No input artifact found. Provide --input path/to/file.json "
            "or place a known artifact under data/samples/.",
            file=sys.stderr,
        )
        return 1

    if not input_path.exists() or not input_path.is_file():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        payload = _read_json(input_path)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to parse JSON from {input_path}: {exc}", file=sys.stderr)
        return 1

    cases, metrics_only_entries, notes = extract_cases(payload, source_path=str(input_path))
    analysis = analyze_cases(cases, metrics_only_entries)

    report: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_file": str(input_path),
        "reviewer_mode": "heuristic",
        "summary": analysis["summary"],
        "findings": analysis["findings"],
        "requirement_breakdown": analysis["requirement_breakdown"],
        "notes": notes,
    }

    if args.use_llm:
        llm_result = try_llm_review(
            cases=cases,
            model_name=args.llm_model,
            base_url=args.llm_base_url,
            max_cases=max(1, args.llm_max_cases),
        )
        report["llm_review"] = llm_result
        report["reviewer_mode"] = "heuristic+llm" if llm_result.get("enabled") else "heuristic"

    output_path = Path(args.output)
    output_format = args.format
    if output_format == "auto":
        output_format = "md" if output_path.suffix.lower() == ".md" else "json"

    try:
        final_output = _write_report(report, output_path=output_path, output_format=output_format)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to write report: {exc}", file=sys.stderr)
        return 1

    print(f"Reviewer completed. Report written to: {final_output}")
    print(
        "Summary: "
        f"{report['summary'].get('total_test_cases', 0)} test cases, "
        f"{len(report['findings'])} findings."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

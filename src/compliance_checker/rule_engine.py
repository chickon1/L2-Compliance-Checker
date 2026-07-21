"""Evaluates rules against raw device config text."""

from __future__ import annotations

import re
from typing import List

from .models import Rule, RuleResult, RuleStatus

_LEADING_FLAGS = re.compile(r"^\(\?[a-zA-Z]+\)")
_LEFTOVER_REGEX_CHARS = re.compile(r"[()\[\]|{}]")


def _humanize_pattern(pattern: str) -> str:
    """Best-effort plain-English rendering of a require/forbid regex, for
    showing "what was expected" without dumping raw regex syntax at the
    user. Falls back to a generic message if the pattern is too complex
    (alternations, character classes) to clean up nicely.
    """
    text = _LEADING_FLAGS.sub("", pattern)
    text = text.replace("^", "").replace("$", "").replace("\\b", "")
    text = text.replace("\\s*", " ").replace("\\s+", " ")
    text = re.sub(r"\\d[+*]", "<number>", text)
    text = re.sub(r"\\d\{[^}]+\}", "<number>", text)
    text = re.sub(r"\\S[+*]", "<value>", text)
    text = text.replace(".*", "<anything>")
    text = text.replace("\\.", ".")
    text = re.sub(r"\s+", " ", text).strip()

    if _LEFTOVER_REGEX_CHARS.search(text):
        return "the required configuration"
    return text


def evaluate(rule: Rule, raw_config: str) -> RuleResult:
    evidence: List[str] = []

    for pattern in rule.require:
        match = re.search(pattern, raw_config)
        if not match:
            return RuleResult(
                rule_id=rule.id,
                status=RuleStatus.FAIL,
                evidence=[f"not found: {_humanize_pattern(pattern)}"],
            )
        evidence.append(match.group(0).strip())

    for pattern in rule.forbid:
        match = re.search(pattern, raw_config)
        if match:
            return RuleResult(
                rule_id=rule.id,
                status=RuleStatus.FAIL,
                evidence=[match.group(0).strip()],
            )

    return RuleResult(rule_id=rule.id, status=RuleStatus.PASS, evidence=evidence)


def evaluate_all(rules: List[Rule], raw_config: str) -> List[RuleResult]:
    return [evaluate(rule, raw_config) for rule in rules]

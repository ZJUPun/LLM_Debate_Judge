"""Pull the final answer out of a model reply, and check it against the answer key."""
from __future__ import annotations

import json
import re
from collections import Counter

_NUM = r"-?\$?\d[\d,]*(?:\.\d+)?"


def _norm_number(s: str | None):
    if s is None:
        return None
    s = s.replace(",", "").replace("$", "").strip().rstrip(".")
    try:
        x = float(s)
    except ValueError:
        return None
    return str(int(x)) if x == int(x) else str(round(x, 6))


def extract_number(text: str):
    """GSM8K: prefer 'Answer: 42', then '\\boxed{42}', then the last number in the reply."""
    if not text:
        return None
    m = re.findall(rf"[Aa]nswer\s*[:：]?\s*\**\s*({_NUM})", text)
    if m:
        return _norm_number(m[-1])
    m = re.findall(rf"\\boxed\{{\s*({_NUM})", text)
    if m:
        return _norm_number(m[-1])
    m = re.findall(_NUM, text)
    return _norm_number(m[-1]) if m else None


def extract_letter(text: str, valid: str = "ABCDEFGHIJ"):
    """MMLU-Pro: prefer 'Answer: C' / 'Answer: (C)', then the last '(C)' in the reply."""
    if not text:
        return None
    m = re.findall(rf"[Aa]nswer\s*(?:is)?\s*[:：]?\s*\**\s*\(?([{valid}])\)?\b", text)
    if m:
        return m[-1]
    m = re.findall(rf"\(([{valid}])\)", text)
    return m[-1] if m else None


def extract_winner(text: str):
    """Judge replies: JSON {"winner": "A"|"B"}; falls back to a regex."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            w = str(json.loads(m.group(0)).get("winner", "")).strip().upper()
            if w in ("A", "B"):
                return w
        except (json.JSONDecodeError, AttributeError):
            pass
    m = re.findall(r'"?winner"?\s*[:=]\s*"?([AB])\b', text, re.I)
    return m[-1].upper() if m else None


def extract(text: str, kind: str):
    return extract_number(text) if kind == "math" else extract_letter(text)


def is_correct(pred, gold, kind: str) -> bool:
    if pred is None:
        return False
    if kind == "math":
        try:
            return abs(float(pred) - float(gold)) < 1e-6
        except ValueError:
            return False
    return str(pred).strip().upper() == str(gold).strip().upper()


def majority_vote(preds):
    """Most common non-empty answer. Ties go to the answer that appeared first."""
    preds = [p for p in preds if p is not None]
    if not preds:
        return None
    counts = Counter(preds)
    best = max(counts.values())
    return next(p for p in preds if counts[p] == best)

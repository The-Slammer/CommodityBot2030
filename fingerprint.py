"""
utils/fingerprint.py — Cheap, LLM-free deduplication.
Generates a hash from title + summary to catch near-duplicates
across sources before anything touches a model.
"""

import hashlib
import re


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation and extra whitespace."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_fingerprint(title: str, summary: str = "") -> str:
    """
    SHA-256 hash of normalized title + first 200 chars of summary.
    Catches identical or near-identical content published across multiple sources.
    """
    normalized = _normalize(title) + " " + _normalize(summary)[:200]
    return hashlib.sha256(normalized.encode()).hexdigest()

"""Lightweight keyword/heuristic frustration detector (no ML model needed)."""
import re

FRUSTRATION_WORDS = {
    "angry", "furious", "frustrated", "frustrating", "ridiculous", "unacceptable",
    "terrible", "horrible", "worst", "awful", "useless", "pathetic", "sick of",
    "fed up", "annoyed", "annoying", "scam", "rip off", "ripoff", "disgusted",
    "enraged", "livid", "outrageous", "incompetent", "hate", "furioso", "molesto",
    "harto", "pesimo", "pésimo", "terrible", "indignante",
}

NEGATION_INTENSIFIERS = ("!!", "???", "?!")


def detect_frustration(text: str) -> dict:
    lowered = text.lower()

    matched_words = [w for w in FRUSTRATION_WORDS if w in lowered]

    exclamations = text.count("!")
    has_multi_punct = any(tok in text for tok in NEGATION_INTENSIFIERS)

    letters = [c for c in text if c.isalpha()]
    caps_ratio = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0
    is_shouting = len(letters) >= 8 and caps_ratio > 0.6

    score = 0
    score += 2 * len(matched_words)
    score += 1 if exclamations >= 2 else 0
    score += 1 if has_multi_punct else 0
    score += 2 if is_shouting else 0

    frustrated = score >= 2

    return {
        "frustrated": frustrated,
        "score": score,
        "signals": {
            "keywords": matched_words,
            "exclamations": exclamations,
            "shouting": is_shouting,
        },
    }

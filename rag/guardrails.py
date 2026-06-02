"""
guardrails.py — Pre-query guards for PII detection and opinion classification.
Ensures the assistant only answers factual MF questions and never stores PII.
"""

import re
from typing import Tuple

# ── PII patterns ──────────────────────────────────────────────────────────────
_PII_PATTERNS = [
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),                    # PAN
    re.compile(r"\b[2-9][0-9]{11}\b"),                            # Aadhaar (12-digit)
    re.compile(r"\b\d{9,18}\b"),                                   # Account / folio numbers
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email
    re.compile(r"\b[6-9]\d{9}\b"),                                 # Indian phone number
    re.compile(r"\botp\b", re.IGNORECASE),                        # OTP mentions
]

# ── Opinion / advice keywords ─────────────────────────────────────────────────
_OPINION_KEYWORDS = [
    r"\bshould i\b",
    r"\bwould you recommend\b",
    r"\bbest fund\b",
    r"\bwhich fund (is|to|should)\b",
    r"\badvise\b",
    r"\badvice\b",
    r"\binvest in\b.*\?",
    r"\bwill.*(give|return|earn|generate)\b",
    r"\bwhat.*(returns|profit|gain)\b.*\?",
    r"\bcompare.*(returns|performance)\b",
    r"\bshould i (buy|sell|redeem|switch)\b",
    r"\bworth (investing|buying)\b",
    r"\bgood (investment|fund|choice|option)\b",
    r"\bportfolio\b",
    r"\btop (fund|pick|choice)\b",
    r"\bbetter (than|fund|option)\b",
]

_OPINION_RE = re.compile("|".join(_OPINION_KEYWORDS), re.IGNORECASE)


def check_pii(query: str) -> Tuple[bool, str]:
    """
    Check if the query contains PII.

    Returns:
        (True, reason) if PII found, (False, "") otherwise.
    """
    for pattern in _PII_PATTERNS:
        if pattern.search(query):
            return True, "PII detected"
    return False, ""


def check_opinion(query: str) -> Tuple[bool, str]:
    """
    Check if the query is asking for investment advice or opinions.

    Returns:
        (True, reason) if opinionated, (False, "") otherwise.
    """
    if _OPINION_RE.search(query):
        return True, "Opinion/advice request"
    return False, ""


def run_guardrails(query: str) -> Tuple[str, str | None]:
    """
    Run all guardrails on the user query.

    Returns:
        ("ok", None)           → query is safe to process.
        ("pii", message)       → PII detected; return message to user.
        ("opinion", message)   → Opinion request; return message with edu link.
    """
    query = query.strip()

    if not query:
        return "ok", None

    # PII check takes priority
    has_pii, _ = check_pii(query)
    if has_pii:
        return "pii", (
            "⚠️ I noticed your message may contain personal information "
            "(e.g., PAN, Aadhaar, account number, or phone number). "
            "Please do not share personal details — I can only answer "
            "factual questions about mutual fund schemes."
        )

    # Opinion / advice check
    has_opinion, _ = check_opinion(query)
    if has_opinion:
        return "opinion", (
            "This assistant provides **facts only** and cannot offer investment "
            "advice or recommend funds. 🙏\n\n"
            "For general education on mutual funds, visit: "
            "[AMFI Investor Corner](https://www.amfiindia.com/investor-corner/knowledge-center/mutual-fund-faqs.html)"
        )

    return "ok", None

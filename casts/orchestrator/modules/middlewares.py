"""Middleware implementations for the Orchestrator graph.

Three middleware patterns:
1. PIIMiddleware — PII detection and masking in text output
2. SummarizationMiddleware — Auto-summarize conversation when messages exceed threshold
3. HumanInTheLoopMiddleware — Require human approval before sensitive operations

Usage in nodes (standalone helpers):
    from .middlewares import apply_pii_filter, MESSAGE_THRESHOLD
    filtered = apply_pii_filter(text)

Usage with agents (middleware factories):
    from .middlewares import get_pii_middleware, get_hitl_middleware
    agent = create_agent(model=..., tools=[...], middleware=[get_hitl_middleware()])

Official document URL:
    - Built-in Middleware: https://docs.langchain.com/oss/python/langchain/middleware/built-in
    - Custom Middleware: https://docs.langchain.com/oss/python/langchain/middleware/custom
"""

import re

from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    PIIMiddleware,
    SummarizationMiddleware,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MESSAGE_THRESHOLD = 6

PII_PATTERNS: dict[str, tuple[str, str]] = {
    "card": (r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}", "[CARD_REDACTED]"),
    "email": (r"[\w.-]+@[\w.-]+\.\w+", "[EMAIL_REDACTED]"),
    "phone": (r"\d{2,3}-\d{3,4}-\d{4}", "[PHONE_REDACTED]"),
}


# ---------------------------------------------------------------------------
# Standalone Helpers (used directly in nodes)
# ---------------------------------------------------------------------------


def apply_pii_filter(text: str, pii_types: list[str] | None = None) -> str:
    """Filter PII patterns from text using regex replacement.

    Args:
        text: Input text to filter.
        pii_types: Specific PII types to filter. Defaults to all types.

    Returns:
        Text with PII patterns replaced by redaction markers.
    """
    types_to_filter = pii_types or list(PII_PATTERNS.keys())
    for pii_type in types_to_filter:
        if pii_type in PII_PATTERNS:
            pattern, replacement = PII_PATTERNS[pii_type]
            text = re.sub(pattern, replacement, text)
    return text


# ---------------------------------------------------------------------------
# Agent Middleware Factories (used with create_agent)
# ---------------------------------------------------------------------------


def get_pii_middleware() -> list[PIIMiddleware]:
    """Create PII middleware instances for agent usage.

    Returns:
        List of PIIMiddleware instances for email and credit card detection.
    """
    return [
        PIIMiddleware("email", strategy="redact", apply_to_input=True),
        PIIMiddleware("credit_card", strategy="mask", apply_to_input=True),
    ]


def get_hitl_middleware() -> HumanInTheLoopMiddleware:
    """Create Human-in-the-Loop middleware for email approval.

    Interrupts execution before the send_email tool is called,
    requiring explicit user approval to proceed.

    Returns:
        HumanInTheLoopMiddleware configured for email sending.
    """
    return HumanInTheLoopMiddleware(
        interrupt_on={"send_email": True},
        description_prefix="이메일 발송 승인 요청",
    )


def get_summarization_middleware() -> SummarizationMiddleware:
    """Create Summarization middleware for long conversations.

    Triggers when message count exceeds MESSAGE_THRESHOLD,
    keeping the last 4 messages and summarizing the rest.

    Returns:
        SummarizationMiddleware configured for Gemini model.
    """
    return SummarizationMiddleware(
        model="gemini-2.0-flash",
        trigger={"messages": MESSAGE_THRESHOLD},
        keep={"messages": 4},
    )

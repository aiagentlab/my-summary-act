"""Conditional routing functions for the Orchestrator graph.

Implements two conditional edges:
1. should_summarize_conversation — Routes to ConversationSummaryNode or skips
2. is_approved — Routes to EmailSendNode or END based on user approval

Each function accepts the current state and returns a string key
that maps to the next node via add_conditional_edges().

Official document URL:
    - Conditional edges: https://docs.langchain.com/oss/python/langgraph/graph-api#conditional-edges
"""

from .middlewares import MESSAGE_THRESHOLD


def should_summarize_conversation(state) -> str:
    """Check if conversation history needs summarization.

    Triggers summarization when message count exceeds MESSAGE_THRESHOLD.

    Returns:
        "needs_summary" if messages exceed threshold, "skip_summary" otherwise.
    """
    messages = state.get("messages", [])
    if len(messages) > MESSAGE_THRESHOLD:
        return "needs_summary"
    return "skip_summary"


def is_approved(state) -> str:
    """Route based on user approval status.

    Returns:
        "approved" if user approved, "rejected" otherwise.
    """
    if state.get("is_approved"):
        return "approved"
    return "rejected"

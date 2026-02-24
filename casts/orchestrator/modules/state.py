"""State definition for the Orchestrator graph.

Defines InputState, OutputState, and OverallState (State) as specified in CLAUDE.md.
"""

from langgraph.graph import MessagesState
from typing_extensions import TypedDict


class InputState(MessagesState):
    """Input state container.

    Users send a plain text message via LangGraph Studio chat UI.
    The messages field (inherited from MessagesState) enables the chat UI.
    """

    pass


class OutputState(TypedDict):
    """Output state container.

    Attributes:
        summary: Structured summary result.
        email_sent: Whether the email was sent successfully.
    """

    summary: str
    email_sent: bool


class State(MessagesState):
    """Graph state container.

    Attributes:
        topic: The topic to search for.
        search_results: Raw web search results.
        summary: Structured summary of search results (PII filtered).
        recipient_email: Recipient email from human-in-the-loop.
        is_approved: Whether the user approved email sending.
        email_sent: Whether the email was sent successfully.
        messages: LLM conversation history (inherited from MessagesState).
    """

    topic: str
    search_results: list[dict]
    summary: str
    recipient_email: str
    is_approved: bool
    email_sent: bool

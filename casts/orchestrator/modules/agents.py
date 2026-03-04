"""Agent construction for the Orchestrator Cast.

Uses `create_agent` to build an agent that dynamically selects tools
(web_search, send_email) with middleware handling PII, HITL, and
conversation summarization automatically.

Official document URL:
    - Agents: https://docs.langchain.com/oss/python/langchain/agents
"""

from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver

from .middlewares import (
    get_hitl_middleware,
    get_pii_middleware,
    get_summarization_middleware,
)
from .prompts import AGENT_SYSTEM_PROMPT
from .tools import send_email, web_search


def my_agent(checkpointer: BaseCheckpointSaver | None = None):
    """Create the myAgent instance with tools and middleware.

    Architecture:
        - Model: gemini-2.0-flash (same as existing StateGraph nodes)
        - Tools: web_search (Tavily), send_email (Resend)
        - Middleware:
            - PIIMiddleware x2 (email + credit_card redaction)
            - HumanInTheLoopMiddleware (interrupt before send_email)
            - SummarizationMiddleware (auto-summarize long conversations)
        - System Prompt: guides search → summarize → email workflow

    Args:
        checkpointer: Optional checkpointer for interrupt/resume support.
            LangGraph Platform provides this automatically; pass InMemorySaver()
            for local/test usage.

    Returns:
        Compiled agent graph ready for LangGraph Platform execution.
    """
    return create_agent(
        model="google_genai:gemini-2.0-flash",
        tools=[web_search, send_email],
        middleware=[
            *get_pii_middleware(),
            get_hitl_middleware(),
            get_summarization_middleware(),
        ],
        system_prompt=AGENT_SYSTEM_PROMPT,
        name="myAgent",
        checkpointer=checkpointer,
    )

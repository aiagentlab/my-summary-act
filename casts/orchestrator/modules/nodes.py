"""Node implementations for the Orchestrator graph.

Implements: WebSearchNode, SummarizeNode, ConversationSummaryNode,
            HumanApprovalNode, EmailSendNode
as specified in CLAUDE.md.
"""

import os

import resend
from langchain_core.messages import HumanMessage, RemoveMessage, SystemMessage
from langchain_tavily import TavilySearch
from langgraph.types import interrupt

from casts.base_node import BaseNode

from .middlewares import apply_pii_filter
from .models import get_gemini_model
from .prompts import CONVERSATION_SUMMARY_PROMPT, SUMMARIZE_PROMPT


class WebSearchNode(BaseNode):
    """Searches the web for the given topic using Tavily.

    Reads: messages (topic extraction)
    Writes: topic, search_results
    """

    def __init__(self):
        super().__init__()
        self._search = None

    @property
    def search(self):
        if self._search is None:
            self._search = TavilySearch(
                max_results=5,
                topic="general",
                include_raw_content=False,
            )
        return self._search

    def execute(self, state):
        topic = state["messages"][-1].content
        results = self.search.invoke({"query": topic})

        return {"topic": topic, "search_results": results.get("results", [])}


class SummarizeNode(BaseNode):
    """Summarizes search results into structured format using Gemini.

    Applies PIIMiddleware to filter personal information from the summary output.

    Reads: topic, search_results
    Writes: summary, messages
    Middleware: PIIMiddleware (apply_pii_filter)
    """

    def __init__(self):
        super().__init__()
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = get_gemini_model()
        return self._model

    def execute(self, state):
        topic = state["topic"]
        search_results = state["search_results"]

        results_text = self._format_results(search_results)

        user_message = HumanMessage(
            content=f"토픽: {topic}\n\n검색 결과:\n{results_text}"
        )

        messages = [SUMMARIZE_PROMPT, user_message]
        response = self.model.invoke(messages)

        # PIIMiddleware: filter personal information from summary
        filtered_summary = apply_pii_filter(response.content)

        return {
            "summary": filtered_summary,
            "messages": [user_message, response],
        }

    def _format_results(self, results: list[dict]) -> str:
        """Format search results into readable text."""
        formatted = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "")
            url = result.get("url", "")
            content = result.get("content", "")
            formatted.append(f"[{i}] {title}\nURL: {url}\n{content}")
        return "\n\n".join(formatted)


class ConversationSummaryNode(BaseNode):
    """Summarizes long conversation history to optimize token usage.

    Triggered by should_summarize_conversation conditional edge
    when message count exceeds MESSAGE_THRESHOLD.

    Reads: messages
    Writes: messages (old messages removed, summary added)
    Middleware: SummarizationMiddleware pattern
    """

    def __init__(self):
        super().__init__()
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = get_gemini_model()
        return self._model

    def execute(self, state):
        messages = state["messages"]

        # Build conversation text for summarization
        conversation_text = "\n".join(
            f"{m.type}: {m.content}"
            for m in messages
            if hasattr(m, "content") and m.content
        )

        summary_msg = HumanMessage(
            content=f"다음 대화를 요약해주세요:\n\n{conversation_text}"
        )
        response = self.model.invoke([CONVERSATION_SUMMARY_PROMPT, summary_msg])

        # Remove old messages and replace with summary
        delete_msgs = [RemoveMessage(id=m.id) for m in messages[:-1]]
        summary_system = SystemMessage(
            content=f"[이전 대화 요약]\n{response.content}"
        )

        return {"messages": delete_msgs + [summary_system]}


class HumanApprovalNode(BaseNode):
    """Pauses for human review, email input, and approval decision.

    Uses LangGraph interrupt() to pause the graph.
    User responds with recipient email to approve, or 'reject' to decline.

    Reads: summary
    Writes: recipient_email, is_approved
    Middleware: HumanInTheLoopMiddleware pattern (interrupt-based)
    """

    def __init__(self):
        super().__init__()

    def execute(self, state):
        summary = state["summary"]

        response = interrupt(
            {
                "summary": summary,
                "instruction": (
                    "요약 결과를 확인해주세요.\n"
                    "승인하려면 수신자 이메일을 입력하세요.\n"
                    "거부하려면 'reject'를 입력하세요."
                ),
            }
        )

        # Route: email string = approved, 'reject' = rejected
        if isinstance(response, str) and response.strip().lower() == "reject":
            return {"recipient_email": "", "is_approved": False}

        return {"recipient_email": str(response), "is_approved": True}


class EmailSendNode(BaseNode):
    """Sends the summary via email using Resend API.

    Only reached when is_approved conditional edge returns "approved".

    Reads: topic, summary, recipient_email
    Writes: email_sent
    """

    def __init__(self):
        super().__init__()

    def execute(self, state):
        topic = state["topic"]
        summary = state["summary"]
        recipient_email = state["recipient_email"]

        resend.api_key = os.environ["RESEND_API_KEY"]
        from_email = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")

        summary_html = summary.replace("\n", "<br>")

        params = {
            "from": from_email,
            "to": [recipient_email],
            "subject": f"[Summary] {topic}",
            "html": f"<h2>{topic} - 요약 리포트</h2><hr>{summary_html}",
        }

        try:
            resend.Emails.send(params)
            return {"email_sent": True}
        except Exception:
            return {"email_sent": False}

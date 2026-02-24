"""Unit tests for Orchestrator cast nodes, conditions, and middlewares.

Tests each node in isolation with mocked external dependencies.
Tests conditional edge functions and middleware helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from casts.orchestrator.modules.conditions import is_approved, should_summarize_conversation
from casts.orchestrator.modules.middlewares import MESSAGE_THRESHOLD, apply_pii_filter
from casts.orchestrator.modules.nodes import (
    ConversationSummaryNode,
    EmailSendNode,
    HumanApprovalNode,
    SummarizeNode,
    WebSearchNode,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SEARCH_RESULTS = [
    {
        "title": "AI Agents Overview",
        "url": "https://example.com/ai-agents",
        "content": "AI agents are autonomous systems that can perform tasks.",
    },
    {
        "title": "LangGraph Guide",
        "url": "https://example.com/langgraph",
        "content": "LangGraph is a framework for building stateful agents.",
    },
]

SAMPLE_TAVILY_RESPONSE = {
    "query": "AI 에이전트",
    "results": SAMPLE_SEARCH_RESULTS,
    "images": [],
    "response_time": 1.31,
}


@pytest.fixture
def mock_tavily():
    """Mock TavilySearch tool."""
    mock = MagicMock()
    mock.invoke.return_value = SAMPLE_TAVILY_RESPONSE
    return mock


@pytest.fixture
def mock_gemini():
    """Mock Google Gemini model."""
    mock = MagicMock()
    mock.invoke.return_value = AIMessage(
        content="## 한줄 요약\nAI 에이전트는 자율적인 시스템입니다.\n\n## 핵심 포인트\n- 포인트1\n- 포인트2"
    )
    return mock


# ---------------------------------------------------------------------------
# Middleware Helper Tests
# ---------------------------------------------------------------------------


class TestApplyPiiFilter:
    def test_filters_email(self):
        text = "연락처: user@example.com"
        result = apply_pii_filter(text)
        assert "[EMAIL_REDACTED]" in result
        assert "user@example.com" not in result

    def test_filters_phone(self):
        text = "전화: 010-1234-5678"
        result = apply_pii_filter(text)
        assert "[PHONE_REDACTED]" in result
        assert "010-1234-5678" not in result

    def test_filters_card(self):
        text = "카드: 1234-5678-9012-3456"
        result = apply_pii_filter(text)
        assert "[CARD_REDACTED]" in result

    def test_filters_all_types(self):
        text = "이메일: a@b.com, 전화: 010-1111-2222, 카드: 1111-2222-3333-4444"
        result = apply_pii_filter(text)
        assert "[EMAIL_REDACTED]" in result
        assert "[PHONE_REDACTED]" in result
        assert "[CARD_REDACTED]" in result

    def test_filters_specific_type_only(self):
        text = "이메일: a@b.com, 전화: 010-1111-2222"
        result = apply_pii_filter(text, pii_types=["email"])
        assert "[EMAIL_REDACTED]" in result
        assert "010-1111-2222" in result  # Phone NOT filtered

    def test_no_pii_returns_unchanged(self):
        text = "일반 텍스트입니다."
        result = apply_pii_filter(text)
        assert result == text

    def test_card_before_phone_avoids_collision(self):
        text = "카드: 1234-5678-9012-3456"
        result = apply_pii_filter(text)
        assert "[CARD_REDACTED]" in result
        assert "[PHONE_REDACTED]" not in result


# ---------------------------------------------------------------------------
# Condition Function Tests
# ---------------------------------------------------------------------------


class TestShouldSummarizeConversation:
    def test_skip_when_below_threshold(self):
        state = {"messages": [HumanMessage(content="m")] * MESSAGE_THRESHOLD}
        assert should_summarize_conversation(state) == "skip_summary"

    def test_needs_summary_when_above_threshold(self):
        state = {"messages": [HumanMessage(content="m")] * (MESSAGE_THRESHOLD + 1)}
        assert should_summarize_conversation(state) == "needs_summary"

    def test_skip_when_empty(self):
        assert should_summarize_conversation({"messages": []}) == "skip_summary"
        assert should_summarize_conversation({}) == "skip_summary"


class TestIsApproved:
    def test_approved_when_true(self):
        assert is_approved({"is_approved": True}) == "approved"

    def test_rejected_when_false(self):
        assert is_approved({"is_approved": False}) == "rejected"

    def test_rejected_when_missing(self):
        assert is_approved({}) == "rejected"


# ---------------------------------------------------------------------------
# WebSearchNode Tests
# ---------------------------------------------------------------------------


class TestWebSearchNode:
    def test_reads_topic_from_messages_and_writes_search_results(self, mock_tavily):
        node = WebSearchNode()
        node._search = mock_tavily

        result = node.execute({"messages": [HumanMessage(content="AI 에이전트")]})

        assert "search_results" in result
        assert len(result["search_results"]) == 2
        assert result["topic"] == "AI 에이전트"
        mock_tavily.invoke.assert_called_once_with({"query": "AI 에이전트"})

    def test_handles_content_block_list(self, mock_tavily):
        """Content may arrive as a list of blocks from LangGraph Studio."""
        node = WebSearchNode()
        node._search = mock_tavily

        content_blocks = [{"type": "text", "text": "AI 에이전트"}]
        result = node.execute(
            {"messages": [HumanMessage(content=content_blocks)]}
        )

        assert result["topic"] == "AI 에이전트"
        mock_tavily.invoke.assert_called_once_with({"query": "AI 에이전트"})

    def test_returns_dict(self, mock_tavily):
        node = WebSearchNode()
        node._search = mock_tavily

        result = node.execute({"messages": [HumanMessage(content="test")]})

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# SummarizeNode Tests
# ---------------------------------------------------------------------------


class TestSummarizeNode:
    def test_reads_topic_and_search_results(self, mock_gemini):
        node = SummarizeNode()
        node._model = mock_gemini

        state = {
            "topic": "AI 에이전트",
            "search_results": SAMPLE_SEARCH_RESULTS,
        }
        result = node.execute(state)

        assert "summary" in result
        assert "messages" in result
        assert "한줄 요약" in result["summary"]

    def test_writes_messages_list(self, mock_gemini):
        node = SummarizeNode()
        node._model = mock_gemini

        state = {
            "topic": "test",
            "search_results": SAMPLE_SEARCH_RESULTS,
        }
        result = node.execute(state)

        assert len(result["messages"]) == 2  # HumanMessage + AIMessage

    def test_formats_results_correctly(self):
        node = SummarizeNode()

        formatted = node._format_results(SAMPLE_SEARCH_RESULTS)

        assert "[1] AI Agents Overview" in formatted
        assert "[2] LangGraph Guide" in formatted
        assert "https://example.com/ai-agents" in formatted

    def test_handles_empty_search_results(self, mock_gemini):
        node = SummarizeNode()
        node._model = mock_gemini

        state = {"topic": "test", "search_results": []}
        result = node.execute(state)

        assert "summary" in result

    def test_applies_pii_filter_to_summary(self):
        """Verify PIIMiddleware is applied to summary output."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(
            content="담당자: admin@company.com, 전화: 010-9999-8888"
        )

        node = SummarizeNode()
        node._model = mock_model

        state = {"topic": "test", "search_results": SAMPLE_SEARCH_RESULTS}
        result = node.execute(state)

        assert "admin@company.com" not in result["summary"]
        assert "[EMAIL_REDACTED]" in result["summary"]
        assert "[PHONE_REDACTED]" in result["summary"]

    def test_model_receives_system_and_user_messages(self, mock_gemini):
        node = SummarizeNode()
        node._model = mock_gemini

        state = {
            "topic": "AI",
            "search_results": SAMPLE_SEARCH_RESULTS,
        }
        node.execute(state)

        call_args = mock_gemini.invoke.call_args[0][0]
        assert len(call_args) == 2  # SystemMessage + HumanMessage


# ---------------------------------------------------------------------------
# ConversationSummaryNode Tests
# ---------------------------------------------------------------------------


class TestConversationSummaryNode:
    def test_summarizes_messages(self):
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(
            content="대화 요약: 사용자가 AI 에이전트에 대해 질문했습니다."
        )

        node = ConversationSummaryNode()
        node._model = mock_model

        messages = [
            HumanMessage(content="AI 에이전트란?", id="msg1"),
            AIMessage(content="AI 에이전트는...", id="msg2"),
            HumanMessage(content="더 알려줘", id="msg3"),
            AIMessage(content="추가 정보는...", id="msg4"),
            HumanMessage(content="요약해줘", id="msg5"),
        ]

        result = node.execute({"messages": messages})

        assert "messages" in result
        mock_model.invoke.assert_called_once()

    def test_removes_old_messages(self):
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content="요약 내용")

        node = ConversationSummaryNode()
        node._model = mock_model

        messages = [
            HumanMessage(content="msg1", id="id1"),
            AIMessage(content="msg2", id="id2"),
            HumanMessage(content="msg3", id="id3"),
        ]

        result = node.execute({"messages": messages})

        # Should contain RemoveMessage objects for old messages + SystemMessage for summary
        result_messages = result["messages"]
        # Last 1 message kept, first 2 removed → 2 RemoveMessages + 1 SystemMessage
        assert len(result_messages) == 3

    def test_summary_contains_context_marker(self):
        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content="핵심 내용 요약")

        node = ConversationSummaryNode()
        node._model = mock_model

        messages = [HumanMessage(content="test", id="id1")]
        result = node.execute({"messages": messages})

        # Find the SystemMessage in results
        system_msgs = [
            m for m in result["messages"] if isinstance(m, SystemMessage)
        ]
        assert len(system_msgs) == 1
        assert "[이전 대화 요약]" in system_msgs[0].content


# ---------------------------------------------------------------------------
# HumanApprovalNode Tests
# ---------------------------------------------------------------------------


class TestHumanApprovalNode:
    @patch("casts.orchestrator.modules.nodes.interrupt")
    def test_approve_with_email(self, mock_interrupt):
        mock_interrupt.return_value = "user@example.com"

        node = HumanApprovalNode()
        result = node.execute({"summary": "테스트 요약"})

        assert result["recipient_email"] == "user@example.com"
        assert result["is_approved"] is True

    @patch("casts.orchestrator.modules.nodes.interrupt")
    def test_reject(self, mock_interrupt):
        mock_interrupt.return_value = "reject"

        node = HumanApprovalNode()
        result = node.execute({"summary": "테스트 요약"})

        assert result["recipient_email"] == ""
        assert result["is_approved"] is False

    @patch("casts.orchestrator.modules.nodes.interrupt")
    def test_reject_case_insensitive(self, mock_interrupt):
        mock_interrupt.return_value = "REJECT"

        node = HumanApprovalNode()
        result = node.execute({"summary": "요약"})

        assert result["is_approved"] is False

    @patch("casts.orchestrator.modules.nodes.interrupt")
    def test_reject_with_whitespace(self, mock_interrupt):
        mock_interrupt.return_value = "  reject  "

        node = HumanApprovalNode()
        result = node.execute({"summary": "요약"})

        assert result["is_approved"] is False

    @patch("casts.orchestrator.modules.nodes.interrupt")
    def test_interrupt_payload_contains_summary(self, mock_interrupt):
        mock_interrupt.return_value = "user@example.com"

        node = HumanApprovalNode()
        node.execute({"summary": "내 요약 내용"})

        call_args = mock_interrupt.call_args[0][0]
        assert "summary" in call_args
        assert call_args["summary"] == "내 요약 내용"
        assert "instruction" in call_args


# ---------------------------------------------------------------------------
# EmailSendNode Tests
# ---------------------------------------------------------------------------


class TestEmailSendNode:
    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    @patch("casts.orchestrator.modules.nodes.resend")
    def test_sends_email_successfully(self, mock_resend):
        mock_resend.Emails.send.return_value = {"id": "email_123"}

        node = EmailSendNode()
        state = {
            "topic": "AI 에이전트",
            "summary": "## 한줄 요약\nAI 요약입니다.",
            "recipient_email": "user@example.com",
        }

        result = node.execute(state)

        assert result["email_sent"] is True
        mock_resend.Emails.send.assert_called_once()

        send_params = mock_resend.Emails.send.call_args[0][0]
        assert send_params["to"] == ["user@example.com"]
        assert "[Summary] AI 에이전트" in send_params["subject"]

    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    @patch("casts.orchestrator.modules.nodes.resend")
    def test_handles_send_failure(self, mock_resend):
        mock_resend.Emails.send.side_effect = Exception("API error")

        node = EmailSendNode()
        state = {
            "topic": "test",
            "summary": "summary",
            "recipient_email": "user@example.com",
        }

        result = node.execute(state)

        assert result["email_sent"] is False

    @patch.dict(
        "os.environ",
        {"RESEND_API_KEY": "re_test_key", "RESEND_FROM_EMAIL": "custom@domain.com"},
    )
    @patch("casts.orchestrator.modules.nodes.resend")
    def test_uses_custom_from_email(self, mock_resend):
        mock_resend.Emails.send.return_value = {"id": "email_123"}

        node = EmailSendNode()
        state = {
            "topic": "test",
            "summary": "summary",
            "recipient_email": "user@example.com",
        }

        node.execute(state)

        send_params = mock_resend.Emails.send.call_args[0][0]
        assert send_params["from"] == "custom@domain.com"

    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    @patch("casts.orchestrator.modules.nodes.resend")
    def test_summary_html_conversion(self, mock_resend):
        mock_resend.Emails.send.return_value = {"id": "email_123"}

        node = EmailSendNode()
        state = {
            "topic": "test",
            "summary": "line1\nline2\nline3",
            "recipient_email": "user@example.com",
        }

        node.execute(state)

        send_params = mock_resend.Emails.send.call_args[0][0]
        assert "<br>" in send_params["html"]

"""Integration tests for the myAgent (create_agent-based) graph.

Tests agent graph compilation, tool registration,
and basic invocation with mocked dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from casts.orchestrator.graph import my_agent_graph
from casts.orchestrator.modules.agents import my_agent
from casts.orchestrator.modules.tools import send_email, web_search


# ---------------------------------------------------------------------------
# Graph Compilation Tests
# ---------------------------------------------------------------------------


class TestMyAgentCompilation:
    def test_graph_is_not_none(self):
        """Agent graph should be created successfully."""
        assert my_agent_graph is not None

    def test_graph_has_invoke(self):
        """Agent graph should be invocable."""
        assert hasattr(my_agent_graph, "invoke")

    def test_graph_name(self):
        """Agent graph should have the configured name."""
        assert my_agent_graph.name == "myAgent"

    def test_platform_graph_has_no_checkpointer(self):
        """Platform-exported graph should have no checkpointer (Platform provides its own)."""
        assert my_agent_graph.checkpointer is None

    def test_creates_new_instance(self):
        """my_agent() should create a fresh agent instance each call."""
        agent = my_agent()
        assert agent is not None
        assert hasattr(agent, "invoke")

    def test_injected_checkpointer(self):
        """my_agent(checkpointer=InMemorySaver()) should attach the checkpointer."""
        from langgraph.checkpoint.memory import InMemorySaver

        saver = InMemorySaver()
        agent = my_agent(checkpointer=saver)
        assert agent.checkpointer is saver


# ---------------------------------------------------------------------------
# Tool Registration Tests
# ---------------------------------------------------------------------------


class TestToolRegistration:
    def test_web_search_tool_exists(self):
        """web_search tool should be defined and callable."""
        assert web_search is not None
        assert web_search.name == "web_search"

    def test_send_email_tool_exists(self):
        """send_email tool should be defined and callable."""
        assert send_email is not None
        assert send_email.name == "send_email"

    def test_web_search_has_description(self):
        """web_search tool should have a docstring-based description."""
        assert web_search.description
        assert "search" in web_search.description.lower()

    def test_send_email_has_description(self):
        """send_email tool should have a docstring-based description."""
        assert send_email.description
        assert "email" in send_email.description.lower()


# ---------------------------------------------------------------------------
# Tool Unit Tests (mocked external calls)
# ---------------------------------------------------------------------------


class TestWebSearchTool:
    @patch("casts.orchestrator.modules.tools.TavilySearch")
    def test_returns_formatted_results(self, mock_tavily_cls):
        """web_search should format Tavily results into readable text."""
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = {
            "results": [
                {
                    "title": "Test Article",
                    "url": "https://example.com",
                    "content": "Test content about AI.",
                },
            ]
        }
        mock_tavily_cls.return_value = mock_instance

        result = web_search.invoke({"query": "AI 트렌드"})

        assert "Test Article" in result
        assert "https://example.com" in result
        assert "Test content about AI." in result

    @patch("casts.orchestrator.modules.tools.TavilySearch")
    def test_handles_empty_results(self, mock_tavily_cls):
        """web_search should handle empty results gracefully."""
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = {"results": []}
        mock_tavily_cls.return_value = mock_instance

        result = web_search.invoke({"query": "nonexistent topic"})
        assert result == ""


class TestSendEmailTool:
    @patch("casts.orchestrator.modules.tools.resend")
    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    def test_successful_send(self, mock_resend):
        """send_email should return success message on successful send."""
        mock_resend.Emails.send.return_value = {"id": "email_123"}

        result = send_email.invoke({
            "to": "user@example.com",
            "subject": "[Summary] AI",
            "body": "테스트 요약입니다.",
        })

        assert "성공" in result
        mock_resend.Emails.send.assert_called_once()

    @patch("casts.orchestrator.modules.tools.resend")
    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    def test_failed_send(self, mock_resend):
        """send_email should return failure message on API error."""
        mock_resend.Emails.send.side_effect = Exception("API error")

        result = send_email.invoke({
            "to": "user@example.com",
            "subject": "Test",
            "body": "Test body",
        })

        assert "실패" in result

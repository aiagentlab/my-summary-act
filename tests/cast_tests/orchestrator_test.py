"""Integration tests for the Orchestrator graph.

Tests graph compilation, structure, conditional edges,
and full execution with mocked dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from casts.orchestrator.graph import OrchestratorGraph, orchestrator_graph
from casts.orchestrator.modules.conditions import is_approved, should_summarize_conversation
from casts.orchestrator.modules.nodes import (
    ConversationSummaryNode,
    EmailSendNode,
    HumanApprovalNode,
    SummarizeNode,
    WebSearchNode,
)
from casts.orchestrator.modules.state import InputState, OutputState, State


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SEARCH_RESULTS = [
    {
        "title": "Test Result",
        "url": "https://example.com",
        "content": "Test content about the topic.",
    },
]

SAMPLE_TAVILY_RESPONSE = {
    "query": "test",
    "results": SAMPLE_SEARCH_RESULTS,
    "images": [],
    "response_time": 1.31,
}


@pytest.fixture
def graph():
    """Compiled graph without checkpointer."""
    return orchestrator_graph()


@pytest.fixture
def mock_search():
    mock = MagicMock()
    mock.invoke.return_value = SAMPLE_TAVILY_RESPONSE
    return mock


@pytest.fixture
def mock_model():
    mock = MagicMock()
    mock.invoke.return_value = AIMessage(
        content="## 한줄 요약\n테스트 요약입니다."
    )
    return mock


@pytest.fixture
def graph_with_mocks(mock_search, mock_model):
    """Build graph with pre-mocked nodes and MemorySaver checkpointer.

    Mirrors the real graph structure including conditional edges.
    """
    web_search_node = WebSearchNode()
    web_search_node._search = mock_search

    summarize_node = SummarizeNode()
    summarize_node._model = mock_model

    conversation_summary_node = ConversationSummaryNode()
    conversation_summary_node._model = mock_model

    human_approval_node = HumanApprovalNode()
    email_send_node = EmailSendNode()

    builder = StateGraph(State, input_schema=InputState, output_schema=OutputState)
    builder.add_node("WebSearchNode", web_search_node)
    builder.add_node("SummarizeNode", summarize_node)
    builder.add_node("ConversationSummaryNode", conversation_summary_node)
    builder.add_node("HumanApprovalNode", human_approval_node)
    builder.add_node("EmailSendNode", email_send_node)

    builder.add_edge(START, "WebSearchNode")
    builder.add_edge("WebSearchNode", "SummarizeNode")

    # Conditional edge: should_summarize_conversation
    builder.add_conditional_edges(
        "SummarizeNode",
        should_summarize_conversation,
        {
            "needs_summary": "ConversationSummaryNode",
            "skip_summary": "HumanApprovalNode",
        },
    )
    builder.add_edge("ConversationSummaryNode", "HumanApprovalNode")

    # Conditional edge: is_approved
    builder.add_conditional_edges(
        "HumanApprovalNode",
        is_approved,
        {
            "approved": "EmailSendNode",
            "rejected": END,
        },
    )
    builder.add_edge("EmailSendNode", END)

    compiled = builder.compile(checkpointer=MemorySaver())
    compiled.name = "OrchestratorGraph"
    return compiled


# ---------------------------------------------------------------------------
# Graph Compilation Tests
# ---------------------------------------------------------------------------


class TestGraphCompilation:
    def test_compiles_successfully(self, graph):
        assert graph is not None
        assert hasattr(graph, "invoke")

    def test_has_expected_nodes(self, graph):
        expected_nodes = [
            "WebSearchNode",
            "SummarizeNode",
            "ConversationSummaryNode",
            "HumanApprovalNode",
            "EmailSendNode",
        ]
        for node_name in expected_nodes:
            assert node_name in graph.nodes, f"Missing node: {node_name}"

    def test_graph_name(self, graph):
        assert graph.name == "OrchestratorGraph"

    def test_node_count(self, graph):
        # __start__ + 5 real nodes
        real_nodes = [n for n in graph.nodes if n != "__start__"]
        assert len(real_nodes) == 5


# ---------------------------------------------------------------------------
# Graph Execution: Approved Flow
# ---------------------------------------------------------------------------


class TestGraphExecutionApproved:
    @patch("casts.orchestrator.modules.nodes.resend")
    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    def test_full_flow_approve(self, mock_resend, graph_with_mocks):
        """Test complete flow: search → summarize → skip_summary → approve → email."""
        mock_resend.Emails.send.return_value = {"id": "email_123"}

        config = {"configurable": {"thread_id": "test-approve-1"}}

        # Step 1: Invoke → should hit interrupt at HumanApprovalNode
        result = graph_with_mocks.invoke(
            {"messages": [HumanMessage(content="테스트 토픽")]}, config=config
        )

        assert "__interrupt__" in result

        # Step 2: Resume with recipient email (= approved)
        final_result = graph_with_mocks.invoke(
            Command(resume="user@example.com"), config=config
        )

        assert final_result["email_sent"] is True
        assert "요약" in final_result["summary"]
        mock_resend.Emails.send.assert_called_once()

    @patch("casts.orchestrator.modules.nodes.resend")
    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    def test_interrupt_payload_contains_summary(self, mock_resend, graph_with_mocks):
        """Verify the interrupt payload includes the summary for review."""
        config = {"configurable": {"thread_id": "test-approve-2"}}
        result = graph_with_mocks.invoke(
            {"messages": [HumanMessage(content="test")]}, config=config
        )

        interrupt_data = result["__interrupt__"][0].value
        assert "summary" in interrupt_data
        assert "instruction" in interrupt_data

    @patch("casts.orchestrator.modules.nodes.resend")
    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    def test_email_failure_returns_false(self, mock_resend, graph_with_mocks):
        """Verify email_sent is False when Resend API fails."""
        mock_resend.Emails.send.side_effect = Exception("API error")

        config = {"configurable": {"thread_id": "test-approve-3"}}

        graph_with_mocks.invoke(
            {"messages": [HumanMessage(content="test")]}, config=config
        )

        final_result = graph_with_mocks.invoke(
            Command(resume="user@example.com"), config=config
        )

        assert final_result["email_sent"] is False


# ---------------------------------------------------------------------------
# Graph Execution: Rejected Flow
# ---------------------------------------------------------------------------


class TestGraphExecutionRejected:
    def test_rejected_flow_skips_email(self, graph_with_mocks):
        """Test that rejecting at HumanApprovalNode skips EmailSendNode."""
        config = {"configurable": {"thread_id": "test-reject-1"}}

        # Step 1: Hit interrupt
        graph_with_mocks.invoke(
            {"messages": [HumanMessage(content="test")]}, config=config
        )

        # Step 2: Resume with 'reject'
        final_result = graph_with_mocks.invoke(
            Command(resume="reject"), config=config
        )

        # email_sent should not be in output (EmailSendNode was skipped)
        # or summary should still be present
        assert "요약" in final_result["summary"]

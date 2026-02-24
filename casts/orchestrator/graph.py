"""Entry point for the Orchestrator graph.

Sequential + Conditional + Middleware pattern:
  START → WebSearchNode → SummarizeNode → [should_summarize_conversation]
    → needs_summary → ConversationSummaryNode → HumanApprovalNode
    → skip_summary → HumanApprovalNode
  HumanApprovalNode → [is_approved]
    → approved → EmailSendNode → END
    → rejected → END

Conditional edges route dynamically based on state.
LangGraph Platform automatically provides checkpointing for interrupt support.
"""

from langgraph.graph import END, START, StateGraph

from casts.base_graph import BaseGraph
from casts.orchestrator.modules.conditions import (
    is_approved,
    should_summarize_conversation,
)
from casts.orchestrator.modules.nodes import (
    ConversationSummaryNode,
    EmailSendNode,
    HumanApprovalNode,
    SummarizeNode,
    WebSearchNode,
)
from casts.orchestrator.modules.state import InputState, OutputState, State


class OrchestratorGraph(BaseGraph):
    """Graph definition for Orchestrator.

    Attributes:
        input: Input schema for the graph.
        output: Output schema for the graph.
        state: State schema for the graph.
    """

    def __init__(self) -> None:
        super().__init__()
        self.input = InputState
        self.output = OutputState
        self.state = State

    def build(self):
        """Builds and compiles the orchestrator graph.

        Returns:
            CompiledStateGraph: Compiled graph ready for execution.
        """
        builder = StateGraph(
            self.state, input_schema=self.input, output_schema=self.output
        )

        # Register nodes
        builder.add_node("WebSearchNode", WebSearchNode())
        builder.add_node("SummarizeNode", SummarizeNode())
        builder.add_node("ConversationSummaryNode", ConversationSummaryNode())
        builder.add_node("HumanApprovalNode", HumanApprovalNode())
        builder.add_node("EmailSendNode", EmailSendNode())

        # Entry edge
        builder.add_edge(START, "WebSearchNode")

        # Sequential edges
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

        graph = builder.compile()
        graph.name = self.name
        return graph


orchestrator_graph = OrchestratorGraph()

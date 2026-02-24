"""[Optional] Helper utilities used across the Orchestrator graph.

Guidelines:
    - Extract reusable data processing or formatting logic.
    - Keep node implementations concise by delegating to helpers.
"""


def extract_text(content) -> str:
    """Extract plain text from message content.

    LangGraph Studio and newer LLM APIs may return content as either
    a plain string or a list of content blocks.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block["text"] for block in content if block.get("type") == "text"
        )
    return str(content)

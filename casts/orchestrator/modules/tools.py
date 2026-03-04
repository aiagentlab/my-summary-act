"""Tool definitions for the Orchestrator agent.

Two tools that replace the fixed StateGraph nodes:
- web_search: Replaces WebSearchNode (Tavily web search)
- send_email: Replaces EmailSendNode (Resend API email delivery)

Usage with create_agent:
    from .tools import web_search, send_email
    agent = create_agent(model=..., tools=[web_search, send_email], ...)
"""

import os

import resend
from langchain_core.tools import tool
from langchain_tavily import TavilySearch


@tool
def web_search(query: str) -> str:
    """Search the web for a given topic and return formatted results.

    Args:
        query: The search topic or query string.

    Returns:
        Formatted search results with title, URL, and content for each result.
    """
    search = TavilySearch(
        max_results=5,
        topic="general",
        include_raw_content=False,
    )
    response = search.invoke({"query": query})
    results = response.get("results", [])

    formatted = []
    for i, result in enumerate(results, 1):
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")
        formatted.append(f"[{i}] {title}\nURL: {url}\n{content}")

    return "\n\n".join(formatted)


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email with the given subject and body to the recipient.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body content (plain text, will be converted to HTML).

    Returns:
        Success or failure message.
    """
    resend.api_key = os.environ["RESEND_API_KEY"]
    from_email = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")

    body_html = body.replace("\n", "<br>")

    params = {
        "from": from_email,
        "to": [to],
        "subject": subject,
        "html": body_html,
    }

    try:
        resend.Emails.send(params)
        return f"이메일이 {to}에게 성공적으로 발송되었습니다."
    except Exception as e:
        return f"이메일 발송 실패: {e}"

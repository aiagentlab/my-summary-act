"""Model configuration for the Orchestrator graph."""

from langchain_google_genai import ChatGoogleGenerativeAI


def get_gemini_model():
    """Create a Google Gemini model instance."""
    return ChatGoogleGenerativeAI(model="gemini-2.0-flash")

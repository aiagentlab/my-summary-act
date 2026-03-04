# my-agent-checkpointer Design Document

> **Summary**: my_agent의 create_agent()에 InMemorySaver checkpointer를 직접 전달하여 로컬/테스트 환경 interrupt/resume 지원
>
> **Project**: my-summary-act
> **Author**: Leo
> **Date**: 2026-03-04
> **Status**: Draft
> **Planning Doc**: [my-agent-checkpointer.plan.md](../../01-plan/features/my-agent-checkpointer.plan.md)

---

## 1. Overview

### 1.1 Design Goals

- `create_agent()`의 `checkpointer` 파라미터에 `InMemorySaver`를 전달하여 로컬 interrupt/resume 지원
- 기존 코드 최소 변경 (1개 파일, 2줄 추가)
- LangGraph Platform 배포 호환성 유지

### 1.2 Design Principles

- **최소 변경 원칙**: agents.py에 import 1줄 + 파라미터 1줄만 추가
- **기존 패턴 일관성**: orchestrator_test.py에서 이미 사용 중인 MemorySaver 패턴과 동일

---

## 2. Architecture

### 2.1 변경 전 (현재)

```
langgraph.json
  └─ "my_agent" → graph.py:my_agent_graph
                    └─ my_agent()  (agents.py)
                        └─ create_agent(model, tools, middleware, ...)
                            └─ checkpointer = None  ← interrupt 불가 (로컬)
```

### 2.2 변경 후

```
langgraph.json
  └─ "my_agent" → graph.py:my_agent_graph
                    └─ my_agent()  (agents.py)
                        └─ create_agent(model, tools, middleware, ..., checkpointer=InMemorySaver())
                            └─ checkpointer = InMemorySaver  ← interrupt/resume 가능
```

### 2.3 LangGraph Platform 호환성

```
로컬 실행 (uv run):
  create_agent(checkpointer=InMemorySaver())  → 메모리 기반 체크포인트 사용

Platform 실행 (langgraph dev / langgraph up):
  Platform이 checkpointer를 PostgreSQL 기반으로 자동 교체  → InMemorySaver 무시됨
```

---

## 3. Implementation Detail

### 3.1 변경 대상 파일

| File | Action | Lines Changed |
|------|--------|:------------:|
| `casts/orchestrator/modules/agents.py` | Modify | +2 |
| `tests/cast_tests/my_agent_test.py` | Create | ~80 |

### 3.2 agents.py 변경 사항

**Before:**
```python
from langchain.agents import create_agent

from .middlewares import (...)
from .prompts import AGENT_SYSTEM_PROMPT
from .tools import send_email, web_search


def my_agent():
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
    )
```

**After:**
```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from .middlewares import (...)
from .prompts import AGENT_SYSTEM_PROMPT
from .tools import send_email, web_search


def my_agent():
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
        checkpointer=InMemorySaver(),
    )
```

### 3.3 my_agent_test.py 설계

```python
"""Tests for my_agent (create_agent based).

Tests interrupt/resume flow via HumanInTheLoopMiddleware.
"""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from casts.orchestrator.graph import my_agent_graph


class TestMyAgentCompilation:
    """Agent graph compiles and has expected structure."""

    def test_compiles_successfully(self):
        assert my_agent_graph is not None
        assert hasattr(my_agent_graph, "invoke")

    def test_graph_name(self):
        assert my_agent_graph.name == "myAgent"


class TestMyAgentInterruptResume:
    """Interrupt/resume flow with mocked LLM and tools."""

    @patch("casts.orchestrator.modules.tools.TavilySearch")
    @patch("casts.orchestrator.modules.tools.resend")
    def test_interrupt_on_send_email(self, mock_resend, mock_tavily):
        # Setup: invoke with topic → agent calls web_search → tries send_email → interrupt
        config = {"configurable": {"thread_id": "test-agent-1"}}
        result = my_agent_graph.invoke(
            {"messages": [HumanMessage(content="AI 뉴스 요약해줘")]},
            config=config,
        )
        # Verify interrupt occurred
        assert "__interrupt__" in result

    @patch("casts.orchestrator.modules.tools.TavilySearch")
    @patch("casts.orchestrator.modules.tools.resend")
    def test_resume_after_approval(self, mock_resend, mock_tavily):
        # Setup + interrupt
        config = {"configurable": {"thread_id": "test-agent-2"}}
        my_agent_graph.invoke(
            {"messages": [HumanMessage(content="test")]},
            config=config,
        )
        # Resume with approval
        final = my_agent_graph.invoke(
            Command(resume="user@example.com"),
            config=config,
        )
        # Verify email tool was called after approval
        mock_resend.Emails.send.assert_called_once()
```

---

## 4. Test Plan

### 4.1 Test Scope

| Type | Target | Tool |
|------|--------|------|
| Unit Test | Agent compilation, structure | pytest |
| Integration Test | interrupt/resume flow | pytest + mocks |
| Manual Test | `langgraph dev` 실행 확인 | LangGraph Studio |

### 4.2 Test Cases

| ID | Case | Expected Result |
|----|------|-----------------|
| TC-01 | Agent graph 컴파일 성공 | `my_agent_graph` is not None |
| TC-02 | Graph name 확인 | `"myAgent"` |
| TC-03 | send_email 호출 시 interrupt 발생 | `__interrupt__` in result |
| TC-04 | resume 후 이메일 발송 | `mock_resend.Emails.send` called |
| TC-05 | 기존 orchestrator 테스트 regression 없음 | 전체 테스트 통과 |

---

## 5. Implementation Order

1. [ ] `agents.py` 수정 (import + checkpointer 파라미터 추가)
2. [ ] `my_agent_test.py` 작성
3. [ ] 전체 테스트 실행 (`uv run pytest`)
4. [ ] `langgraph dev` 기동 확인

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-04 | Initial draft | Leo |

# my_agent InMemorySaver Checkpointer 설정 Planning Document

> **Summary**: my_agent(create_agent 기반)에 InMemorySaver checkpointer를 연결하여 로컬/테스트 환경에서 interrupt/resume 지원
>
> **Project**: my-summary-act
> **Author**: Leo
> **Date**: 2026-03-04
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

`my_agent`는 `create_agent()`로 생성된 compiled graph를 반환하지만, checkpointer가 명시적으로 설정되어 있지 않다. LangGraph Platform 배포 시에는 자동 주입되지만, **로컬 실행 및 테스트 환경**에서는 `interrupt`/`resume`가 동작하지 않는 문제를 해결한다.

### 1.2 Background

- `orchestrator_graph`(StateGraph 기반)의 테스트에서는 이미 `MemorySaver`를 수동 주입하여 사용 중 (`orchestrator_test.py:121`)
- `my_agent`는 `create_agent` API를 사용하며, `HumanInTheLoopMiddleware`가 `send_email` 전에 interrupt를 발생시킴
- Checkpointer 없이는 interrupt 후 resume가 불가능하여 이메일 승인 플로우가 로컬에서 작동하지 않음

### 1.3 Related Documents

- Cast Architecture: `casts/orchestrator/CLAUDE.md`
- 현재 Agent 코드: `casts/orchestrator/modules/agents.py`
- 기존 테스트 참조: `tests/cast_tests/orchestrator_test.py`

---

## 2. Scope

### 2.1 In Scope

- [ ] `my_agent()` 함수에 `checkpointer` 파라미터 추가
- [ ] `InMemorySaver`를 기본 checkpointer로 설정
- [ ] `my_agent` 전용 테스트 작성 (interrupt/resume 검증)

### 2.2 Out of Scope

- `orchestrator_graph`(StateGraph 기반) 수정
- PostgreSQL 등 영구 저장소 checkpointer 연결 (Platform 배포용)
- 미들웨어 로직 변경

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | `create_agent()`에 `checkpointer=InMemorySaver()` 전달 | High | Pending |
| FR-02 | `langgraph dev` 실행 시 기존 동작과 동일하게 작동 | High | Pending |
| FR-03 | interrupt/resume 플로우 테스트 작성 및 통과 | High | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| 호환성 | LangGraph Platform 자동 checkpointer와 충돌 없음 | `langgraph dev`로 실행 확인 |
| 테스트 | my_agent interrupt/resume 테스트 통과 | `uv run pytest` |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] `agents.py`에 `InMemorySaver` checkpointer 연결 완료
- [ ] `my_agent` 테스트에서 interrupt → resume → email_sent 플로우 통과
- [ ] 기존 `orchestrator_graph` 테스트 영향 없음 (regression 없음)

### 4.2 Quality Criteria

- [ ] 기존 테스트 전체 통과
- [ ] `langgraph dev` 정상 기동 확인

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `create_agent`가 `checkpointer` 파라미터를 지원하지 않을 수 있음 | High | Medium | 공식 문서 확인 후 대안(graph.py에서 래핑) 준비 |
| Platform 자동 checkpointer와 InMemorySaver 충돌 | Medium | Low | Platform은 compile 시점에 덮어쓰므로 충돌 없을 것으로 예상 |
| InMemorySaver는 프로세스 재시작 시 상태 소실 | Low | High | 로컬/테스트 용도이므로 의도된 동작 |

---

## 6. Implementation Approach

### 6.1 변경 대상 파일

| File | Change | Description |
|------|--------|-------------|
| `casts/orchestrator/modules/agents.py` | Modify | `create_agent()`에 `checkpointer` 파라미터 추가 |
| `tests/cast_tests/my_agent_test.py` | Create | interrupt/resume 플로우 테스트 |

### 6.2 핵심 변경 내용

**Option A** (우선): `create_agent`에 직접 전달

```python
from langgraph.checkpoint.memory import InMemorySaver

return create_agent(
    model="google_genai:gemini-2.0-flash",
    tools=[web_search, send_email],
    middleware=[...],
    system_prompt=AGENT_SYSTEM_PROMPT,
    name="myAgent",
    checkpointer=InMemorySaver(),
)
```

**Option B** (대안): `graph.py`에서 래핑

```python
# graph.py
from langgraph.checkpoint.memory import InMemorySaver

agent = my_agent()
my_agent_graph = agent  # Platform용 (자동 주입)
my_agent_graph_local = agent.compile(checkpointer=InMemorySaver())  # 로컬용
```

### 6.3 구현 순서

1. `create_agent` API의 `checkpointer` 파라미터 지원 여부 확인
2. `agents.py` 수정 (Option A 또는 B)
3. `my_agent_test.py` 작성
4. 전체 테스트 실행 및 검증

---

## 7. Next Steps

1. [ ] Design 문서 작성 (`/pdca design my-agent-checkpointer`)
2. [ ] 구현 시작 (`/pdca do my-agent-checkpointer`)
3. [ ] Gap 분석 (`/pdca analyze my-agent-checkpointer`)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-04 | Initial draft | Leo |

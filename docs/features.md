# 기능명세서: My Summary Agent

## 문서 정보

| 항목 | 내용 |
|------|------|
| 프로젝트 | My Summary Agent |
| 버전 | v2 (Sequential + Conditional + Middleware) |
| 최종 수정일 | 2026-02-24 |

---

## 1. 기능 목록

| ID | 기능명 | 분류 | 우선순위 | 구현 파일 |
|----|--------|------|----------|-----------|
| F-1 | 웹 검색 | 핵심 | P0 | nodes.py (WebSearchNode) |
| F-2 | 구조화된 요약 생성 | 핵심 | P0 | nodes.py (SummarizeNode) |
| F-3 | PII 자동 마스킹 | 보안 | P0 | middlewares.py (apply_pii_filter) |
| F-4 | 사용자 승인/거부 | 핵심 | P0 | nodes.py (HumanApprovalNode) |
| F-5 | 이메일 발송 | 핵심 | P0 | nodes.py (EmailSendNode) |
| F-6 | 대화 이력 자동 요약 | 최적화 | P1 | nodes.py (ConversationSummaryNode) |
| F-7 | 조건부 분기: 대화 요약 | 제어 흐름 | P1 | conditions.py (should_summarize_conversation) |
| F-8 | 조건부 분기: 승인 라우팅 | 제어 흐름 | P1 | conditions.py (is_approved) |
| F-9 | Agent Middleware 팩토리 | 확장 | P2 | middlewares.py (get_*_middleware) |

---

## 2. 기능 상세

### F-1. 웹 검색

**구현체:** `WebSearchNode` (`casts/orchestrator/modules/nodes.py`)

#### 설명
사용자가 입력한 토픽으로 Tavily API를 호출하여 웹 검색을 수행한다.

#### 입력/출력

| 구분 | 필드 | 타입 | 설명 |
|------|------|------|------|
| 입력 | messages | list[AnyMessage] | 사용자 채팅 입력 (마지막 메시지에서 토픽 추출) |
| 출력 | topic | str | 추출된 검색 토픽 |
| 출력 | search_results | list[dict] | 검색 결과 리스트 |

#### 동작 규칙
- `state["messages"][-1].content`에서 토픽 문자열을 추출한다.
- TavilySearch를 `max_results=5`, `topic="general"`, `include_raw_content=False`로 호출한다.
- 검색 결과의 각 항목은 `title`, `url`, `content` 필드를 포함한다.
- 검색 결과가 없으면 빈 리스트를 반환한다.

#### 외부 의존성
- **Tavily API** (`TAVILY_API_KEY` 필수)
- **패키지:** `langchain-tavily`

#### 테스트 커버리지
- `TestWebSearchNode::test_reads_topic_from_messages_and_writes_search_results`
- `TestWebSearchNode::test_returns_dict`

---

### F-2. 구조화된 요약 생성

**구현체:** `SummarizeNode` (`casts/orchestrator/modules/nodes.py`)

#### 설명
웹 검색 결과를 Google Gemini 모델로 구조화된 한국어 요약을 생성한다.

#### 입력/출력

| 구분 | 필드 | 타입 | 설명 |
|------|------|------|------|
| 입력 | topic | str | 검색 토픽 |
| 입력 | search_results | list[dict] | 웹 검색 결과 |
| 출력 | summary | str | 구조화된 요약 (PII 필터링 적용) |
| 출력 | messages | list[AnyMessage] | HumanMessage + AIMessage |

#### 요약 출력 형식
```
## 한줄 요약
[핵심 발견 사항 한 문장]

## 핵심 포인트
- [포인트 1~5]

## 키워드
[키워드 5개, 쉼표 구분]

## 상세 요약
[2~3 문단]
```

#### 동작 규칙
- 검색 결과를 `[번호] 제목\nURL: url\n내용` 형식으로 포맷팅한다.
- `SUMMARIZE_PROMPT` (SystemMessage) + 포맷팅된 검색 결과 (HumanMessage)를 Gemini에 전달한다.
- 응답 content에 `apply_pii_filter()`를 적용하여 PII를 마스킹한다.
- 빈 검색 결과도 처리 가능하다 (LLM이 정보 부족을 명시).

#### 외부 의존성
- **Google Gemini** (`GOOGLE_API_KEY` 필수)
- **모델:** gemini-2.0-flash
- **패키지:** `langchain-google-genai`

#### 테스트 커버리지
- `TestSummarizeNode::test_reads_topic_and_search_results`
- `TestSummarizeNode::test_writes_messages_list`
- `TestSummarizeNode::test_formats_results_correctly`
- `TestSummarizeNode::test_handles_empty_search_results`
- `TestSummarizeNode::test_applies_pii_filter_to_summary`
- `TestSummarizeNode::test_model_receives_system_and_user_messages`

---

### F-3. PII 자동 마스킹

**구현체:** `apply_pii_filter()` (`casts/orchestrator/modules/middlewares.py`)

#### 설명
텍스트에서 개인식별정보(PII)를 정규식으로 탐지하고 마스킹 문자열로 교체한다.

#### 지원 PII 유형

| 유형 | 정규식 패턴 | 마스킹 결과 | 예시 |
|------|------------|------------|------|
| 카드번호 | `\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}` | `[CARD_REDACTED]` | 1234-5678-9012-3456 |
| 이메일 | `[\w.-]+@[\w.-]+\.\w+` | `[EMAIL_REDACTED]` | user@example.com |
| 전화번호 | `\d{2,3}-\d{3,4}-\d{4}` | `[PHONE_REDACTED]` | 010-1234-5678 |

#### 동작 규칙
- **적용 순서**: 카드 → 이메일 → 전화 (더 구체적인 패턴을 먼저 적용하여 충돌 방지)
- `pii_types` 파라미터로 특정 유형만 선택적으로 필터링 가능
- PII가 없는 텍스트는 변경 없이 반환

#### 적용 지점
- `SummarizeNode.execute()` → LLM 응답의 `summary` 필드에 적용

#### 인터페이스
```python
apply_pii_filter(text: str, pii_types: list[str] | None = None) -> str
```

#### 테스트 커버리지
- `TestApplyPiiFilter::test_filters_email`
- `TestApplyPiiFilter::test_filters_phone`
- `TestApplyPiiFilter::test_filters_card`
- `TestApplyPiiFilter::test_filters_all_types`
- `TestApplyPiiFilter::test_filters_specific_type_only`
- `TestApplyPiiFilter::test_no_pii_returns_unchanged`
- `TestApplyPiiFilter::test_card_before_phone_avoids_collision`

---

### F-4. 사용자 승인/거부 (Human-in-the-Loop)

**구현체:** `HumanApprovalNode` (`casts/orchestrator/modules/nodes.py`)

#### 설명
요약 결과를 사용자에게 표시하고, 이메일 발송 승인 또는 거부를 결정받는다. LangGraph의 `interrupt()` 메커니즘으로 그래프 실행을 일시 중지한다.

#### 입력/출력

| 구분 | 필드 | 타입 | 설명 |
|------|------|------|------|
| 입력 | summary | str | 구조화된 요약 결과 |
| 출력 | recipient_email | str | 수신자 이메일 (거부 시 빈 문자열) |
| 출력 | is_approved | bool | 승인 여부 |

#### interrupt 페이로드
```json
{
  "summary": "요약 내용...",
  "instruction": "요약 결과를 확인해주세요.\n승인하려면 수신자 이메일을 입력하세요.\n거부하려면 'reject'를 입력하세요."
}
```

#### 사용자 응답 처리

| 입력 | 해석 | is_approved | recipient_email |
|------|------|-------------|-----------------|
| `user@example.com` | 승인 | `True` | `user@example.com` |
| `reject` | 거부 | `False` | `""` |
| `REJECT` | 거부 (대소문자 무관) | `False` | `""` |
| `  reject  ` | 거부 (공백 무시) | `False` | `""` |

#### 후속 분기
- `is_approved == True` → `EmailSendNode`로 진행
- `is_approved == False` → `END`로 종료 (이메일 발송 안 함)

#### 테스트 커버리지
- `TestHumanApprovalNode::test_approve_with_email`
- `TestHumanApprovalNode::test_reject`
- `TestHumanApprovalNode::test_reject_case_insensitive`
- `TestHumanApprovalNode::test_reject_with_whitespace`
- `TestHumanApprovalNode::test_interrupt_payload_contains_summary`

---

### F-5. 이메일 발송

**구현체:** `EmailSendNode` (`casts/orchestrator/modules/nodes.py`)

#### 설명
Resend API를 사용하여 지정된 수신자에게 요약 이메일을 발송한다. `is_approved` 조건부 엣지가 `"approved"`를 반환할 때만 도달한다.

#### 입력/출력

| 구분 | 필드 | 타입 | 설명 |
|------|------|------|------|
| 입력 | topic | str | 이메일 제목에 사용 |
| 입력 | summary | str | 이메일 본문 |
| 입력 | recipient_email | str | 수신자 이메일 |
| 출력 | email_sent | bool | 발송 성공 여부 |

#### 이메일 형식

| 항목 | 값 |
|------|-----|
| 발신자 | `RESEND_FROM_EMAIL` 환경변수 (기본값: `onboarding@resend.dev`) |
| 수신자 | `recipient_email` (단일) |
| 제목 | `[Summary] {topic}` |
| 본문 | `<h2>{topic} - 요약 리포트</h2><hr>{summary_html}` |
| 형식 | HTML (`\n` → `<br>` 변환) |

#### 에러 처리
- 발송 성공: `{"email_sent": True}`
- 발송 실패 (모든 Exception): `{"email_sent": False}` (예외를 catch하여 그래프 중단 방지)

#### 외부 의존성
- **Resend API** (`RESEND_API_KEY` 필수)
- **패키지:** `resend`

#### 테스트 커버리지
- `TestEmailSendNode::test_sends_email_successfully`
- `TestEmailSendNode::test_handles_send_failure`
- `TestEmailSendNode::test_uses_custom_from_email`
- `TestEmailSendNode::test_summary_html_conversion`

---

### F-6. 대화 이력 자동 요약

**구현체:** `ConversationSummaryNode` (`casts/orchestrator/modules/nodes.py`)

#### 설명
대화 이력이 `MESSAGE_THRESHOLD` (6개)를 초과하면, 기존 메시지를 LLM으로 요약하여 토큰 사용량을 최적화한다.

#### 입력/출력

| 구분 | 필드 | 타입 | 설명 |
|------|------|------|------|
| 입력 | messages | list[AnyMessage] | 전체 대화 이력 |
| 출력 | messages | list[AnyMessage] | RemoveMessage + SystemMessage (교체) |

#### 동작 규칙
- 모든 메시지의 `type: content` 형태로 대화 텍스트를 구성한다.
- `CONVERSATION_SUMMARY_PROMPT`를 사용하여 Gemini에 요약을 요청한다.
- 마지막 1개 메시지를 제외한 모든 이전 메시지에 대해 `RemoveMessage(id=m.id)`를 생성한다.
- `[이전 대화 요약]` 프리픽스가 포함된 `SystemMessage`를 추가한다.
- `add_messages` 리듀서가 RemoveMessage → 삭제, SystemMessage → 추가를 처리한다.

#### 트리거 조건
- `should_summarize_conversation` 조건부 엣지가 `len(messages) > 6` 일 때 `"needs_summary"` 반환

#### 테스트 커버리지
- `TestConversationSummaryNode::test_summarizes_messages`
- `TestConversationSummaryNode::test_removes_old_messages`
- `TestConversationSummaryNode::test_summary_contains_context_marker`

---

### F-7. 조건부 분기: 대화 요약 필요 여부

**구현체:** `should_summarize_conversation()` (`casts/orchestrator/modules/conditions.py`)

#### 설명
SummarizeNode 이후, 대화 이력의 길이를 확인하여 ConversationSummaryNode 경유 여부를 결정한다.

#### 분기 로직

| 조건 | 반환값 | 다음 노드 |
|------|--------|----------|
| `len(messages) > MESSAGE_THRESHOLD` (6) | `"needs_summary"` | ConversationSummaryNode |
| `len(messages) <= MESSAGE_THRESHOLD` | `"skip_summary"` | HumanApprovalNode |
| messages가 비어있거나 없음 | `"skip_summary"` | HumanApprovalNode |

#### 설정값
- `MESSAGE_THRESHOLD = 6` (middlewares.py에 정의)

#### 테스트 커버리지
- `TestShouldSummarizeConversation::test_skip_when_below_threshold`
- `TestShouldSummarizeConversation::test_needs_summary_when_above_threshold`
- `TestShouldSummarizeConversation::test_skip_when_empty`

---

### F-8. 조건부 분기: 승인 라우팅

**구현체:** `is_approved()` (`casts/orchestrator/modules/conditions.py`)

#### 설명
HumanApprovalNode 이후, 사용자의 승인/거부 결정에 따라 EmailSendNode 또는 END로 분기한다.

#### 분기 로직

| 조건 | 반환값 | 다음 노드 |
|------|--------|----------|
| `state["is_approved"] == True` | `"approved"` | EmailSendNode |
| `state["is_approved"] == False` | `"rejected"` | END |
| `is_approved` 필드 없음 | `"rejected"` | END |

#### 테스트 커버리지
- `TestIsApproved::test_approved_when_true`
- `TestIsApproved::test_rejected_when_false`
- `TestIsApproved::test_rejected_when_missing`

---

### F-9. Agent Middleware 팩토리

**구현체:** `get_pii_middleware()`, `get_hitl_middleware()`, `get_summarization_middleware()` (`casts/orchestrator/modules/middlewares.py`)

#### 설명
LangChain `create_agent()`와 함께 사용할 수 있는 미들웨어 인스턴스를 생성하는 팩토리 함수들. 현재 워크플로우에서는 standalone helper 방식을 사용하며, 이 팩토리들은 향후 에이전트 패턴 전환 시 활용된다.

#### 팩토리 목록

| 함수 | 반환 타입 | 용도 |
|------|----------|------|
| `get_pii_middleware()` | `list[PIIMiddleware]` | 이메일/카드번호 PII 탐지 및 마스킹 |
| `get_hitl_middleware()` | `HumanInTheLoopMiddleware` | `send_email` 도구 실행 전 승인 요청 |
| `get_summarization_middleware()` | `SummarizationMiddleware` | 메시지 6개 초과 시 자동 요약 |

#### 사용 예시 (에이전트 패턴)
```python
from langchain.agents import create_agent
from .middlewares import get_hitl_middleware, get_pii_middleware

agent = create_agent(
    model=get_gemini_model(),
    tools=[send_email_tool],
    middleware=[get_hitl_middleware(), *get_pii_middleware()],
)
```

---

## 3. 워크플로우 시나리오

### 시나리오 A: 정상 흐름 (승인)

```
1. 사용자 → "AI 에이전트 최신 동향" 입력
2. WebSearchNode → Tavily 검색 (5개 결과)
3. SummarizeNode → Gemini 요약 + PII 마스킹
4. should_summarize_conversation → "skip_summary" (첫 실행, 메시지 적음)
5. HumanApprovalNode → interrupt (요약 표시)
6. 사용자 → "user@example.com" 입력 (승인)
7. is_approved → "approved"
8. EmailSendNode → Resend API 이메일 발송
9. 출력: {summary: "...", email_sent: true}
```

### 시나리오 B: 거부 흐름

```
1~5. (시나리오 A와 동일)
6. 사용자 → "reject" 입력 (거부)
7. is_approved → "rejected"
8. END (이메일 발송 없이 종료)
9. 출력: {summary: "...", email_sent 없음}
```

### 시나리오 C: 대화 요약 트리거

```
1~3. (시나리오 A와 동일, 단 이전 대화가 6개 초과)
4. should_summarize_conversation → "needs_summary"
5. ConversationSummaryNode → 이전 메시지 요약 + 교체
6. HumanApprovalNode → interrupt
7~9. (시나리오 A 또는 B와 동일)
```

### 시나리오 D: 이메일 발송 실패

```
1~7. (시나리오 A와 동일)
8. EmailSendNode → Resend API 호출 실패 (Exception)
9. 출력: {summary: "...", email_sent: false}
```

---

## 4. 설정값 참조

| 설정 | 값 | 위치 | 설명 |
|------|-----|------|------|
| 검색 결과 수 | 5 | nodes.py (TavilySearch) | 최대 검색 결과 수 |
| 검색 토픽 | "general" | nodes.py (TavilySearch) | 검색 카테고리 |
| LLM 모델 | gemini-2.0-flash | models.py | 요약 및 대화 요약용 |
| 메시지 임계값 | 6 | middlewares.py (MESSAGE_THRESHOLD) | 대화 요약 트리거 기준 |
| 기본 발신 이메일 | onboarding@resend.dev | nodes.py (EmailSendNode) | RESEND_FROM_EMAIL 미설정 시 |

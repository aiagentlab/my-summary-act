#  **3주차: 미들웨어와 제어 흐름 (Middleware & Control Flow)**

## **목표:**

Act Operator의 강점인 미들웨어 시스템을 적용하여 에이전트의 안정성과 제어권을 확보합니다.

## **핵심 학습 내용:**

◦ **미들웨어(Middleware) 적용:** 

  LangChain v1의 핵심 기능인 미들웨어를 통해 **Human-in-the-loop(승인 절차)**, **Summarization(대화 요약)**, **PII(개인정보 보호)** 기능을 **middlewares.py**에 구현.

◦ **LangGraph 제어 흐름:** 

  **conditions.py**를 활용한 **조건부 분기(Conditional Edge)** 및 **체크포인터(Checkpointer)**를 통한 상태 저장(Persistence) 구현.

◦ **복합 패턴:** 

  AI에게 developing-cast 스킬을 통해 특정 도구 실행 전 "사용자 승인"을 받도록 로직 수정 요청.

## **실습 과제:** 
이메일 전송 전 사용자 승인을 요청하는 HumanInTheLoopMiddleware를 적용하고, 대화가 길어질 경우 자동으로 요약하는 로직 추가하기.
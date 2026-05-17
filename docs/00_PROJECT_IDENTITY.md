# 00. Project Identity

## 1. 정체성

본 프로젝트는 특정 보안 도구가 아니라, 여러 도메인에 적용 가능한 관계-판단-수치 기반 AI Agentic RAG 프레임워크다.

기존 RAG는 보통 문서를 쪼개고, 임베딩하고, 유사 문서를 검색해 LLM 답변을 보강한다.

```text
Document → Chunk → Embedding → Vector Search → LLM Answer
```

본 프레임워크는 그보다 앞단의 판단 구조를 다룬다.

```text
Data → Relation → Rule-based Judgment → Numeric Score → Action → Memory
```

## 2. 핵심 질문

프레임워크가 다루는 질문은 다음과 같다.

```text
이 데이터는 어떤 대상과 연결되는가?
이 연결은 기존 관계를 확장하는가?
확장은 어떤 규칙 때문에 발생했는가?
판단에 부족한 증거는 무엇인가?
어떤 행동이 다음에 필요한가?
이 흐름은 장기 기억으로 저장할 가치가 있는가?
```

## 3. 적용 도메인

Core는 도메인 중립이어야 한다.

```text
Security Adapter      → Asset / Service / Evidence / Risk Signal
Education Adapter     → Student / Concept / Exercise / Weakness
Research Adapter      → Paper / Claim / Method / Limitation
Business Adapter      → Customer / Event / Need / Proposal
Operation Adapter     → System / Event / State / Action
```

도메인이 바뀌어도 Core는 바뀌지 않는다. Adapter만 바뀐다.

## 4. 한 줄 정의

```text
관계-판단-수치 기반 지능형 RAG 프레임워크는
데이터가 왜 확장되었고, 얼마나 믿을 수 있으며,
다음 행동과 장기 기억으로 어떻게 이어질지를 계산하는
범용 AI Agent 판단 프레임워크다.
```

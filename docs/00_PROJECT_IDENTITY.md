# 00. Project Identity

## 0. Origin

본 프로젝트는 그린필드 프레임워크가 아니다.

켈베로스(Cerberus) 보안 진단 프로젝트에서 진행한 evidence-centric 수집, 도구 결과 정규화, Claim / Gap / Action 사고, RAG 운영 철학, 수치 기반 판단 구조를 보안 도메인 밖으로 추상화하기 위해 분리되었다.

```text
Cerberus
 └─ 보안 도메인에서 발생한 실제 문제
    ├─ 도구 결과가 많아짐
    ├─ 같은 사실을 가리키는 증거 연결 필요
    ├─ 판단에 필요한 근거 부족 계산 필요
    ├─ 다음 점검 행동 선택 필요
    └─ 로컬 RAG/LLM 기반 설명 필요

Intelligent RAG Framework
 └─ 위 구조를 범용화
    ├─ Observation / Evidence / Claim / Gap
    └─ Rule / Score / Action / Feedback
```

켈베로스와의 관계는 다음과 같이 고정한다.

```text
켈베로스 내부 모듈              ❌
켈베로스에서 추출한 범용 판단 엔진   ✅
켈베로스는 첫 번째 도메인 어댑터    ✅
프레임워크는 켈베로스에 종속되지 않음 ✅
```

### 용어 충돌 방지 규칙

```text
Framework Core 용어는 도메인 독립 개념으로 정의한다.
Cerberus 용어는 보안 도메인 어댑터에서 확장한다.
같은 이름을 사용할 경우 Framework Core 정의를 우선하고,
Cerberus는 domain-specific field 또는 adapter layer에서 보강한다.
```

예시:

```text
Framework Evidence
= 어떤 판단을 뒷받침하는 정규화된 근거 단위

Cerberus Evidence
= 보안 도구, 로그, 배너, API, 취약점 DB에서 나온 보안 근거 단위
```

---

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

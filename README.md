# Intelligent RAG Framework

관계-판단-수치 기반 범용 AI Agentic RAG 프레임워크.

이 프로젝트는 켈베로스 보안 도구 자체가 아니다. 보안은 하나의 적용 도메인일 뿐이며, 본 프로젝트의 중심은 데이터가 들어왔을 때 다음을 계산하는 범용 판단 Core다.

```text
새 데이터는 무엇과 연결되는가?
그 연결은 어떤 규칙 때문에 생겼는가?
현재 판단에 부족한 Gap은 무엇인가?
그 판단은 얼마나 신뢰할 수 있는가?
다음 행동은 무엇이어야 하는가?
이 흐름은 장기 기억/RAG에 저장할 가치가 있는가?
```

## Project Boundary

```text
C Core
- Entity / Observation / Claim / Evidence / Relation
- Rule Expansion
- Gap Calculation
- Numeric Scoring
- Action Candidate Ranking
- Memory Eligibility Gate

Python Layer
- 원본 데이터 파싱
- 도메인 Adapter
- RAG / Vector DB / Graph DB 연결
- LLM 호출
- 실험 및 시각화
```

## Minimal MVP

초기 구현은 RAG나 LLM부터 붙이지 않는다.

```text
Raw Input
→ Observation
→ Claim
→ Evidence
→ Rule Expansion
→ Gap
→ Score
→ Action Candidate
→ Memory Eligibility
```

MVP의 성공 조건은 세 가지다.

```text
1. 관계가 만들어진다.
2. 왜 만들어졌는지 rule_id / reason_code가 남는다.
3. 신뢰도와 우선순위가 수치로 계산된다.
```

## Documentation Map

```text
docs/00_PROJECT_IDENTITY.md
docs/01_CORE_PHILOSOPHY.md
docs/02_LAYER_MODEL.md
docs/03_RUNTIME_LOOP.md
docs/contracts/04_C_CORE_BOUNDARY.md
docs/contracts/05_DATA_CONTRACT_MVP.md
docs/contracts/06_MEMORY_RAG_GATE.md
docs/roadmap/07_IMPLEMENTATION_ROADMAP.md
docs/agent/08_CLAUDE_IMPLEMENTATION_BRIEF.md
docs/archive/ORIGINAL_NOTE.md
```

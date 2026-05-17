# 01. Core Philosophy

## 1. 저장보다 확장 이유가 중요하다

본 프레임워크는 데이터를 많이 저장하는 시스템이 아니다.

중요한 것은 다음이다.

```text
무엇을 저장했는가?
```

보다,

```text
어떤 근거와 규칙 때문에 이 데이터가 다음 판단 데이터로 확장되었는가?
```

이다.

## 2. Core의 역할

Core는 LLM처럼 자유롭게 생각하지 않는다. Core는 상태 계산 엔진이다.

```text
ID 연결
규칙 검사
Gap 생성
점수 계산
상태 갱신
Memory 후보 판정
```

Core가 해야 할 일은 명확한 계약 기반 계산이다.

## 3. 원본과 판단의 분리

데이터는 네 층으로 분리한다.

```text
1. Raw Data
   원본 텍스트, 로그, 문서, API 응답

2. Canonical Data
   정규화된 Observation, Claim, Evidence

3. Decision Data
   rule_id, reason_code, gap_type, action_reason

4. Numeric Data
   confidence, priority, evidence_strength, memory_value
```

C Core는 2~4번을 직접 다룬다. Raw Data는 외부 저장소에 두고 Core에는 raw_ref_id만 둔다.

## 4. 구현 원칙

```text
원본은 크게 저장하지 않는다.
판단에 필요한 최소 상태만 남긴다.
관계는 ID로 연결한다.
판단 이유는 코드화한다.
수치 의미값은 float 0.0~1.0으로 계산하고, 저장/직렬화 단계에서만 정수 스케일로 압축한다.
재계산 가능한 값은 저장하지 않는다.
```

## 5. 금지 원칙

초기 MVP에서 금지할 것.

```text
LLM 직접 연결 금지
RAG 직접 연결 금지
도메인 특화 로직 삽입 금지
긴 자연어를 C 구조체에 저장 금지
JSON 파서를 C Core에 직접 내장 금지
```

먼저 관계-판단-수치 루프만 닫는다.

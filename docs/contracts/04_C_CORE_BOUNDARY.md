# 04. C Core Boundary Contract

## 0. Status

이 문서는 **목표 C 경계 계약**을 정의한다.

초기 MVP는 Python Reference Core로 구현하며, 이 문서의 모든 구조와 API는 Python 구현이 따라야 할 **이식 목표 계약**으로 작동한다.

C 구현은 다음 조건이 모두 충족된 뒤에만 시작한다.

```text
1. Evidence / Claim / Gap 구조가 안정화됨
2. 룰 firing 계약이 안정화됨
3. 최소 도메인 시나리오 1개가 끝까지 동작
4. profiler로 병목 구간 확인됨
5. Python 구현이 테스트 기준선 역할 수행
```

이 문서에서 "C Core"라고 표기된 부분은 **현 시점에서는 Python Reference Core가 같은 책임을 진다**고 읽어야 한다.

---

## 1. C Core가 담당하는 것

```text
Entity / Observation / Claim / Evidence ID 관리
Relation 저장
Rule Engine
Gap 계산
Score 계산
Memory Eligibility 판단
Action Candidate 우선순위 정렬
```

## 2. C Core가 담당하지 않는 것

```text
긴 자연어 설명 생성
LLM 프롬프트 구성
RAG 문서 생성
Vector DB 연결
Graph DB 연결
JSON/API 파싱 실험
UI / Web Server
도메인별 파서
```

## 3. 언어 경계

```text
Python Layer
- Raw Data 파싱
- Domain Adapter
- Storage Adapter
- RAG / LLM 연결
- 실험 코드

C Core
- 관계/판단/수치 계산
- 상태 전이
- 최소 메모리 구조

Python Binding
- ctypes 또는 cffi
- C Core API 호출
```

## 4. Opaque Pointer 원칙

Python은 C 내부 구조체를 직접 만지지 않는다.

```c
typedef struct Engine Engine;

Engine* engine_create(void);
void engine_free(Engine* e);
```

Python은 Engine*를 핸들로만 사용한다.

## 5. 메모리 원칙

```text
문자열 직접 저장 금지
관계는 포인터가 아니라 ID로 연결
수치 의미값은 float 0.0~1.0, 저장 / hot loop에서만 uint16 0~10000으로 패킹
원본 데이터는 raw_ref_id로만 참조
batch API를 추후 도입
```

## 6. 초기 빌드 형태

```text
Linux/macOS: libragcore.so
Windows: ragcore.dll
Python: ctypes wrapper
```

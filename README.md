# Intelligent RAG Framework

관계-판단-수치 기반 범용 AI Agentic RAG 프레임워크.

## Origin

본 프레임워크는 켈베로스(Cerberus) 보안 진단 프로젝트에서 축적한 evidence-centric 판단 구조를 범용화하기 위해 분리된 프로젝트다. 켈베로스는 첫 번째 도메인 적용 사례이며, 본 프레임워크는 보안 도메인에 종속되지 않는 관계-판단-수치 기반 RAG 엔진을 목표로 한다.

```text
Cerberus  = 첫 번째 실전 도메인 어댑터
Framework = 켈베로스에서 추출된 범용 판단 엔진
```

자세한 출처와 용어 충돌 방지 규칙은 [docs/00_PROJECT_IDENTITY.md](docs/00_PROJECT_IDENTITY.md) 참고.

## What

이 프로젝트는 켈베로스 보안 도구 자체가 아니다. 보안은 하나의 적용 도메인일 뿐이며, 본 프로젝트의 중심은 데이터가 들어왔을 때 다음을 계산하는 범용 판단 Core다.

```text
새 데이터는 무엇과 연결되는가?
그 연결은 어떤 규칙 때문에 생겼는가?
현재 판단에 부족한 Gap은 무엇인가?
그 판단은 얼마나 신뢰할 수 있는가?
다음 행동은 무엇이어야 하는가?
이 흐름은 장기 기억/RAG에 저장할 가치가 있는가?
```

## Project Status

```text
Version:                 0.1.0
Package import name:     ragcore
Method surface:          frozen (PR36-PKG §48)
Algorithm / mathematics: allowed to evolve (PR36-PKG §48.3)
Integration readiness:   audited in §49 (D-mid completion in progress)
```

핵심 원칙:

```text
Freeze method surface, not judgment mathematics.
Algorithm can evolve. Integration boundary must be complete.
```

이 프로젝트는 production 보안 도구가 아니다. 외부 consumer (켈베로스 포함) 가 method surface 에 의존해도 되도록 잠겨 있으며, 내부 알고리즘 / modifier 수치 / threshold 정책은 향후 실사용 피드백에 따라 진화할 수 있다.

자세한 잠금 규칙은 `docs/contracts/05_DATA_CONTRACT_MVP.md` 의 §48 (method surface freeze) 과 §49 (integration readiness boundary) 참고.

## Quickstart

### Minimal usage

```python
from ragcore import Engine, ScoreValue

engine = Engine()

# 1. 주체(Entity) 생성
entity_id = engine.add_entity(entity_type=1)

# 2. Claim 추가 (rule_id=0 — 룰 미사용 경로)
claim_id = engine.add_claim(
    subject_id=entity_id,
    claim_type=1,
    rule_id=0,
    rule_version=0,
    reason_code=1,
    base_confidence=0.8,
)

# 3. 종합 신뢰도 계산
score = engine.compute_effective_confidence(claim_id)
print(score.value)  # ScoreValue 객체의 value 속성

# 4. lifecycle 이력 조회
history = engine.claim_lifecycle_history(claim_id)

# 5. 상태 저장 (snapshot 은 JSON-compatible dict)
snapshot = engine.to_snapshot()

# 6. 복원
restored = Engine.from_snapshot(snapshot)
```

### 다음 단계

- 6 canonical usage recipes (candidate confirmation / disputed review / refutation / snapshot restore / observed_precision feedback / hint evidence type cycle) → `docs/contracts/05_DATA_CONTRACT_MVP.md` §43
- 6 canonical report shapes (claim_summary / effective_breakdown / lifecycle / evidence_contradiction / rule_pinning / snapshot_metadata) → `docs/contracts/05_DATA_CONTRACT_MVP.md` §44

## Persistence Boundary

Framework 는 파일 IO / DB IO / 외부 네트워크 호출을 수행하지 않는다.

```python
import json
from ragcore import Engine

engine = Engine()

# Engine 은 dict 를 반환할 뿐, 어디에 저장할지는 consumer 가 결정한다.
snapshot_dict = engine.to_snapshot()

# 예 1: JSON 파일로 저장 (consumer 책임)
with open("engine_state.json", "w") as f:
    json.dump(snapshot_dict, f)

# 예 2: 다시 로드 (consumer 책임)
with open("engine_state.json") as f:
    restored_dict = json.load(f)

restored = Engine.from_snapshot(restored_dict)
```

**저장 책임 분리** (§39.4 / §42.6 / §44.8):

```text
Framework 책임:
- to_snapshot() 이 JSON-compatible dict 를 반환한다
- from_snapshot(dict) 이 동일한 Engine 상태를 복원한다
- schema_version 이 명시되어 있어 migration framework 가 작동한다

Consumer 책임:
- 저장 매체 선택 (JSON 파일 / SQLite / S3 / RDB ...)
- 저장 시점 / 빈도 결정
- 동시성 제어 / 잠금
- 백업 / 보존 정책
```

Framework 는 dict 만 만든다. 그 dict 를 어디에 저장할지는 consumer 가 결정한다.

## Stability & Evolvability

### Stable forever (consumer 가 의존해도 되는 영역)

```text
- from ragcore import Engine
- Engine public method names / signatures / return shapes
- snapshot to_snapshot / from_snapshot 입출력 형식
- snapshot top-level 18 keys + schema_version
- 6 canonical report shapes (§44 frozensets)
- modifier helper signatures (PR34-O 6 helpers, claim_id-based)
- serialize / restore helper symmetry (PR35-O7 6×6)
- package import surface (side-effect free)
```

### Allowed to evolve (Engine 업데이트 영역)

```text
- modifier strength / composition / threshold policy
- contradiction / freshness / gap / RuleStats / evidence_type 해석
- effective confidence calibration
- false positive / false negative 대응 (consumer 실사용 피드백 반영)
- 새 modifier 추가 (additive)
```

### Breaking change 규칙 (§48.5)

method 이름 변경 / 제거 / signature 변경 / snapshot key 제거 / report key 제거 는 explicit "method surface migration" PR + deprecation cycle 필수. 알고리즘 정책 변경은 새 § 섹션 (§50+) 으로 documented judgment policy update.

## Project Boundary

```text
Core Contract
- Entity / Observation / Claim / Evidence / Relation
- Rule Expansion
- Gap Calculation
- Numeric Scoring
- Action Candidate Ranking
- Memory Eligibility Gate

Python Reference Core
- MVP 판단 루프 구현
- 룰 계약 검증
- 테스트 기준선 제공
- 도메인 Adapter 실험

Future Native Core
- 검증된 hot loop만 C/Rust로 이식
- score packing / bulk matching / rule firing 최적화
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

### Project foundation

```text
docs/00_PROJECT_IDENTITY.md          프로젝트 origin + 켈베로스 관계 (도메인 분리)
docs/01_CORE_PHILOSOPHY.md           evidence-centered 설계 철학
docs/02_LAYER_MODEL.md               3-계층 모델 (relation / intelligence / numeric)
docs/03_RUNTIME_LOOP.md              판단 루프
docs/09_GIT_WORKFLOW.md              contributor workflow
```

### Consumer contracts (`docs/contracts/`)

```text
04_C_CORE_BOUNDARY.md                future C/Rust boundary
05_DATA_CONTRACT_MVP.md              §17~§49 — 모든 boundary 명문화 (중심 문서)
06_MEMORY_RAG_GATE.md                memory eligibility gate
```

### Consumer entry points (§-references inside 05_DATA_CONTRACT_MVP.md)

```text
§39  External call boundary           how to call the Engine
§42  Consumer policy guides           how to interpret outputs
§43  AI-readable usage recipes         6 canonical scenarios (confirm / dispute /
                                       refute / snapshot / precision / hint)
§44  Report surface                    6 canonical report shapes (frozensets)
§48  Method surface freeze            method names / shapes locked
§49  Integration readiness boundary    "algorithm evolves, integration stable"
```

이 6개 § 섹션이 외부 consumer (켈베로스 / AI 에이전트 / report generator 등) 가 framework 를 사용하기 위해 읽어야 할 핵심 entry point.

### Per-PR implementation records (`docs/dev/`)

```text
PR_001 ~ PR_037                       각 PR cycle 별 implementation 기록
```

### Other

```text
docs/agent/08_CLAUDE_IMPLEMENTATION_BRIEF.md  implementer 가이드 (consumer 용 아님)
docs/archive/ORIGINAL_NOTE.md                  historical note
```

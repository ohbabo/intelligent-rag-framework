# Intelligent RAG Framework

관계-판단-수치 기반 범용 AI Agentic RAG 프레임워크.

## Core Thesis

```text
The truth unit is evidence, not the tool.
LLM is a reader and proposer, not the judge.
RAG is an operational knowledge layer, not just vector search.
```

이 프로젝트는 "문서를 검색해서 LLM 답변을 보강하는 RAG"에 머물지 않는다.

목표는 도구 출력, API 신호, 로그, 문서, 사람의 판단 기록을 모두 **검증 가능한 evidence 단위**로 정규화하고, 그 evidence가 어떤 claim을 지지하거나 반박하는지, 무엇이 아직 부족한지, 다음에 무엇을 확인해야 하는지를 계산하는 것이다.

```text
Raw output / API signal / document / log
→ Canonical evidence
→ Claim / Gap / Contradiction
→ Lifecycle state
→ Effective confidence
→ LLM-readable packet
→ Proposal validation
→ Operator gate
```

LLM은 이 흐름에서 최종 판단자가 아니다.

LLM은 Engine이 만든 상태를 읽고, 다음 조사 후보를 제안할 수 있다. 그러나 claim의 truth, lifecycle transition, confidence, execution decision은 evidence, rule, validator, operator gate를 통해 통제된다.

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
현재 판단을 반박하는 Contradiction은 무엇인가?
그 판단은 얼마나 신뢰할 수 있는가?
LLM에게 어떤 상태까지 읽게 할 수 있는가?
LLM 제안은 어떤 검증을 통과해야 하는가?
다음 행동은 무엇이어야 하는가?
이 흐름은 장기 기억/RAG에 저장할 가치가 있는가?
```

## Not a Prompt-only System

이 프로젝트는 긴 프롬프트 하나로 LLM을 설득하는 방식이 아니다.

```text
Prompt only        ❌
Vector search only ❌
LLM-as-judge       ❌
Tool-as-truth      ❌
```

대신 다음 구조를 지향한다.

```text
Engine state
→ Read packet
→ Packet validator
→ LLM context
→ LLM proposal
→ Proposal schema validator
→ Proposal safety validator
→ Operator decision boundary
→ Consumer-owned execution
```

프롬프트는 이 흐름의 한 부품이다. 핵심은 LLM에게 무엇을 보여줄지, 무엇을 말하지 못하게 할지, 어떤 제안을 위험하다고 볼지, 사람이 어디서 승인해야 하는지를 구조로 고정하는 것이다.

## RAG Model

일반적인 RAG 흐름은 다음과 같다.

```text
Document → Chunk → Embedding → Vector Search → LLM Answer
```

본 프레임워크는 이보다 앞단과 뒷단을 함께 다룬다.

```text
Data → Relation → Rule-based Judgment → Numeric Score → Read Packet → Proposal → Gate → Memory
```

Vector store는 사용할 수 있다. 그러나 vector store는 truth source가 아니다.

```text
Vector retrieval = candidate knowledge lookup
Evidence         = normalized support or contradiction unit
Engine state     = current judgment state
LLM              = reader / summarizer / proposer
Operator         = execution authority
```

즉 이 프로젝트에서 RAG는 "LLM의 백과사전"이 아니라, LLM이 현재 상황을 안전하게 읽고 다음 확인 후보를 제안할 수 있도록 만드는 운영 지식층이다.

## Project Status

```text
Version:                 0.1.0   (ragcore; matches pyproject.toml — intentionally not bumped)
Package import name:     ragcore
Engine v1 refactoring:   COMPLETE — Phase 0–4 CLOSED
Verified local suite:    2204 passed  (local only; no CI / GitHub Actions configured)
Engine public methods:   42
ragcore.__all__:         50
Snapshot:                schema_version 2 / 18 top-level keys
PR51 context packet:     7 keys
Final architecture:      thin C1 core + 9 private mixins + 2 pure kernels
Authoritative boundary:  docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md
Engine v2:               NOT STARTED  (separate GPT + user design directive required)
Cerberus integration:    NOT STARTED  (later roadmap item)
```

핵심 원칙:

```text
Freeze the defined external contract, not the judgment mathematics.
The internal structure may be refactored only while preserving the contract and
  judgment meaning (Phase 0–4 did exactly this — 0 contract/semantic change).
The v1 judgment policy (ragcore.effective-confidence.v1) is fixed; changing it
  requires an explicit, versioned migration — not a silent edit.
```

이 프로젝트는 production 보안 도구가 아니다. 외부 consumer (켈베로스 포함) 가 method surface 에 의존해도 되도록 잠겨 있다. 현재 v1 의 modifier 수치 / threshold / composition 정책은 `ragcore.effective-confidence.v1` 으로 고정돼 있으며, 이를 바꾸는 것은 별도 directive 와 versioned boundary 에서 결정한다 (조용한 수정 금지). 내부 구조 리펙토링은 계약·판단 의미를 보존할 때만 허용된다.

자세한 잠금 규칙은 `docs/contracts/05_DATA_CONTRACT_MVP.md` 의 §48 (method surface freeze) 과 §49 (integration readiness boundary) 참고. 현재 구조의 권위 문서는 `docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md`.

## Current Architecture (Engine v1)

Engine v1 리펙토링(Phase 0–4)이 완료되어, `Engine` 은 얇은 C1 core 에 9개 private mixin 을 합성하고 2개 pure kernel 을 module function 으로 분리한 구조다.

```text
ragcore.engine.Engine
  ├─ C1 thin core (Engine 본문 잔류)
  │    __init__ / id 발급 / revision / state_identity / 존재성 guard
  ├─ 9 private mixins (ragcore/_engine/*)
  │    HintEvidence · Relations · Rules · Gaps · ConfidenceAdapters ·
  │    LifecycleHistory · Crud · Lifecycle · Snapshot
  └─ 2 pure kernels (stdlib + ragcore.types 만 import)
       serialization · confidence
```

전체 ownership 표 / import graph / frozen contract / accepted introspection delta 는
`docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md` 가 authoritative 다 (README 에 52-method
ownership 전체 표나 내부 PR chronology 를 중복하지 않는다).

## Design Principles

### 1. Evidence is the truth unit

도구는 truth가 아니다. 도구는 raw output을 만든다.

```text
Nmap output     ≠ truth
LLM summary     ≠ truth
API enrichment  ≠ truth
Parsed evidence = judgment input
```

판단은 도구 이름이 아니라, 정규화된 evidence와 그 evidence가 claim과 맺는 관계를 기준으로 한다.

### 2. Preserve raw output, compute normalized state

Raw output은 삭제하지 않는다.

```text
raw text / JSON / log
→ normalized evidence
→ computed signal
→ score / lifecycle / report
```

나중에 parser나 scoring formula가 바뀌어도, raw output과 normalized evidence가 남아 있으면 재평가할 수 있다.

### 3. LLM reads state, not private engine internals

LLM은 Engine private state를 직접 읽지 않는다.

```text
Engine private state ❌
Public read surface ✅
LLM context packet ✅
```

LLM에게 들어가는 정보는 consumer-side packet으로 정리되어야 하며, forbidden reading은 validator가 차단한다.

### 4. Proposal is not execution

LLM proposal은 실행 명령이 아니다.

```text
validator pass      = reviewable proposal
operator acceptance = consumer gate pass
Engine truth        = unchanged
```

제안이 안전 validator를 통과해도 Engine truth가 되지 않는다. 사람이 승인해도 Engine truth가 되지 않는다. 실행과 truth update는 consumer adapter가 evidence를 다시 넣는 방식으로 분리된다.

### 5. Domain adapter owns domain meaning

Core는 도메인 중립이어야 한다.

```text
Framework Core: Entity / Observation / Claim / Evidence / Gap / Contradiction
Cerberus Adapter: Asset / Service / Port / CVE / Tool output / Risk signal
```

보안 용어는 Cerberus adapter에서 확장한다. Core는 보안 도구에 종속되지 않는다.

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

### May change only through an explicit, versioned judgment-policy update

다음은 진화할 수 있는 영역이지만, 현재 v1 에서는 `ragcore.effective-confidence.v1`
정책으로 **고정**돼 있다. 아래를 바꾸려면 조용한 수정이 아니라 새 § 섹션(§50+) 또는
별도 directive 로 documented + versioned 판단정책 업데이트가 필요하다.

```text
- modifier strength / composition / threshold policy   (현재 v1 고정)
- contradiction / freshness / gap / RuleStats / evidence_type 해석
- effective confidence calibration
- false positive / false negative 대응 (consumer 실사용 피드백 반영)
- 새 modifier 추가 (additive)  — v1 계약을 깨지 않는 방식으로, 명시적 업데이트로만
```

미래 수학모델이나 v2 policy 는 별도 directive 와 versioned boundary 에서 결정한다
(Engine v2 는 아직 NOT STARTED).

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

### Start here (read in order)

```text
1. docs/README.md                                 current navigation / baseline map
2. docs/01_CORE_PHILOSOPHY.md                     evidence-centered design philosophy
3. docs/contracts/05_DATA_CONTRACT_MVP.md         consumer-facing contract (central)
4. docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md  current Engine v1 structural authority
```

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

### Architecture (`docs/architecture/`)

```text
ENGINE_V1_FINAL_BOUNDARY.md           current Engine v1 structural authority
ENGINE_V1_REFACTORING_PLAN.md         completed refactoring plan (+ historical proposal)
ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md  accepted mixin decision (+ historical evidence)
ENGINE_INTERNAL_MAP.md                SUPERSEDED — historical single-class audit
```

### Per-PR implementation / audit records (`docs/dev/`)

```text
docs/dev/                             역사·감사 기록 영역 — PR cycle 별 implementation /
                                       review / post-merge 기록 (계속 증가; 특정 번호
                                       범위로 고정하지 않음). 현재 baseline 의 첫 진입점이
                                       아니라 당시 판단·검수 보존용.
```

### Other

```text
docs/agent/08_CLAUDE_IMPLEMENTATION_BRIEF.md  implementer 가이드 (consumer 용 아님)
docs/archive/ORIGINAL_NOTE.md                  historical note
```

## Current Roadmap

```text
Engine v1 refactoring   COMPLETE   (Phase 0–4 CLOSED)
Engine v2               NOT STARTED — philosophy / math / projection / state-identity /
                                     materialization 은 별도 GPT + user directive 필요
Cerberus integration    NOT STARTED — later roadmap item
```

자동으로 시작되는 다음 구현 PR 은 없다. 어떤 트랙도 명시적 directive 를 기다린다
(이 문서의 갱신이 v2 자동 착수를 의미하지 않는다).

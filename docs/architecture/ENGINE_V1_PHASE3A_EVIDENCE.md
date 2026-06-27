# Engine v1 — Phase 3A persistent evidence (auto-derived, re-checkable)

Companion to `ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md`. Parent-aware AST
over `ragcore/engine.py` (current main). **Operation legend (precise):**
`R` read of contents (subscript-Load `self._s[k]`, reading method, `k in self._s`,
iteration/len/arg) — *not* the write-container load of `self._s[k]=…` or
`self._s.append(…)`; `W` whole-rebind `self._s=…` or subscript replace-existing
(`self._s[k]=…` where the method also subscript-reads `self._s[k]`); `A` insert of
a new key / append/add/extend/setdefault; `D` del / pop/remove/discard/clear;
`M` update/difference_update; `I` revision counter; `ID` id-counter allocation
(`_allocate_id` only). Stores shown without the leading underscore. `__init__`
and the bulk `_install`/`_state_view` restore/encode boundary are listed but
excluded from *operational* mutation-ownership and port totals.

## Per-method sparse table (63 methods)

| method | vis | cluster | reads | mutates (op) | self callees | cross-cluster callees | kind |
|---|---|---|---|---|---|---|---|
| `_advance_state_revision` | priv | C1 | — | state_revision:I | — | — | mutating |
| `_allocate_id` | priv | C1 | next_id | next_id:ID | — | — | mutating |
| `_assert_claim_exists` | priv | C1 | claims | — | — | — | read-only |
| `_assert_entity_exists` | priv | C1 | entities | — | — | — | read-only |
| `_assert_evidence_exists` | priv | C1 | evidences | — | — | — | read-only |
| `_assert_gap_exists` | priv | C1 | gaps | — | — | — | read-only |
| `_assert_rule_pair_exists` | priv | C1 | rule_definitions | — | — | — | read-only |
| `_assert_rule_stats_pair_exists` | priv | C1 | rule_stats | — | — | — | read-only |
| `_id_exists` | priv | C1 | — | — | _storage_for_kind | — | read-only |
| `_storage_for_kind` | priv | C1 | claims entities evidences gaps observations relations | — | — | — | read-only |
| `state_identity` | pub  | C1 | state_identity_token state_revision | — | — | — | read-only |
| `_install` | priv | C10 | — | claim_gap_refs:W claim_lifecycle_events:W claims:W contradictions:W entities:W evidences:W gap_dedup_index:W gap_resolutions:W gaps:W hint_evidence_types:W lifecycle_seq:W next_id:W observations:W relations:W resolved_contradictions:W rule_definitions:W rule_stats:W | — | — | mutating |
| `_state_view` | priv | C10 | claim_gap_refs claim_lifecycle_events claims contradictions entities evidences gap_dedup_index gap_resolutions gaps hint_evidence_types lifecycle_seq next_id observations relations resolved_contradictions rule_definitions rule_stats | — | — | — | read-only |
| `from_snapshot` | pub  | C10 | — | — | — | — | read-only |
| `to_snapshot` | pub  | C10 | — | — | _state_view | — | read-only |
| `add_claim` | pub  | C2 | entities | claims:A | _advance_state_revision _allocate_id | C1:_advance_state_revision C1:_allocate_id | mutating |
| `add_entity` | pub  | C2 | — | entities:A | _advance_state_revision _allocate_id | C1:_advance_state_revision C1:_allocate_id | mutating |
| `add_evidence` | pub  | C2 | — | evidences:A | _advance_state_revision _allocate_id _assert_claim_exists | C1:_advance_state_revision C1:_allocate_id C1:_assert_claim_exists | mutating |
| `add_observation` | pub  | C2 | — | observations:A | _advance_state_revision _allocate_id _assert_entity_exists | C1:_advance_state_revision C1:_allocate_id C1:_assert_entity_exists | mutating |
| `evidences_for_claim` | pub  | C2 | evidences | — | _assert_claim_exists | C1:_assert_claim_exists | read-only |
| `get_claim` | pub  | C2 | claims | — | — | — | read-only |
| `get_entity` | pub  | C2 | entities | — | — | — | read-only |
| `get_evidence` | pub  | C2 | evidences | — | — | — | read-only |
| `get_observation` | pub  | C2 | observations | — | — | — | read-only |
| `add_relation` | pub  | C3 | — | relations:A | _advance_state_revision _allocate_id _id_exists | C1:_advance_state_revision C1:_allocate_id C1:_id_exists | mutating |
| `get_relation` | pub  | C3 | relations | — | — | — | read-only |
| `add_gap` | pub  | C4 | claims gap_dedup_index | claim_gap_refs:A gap_dedup_index:W gaps:A | _advance_state_revision _allocate_id _assert_claim_exists | C1:_advance_state_revision C1:_allocate_id C1:_assert_claim_exists | mutating |
| `gap_resolution` | pub  | C4 | gap_resolutions | — | _assert_gap_exists | C1:_assert_gap_exists | read-only |
| `gaps_for_claim` | pub  | C4 | claim_gap_refs gaps | — | _assert_claim_exists | C1:_assert_claim_exists | read-only |
| `get_gap` | pub  | C4 | gaps | — | — | — | read-only |
| `resolve_gaps_for_evidence` | pub  | C4 | evidences gap_resolutions | gap_resolutions:A | _advance_state_revision _assert_evidence_exists gaps_for_claim | C1:_advance_state_revision C1:_assert_evidence_exists | mutating |
| `active_contradictions_by_freshness` | pub  | C5 | contradictions resolved_contradictions | — | _assert_claim_exists | C1:_assert_claim_exists | read-only |
| `active_contradictions_for_claim` | pub  | C5 | contradictions resolved_contradictions | — | _assert_claim_exists | C1:_assert_claim_exists | read-only |
| `confirm_claim_if_ready` | pub  | C5 | claims | claims:W | _advance_state_revision _assert_claim_exists _record_claim_lifecycle_transition gap_resolution gaps_for_claim | C1:_advance_state_revision C1:_assert_claim_exists C4:gap_resolution C4:gaps_for_claim C6:_record_claim_lifecycle_transition | mutating |
| `contradictions_for_claim` | pub  | C5 | contradictions | — | _assert_claim_exists | C1:_assert_claim_exists | read-only |
| `dispute_claim_if_ready` | pub  | C5 | claims contradictions | claims:W | _advance_state_revision _assert_claim_exists _record_claim_lifecycle_transition | C1:_advance_state_revision C1:_assert_claim_exists C6:_record_claim_lifecycle_transition | mutating |
| `refute_claim_if_ready` | pub  | C5 | claims contradictions | claims:W | _advance_state_revision _assert_claim_exists _record_claim_lifecycle_transition | C1:_advance_state_revision C1:_assert_claim_exists C6:_record_claim_lifecycle_transition | mutating |
| `refute_disputed_claim_if_ready` | pub  | C5 | claims evidences | claims:W | _advance_state_revision _assert_claim_exists _record_claim_lifecycle_transition active_contradictions_for_claim | C1:_advance_state_revision C1:_assert_claim_exists C6:_record_claim_lifecycle_transition | mutating |
| `refute_disputed_claim_if_ready_by_freshness` | pub  | C5 | claims evidences | claims:W | _advance_state_revision _assert_claim_exists _record_claim_lifecycle_transition active_contradictions_by_freshness | C1:_advance_state_revision C1:_assert_claim_exists C6:_record_claim_lifecycle_transition | mutating |
| `register_contradiction` | pub  | C5 | — | contradictions:A | _advance_state_revision _assert_claim_exists _assert_evidence_exists | C1:_advance_state_revision C1:_assert_claim_exists C1:_assert_evidence_exists | mutating |
| `register_contradiction_resolution` | pub  | C5 | contradictions | resolved_contradictions:A | _advance_state_revision _assert_claim_exists _assert_evidence_exists | C1:_advance_state_revision C1:_assert_claim_exists C1:_assert_evidence_exists | mutating |
| `resolve_disputed_claim_if_ready` | pub  | C5 | claims | claims:W | _advance_state_revision _assert_claim_exists _record_claim_lifecycle_transition active_contradictions_for_claim | C1:_advance_state_revision C1:_assert_claim_exists C6:_record_claim_lifecycle_transition | mutating |
| `resolved_contradictions_for_claim` | pub  | C5 | resolved_contradictions | — | _assert_claim_exists | C1:_assert_claim_exists | read-only |
| `_record_claim_lifecycle_transition` | priv | C6 | lifecycle_seq | claim_lifecycle_events:A lifecycle_seq:W | — | — | mutating |
| `claim_lifecycle_history` | pub  | C6 | claim_lifecycle_events | — | _assert_claim_exists | C1:_assert_claim_exists | read-only |
| `get_rule` | pub  | C7 | rule_definitions | — | _assert_rule_pair_exists | C1:_assert_rule_pair_exists | read-only |
| `get_rule_stats` | pub  | C7 | rule_stats | — | _assert_rule_stats_pair_exists | C1:_assert_rule_stats_pair_exists | read-only |
| `register_rule` | pub  | C7 | rule_definitions | rule_definitions:A rule_stats:A | _advance_state_revision | C1:_advance_state_revision | mutating |
| `update_rule_stats` | pub  | C7 | rule_stats | rule_stats:W | _advance_state_revision _assert_rule_stats_pair_exists | C1:_advance_state_revision C1:_assert_rule_stats_pair_exists | mutating |
| `_validate_hint_evidence_type_values` | priv | C8 | — | — | — | — | read-only |
| `clear_hint_evidence_types` | pub  | C8 | hint_evidence_types | hint_evidence_types:D | _advance_state_revision | C1:_advance_state_revision | mutating |
| `register_hint_evidence_types` | pub  | C8 | hint_evidence_types | hint_evidence_types:M | _advance_state_revision _validate_hint_evidence_type_values | C1:_advance_state_revision | mutating |
| `unregister_hint_evidence_types` | pub  | C8 | hint_evidence_types | hint_evidence_types:M | _advance_state_revision _validate_hint_evidence_type_values | C1:_advance_state_revision | mutating |
| `_compute_effective_confidence_core` | priv | C9 | claims | — | _assert_claim_exists _count_modifier_for_claim _evidence_type_modifier_for_claim _freshness_modifier_for_claim _gap_modifier_for_claim _rule_stats_modifier_for_claim _status_modifier_for_claim state_identity | C1:_assert_claim_exists C1:state_identity | read-only |
| `_count_modifier_for_claim` | priv | C9 | evidences | — | active_contradictions_for_claim | C5:active_contradictions_for_claim | read-only |
| `_evidence_type_modifier_for_claim` | priv | C9 | contradictions evidences hint_evidence_types resolved_contradictions | — | — | — | read-only |
| `_freshness_modifier_for_claim` | priv | C9 | evidences | — | active_contradictions_by_freshness | C5:active_contradictions_by_freshness | read-only |
| `_gap_modifier_for_claim` | priv | C9 | claim_gap_refs gap_resolutions | — | — | — | read-only |
| `_rule_stats_modifier_for_claim` | priv | C9 | claims rule_stats | — | — | — | read-only |
| `_status_modifier_for_claim` | priv | C9 | claims | — | — | — | read-only |
| `compute_effective_confidence` | pub  | C9 | — | — | _compute_effective_confidence_core | — | read-only |
| `compute_effective_confidence_with_trace` | pub  | C9 | — | — | _compute_effective_confidence_core | — | read-only |
| `evidence_freshness` | pub  | C9 | — | — | _assert_evidence_exists | C1:_assert_evidence_exists | read-only |

## Derived values (recomputed from the table above)
```
methods analyzed (excl __init__)     63
non-trivial SCCs (self-call graph)   0  -> DAG
revision-authority callers           20 call _advance_state_revision
ID-authority callers                 6 call _allocate_id
cross-cluster call edges:
  C2 -> C1: 11  [shared-infra]   ['add_claim->_advance_state_revision', 'add_claim->_allocate_id', 'add_entity->_advance_state_revision', 'add_entity->_allocate_id', 'add_evidence->_advance_state_revision', 'add_evidence->_allocate_id', 'add_evidence->_assert_claim_exists', 'add_observation->_advance_state_revision', 'add_observation->_allocate_id', 'add_observation->_assert_entity_exists', 'evidences_for_claim->_assert_claim_exists']
  C3 -> C1: 3  [shared-infra]   ['add_relation->_advance_state_revision', 'add_relation->_allocate_id', 'add_relation->_id_exists']
  C4 -> C1: 7  [shared-infra]   ['add_gap->_advance_state_revision', 'add_gap->_allocate_id', 'add_gap->_assert_claim_exists', 'gap_resolution->_assert_gap_exists', 'gaps_for_claim->_assert_claim_exists', 'resolve_gaps_for_evidence->_advance_state_revision', 'resolve_gaps_for_evidence->_assert_evidence_exists']
  C5 -> C1: 22  [shared-infra]   ['active_contradictions_by_freshness->_assert_claim_exists', 'active_contradictions_for_claim->_assert_claim_exists', 'confirm_claim_if_ready->_advance_state_revision', 'confirm_claim_if_ready->_assert_claim_exists', 'contradictions_for_claim->_assert_claim_exists', 'dispute_claim_if_ready->_advance_state_revision', 'dispute_claim_if_ready->_assert_claim_exists', 'refute_claim_if_ready->_advance_state_revision', 'refute_claim_if_ready->_assert_claim_exists', 'refute_disputed_claim_if_ready->_advance_state_revision', 'refute_disputed_claim_if_ready->_assert_claim_exists', 'refute_disputed_claim_if_ready_by_freshness->_advance_state_revision', 'refute_disputed_claim_if_ready_by_freshness->_assert_claim_exists', 'register_contradiction->_advance_state_revision', 'register_contradiction->_assert_claim_exists', 'register_contradiction->_assert_evidence_exists', 'register_contradiction_resolution->_advance_state_revision', 'register_contradiction_resolution->_assert_claim_exists', 'register_contradiction_resolution->_assert_evidence_exists', 'resolve_disputed_claim_if_ready->_advance_state_revision', 'resolve_disputed_claim_if_ready->_assert_claim_exists', 'resolved_contradictions_for_claim->_assert_claim_exists']
  C5 -> C4: 2   ['confirm_claim_if_ready->gap_resolution', 'confirm_claim_if_ready->gaps_for_claim']
  C5 -> C6: 6  [shared-infra]   ['confirm_claim_if_ready->_record_claim_lifecycle_transition', 'dispute_claim_if_ready->_record_claim_lifecycle_transition', 'refute_claim_if_ready->_record_claim_lifecycle_transition', 'refute_disputed_claim_if_ready->_record_claim_lifecycle_transition', 'refute_disputed_claim_if_ready_by_freshness->_record_claim_lifecycle_transition', 'resolve_disputed_claim_if_ready->_record_claim_lifecycle_transition']
  C6 -> C1: 1  [shared-infra]   ['claim_lifecycle_history->_assert_claim_exists']
  C7 -> C1: 5  [shared-infra]   ['get_rule->_assert_rule_pair_exists', 'get_rule_stats->_assert_rule_stats_pair_exists', 'register_rule->_advance_state_revision', 'update_rule_stats->_advance_state_revision', 'update_rule_stats->_assert_rule_stats_pair_exists']
  C8 -> C1: 3  [shared-infra]   ['clear_hint_evidence_types->_advance_state_revision', 'register_hint_evidence_types->_advance_state_revision', 'unregister_hint_evidence_types->_advance_state_revision']
  C9 -> C1: 3  [shared-infra]   ['_compute_effective_confidence_core->_assert_claim_exists', '_compute_effective_confidence_core->state_identity', 'evidence_freshness->_assert_evidence_exists']
  C9 -> C5: 2   ['_count_modifier_for_claim->active_contradictions_for_claim', '_freshness_modifier_for_claim->active_contradictions_by_freshness']
C2<->C5 direct calls                 0  (C2/C5 independent -> separate 3B PRs)
cross-cluster WRITE ownership         stores written by >1 cluster = ['_claims']  (operational; excludes C10 bulk _install)

module-function state-port width (non-infra clusters = all except C1/C6 infra;
excludes C10 _install/_state_view restore/encode boundary):
  DIRECT  : 14 stores + 11 infra methods
    direct port stores  (14): ['claim_gap_refs', 'claims', 'contradictions', 'entities', 'evidences', 'gap_dedup_index', 'gap_resolutions', 'gaps', 'hint_evidence_types', 'observations', 'relations', 'resolved_contradictions', 'rule_definitions', 'rule_stats']
    direct infra methods (11): ['_advance_state_revision', '_allocate_id', '_assert_claim_exists', '_assert_entity_exists', '_assert_evidence_exists', '_assert_gap_exists', '_assert_rule_pair_exists', '_assert_rule_stats_pair_exists', '_id_exists', '_record_claim_lifecycle_transition', 'state_identity']
  TRANSITIVE: 19 stores + 12 private methods
    transitive-only added stores  (5): ['_claim_lifecycle_events', '_lifecycle_seq', '_next_id', '_state_identity_token', '_state_revision']
    transitive-only added methods (1): ['_storage_for_kind']
```

These reproduce the ADR headline claims: DAG (0 SCCs); single revision
authority (_advance_state_revision, 20 callers) + single ID authority
(_allocate_id, 6 callers); `_claims` the only store written by >1 cluster
(operational, excl. C10 bulk `_install`); C2<->C5 direct calls = 0; module-function
port = 14 stores + 11 infra methods directly, transitive closure
19 stores + 12 private methods (the transitive-only additions are listed above).

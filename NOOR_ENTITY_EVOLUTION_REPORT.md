# Noor Entity Evolution Report

## 1. What existed before

The prior repository was a request/response prototype with a coordinator, in-memory spatial memory, a browser helper, policy heuristics, a grid vision fallback, an ADB bridge, and a dashboard. It did not contain durable beliefs, evidence records, prediction errors, inquiry decisions, world state, or a self-model derived from outcomes.

## 2. What changed

This iteration adds a compact cognitive core inside the existing backend. It keeps the existing stack and service layout, but adds testable internal state for evidence, beliefs, world relations, goals, predictions, outcomes, learning statistics, inquiry decisions, autonomy ticks, and JSON persistence.

## 3. New files

- `backend/app/cognitive_core.py`: the cognitive state engine.
- `backend/tests/test_cognitive_core.py`: unit, integration, causal ablation, anti-fake, persistence, and 10,000 tick simulation tests.
- `NOOR_ENTITY_EVOLUTION_REPORT.md`: this report.

## 4. Belief architecture

A belief has proposition, confidence, supporting evidence ids, counter-evidence ids, source, timestamps, last-tested timestamp, prediction history, contradiction count, revision count, status, and audit trail. Confidence changes only through evidence or prediction outcome evidence. Counter-evidence lowers confidence and records a before/after audit entry.

## 5. Evidence architecture

Evidence records require a non-empty claim and source. Each record has source type, source reliability, support/contradict relation, strength, collection time, and metadata. LLM-originated data is treated as a source type only; it cannot mutate authoritative state without passing the same validation.

## 6. World Model

The world model stores relation records with subject, relation, object, confidence, evidence ids, and update time. It is updated from beliefs and evidence, and can be disabled in causal ablation tests to prove behavior differs.

## 7. Inquiry Loop

The inquiry engine computes meta-state, uncertainty, information value, resource limits, and selected action. It can choose search, ask human, reason internally, defer, or act despite uncertainty. Browser search results are no longer a terminal output only: usable results become evidence through `run_inquiry_results`; empty results cannot be considered success.

## 8. Prediction and Learning

The prediction engine stores expected outcomes and probabilities. When an outcome is recorded, it computes prediction error. Prediction outcomes generate support or counter-evidence for linked beliefs. Learning statistics update source/domain performance, producing self-model data from history rather than random variables.

## 9. Self Model

The self-model reports prediction count, accuracy, and mean error by domain. It is derived only from resolved predictions. If the self-model feature is disabled, outcome resolution still works but self-model statistics do not update.

## 10. Autonomous Loop

The life loop is a bounded `tick()` scheduler. Each tick examines uncertain or contradictory beliefs and may choose inquiry-related action, or idle. It has a tick budget and bounded event history. Autonomy does not imply constant action.

## 11. Persistence

The cognitive core persists evidence, beliefs, world model, predictions, goals, events, learning history, ticks, and browser request count to JSON. This is intentionally simple and avoids adding a database.

## 12. Causal tests

The tests disable memory, beliefs, inquiry, world model, prediction, self-model, and autonomy and compare behavior. Examples: no belief engine makes the decision ask a human instead of search; no inquiry selects internal reasoning; no autonomy disables ticks; no world model prevents relation creation.

## 13. Long-term simulation

A test runs 10,000 ticks without human input and verifies tick count, event bounds, stable belief count, and scheduler stability.

## 14. Security and anti-fake tests

Tests prevent evidence-free belief creation, confidence changes without evidence path, search success without evidence, LLM authoritative writes without validation, and frontend/README claims of consciousness or self-awareness.

## 15. Test count before and after

- Before this iteration: 19 backend tests passed.
- After this iteration: 31 backend tests pass.

## 16. Failed tests and causes during implementation

- Initial cognitive tests exposed that weak browser evidence was treated as known. Fixed by making `knows()` require `known`, not merely `likely`.
- Initial ablation tests exposed feature overrides were merged incorrectly, making disabled components stay enabled. Fixed by applying explicit feature overrides after defaults.
- Self-model ablation initially had no causal effect. Fixed by preventing learning stats updates when `self_model` is disabled.

## 17. Hostile engineering critique

- Noor is still a prototype. It now has inspectable cognitive state, but it is not a living system.
- Belief revision is deterministic and evidence-weighted, but the proposition matcher is still simple exact-normalized text. It does not solve semantic equivalence.
- World modeling uses a simple subject/relation/object parser from text. It is auditable, but shallow.
- Inquiry can decide to search, but production browser evidence extraction remains thin and source reliability is crude.
- The autonomous loop is bounded and testable, but it is not a rich planner. It mostly inspects uncertainty and decides whether inquiry is worthwhile.
- Learning is real state change from prediction error, but it is statistical bookkeeping, not model training or deep skill acquisition.
- Persistence uses JSON, which is good for simplicity but weak for concurrent production use.
- The self-model is a performance summary. It is causal and history-derived, but narrow.

## 18. Fixes after critique

The critique identified three concrete weaknesses that were fixed in code before final testing:

1. Browser evidence was too easily promoted to knowledge; `knows()` now requires the `known` meta-state.
2. Feature ablation was not actually disabling components due to merge order; explicit overrides now take precedence.
3. Self-model ablation was not causal; prediction outcome learning now respects the `self_model` feature flag.

## 19. What could not be built here

- Real semantic belief merging beyond manual `merge_beliefs`.
- Durable multi-process storage with locking.
- Full browser evidence credibility scoring across independent sources.
- A rich planner or society-of-minds implementation. This iteration does not fake those.
- True multimodal vision. The vision layer remains an honest grid fallback.

## 20. What proves Noor became more independent

The proof is not language. It is code and tests:

1. Unknown propositions produce explicit meta-state.
2. Inquiry decisions derive from uncertainty, importance, and resource budgets.
3. Search results must become evidence or fail.
4. Evidence revises beliefs with an audit trail.
5. Predictions create measurable errors when outcomes arrive.
6. Errors update belief and self-model statistics.
7. Decisions change when beliefs, inquiry, world model, prediction, self-model, memory, or autonomy are ablated.
8. State survives restart through JSON persistence.
9. A 10,000-tick loop stays bounded and stable.

No claim of consciousness or self-awareness is made.

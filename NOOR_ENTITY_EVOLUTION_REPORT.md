# Noor Entity Evolution Report — Final Hardening

## 1. What is now causal

- Beliefs are created and revised only by validated evidence records. Every confidence update stores the evidence id, before/after confidence, effective relation, evidence weight, and timestamp in the belief audit trail.
- Evidence impact is causally moderated by source credibility, evidence strength, browser result quality, source history, and contradiction handling.
- Browser search success requires usable, scored, deduplicated results. Empty, duplicate-only, or low-value results produce observable `inquiry.search_failed` events instead of knowledge claims.
- Inquiry action selection uses meta-state, importance, expected gain, search cost, source credibility assumptions, and contradiction severity. It can search, ask, defer, idle, or act despite uncertainty.
- World relations are backed by evidence ids and include typed relation state, confidence, temporal hints, and ambiguity handling.
- Self-model output is derived from prediction/outcome history by domain and action type. It reports strengths, weaknesses, overconfidence risk, and help-seeking recommendations only when history exists.
- Autonomy ticks are bounded by check count and time budget. Each tick records an action/state plus reason codes.
- Persistence includes a state version, migration hook, atomic temp-file replacement, and a write lock guard.

## 2. What remains heuristic

- Semantic belief normalization is intentionally lightweight. It uses canonical terms, aliases, relation hints, polarity, stop-word removal, and equivalence thresholds; it is not a full natural-language understanding system.
- World extraction uses constrained lexical patterns for entities, relations, causes, and temporal hints. Ambiguous text is marked weak or ambiguous instead of being interpreted with false precision.
- Source credibility is a practical scoring heuristic based on source type, URL/domain hints, result content hints, and source history. It is not a truth oracle.
- Inquiry value-of-information is a transparent formula, not an optimal Bayesian planner.
- Self-model domain detection uses domain/action hints from recorded predictions. It is inspectable but still prototype-level.

## 3. What is durable after restart

- Evidence records, belief clusters, aliases, contradiction counts, audit trails, world relations, predictions, goals, unknowns, events, source statistics, self-history, browser request counts, tick count, and state version persist to JSON.
- Restart consistency is protected by atomic write replacement and a lock file. Simulated partial write failure leaves the previous state readable.

## 4. What is still prototype

- The persistence backend is hardened JSON, not a database or multi-process transactional store.
- Semantic clustering is lightweight and local to proposition text; it does not call embeddings or an LLM.
- Browser scoring is conservative and rejects many weak results; it does not perform full webpage retrieval or fact extraction.
- The scheduler is bounded and introspective, not a general autonomous planner.

## 5. What must not be claimed

- Do not claim consciousness, sentience, emotions, self-awareness, personhood, or living agency.
- Do not claim visual object recognition beyond the implemented vision fallback unless a real adapter is added and tested.
- Do not claim browser search creates strong knowledge automatically; it only attaches scored evidence when usable.
- Do not claim the self-model is introspective awareness; it is an outcome-history summary.
- Do not claim world relations are facts without backing evidence and confidence.

## 6. Tests that prevent pretending

- Semantic normalization clusters alias propositions and detects contradiction across different phrasings.
- Relation extraction tests verify typed causal/temporal relations and ambiguous-state handling.
- Inquiry tests verify different decisions under changed importance, contradiction, and search cost.
- Browser evidence tests verify scoring, source credibility impact, deduplication, rejection, and observable failure.
- Self-model tests verify domain-specific differences and help-seeking flags from actual prediction outcomes.
- Persistence tests verify roundtrip, versioning, and partial-write safety.
- Scheduler tests verify idle behavior, reason codes, and bounded checks.
- Anti-fake tests block evidence-free beliefs, source-free evidence, search success without evidence, self-model claims without history, unbacked world relations, and forbidden consciousness-like interface claims.
- Long-term simulation runs 10,000 ticks and checks bounded events and stable belief count.

## 7. Operational note about the reported startup failure

The reported Windows startup log shows Uvicorn reached application startup and then failed with `Errno 10048` binding `127.0.0.1:8000`. That error means port 8000 was already occupied by another process; it is not an application import/startup failure. The backend was verified on a free port during this hardening pass. To run locally when port 8000 is occupied, stop the existing process or choose another port, for example `python -m uvicorn app.main:app --host 127.0.0.1 --port 8765` with `PYTHONPATH=backend` from the repository root, or equivalent `PYTHONPATH=src` if running from a service layout that imports `src.main`.

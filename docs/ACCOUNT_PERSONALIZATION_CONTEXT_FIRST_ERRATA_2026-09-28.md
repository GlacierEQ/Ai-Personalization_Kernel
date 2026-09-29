# Account Personalization Control Plane — Context-First Errata

**Effective:** 2026-09-28

This errata supersedes the stale phrase "deep retrieval is selective" wherever
it appears in the Account Personalization Control Plane.

## Governing retrieval semantics

1. The compact user model is always active.
2. Core continuity recovery is requested on every turn before action selection:
   - current conversation;
   - recent exact messages;
   - project state;
   - historical chats;
   - canonical user-owned artifacts;
   - external memory indexes.
3. A model-side relevance judgment cannot suppress the core recovery pass.
4. Live-provider freshness and public-web acquisition are additive and
   task-scoped; they are not substitutes for historical/project recovery.
5. Requested/activated context does not count as retrieved context. The receipt
   must distinguish attempted, retrieved, empty, and unavailable source lanes.
6. Missing adapters or empty results create explicit retrieval-state facts.
   They do not permit the runtime to claim context was recovered.
7. Action selection occurs after the recovery receipt is assembled.

## Runtime binding

The default boot path is being migrated to the context-first implementation in:

- src/apk/context_first_router_v2.py
- src/apk/boot.py
- tests/test_context_first_router_v2.py
- tests/test_context_first_boot.py

This errata strengthens the original goals of the control plane: causal
personalization, continuity across sessions, and prevention of instruction
displacement. It does not change provider, security, or platform boundaries.

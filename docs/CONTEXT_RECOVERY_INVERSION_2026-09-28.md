# Context Recovery Inversion — 2026-09-28

## Defect

The current router says deep retrieval is selective and, with no trigger, the
existing regression test expects only the compact user model. That conflicts
with the Operator requirement that context recovery occur before relevance
judgment on every turn.

A second defect is receipt semantics: the existing boot path can infer
context_retrieved from activated tiers rather than actual returned context.

## Replacement contract

MESSAGE
-> LOAD COMPACT USER MODEL
-> REQUEST CORE CONTEXT LANES UNCONDITIONALLY
   - current conversation
   - recent exact messages
   - project state
   - historical chats
   - canonical artifacts
   - external memory indexes
-> RECORD EACH LANE AS attempted / retrieved / empty / unavailable
-> ONLY ACTUAL RETURNED CONTEXT COUNTS AS RETRIEVED
-> RECONCILE
-> ACTION SELECTION
-> OPTIONAL LIVE PROVIDER / WEB ACQUISITION WHEN THE TASK NEEDS IT
-> EXECUTE

No model relevance judgment controls whether core history/project context is
requested.

Live-provider freshness and public-web retrieval remain additive because they
answer external-state questions rather than continuity questions.

## Implementation

- src/apk/context_first_router_v2.py
- tests/test_context_first_router_v2.py

The existing router is preserved until the replacement is promoted after CI.
That preserves lineage and makes the semantic delta falsifiable rather than
silently rewriting history.

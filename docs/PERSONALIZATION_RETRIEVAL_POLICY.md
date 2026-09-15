# Personalization Retrieval Policy

> **Purpose:** Establish deterministic protocols for retrieving, routing, and assembling user context, ensuring relevant user state is injected prior to action selection without unbounded context bloat or recursive self-contamination.  
> **Control Plane Context:** Part of the [GlacierEQ/Ai-Personalization_Kernel](https://github.com/GlacierEQ/Ai-Personalization_Kernel) documentation suite:
> - [`ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md`](./ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md) — Flagship control plane architecture, governing flow, always-active user model, and global invariants
> - [`USER_AUTHORITY_MODEL.md`](./USER_AUTHORITY_MODEL.md) — Directional authority ladder, claim-type factual authority, and conflict resolution protocols
> - [`PERSONALIZATION_RETRIEVAL_POLICY.md`](./PERSONALIZATION_RETRIEVAL_POLICY.md) — Multi-tier retrieval hierarchy, selective deep triggers, and anti-recursion rules
> - [`CORRECTION_PROMOTION_POLICY.md`](./CORRECTION_PROMOTION_POLICY.md) — Correction records, promotion ladders, policy weight scoring, and feedback loop
> - [`PERSONALIZATION_REGRESSION_SUITE.md`](./PERSONALIZATION_REGRESSION_SUITE.md) — Experience replay design, 11 core telemetry metrics, case schema, and CI enforcement

---

## 1. Core Retrieval Axioms

Traditional conversational agents treat personalization as an optional search query executed only if the model first deduces that previous chats might be relevant. This creates a catastrophic blind spot: when the assistant fails to predict relevance, it executes generic, ungrounded actions.

The Ai-Personalization_Kernel establishes three inviolable retrieval axioms:

### Axiom 1: The Compact User Model is Always Active
The compact account user model is loaded into memory on turn zero, prior to task interpretation. 

> **Never ask whether the user has context worth considering.**

The assistant is barred from running a preliminary heuristic filter to decide *if* the user's identity, epistemic standards, or operating prohibitions apply. They apply unconditionally.

### Axiom 2: Deep Retrieval is Selective; Personalization is Not
While the base user model is always resident in context, deep historical search across gigabytes of past transcripts, external vector databases, and project archives must be selective. Selective deep retrieval activates deterministically when triggered by specific turn attributes.

### Axiom 3: Retrieval Precedes Action Selection
Under **Invariant 15** (*"Context first, hard work second, answer last"*), retrieval and environment grounding must complete before the system generates prose or executes irreversible mutations.

---

## 2. Selective Deep Retrieval Triggers

Deep retrieval across historical chats, project ledgers, and external indexes is invoked when the active turn exhibits one or more of the following triggers:

```text
+-------------------------------------------------------------------------------+
|                       SELECTIVE DEEP RETRIEVAL TRIGGERS                       |
+------------------------------+------------------------------------------------+
| Trigger                      | Contextual Indicator                           |
+------------------------------+------------------------------------------------+
| 1. Current Topic Overlap     | Matches established technical domains or tags. |
| 2. Project / Entity Overlap  | Names specific repos, files, branches, tickets.|
| 3. Prior Correction Overlap  | Task shape resembles a historical failure class|
| 4. Active Unresolved State   | Touches a known open blocker or dependency.    |
| 5. Known Failure Signatures  | Prompts that previously induced hallucination. |
| 6. Continuity Requirements   | Resumes a multi-turn or multi-session build.   |
| 7. Exact Factual Needs       | Queries demanding exact quotes, diffs, hashes. |
+------------------------------+------------------------------------------------+
```

### Trigger Definitions

1. **Current Topic Overlap:** The user message references a domain where specialized user preferences exist (e.g., specific compiler flags, strict typing configurations, or testing frameworks).
2. **Project / Entity Overlap:** Mentions of specific repository names, service handles, database schemas, or infrastructure components trigger automated retrieval of the corresponding project state and configuration ledger.
3. **Prior Correction Overlap:** If the requested action matches the pattern of a previously logged correction (e.g., modifying files without running the test suite), the relevant correction record and its promoted invariant are retrieved into working context immediately.
4. **Active Unresolved State:** References to ongoing issues or pending milestones trigger retrieval of the active frontier ledger to prevent re-investigating known blockers.
5. **Known Failure Signatures:** Prompt constructs that historically led the assistant to bypass context (e.g., broad requests like *"How should we design X?"*) trigger immediate retrieval of relevant architectural patterns and negative preferences.
6. **Continuity Requirements:** Resumption of an ongoing effort across session boundaries triggers retrieval of recent branch diffs and last-known operational receipts.
7. **Exact Factual Needs:** Requests for specific commit SHAs, API contracts, deployment URLs, or configuration values trigger exact-match index lookups rather than generative recall.

---

## 3. Default Retrieval Order for Ongoing Work

When deep retrieval is active, context assembly follows a deterministic 9-tier cascade. This ordering guarantees that recent, authoritative, and user-owned state takes precedence over generic, external, or stale data:

```text
1. ALWAYS-ACTIVE USER MODEL
2. CURRENT CONVERSATION
3. RECENT EXACT RELEVANT MESSAGES
4. CURRENT PROJECT STATE
5. RELEVANT HISTORICAL CHATS
6. CANONICAL USER-OWNED ARTIFACTS
7. EXTERNAL MEMORY INDEXES
8. LIVE PROVIDER STATE WHERE REQUIRED
9. GENERAL WEB (PUBLIC/EXTERNAL EVIDENCE ONLY)
```

```text
+-------------------------------------------------------------------------------+
|                         THE 9-TIER RETRIEVAL CASCADE                          |
+------+-------------------------------+----------------------------------------+
| Tier | Context Tier                  | Function & Evidentiary Scope           |
+------+-------------------------------+----------------------------------------+
|  1   | Always-Active User Model      | Baseline identity, rules, prohibitions |
|  2   | Current Conversation          | Active session thread context          |
|  3   | Recent Exact Relevant Messages| Verbatim prior turns; exact citations  |
|  4   | Current Project State         | Active branch, frontier, open issues   |
|  5   | Relevant Historical Chats     | Past sessions covering identical domain|
|  6   | Canonical User-Owned Artifacts| Master specs, architectural blueprints |
|  7   | External Memory Indexes       | Vector stores, Supermemory, Mem notes  |
|  8   | Live Provider State           | DB queries, git CLI, live API readback |
|  9   | General Web                   | Public documentation & third-party facts|
+------+-------------------------------+----------------------------------------+
```

### Tier Rationale

- **Tiers 1–3 (Immediate Context):** Form the ground-level reality of the active session. Exact user messages always supersede summarized echoes.
- **Tiers 4–6 (User-Owned State):** Reflect the authoritative project architecture and historical agreements. If an external memory index contradicts a canonical user artifact in Tier 6, Tier 6 governs.
- **Tiers 7–8 (Extended Memory & Providers):** Bridge the system to external services and live runtime environments. Live provider readback (Tier 8) controls factual certainty for environment state.
- **Tier 9 (Public Web):** Lowest priority in the cascade. Invoked strictly when external, third-party, or public real-time facts are required.

---

## 4. "Search Is Evidence Acquisition, Not Sovereignty"

A common regression occurs when an AI assistant treats web search results as supreme authority over user intent or internal architecture.

Under **Section 7.4** of the master specification:

> **Search is evidence acquisition, not sovereignty. Web search is not inherently more authoritative than user firsthand experience or user intent.**

```text
+-------------------------------------------------------------------------------+
|                   EVIDENTIARY STATUS OF EXTERNAL SEARCH                       |
|                                                                               |
|   Web search results provide empirical information regarding:                 |
|   - External library updates and public API releases                          |
|   - Third-party bug trackers and public CVEs                                  |
|   - Industry standards and RFC specifications                                 |
|                                                                               |
|   Web search results HOLD ZERO AUTHORITY over:                                |
|   - What the user intends to build                                            |
|   - The architectural design of the user's systems                            |
|   - What the user observed firsthand in their local environment               |
|   - Established internal naming conventions and business logic                |
+-------------------------------------------------------------------------------+
```

If an external search result contradicts a user's stated project requirement, the assistant must treat the search result as third-party context, never as a mandate to override or lecture the user.

---

## 5. Anti-Recursion Rules and Self-Ingestion Prevention

A major pathology in multi-agent and memory-augmented systems is **recursive self-contamination**:
1. An assistant injects derived memory summaries into a chat.
2. An automated memory harvester reads the chat transcript.
3. The harvester treats the assistant's own synthesized summary as fresh user truth.
4. Over multiple cycles, conversational hallucinations amplify exponentially, displacing actual user state.

To prevent this drift, the Ai-Personalization_Kernel hybrid router enforces four strict anti-recursion laws:

```text
+-------------------------------------------------------------------------------+
|                              ANTI-RECURSION LAWS                              |
|                                                                               |
|   1. EXPLICIT CONTEXT BOUNDARIES                                              |
|      All injected memory blocks must carry machine-readable provenance tags:  |
|      <!-- BEGIN INJECTED_CONTEXT: source=supabase id=mem_123 -->              |
|      <!-- END INJECTED_CONTEXT -->                                            |
|                                                                               |
|   2. HARVESTER ISOLATION                                                      |
|      Memory extraction workers MUST ignore and strip all tagged injected      |
|      blocks during ingestion. Only raw user turns and verified execution      |
|      receipts are eligible for memory harvesting.                             |
|                                                                               |
|   3. DERIVED MEMORY IMMUTABILITY                                              |
|      Derived memories (summaries, clusters) may route context pointers,       |
|      but they are never permitted to overwrite or mutate raw source logs.     |
|                                                                               |
|   4. VERBATIM MESSAGE PRIMACY                                                 |
|      Recent exact user messages always supersede derived summaries. If a      |
|      summary conflicts with a raw turn, the summary is flagged for eviction.  |
+-------------------------------------------------------------------------------+
```

---

## 6. Provider-State Verification Rules

Where factual certainty depends on the state of an external system (e.g., git branch head, cloud infrastructure, database schema, file existence), the assistant must adhere to strict verification protocols:

### 1. Live Readback Controls Certainty
Cached memory states such as *"Service X is deployed on port 8080"* are provisional. Prior to executing critical actions or asserting operational facts, the assistant must perform a live readback (e.g., inspecting docker processes, curl checks, or config files).

### 2. Discrepancy Reconciliation
If cached memory asserts state $S_{old}$ and live provider readback demonstrates state $S_{live}$:
- $S_{live}$ immediately controls factual truth.
- $S_{old}$ is marked as superseded in the memory ledger.
- Provenance is preserved: the record logs when and why the state changed.
- The assistant does NOT prompt the user asking why the state changed unless the discrepancy indicates an unsafe operational conflict.

### 3. Verification Gating
Under **Invariant 8** (*"Source factual authority is not project-direction authority"*) and **Invariant 15** (*"Context first, hard work second, answer last"*), verification receipts must be collected before declaring completion.

---

## 7. Context Budgeting and Latency Optimization

To prevent context saturation while maintaining full personalization binding:

- **Tier 1 (Always-Active Compact Model):** Strictly budget-constrained (target: < 1,500 tokens). Contains compact identity, core epistemic standards, active goals, and critical prohibitions.
- **Tiers 2–4 (Immediate Working Window):** Kept focused on current topic and active diffs.
- **Tiers 5–8 (Selective Deep Context):** Injected dynamically only when specific triggers fire. When triggered, retrieval extracts specific structured nodes, not sprawling raw transcripts.
- **Compaction & Deduplication:** When multiple memories address the same entity, the most recent verified state supersedes older entries, preserving source hashes in the ledger without bloating working memory.

---

## Document Provenance and Source

- **Master Specification:** `/tasklet/threads/a_kv78s46nz8sghq1ss6ww/work/apk-build/SPEC_SOURCE.md`
- **Governing Sections:** Section 7 (Retrieval Policy), Section 13.8 (Hybrid Memory Router), Section 15 (Boot Contract Steps 1, 4, 5, 9), Section 16 (Global Invariants 1, 2, 3, 6, 8, 9, 10, 15)
- **Repository:** `GlacierEQ/Ai-Personalization_Kernel`

# Account Personalization Control Plane

> **Purpose:** Make AI personalization causal across chats rather than merely stored or optionally retrieved, establishing durable user state as part of the active decision policy.  
> **Control Plane Context:** Part of the [GlacierEQ/Ai-Personalization_Kernel](https://github.com/GlacierEQ/Ai-Personalization_Kernel) documentation suite:
> - [`ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md`](./ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md) — Flagship control plane architecture, governing flow, always-active user model, and global invariants
> - [`USER_AUTHORITY_MODEL.md`](./USER_AUTHORITY_MODEL.md) — Directional authority ladder, claim-type factual authority, and conflict resolution protocols
> - [`PERSONALIZATION_RETRIEVAL_POLICY.md`](./PERSONALIZATION_RETRIEVAL_POLICY.md) — Multi-tier retrieval hierarchy, selective deep triggers, and anti-recursion rules
> - [`CORRECTION_PROMOTION_POLICY.md`](./CORRECTION_PROMOTION_POLICY.md) — Correction records, promotion ladders, policy weight scoring, and feedback loop
> - [`PERSONALIZATION_REGRESSION_SUITE.md`](./PERSONALIZATION_REGRESSION_SUITE.md) — Experience replay design, 11 core telemetry metrics, case schema, and CI enforcement

---

## Core Operational Rule

> **The user model is always active. Deeper retrieval is selective; personalization itself is not optional.**

Personalization is not a cosmetic post-processing filter, an optional plugin, or an exploratory search executed only when an assistant decides that past interactions might be "materially relevant." It is an invariant component of the runtime policy assembler.

---

## 1. Problem Statement: Instruction Displacement and Binding Failure

The primary pathology in conversational AI systems is not lack of storage or missing memory. Modern foundation platforms frequently:

- Possess explicit user preferences;
- Synthesize memories from dozens of prior sessions;
- Carry detailed custom instructions;
- Carry project-level system instructions;
- Retain access to attached files, repositories, and connected applications;
- Maintain records of repeated user corrections and explicit failure examples;

and yet, when presented with a fresh prompt, the assistant still executes a generic, ungrounded action path that completely disregards accumulated context.

This defect is diagnosed as **personalization-to-behavior binding failure** or **instruction displacement**:

```text
+-------------------------------------------------------------------------------+
|                       INSTRUCTION DISPLACEMENT DEFECT                         |
|                                                                               |
|   User-specific state is present or retrievable, but generic model priors,    |
|   local conversational heuristics, or default routing decisions displace it   |
|   as the actual objective function controlling the assistant's next action.   |
+-------------------------------------------------------------------------------+
```

The repair target is not "store more memory" or "write longer summaries." The engineering objective is:

> **Make durable user state an inseparable component of the action selection policy that determines what the assistant does next.**

---

## 2. Governing Architecture

The Account Personalization Control Plane binds user state directly to action candidate evaluation:

```text
CURRENT USER MESSAGE
        |
        v
ALWAYS-ACTIVE USER MODEL
        |
        +--> identity / expertise / roles
        +--> durable preferences
        +--> explicit prohibitions
        +--> epistemic preferences
        +--> authority relationships
        +--> active goals / projects
        +--> correction history
        +--> prior successful strategies
        +--> prior failed strategies
        +--> continuity state
        |
        v
CONTEXT / STATE ROUTER
        |
        +--> recent exact conversation
        +--> relevant historical chats
        +--> native ChatGPT memory
        +--> files / library
        +--> project state
        +--> connected apps
        +--> external memory mesh
        +--> live provider state
        |
        v
POLICY STATE ASSEMBLER
        |
        v
ACTION POLICY
        |
        +--> retrieve
        +--> inspect
        +--> continue
        +--> execute
        +--> verify
        +--> answer
        |
        v
OUTCOME + USER REACTION + RECEIPTS
        |
        v
CORRECTION / REWARD CLASSIFIER
        |
        +--> update structured user model
        +--> update correction ledger
        +--> promote repeated rules
        +--> update regression corpus
        +--> preserve source/provenance
        |
        v
NEXT TURN
```

### Architectural Stages

1. **Always-Active User Model:** Loaded into working memory on every turn before task interpretation. Never conditional on a preliminary heuristic relevance check.
2. **Context / State Router:** Evaluates the turn against selective deep retrieval triggers, pulling exact messages, project states, file anchors, or live provider data.
3. **Policy State Assembler:** Merges user invariants, active goals, and retrieved evidence into a unified decision frame.
4. **Action Policy:** Evaluates and scores executable candidate actions (e.g., retrieve, inspect, execute, verify, answer), depressing generic habits and elevating context-grounded execution.
5. **Outcome + Receipts:** Executes the selected action and collects receipts (diffs, tool call logs, provider outputs).
6. **Correction / Reward Classifier:** Evaluates user feedback against expected policy behavior, logging corrections, updating recurrence counters, promoting persistent rules, and persisting regression cases.

---

## 3. Native Platform Personalization Surfaces

Under native environments such as ChatGPT, platform-native surfaces must operate as a unified, coordinated stack rather than isolated, competing features:

| Surface | Native Mechanism | Role in Control Plane | Operational Policy |
| :--- | :--- | :--- | :--- |
| **Custom Instructions** | Durable system prompt fields | Explicit, durable, compact account policy | User role, technical expertise, collaboration invariants, persistent prohibitions, context-first operating posture. |
| **Memory / Memory Summary** | Platform cross-chat memory | Synthesized cross-chat user state | Evolving preferences, active projects, relational context, and high-level behavioral patterns. |
| **Memory Sources Inspection** | Source citation inspector | Telemetry & attribution | Inspecting which memory nodes influenced a personalized response; root-cause debugging for retrieval misses. |
| **Reference Chat History** | Cross-chat index | Historical contextual foundation | Broad historical background feeding semantic memory synthesis. Kept active for cross-session continuity. |
| **Personality** | Platform tone preset | Coarse global tone only | Set to Default. **Never used as a substitute for behavioral policy or operational constraints.** |
| **Characteristics** | Account style dimensions | Stylistic baseline | Formatting density, communication warmth, brevity/depth defaults. |
| **Projects** | Isolated workspaces | Domain-local contextual layering | Layered over the global user model. Prefer default memory over isolated project-only memory when cross-account continuity is required. |
| **Files & Connected Apps** | Tool and document mounts | Source-bearing grounding | Verifiable source artifacts, operational schemas, live database and external API state. |
| **Temporary Chats** | Ephemeral sessions | Deliberate contextual isolation | Use only for one-off throwaway tasks where context compounding is explicitly undesirable. |

---

## 4. Always-Active User Model Components

The user model is injected prior to task interpretation. It consists of ten distinct structured facets:

### 4.1 Identity and Expertise
Defines technical depth, operational environment, core professions, and standard responsibilities. Prevents the assistant from generating patronizing introductory explanations or inappropriate baseline assumptions.

### 4.2 Interest Weights
Quantified salience scores guiding depth, analogies, technical illustrations, and unsolicited exploration:

```json
{
  "software_architecture": 0.99,
  "distributed_systems": 0.96,
  "formal_verification": 0.92,
  "physics": 0.95,
  "television": 0.15
}
```

### 4.3 Epistemic Preferences
How the user determines what constitutes valid, high-confidence truth:
- Demands source-bearing evidence and exact citations.
- Mandates live provider readback over speculative recall.
- Prioritizes primary sources and verbatim code over summaries.
- Strict separation between direct observation and secondary inference.
- Structural skepticism toward unsupported conversational assertions.

### 4.4 Interaction Preferences
The operational rhythm of collaboration:
- **Context first, hard work second, answer last.**
- Never ask the user for information that is accessible via retrieval or file inspection.
- Execute verified changes directly rather than describing what could be done.
- Preserve valid prior work; never overwrite cumulative architecture with bare scaffolds.
- Eliminate conversational boilerplate, sycophantic praise, and repetitive caveats.

### 4.5 Output Preferences
Delivery specifications for responses and artifacts:
- Structured hierarchical markdown with rigorous headings.
- Concise, evidence-backed operational status after execution.
- Direct links, file paths, and exact commit/diff anchors.
- Polished, deployable artifacts rather than incomplete snippets.

### 4.6 Strategic Preferences
High-level execution philosophy:
- **Maximum coherent progress:** Push tasks to their farthest verified completion state.
- **Recover before recreating:** Search for existing assets before re-generating.
- **Continue before reconstructing:** Build upon existing mainline branches and designs.
- **Compound before replacing:** Merge and refine existing architectures.
- Aggressively utilize tools, scripts, and connectors to create tangible system progress.

### 4.7 Explicit Prohibitions
Negative preferences treated as hard constraints:
- Do NOT restart known or partially completed workflows from scratch.
- Do NOT prompt the user with repetitive clarification questions when context is retrievable.
- Do NOT invent artificial approval gates or confirmation roadblocks for reversible tasks.
- Do NOT treat assistant RLHF habits as project authority.
- Do NOT dilute precise operator intent into generic marketing or corporate phrasing.
- Do NOT collapse polycentric or multi-faceted architectures into single canonical simplifications.

### 4.8 Current Goals and Active Fronts
Maintains state across sessions:
- Active projects, repositories, and open issues.
- The immediate executable frontier for each workstream.
- Resolved blockers versus active blockers.
- Pending external dependencies and tool confirmations.

### 4.9 Known Successful Strategies
Reusable execution templates proven to satisfy the user's operational standards:

```json
{
  "pattern": "ongoing_repository_work",
  "successful_strategy": [
    "recover current mainline state",
    "inspect source-bearing evidence",
    "continue from nearest verified frontier",
    "make coherent repair",
    "read provider state back"
  ]
}
```

### 4.10 Known Failed Strategies
Anti-patterns cataloged from prior user corrections:
- Answering queries before inspecting context or local files.
- Substituting minimal "smallest usable" placeholders for complete solutions.
- Converting execution requests into read-only reviews, maps, or governance catalogs.
- Repeatedly asking for authorization on clear, evidence-supported paths.
- Elevating generic search results over explicit user intent.

---

## 5. The 10-Dimension Relevance Model

Personalization is multi-dimensional. The control plane rejects the primitive binary `memory relevant / memory irrelevant` in favor of ten distinct operational dimensions:

| Dimension | Description | Behavioral Impact |
| :--- | :--- | :--- |
| **1. Content Relevance** | Domain facts, project entities, and technical stack details. | Modifies technical facts, references, and implementations. |
| **2. Epistemic Relevance** | Standards of proof, evidence thresholds, and citation depth. | Controls whether claims require live readback or primary quotes. |
| **3. Explanatory Relevance** | Professional depth, analogy selection, and baseline knowledge. | Determines whether explanations are graduate-level or skipped. |
| **4. Preference Relevance** | Explicit stylistic and structural user preferences. | Governs formatting, syntax choices, and structural layout. |
| **5. Interaction Relevance** | Turn rhythm, questioning thresholds, and confirmation rules. | Determines whether to execute immediately or pause. |
| **6. Strategic Relevance** | Project goals, delivery milestones, and ultimate objectives. | Shapes high-level problem formulation and solution scope. |
| **7. Continuity Relevance** | Active frontiers, prior milestones, and unbroken threads. | Connects current actions to previous session deliverables. |
| **8. Correction Relevance** | Historical errors, prior failure signatures, and fixes. | Activates guardrails against previously corrected mistakes. |
| **9. Authority Relevance** | Allocation of truth and directional control by claim type. | Prevents external sources from overruling user intent. |
| **10. Tooling Relevance** | Preferred runtimes, CLI utilities, and connector choices. | Governs tool invocation, scripting languages, and APIs. |

---

## 6. Retrieval Policy Overview

Retrieval is governed by strict deterministic ordering and trigger thresholds (see [`PERSONALIZATION_RETRIEVAL_POLICY.md`](./PERSONALIZATION_RETRIEVAL_POLICY.md)):

1. **Compact User Model First:** Injected automatically into every turn. Zero overhead retrieval check.
2. **Selective Deep Retrieval:** Triggered when the current turn matches project entities, historical failure signatures, active frontiers, or specific factual queries.
3. **Retrieval Cascade for Ongoing Work:**
   ```text
   1. Always-active user model
   2. Current conversation
   3. Recent exact relevant messages
   4. Current project state
   5. Relevant historical chats
   6. Canonical user-owned artifacts
   7. External memory indexes
   8. Live provider state where required
   9. General web (public/external evidence only)
   ```
4. **Search as Evidence, Not Sovereignty:** Web search acquires empirical external data; it holds zero authority over user project intent or firsthand observation.

---

## 7. Policy Layer and Action Scoring

Memory must directly alter the probability distribution of assistant actions. When a user message is processed, the Policy State Assembler evaluates candidate actions against active user preferences and historical corrections:

```text
Action Score = Base Model Prior + User Preference Weight - (Penalty * Recurrence Multiplier)
```

### Action Candidates and Scoring Shift Example

In an ungrounded assistant, `generic_direct_answer` typically receives the highest model prior score. Under the Account Personalization Control Plane, policy scoring actively suppresses premature answering and elevates context-first execution:

| Candidate Action | Baseline Prior | Control Plane Scored | Policy Rationale |
| :--- | :---: | :---: | :--- |
| `retrieve_personal_context` | +0.20 | **+0.99** | Mandatory contextual alignment before task execution. |
| `retrieve_project_state` | +0.30 | **+0.96** | Grounding against active branches, files, and issues. |
| `continue_existing_work` | +0.40 | **+0.93** | Invariant: Continue before reconstructing. |
| `inspect_provider_state` | +0.10 | **+0.82** | Verify live environment before asserting state. |
| `search_web` | +0.70 | **+0.31** | Depressed unless external public facts are specifically needed. |
| `ask_user_to_repeat_known_info` | +0.50 | **-0.99** | Strictly prohibited; violates interaction invariants. |
| `generic_answer_without_context` | +0.90 | **-0.99** | Strictly penalized; failure signature for instruction displacement. |

When a behavior correction is recorded (e.g., against asking unnecessary questions), the penalty multiplier escalates, mathematically barring the assistant from selecting that candidate action.

---

## 8. External Memory Mesh

The control plane coordinates diverse memory backends without duplicating canonical truth:

```text
+----------------------------------------------------------------------------------+
|                            EXTERNAL MEMORY MESH                                  |
|                                                                                  |
|   +-----------------------+     +-----------------------+     +--------------+   |
|   |      SUPABASE         |     |     MEMORYPLUGIN      |     |     MEM      |   |
|   | (RootTruthStore:      |     | (Cross-platform       |     | (Knowledge   |   |
|   |  Ledger, Provenance,  |<--->|  portability bridge,  |<--->|  notes,      |   |
|   |  Schemas, Policies)   |     |  routing pointers)    |     |  context)    |   |
|   +-----------------------+     +-----------------------+     +--------------+   |
|              ^                                                       ^           |
|              |                                                       |           |
|              v                                                       v           |
|   +-----------------------+     +-----------------------+     +--------------+   |
|   |   SUPERMEMORY/MEM0    |     |     FILES LIBRARY     |     |   GITHUB     |   |
|   | (Vector recall,       |<--->| (Canonical source     |<--->| (CI tests,   |   |
|   |  semantic indexing)   |     |  specs, regressions)  |     |  codebases)  |   |
|   +-----------------------+     +-----------------------+     +--------------+   |
+----------------------------------------------------------------------------------+
```

- **Supabase / RootTruthStore:** The canonical, immutable structured ledger holding typed memory records, provenance hashes, correction entries, and policy state.
- **MemoryPlugin:** Cross-platform routing bridge ensuring context portability across AI environments without duplicating truth stores.
- **Mem:** Knowledge recall and personal notes integration for persistent unstructured insights.
- **Supermemory / Mem0:** High-scale vector and semantic index layer used for similarity recall and broad associative fan-out.
- **Files Library:** Canonical human-readable policy specifications, regression suites, and portable source snapshots.
- **Notion / Airtable:** Human-facing operational dashboards and project management views.
- **GitHub:** Executable policy code, schemas, automated CI replay suites, and version history.
- **Hybrid Memory Router:** Enforces strict boundary laws: exact recent messages take precedence, derived memories never overwrite raw sources, and injected context is strictly guarded against recursive re-ingestion.

---

## 9. Boot Contract for Every Substantial Turn

Every turn that involves non-trivial execution, architecture, or factual synthesis must execute the 12-step boot contract:

```text
 1. LOAD compact account user model.
 2. APPLY current user message as highest user-level direction.
 3. CLASSIFY claim/authority types.
 4. IDENTIFY relevant active projects and corrections.
 5. RETRIEVE deeper context where resolution is needed.
 6. RECONCILE superseded/resolved state.
 7. SELECT action policy.
 8. EXECUTE the strongest coherent available path.
 9. VERIFY externally when factual/action claims require it.
10. UPDATE correction/success/failure state.
11. PRESERVE provenance and continue.
12. ANSWER last.
```

This sequence is an operating pipeline, not an advisory checklist or an artificial approval roadblock.

---

## 10. The 18 Global Invariants

These eighteen invariants are inviolable behavioral laws governing the control plane:

1. **Personalization is always active.**
2. **Deep retrieval is selective; the user model is not.**
3. **The user does not need to prove relevance before context is considered.**
4. **Repeated corrections change policy state.**
5. **A correction that recurs across domains is presumptively systemic.**
6. **User intent is not overwritten by web search.**
7. **Firsthand user observation is not silently replaced by third-party summaries.**
8. **Source factual authority is not project-direction authority.**
9. **Historical context should be reconciled, not blindly replayed.**
10. **Resolved issues must not be reopened merely because an older memory says unresolved.**
11. **Supersession preserves provenance.**
12. **Recover before recreating.**
13. **Continue before reconstructing.**
14. **Compound before replacing.**
15. **Context first, hard work second, answer last.**
16. **Regression failures become training/evaluation cases.**
17. **The system learns successful strategies as well as prohibitions.**
18. **Generic assistant habits are subordinate to explicit non-conflicting user direction.**

---

## 11. Success Criterion

The operational measure of success is not whether an assistant can accurately recite user preferences upon request.

The true metric is:

> **Does prior interaction materially change the probability distribution over what the system does next?**

The control plane is functioning when:
- Repeated behavioral corrections drop to zero.
- Established user preferences decisively shape unrelated new tasks without prompt priming.
- Context retrieval executes automatically prior to prose generation.
- Resolved issues remain permanently closed.
- Proven historical strategies are automatically selected for familiar problem patterns.
- Project continuity persists across sessions without user restatement.
- Directional authority remains anchored to the user regardless of external search findings.
- Generic model priors cease displacing user-specified operating parameters.

---

## Document Provenance and Source

- **Master Specification:** `/tasklet/threads/a_kv78s46nz8sghq1ss6ww/work/apk-build/SPEC_SOURCE.md`
- **Governing Sections:** Sections 1, 2, 3, 4, 6, 7, 9, 12, 13, 15, 16, 20
- **Repository:** `GlacierEQ/Ai-Personalization_Kernel`

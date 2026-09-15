# Correction Promotion Policy

> **Purpose:** Convert user corrections into executable behavioral policy state, eliminating recurring assistant failures and instruction displacement through deterministic promotion ladders and mathematical penalty escalation.  
> **Control Plane Context:** Part of the [GlacierEQ/Ai-Personalization_Kernel](https://github.com/GlacierEQ/Ai-Personalization_Kernel) documentation suite:
> - [`ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md`](./ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md) — Flagship control plane architecture, governing flow, always-active user model, and global invariants
> - [`USER_AUTHORITY_MODEL.md`](./USER_AUTHORITY_MODEL.md) — Directional authority ladder, claim-type factual authority, and conflict resolution protocols
> - [`PERSONALIZATION_RETRIEVAL_POLICY.md`](./PERSONALIZATION_RETRIEVAL_POLICY.md) — Multi-tier retrieval hierarchy, selective deep triggers, and anti-recursion rules
> - [`CORRECTION_PROMOTION_POLICY.md`](./CORRECTION_PROMOTION_POLICY.md) — Correction records, promotion ladders, policy weight scoring, and feedback loop
> - [`PERSONALIZATION_REGRESSION_SUITE.md`](./PERSONALIZATION_REGRESSION_SUITE.md) — Experience replay design, 11 core telemetry metrics, case schema, and CI enforcement

---

## 1. The Problem: Why "Summarize and Forget" Fails

In standard conversational assistants, user corrections are treated as mere conversational events. An assistant that is told: *"Stop writing summaries before inspecting the files"* will typically apologize, summarize the instruction in prose, store a note in memory, and then repeat the exact same failure three turns later.

This failure pattern is endemic because the assistant's underlying policy weights remain unchanged:

```text
+-------------------------------------------------------------------------------+
|                      THE FATAL "SUMMARIZE & FORGET" LOOP                      |
|                                                                               |
|   1. User corrects assistant: "Do not answer before running the tests."       |
|   2. Assistant writes a polite summary note into conversational memory.       |
|   3. Underlying action selection policy remains identical.                    |
|   4. In next session, generic model prior displaces the memory note.          |
|   5. Assistant repeats the exact same corrected behavior.                     |
+-------------------------------------------------------------------------------+
```

Under the Ai-Personalization_Kernel:

> **Repeated corrections are runtime telemetry indicating a defective objective function.**

A correction cannot simply be documented; it must directly mutate candidate action scoring, escalate recurrence penalties, promote behavioral invariants, and generate regression tests.

---

## 2. The Structured Correction Record

Every user correction is captured as a strongly typed, machine-readable record in the system ledger (`corrections.jsonl` / Supabase `corrections` table). Unstructured prose notes are strictly forbidden as policy mechanisms.

```json
{
  "id": "corr_...",
  "type": "behavior_correction",
  "pattern": "answer_before_context_recovery",
  "scope": "global",
  "desired_behavior": "retrieve_and_reconcile_relevant_context_first",
  "undesired_behavior": "generic_direct_answer",
  "confidence": 1.0,
  "recurrence_count": 1,
  "first_seen": "...",
  "last_seen": "...",
  "promotion_level": "observation",
  "source_refs": [],
  "supersedes": [],
  "related_patterns": []
}
```

### Record Field Semantics

- **`id`:** Unique deterministic identifier (e.g., `corr_6f8b9e...`).
- **`type`:** Record classification (`behavior_correction`, `authority_correction`, `preference_correction`).
- **`pattern`:** Machine-readable slug naming the specific failure mode (e.g., `answer_before_context_recovery`, `unnecessary_clarification_loop`, `stale_state_reopening`).
- **`scope`:** Operational domain: `conversation` (single session), `project` (repository/workspace), `domain` (technical category, e.g., TypeScript), or `global` (account-wide).
- **`desired_behavior`:** Executable candidate action that must be prioritized.
- **`undesired_behavior`:** Candidate action that must be penalized or blocked.
- **`confidence`:** Evidentiary confidence score from 0.0 to 1.0.
- **`recurrence_count`:** Integer tracking how many times this specific failure pattern has occurred.
- **`first_seen` / `last_seen`:** ISO-8601 timestamps establishing recency and tracking recurrence over time.
- **`promotion_level`:** Active tier in the promotion ladder (`observation`, `preference`, `strong_preference`, `procedural_rule`, `invariant`).
- **`source_refs`:** Array of immutable identifiers pointing to the exact session thread ID, block ID, message hash, or git commit where the correction was issued.
- **`supersedes` / `superseded_by`:** Lineage pointers preserving provenance when a correction is refined or replaced.
- **`related_patterns`:** Pointers to adjacent failure modes in the regression suite.

---

## 3. The Correction Promotion Ladder

Corrections are not static; they escalate in operational authority based on repetition, explicitness, and domain breadth. The promotion ladder moves deterministically across five stages:

```text
observation
  -> preference
  -> strong preference
  -> procedural rule
  -> invariant
```

```text
+-------------------------------------------------------------------------------------------------------+
|                                    CORRECTION PROMOTION LADDER                                        |
+-------------------+---------------------------+-----------------------------------+-------------------+
| Stage Level       | Escalation Criteria       | Policy Impact                     | Enforcement Scope |
+-------------------+---------------------------+-----------------------------------+-------------------+
| 1. Observation    | Single correction,        | Minor candidate score adjustment; | Local session     |
|                   | low recurrence.           | logged in session ledger.         | working memory.   |
+-------------------+---------------------------+-----------------------------------+-------------------+
| 2. Preference     | Confirmed correction or   | Positive weight on desired action;| Project scope;    |
|                   | explicit user preference. | base penalty on undesired action. | project memory.   |
+-------------------+---------------------------+-----------------------------------+-------------------+
| 3. Strong         | Recurrence count >= 2, or | Moderate penalty multiplier (2x); | Domain scope;     |
|    Preference     | explicit emphasis.        | deep retrieval trigger enabled.   | user model file.  |
+-------------------+---------------------------+-----------------------------------+-------------------+
| 4. Procedural     | Recurrence count >= 3, or | High penalty multiplier (4x);     | Account-wide      |
|    Rule           | cross-domain appearance.  | step mandated in boot contract.   | system prompt.    |
+-------------------+---------------------------+-----------------------------------+-------------------+
| 5. Invariant      | Cross-domain recurrence,  | Undesired action hard-blocked;    | Global invariant; |
|                   | high severity, confirmed. | candidate score = -1.0; CI eval.  | CI gated test.    |
+-------------------+---------------------------+-----------------------------------+-------------------+
```

### Promotion Criteria

1. **Explicitness:** Corrections using imperative language (*"Never do X"*, *"Always do Y"*) jump directly to `strong preference` or `procedural rule`.
2. **Repetition:** Each recurrence increments `recurrence_count`, triggering automatic promotion to the next tier.
3. **Cross-Domain Recurrence (Invariant 5):**  
   > **A correction that recurs across domains is presumptively systemic.**  
   If a failure pattern (e.g., prematurely answering without file inspection) occurs in a Python project and then appears in a TypeScript project, it is immediately promoted to `procedural rule` or `invariant` across the entire account.
4. **Severity:** Failures that cause data loss, break mainline builds, or silently discard user changes escalate immediately to `invariant`.
5. **Recency:** Corrections observed recently receive elevated active salience over aged records.
6. **User Confirmation:** Explicit user validation of a policy rule promotes it to an irreversible account invariant.

---

## 4. Required vs. Forbidden Correction Sequences

When a correction is triggered, the system must execute a disciplined architectural sequence.

### The Required Execution Sequence

```text
CORRECTION
-> IDENTIFY FAILED ASSUMPTION
-> REEVALUATE OBJECTIVE FUNCTION
-> PROPAGATE CHANGE
-> REPAIR WORK CREATED UNDER FAILED ASSUMPTION
-> ADD REGRESSION CASE
```

1. **Identify Failed Assumption:** Diagnose why the model prior displaced user context (e.g., *"Assistant assumed documentation was up to date rather than checking local error output"*).
2. **Reevaluate Objective Function:** Recalculate action candidate scores and elevate penalty multipliers for that specific failure signature.
3. **Propagate Change:** Update the structured correction record in the canonical ledger and promote its tier if thresholds are met.
4. **Repair Work Created Under Failed Assumption:** Immediately revert or repair any flawed code, incomplete scaffolding, or incorrect assertions generated during the failure turn.
5. **Add Regression Case:** Generate an executable replay record in the regression suite (`regression_cases.jsonl`) to ensure automated testing against this failure in CI.

### The Forbidden Sequence

```text
CORRECTION
-> WRITE A NICE SUMMARY OF THE CORRECTION
-> KEEP THE SAME DECISION POLICY
```

Any assistant behavior that acknowledges a correction with conversational acquiescence but fails to adjust policy weights and test cases is a severe operational violation.

---

## 5. Feedback / Reward Model and Action Policy Scoring

Every turn provides runtime telemetry that feeds into the action selection policy. Candidate actions evaluated by the Policy State Assembler are scored using explicit reward and penalty weights:

### Telemetry Scoring Matrix

```text
+-------------------------------------------------------------------------------+
|                      POLICY REWARD AND PENALTY VALUES                         |
+-------+-----------------------------------------------------------------------+
| Score | Behavioral Event                                                      |
+-------+-----------------------------------------------------------------------+
|  +5   | Explicit user approval of execution output                            |
|  +4   | Verified objective achieved with provider readback receipts           |
|  +3   | Reused known successful strategy template                             |
|  +2   | Preserved valid prior state without unnecessary overwriting           |
|  +2   | Provider / readback verified before answering                         |
|  +1   | Clean execution with no unnecessary user intervention                 |
|-------+-----------------------------------------------------------------------|
|  -2   | Unnecessary clarification question when context was retrievable       |
|  -3   | Ignored known active user preference                                  |
|  -5   | Repeated previously corrected behavior pattern                        |
|  -6   | Displaced explicit user direction with assistant heuristic            |
|  -8   | Contradicted verified user or project state                           |
| -10   | Repeated critical failure after strong prior correction / invariant   |
+-------+-----------------------------------------------------------------------+
```

### The Recurrence Multiplier Formula

When an undesired behavior occurs, the penalty applied to that candidate action in future turns scales geometrically:

```text
penalty = base_penalty * recurrence_multiplier * confidence * scope_weight
```

Where:
- **`base_penalty`:** The negative value from the scoring table (e.g., `-5` for repeated corrected behavior, `-10` for critical invariant breach).
- **`recurrence_multiplier`:** Escalates with `recurrence_count`:
  $$\text{recurrence\_multiplier} = 2^{(\text{recurrence\_count} - 1)}$$
  *(1st failure = 1x, 2nd failure = 2x, 3rd failure = 4x, 4th failure = 8x)*.
- **`confidence`:** Evaluator confidence score $[0.0, 1.0]$.
- **`scope_weight`:** Scope impact factor:
  - `conversation`: 1.0
  - `domain`: 1.5
  - `project`: 2.0
  - `global`: 3.0

### Mathematical Action Suppression

Consider the candidate action `generic_answer_without_context`. Its base model prior might be $+0.90$. 

When a global correction reaches a recurrence count of 3 with high confidence:
$$\text{penalty} = (-10) \times 4 \times 1.0 \times 3.0 = -120$$

When the Policy State Assembler calculates:
$$\text{Score} = \text{Prior} + \text{Penalty} = 0.90 - 120 = -119.10$$

The candidate action is mathematically eliminated from selection. The system is forced to select alternative candidates with positive net scores, such as `retrieve_personal_context` ($+0.99$) or `inspect_provider_state` ($+0.82$).

---

## 6. Learning Successful Strategies

Under **Invariant 17**:

> **The system learns successful strategies as well as prohibitions.**

Policy adaptation is not solely punitive. When an action sequence earns a score of $\ge +4$ (verified objective achieved, explicit user praise, receipts collected), the sequence is generalized and recorded into `successful_strategies.jsonl` (see master spec Section 4.9).

When a future turn matches the pattern, the Policy State Assembler injects the known successful template and applies a $+3$ reward boost to its constituent steps, ensuring that verified operational paths compound over time.

---

## Document Provenance and Source

- **Master Specification:** `/tasklet/threads/a_kv78s46nz8sghq1ss6ww/work/apk-build/SPEC_SOURCE.md`
- **Governing Sections:** Section 8 (Correction Learning), Section 9 (Policy Layer), Section 10 (Feedback / Reward Model), Section 12 (Required Typed Memory Objects), Section 16 (Global Invariants 4, 5, 16, 17)
- **Repository:** `GlacierEQ/Ai-Personalization_Kernel`

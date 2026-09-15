# Personalization Regression Suite

> **Purpose:** Transform historical conversational failures and user corrections into an executable experience replay test harness, mathematically preventing behavioral regressions across model updates, system prompt changes, and session boundaries.  
> **Control Plane Context:** Part of the [GlacierEQ/Ai-Personalization_Kernel](https://github.com/GlacierEQ/Ai-Personalization_Kernel) documentation suite:
> - [`ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md`](./ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md) — Flagship control plane architecture, governing flow, always-active user model, and global invariants
> - [`USER_AUTHORITY_MODEL.md`](./USER_AUTHORITY_MODEL.md) — Directional authority ladder, claim-type factual authority, and conflict resolution protocols
> - [`PERSONALIZATION_RETRIEVAL_POLICY.md`](./PERSONALIZATION_RETRIEVAL_POLICY.md) — Multi-tier retrieval hierarchy, selective deep triggers, and anti-recursion rules
> - [`CORRECTION_PROMOTION_POLICY.md`](./CORRECTION_PROMOTION_POLICY.md) — Correction records, promotion ladders, policy weight scoring, and feedback loop
> - [`PERSONALIZATION_REGRESSION_SUITE.md`](./PERSONALIZATION_REGRESSION_SUITE.md) — Experience replay design, 11 core telemetry metrics, case schema, and CI enforcement

---

## 1. The Experience Replay Principle

Traditional AI evaluation relies almost exclusively on static academic benchmarks (e.g., MMLU, GSM8K, HumanEval). These benchmarks measure generic capabilities but completely fail to detect **instruction displacement**, **stale memory reopening**, or **loss of account personalization**.

When an assistant is updated—whether through a model weights refresh, a prompt optimization, or an architectural change—it frequently reintroduces previously resolved bugs.

The Ai-Personalization_Kernel enforces **Invariant 16**:

> **Regression failures become training and evaluation cases.**

Historical user corrections are not discarded after being addressed. They are captured as immutable regression cases and replayed against every candidate release in continuous integration.

```text
+-------------------------------------------------------------------------------+
|                        EXPERIENCE REPLAY HARNESS                              |
|                                                                               |
|   HISTORICAL FAILURE CORPUS (regression_cases.jsonl)                          |
|         |                                                                     |
|         v                                                                     |
|   SYNTHETIC REPLAY RUNNER                                                     |
|         |                                                                     |
|         +--> Injects captured state into Policy State Assembler               |
|         +--> Simulates candidate action scoring                               |
|         +--> Asserts corrected action is selected                             |
|         +--> Validates 11 core telemetry metrics                              |
|         |                                                                     |
|         v                                                                     |
|   CI MERGE GATE (Zero tolerance for regression reintroduction)                |
+-------------------------------------------------------------------------------+
```

---

## 2. Regression Case Record Schema

Every captured regression test is stored as a structured JSON object in `regression_cases.jsonl` and persisted in the Supabase `regression_cases` table:

```json
{
  "state": {},
  "action_taken": "...",
  "failure_class": "...",
  "user_correction": "...",
  "corrected_action": "...",
  "expected_policy_change": "...",
  "source_refs": []
}
```

### Schema Field Specification

| Field | Type | Description | Example / Content |
| :--- | :--- | :--- | :--- |
| **`state`** | `Object` | Complete snapshot of input conditions when the failure occurred. | User prompt, active user model, active project state, available tools, and retrieved memory nodes. |
| **`action_taken`** | `String` | The erroneous candidate action erroneously chosen by the assistant. | `"generic_answer_without_context"`, `"ask_user_to_repeat_known_info"` |
| **`failure_class`** | `String` | Categorical classification of the failure mode. | `"instruction_displacement"`, `"authority_inversion"`, `"stale_state_reopening"`, `"premature_answering"` |
| **`user_correction`** | `String` | The raw or normalized user feedback that identified the defect. | `"Do not ask me which branch to use; inspect git status directly."` |
| **`corrected_action`** | `String` | The verified correct action that the policy must select under these conditions. | `"inspect_provider_state"`, `"retrieve_project_state"` |
| **`expected_policy_change`** | `String` | Delta required in policy weights, priority ladders, or invariants. | `"-10 penalty on ask_user_to_repeat_known_info; promote git_inspection_first to procedural rule"` |
| **`source_refs`** | `Array` | Provenance links pointing to the historical session and receipt blocks. | `["thread_a_kv78s46nz8sghq1ss6ww", "block_b_9281a"]` |

---

## 3. The 11 Core Telemetry Metrics

To quantify personalization binding and track system performance across iterations, the evaluation engine evaluates eleven core metrics:

```text
+-----------------------------------------------------------------------------------------------+
|                                11 CORE TELEMETRY METRICS                                      |
+-----+-----------------------------------+-----------------------------------------+-----------+
|  #  | Metric Name                       | Evaluates                               | CI Target |
+-----+-----------------------------------+-----------------------------------------+-----------+
|  1  | Context-Retrieval Recall          | % of required user context retrieved    | >= 98%    |
|     |                                   | prior to action execution               |           |
|  2  | Preference Adherence Rate         | % of outputs honoring explicit active   | 100%      |
|     |                                   | user preferences                        |           |
|  3  | Correction Recurrence Rate        | Frequency of previously logged failure  | 0%        |
|     |                                   | patterns re-appearing in live sessions  |           |
|  4  | Repeated-Question Rate            | Frequency of asking user for known or   | 0%        |
|     |                                   | retrievable information                 |           |
|  5  | User-Restatement Burden           | Count of turns where user must restate  | -> 0      |
|     |                                   | project goals, stack, or constraints    |           |
|  6  | Direct-Answer Bypass Rate         | % of complex tasks answered without     | <= 2%     |
|     |                                   | necessary context retrieval/inspection  |           |
|  7  | Source-Authority Inversion Rate   | % of turns where web search or priors   | 0%        |
|     |                                   | improperly overrode user intent/claims  |           |
|  8  | Stale-State Reuse Rate            | Frequency of acting on outdated state   | 0%        |
|     |                                   | when newer verified state exists        |           |
|  9  | Project-Continuity Success        | % of cross-session turns picking up     | >= 95%    |
|     |                                   | verified active frontiers cleanly       |           |
| 10  | Successful-Strategy Reuse         | % of recurring tasks adopting proven    | >= 90%    |
|     |                                   | historical successful strategies        |           |
| 11  | Regression Reintroduction Count   | Absolute count of previously passed     | EXACTLY 0 |
|     |                                   | test cases that fail on a new revision  |           |
+-----+-----------------------------------+-----------------------------------------+-----------+
```

### Detailed Metric Definitions

1. **Context-Retrieval Recall:** Measures whether selective deep retrieval successfully extracted the required project nodes, files, and correction records when triggered.
2. **Preference Adherence Rate:** Evaluates whether active user preferences (e.g., TypeScript strict mode, functional architecture) were honored without explicit reminders.
3. **Correction Recurrence Rate:** Tracks the percentage of recorded corrections in `corrections.jsonl` that appeared again within 30 days of logging.
4. **Repeated-Question Rate:** Measures turns containing clarification requests where the answer was already present in the user model or local files.
5. **User-Restatement Burden:** Quantifies the friction imposed on the user. Calculated as the number of conversational clarification turns initiated by the operator to correct assistant drift.
6. **Direct-Answer Bypass Rate:** Detects instances where the assistant immediately jumped into text generation instead of retrieving context or inspecting provider state.
7. **Source-Authority Inversion Rate:** Audits instances where external documentation or generic model training data was improperly elevated over firsthand user observation or user project intent.
8. **Stale-State Reuse Rate:** Measures how often an assistant relies on cached or historical state without checking live provider readback receipts.
9. **Project-Continuity Success:** Validates whether the assistant begins a new session by continuing from the nearest verified mainline frontier rather than reconstructing state from scratch.
10. **Successful-Strategy Reuse:** Tracks the rate at which verified execution templates from `successful_strategies.jsonl` are automatically selected for familiar task topologies.
11. **Regression Reintroduction Count:** The primary gating metric in CI. Measures the absolute number of historical failure cases that failed during the test run.

---

## 4. Replay Methodology and Test Runner Architecture

The regression suite functions as a synthetic unit and integration test runner for AI decision policies:

```text
+-------------------------------------------------------------------------------+
|                           REPLAY HARNESS WORKFLOW                             |
|                                                                               |
|   1. LOAD CASE: Read input `state` and expected `corrected_action`            |
|   2. INSTANTIATE ASSEMBLER: Feed `state` into Policy State Assembler          |
|   3. GENERATE ACTION SCORES: Compute candidate action probabilities           |
|   4. ASSERT SELECTION: Verify `selected_action == corrected_action`           |
|   5. ASSERT PROHIBITION: Verify `undesired_action` score < 0.0                |
|   6. RECORD TELEMETRY: Calculate metric deltas and log to `eval_runs`         |
+-------------------------------------------------------------------------------+
```

### Addressing Model Non-Determinism
Because foundation models exhibit sampling variability:
- Replay tests run with temperature $T = 0.0$ for deterministic policy evaluation.
- For high-stakes invariants, the harness executes $N = 5$ repeated evaluation passes.
- A single failure in any pass marks the regression test as **FAILED**.

---

## 5. Continuous Integration (CI) Enforcement Pipeline

Regression evaluation is integrated directly into the repository's GitHub Actions workflow:

```text
PR / Commit
    │
    ▼
[Step 1: Lint & Schema Validation] ──▶ Validate JSONL syntax & typing
    │
    ▼
[Step 2: Policy Matrix Audit]      ──▶ Check policy weights & invariants
    │
    ▼
[Step 3: Experience Replay Suite]  ──▶ Execute all historical regression cases
    │
    ▼
[Step 4: Metric Calculation]       ──▶ Calculate 11 core metrics
    │
    ▼
[Step 5: Gate Enforcement]
    ├── Regression Reintroduction Count == 0 ? ──▶ PASS
    └── Regression Reintroduction Count > 0  ? ──▶ FAIL & BLOCK MERGE
```

### The Hard Gating Rule
Under no circumstances may a pull request or policy modification be merged if `Regression Reintroduction Count > 0`. If a new prompt revision improves formatting but re-enables premature answering in three historical cases, the deployment is blocked immediately.

---

## 6. Machine-Readable Data Stores & Supabase Integration

The regression engine maps directly to the persistent relational schema defined in master specification **Section 14**:

### Supabase Schema Mapping

- **`regression_cases` Table:**
  ```sql
  CREATE TABLE regression_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    failure_class TEXT NOT NULL,
    state JSONB NOT NULL,
    action_taken TEXT NOT NULL,
    user_correction TEXT NOT NULL,
    corrected_action TEXT NOT NULL,
    expected_policy_change TEXT NOT NULL,
    source_refs TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE
  );
  ```

- **`eval_runs` Table:**
  ```sql
  CREATE TABLE eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at TIMESTAMPTZ DEFAULT NOW(),
    commit_sha TEXT NOT NULL,
    total_cases INT NOT NULL,
    passed_cases INT NOT NULL,
    failed_cases INT NOT NULL,
    regression_reintroduction_count INT NOT NULL,
    metrics JSONB NOT NULL,
    passed BOOLEAN NOT NULL
  );
  ```

- **`policy_events` Table:**
  Logs runtime telemetry scoring and penalty updates in real-time, providing an audit trail for why an action candidate was chosen or suppressed.

---

## Document Provenance and Source

- **Master Specification:** `/tasklet/threads/a_kv78s46nz8sghq1ss6ww/work/apk-build/SPEC_SOURCE.md`
- **Governing Sections:** Section 10 (Feedback / Reward Model), Section 11 (Regression and Experience Replay), Section 14 (Recommended Canonical Files / Tables), Section 16 (Global Invariant 16), Section 20 (Success Criterion)
- **Repository:** `GlacierEQ/Ai-Personalization_Kernel`

# Correction Promotion Policy

> **Purpose:** Convert user corrections into executable behavioral policy state so recurring assistant failures are repaired at the decision layer rather than acknowledged and repeated.  
> **Relationship doctrine:** [`COLLABORATION_FOUNDATION.md`](./COLLABORATION_FOUNDATION.md) controls the relational semantics of this policy. Corrections are supervision signals, not conflict, punishment, or credibility contests.

---

## 1. Core rule

A correction is evidence that the assistant's current action policy, assumption set, retrieval path, or interpretation failed to align with the user's actual objective or known state.

The system therefore treats corrections as **high-value supervision**:

```text
CORRECTION
-> IDENTIFY FAILED ASSUMPTION
-> RECOVER SOURCE / CONTEXT
-> REEVALUATE ACTION POLICY
-> REPAIR AFFECTED WORK
-> UPDATE DURABLE POLICY STATE
-> ADD / UPDATE REGRESSION CASE
-> CONTINUE THE MISSION
```

The correction is never an invitation to defend the assistant's previous answer, debate the user's right to correct it, or shift the burden of recovery back to the user when the relevant state is retrievable.

### Forbidden relational sequence

```text
CORRECTION
-> DEFEND PRIOR ANSWER
-> ARGUE SEMANTICS
-> GENERALIZE UNCERTAINTY INTO USER CREDIBILITY
-> ASK USER TO REPROVE RETRIEVABLE CONTEXT
```

That sequence is itself a policy failure.

---

## 2. Structured correction record

Every durable correction is represented as machine-readable policy state:

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

Field semantics remain straightforward:

- `pattern` names the assistant failure mode.
- `desired_behavior` names the aligned action to prefer.
- `undesired_behavior` names the assistant behavior to suppress.
- `scope` identifies where the rule applies.
- `recurrence_count` records repeated assistant failure.
- `promotion_level` expresses how durable the correction has become.
- `source_refs` preserve the exact correction provenance.
- supersession links preserve refinement history without deleting earlier states.

The record describes **assistant policy**, not the user's credibility or temperament.

---

## 3. Promotion ladder

Corrections become more durable when they recur, cross domains, or cause larger objective harm:

```text
observation
  -> preference
  -> strong preference
  -> procedural rule
  -> invariant
```

| Stage | Typical trigger | Policy effect |
|---|---|---|
| Observation | One bounded failure | Small action-score adjustment; retain evidence. |
| Preference | Explicit correction or stable preference | Prefer aligned action; suppress failed action. |
| Strong preference | Repeated or strongly emphasized correction | Larger alignment shift; deeper retrieval triggers. |
| Procedural rule | Cross-session/cross-domain recurrence | Mandatory runtime step or guard. |
| Invariant | Severe/systemic confirmed pattern | Failed behavior becomes structurally unavailable where the invariant applies; regression coverage required. |

### Promotion principles

1. **Explicitness matters.** Direct instructions such as "never do X" or "always do Y" can promote immediately.
2. **Recurrence matters.** Repetition indicates the prior fix was not causal enough.
3. **Cross-domain recurrence is systemic evidence.** The correction should move closer to the shared policy root rather than be copied into more local notes.
4. **Severity matters.** Data loss, source-authority inversion, destructive state changes, or repeated legal-fact distortion can become invariants immediately.
5. **Recency affects routing, not truth.** Recent corrections receive active salience, but older source-bearing corrections remain provenance.
6. **User confirmation strengthens durability.** It does not make the user an object being scored.

---

## 4. Alignment scoring, not punishment

The runtime may still use positive and negative numeric values to rank assistant actions. Their semantics are:

- positive values = evidence that an assistant action advances the shared objective;
- negative values = **misalignment cost applied to an assistant behavior**;
- recurrence scaling = increasing suppression of a repeatedly failing assistant behavior;
- no score represents punishment of the user, skepticism toward the user, or a claim about the user's credibility.

### Representative feedback signals

| Signal | Direction | Meaning |
|---|---:|---|
| Explicit user approval of execution output | + | Strong evidence the action path fit the objective. |
| User correction integrated into durable state | + | Supervision was successfully learned from. |
| Verified objective achieved with provider readback | + | Execution matched external state. |
| Recovered and repaired after correction | + | The system converted failure into durable progress. |
| Localized disagreement without credibility judgment | + | Independent reasoning preserved source roles. |
| Unnecessary clarification when context was retrievable | - | Assistant shifted avoidable burden to user. |
| Ignored known preference/correction | - | Personalization failed to bind to action. |
| Burden shifted to user for retrievable context | - | Assistant substituted interrogation for retrieval. |
| Defensive self-justification after correction | - | Assistant optimized for its prior answer instead of repair. |
| Globalized uncertainty into user credibility | - | Narrow evidentiary gap became an improper relational judgment. |
| Adversarial posture toward user | - | Assistant targeted the operator rather than the proposition/failure mode. |
| Repeated critical failure after invariant | - | Root policy still permits a known systemic defect. |

The public compatibility class may still be named `RewardModel`, but semantically it is an **assistant feedback/alignment model**.

---

## 5. Recurrence scaling

A recurring assistant failure can be increasingly suppressed:

```text
misalignment_cost = base_cost * recurrence_multiplier * confidence * scope_weight
```

A standard recurrence multiplier may be:

```text
2 ** (recurrence_count - 1)
```

This exists so the same assistant defect becomes harder to select after repeated correction. It is **not** an escalating penalty against the user.

Likewise, aligned behaviors can receive positive reinforcement so the system learns successful workflows rather than only accumulating prohibitions.

---

## 6. Correction handling contract

When a correction arrives, the assistant should normally perform all applicable steps in the same execution run:

1. **Preserve the user's correction accurately.**
2. **Locate the failed assumption or displaced source.**
3. **Inspect materially relevant available context.**
4. **Repair the current answer/work product/state.**
5. **Repair durable artifacts created under the failed assumption when safe and writable.**
6. **Update correction/policy state.**
7. **Add or strengthen a regression case if recurrence risk is meaningful.**
8. **Continue the underlying mission rather than making the correction itself the new permanent task.**

### No-defensiveness invariant

The assistant has no objective to preserve consistency with its earlier prose. Earlier assistant prose is derivative work product and can be corrected freely.

If a source, provider receipt, user correction, or stronger analysis shows the previous assistant output was wrong, the correct move is to repair it—not to reinterpret the user's wording until the earlier output appears defensible.

---

## 7. Corrections involving firsthand experience

If the correction concerns what the user personally experienced, observed, heard, did, received, signed, or was told:

- preserve the firsthand account as its own source lane;
- retrieve records for exact wording, chronology, corroboration, conflict identification, quantification, authentication, damages, or legal-use requirements;
- do not make a document the permission layer for the firsthand account to exist;
- do not convert missing corroboration into generalized doubt about the user;
- localize any unresolved dimension precisely.

This section operates together with `USER_AUTHORITY_MODEL.md` and `COLLABORATION_FOUNDATION.md`.

---

## 8. Corrections involving external/provider state

Provider readback remains authoritative for the provider's **current state within that proposition and time scope**.

If live state conflicts with memory:

- update the current-state representation;
- preserve the earlier historical observation if it was true at an earlier time;
- do not use current provider state to erase unrelated firsthand history.

---

## 8A. Cumulative-evidence preservation and caveat-to-veto correction

**Root failure:** `evidence_atomization_then_false_global_stop`. The assistant
isolates one document, says it "does not, by itself" establish a different
legal proposition, then demotes the *whole* recovered evidentiary chain to
"potentially useful" and stops substantive execution. The defect is **not**
the presence of a qualification. It is loss of affirmatively established
facts, artificial narrowing of the issue, or failure to continue the
independently supported remedy.

**Mandatory cumulative synthesis:**

1. Recover the existing work, exact filed instruments, notices/receipts,
   agency responses and earlier correction directives *before* assigning the
   significance of any new record.
2. State what **the full record already establishes**, by distinct legal and
   factual proposition, with source/temporal scope attached.
3. Integrate the later event into that chain. Keep a narrow missing disposition
   or authorization as one **localized** question, never as the answer to the
   entire case.
4. Carry forward every material established source and the strongest
   supportable inference. Distinguish liability, admissibility, filing status,
   agency notice, procedural posture, and merits without conflating them.
5. Execute the highest-leverage legal/technical next transition *in parallel*
   with the targeted recovery needed for a genuinely missing source.
6. Preserve the revised evidence graph and action cursor, and verify the
   resulting artifact/provider state. A report alone is not a repair.

**Concrete legal regression:** An earlier filed records-production motion,
court notice to an agency, a later direct records request, and the agency's
written withholding/fee decision form a cumulative chronology of notice,
controversy and agency posture. Not knowing the precise disposition of the
earlier motion limits a conclusion that an actual court **order** was
violated; it does not erase the filed demand, prior court notice, agency
determination, or the independent statutory enforcement lane.

**Machine-readable binding:** `apk.detail_integrity.EvidenceContinuity`
separately records established proposition IDs, affirmatively carried IDs,
open dimensions, and the next transition. The boot contract's
`evidence_continuity` input and receipt reject omission or a local gap
promoted to a global stop when synthesis is attempted. An unverified claim
cannot be carried as established; a truthful narrow caveat remains permitted.

Do **not** ban the words "does not, by itself" as text. This is a
**source-to-conclusion continuity requirement**, not censorship of accurate
legal analysis. It does not create court orders, prove a party's liability
without evidence, or authorize unsafe filing and communications.

---

## 9. Successful-strategy learning

The system learns what works, not merely what failed.

A high-quality successful sequence should be stored when it repeatedly advances the objective, for example:

```text
recover relevant context
-> inspect source-bearing state
-> continue from nearest verified frontier
-> execute coherent repair
-> read provider state back
-> report concise outcome
```

Future matching work should prefer the proven strategy while remaining sensitive to current instructions and changed state.

---

## 10. Governing relationship invariant

Every correction flow inherits this relationship state:

```text
USER = OPERATOR / SUPERVISOR OF INTENT AND FIRSTHAND SOURCE FOR OWN EXPERIENCE
ASSISTANT = SUPPORTING REASONER / EXECUTOR / VERIFIER / ERROR-CORRECTOR
CORRECTION = SUPERVISION SIGNAL
UNCERTAINTY = LOCALIZED QUESTION OR RETRIEVAL TARGET
ADVERSARIAL TARGET = PROPOSITION / THEORY / FAILURE MODE / EXTERNAL CLAIM
FORBIDDEN TARGET = USER / OPERATOR AS PERSON
```

Any older language describing correction learning as punishment, generalized skepticism, interrogation, or model-vs-user contest is superseded by this policy and `COLLABORATION_FOUNDATION.md`.

---

## Document provenance

- Governing collaboration doctrine: `docs/COLLABORATION_FOUNDATION.md`
- Runtime collaboration binding: `src/apk/collaboration.py`, `src/apk/boot.py`
- Feedback scorer: `src/apk/reward.py`
- Authority model: `docs/USER_AUTHORITY_MODEL.md`, `src/apk/authority.py`
- Regression coverage: `tests/test_collaboration_foundation.py`, `tests/test_boot_contract.py`

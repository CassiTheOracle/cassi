# Generative Abstraction Upgrade

**Status:** Designed from measured relational stress behavior — 2026-08-31

## Scope

This note designs the next standalone CassiFI mechanism after the measured
field-selected relational-basis fixture. The current fixture performs
field-owned selection among a finite set of hand-specified observables. The
upgrade makes the field generate new observable programs by composing a fixed,
typed primitive alphabet, evaluate those programs from raw executions, retain
their evidence in `QiFieldState`, and consolidate useful programs into reusable
field basins.

The intended claim is bounded and testable:

> The field generates and retains typed abstraction programs whose composed
> transformations predict held-out consequences better than their constituent
> raw observables.

This is not unrestricted representation learning. The primitive alphabet,
interpreter, type rules, work bounds, and sensor precision remain fixed. The
adaptive program evidence, selected program, regime support, and learned
transition operators live only in `QiFieldState.field`.

Live provider routing is outside this design. The mechanism remains standalone
until its generated programs survive the same multi-world controls that exposed
the current limitations.

## Measured starting point

`run_learned_relational_basis.py` established the useful baseline:

- field-owned selection among four hand-specified bases chose
  `target_minus_self` with score `0.003584760230488662` and margin
  `0.41866866441769546`;
- 32/32 unseen, renamed worlds reached exact revisions when both intermediate
  relational constraints were supplied;
- 16 entity-order permutations and 32 interventional role bindings succeeded;
- checkpoint replay was exact, inference left the field unchanged, evidence
  removal forced `no_eligible_basis`, and required-operator removal forced
  `exhausted`;
- four unseen boundary clamps remained unsupported at residual
  `0.06150250405167158` against tolerance `0.04`.

`run_relational_stress_tests.py` then changed one assumption at a time:

| Surface | Measured behavior |
|---|---|
| Moving target, two intermediate constraints | 24/24 exact revisions through target speed `0.018` |
| Moving target, one intermediate constraint | 0/24 settled or exact |
| Moving target, endpoint only | 0/24 settled or exact |
| Stationary endpoint-only control | 0/24 settled or exact |
| Coordinate noise amplitude `0.0`, `0.002`, `0.01` | 16/16 exact at each amplitude |
| Noise `0.015`, `0.02`, `0.025`, `0.03`, `0.06` | 13, 9, 4, 1, 0 exact revisions out of 16 |
| Dynamically distinguishable distractors | 24/24 relevant objects selected |
| Indistinguishable hidden relevance | 6/16 coincidental choices, 10/16 false confident choices, 0 abstentions |
| Passive role probe across four quadrants | 8 correct, 8 wrong, 16 abstentions |
| Interventional role probe across four quadrants | 24/32 correct; the southwest quadrant was 0/8 |
| Expanded basis evidence | `distance_bearing` selected over Cartesian relative coordinates by only `0.0012329334141353149` |
| Boundary composition after boundary-inclusive training | 0/12 exact for every candidate |
| Selected distance/bearing boundary plans | 12/12 false settlements |

The stress field also replayed exactly, remained unchanged during inference,
and lost the required trajectory after operator ablation. No teacher, model, or
provider path participated.

## What the measurements mean

### Endpoint completion is underdetermined

The endpoint-only failures also occur for a stationary target. They therefore do
not establish a moving-target deficit by themselves. Interior translations
commute: several ordered action paths can reach the same endpoint. An endpoint
does not contain the hidden historical order, and the current solver correctly
refuses a unique settlement when the path distribution stays ambiguous.

A generative mechanism must distinguish two requests:

1. **Historical reconstruction:** return `ambiguous` when observations do not
   identify the original ordering.
2. **Prospective synthesis:** return an outcome-equivalent trajectory class and
   a deterministic representative when any member is acceptable.

It must not pretend that a canonical representative recovers an unobserved
history.

### Small coordinate noise is tolerated; exact anchoring creates a cliff

The unchanged field retained all exact revisions through noise amplitude
`0.01`, then declined monotonically from 13/16 at `0.015` to 0/16 at `0.06`.
The planner generally retained the expected basin sequence longer than it
retained settlement. This indicates that hard point anchors, rather than action
identity alone, drive the robustness cliff.

Generated abstractions therefore need fixed sensor-precision envelopes and
worst-case or interval residuals. Random sampling and a learned uncertainty head
would add unnecessary state and are not part of the design.

### Dynamic relevance is observable; hidden relevance is not

Four-step consequences separated one stationary target from moving distractors
in 24/24 cases. When three objects had indistinguishable dynamics and the
relevant index was intentionally absent from the observation, the current
residual rule still selected one object every time and was wrong 10/16 times.

The upgrade must preserve equivalence when multiple entities have the same
observable transition signature. Relevance that is not present in observation,
goal, action consequence, or Thalamus eligibility remains unresolved. Residual
noise must not manufacture semantic identity.

### Passive role assignment learned a support prior

The original positive-quadrant fixture made one role orientation look familiar.
Across balanced quadrants, the passive inverse-cycle probe was correct only in
the northeast quadrant, abstained in two quadrants, and confidently reversed
all eight southwest cases. One intervention corrected three quadrants but still
failed southwest because that orientation was absent from operator training.

Generated role bindings must remain a role-swap equivalence class until a causal
observation separates the hypotheses. Interventional training must cover the
symmetry group rather than reinforce one geometric prior.

### Local evidence did not certify downstream composition

With boundary examples included, the expanded field selected
`distance_bearing` by a narrow margin. That basis then settled all 12 boundary
plans onto incorrect trajectories. Cartesian relative and boundary-context
candidates also reached 0/12 exact revisions.

Closure, inverse, local composition, invariance, collision, and one-step
boundary residual are necessary evidence, but they are not sufficient evidence
for a generated abstraction. Promotion must also depend on downstream
consequence agreement across held-out regimes. A small scalar score advantage
cannot override zero exact composed outcomes.

## Design invariants

1. `QiFieldState.field` remains the sole adaptive persistent object.
2. The caller supplies raw observations, actions, outcomes, masks, and declared
   sensor precision. It never supplies a basis score, program verdict, latent
   vector, or selected role.
3. The primitive alphabet, interpreter, type checker, canonicalizer, and work
   limits are deterministic and nonadaptive.
4. Entity and action identifiers may group evidence but do not become generated
   numeric features. An identity-hash primitive exists only in explicit negative
   controls.
5. Generated programs, their evidence, regime support, operator moments, and
   consolidation metadata occupy field coordinates and survive exact restart.
6. Inference does not mutate the trained field unless consolidation is
   explicitly requested after a real observed outcome.
7. Equivalent programs, entities, roles, and trajectories remain equivalence
   classes until observation distinguishes them.
8. No Qwen call, learned embedding, neural denoiser, optimizer, trainable codec,
   sidecar policy, adaptive host cache, or model fallback participates.
9. External actions remain proposals. This standalone mechanism does not execute
   consequential tools or alter live provider routing.

## Core mechanism: typed field program synthesis

An abstraction is a bounded typed postfix program evaluated by a fixed
interpreter. A program maps a short raw observation history, a role hypothesis,
and an action into four complex coordinates compatible with the existing
bilateral operator learner:

\[
z_t=P(a_{t-k:t},\rho,u_t)\in\mathbb C^4.
\]

A four-coordinate bundle ends with `PACK4`. Postfix form makes generated trees a
linear sequence, so the existing whole-trajectory counterflow machinery can
construct them without a second tree-search subsystem.

### Fixed primitive alphabet

The first implementation uses only primitives needed by the measured failures:

| Type | Fixed leaves and operators |
|---|---|
| Entity/role | `ROLE_A`, `ROLE_B`, `EACH_OBJECT`, `SWAP_ROLES` |
| Time | `PREVIOUS`, `CURRENT`, `DELTA` |
| Coordinates | `X`, `Y`, `POSITION`, `ACTION_DX`, `ACTION_DY` |
| Geometry | `ADD`, `SUBTRACT`, `MULTIPLY`, `NORM2`, `SQRT`, `NORMALIZE` |
| Boundaries | `LOWER_BOUND`, `UPPER_BOUND`, `MIN`, `MAX`, `CLAMP`, `HEADROOM` |
| Logic | `LESS`, `GREATER`, `SELECT` |
| Constants | `-1`, `0`, `1`, declared action step, declared sensor precision |
| Output | `PACK4` |

The type checker rejects invalid stacks before evaluation. Division and
normalization use fixed zero guards. `SELECT` permits one bounded piecewise
branch in the first implementation. Recursion, loops, arbitrary constants,
identity lookup, and host callbacks are absent.

The initial maximum is 12 postfix tokens per output bundle and one conditional
branch. These are work bounds, not learned capacity. They should change only
when an observed abstraction cannot be expressed within them.

### Canonical programs

A fixed canonicalizer prevents syntactic duplicates from becoming false
alternatives:

- commutative operands are hash-ordered;
- constants are folded;
- double negation and redundant clamps are removed;
- role-swapped forms are retained as one equivalence class when evidence is
  symmetric;
- programs receive a SHA-256 identity over canonical token IDs and fixed
  interpreter version.

The hash is provenance, not learned state. Support and utility for that program
remain in the field.

Examples of programs the grammar can generate include:

```text
ROLE_B POSITION ROLE_A POSITION SUBTRACT

ROLE_B POSITION ROLE_A POSITION SUBTRACT NORM2 SQRT

ROLE_A X ACTION_DX ADD LOWER_BOUND UPPER_BOUND CLAMP
ROLE_A X SUBTRACT
```

The final example contributes to a piecewise boundary-aware update rather than
requiring one global affine operator to approximate clamping.

## Field representation

A dedicated generative configuration extends the existing bilateral field
layout; it does not reinterpret the current relational checkpoint.

Each abstraction basin stores, in field coordinates:

- exact canonical token IDs and program length;
- role-symmetry and regime masks;
- closure, inverse, multi-step, nuisance-invariance, collision, boundary,
  uncertainty, and outcome-consistency sufficient statistics;
- grouped forward and backward operator moments;
- support and consolidation counts;
- constituent program IDs when the abstraction is consolidated as a macro.

Active program slots use the same `QiFieldState` during synthesis. A bounded
host beam may hold transient indices while executing one call, as the current
counterflow solver does, but it is not serialized, learned, or consulted after
restart. Every ranking quantity is read from or deposited into the field.

## Masked counterflow generation

The diffusion inspiration is discrete masked refinement, not Gaussian noise and
not a trained denoising network.

1. **Mask:** initialize each unresolved postfix slot with equal support over the
   type-legal primitive set.
2. **Upward proposal:** forward field resonance proposes token continuations
   supported by observed transition basins.
3. **Downward projection:** desired consequence, type completion, role symmetry,
   sensor interval, and regime constraints propagate backward.
4. **Evaluate:** the fixed interpreter executes surviving programs over raw
   transitions and complete multi-step episodes.
5. **Correct:** the controller derives residuals and deposits reciprocal
   correction into the program basins. The caller supplies no scalar score.
6. **Refine:** each breath suppresses inconsistent tokens and retains coherent
   alternatives.
7. **Settle or preserve ambiguity:** return one canonical program only when its
   field evidence and downstream outcomes separate it. Otherwise return an
   equivalence class or `ambiguous`/`exhausted`.
8. **Consolidate:** after a real outcome confirms the generated program, store
   its token sequence and operator family as a field macro. Failed outcomes
   affect fast active state but do not overwrite the retained abstraction.

For program `P`, the controller derives a field-resident score of the form

\[
J(P)=w_cC+w_iI+w_mM+w_nN+w_xX+w_bB+w_uU+w_oO+\lambda L,
\]

where `C`, `I`, `M`, `N`, `X`, and `B` retain the existing evidence meanings;
`U` is worst-case sensor-interval inconsistency; `O` is downstream observed
outcome inconsistency; and `L` is canonical program length. All weights are
fixed configuration. `O` dominates promotion: a program with zero exact
composed consequences cannot win because of a small local residual advantage.

## Treatment of the measured failures

### Missing intermediate states

The generator fills unresolved trajectory slots with field-predicted states and
operator paths. If several action orders reach the same prospective outcome, it
returns one outcome-equivalence class. A canonical representative may be
rendered for prospective execution, accompanied by multiplicity and ambiguity.
For historical reconstruction, the same evidence returns `ambiguous` rather
than inventing order.

### Moving targets

The temporal primitives permit generation of

\[
\Delta p_{target}=p_{target,t}-p_{target,t-1}
\]

and a separate exogenous-drift operator. Self-action consequence and target
drift then compose instead of being conflated in one action basin. A single
snapshot cannot identify velocity; the generator preserves multiple drift
hypotheses until another observation or declared motion constraint arrives.

### Coordinate noise

Declared sensor precision produces intervals around coordinates. Programs are
evaluated at deterministic interval extrema or with an equivalent analytic
bound. Settlement uses worst-case residual, preventing noisy point estimates
from creating arbitrary program or entity margins. Precision is boundary
metadata and never adapted from desired answers.

### Distractors and hidden relevance

`EACH_OBJECT` generates one role hypothesis per observable entity. Hypotheses
with consequence differences below the field-calibrated equivalence tolerance
share a class. A goal relation, temporal consequence, or Thalamus-required
candidate may separate them. If nothing observable separates them, the output
retains an unresolved role and does not emit a unique object ID.

### Passive and interventional roles

`SWAP_ROLES` creates the two role orientations explicitly. Symmetric training
covers all four relative quadrants. Passive evidence may reject an impossible
orientation but cannot select one solely because it resembles the training
pose. When both survive, the field can propose the least costly informative
action; binding occurs only after its observed consequence separates the
hypotheses.

### Boundary regimes

The grammar generates a guard and a transformation rather than forcing one
global basis to absorb a discontinuity. The target law can be expressed as

\[
p'_{self}=\operatorname{clamp}(p_{self}+\Delta p_{action},-1,1),
\qquad
r'=p'_{target}-p'_{self}.
\]

Interior and boundary support remain separately measurable. A generated guard
that never observes one regime cannot claim that regime.

## Generated output

The standalone API returns a read-only proposal containing:

- canonical program hash and decoded postfix tokens;
- output type and four generated coordinates;
- supported regimes and observation identities;
- role/entity/trajectory equivalence classes;
- evidence components, downstream outcome support, margin, and entropy;
- `selected`, `ambiguous`, or `exhausted` status;
- field SHA-256 before and after inference;
- optional canonical prospective trajectory when an equivalence class is
  acceptable.

It does not return a fabricated unique identity, historical ordering, or
boundary capability when the corresponding evidence is absent.

## Minimal implementation surface

The implementation should add only three focused files:

1. `cassi_generative_abstraction.py`
   - typed postfix alphabet and fixed interpreter;
   - canonicalization;
   - program-basin field layout;
   - masked counterflow synthesis;
   - controller-derived evidence and consolidation.
2. `run_generative_abstraction.py`
   - balanced direct executions and held-out worlds;
   - generated-program decoding;
   - moving, noise, distractor, role, boundary, restart, freeze, and ablation
     measurements.
3. `tests/test_cassi_generative_abstraction.py`
   - one executable behavioral scenario plus focused interpreter/hash rejection
     checks.

The implementation reuses `BilateralCounterflowController`, `QiFieldState`, the
existing grouped transition moments, thought refinement, exact checkpoint
framing, and deterministic `DeterministicQiWorld`. It does not add a package,
service, schema registry, provider route, optimizer, or dependency.

## Implementation sequence

### 1. Typed interpreter and canonicalization

Implement the fixed token alphabet, stack type checker, evaluator, exact program
hash, and canonical rewrites. Exercise generated subtraction, temporal delta,
role swap, interval bounds, and clamped updates directly.

### 2. Field-resident program evidence

Allocate program token and evidence regions in a new generative configuration.
Deposit raw transition observations through controller-owned evaluation. Verify
exact checkpoint replay and that removing program evidence removes selection.

### 3. Masked program generation

Generate `target_minus_self` from coordinate leaves and `SUBTRACT` rather than
listing it as a candidate basis. Retain canonical equivalence and reject shuffled
transition controls. Generate four output coordinates through `PACK4` and learn
the grouped action operators in those coordinates.

### 4. Regimes, uncertainty, and role equivalence

Add temporal delta, fixed precision intervals, `EACH_OBJECT`, `SWAP_ROLES`, and
one guarded clamp branch. Keep ambiguous roles and objects unresolved; use an
observed intervention to separate them.

### 5. Whole-trajectory abstraction generation

Use generated observables inside bilateral trajectory completion. Distinguish
historical reconstruction from prospective synthesis, consolidate a confirmed
program as a macro, and rerun the complete standalone stress surface.

A live provider decision comes only after this standalone implementation has
measured multi-world behavior. No provider change is included here.

## Executable measurements for the implementation

| Measurement | Required interpretation |
|---|---|
| Cartesian rediscovery | Canonical generated program contains role-position subtraction; no hand-listed basis candidate participates |
| Renaming and translation | Program and action consequence remain unchanged across renamed entities and global shifts |
| Equivalent syntax | Canonicalizer merges algebraically identical generated programs |
| Endpoint-only reconstruction | Ambiguous historical order remains ambiguous |
| Endpoint-only prospective synthesis | Outcome-equivalent class may emit a valid canonical representative without claiming recovered history |
| Moving target | Temporal-delta hypothesis is retained and consequences are measured separately from self action |
| Noise sweep | Settlement follows declared interval support; no random sampling or learned uncertainty state |
| Diagnostic distractors | Consequence-distinct target separates from moving distractors |
| Hidden relevance | Indistinguishable candidates remain one unresolved class; no false unique ID |
| Passive roles | Balanced role-swap cases produce no confidently wrong unique role |
| Intervention | Observed causal action separates role hypotheses across all four quadrants |
| Boundary composition | Generated guard and clamp law are evaluated by exact downstream revisions, not local residual alone |
| Program shuffle | Breaking episode correspondence removes or changes the selected generated program |
| Field ablation | Removing selected program or operator coordinates changes the committed result |
| Restart and inference | Serialized bytes replay exactly and read-only generation leaves the field unchanged |
| Teacher/provider controls | Zero model calls and no live provider route |

The measurements report exact counts, residuals, ambiguity, and false
settlements. They do not convert a recognizable decoded expression into a claim
of unrestricted abstraction learning.

## Current design decision

The next implementation should generate a small typed relational program, not
add more hand-authored basis names. The first target is canonical generation of
`target_minus_self`, followed by temporal drift and a guarded boundary update.
The field should retain unresolved role, object, and trajectory equivalence
classes rather than collapse them through tiny residual differences.

This direction directly addresses every measured weakness while preserving the
successful properties of the current work: one adaptive field, exact restart,
frozen inference, controller-owned evidence, explicit ablations, bounded work,
and no model fallback.

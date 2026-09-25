# Cassi Market Algorithm Distiller

## Status

This document defines the maximum-ambition destination for `CassiTrading`.
It deliberately extends the current bounded strategy foundry into a field-owned
market intelligence and algorithm synthesis system. It is a design contract,
not a claim that every surface is implemented.

The implementation target is one Cassi-native intelligence with shared learned
state, shared programs, shared evidence semantics, and shared checkpoint
lineage. It is not a collection of independent trading models.

## 1. North star

Cassi ingests a temporally ordered, multi-modal historical world, uses its
already acquired mathematical and Python capabilities to construct bounded
programs, discovers which structures apply to which market conditions, and
continuously distills the best currently supported portfolio and execution
policy.

The output is not a fixed indicator recipe. It is a versioned policy that can:

- represent the current market state and applicable regime;
- select or synthesize a bounded executable program;
- decide whether to act or abstain;
- allocate risk across instruments and horizons;
- model execution costs and capacity;
- retain its assumptions, evidence, applicability, and failure conditions;
- revise or retire itself when new observations invalidate its support.

The core transformation is:

```text
historical world
    -> canonical evidence and typed observations
    -> field-owned relations, regimes, and programs
    -> hypotheses and bounded program synthesis
    -> adversarial, counterfactual, and forward evaluation
    -> portfolio/execution policy
    -> joined prediction/outcome learning
    -> explicit consolidation and revision
```

## 2. Governing ownership model

The system has exactly one adaptive cognitive owner: the canonical field.
Everything else is either immutable evidence, fixed computation, or operational
authority.

Let:

- `F_t` be the canonical adaptive field at generation `t`, containing learned
  numerical relations, typed structures, programs, support, applicability,
  continuations, and bounded working state;
- `E_t` be immutable or append-only evidence: source bytes, observations,
  revisions, execution records, and independent certificates;
- `A_t` be nonlearned authority and operational state: user objectives,
  permissions, revocations, venue limits, operation identities, and approvals;
- `K` be fixed codecs, parsers, CassiPy interpreter semantics, numerical
  kernels, validators, resource accounting, and checkpoint rules.

A transition is:

```text
(F_t, E_t, A_t, input_t, K) -> (F_{t+1}, receipt_t)
```

No second adaptive owner is permitted. In particular, the following are not
allowed to become hidden learning systems:

- an embedding database;
- a learned feature encoder;
- a strategy-ranking model beside the field;
- an independent policy table;
- an untracked SQLite belief graph;
- an optimizer or trainable projection head;
- a prompt-memory sidecar;
- a cache whose contents change future decisions and cannot be reconstructed
  from the canonical field.

An external index may accelerate access only when it is reconstructible from
canonical field content and evidence identities.

## 3. Three knowledge layers

### 3.1 General capability knowledge

This is the already acquired math/Python capability layer. It includes:

- arithmetic and algebraic transformations;
- conditionals and piecewise functions;
- bounded iteration and aggregation;
- lists and structured values;
- functions, scope, and recursion;
- numerical/statistical operators acquired elsewhere in Cassi;
- program optimization and equivalence checks;
- exact solvers and bounded mathematical procedures;
- composition, planning, and verification patterns.

These capabilities answer: **what can Cassi compute and express?**

### 3.2 Domain knowledge

This is the market field. It contains learned, source-bound relationships such
as:

- regime-conditioned relations;
- instrument and cross-instrument dependencies;
- temporal persistence and transition patterns;
- execution-cost relationships;
- strategy applicability and failure conditions;
- prediction/outcome attribution;
- policy support, alternatives, and unresolved branches.

This knowledge answers: **which computation applies here, and what happens when it
is used?**

### 3.3 Operational policy

This is the current executable policy and its authority boundary. It contains:

- active program identity;
- regime guards;
- position and portfolio constraints;
- execution instructions;
- abstention conditions;
- current evidence and field versions;
- required approvals and revocation state.

This layer answers: **what is permitted now?**

General capability knowledge and market knowledge must not be merged by copying
opaque bytes. A verified `CassiSkillBundle` is a read-only, content-addressed
export of general executable capabilities. The canonical field remains the
source of adaptive truth; the bundle is an explicit import/export view with
provenance.

## 4. Canonical intermediate language

The system needs one typed intermediate language connecting raw data, math,
hypotheses, programs, and policy. All higher layers operate on these objects.

### 4.1 Event

```text
Event {
  event_id
  source_id
  source_revision
  observed_at
  available_at
  event_type
  subject_ids
  payload
  units
  coordinate_frame
  missingness
  uncertainty
  source_span
  content_sha256
}
```

`observed_at` is when the event occurred. `available_at` is when a decision
could have known it. Training, evaluation, and live policy access use
`available_at`, never an inferred publication time.

### 4.2 Derived observation

A deterministic transformation of admitted evidence:

```text
DerivedObservation {
  observation_id
  operator_id
  operator_version
  input_event_ids
  input_digests
  parameters
  output_schema
  value
  units
  valid_from
  valid_until
  derivation_sha256
}
```

A derived observation is not new world evidence. It can be used by a program,
but its dependency closure remains visible.

### 4.3 Skill

```text
Skill {
  skill_id
  title
  domains
  input_schema
  output_schema
  source_program
  canonical_ast
  verification_cases
  program_sha256
  support_roots
  applicability_guards
  known_failures
  resource_budget
  revision_id
}
```

A skill is a reusable typed computation, not a vague label. It may be
mathematical, procedural, temporal, relational, or domain-specific.

### 4.4 Hypothesis

```text
Hypothesis {
  hypothesis_id
  claim
  target_schema
  expected_direction_or_outcome
  applicable_context
  assumptions
  candidate_program_ids
  evidence_roots
  disconfirming_observations
  status
}
```

Statuses are explicit:

```text
proposed
supported
partially-supported
contradicted
unresolved
inapplicable
revoked
```

A hypothesis never becomes support merely because its program executes or its
language is plausible.

### 4.5 Program

```text
Program {
  program_id
  parent_ids
  source
  canonical_ast
  typed_inputs
  typed_outputs
  guards
  state_ports
  resource_budget
  evidence_roots
  skill_dependencies
  program_sha256
}
```

Programs are bounded and executable by the fixed CassiPy interpreter or a
fixed numerical kernel. Learned content belongs in the field; interpreter
semantics remain fixed.

### 4.6 Regime

```text
Regime {
  regime_id
  state_variables
  applicability_guards
  supporting_observations
  competing_regimes
  transition_programs
  uncertainty
  revision_id
}
```

A regime is not a hard label produced by a hidden classifier. It is a field-owned
state hypothesis with support, alternatives, and explicit unknown branches.

### 4.7 Policy

```text
Policy {
  policy_id
  regime_bindings
  program_bindings
  portfolio_controller
  execution_controller
  abstention_rules
  risk_limits
  applicability
  support_roots
  policy_sha256
}
```

### 4.8 Prediction and outcome

Every actionable prediction is frozen before its outcome:

```text
Prediction {
  prediction_id
  predecessor_field_sha256
  policy_id
  program_id
  input_event_ids
  available_at
  predicted_outcome
  alternatives
  cost_expectation
  risk_expectation
}

Outcome {
  outcome_id
  prediction_id
  observed_at
  realized_outcome
  execution_trace
  attribution
  cost_vector
  source_event_ids
}
```

A prediction and outcome are joined by identity. Replaying the same outcome does
not create new evidence or consume learning twice.

## 5. Historical data compiler

### 5.1 Supported source families

The ingestion boundary eventually supports:

- trades, quotes, candles, and order books;
- funding, open interest, options, and futures;
- corporate actions and fundamentals;
- macroeconomic releases and revisions;
- news, filings, and sentiment;
- calendars, sessions, and venue state;
- execution acknowledgments, partial fills, and cancellations.

Every source has a declared schema, clock, units, revision behavior, and
availability rule.

### 5.2 Canonical event stream

The compiler performs fixed operations only:

1. authenticate source bytes and source revision;
2. parse into typed events;
3. normalize units and coordinate frames;
4. preserve raw timestamps and availability timestamps;
5. record missingness and revision history;
6. reject impossible or ambiguous rows rather than silently repairing them;
7. create content-addressed source objects;
8. emit a deterministic event index and split manifest.

It must never use a learned model to repair a source before the source becomes
part of evidence. A repaired or inferred value is a derived observation with
its own identity and uncertainty.

### 5.3 Relational market coordinates

Programs should not learn every asset independently. Fixed operators expose
normalized coordinates such as:

- log or arithmetic returns;
- volatility-normalized displacement;
- relative strength and cross-asset spreads;
- volume and liquidity ratios;
- lead/lag windows;
- term structure and basis;
- event-time distance;
- regime-relative coordinates;
- multi-horizon summaries.

These operators are typed and versioned. Their outputs retain source
relationships and units.

## 6. Capability registry and program synthesis

### 6.1 Skill bundle import

The current `cassi_skill_bundle.py` exports twenty-one verified CassiPy
curriculum skills: eight general algorithmic lessons and thirteen
financial-math algorithms covering returns, drawdown, volatility, downside and
tail risk, execution cost, sizing, multi-dimensional portfolio objectives, hit
rate, profit factor, and risk of ruin. The complete system extends this
exporter to include:

- accepted teacher programs;
- verified math-study programs;
- exact solver procedures;
- field-promoted transformations;
- temporal and causal programs;
- resource-aware execution patterns.

Import validates:

- program schema;
- AST digest;
- input/output contract;
- differential cases;
- source and field provenance;
- revocation and applicability state.

No imported skill receives authority merely because it is verified as executable.
Execution correctness and domain truth remain separate.

### 6.2 Typed program grammar

The synthesizer operates over a bounded open grammar:

```text
literal, variable, tuple, record, list
arithmetic and comparison
conditional and guarded branch
bounded fold and bounded loop
function definition and application
finite state transition
windowed temporal operator
relational lookup through field bindings
portfolio aggregation
risk and abstention operator
```

Each candidate has a static resource budget:

- AST nodes;
- nesting and call depth;
- loop iterations;
- state cells;
- numerical work;
- branch count;
- source/evidence reads;
- checkpoint bytes.

### 6.3 Candidate generation

The field owns the productive candidate frontier. Fixed host code provides
syntax, parsing, and bounded execution, but does not hide a complete adaptive
candidate table.

Candidate expansion proceeds locally:

1. identify the unresolved distinction or failed prediction;
2. collect relevant typed skills and program dependencies;
3. propose the shortest well-typed substitutions, compositions, guards, and
   parameter bindings;
4. canonicalize alpha-equivalent programs;
5. reject programs with invalid contracts or unbounded resource demands;
6. predict before updating;
7. execute on development evidence;
8. retain the result and its attribution;
9. promote only supported substitutions.

The old fixed strategy mutation catalog remains a smoke-test baseline, not the
ultimate synthesizer.

The current foundry implements this composition boundary for financial
algorithms. For each failure regime, the field orders bounded compositions of
returns, drawdown, volatility, downside deviation, expected shortfall,
execution cost, hit rate, profit factor, Kelly-capped sizing, and risk of ruin.
Candidate promotion uses the selected composition on validation slices; the
frozen holdout receives the same composition afterward, preserving an explicit
in-sample versus held-out comparison.

### 6.4 Program selection

Selection is conjunctive:

- applicability must hold;
- evidence coverage must be sufficient;
- error and risk limits must hold;
- resource cost must be acceptable;
- alternatives must be accounted for;
- the program must improve the declared objective on future evidence;
- simpler or cheaper equivalent programs are preferred.

A scalar score may assist ordering, but it cannot collapse incompatible
hypotheses, override applicability, or turn uncertainty into authority.

## 7. Market world model

### 7.1 Multi-scale state

The world model contains nested scopes:

```text
structural era
  -> macro environment
    -> market/sector regime
      -> instrument state
        -> local opportunity
          -> execution state
```

Each scope has its own variables, support, update cadence, and applicability.
A local update must not mutate unrelated structures.

### 7.2 Regime representation

Regimes are typed field structures with:

- observed variables;
- derived variables;
- guards and boundary conditions;
- competing explanations;
- transition likelihood or bounded alternatives where justified;
- historical support;
- known exceptions;
- revision and invalidation dependencies.

The system may return multiple active alternatives or `unresolved`; it must not
force an arbitrary single label.

### 7.3 Hypothesis and inquiry loop

When the field cannot distinguish candidate models, it chooses among:

- retrieve exact evidence;
- derive a deterministic measurement;
- run a simulation;
- perform a counterfactual;
- wait for a future observation;
- reduce exposure;
- stop.

The cheapest useful inquiry is selected by expected distinction under declared
bounds, not by fabricated entropy or confidence.

### 7.4 Counterfactual world model

Counterfactuals are explicitly marked as hypothetical. They can generate
questions and candidate programs but never become observations.

Required counterfactual controls include:

- feature lesion;
- time-shuffle and source-shuffle controls;
- regime-preserving perturbations;
- cost and slippage stress;
- delayed-action replay;
- alternate execution venue;
- policy ablation;
- competing-model simulation;
- action/no-action matched pairs.

## 8. Portfolio and execution controller

### 8.1 Portfolio policy

The policy output is a portfolio transition, not an isolated signal:

```text
weights_before
  -> target exposures
  -> risk-budget allocation
  -> turnover and concentration checks
  -> executable order plan
```

It accounts for:

- correlated exposures;
- leverage and concentration;
- liquidity and capacity;
- cross-asset hedges;
- cash and abstention;
- funding and financing;
- execution costs;
- portfolio-level drawdown and tail constraints.

### 8.2 Execution policy

Execution is part of the learned algorithm and includes:

- urgency;
- order type;
- venue and route;
- price bands;
- partial fills;
- cancellation and replacement;
- impact estimates;
- timeout and failure handling.

A signal that is profitable only at an impossible fill is rejected.

### 8.3 Authority boundary

The research system has three explicit modes:

```text
research      historical replay and synthesis only
shadow        live observation and hypothetical decisions, no external effect
authorized    explicit user-approved effect through a named adapter
```

Transition between modes is never automatic. External effects require a point
of use authority check, operation identity, feasibility check, and exactly-once
acknowledgment.

## 9. Lifelong learning and consolidation

### 9.1 Chronological update rule

For each time window `W_t`:

1. restore the field and policy predecessor;
2. freeze the current policy;
3. ingest only events available before the decision boundary;
4. issue predictions before outcomes;
5. execute a bounded research or authorized action;
6. admit the identified outcome once;
7. attribute mismatch without assuming its cause;
8. update the field;
9. checkpoint successor state and receipt;
10. move the evaluation boundary forward.

A period used to revise the field is no longer untouched holdout evidence.

### 9.2 Memory temperatures

Knowledge has retention modes, not different owners:

- hot: current working hypotheses and unresolved branches;
- warm: active applicable relations and programs;
- cold: stable supported skills and historical evidence handles;
- archived: immutable evidence and superseded revisions.

Temperature changes access and scheduling, not epistemic status.

### 9.3 Consolidation

Capacity pressure invokes explicit alternatives:

- exact relocation;
- deduplication of identical structures;
- field-resident abstraction with expansion recipe;
- retire invalidated derived artifacts;
- archive immutable evidence;
- request authorized capacity growth;
- report exhaustion.

Lossy semantic consolidation is a new field version and requires an independent
assessment. It cannot silently erase rare guards, applicability boundaries,
or counterexamples.

### 9.4 Revision and revocation

Every field-supported program retains its dependencies. A source correction,
market-data revision, failed applicability condition, or explicit revocation
invalidates dependent predictions, programs, and policies.

An old checkpoint cannot restore revoked support. If affected support cannot be
reconstructed, the capability remains unavailable rather than silently serving
stale knowledge.

## 10. Checkpoint and lineage protocol

A checkpoint root binds:

- field schema and coordinate profile;
- complete adaptive field bytes/pages;
- structural programs and skill dependencies;
- support and applicability;
- evidence index and source digests;
- policy identity;
- authority/revocation generation;
- pending operation identity;
- predecessor and successor hashes;
- resource counters;
- operation journal and recovery envelope.

Publication is staged:

1. write immutable pages;
2. validate all reachable dependencies and capacity;
3. write successor manifest;
4. atomically advance current head;
5. publish receipt and operation replay record.

An interrupted transition either recovers the same successor or exposes the
unchanged predecessor. It never exposes a mixed field/evidence/policy state.

The current `--field-in --frozen-field` path is the first trading-foundry slice
of this protocol. The complete system must extend it from one raw-event field
to the full field, program, evidence, and policy closure.

## 11. Evaluation architecture

### 11.1 Evidence partitions

Maintain disjoint identities for:

- capability verification cases;
- program-development observations;
- calibration windows;
- model-selection windows;
- untouched holdouts;
- forward or shadow periods;
- adversarial and counterfactual controls.

A source digest alone is insufficient; the split manifest and availability
boundary are also hashed.

### 11.2 Benchmark families

#### Capability benchmark

Can the imported math/Python skill execute, compose, and remain valid after
checkpoint/reload?

Controls:

- AST/source mutation;
- input-contract mutation;
- bounded-loop exhaustion;
- differential mismatch;
- missing skill dependency;
- corrupted bundle.

#### Program-composition benchmark

Can the field compose withheld skills into a program never explicitly taught?

Controls:

- renamed variables;
- reordered inputs;
- held-out composition;
- deeper bounded nesting;
- conflicting type/units;
- ablated skill;
- no host-side candidate enumeration.

#### Market-transfer benchmark

Does a field-learned structure transfer across:

- later time windows;
- instruments;
- sampling intervals;
- volatility regimes;
- execution-cost conditions?

#### Causal ownership benchmark

Does the field change the candidate frontier, committed program, portfolio action,
or execution route relative to a field-lesioned control?

#### Lifelong benchmark

Can the system learn sequentially, preserve prior useful skills, incorporate a
correction, invalidate a dependent policy, and restart exactly?

### 11.3 Required controls

Every major claim needs matched controls:

- blank field;
- frozen field;
- field lesion;
- shuffled field/context;
- duplicate/degenerate identity;
- source mutation;
- future-information injection;
- cost stress;
- regime renaming;
- checkpoint restart;
- no-model/no-teacher path;
- no-host-planner path.

The decisive readout is a field-only intervention that changes a committed
candidate, program, or policy while all external data and fixed kernels remain
matched.

## 12. Receipts and verdict vocabulary

Each operation receipt reports:

- source and split manifests;
- predecessor/successor field hashes;
- skill and program dependencies;
- prediction and outcome identities;
- candidate frontier and rejected alternatives;
- resource usage;
- field-owned decisions;
- native/model calls, if any;
- checkpoint identity;
- validation and holdout metrics;
- applicability and unresolved conditions.

Use explicit verdicts:

```text
PASS / FAIL / NULL / INCONCLUSIVE
SUPPORTS / CONTRADICTS / EMERGES / DOES NOT EMERGE
ADOPT / REJECT / RETIRE / REVISE
```

A missing artifact is not a pass. A changed output without a causal field
control is not an ownership result. A profitable backtest without a valid
availability boundary is not evidence.

## 13. Implementation architecture

The full workspace should converge on these modules:

```text
cassi_event_store.py
  canonical sources, availability times, event identity, split manifests

cassi_market_coordinates.py
  fixed typed transformations and units

cassi_skill_bundle.py
  verified general math/Python capability export/import

cassi_field_owner.py
  sole adaptive state, admission, inference, consolidation, revocation

cassi_world_model.py
  regimes, relations, competing hypotheses, transition programs

cassi_program_synthesizer.py
  typed open-vocabulary bounded CassiPy program generation and selection

cassi_policy.py
  regime-conditioned portfolio and execution policy

cassi_counterfactual.py
  matched interventions, simulation, cost and execution stress

cassi_lineage.py
  checkpoint closure, manifests, operation journal, recovery, provenance

cassi_benchmark.py
  benchmark plans, controls, independent verification, reconciliation
```

The current files map as follows:

- `cassi_trading_foundry.py` is the bounded replay and first policy-search
  kernel;
- `cassi_skill_bundle.py` is the first general-capability export;
- `run_cassi_trading_benchmark.py` is the first matched-arm benchmark;
- `download_coinbase_history.py` is the first public historical source adapter;
- `run_cassi_trading_foundry.py --field-in --frozen-field` is the first reusable
  field checkpoint surface.

The fixed strategy families remain useful as controls while the open synthesizer
is built. They must not become the final architecture.

## 14. Build order for a maximum-ambition implementation

The system can be built as one coordinated program with these dependency
boundaries:

### Wave A: shared contracts

- canonical event and availability schema;
- skill, program, hypothesis, regime, prediction, outcome, and policy schemas;
- content-addressed source and checkpoint closure;
- fixed resource and authority semantics.

### Wave B: capability and field integration

- export all verified math/Python skills;
- import with differential and provenance verification;
- bind skills to the sole field owner;
- implement exact field checkpoint/reload/consolidation;
- preserve frozen versus adaptive modes.

### Wave C: open program synthesis

- typed market input bindings;
- bounded composition grammar;
- field-owned candidate frontier;
- prediction-before-update assessment;
- program promotion, rejection, and revision.

### Wave D: world model and counterfactuals

- multi-scale market relations;
- regime alternatives and transitions;
- hypothesis/inquiry loop;
- counterfactual and execution simulation;
- explicit unknown and outside-envelope branches.

### Wave E: policy and execution

- portfolio-level allocation;
- execution and cost model;
- shadow mode;
- authorized adapter boundary;
- exactly-once acknowledgment and revocation.

### Wave F: lifelong campaign

- multi-instrument, multi-resolution historical ingestion;
- chronological rolling evaluation;
- capability transfer tests;
- consolidation and revision campaigns;
- independent receipt reconciliation.

“All at once” means these surfaces share one canonical contract and are designed
for integration from the beginning. It does not mean that an unverified
execution adapter is allowed to masquerade as a complete intelligence system.

## 15. Non-negotiable acceptance gates

The complete system is not accepted merely because it produces a profitable
backtest or fluent explanation. It must demonstrate:

1. one canonical adaptive owner;
2. exact skill/program/evidence provenance;
3. no future-information leakage;
4. executable bounded programs;
5. field-owned candidate selection or policy change;
6. exact checkpoint and restart;
7. explicit capacity and consolidation behavior;
8. correction and revocation of dependent knowledge;
9. held-out and forward evaluation;
10. matched field-lesion controls;
11. explicit unknown, abstention, and resource-exhausted outcomes;
12. no unreported model or host-planner fallback;
13. portfolio and execution costs represented in the objective;
14. authorized external effects only through the declared adapter;
15. receipts sufficient for independent reproduction.

The final claim is then appropriately strong:

> Cassi can ingest a declared historical world, reuse its acquired mathematical
> and Python capabilities, synthesize bounded executable policies, learn
> domain-specific applicability through field-owned experience, and revise or
> retire those policies through an evidence- and lineage-preserving loop.

Anything narrower is a measured subsystem result, not the complete destination.

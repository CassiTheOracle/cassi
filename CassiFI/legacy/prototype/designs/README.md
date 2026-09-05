# Cassi Field Intelligence implementation plan

## Status: implementation design with measured universal-data slice—2026-09-01

This directory is the normative implementation plan for replacing the current
modal Qi reservoir with a spatially propagating, field-owned intelligence
runtime. It preserves the complete engineering contract while separating the
physics, cognition, runtime, serving, verification, and cutover concerns into
maintainable documents.

The design remains governed by one invariant: the sole adaptive persistent
object is `QiFieldState.field` with logical shape `[S, 9M, B]`. Geometry,
probes, boundary maps, profiles, schemas, transaction machinery, and
verification code are fixed operators or evidence. They do not become a
second learned or adaptive model.

## Capability north star

[`UNIVERSAL-DATA-FIELD-DESIGN.md`](UNIVERSAL-DATA-FIELD-DESIGN.md) owns the
definitions of universal substrate, measured semantics, capability accounting,
theory-to-test boundaries, and the first cross-format proof.

Parts 0–13 remain the surrounding implementation plan. The north star records
the common packet, journal, typed-view, exact-reference, cross-format, and
shared-checkpoint seams that are now implemented and measured; unimplemented
parts remain design rather than live contract.

## Reading order

| Part | Document | Scope |
|---:|---|---|
| North star | [`UNIVERSAL-DATA-FIELD-DESIGN.md`](UNIVERSAL-DATA-FIELD-DESIGN.md) | Universal substrate, bounded semantic claims, capability accounting, theory boundaries, and first cross-format proof |
| 0 | [`00-foundations.md`](00-foundations.md) | Purpose, engineering policy, architectural thesis, and present implementation truth |
| 1 | [`01-field-physics.md`](01-field-physics.md) | Derived coordinates, geometry, transport, conversion, and reciprocal scale circulation |
| 2 | [`02-retention-capacity-and-cognition.md`](02-retention-capacity-and-cognition.md) | topological-retention retention, dynamical capacity, boundary work, cognition definitions, diagnostics, and release criteria |
| 3 | [`03-architecture-profiles-and-schemas.md`](03-architecture-profiles-and-schemas.md) | Implementation phases, source ownership, clean cutover, profiles, schemas, and hashing |
| 4 | [`04-execution-contract.md`](04-execution-contract.md) | Normative split-step execution, admissibility, guards, work accounting, and failure semantics |
| 5 | [`05-boundaries-body-and-action.md`](05-boundaries-body-and-action.md) | Fixed modality boundaries, embodiment, predictive remapping, attention, gaze, and action |
| 6 | [`06-memory-and-learning.md`](06-memory-and-learning.md) | Recall, grounding, acquisition, consolidation, interference, and field-experience curriculum |
| 7 | [`07-world-loop-and-transactions.md`](07-world-loop-and-transactions.md) | Unified world loop, wire protocol, idempotency, Commit A/Commit B, and crash recovery |
| 8 | [`08-language-and-serving.md`](08-language-and-serving.md) | Trajectory-owned byte emission, reaction feasibility, streaming, and provider behavior |
| 9 | [`09-backends-receipts-and-verification.md`](09-backends-receipts-and-verification.md) | State inventory, units, CPU/ROCm execution, capacity, receipt graph, and independent verification |
| 10 | [`10-work-packages.md`](10-work-packages.md) | Mandatory implementation packages and dependency graph |
| 11 | [`11-validation-gates.md`](11-validation-gates.md) | Engineering gate matrix and acceptance evidence |
| 12 | [`12-decisions-deployment-and-completion.md`](12-decisions-deployment-and-completion.md) | Frozen decisions, risk closure, integration order, deployment, rollback, commands, and definition of complete |
| 13 | [`13-requirements-registry.md`](13-requirements-registry.md) | Stable identities for the load-bearing cross-document requirements |

## Suggested reading paths

### Architectural review

Read the [North star](UNIVERSAL-DATA-FIELD-DESIGN.md), then Parts 0–3 and Parts
10–13.

### Physics and numerical implementation

Read the [North star](UNIVERSAL-DATA-FIELD-DESIGN.md), then Parts 1, 2, 4, 5,
9, 10, and 11.

### Learning, embodiment, and language

Read the [North star](UNIVERSAL-DATA-FIELD-DESIGN.md), then Parts 2, 5, 6, 7,
8, 10, and 11.

### Runtime, provider, and recovery

Read the [North star](UNIVERSAL-DATA-FIELD-DESIGN.md), then Parts 3, 4, 7, 8,
9, 10, 11, and 12.

## Normative structure

The documents form one design. A statement is normative when it defines a
required invariant, equation, operator order, schema field, failure rule,
work package, gate, or completion condition. The requirements registry gives
stable names to the cross-cutting invariants but does not override the full
mathematical and protocol definitions in their owning documents.

A contradiction between documents is a design defect. It must be resolved in
the owning definition, every consuming work package, the relevant gate, and
the requirements registry in the same change. No chapter silently wins by
being later in the reading order.

## Cross-document dependency

```text
capability north star
  -> foundations
  -> field physics
  -> retention and capacity
  -> profiles and schemas
  -> execution contract
  -> boundaries, body, and action
  -> memory and learning
  -> world transactions
  -> language and serving
  -> backends and receipts
  -> work packages
  -> validation gates
  -> deployment and completion
```

The W0-owned hashed
`cassi.qi-flow-dependency-manifest.v1` is authoritative for the implementation
and evidence graph: the package Mermaid/prose view in
[`10-work-packages.md`](10-work-packages.md), the gate view in
[`11-validation-gates.md`](11-validation-gates.md), and the registry
cross-references in [`13-requirements-registry.md`](13-requirements-registry.md)
are generated from or checked against that manifest. None may silently weaken
an operator or causal contract defined in an earlier part.

## Design direction added in this revision

This split plan incorporates the following refinements as first-class design
requirements rather than optional follow-up work:

- one typed lossless substrate across modalities with separately measured
  within-modality and cross-modal semantics;
- an explicit release comparison between a full-rank temporal scale stack and
  a rank-reducing spatiotemporal pyramid;
- early integration of the topological-retention Hamiltonian, topology, and stability law;
- separate within-sector analog acquisition and topological consolidation;
- a conversion-viability audit and physical-time constitutive memory;
- a reproducible field-experience curriculum for raw UTF-8 and grounded world
  streams;
- passive field-owned sensory permeability and observability-seeking action;
- scale-link and external-port scattering receipts;
- dynamical text-frame calibration and exact certified reaction pruning;
- an explicit state-lineage fork for profile changes that do not reinterpret
  field state;
- bounded model exploration of the Commit A/Commit B transaction protocol;
- offline numerical certification feeding cheap online decision guards; and
- stable requirement identities linking equations, implementations, gates,
  and evidence.
- a contract-root identity that binds the canonical codec, schema registry, projection registry, and materialized defaults, with one hashed dependency manifest authoritative for package, gate, prose, Mermaid, and registry graphs;
- a canonical capacity ladder over exact `advance()` trajectories, fixed controller grammar/horizon, and nonnegative incident/source work, plus periodic-sheet/topology realizability, complete conversion-domain, immutable-certificate, transaction-indeterminate, permeability, causal, and text-ownership refinements;
- post-cutover research cards for field-selected practice, body-model adaptation, source-free rest/consolidation, causal lesion mapping, factorized composition, and cross-profile scaling; these cards are runnable research only and are not G15 release dependencies or live fallback/state;

None of these refinements adds learned weights, a hidden policy, an external
memory, a semantic lookup table, or a fallback language model.

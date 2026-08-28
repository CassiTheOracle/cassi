# Decisions, risks, deployment, and completion

> CassiFI implementation plan, Part 12. [Previous](./11-validation-gates.md) · [Index](README.md) · [Plan index](README.md)

## Current implementation decisions

These decisions remove local architectural ambiguity from the work packages.
They are the current shared design, not a lock on future engineering. A
cross-cutting change is made centrally in this plan and migrates every affected
profile, caller, test, and receipt together; an implementer cannot create an
untracked second convention.

| ID | Current decision | Consequence |
|---|---|---|
| D1 | The sole adaptive persistent object is real packed-plane `QiFieldState.field[S,9M,B]`; complex `E_Y/E_I/D/C` views are transient exact coordinates. | No complex storage reinterpretation, cache, recurrent vector, action history, saliency map, model state, or pending tensor may become a second adaptive owner. |
| D2 | Active slots are a declared row-major physical sheet; FFT/DFT values are transient operator coordinates. | Spatial derivatives, remaps, and analytic probes use the hashed FFT convention; boundaries inject physical-grid drives. |
| D3 | The controller exposes one production entry point, `advance(state, drive_bundle)`, including the explicit non-time-advancing `port_reaction` transition. | Standalone production `sense/evolve/convert/consolidate/emit` calls and raw boundary tensor writes are removed, not wrapped. |
| D4 | Yang/Yin conversion is the exact centered once-per-step frozen-`Q` position-density exchange under dimensionless `rho_ref`; production uses the receipted dissipative-v1 energy rule. | Resolved-positive and source-ambiguous candidates reject whole; numerical-zero adds no sink; resolved-negative work is one named sink; no projection, clamp, duplicate invocation, velocity conversion, or caller rate survives. |
| D5 | Both `D` and `C` have positive distributed adjacent-scale coupling over each coarse scale's measured retained subspace. | Nullspaces and signed scale currents are explicit; zero links and historical top-one writes exist only as named controls/historical code. |
| D6 | Optical, audio, proprioceptive, text, and motor boundaries are versioned fixed descriptors under one rational causal clock and passive-egress contract. | No learned encoder, semantic label, installed-font dependency, adaptive codebook, undeclared resampling, or host-time causality enters the live graph. |
| D7 | Prediction, attention, action, recall, acquisition, and text selection are derived from field trajectory and fixed geometry; production retention is topological-retention `topological-v1` inside the existing slow field scale. | Topology is derived, not stored; fading retention is a comparator only; no host branch, basin key, replay, or auxiliary state becomes adaptive memory. |
| D8 | Commit A atomically publishes successor, exact ingress cursors, response, passive proposal/reaction, and at most one tick outbox before external I/O; Commit B publishes terminal acknowledgement and applied efference. | Consume-after-commit ingress is exact-once, locks span no network wait, and only terminal `applied` establishes world effect/remap input. |
| D9 | CPU float64 is the analytic oracle; CPU float32 and ROCm float32 are required release backends. | Missing ROCm or silent CPU fallback blocks that release; a dedicated field kernel is profiler-gated and contains no Qwen/llama dependency. |
| D10 | Text/provider streaming is validate -> precompute -> atomic commit -> ordered stored-event streaming. | Malformed requests fail before session lock/allocation; a disconnect cannot leave half a field transition; stream/nonstream bytes and state are identical. |
| D11 | Both the deterministic reference world and real default-off CassiCosmos adapter are required for the full embodied endpoint. | Reference-world success cannot substitute; adapter-off deterministic artifacts are byte-identical to the pinned pre-W13C baseline, while only schema-declared volatile telemetry may use the G13D projection contract. |
| D12 | Legacy v2/F3/F5/conscious/organism/native experiments stay behind an explicit historical boundary. | There is no compatibility alias, automatic state conversion, or runtime fallback. |
| D13 | Runtime receipts are engineering outputs subject to independent recomputation by W1-owned `verify_cassi_qi_flow.py`. | A self-reported counter, finite state, plausible text, or candidate-edited verifier is insufficient. |
| D14 | Composite profile identity is derived from a complete JSON-Pointer projection registry, and raw field bytes bind to the state-relevant contract. | Every functional leaf has declared subhash membership; operational/API/evidence edits do not silently reinterpret field state. |
| D15 | This plan is a living engineering design. | Better mechanisms replace weaker ones by clean cutover; historical run artifacts keep their original identities. |
| D16 | Intrinsic and endpoint causal capacity are separate audits. | W6A/G6A cannot claim boundary usefulness; W6B/G6C runs only after actual boundaries, action, text, acquisition, and topological-retention retention exist. |
| D17 | The mandatory capability matrix is external to the candidate. | A candidate may fail or block a required row but cannot omit, weaken, or mark it optional. |
| D18 | Release evidence is post-cutover and candidate-frozen before documentation. | W16A freezes executable source/config/profile/schema/fixture/toolchain/commands and reruns all required evidence after W15A; W15B prose is downstream. |
| D19 | Existing `_diag` artifacts and the pinned base GGUF remain immutable inputs/historical evidence. | Cleanup creates new content-addressed indexes/quarantine receipts and never mutates, renames, overwrites, or uses newest-file inference. |
| D20 | `QI-NUM-001`: `QiNumericalCertificate` is an offline high-precision/enclosure derivation paired with cheap online guards and independent replay. | Guards may reject before commit but may not widen enclosures, clip values, or replace the offline certificate. |
| D21 | `QI-SCALE-001`: production stores an explicit `scale_geometry_mode` selected after a registered `temporal-full-rank` versus `spatiotemporal-pyramid` comparison. | Rank loss is never implicit; the selected mode, comparison, rank, conditioning, and cross-talk are profile-bound evidence. |
| D22 | `QI-RET-001`: W4R installs the topological-retention Hamiltonian/topology core after W4 and before W5; W10R owns later behavioral retention/consolidation. | Conversion consumes the installed law, while behavioral acquisition cannot silently implement or replace its core. |
| D23 | `QI-RET-002`: within-sector analog acquisition and topological consolidation are distinct tiers in the same field tensor. | No buffer, key, replay, matrix, optimizer, or other adaptive state is added for either tier. |
| D24 | `QI-RET-003`: topology algebra, reachable basin capacity, saturation, overwrite, interference, and recovery are measured capabilities. | A sector label or one successful phase slip cannot stand in for capacity evidence; unmeasured behavior blocks release. |
| D25 | `QI-CONV-001`: W5V freezes `epsilon_prog_min`, `D_prog`, `D_neutral`, and proves every support cell maps into both `D_conv` and `A_accepted`; `D_prog` has a positive signed progress margin while `D_neutral` has a bounded-transfer margin near `epsilon=0`. | Exact balanced/zero controls remain no-ops; no uniform positive margin is demanded in `D_neutral`, and unresolved/shrunk support or repeated rejection still blocks. Physical `epsilon_memory_time` remains the stored parameter. |
| D26 | `QI-BOUND-001`: `QiBoundaryPermeabilityProfile` derives passive sensory coupling from field geometry/metric/scale and accounts for admitted/reflected/absorbed work. | Boundary descriptors carry no learned encoder or hidden state, and unexplained work blocks the modality. |
| D27 | `QI-ACT-001`: gaze/action includes a no-peek finite-horizon observability-improvement term derived from current committed field/input and fixed geometry. | Future candidate consequences cannot enter scoring; proposal, reaction, and applied effect remain separate. |
| D28 | `QI-PORT-001`: `QiScatteringReceipt` records incident, reflected, transmitted, and absorbed work at each scale and external port. | Scale and boundary ledgers independently close; double-counted or unexplained port work is a hard failure. |
| D29 | `QI-LEARN-001`: `QiFieldExperiencePlan` freezes byte/world streams, timing, work budgets, whole-episode splits, washout, stopping, and checkpoint selection before acquisition. | Plan edits, packet-level leakage, and post-hoc checkpoint choice invalidate acquisition and descendants. |
| D30 | `QI-TEXT-001`: `QiDynamicPortFrame` measures trajectory-response rank, conditioning, singular spectrum, and cross-talk on actual `N_0`. | Text capability is not inferred from a static frame; frame identity and raw trajectory evidence are mandatory. |
| D31 | `QI-TEXT-002`: interval-certified reaction pruning must be decision-equivalent to exhaustive candidate evaluation. | No heuristic pruning or silent exhaustive fallback may alter feasibility, winner identity, or committed bytes. |
| D32 | `QI-LINEAGE-001`: `QiStateLineageForkReceipt` authorizes a new-session fork only across profile differences that do not reinterpret exact field bytes. | Parents remain immutable; in-place reinterpretation, silent migration, and automatic conversion are rejected. |
| D33 | `QI-TXN-001`: `QiTransactionModelReceipt` is produced by bounded explicit-state exploration of Commit A/Commit B crash and replay interleavings. | Runtime transaction code must stay within the explored state space and preserve at-most-one terminal effect and authoritative predecessor semantics. |
| D34 | `QI-EVID-001`: adapter-off equality compares exact deterministic artifacts; only schema-declared volatile telemetry may use a deterministic projection proven by mutation controls. | Numerical similarity, counts, or self-selected summaries never establish adapter equivalence. |
| D35 | `QI-DOC-001`: `13-requirements-registry.md` is the exact-once index from every QI-* ID to owner document, package, gate, artifacts, and failure behavior. | G15B also proves every indexed CassiFI document is covered; root monolithic-plan prose is a navigation pointer only. |
| D36 | `QI-ID-001`: profile identity is a `cassi.qi-flow-contract-root.v1` binding of the canonical codec, complete schema registry, projection registry, and materialized defaults. | A child identity mutation mints a new root; profiles, state, receipts, and gates reject missing, reordered, or substituted root inputs. |
| D37 | `QI-CAP-001`: capacity is a ladder generated only by exact canonical `advance()` trajectories under frozen controller grammar, exact physical horizon, and nonnegative incident/source-work budget. | Geometric, reachable, observable, usable, retained, and reusable capacity remain distinct; reset/startup/failed/uncommitted steps never count as acquisition. |
| D38 | Release FFT sheets are explicitly periodic, and topology codebooks must be realizable at selected resolution, resolution-scaled, and preserved by zero-clock remaps. | A future nonperiodic operator family requires distinct transform, metric, flux, and receipt identities; unrealizable or remap-changing codebooks fail capacity claims. |
| D39 | `QI-CONV-001` includes a frozen complete-domain interval/analytic proof over `epsilon_prog_min`, `D_prog`, `D_neutral`, `D_conv`, and `A_accepted`; fixtures are witnesses only and unresolved cells fail. | The support domain is fixed before outcomes and cannot shrink after observation; `D_prog` requires positive signed progress, `D_neutral` bounded transfer (not uniform positivity), and exact balanced/zero no-op controls; a changed support/predicate/proof identity reruns conversion descendants. |
| D40 | `QI-TXN-001` includes two competing callers and all Commit-B CAS interleavings; unknown external application truth is a sealed indeterminate lineage unless exact authenticated resolution succeeds. | Unknown truth cannot resume normal continuation; at-most-one applied effect and no dropped committed response remain mandatory. |
| D41 | `QI-NUM-001` certificates are immutable parent-linked extension chains whose final certificate names a complete section inventory. | A changed parent/law mints a new extension chain; missing, reordered, implicit, or placeholder sections fail independent replay. |
| D42 | `QI-ACT-001` capability claims use uncertainty/null-thresholded causal consequences; runtime observability is no-peek, paired-world discriminability is offline, and delayed influence is evidence plus ordinary residual packets. | No future consequence enters runtime scoring and no persistent credit/eligibility/attribution state may be added. |
| D43 | `QI-BOUND-001` requires field-derived sensory openness and bounded recovery normalized by incident work for every mandatory port. | Permanent blindness, caller-gain compensation, or unexplained admitted/reflected/absorbed work blocks the boundary. |
| D44 | `QI-TEXT-003` requires field-state-necessity intervention evidence and uncertainty-aware codebook separation/packing; rank is measured, not fixed to 260 or alphabet size. | Missing necessity or overlapping packing intervals blocks text claims; codec cardinality does not substitute for trajectory rank. |
| D45 | One hashed machine-readable dependency manifest is authoritative for W/G/prose/Mermaid/registry/artifact graphs, and G15A emits engineering readiness only while G15B emits final-release readiness. | Graph drift or hand edits fail G0/G15B; G15A has no G15B prerequisite and cannot certify prose. |
| D46 | Post-cutover research cards are isolated, field-only, and optional (practice, body adaptation, source-free rest, lesion atlas, composition, scaling). | A card may fail or rerun without changing live state, adding fallback, weakening evidence, or delaying G15 release. |

## Risk and decision-closure register

| Risk | Earliest observable signal | Mandatory response | Stop/release condition |
|---|---|---|---|
| Numerical coefficients are underdetermined | G0 cannot fill a real profile value from an analytic identity, measured fixture, or explicit design choice | keep the value as a named blocker, derive it under the owning W package, issue a new manifest hash, and rerun affected descendants | no placeholder, inherited v2 value, or silent zero may enter `cassi-qi-flow.json` |
| Spatial capacity is too small for boundary collisions or long-range flow | basis/collision audit, G2 operator probes, or G7 boundary round-trip fails | increase the integrated profile geometry/capacity and recompute memory/performance formulas; do not change the codebook or add a learned projection | current release profile must pass every modality and world loop at its real capacity |
| Full dynamics are unstable without clipping | envelope validation, rejected candidate, or G3/G14B long-horizon residual grows beyond bound | correct timestep/coefficient/integrator profile under a new identity and retain the failed artifact | any clip/rescale, nonfinite accepted state, or unaccounted energy remains a hard `FAIL` |
| Composition steering is mathematically present but causally ineffective | matched G4 reversals do not change the registered trajectory/current | inspect the flow channel, potential, coefficient range, and fixture; simplify or redesign the mechanism and rerun affected checks | the carrier-steering capability does not ship until the repaired production path is effective |
| Cross-scale energy appears without reciprocal source loss | link-energy/source/target ledger fails or historical top-one control matches production | fix adjoints, metric weights, stage ordering, or ledger; never add a discrete winner | no memory/circulation claim until G6 closes |
| Boundary transforms leak labels or discard unexplained information | schema trap, adjoint mismatch, collision, saturation, installed resource, or hidden metadata is observed | reject packet/profile and correct the fixed descriptor/fixture provenance | affected modality and all dependent gates remain failed |
| Predictive remap erases external change or preserves self-motion residual | G8 correct/absent/lagged/permuted controls do not separate | correct body-frame convention, acknowledgement use, or remap operator under new hashes | no self/external separation claim until directional controls pass |
| Attention peeks at candidate consequences | access log observes future patch/frame/label or candidate permutation changes physical result | remove the access path and rerun G9-G15B from fresh parents | one no-peek breach rejects attention, grounding, and release readiness |
| External action is double-applied across a crash | duplicate idempotency key changes world twice or returns a different acknowledgement | fail motor path, retain raw wire evidence, correct adapter retention/transaction protocol | no embodied or provider-world release readiness until every crash window passes |
| Memory is a slow afterimage or topological-retention topology is numerically fictitious | G10 cue effect vanishes, G6B barrier/sector control fails, or G10A repeated experience lacks a receipted phase slip and held-out effect | repair `U_topo`, curvature/barrier/domain, reciprocal return, residual coupling, or fixed coefficients under a new profile; never add a buffer/key/optimizer | topological-retention production retention and acquisition remain unfinished until G6B/G10/G10A pass; fading retention cannot substitute |
| Text emission collapses to static resonance, terminal-dark history, loops, or perpetual abstention | G11 flow/order/window/reaction controls are inert, actual-`N_0` frame is ill-conditioned, or no event passes | repair frame, sampling, passive port, feasibility/margin, or field dynamics without templates/sampling | trajectory-owned emission requires a reaction-feasible terminal-positive passive output and designated coverage |
| Provider accidentally reacquires offline/Qwen dependencies | import graph, loaded module/file/socket evidence, or startup trace includes displacement builder, GGUF, llama, Qwen, teacher, or learned stack | remove the live edge and rerun G12A/G12E and affected descendants in a fresh process | any live dependency or silent fallback is a hard failure |
| CPU/ROCm numeric differences cross a decision margin | numeric state remains close but action/text winner differs | increase analytic margin or correct backend/operator parity under a new profile; never force the winner post hoc | all mandatory discrete decisions must meet the gate's identical-decision contract |
| Performance misses interactive capacity | G14B repeated latency, memory, allocation, or synchronization budget fails | profile full correct Torch execution; optimize/preallocate/batch; authorize a dedicated field kernel only under D9 criteria | capacity/performance readiness and the release backend remain blocked |
| Receipt code verifies itself | independent recomputation cannot derive a raw measure or shares the runtime builder | retain missing raw state/packet/action artifact and implement the independent computation | G15A/G15B cannot pass on runtime summary JSON alone |
| CassiCosmos adapter authorization or hardware exercise is unavailable | path-level ownership brief absent, Godot editor already occupies required surface, or windowed scene cannot run | finish every reachable reference/CPU artifact and issue `BLOCKED`; do not substitute a mock or headless RD scene | full embodied endpoint remains blocked until the real adapter and unchanged battery pass |
| Owner-live files change during implementation | source/profile hash changes between ownership assignment and integration | stop editing that path, coordinate one owner, rebase the work package contract, and mint a new manifest identity | never overwrite collaborator work or integrate an unreviewed mixed file |
| Documentation overstates behavior | README/release text exceeds a passing capability or names stale commands | correct the implementation or reduce the statement to the exact working surface | G15B rejects misleading documentation even when unrelated mechanics pass |
| Rational clock or ingress replay loses causal identity | G7 LCM/antialias/watermark reconstruction fails or a crash loses/duplicates a packet | reject the profile/source, repair clock/journal/retention and rerun all causal descendants | no host-time rounding, dequeue-before-commit, or unreplayable admitted range may release |
| Proposal is mistaken for external effect | G8/G9 sees a remap/residual/world claim before terminal `applied` | repair prediction/proposal/reaction/ack/applied-efference separation and replay every crash window | only one Commit-B applied-efference can carry `world_effect=true` |
| Intrinsic capacity hides a dark endpoint | G6A passes but G6C transfer/multimodal rows are rank-deficient or stop at uncommitted outputs | repair actual boundary/law/capacity and rerun endpoint descendants | required external capability remains failed regardless of allocated state size |
| Candidate reuses stale or self-selected evidence | G15A input predates W15A, omits a capability row, or changes verifier/toolchain/command | discard the candidate board, regenerate external matrix/freeze, and rerun post-cutover evidence | no pre-cutover, out-of-root, unindexed, or candidate-weakened artifact satisfies release |


### Refinement risk closure

The following rows bind each shared requirement to an observable risk and a
stop rule; they refine the register above and do not create alternate
requirements.

| Requirement | Observable risk | Mandatory response | Stop condition |
|---|---|---|---|
| `QI-NUM-001` | Online guard accepts a state outside the offline enclosure, replay disagrees, or the final certificate omits a section. | Recompute from raw inputs and append an immutable parent-linked `cassi.qi-flow-certificate-extension.v1` with complete section inventory; preserve failed boundary. | No accepted state or gate pass with widened/clip-adjusted bounds, broken parent chain, or incomplete inventory. |
| `QI-SCALE-001` | A scale implementation silently drops rank, leaves mode implicit, uses a nonperiodic identity, or ties unresolved candidates. | Run the frozen pre-run selector over rank/conditioning/cross-talk/work/cost intervals and mint the profile-bound selection receipt. | No production run without explicit selected mode, periodic identity, realizable resolution-scaled codebook, and deterministic non-overlapping decision. |
| `QI-RET-001` | Conversion sees a missing/alternate topological-retention law or W10R reimplements physics. | Restore W4R-before-W5 ownership and rerun G4R plus descendants. | W5 and W5V/G5V remain blocked until the W4R core is installed. |
| `QI-RET-002` | Analog acquisition and sector consolidation collapse into an unreceipted buffer/key. | Remove added state and split the two receipts over the one field tensor. | Any added memory state or tier ambiguity blocks retention. |
| `QI-RET-003` | Capacity, saturation, overwrite, recovery, or forgetting is asserted from one successful cue or reset. | Run exact canonical `advance()` reachability/retention trajectories under frozen grammar/horizon/nonnegative work with raw topology, basin, and forgetting receipts; keep capacity classes distinct. | Unmeasured dynamical reachability/forgetting, negative/unknown work, reset acquisition, or conflated geometric/reachable/observable/usable/retained/reusable capacity blocks retention. |
| `QI-CONV-001` | Frozen-`Q` repeatedly rejects, stores a timestep-dependent EMA coefficient, narrows support after seeing outcomes, or misclassifies near-zero/balanced states. | Revise the law/profile; freeze `epsilon_prog_min`, `D_prog`, `D_neutral`, `D_conv`, and `A_accepted`; prove complete support coverage, positive signed `D_prog` margin, bounded-transfer `D_neutral` margin, exact balanced/zero no-ops, store physical `epsilon_memory_time`, and derive the coefficient per step. | No unresolved cell, normalized rejection, fallback domain, post-observation shrink, missing predicate/margin, or uniform-positive-near-zero demand may ship. |
| `QI-BOUND-001` | Boundary coupling leaks labels, admits/refuses unexplained work, or a mandatory port remains blind forever. | Recompute field-derived `QiBoundaryPermeabilityProfile`, incident-work-normalized openness/recovery, and `QiScatteringReceipt` from field/port inputs. | Every mandatory port must have positive normalized openness and bounded recovery; missing work accounting or permanent blindness blocks. |
| `QI-ACT-001` | Gaze/action sees a candidate's future consequence, or capability is claimed without uncertainty/null-thresholded paired-world causal evidence. | Remove the peek path; rerun finite-horizon no-peek baseline/controls and offline paired-world discriminability plus delayed-influence evidence as ordinary residual packets. | One peek, proposal-as-effect, missing positive causal margin, or persistent delayed-credit state invalidates action release. |
| `QI-PORT-001` | Scale/port work is double counted or closure is merely a runtime summary. | Independently replay `QiScatteringReceipt` from raw trajectories and ledgers. | Any unexplained incident/reflected/transmitted/absorbed row blocks G6T. |
| `QI-LEARN-001` | Experience plan leaks packets, edits budgets, or selects a checkpoint post hoc. | Freeze `QiFieldExperiencePlan` before acquisition and rerun whole-episode splits. | Mutable plan or leakage invalidates all acquisition evidence. |
| `QI-TEXT-001` | Static text-frame metrics hide ill-conditioned trajectory response or cross-talk. | Recalibrate `QiDynamicPortFrame` at actual `N_0` with raw trajectories. | Missing rank/conditioning/cross-talk evidence blocks text claims. |
| `QI-TEXT-002` | Interval pruning changes a feasible candidate, winner, or committed bytes. | Compare every pruned decision with exhaustive evaluation under exact intervals. | Any mismatch blocks pruning and text release. |
| `QI-LINEAGE-001` | Profile drift silently reinterprets field bytes or mutates a parent session. | Require an explicit `QiStateLineageForkReceipt` and immutable parent replay. | Ambiguous compatibility or parent mutation blocks resume/fork. |
| `QI-TXN-001` | Crash/replay interleaving, two competing callers, or Commit-B CAS duplicates an external effect, drops a response, or clears unknown truth. | Expand bounded explicit-state exploration and rerun Commit A/Commit B/two-caller CAS with exact authenticated resolution receipts. | Any unexplored interleaving, duplicate/dropped effect, unauthenticated resolution, or normal continuation after unknown truth blocks runtime. |
| `QI-EVID-001` | Adapter-off equality accepts similarity or hides a changed deterministic byte as telemetry. | Compare exact artifacts and mutate every volatile declaration/projection. | Only schema-declared volatile projection may differ; otherwise `FAIL`. |
| `QI-DOC-001` | Registry omits an ID/document or duplicates an entry while root prose claims completion. | G15B alone recomputes exact-once rows, manifest consistency, and every indexed-document link after G15A engineering readiness. | Missing/duplicate/orphaned registry coverage or any G15A documentation claim blocks final release. |
| `QI-ID-001` | A profile, receipt, or state silently substitutes codec/schema/projection/default bytes or uses a child hash without its root. | W1 constructs `cassi.qi-flow-contract-root.v1`; G1 and every consumer validate canonical child order and root hash before mutation. | Missing, reordered, substituted, or child/root-mismatched identity is `PROFILE_MISMATCH`; mint a new root and rerun G1/consumers. |
| `QI-CAP-001` | Allocated state or a reset/failed/uncommitted trajectory is mislabeled as reachable/usable/retained/reusable capacity, or topological-retention work is negative/unknown. | W6A/W6B/W10R publish `cassi.qi-flow-capacity-ladder.v1` from exact canonical `advance()` trajectories under frozen grammar/horizon/nonnegative incident/source work; G6A/G6B/G6C replay each rung and class. | Any reset acquisition, noncanonical trajectory, negative/unknown work, missing uncertainty/null predicate, or conflated geometric/reachable/observable/usable/retained/reusable rung is `FAIL`. |
| `QI-TEXT-003` | Text ownership is claimed from a static frame/alphabet or codebook rank is asserted without field-state necessity and uncertainty separation. | W11D publishes `cassi.qi-flow-text-ownership.v1` and `cassi.qi-flow-text-codebook-packing.v1`; G11/G11D run intact versus field-off/frozen/permuted interventions and exact packing/pruning replay. | Missing positive field-state-necessity evidence, overlapping packing intervals, rank/alphabet assumption, or pruned/exhaustive mismatch blocks text release; rerun W11D/G11/G11D. |

## Implementation coordination and integration order

The implementation uses stable shared interfaces without turning the design
into a frozen contract:

1. one integration owner maintains G0, the composite/subprofile identity graph,
   shared schema/receipt boundaries, and the single hashed
   `cassi.qi-flow-dependency-manifest.v1`; all Mermaid/prose/registry graph
   views are generated from or checked against that manifest;
2. each work package has one primary owner and disjoint source/test/artifact
   paths from the ownership table;
3. a cross-cutting improvement updates the plan/interface once, broadcasts the
   new identity, and migrates every consumer instead of accumulating shims;
4. implementers finish their named package and focused checks without running
   project-wide validation against concurrently changing siblings;
5. integration occurs at the declared parent edge, where the owner runs the
   focused command and records the artifact;
6. a failed integration returns to the owning package with raw state and the
   exact breached invariant; the design is repaired rather than preserved for
   the sake of a prior manifest;
7. full terminal/Godot/backend/release verification runs once after the
   integrated candidate lands, while focused regressions run throughout
   development.

The merge sequence is:

```text
Identity, numerics, law, conversion, scale, and intrinsic capacity:
  W0 -> W1 -> W2 -> W3 -> W3N/G3N -> W4 -> W4R/G4R
  -> W5 -> W5V/G5V -> W6 -> W6T/G6T -> W6A

Boundaries, cognition, retention, experience, and endpoint capacity:
  W6A -> W7 -> W7P/G7P -> W8 -> W9 -> W9O/G9O -> W10
  -> W10R -> W10E/G10E -> W10A
  W7 -> W11; W11 + W7P + W3N + W6T -> W11D
  W7P + W8 + W9O + W10 + W10R + W10E + W10A + W11D -> W6B

Backend, runtime, transaction lineage, and worlds:
  W6B -> W14A -> W12M/G12M -> W12L/G12L -> W12A -> W12E
  W12A -> W13R -> W13C -> G13D

Full-system selection, executable cutover, and release:
  W14A + W12E + W13C + G13D -> W14B -> G14B
  G14B -> W15A -> W16A -> G15A -> W15B -> W16B -> G15B
```

The requirement edges are not optional annotations: W3N/G3N establishes the
`QI-NUM-001` container and intrinsic certificate section; W4/G4, W4R/G4R,
W5V/G5V, and W6T/G6T close its required immutable parent-linked sections;
`QI-ID-001` is owned by Part 3, implemented by W1, and consumed by G1 through
`cassi.qi-flow-contract-root.v1`; `QI-SCALE-001` is closed by W6T/G6T with
the frozen rank/conditioning/cross-talk/work/cost selector and periodic/
resolution-scaled topology evidence; `QI-RET-001` by W4R/G4R;
`QI-RET-002` by W10R/G6B; `QI-RET-003` by W6A/W6B/W10R and G6A/G6B/G6C;
`QI-CONV-001` by W5V/G5V; `QI-BOUND-001` by W7P/G7P;
`QI-ACT-001` by W9O/G9O with offline paired-world discriminability;
`QI-PORT-001` by W6T/G6T; `QI-LEARN-001` by W10E/G10E;
`QI-TEXT-001` and `QI-TEXT-002` by W11D/G11D; `QI-TEXT-003` is owned by
Part 8, implemented by W11D, and consumed by G11/G11D through
`cassi.qi-flow-text-ownership.v1` and
`cassi.qi-flow-text-codebook-packing.v1`; `QI-LINEAGE-001` by W12L/G12L;
`QI-TXN-001` by W12M/G12M (including two callers and Commit-B CAS);
`QI-EVID-001` by W13C/G13D; and `QI-CAP-001` is owned by Part 2,
implemented by W6A/W6B/W10R, and consumed by G6A/G6B/G6C through
`cassi.qi-flow-capacity-ladder.v1`. `QI-DOC-001` is by W0/W15B/G15B only.
A failed edge stops every descendant and preserves its raw evidence.

This ordering minimizes shared-file churn without narrowing the endpoint.
Every named package from W0 through W16B, both worlds, both release backends,
every boundary, both retention classes, every new G3N/G4R/G5V/G6T/G6A/G6B/
G6C/G7P/G9O/G10E/G11D/G12M/G12L/G13D gate, every contract-root/capacity/
openness/action/delayed-influence/forgetting/text/certificate/indeterminate
artifact, and every external capability-matrix row remain implementation work.

## Clean deployment and rollback procedure

There is no automatic runtime fallback. Operational rollback means stopping
the failed flow service and deliberately restoring a prior source/config
deployment; it never means routing a live request to v2, Qwen, or a learned
stack.

The implementation campaign and release cutover sequence is:

1. before W1 or any implementation package changes a current source, config, or
   checkpoint, stop current writers and complete W0's snapshot under its global
   snapshot lock: `historical/qi-v2/source-index.json` maps every original
   root-relative source path to its exact
   `historical/qi-v2/source/<original-root-relative-path>` copy;
   `historical/qi-v2/checkpoint-index.json` maps every reachable old checkpoint
   to its content-addressed
   `historical/qi-v2/checkpoints/<sha256>.bin` copy; and
   `historical/qi-v2/manifest.json` binds both indexes, the exact
   `historical/qi-v2/run_cassi_qi_behavior_demo.py` wrapper,
   `historical/qi-v2/cassi-qi-language.json` config, old invocation/environment,
   counts, digests, and byte counts. Reopen-verify all bytes before any
   mutation;
2. execute the packages and gates in the declared acyclic order against new
   development run IDs, keeping the W0 snapshot and the hashed dependency
   manifest immutable: G3N must close `QiNumericalCertificate` before W4; G4R
   must close the topological-retention core before W5; G5V before conversion descendants;
   G6T before intrinsic capacity; G6A/G6B/G6C before endpoint claims; G7P
   before body/action ingress; G9O before experience; G10E before acquisition;
   G11D before endpoint text; and G12M/G12L before W12A. Record each QI-*
   receipt and return failures directly to the owning package.
3. stop terminal/provider/world writers, acquire the global cutover lock, and
   complete W15A: install the selected profile through `cassi-qi-flow.json`,
   create a fresh v3 session root, migrate every caller, remove obsolete live
   aliases/imports, and rebuild the import inventory;
4. have W16A generate the release-candidate manifest and run every required
   G0-G14B check from fresh processes, explicitly including
   G3N/G4R/G5V/G6T/G6A/G6B/G6C/G7P/G9O/G10E/G11D/G12M/G12L/G13D,
   terminal/provider, reference world, authenticated windowed CassiCosmos
   adapter, adapter-off exact-artifact check, CPU/ROCm, restart, raw process
   evidence, and independent verification;
5. repair any failure, regenerate the candidate identity, and rerun its
   changed dependency descendants until every listed engineering gate reports
   `status=PASS` with `engineering_ready=true`; this step performs no prose or
   registry certification;
6. have W15B update README/config examples to the exact working commands and
   capability surface, then have W16B verify them and G15B emit the final
   release board with `final_release_ready=true`;
7. start the canonical provider/world server and any explicitly invoked
   terminal against fresh v3 sessions only after the board passes;

8. retain old artifacts read-only. Rollback stops the affected flow service,
   restores only original paths named by the frozen source index, loads only
   checkpoint bytes named by the frozen checkpoint index, verifies every
   digest before use, and invokes only the manifest-bound historical wrapper/
   config/environment. It never converts state or opens a hidden legacy path.
Post-cutover research cards may run only from that final board in isolated
offline child processes. They are not G15 dependencies; their failure or
absence cannot add live fallback/state, weaken a gate, or delay release.
A post-cutover defect preserves its failed chain, repairs the design under a
new source identity, and reruns every affected check.

Old sessions fail with a clear schema/profile error and remain recoverable as
historical artifacts. A user who needs an old experiment invokes the explicitly
historical command/environment; a canonical request never converts, resets, or
falls back on their behalf.

## Target verification and launch commands

The completed implementation must make these target commands real.
`<development_run_id>` and `<candidate_run_id>` name distinct immutable run
roots; `<development_root>` and `<candidate_root>` expand to their respective
`_diag/cassi-qi-flow/<run_id>` directories. `<cleanup_fixture_root>` is a
disposable G12A confinement fixture: the commands below validate the exact
cleanup grammar without mutating candidate evidence. A real later cleanup
operator substitutes an approved run root only through the interactive
plan/apply/purge contract above.

```text
python run_cassi_qi_numerical_certificate.py --run-id <development_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --out gates/g03n-numerical-certificate
python run_cassi_qi_retention_core.py --run-id <development_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --out gates/g04r-retention-core
python run_cassi_qi_conversion_viability.py --run-id <development_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --out gates/g05v-conversion-viability
python run_cassi_qi_scattering.py --run-id <development_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --out gates/g06t-scale-scattering
python run_cassi_qi_boundary_permeability.py --run-id <development_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --out gates/g07p-boundary-permeability
python run_cassi_qi_observability.py --run-id <development_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --out gates/g09o-observability
python run_cassi_qi_experience_plan.py --run-id <development_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --out gates/g10e-experience-plan
python run_cassi_qi_dynamic_port.py --run-id <development_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --out gates/g11d-dynamic-port
python run_cassi_qi_transaction_model.py --run-id <development_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --out gates/g12m-transaction-model
python run_cassi_qi_state_lineage.py --run-id <development_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --out gates/g12l-state-lineage
python run_cassi_qi_cassicosmos_baseline.py --run-id <candidate_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json --adapter-off
python verify_cassi_qi_adapter_off_identity.py --run-id <candidate_run_id> --root _diag/cassi-qi-flow --gate-dir gates/g13d-adapter-off-equality
python verify_cassi_qi_requirements_registry.py --registry CassiFI/13-requirements-registry.md --docs CassiFI --gates CassiFI/11-validation-gates.md --owner-map CassiFI/10-work-packages.md
python run_cassi_qi_flow_manifest.py --phase historical-bootstrap --source-root . --historical-root historical/qi-v2 --config cassi-qi-language.json --entrypoint run_cassi_qi_behavior_demo.py
python run_cassi_qi_flow_manifest.py --phase development --run-id <development_run_id> --root _diag/cassi-qi-flow --profile cassi-qi-flow-development.json
python run_cassi_qi_validation.py --mode development --run-id <development_run_id> --root _diag/cassi-qi-flow --manifest run-spec/manifest.json --profile run-spec/profile.json
python run_cassi_qi_flow_manifest.py --phase release-candidate --run-id <candidate_run_id> --root _diag/cassi-qi-flow --profile cassi-qi-flow.json
python run_cassi_qi_validation.py --mode release-candidate --run-id <candidate_run_id> --root _diag/cassi-qi-flow --manifest run-spec/manifest.json --profile run-spec/profile.json
python run_cassi_qi_world_episode.py --world reference --run-id <candidate_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json
python run_cassi_qi_world_episode.py --world cassicosmos --run-id <candidate_run_id> --root _diag/cassi-qi-flow --profile run-spec/profile.json
python run_cassi_qi_release.py --stage candidate --run-id <candidate_run_id> --root _diag/cassi-qi-flow --manifest run-spec/manifest.json --profile run-spec/profile.json
python verify_cassi_qi_flow.py --root _diag/cassi-qi-flow --run-id <candidate_run_id> --manifest run-spec/manifest.json --profile run-spec/profile.json --board candidate/engineering-board.json
python run_cassi_qi_release.py --stage final --run-id <candidate_run_id> --root _diag/cassi-qi-flow --manifest run-spec/manifest.json --profile run-spec/profile.json
python verify_cassi_qi_flow.py --root _diag/cassi-qi-flow --run-id <candidate_run_id> --manifest run-spec/manifest.json --profile run-spec/profile.json --board release-board.json
python run_cassi_qi_artifact_cleanup.py --mode plan --root <cleanup_fixture_root> --expected-index-sha256 <index_sha256> --approved-digests run-spec/raw-retention-policy.json --out gates/g12a-live-runtime/artifact-cleanup/plan.json
python run_cassi_qi_artifact_cleanup.py --mode apply --root <cleanup_fixture_root> --plan gates/g12a-live-runtime/artifact-cleanup/plan.json --expected-plan-sha256 <plan_sha256> --out gates/g12a-live-runtime/artifact-cleanup/result.json
python run_cassi_qi_artifact_cleanup.py --mode purge --root <cleanup_fixture_root> --result gates/g12a-live-runtime/artifact-cleanup/result.json --expected-result-sha256 <result_sha256> --out gates/g12a-live-runtime/artifact-cleanup/purge.json
python run_cassi_conscious_chat.py --config conscious-chat.json --session-id <session_id> --create-session --request-sequence 0 --idempotency-key <key>
python cassi_persistent_provider.py --config conscious-chat.json --world-server
```

The explicit historical entry point is:

```text
python historical/qi-v2/run_cassi_qi_behavior_demo.py --manifest historical/qi-v2/manifest.json --config historical/qi-v2/cassi-qi-language.json
```

It has no import edge into any command above.

The real CassiCosmos arm and unchanged battery run from `../CassiCosmos` with
the documented Godot 4.7.1 Mono console executable:

```text
"C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" --path . res://scenes/verify_qi_world_adapter.tscn
"C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" --path . --headless -s res://verify/run_all.gd
```

The focused adapter scene is windowed. Only the existing battery runner uses
`--headless`; its GPU arms remain windowed children under the established
battery contract.

## Definition of complete

The full-system implementation is complete only when all of the following are
true:

- every target source/config/test/driver exists with production behavior; no
  placeholder, stub, alias, compatibility shim, unowned caller, or future
  unspecified acquisition mechanism remains;
- the canonical runtime owns exactly one adaptive `[S,9M,B]` field and all
  perception, transport, conversion, scale exchange, prediction, attention,
  retention, recall, acquisition, action, text, and persistence paths causally
  use it;
- production `topological-v1` topological-retention retention proves a nonzero barrier,
  source-free metastable residence, receipted phase slips, cue-causal return,
  interference/recovery, exact restart, and no fading-retention fallback or auxiliary
  topology state; every topological-retention capacity rung comes from exact canonical
  `advance()` under frozen grammar, exact physical horizon, and nonnegative
  incident/source work, with reset excluded from acquisition and capacity
  classes kept distinct;
- intrinsic and endpoint capacity audits both pass; every required coordinate
  is reachable and observable over its horizon, and dark/uncommitted dimensions
  are excluded from capacity;
- optical, audio, proprioceptive, text, and motor boundaries pass fixed
  transform/frame/work/unit contracts under the rational multirate clock,
  antialias, watermark, durable replay, and exact-once ingress rules; every
  mandatory sensory port also passes field-derived incident-work-normalized
  openness and bounded recovery;
- text emission selects only terminal-positive reaction-feasible trajectories
  against raw/null uncertainty, commits a passive full-Hamiltonian reaction,
  flushes UTF-8 exactly, demonstrates field-state necessity and uncertainty-
  aware codebook separation/packing, and demonstrates designated output rather
  than perpetual abstention; rank is not assumed to be 260 or the alphabet
  size;
- motor emission has a passive `world_effect=false` proposal reaction, and
  prediction, proposal, command, acknowledgement, applied efference, remap, and
  residual are separately identified; only terminal `applied` changes the
  world/remap path;
- repeated ordinary experience crosses a receipted topological-retention basin barrier,
  produces post-washout held-out improvement, and survives interference/restart
  without another adaptive object;
- the deterministic world and real CassiCosmos adapter both complete the exact
  sensing-plus-provider-text/applied-action loop without labels, no-peek
  breaches, duplicate effects, lock-held I/O, or a second field; unknown
  external truth remains a sealed indeterminate lineage unless exact
  authenticated resolution succeeds, and two-caller Commit-B CAS behavior,
  adapter-off deterministic CassiCosmos bytes match the pre-W13C baseline
  exactly, raw artifacts remain retained, and only schema-declared volatile
  telemetry uses the G13D projection contract;
- CPU and ROCm execute the release capacity under termwise stage/stability/
  space-scale/Hodge/retention/topology parity, decision margins, allocation,
  end-to-end request cost, latency, and long-horizon contracts with no fallback;
- terminal and loopback provider validate before session lock/state allocation,
  run the same engine, commit ingress/response/outbox/efference atomically,
  stream stored bytes exactly, restart exactly, and touch zero Qwen/GGUF/llama/
  learned runtime resources;
- W15A cleanly removes every old live caller while preserving historical
  `_diag` and the pinned GGUF, and W16A freezes the external capability matrix,
  executable source/config/profile/projections/schemas/fixtures/toolchain/
  commands before rerunning every required post-cutover artifact;
- one candidate run root contains canonical `run-spec` objects, the single
  hashed machine-readable dependency manifest, every required G1-G14B indexed
  receipt, the G15A engineering board with `engineering_ready=true`, downstream
  G15B documentation receipt/final board, and a graph independently
  recomputable by hash without external paths or candidate-edited verifier
  logic;
- every required capability row is `PASS`, none is `BLOCKED` or `NOT_RUN`, and
  README/current commands exactly match the final board.
- every new gate `G3N`, `G4R`, `G5V`, `G6T`, `G6A`, `G6B`, `G6C`, `G7P`, `G9O`,
  `G10E`, `G11D`, `G12M`, `G12L`, `G12A`, and `G13D` is `PASS` from the same
  post-cutover candidate; none is inferred from a neighboring gate,
  pre-cutover receipt, summary, or root-monolithic-plan prose;
- `QI-NUM-001`, `QI-ID-001`, `QI-CAP-001`, `QI-SCALE-001`, `QI-RET-001`,
  `QI-RET-002`, `QI-RET-003`, `QI-CONV-001`, `QI-BOUND-001`, `QI-ACT-001`,
  `QI-PORT-001`, `QI-LEARN-001`, `QI-TEXT-001`, `QI-TEXT-002`,
  `QI-TEXT-003`, `QI-LINEAGE-001`, `QI-TXN-001`, and `QI-EVID-001` each
  have their required receipt, raw artifacts, independent replay, mutation
  controls, and consuming gate; the immutable certificate extension chain
  names a complete section inventory, and the topological-retention core precedes
  conversion while behavioral retention remains W10R-owned;
- `QI-DOC-001` passes G15B: `13-requirements-registry.md` has exactly one
  section/row for each shared ID, maps owner document/package/gate/artifacts/
  failure semantics, and covers every indexed CassiFI document while the root
  monolith remains a non-normative navigation pointer;
- completion is denied if any required gate or registry row is `BLOCKED`,
  `NOT_RUN`, missing, duplicated, stale, or supported only by a deterministic
  projection outside its schema declaration.

A failed required cognition, topological-retention retention, grounding, language, backend,
security, persistence, or embodiment check means the full endpoint still needs
engineering work. Its immutable failure artifact is useful diagnosis, but it
does not authorize a static substitute, omitted subsystem, learned sidecar,
fading-retention fallback, weakened capability matrix, stale evidence, or reduced
endpoint.


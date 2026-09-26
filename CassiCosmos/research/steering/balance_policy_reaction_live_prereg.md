# Balance Policy Reaction-Context Live Continuation

## Status: Plan—pre-registered 2026-08-17; no live run

This is a NEW preregistration following the offline regime wave. It does not edit or supersede `balance_policy_regime_prereg.md`, its result, or its receipts.

## 1. Claim scope and frozen primary policy

The offline result selects the parsimonious `REACTION` block as the primary contextual policy. REACTION and ALL_NO_TRANSPORT tie the best validation result (`0.9375` accuracy; `2.2099690088942807e-9` regret), while REACTION uses 17 features versus 25. TRANSPORT and ALL have slightly worse regret, and transport ablation fails. This continuation therefore tests only **contextual gain scheduling** on frozen seeds; it does not test or claim reaction–transport mechanism support, general intelligence, or general policy learning.

The primary policy is copied exactly from `_diag/balance_policy_regime/result.json`; it is not refit, pruned, threshold-tuned, or changed. Frozen model record:

- Feature IDs, exact order: `[1,2,3,4,5,6,7,8,9,10,11,12,13,14,23,24,25]` (F02 and F13 remain included despite their degeneracy flags).
- Weights: exact `models.REACTION.weights` 18×3 matrix.
- Means: exact `models.REACTION.mean`.
- Standard deviations: exact `models.REACTION.std`.
- Final training loss: `0.18894791216349827`.
- Validation: accuracy `0.9375`, regret `2.2099690088942807e-9`.
- Majority validation: accuracy `0.875`, regret `3.661939830774534e-9`.
- REACTION frozen-permutation validation: accuracy `0.1875`, regret `1.800619553843945e-7`.
- Manifest partition hash: `398dd4c43756bc038697a4ed3d4ca27e84216a5797dab5552121aef432a07072`.
- Manifest feature hash: `a180dab27cf389d1217d5e0bca5f2753e6d6bcafa4200681a2729355c76170a7`.
- Canonical model-record SHA-256: `519d093e946bbb163f20f8e37b3c2cccc90d049f1cd3f150cdcf64267cbd6d59`.

The model-record hash is SHA-256 of canonical UTF-8 JSON (`sort_keys=true`, separators `(',',':')`, `allow_nan=false`) over exactly `{feature_ids,weights,mean,std,loss,manifest_hashes}`. Before any live run, recompute and require equality. Also require every frozen source hash and manifest hash to match the official result. No live standardization or refit is permitted.
The implementation must compute the frozen model hash by loading the official JSON fields in their exact stored numeric arrays, constructing the exact ordered object `{feature_ids,weights,mean,std,loss,manifest_hashes}`, canonicalizing with the same UTF-8 JSON settings, and hashing those bytes; it must self-test equality to `519d093e946bbb163f20f8e37b3c2cccc90d049f1cd3f150cdcf64267cbd6d59`. No alternate extraction, float formatting, or re-serialization path is accepted.

`H*` and `J_proxy` are fully held out from action, branch selection, and policy features. They may be recorded only as disclosed diagnostics. The claim is limited to contextual gain scheduling under this protocol.

## 2. Frozen engine, IC, and live seeds

- Pinned scene: `scenes/mind_engine_cache.tscn`, `N=32`, `auto_step=false`, bridge `127.0.0.1:7599`.
- Constants: `phi=1.618033988749895`, `dt=0.005`, `omega2=20`, `extent=(1,1,1)`, `source_strength=0`, `ham_completion=0`, `sigma=1`, analytic strength `0.25`, absolute charge budget `<=0.25` per rung.
- IC: exact `tools/balance_spiral_observability.py::make_ic(seed,10)`.
- Live seeds: `20260817`, `20260819`, `20260821`, untouched by offline fitting.
- Cadence: `[1,2,3,4,7,11,18,29]`; project `k=8`; returned CPU projection indices/coordinates are authoritative. Projection uses CPU `i=gx*N*N+gy*N+gz`; shader invocation indexing is distinct and unchanged.
- History F26–F30 follows the frozen regime collector convention exactly: rung 0 has its prescribed zero previous-summary values and `history_valid=0`; later rungs use only the immediately previous pre-action field summary within the same arm. No history crosses arms or seeds.

A pre-run scene parser must require exact pinned properties: grid_n 32, auto_step false, bridge_port 7599, and Script ext-resource path `res://scripts/cassi_mind_engine.gd` assigned by the matching ExtResource ID. The `clear` reply is validated only as `{ok:true,cmd:"clear"}`; it has no required step/time fields. Then `ping` must report `{step:0,t:0}`. Step/time are checked on ping, flush step, every readout/project, and every post-action step/readout. Timing is never inferred.
### Pre-run clarification (2026-08-17; no live run)

“Projection payload identity across matched arms” means: (a) every projected cell payload is validated and stored against the same-arm readout and the authoritative CPU index/coordinates; (b) rung-0 payloads and baselines must match across fresh arms; later projection values/cells may diverge because interventions change the field. Protocol, candidate set, cadence, and constants remain identical across all arms. Frozen-P logits, probabilities, and recommendation are recorded counterfactually on every arm, while only P acts on them.

## 3. Arms and frozen policy action

Run five fresh arms per seed with identical IC, cadence, and readout protocol:

- **D:** undriven control; no candidate deposit at decision rungs.
- **A:** analytic multiplier `1.0` at every rung.
- **M:** constant majority multiplier `1.5` at every rung.
- **P:** frozen REACTION argmax selecting `{0.5,1.0,1.5}`.
- **R:** deterministic random candidate from `{0.5,1.0,1.5}`, generated with `default_rng(2026081701 + seed_index)` and one draw per rung, reset by seed in frozen seed-list order.

For P, compute the exact 30-feature vector with the frozen regime module, select only the frozen REACTION IDs, standardize with frozen training means/stds, prepend the unstandardized intercept, multiply by frozen weights, and choose the first argmax in class order `[0.5,1.0,1.5]`. Do not drop F02/F13. Do not use H*, J_proxy, future/post-action fields, live labels, or thresholds. Direction, TSC deposit, sign convention, sigma, analytic formula, and budget projection are unchanged.

## 4. Per-rung measurements and identity gates

Each arm records pre-action features, P logits/probabilities, selected multiplier, deposited `cy/ci`, cumulative absolute charge, exact step/time envelope, post-cadence epsilon RMS, q coherence/power, field power, and held-out H*/J diagnostics. Endpoint is the final post-rung readout. Integrated balance is the arithmetic mean of epsilon RMS across the eight post-rung readouts; endpoint and integrated metrics use identical formulas in every arm.

Before accepting a seed, require all arms to have eight complete rungs and finite values. Require identical IC identity, candidate set, cadence, constants, projection payload identity, and step/time envelope across matched arms. Require P's source/model/manifest hashes to match the frozen record, finite features/logits/actions, first-argmax determinism, and total absolute charge `<=0.25` at every rung. The live tool's own source hash is written before the run and after the run and must match. Any mismatch, missing response, nonfinite quantity, changed source/model hash, changed seed/IC/cadence/N/constants, or malformed envelope is **INVALID—STOP**.

Safety is a field/readout identity gate, not a ratio to D: every readout must be finite; canonical coherence cell values must lie in `[0,1]` within the frozen tolerance; maximum cell field power at any readout must be `<=100×` the same-seed post-IC baseline maximum field power; per-rung absolute charge must be `<=.25`; and exactly eight rungs must complete. Do not ratio action charge, endpoint epsilon, or integrated epsilon to D for safety. A zero post-IC baseline power with positive later power is a safety failure.

## 5. Frozen efficacy decision tree

Define P endpoint-win-D/M strictly by lower endpoint epsilon RMS. Define integrated non-worse-versus-M only within the same seeds where P wins M, using `P_integrated <= M_integrated` (exact equality passes). Report A and R in every per-seed table.

1. Any source/model/manifest hash, scene, step/envelope, IC, finite, charge, candidate, or 100× safety failure → **INVALID—STOP**.
2. If P's selected action sequence equals M at every rung for every live seed → **COLLAPSES TO MAJORITY**, regardless of metrics.
3. **ADOPT** requires P endpoint epsilon RMS < D in at least 2/3 seeds, P endpoint epsilon RMS < M in at least 2/3 seeds, and integrated P <= M in those same P-vs-M winning seeds. A is reported as a matched analytic control; P must also pass safety.
4. If P beats D and A in at least 2/3 seeds on endpoint epsilon RMS but fails the strict ADOPT M criterion → **REDISCOVERS HIGH GAIN**.
5. If P beats D in fewer than 2/3 seeds → **REJECT**.
6. If P beats D in at least 2/3 but satisfies neither strict ADOPT nor REDISCOVERS HIGH GAIN → **HOLD/INCONCLUSIVE**.

No threshold, seed, arm, or metric change is permitted after observing outcomes. No live policy is adopted beyond this tree. Any further refinement requires a separate new preregistration.

## 6. Outputs and implementation contract

Implementation is not part of this turn. Planned file: `CassiCosmos/tools/balance_policy_reaction_live.py` (implemented in this turn but not run against Godot).

Planned new outputs:

- `_diag/balance_policy_reaction_live/manifest.json`: canonical protocol, exact model record, source/model/manifest hashes, seeds, arm constants, RNG declaration;
- `_diag/balance_policy_reaction_live/raw.json`: per-seed/arm/rung readouts, features, logits, actions, charge, endpoint, integrated values, envelope and held-out diagnostics;
- `_diag/balance_policy_reaction_live/result.json`: safety gates, matched-control tables, action sequences, endpoint/integrated metrics, and exact tree branch;
- `_diag/balance_policy_reaction_live/summary.json`: compact verdict receipt.

The tool must expose `--self-test`, `--collect`, and `--all`. Self-test must not contact Godot and must verify model-record hash, source/manifest hashes, exact REACTION IDs/order including F02/F13, no H*/J action dependence, deterministic logits/argmax/R RNG, arm isolation, charge budget, step/envelope checks, scene contract, action-sequence collapse fixture, efficacy branches, and 100× safety fixture. Canonical JSON uses UTF-8, recursive `sort_keys=true`, separators `(',',':')`, `allow_nan=false`, and no trailing newline. Manifest is written before raw collection and source hashes are checked before/after.
## Synthetic-smoke amendment

Before any scientific collection, a harness-only actual-engine sidecar smoke may use seed `20260000` and the actual `run_arm` implementation for D followed by P, with the same eight-rung cadence, baseline/envelope/safety/hash gates, and no efficacy interpretation. Its metrics and outputs are discarded and it must not enter the decision tree or official result. The sidecar is stopped and restarted around the smoke to confirm clean arm initialization; this amendment does not alter the three frozen scientific seeds or any verdict criterion.

### Disclosed smoke receipt — S0

On 2026-08-17, a fresh windowed sidecar (PID 16664) reached bridge readiness on port 7599, but the harness wrapper's `request` binding raised `TypeError: req() takes 1 positional argument but 2 were given` before `run_arm` executed D or P. Therefore no seed-arm field command, outcome, or metric was executed or observed, and no official output was written. This was not a scientific arm. The first-failure stopping rule was obeyed; only the launched sidecar was terminated, and its process plus port 7599 were closed.

### Frozen replacement smoke — S1

S1 is the single replacement harness-only smoke: use `regime.obs.BridgeClient` directly (no custom request wrapper), with seed `20260000`, D followed by P, and the same identity/safety-only gates: initial ping at step 0/time 0; identical D/P baseline digest and rung-0 projection digest; eight rungs and eight actions each; exact `[1, *CADENCE]` post-step envelope; safe flags; exact model and source hashes; legal P actions; all-zero D actions; unchanged source hashes. Do not inspect or report endpoint, integrated-efficacy, H, or J metrics; do not run `tree`; write no official output. Any S1 failure stops this harness-only path with no further smoke retry.

No scientific thresholds, actions, seeds, arms, metrics, or verdict criteria changed. Status remains explicitly no scientific live run.
### Disclosed smoke receipt — S1

On 2026-08-17, a fresh windowed sidecar (PID 29824) reached bridge readiness on port 7599 and the harness used `regime.obs.BridgeClient` directly for seed `20260000`, D followed by P. The D synthetic run reached heldout, then failed with `KeyError: 'qi_coherence'` in `observe`; no tree was called, no official output was written, and no endpoint, integrated-efficacy, H, or J metric was inspected or reported. The client was closed; only PID 29824 was stopped, and process plus port cleanup was proved. S1 was not retried.

V1 scientific collection did not run. The V1 live gate is closed; any continuation requires a separately preregistered V2. No scientific thresholds, actions, seeds, arms, metrics, or verdict criteria changed.

## 7. Stopping rule and audit status

This preregistration is finalized; no Godot launch, live collection, or result run occurred in this turn. Stop on the first actual harness or scientific failure; do not retry a scientific arm. Preserve D/A/M/R honest controls and null outcomes. The only supported claim, if ADOPT fires, is contextual gain scheduling on these frozen live seeds and protocol—not reaction–transport mechanism support, not general intelligence.

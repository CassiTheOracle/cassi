# Balance Policy Reaction-Context Live Continuation — v2

## Status: Pre-registered v2 continuation — no scientific live run

This is a fresh, self-contained v2 preregistration after the closed v1 continuation's S0 and S1 harness `INVALID` receipts. V1 scientific collection did not run: S0 failed before `run_arm`, and S1 reached the real D arm's heldout path before the observability data-shape `KeyError: 'qi_coherence'`. V1's live gate is closed. This document is not a patch to v1 and does not reopen or alter it; it is the only protocol governing a future v2 invocation.

V2 has no optional engine pre-smoke. The offline self-test is passed. The first next engine invocation under this document is the scientific collection. No result, threshold, arm, seed, or metric may be selected or revised using either v1 harness failure.

## 1. Claim scope and frozen scientific content

The offline result selects the parsimonious `REACTION` block as the primary contextual policy. This continuation tests contextual gain scheduling on frozen seeds only. It does not test or claim reaction–transport mechanism support, general intelligence, or general policy learning. The model is copied exactly from `_diag/balance_policy_regime/result.json`; it is not refit, pruned, threshold-tuned, or changed.

Frozen model facts:

- REACTION feature IDs, exact order: `[1,2,3,4,5,6,7,8,9,10,11,12,13,14,23,24,25]` (F02 and F13 remain included).
- Final training loss: `0.18894791216349827`.
- Manifest partition hash: `398dd4c43756bc038697a4ed3d4ca27e84216a5797dab5552121aef432a07072`.
- Manifest feature hash: `a180dab27cf389d1217d5e0bca5f2753e6d6bcafa4200681a2729355c76170a7`.
- Canonical model-record SHA-256: `519d093e946bbb163f20f8e37b3c2cccc90d049f1cd3f150cdcf64267cbd6d59`.

The model-record hash is SHA-256 of canonical UTF-8 JSON (`sort_keys=true`, separators `(',',':')`, `allow_nan=false`) over exactly `{feature_ids,weights,mean,std,loss,manifest_hashes}` loaded from the official result. No live standardization, refit, alternate extraction, float formatting, or re-serialization path is permitted.

`H*` and `J_proxy` are fully held out from action, branch selection, and policy features. They are disclosed diagnostics only. Endpoint and integrated metrics are epsilon metrics, not H/J metrics.

## 2. Frozen engine, scene, IC, and constants

- Pinned scene: `scenes/mind_engine_cache.tscn`.
- Grid: `N=32`; scene must have `auto_step=false`, bridge port `7599`, and script `res://scripts/cassi_mind_engine.gd` bound through the matching ExtResource ID.
- Bridge: `127.0.0.1:7599`; launch only the repo-authoritative 4.7.1 Mono console executable in the run record, windowed and never `--headless`.
- Constants: `phi=1.618033988749895`, `dt=0.005`, `omega2=20`, `extent=(1,1,1)`, `source_strength=0`, `ham_completion=0`, `sigma=1`, analytic strength `0.25`, and absolute charge budget `<=0.25` per rung.
- IC: exact `tools/balance_spiral_observability.py::make_ic(seed,10)`.
- Scientific seeds, untouched by offline fitting: `20260817`, `20260819`, `20260821`.
- Cadence: `[1,2,3,4,7,11,18,29]`; `k=8`; returned CPU projection indices/coordinates are authoritative. CPU projection index is `gx*N*N+gy*N+gz`; shader invocation indexing is distinct and unchanged.
- History F26–F30 follows the frozen collector convention: rung 0 uses prescribed zero previous-summary values and `history_valid=0`; later rungs use only the immediately previous pre-action field summary within the same arm. No history crosses arms or seeds.

Before collection, parse and require the exact scene contract. Validate `clear` as `{ok:true,cmd:"clear"}` and then require `ping` `{step:0,t:0}`. Validate step/time on ping, flush step, every readout/project, and every post-action step/readout; timing is never inferred.

## 3. Arms and frozen action policy

Run five fresh arms per scientific seed with identical IC, cadence, and readout protocol:

- **D:** undriven control; no candidate deposit at decision rungs; action is exactly `0.0` at all eight rungs.
- **A:** analytic multiplier exactly `1.0` at every rung.
- **M:** constant majority multiplier exactly `1.5` at every rung.
- **P:** frozen REACTION policy: compute the exact 30-feature vector, select only the frozen REACTION IDs above, standardize with frozen training means/stds, prepend the unstandardized intercept, multiply by frozen weights, and take the first argmax in class order `[0.5,1.0,1.5]`.
- **R:** deterministic random candidate from `{0.5,1.0,1.5}`, using `default_rng(2026081701 + seed_index)` with one draw per rung, reset by scientific seed-list order.

The P first-argmax and R candidate rules are frozen exactly. Do not drop F02/F13. Do not use H*, J_proxy, future/post-action fields, live labels, or thresholds. Direction, TSC deposit, sign convention, sigma, analytic formula, and budget projection are unchanged.

## 4. Sole declared source correction

The only declared source correction between the closed v1 implementation and v2 is `observability_field`. Real heldout now derives the complete observability representation from the same EY/EI readout using `regime.obs.derive_arrays(...)` before observability and matched-control diagnostics. The complete representation is exactly `{ey,ei,field_power,eps,rho,qi_coherence,theta}`.

This correction fixes harness data-shape compatibility only. It does not change action features, policy inputs, action selection, deposits, PDE evolution, constants, five arms, scientific seeds, cadence, thresholds, endpoint or integrated statistics, H/J separation, safety gates, or the decision tree. No ad hoc keys are added and no missing-key exception is suppressed.

## 5. Per-rung measurements, endpoint, integrated metric, and safety

Each arm records pre-action features, P logits/probabilities, selected multiplier, deposited `cy/ci`, cumulative absolute charge, exact step/time envelope, post-cadence epsilon RMS, q coherence/power, field power, and held-out H*/J diagnostics. Endpoint is the final post-rung epsilon RMS. Integrated balance is the arithmetic mean of epsilon RMS over the eight post-rung readouts. Endpoint and integrated formulas are identical for every arm.

Before accepting a seed, require five arms with eight complete rungs, finite values, identical IC identity, candidate set, cadence, constants, projection payload identity, and step/time envelope across matched arms. Require P source/model/manifest hashes, finite features/logits/actions, first-argmax determinism, and total absolute charge `<=0.25` at every rung. The live tool source hash is captured before and after the run and must match. Any mismatch, missing response, nonfinite quantity, changed source/model/prereg/scene hash, changed seed/IC/cadence/N/constants, or malformed envelope is `INVALID—STOP`.

Safety is a field/readout identity gate, not a ratio to D: every readout is finite; canonical coherence cell values lie in `[0,1]` within the frozen tolerance; maximum cell field power at any readout is `<=100×` the same-seed post-IC baseline maximum field power; per-rung absolute charge is `<=.25`; and exactly eight rungs complete. A zero post-IC baseline power with positive later power is a safety failure. Do not ratio charge, endpoint epsilon, or integrated epsilon to D for safety.

## 6. Frozen efficacy decision tree

Define P endpoint-win-D/M strictly by lower endpoint epsilon RMS. Define integrated non-worse-versus-M only within the same seeds where P wins M, using `P_integrated <= M_integrated`; exact equality passes. Report A and R for every seed.

1. Any source/model/manifest/prereg/scene, step/envelope, IC, finite, charge, candidate, or 100× safety failure → **INVALID—STOP**.
2. If P's selected action sequence equals M at every rung for every scientific seed → **COLLAPSES TO MAJORITY**, regardless of metrics.
3. **ADOPT** requires P endpoint epsilon RMS `< D` in at least 2/3 seeds, P endpoint epsilon RMS `< M` in at least 2/3 seeds, and integrated P `<= M` in those same P-vs-M winning seeds. P must pass safety.
4. If P beats D and A in at least 2/3 seeds on endpoint epsilon RMS but fails strict ADOPT M criterion → **REDISCOVERS HIGH GAIN**.
5. If P beats D in fewer than 2/3 seeds → **REJECT**.
6. If P beats D in at least 2/3 but satisfies neither strict ADOPT nor REDISCOVERS HIGH GAIN → **HOLD/INCONCLUSIVE**.

No threshold, seed, arm, metric, source correction, or decision-tree criterion may be changed after observing outcomes. No live policy is adopted beyond this tree. Any further refinement requires a separate preregistration.

## 7. Output receipt and hash contract

No official output is written before all source and scene checks pass. The manifest is written before raw collection and contains the canonical protocol, exact model record, source/model/manifest/prereg/scene hashes, scientific seeds, arm constants, RNG declaration, and collection identity. The planned official files are:

- `_diag/balance_policy_reaction_live/manifest.json`: canonical protocol, exact model record, all frozen hashes, seeds, arm constants, and RNG declaration.
- `_diag/balance_policy_reaction_live/raw.json`: per-seed/arm/rung readouts, features, logits, actions, charge, endpoint/integrated values, envelope, and held-out diagnostics.
- `_diag/balance_policy_reaction_live/result.json`: safety gates, matched-control tables, action sequences, endpoint/integrated metrics, and exact tree branch.
- `_diag/balance_policy_reaction_live/summary.json`: compact verdict receipt.

Canonical JSON is UTF-8, recursive `sort_keys=true`, separators `(',',':')`, `allow_nan=false`, with no trailing newline. Source hashes are checked before and after collection. Any official output mismatch is `INVALID—STOP`.

## 8. One-attempt stopping rule and no-retroactive inference

Each scientific arm is one attempt. Stop on the first harness, bridge, source, identity, safety, or scientific failure; do not repair, retry, substitute a seed, rerun an arm, or continue to later arms after that failure. No optional pre-smoke exists in v2: the first engine invocation is the scientific collection.

The v1 S0 and S1 harness INVALIDs are historical receipts only. They provide no retroactive inference about a scientific arm, field outcome, metric, action, threshold, or verdict. The v2 `observability_field` correction is a compatibility repair, not evidence for or against the claim. V1 closure is recorded in `research/steering/balance_policy_reaction_live_prereg.md`; v2 does not reopen it.

## 9. Frozen receipt of current inputs

These hashes and IDs were read offline on 2026-08-17 while authoring this document; offline path and hash checks only; no Godot/engine/output collection.

- Live runner source: `tools/balance_policy_reaction_live.py` — SHA-256 `a6e66d3534cb60462ac0ffd77f291f24f9a4ec5ad6aff34d80dff4e3d2183c59`.
- Closed v1 prereg: `research/steering/balance_policy_reaction_live_prereg.md` — SHA-256 `525b048bb13ddcdd0bbb437ccb29d610713babf4c92e3d192227709379e07b00`.
- The run-time manifest records `prereg_sha256` as the SHA-256 of this exact final v2 file immediately before collection. It is not embedded here because self-embedding has no fixed-point value.
- Regime dependency: `tools/balance_policy_regime.py` — SHA-256 `38d589e27882655aaa822494c4e8b4f7ede52931fa2c9f4dc5bf655b37c676f7`.
- Observability dependency: `tools/balance_spiral_observability.py` — SHA-256 `bb96ecb1b0914e7b526db1c11218668acc5f4a14da3dc7569de088f00ae1c37d`.
- Model result: `_diag/balance_policy_regime/result.json` — SHA-256 `848d88eaa928ca5efc279b5c52f5e3259c0d50bc1963fe29a5f921e2ba38d2d2`.
- Model manifest: `_diag/balance_policy_regime/manifest.json` — SHA-256 `df763748be141a0290a7d879740cf0990f6d12cfef3d399506247b96010082c7`.
- Pinned scene: `scenes/mind_engine_cache.tscn` — SHA-256 `1161771b93226a809441d09c2dbdadbe0460f55b950c8e318f2e58fcd298ae6e`.
- REACTION feature IDs/order: `[1,2,3,4,5,6,7,8,9,10,11,12,13,14,23,24,25]`.
- Model-record SHA-256: `519d093e946bbb163f20f8e37b3c2cccc90d049f1cd3f150cdcf64267cbd6d59`.
- Regime manifest partition hash: `398dd4c43756bc038697a4ed3d4ca27e84216a5797dab5552121aef432a07072`.
- Regime manifest feature hash: `a180dab27cf389d1217d5e0bca5f2753e6d6bcafa4200681a2729355c76170a7`.

### Validation receipt

The cited paths above were validated by offline file reads and SHA-256 hashing. The run-time manifest convention above is the non-self-referential receipt for this file; no concrete v2 self-hash is embedded. No scientific inconsistency was found in the frozen IDs, cadence, seeds, arms, hashes, or source-correction statement.

### V2 collection receipt — INVALID—PROTOCOL (2026-08-17)

The one authorized collection used fresh windowed sidecar PID `30436`; the exact command `python tools/balance_policy_reaction_live.py --collect` exited `0`. The official artifact files and SHA-256 audit receipts were: `_diag/balance_policy_reaction_live/manifest.json` `fc1c567b226288b952d9193e6872c22bc2d18eadf66822472a80d40195a90f88`; `_diag/balance_policy_reaction_live/raw.json` `913d643a410520838bd89a5002598e9f24febdd72d50a95fde07de8dafe414a6`; `_diag/balance_policy_reaction_live/result.json` `1a761626f9b4dd21e35dfe05b52a399e2df67cb862845dc57efda87b0c501f42`; `_diag/balance_policy_reaction_live/summary.json` `09bf313447b4a6d53167b5c92f2c13ca502178c7d39b40c60d590f0257dfe12c`.

The internal receipt, safety, and arms gates reported `true`, but the manifest/result protocol is `balance-policy-reaction-live-v1` and `live_prereg_sha256` identifies the closed v1 prereg (`525b048bb13ddcdd0bbb437ccb29d610713babf4c92e3d192227709379e07b00`) rather than the frozen v2 protocol and exact final v2 prereg hash convention. The exact v2 receipt gate therefore fails before efficacy interpretation. The observed raw collection is an audit receipt only, not a v2-valid efficacy result; its `REDISCOVERS HIGH GAIN` label is not a v2 scientific verdict. No V2 `ADOPT`, `REDISCOVERS`, `REJECT`, or `HOLD` verdict is assigned. No rerun or substitution is permitted under the v2 one-attempt stopping rule.

### Final status

**V2 is closed INVALID—PROTOCOL. No valid scientific live conclusion is assigned; no adoption or efficacy interpretation is permitted, and no rerun/substitution may occur under this frozen v2 protocol.**
This v2 closure is the current live-policy record for the balance-policy program. The raw `REDISCOVERS HIGH GAIN` string in `_diag/balance_policy_reaction_live/summary.json` is retained as an audit receipt only; it is not a valid v2 conclusion because the receipt protocol and preregistration hash remained v1. The offline reaction discriminator remains **CONTEXT SUPPORTED / TRANSPORT PROXY NOT SUPPORTED**. V1 closed after S0/S1 `INVALID` harnesses. Focused offline regressions passed. No live efficacy conclusion, policy adoption, or rerun under the closed v2 protocol is authorized.

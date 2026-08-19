# Balance Policy — Local Reaction/Transport Regime Pre-registration

## Status: Plan—pre-registered 2026-08-17; locked before collection or experiment

This response-archaeology wave tests whether minority low-gain (`0.5×`) decisions are distinguished by local reaction-versus-transport structure rather than generic capacity. The protocol below was locked before collection. No live seed is used.

## 1. Scope and exact operator boundary

The sidecar readout exposes float32 `EY`/`EI`; bridge CPU projection/readout uses `i=gx*N*N+gy*N+gz`, while shader invocation indexing is `i+N*(j+N*k)`. The distinction is retained explicitly. Readout algebra is `P=EY²+EI²`, `rho=EY+EI`, `epsilon=EY−phi*EI`. With `ham_completion=0`, `omega2=20`, `source_strength=0`, and zero sidecar rho buffer, exact reconstructed components are `acc_EY=lap_EY−20*epsilon` and `acc_EI=lap_EI+20*epsilon`. Velocity is unavailable; no full next-step transport split, wake, or advection is claimed. Shader-exact periodic 19-point Laplacian uses `h_i=2*extent_i/N`, `extent=(1,1,1)`. Gradients, J_proxy, divergence, and anisotropy are deterministic readout proxies.

## 2. Frozen engine, actions, and partitions

Scene `scenes/mind_engine_cache.tscn`, `N=32`, `auto_step=false`, bridge `127.0.0.1:7599`, `dt=.005`, `phi=1.618033988749895`, `omega2=20`, `source_strength=0`, `sigma=1`, `B=.25`, analytic strength `.25`, cadence `[1,2,3,4,7,11,18,29]`, `project k=8`, candidates `[.5,1,1.5]`. Prefix candidates are `1.0`; designated candidate is applied only at the designated rung; every branch is fresh. Training seeds `20260901..20260908`; validation `20260911,20260912`; untouched live seeds `20260817,20260819,20260821`; fit seed `20260900`; permutation seed `20260913`. Projection uses N−1 endpoint coordinates while scatter uses N/2; returned CPU projection index/coordinates are authoritative.

## 3. Label and response

One aggregate decision row measures `y(m)=epsilon_RMS²(pre)−epsilon_RMS²(post)` after exactly one cadence interval. Label is first argmax in ordered candidates `.5<1<1.5`; raw responses remain float64. `H*` is fully held out and never a feature, target, metric, or selection input.

## 4. Rows and feature manifest

Exactly 80 classifier rows: one seed/rung decision, 10 offline seeds × 8 rungs. Features aggregate over the eight projected cells and global field. Auxiliary provenance is numeric float64 `(80,8,11)` with fields `(rank,index,gx,gy,gz,x,y,z,EY,EI,P)` from canonical `.5×` pre-action branch. All three branches must have identical pre-action projected payload and all 30 features before responses are accepted. Decoded fields stay float32; feature math/reductions are float64. Quantile is NumPy linear q=.50. F01/F02 masks are exact `>0`; support floor is `P>1e-6*max(P)`, zero-field support=0. Ratio guard: if reaction norm ≤1e−12, ratio=0 and flag=1.

|ID|Name and scalar formula|Family / class|
|---|---|---|
|F01|mean(abs(rho)>0) global|SUPPORT / exact algebra|
|F02|mean(abs(rho_proj)>0)|SUPPORT / exact algebra|
|F03|mean(P>1e−6 max(P)); zero max→0|SUPPORT / exact algebra|
|F04|RMS(epsilon_proj)|BALANCE / exact algebra|
|F05|Q.50(abs(epsilon_proj))|BALANCE / exact algebra|
|F06|RMS(rho_proj)|BALANCE / exact algebra|
|F07|RMS(P_global)|BALANCE / exact algebra|
|F08|RMS(epsilon/(abs(rho)+phi^-1)) projected|BALANCE / exact algebra|
|F09|RMS(lap19(EY)_proj)|REACTION_OPERATOR / exact operator|
|F10|RMS(lap19(EI)_proj)|REACTION_OPERATOR / exact operator|
|F11|RMS(20*epsilon_proj)|REACTION_OPERATOR / exact operator|
|F12|(F09+F10)/F11 if F11>1e−12 else 0|REACTION_OPERATOR / exact operator|
|F13|int(F11≤1e−12)|REACTION_OPERATOR / exact operator|
|F14|mean((sign((-20eps)lapEY)+sign((20eps)lapEI))>0)|REACTION_OPERATOR / exact operator|
|F15|sqrt(mean_targets(sum_axes(centered_gradient(epsilon)^2)))|GRADIENT / stencil proxy|
|F16|sqrt(mean_targets(sum_axes(centered_gradient(rho)^2)))|GRADIENT / stencil proxy|
|F17|RMS(lap19(epsilon)_proj)|GRADIENT / exact stencil|
|F18|RMS(J_proxy)|TRANSPORT / current proxy|
|F19|RMS(div_periodic(J_proxy))|TRANSPORT / current proxy|
|F20|F18/(F09+F10) if denominator>1e−12 else 0|TRANSPORT / current proxy|
|F21|max(axis RMS centered gradients epsilon)/(mean+1e−12), all-zero→0|TRANSPORT / morphology proxy|
|F22|max(axis RMS directional `a_i*(f+ + f−−2f0)` epsilon)/(mean+1e−12), all-zero→0|TRANSPORT / morphology proxy|
|F23|sum(P_proj)/sum(P_global), zero denominator→0|CONCENTRATION / exact algebra|
|F24|sum(abs(epsilon_proj))/sum(abs(epsilon_global)), zero→0|CONCENTRATION / exact algebra|
|F25|RMS(P_proj)/RMS(P_global), zero→0|CONCENTRATION / exact algebra|
|F26|rung/7|HISTORY / protocol covariate|
|F27|tau/29|HISTORY / protocol covariate|
|F28|F04−previous F04; first=0|HISTORY / history proxy|
|F29|F07−previous F07; first=0|HISTORY / history proxy|
|F30|int(rung>0)|HISTORY / history flag|

Physical h is used for every centered gradient; lap19 is periodic shader coefficient/order. J_proxy is eligible only in TRANSPORT/ALL and remains a proxy. H* is absent.

## 5. Exact block vectors and models

`REACTION=[F01–F14,F23–F25]`; `TRANSPORT=[F09–F13,F15–F22]`; `HISTORY=[F26–F30]`; `ALL_NO_TRANSPORT=[F01–F17,F23–F30]` excluding F18–F22; `ALL=[F01–F30]`. One final-epoch multinomial logistic per block: training-only standardization (std<1e−12→1), zero weights/intercept, unstandardized/unpenalized intercept, full-batch Adam beta1=.9 beta2=.999 eps=1e−8, lr=.03, 200 updates, CE+.5λ sum(nonintercept²), λ=.001, final update only. Majority is training class-count tie→lowest class. Stumps are descriptive only: threshold candidates are adjacent training midpoints plus ±inf; each orientation independently selects left/right classes by training response regret, misclassification, threshold, left class, right class; constant columns use majority.

## 6. Permutation and metrics

One frozen training-label permutation `default_rng(20260913).permutation`, reused across blocks; validation labels/responses unchanged. Report train/validation class counts, accuracy, total and per-class regret (null class→null), confusion, finite status, loss, coefficients, standardizers, degeneracy flags, stumps, and permutation train/validation metrics. A block passes only if it strictly beats majority on validation accuracy and regret and real labels strictly beat its permutation on both.

## 7. Decision tree

Protocol/partition/readout/nonfinite failure→INVALID. Fewer than two training classes→NO CONTEXTUAL TARGET. No named logistic block beating majority and permutation→REGIME DISCRIMINATOR NULL. Named nontransport block passing→REGIME CONTEXT SUPPORTED, TRANSPORT PROXY NOT SUPPORTED unless transport criterion passes. REACTION–TRANSPORT support additionally requires TRANSPORT or ALL to beat ALL_NO_TRANSPORT on both validation metrics, while also passing majority/permutation. ALL-only without paired ablation→GENERIC LOW-CAPACITY CONTEXT ONLY. Any eligible live refinement requires a separate new prereg; no live policy is run here.

## 8. Stopping rule

No post-hoc feature, threshold, seed, branch, or retry after a scientific failure. Harness-only failures are disclosed by amendment; source hashes are load-bearing. Collection/fit are exact commands and final-epoch only.

## 9. Deterministic manifest and hash

Manifest is canonical UTF-8 JSON (`sort_keys=true`, separators `(',',':')`, `allow_nan=false`, no trailing newline), written before samples and rewritten after collection with source hashes. Partition hash is SHA-256 of canonical `{train,validation,live}` seed object. Feature hash is SHA-256 canonical ordered F01–F30 records. Source paths are repo-relative and before/after SHA-256 bytes must match current source. NPZ schema keys exactly `seed,rung,x,label,responses,aux_cells`; shapes `(80,)`, `(80,)`, `(80,30)`, `(80,)`, `(80,3)`, `(80,8,11)`; row order `repeat(seed list,8)` and `tile(rung,10)`; labels equal first exact argmax.

## 10. Outputs

Tool: `tools/balance_policy_regime.py`. Official outputs: `_diag/balance_policy_regime/manifest.json`, `samples.npz`, `result.json`. Attempt receipts preserved as `attempt1_manifest.json`, `attempt1_samples.npz`, `attempt2_manifest.json`, `attempt2_samples.npz`.

## 11. Prior-wave anchors

Prior training winners `{.5:16,1:0,1.5:48}`; validation `{.5:2,1:0,1.5:14}`. Prior six-feature softmax validation accuracy `.8125` versus majority `.875`, regret `5.8928565e−9` versus `3.6619398e−9`, verdict CONTEXT POLICY NOT LEARNABLE.

## Pre-run clarification amendment — 2026-08-17

F15/F16 use full arrays and physical h; F17 direct lap19; F21/F22 exact axis definitions with all-zero guard; auxiliary `(80,8,11)`; exact step counters and fresh branches; float32 decode/float64 math; exact Adam/loss; deterministic stumps; canonical manifest/source/partition hashes; exact first argmax; pinned auto_step=false contract.

## Pre-run harness amendment 2 — 2026-08-17

The first collect failed before bridge connection/manifest/data with `ValueError: pinned scene properties mismatch` because the scene uses Script ext_resource path/id and `script=ExtResource("1_eng")`. Only parser correctness changed; no scientific protocol, metrics, seeds, or gates changed.

## Pre-run harness amendment 3 — 2026-08-17

The corrected collect failed before data with `ValueError: invalid projection index`; actual project cells are `i,gx,gy,gz,x,y,z,q`, no EY/EI. Diagnostic proof: all eight indices matched CPU formula and max |dq| was `2.282e−8`. Only project schema validation changed; no scientific changes.

## Pre-run harness amendment 4 — 2026-08-17

Shader invocation flattening `i+N*(j+N*k)` differs from CPU projection `gx*N*N+gy*N+gz`; all prior diagnostic indices matched CPU. Only projection/readout validation and tests changed. On the pinned cube scalar lap19 and max/mean anisotropy are permutation-invariant; feature formulas did not change.

## Pre-run harness amendment 5 — 2026-08-17

First valid collection fit failed before model/report with `IndexError: too many indices for array, 2-D indexed with 3`; degeneracy used `x[tr,0,c]`. No metrics were inspected. Attempt-one receipts: manifest SHA-256 `344ac4a9...bb844`, NPZ ZIP SHA-256 `de2f1f70...8235a`, canonical array digest `cb7bbcea...3ecc1`. Attempt-one and attempt-two arrays were later independently confirmed identical. Only degeneracy reporting changed.

## Pre-run harness amendment 6 — 2026-08-17

Recollected valid fit reached decision and failed with `TypeError: '>' not supported between instances of 'str' and 'int'`: production classes were `{train,validation}` while the fixture was a list. No official result or metrics were interpreted. Only decision reading `classes['train']` and production-shaped fixture changed.

## Measured ledger — final frozen run, 2026-08-17

Official commands, in order: `python tools/balance_policy_regime.py --self-test` (PASS); pinned windowed Mono sidecar on `res://scenes/mind_engine_cache.tscn`; `python tools/balance_policy_regime.py --collect` (PASS, 80 rows, 30 features, aux `[80,8,11]`, 124.27 s); clean sidecar stop; `python tools/balance_policy_regime.py --fit` (PASS, result written). No source edits occurred between successful collection and fit. Final NPZ arrays matched both attempt1 and attempt2 key-by-key and byte-content digest: `cb7bbceac758a24f98486e5e7a933051420d3cf26c1acf9154a13fb5b7a3ecc1`.

Final classes: train `[16,0,48]`; validation `[2,0,14]`. Majority validation accuracy/regret `0.875`, `3.661939830774534e−9`. Logistic validation accuracy/regret and frozen-permutation validation accuracy/regret:

- REACTION: `0.9375`, `2.2099690088942807e−9`; permutation `0.1875`, `1.800619553843945e−7`.
- TRANSPORT: `0.9375`, `2.230916561419871e−9`; permutation `0.3125`, `1.5312393868189633e−7`.
- HISTORY: `0.875`, `8.428774430450897e−9`; permutation `0.875`, `3.661939830774534e−9`.
- ALL_NO_TRANSPORT: `0.9375`, `2.2099690088942807e−9`; permutation `0.4375`, `9.564026701691826e−8`.
- ALL: `0.9375`, `2.230916561419871e−9`; permutation `0.375`, `1.1703790395788951e−7`.

ALL minus ALL_NO_TRANSPORT: accuracy `0.0`; regret `+2.0947552525590508e−11` (ALL is worse). Thus TRANSPORT/ALL do not beat ALL_NO_TRANSPORT on both metrics. REACTION, TRANSPORT, ALL_NO_TRANSPORT, and ALL beat majority and their permutations; HISTORY does not.

Descriptive stumps only: REACTION F07 threshold `0.0005946905376144026`, left 0/right 2; TRANSPORT F10 threshold `0.3698987672620182`, left 0/right 2; HISTORY F28 threshold `−0.11860475524356309`, left 0/right 2; ALL_NO_TRANSPORT and ALL F28 threshold `−0.11860475524356309`, left 0/right 2. Stumps did not open any branch.

Largest absolute logistic coefficients (feature ID, class, coefficient): REACTION F03 class 0 `−1.5748819557853715`, F03 class 2 `1.5233040420639061`, F12 class 2 `−1.4448021972361287`; TRANSPORT F10 class 0 `−2.0515632563457906`, F10 class 2 `1.8279257788349834`, F11 class 0 `1.7313114639595812`; ALL_NO_TRANSPORT F23 class 0 `−2.267511251913754`, F23 class 2 `2.034930382700397`; ALL F28 class 0 `−2.0330268616687657`, F28 class 2 `1.9790402685356097`. The complete coefficient matrices are authoritative in `_diag/balance_policy_regime/result.json`.

Frozen tree branch 5: **REGIME CONTEXT SUPPORTED, TRANSPORT PROXY NOT SUPPORTED**, passing blocks REACTION/TRANSPORT/ALL_NO_TRANSPORT/ALL. This is not reaction–transport support because neither TRANSPORT nor ALL beats ALL_NO_TRANSPORT. No live policy was run. An eligible policy refinement, if desired, requires a separate new preregistration before any live collection; untouched live seeds remain untouched.

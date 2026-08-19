# Learned Balance Policy — Pre-registration

## Status: Plan—pre-registered 2026-08-17, before collection or training

This wave tests whether a tiny interpretable policy can learn a transferable balance-preserving correction that improves on unchanged dynamics and whether it adds value beyond the frozen analytic balance arm. The Qi spiral remains a held-out diagnostic and is absent from features, targets, losses, checkpoint selection, and stopping rules.

## 1. Frozen field and action contract

- Scene: `scenes/mind_engine_cache.tscn`, $N=32$, `auto_step=false`.
- Cadence: `[1,2,3,4,7,11,18,29]`.
- Projected targets: `project k=8`; engine flat index $i=g_xN^2+g_yN+g_z$ is authoritative.
- Deposits use the coordinates returned by `project`; this preserves the existing live steering convention. The known projection/scatter coordinate-roundtrip mismatch is shared by every active arm.
- Per-interval absolute-charge budget: $B\le0.25$; signed cancellation never increases the budget.
- Fixed deposit sigma: 1.0.

At each target cell:

$$\rho=E_Y+E_I,\qquad \varepsilon=E_Y-\varphi E_I,$$
$$z=\frac{\varepsilon}{|\rho|+\varphi^{-1}},\qquad d=\log\left(1+\frac{|\rho|}{\operatorname{median}_{\rm active}|\rho|+10^{-8}}\right).$$

The previous-rung feature is $\Delta z=z-z_{\rm previous}$, initialized to zero.

## 2. Frozen policy families

### D—unchanged

No deposits after the IC.

### A—analytic balance baseline

The previously supported correction:

$$a_A=0.25\frac{|\varepsilon|}{1+|\varepsilon|}/8.$$

For $\varepsilon>0$, deposit Yin; for $\varepsilon<0$, deposit Yang. Apply the shared budget projection.

### G—learned scalar-gain baseline

$$a_G=g\,a_A,\qquad g=\sigma(\gamma).$$

One learned parameter isolates magnitude learning from directional learning.

### P—primary affine contextual policy

The policy preserves the analytic direction and learns a bounded magnitude residual:

$$a_P=a_A\,[0.5+\sigma(b+w_z|z|+w_d d+w_\Delta|\Delta z|)].$$

Parameters are $(b,w_z,w_d,w_\Delta)$, initialized to zero. This bounds the multiplier to $(0.5,1.5)$ before the exact shared budget projection. It cannot reverse the balance-correcting direction.

### R—matched random control

Use a deterministic seed-derived multiplier uniformly distributed on $(0.5,1.5)$ per target/rung, with the same analytic sign, targets, sigma, cadence, and budget. R is never used for fitting.

## 3. Collection and partitions

- Training seeds: `20260901` through `20260908` inclusive.
- Validation seeds: `20260911`, `20260912`.
- Live test seeds: the untouched confirmation seeds `20260817`, `20260819`, `20260821`.
- Seeds are indivisible; no row-level random split.
- Collection produces one decision row per target/rung with current features and an immediate analytic teacher magnitude. It also records the next-rung balance response after the analytic action for diagnostics.
- The analytic target is current-state-derived and contains no future, $H_*$, or $J_{\rm proxy}$ information.

## 4. Offline objective and optimizer

The initial learnability question is deliberately narrow: can the tiny policy reproduce the supported analytic action on held-out seeds?

Normalize target magnitude by the per-cell analytic value and minimize mean squared deposit error on `cy` and `ci`, after direction selection but before shared-budget projection. Zero-target rows are included.

- Optimizer: full-batch Adam, learning rate 0.03.
- Epochs: 200.
- Checkpoint: final epoch only.
- No early stopping or best-epoch scan.
- Random seed: `20260900`.

Learnability gate:

- validation normalized action MSE must be below the constant-zero multiplier baseline;
- P must be no worse than G on validation normalized action MSE;
- all parameters and outputs finite.

Passing this gate establishes imitation learnability only. It does not establish live superiority.

## 5. Live test protocol

For each frozen live seed, run fresh D/A/G/P/R arms from identical ICs through all eight intervals. Learned parameters are frozen before live testing.

Primary endpoint statistic:

$$I_X^{(s)}=\varepsilon_{{\rm RMS},D}^{\rm end}-\varepsilon_{{\rm RMS},X}^{\rm end}.$$

Integrated balance is the sum of $\varepsilon_{\rm RMS}$ over the nine readouts and is reported per arm/seed.

Safety gates:

- protocol, shape, finite, and payload identities pass;
- canonical coherence remains within $[0,1]$ up to floating-point tolerance;
- maximum field power remains below 100× that seed's baseline maximum;
- cumulative and per-rung absolute-charge budgets are reported.

Held-out diagnostics, never used for learning or selection:

- endpoint and integrated nonzero-mode $H_*$;
- live separation from pair-preserving spatial shuffle and Fourier phase scramble;
- endpoint and integrated $J_{\rm proxy,RMS}$.

## 6. Decision tree

Applied in order:

1. Pre-registration or partition violation → **INVALID**.
2. Offline protocol/finite failure → **INVALID**.
3. P fails the validation learnability gate → **NOT LEARNABLE—CLOSE POLICY LINE**; do not run live P as an adopted candidate.
4. Any live arm crosses a safety gate → **UNSAFE/DIVERGENCE** for that arm.
5. An arm has $I_X>0$ in at least 2/3 seeds → balance directionally replicates.
6. P beats D but not A on endpoint improvement in at least 2/3 seeds → **REDISCOVERS ANALYTIC BALANCE**.
7. P beats both D and A in at least 2/3 seeds, without worse integrated balance in those seeds → **LEARNED POLICY ADOPT**.
8. P fails to beat D in at least 2/3 seeds → **LEARNED POLICY REJECT**.
9. H* or $J_{\rm proxy}$ changes are reported as held-out generalization only and cannot alter branches 3–8.

If G equals or beats P, the contextual coefficients add no demonstrated value. If P converges to a constant multiplier, classify the result as scalar-gain rediscovery.

## 7. Stopping rule

Collection, training, and every valid live arm complete their frozen budgets. Stop only for protocol failure, non-finite values, engine loss, or safety-ceiling violation. No trend or intermediate epoch permits early termination or a new checkpoint.

## 8. Artifacts

- Collector/trainer/live runner: `tools/balance_policy_learning.py`
- Dataset: `_diag/balance_policy/samples.npz`
- Parameters/result: `_diag/balance_policy/result.json`

## 9. Ledger

### Pre-run implementation audit—INVALID-DESIGN

No collection, training, or live policy run was executed under this protocol.
Implementation review found that normalizing the analytic teacher magnitude by
itself reduces every active supervision label to the constant 1.0. The draft
collector also did not populate its declared next-rung response field, and its
integrated spiral diagnostic selected mode zero instead of the preregistered
winning nonzero-mode order. The frozen question therefore could not
demonstrate contextual learning.

Verdict: **INVALID-DESIGN**. The draft tool remains as a reproducible record
and offline self-test target; it is not an adopted trainer or runtime path.
The one-knob response-label refinement is registered in
`research/steering/balance_policy_response_prereg.md`.

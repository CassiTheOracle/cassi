# Contextual Balance Policy — Response-Learning Refinement

## Status: Plan—pre-registered 2026-08-17, before response collection

The imitation draft in `balance_policy_learning_prereg.md` is closed as **INVALID-DESIGN** before any live policy run: dividing the analytic teacher magnitude by itself makes every active label one, `next_eps` was not populated, and the integrated spiral field used mode zero. This refinement changes one load-bearing element: the learned target is measured next-rung balance response under frozen candidate magnitudes. All other engine, cadence, partition, budget, safety, and held-out-diagnostic rules remain.

## 1. Frozen candidate response collection

For each training/validation seed and each cadence rung, branch fresh identical engine states from the same seed/IC and replay prefix. At the current projected eight cells, evaluate three scalar multipliers of the analytic direction:

$$m\in\{0.5,1.0,1.5\}.$$

Each candidate uses the same targets, sign, sigma 1.0, cadence interval, and absolute-charge budget 0.25. Measure the global next-rung response

$$y(m)=\varepsilon_{\rm RMS}^2(t)-\varepsilon_{\rm RMS}^2(t+\tau).$$

The label is the candidate multiplier with maximal $y(m)$; ties choose the smaller multiplier. This is a measured response label, not analytic imitation. No $H_*$, $J_{\rm proxy}$, field-power efficacy, future test seed, or live-test result enters the label.

To keep every branch independent, collection reconstructs and replays the full prefix from the frozen IC for each `(seed,rung,multiplier)` branch. The prefix policy is analytic $m=1$ at earlier rungs.

## 2. Frozen features and model

One row describes a decision rung using the projected-cell aggregate:

- mean and RMS $|z|$, where $z=\varepsilon/(|\rho|+\varphi^{-1})$;
- mean density feature $d=\log(1+|\rho|/(\operatorname{median}_{active}|\rho|+10^{-8}))$;
- mean and RMS $|\Delta z|$ from the replayed prior rung;
- cadence index normalized by 7.

The primary policy is multinomial linear softmax over the three multipliers: six features including a constant, three classes, 18 parameters. This is the smallest contextual classifier that can select among the measured bounded actions.

- Full-batch softmax cross-entropy.
- Adam, learning rate 0.03.
- 200 epochs.
- Final epoch only.
- Parameter seed 20260900.
- Standardize nonconstant features using training seeds only.

Baselines:

- **A:** constant multiplier 1.0.
- **M:** training-set majority candidate, frozen before validation.
- **R:** deterministic random candidate with matched action set.
- **D:** unchanged live field.

## 3. Partitions

- Training: `20260901`–`20260908`.
- Validation: `20260911`, `20260912`.
- Untouched live test: `20260817`, `20260819`, `20260821`.
- Whole-seed partitions only.

## 4. Learnability gate

The response dataset must contain at least two winning candidate classes across training seeds. Otherwise: **NO CONTEXTUAL TARGET—CLOSE LINE**.

At the final epoch:

- all parameters and losses finite;
- validation classification accuracy of P must exceed the frozen majority baseline M;
- validation response regret

$$R=y(m_*)-y(m_P)$$

must have lower mean for P than for M.

Failure: **CONTEXT POLICY NOT LEARNABLE**. Passing opens live testing but does not adopt the policy.

## 5. Live efficacy

Run fresh D/A/M/P/R arms on the untouched seeds with the existing eight cadence intervals. P chooses one of `{0.5,1.0,1.5}` at each rung. Every active arm shares the same analytic direction, targets, sigma, and exact budget projection.

Primary endpoint improvement:

$$I_X^{(s)}=\varepsilon_{{\rm RMS},D}^{end}-\varepsilon_{{\rm RMS},X}^{end}.$$

P adopts only if:

1. $I_P>0$ in at least 2/3 seeds;
2. endpoint $\varepsilon_{\rm RMS,P}<\varepsilon_{\rm RMS,A}$ in at least 2/3 seeds;
3. integrated balance of P is no worse than A in those same winning seeds;
4. all safety gates pass.

If P beats D but not A: **CONTEXT POLICY REDISCOVERS BALANCE**. If it fails to beat D in 2/3: **CONTEXT POLICY REJECT**.

## 6. Held-out diagnostics

Report endpoint/integrated winning nonzero-mode $H_*$ and $J_{\rm proxy,RMS}$ plus matched controls. They remain absent from features, labels, losses, model selection, and the adoption branch.

## 7. Safety and stopping

Existing gates apply: protocol/shape/identity/finite; coherence in `[0,1]`; field power below 100× baseline; per-rung budget at most 0.25. Collection, training, and live arms complete frozen budgets unless a gate fails. No early stopping or post-run refinement.

## 8. Artifacts

- Tool: `tools/balance_policy_response.py`
- Dataset/result: `_diag/balance_policy_response/`

## 9. Ledger

### Run 2026-08-17—response collection and final-epoch learnability gate

- Response rows: 80 (64 training, 16 validation), each from a fresh replayed
  `(seed,rung,multiplier)` branch.
- Training winning classes for multipliers `{0.5,1.0,1.5}`: `{16,0,48}`.
  The dataset contains two contextual targets, so the target-diversity gate
  passed. Multiplier 1.0 was never optimal.
- Validation winning classes: `{2,0,14}`.
- Final-epoch P validation accuracy: 0.8125.
- Frozen majority baseline accuracy: 0.875.
- P mean validation response regret:
  $5.893\times10^{-9}$.
- Majority mean validation response regret:
  $3.662\times10^{-9}$.
- All parameters and losses were finite; final cross-entropy was 0.330807.

The primary policy failed both frozen learnability comparisons: it had lower
accuracy and higher response regret than the constant 1.5× majority policy.
Decision-tree verdict: **CONTEXT POLICY NOT LEARNABLE** (branch 4).

Per the frozen tree, no live P efficacy run was performed and no learned
policy was integrated. The measured response itself is still informative:
1.5× was the best candidate in 48/64 training and 14/16 validation decisions,
while 0.5× won the remaining decisions. This establishes a mostly monotone
gain preference with a minority low-gain regime, but the frozen six-feature
linear policy did not generalize that regime.

Artifacts:
`_diag/balance_policy_response/samples.npz` and
`_diag/balance_policy_response/result.json`.

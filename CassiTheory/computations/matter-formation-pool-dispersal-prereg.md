# Controlled Dispersal of a Self-Bound Field Pool

## Status: Hypothesized—September 2026

## Abstract

This protocol tests whether one prepared charged scalar pool can reorganize into two spatially separated, compact, lower-charge bound pools under a fixed axial phase impulse. The preparation, action, profile stage, finite-volume schedule, comparison statistic, decision tree, stopping rule, source identities, and artifact contract are fixed before the dispersal trajectory is executed. A positive result is conditional on the supplied scalar action and prepared charge; every receipt retains `complete_physical_matter_formation=false`.

## 1. Physical question and scope

The calculation asks whether a single stationary pool with signed charge $Q=512$ can produce two persistent finite-time compact comparisons with approximately $Q=256$ on the two sides of an axial disturbance. The daughter profiles are energy references. They are not inserted into the initial state.

The calculation supplies an axis-selecting phase preparation, so it tests a declared two-lobe channel rather than unrestricted fragmentation. It does not select a microscopic field, quantum state, particle statistics, particle charge, particle mass, multiplicity, nonaxisymmetric stability class, or infinite-time asymptotic state. A qualifying pool split is therefore a conditional collective-field result.

The fixed scientific verdicts are:

- `EMERGES—conditional smaller pools from one dispersed pool` when the complete numerical contract passes and at least one nonzero impulse satisfies the two-pool predicate on every applicable grid and in both numerical methods;
- `DOES NOT EMERGE in the specified pool-dispersal calculation` when the complete numerical contract passes and neither nonzero impulse satisfies that predicate;
- `INCONCLUSIVE` for every failed prerequisite, source mismatch, profile failure, finite-value failure, raw-state mismatch, control failure, resolution failure, or method-comparison failure.

The stopping rule is the end of the declared schedule at $t=32$. No arm, threshold, grid, phase impulse, domain, or comparison tolerance may be changed after the first scientific trajectory is opened.

## 2. Fixed scalar action and preparation

Use the scalar restriction with

$$
a=\frac1{16},\qquad c_\Psi=\frac18,\qquad u_\rho=4,
\qquad u_C=k_{Cx}=1,\qquad e_C=\frac34,$$

and the supplied mapped coupling

$$h_C=2.9598260763447164.$$

The derived fixed coefficients used by the implementations are

$$B=e_C+\frac1{4a}=4.75,\qquad c_*^2=\frac1{c_\Psi}=\frac{k_{Cx}}{2a}=8.$$

The real mediator is $f$ and the complex carrier is $z$. At fixed positive charge $Q$, the stationary radial reference uses

$$
E_Q[f,c]=\int\left[
\frac{|\nabla f|^2}{2}+\frac{k_{Cx}|\nabla c|^2}{2}
+\frac{u_\rho}{4}(f^2-1)^2
+(B-h_C+h_Cf^2)c^2+\frac{u_C}{2}c^4
\right]d^3x+\frac{Q^2}{4aN},
$$

where $N=\int c^2d^3x$. The stationary equations are

$$
-\Delta f+u_\rho(f^2-1)f+2h_Cfc^2=0,
$$

$$
-\frac{k_{Cx}}2\Delta c+(B-h_C+h_Cf^2+u_Cc^2-a\Omega^2)c=0.
$$

The finite-volume profile stage uses exact spherical cell volumes, $f(R)=1$, $c(R)=0$, the positive branch $0\le f\le1$, $c\ge0$, and the fixed-charge temporal terms

$$\frac{N}{4a}+\frac{Q^2}{4aN}.$$

The selected parent is the qualified $Q=512$, grid `S1`, seed `s0` endpoint named `q512_S1_s0`. The daughter reference is the corresponding selected `q256_S1_s0` endpoint. The profile stage computes all twelve charge/grid/seed endpoints before selecting either reference.

## 3. Profile prerequisite and identity contract

The profile schedule is

| Charge | Grids | Seeds |
|---|---|---|
| $Q=256$ and $Q=512$ | `S0`: $(R,\Delta r)=(24,1/8)$; `S1`: $(24,1/16)$; `S2`: $(48,1/16)$ | $s=0.8,1.2$ |

The optimizer settings are L-BFGS-B with mass-weighted coordinates $\sqrt V(f-1)$ and $\sqrt Vc$, maximum 50,000 iterations, maximum 200,000 evaluations, `ftol=1e-15`, `gtol=1e-9`, and `maxcor=50`. Qualification is determined by the physical predicates:

1. normalized stationary residuals below $10^{-5}$ for both fields;
2. charge reconstruction relative error below $10^{-10}$;
3. outer-half population below $10^{-6}$;
4. seed agreement within $10^{-5}$ in energy, frequency, and charge-weighted RMS radius;
5. spatial refinement agreement within $2\times10^{-3}$;
6. domain agreement within $10^{-5}$;
7. $E_Q<0.999\,\Omega_\infty Q$ and $\Omega<0.999\,\Omega_\infty$;
8. finite raw arrays and independently reconstructed profile observables.

The selected references are accepted only when all twelve rows qualify and the profile receipt records

```text
selected = {"Q256": "q256_S1_s0", "Q512": "q512_S1_s0"}
```

The profile identity is part of the scientific input. A valid profile receipt must bind the manifest SHA, all twelve raw archive hashes, the selected archive names, the selected archive hashes, and the profile receipt hash. The dispersal runner accepts only that exact receipt and selected parent archive; a missing, duplicate, stale, or changed profile identity returns `INCONCLUSIVE` before evolution.

The source inventory is fixed to these raw SHA-256 identities:

| Repository path | SHA-256 |
|---|---|
| `computations/matter_formation_pool_profiles.py` | `2a489a534480a325c83087ae570ed6bba3e1b43588b35565a731b73868d1b6d5` |
| `computations/matter_formation_pool_dispersal.py` | `5147fcda1c3482c7a7c883bebcc4d16b57af0b93e75464e3cfe068f9a70a5055` |
| `computations/verify_matter_formation_pool_dispersal.py` | `5f3c27a1c62c1d472c57b988f7eba03ab9ee77a6befed8dd63111214be3657ed` |
| `computations/matter_formation_radial.py` | `69686235a26ab2d78b0a261fdbb21711c2b2a4946701099cba2b5aaf5b26f37e` |
| `computations/matter_formation_radial_cloud.py` | `7ed6029e878c6642ab22a6c2526b4a02b2107b1538b751a6c1ea66762f5f6cb4` |
| `computations/matter_formation_neutral_packets.py` | `743e2e75e6b8bc5c5ffd6a75393a49b9da6e5481b9b0b4dee08b040b3f1b901f` |

The frozen report sections are the exact spans beginning at the following headings and ending immediately before the next H2. Their canonical SHA-256 identities are:

| Section | SHA-256 |
|---|---|
| `## 74. Working notes: dispersal of a self-bound field pool` | `9d0147ef88901c2fafa05c73d0df21f7eb63730a891a155701e760e04efd46f7` |
| `## 75. Working notes: controlled pool-dispersal experiment` | `42467128ae45f6ac7669db8b786d4746b63dd60b4bd3cfbf53c077d776e07474` |

An execution manifest must copy both section spans into the run directory, record these section hashes, repeat the six source hashes, record the selected profile receipt and archive hashes, and reject every mismatch before scientific arrays are opened.

## 4. Evolution, diagnostics, and statistic

Interpolate the selected $Q=512$ parent onto the cylindrical domain with shape-preserving cubic interpolation, even radial reflection, and vacuum exterior. Normalize the carrier exactly once at preparation so that

$$2a\Omega\sum_iV_i c_i^2=512.$$

Keep the mediator and frequency fixed during preparation. For axial coordinate $\zeta$, use

$$
\vartheta_p(\zeta)=p\left(\sqrt{\zeta^2+4}-2\right),
$$

$$z(0)=c e^{i\vartheta_p},\qquad \dot z(0)=-i\Omega z(0),\qquad \dot f(0)=0,$$

with exactly

$$p\in\left\{0,\frac12,\frac32\right\}.$$

The four arms are:

| Arm | Phase impulse | Coupling | Role |
|---|---:|---:|---|
| `hold` | $p=0$ | $h_C$ | parent survival control |
| `weak` | $p=1/2$ | $h_C$ | nonzero candidate |
| `strong` | $p=3/2$ | $h_C$ | nonzero candidate |
| `uncoupled` | $p=3/2$ | $0$ | binding control |

The finite-volume domain is cylindrical with regular axis, vacuum Dirichlet outer values, and volume element $2\pi r\,dr\,d\zeta$. Evolve the complete scalar equations without damping, traps, absorbers, clamping, daughter insertion, or runtime normalization. The primary method is fourth-order Yoshida-composed velocity Verlet. The independent method is separately assembled classical RK4 in float64.

The schedule is:

| Grid | $R$ | $\Delta r=\Delta\zeta$ | $\Delta t$ | Arms |
|---|---:|---:|---:|---|
| `G0` | 112 | $1/4$ | $1/256$ | `hold`, `weak`, `strong`, `uncoupled` |
| `G1` | 112 | $1/8$ | $1/256$ | `hold`, `weak`, `strong`, `uncoupled` |
| `G2` | 160 | $1/4$ | $1/256$ | `strong` |
| `T1` | 112 | $1/8$ | $1/512$ | `strong` |

Every arm ends at $t=32$. Diagnostics are sampled every $1/8$ time unit, giving 257 samples. Full fields, velocities, geometry and volume are retained at $t=0,24,32$. The late decision window is the 65 samples with $24\le t\le32$.

For each half-space, define the positive charge from

$$\rho_a=-2a\operatorname{Im}(z^*\dot z).$$

Use its centroid and the fixed compact cutoff: weight one inside distance eight, zero outside distance twelve, and $1-3s^2+2s^3$ in the transition, where $s=(d-8)/4$. Include cutoff-gradient energy. The recorded half-space observables are positive charge, centroid, core charge fraction, core RMS radius, core $f^2$, cut charge, cut energy, cut momentum, energy–momentum radicand, binding ratio, and boundary clearance.

A candidate arm is a two-pool success at a sampled time exactly when, for both half-spaces,

$$
Q_\theta\ge128,\quad
F_{\rm core}\ge0.6,\quad
R_{\rm core}<6,\quad
\langle f^2\rangle_{\rm core}\le0.5,
$$

$$
0<M_\theta<0.98\,\Omega_\infty Q_\theta,
\qquad |\zeta_{\rm centroid}|>12,
\qquad \text{clearance}>16.
$$

The arm-level formation statistic is

$$
F_{a,g,m}=\prod_{t\in[24,32]}
\mathbf 1\{\text{all two-pool inequalities hold for arm }a,\text{ grid }g,\text{ method }m\}.
$$

The campaign statistic is

$$
N_{\rm split}=\sum_{a\in\{\mathrm{weak},\mathrm{strong}\}}
\mathbf 1\left\{F_{a,g,m}=1\text{ for every applicable }(g,m)\right\}.
$$

The complete numerical contract is a conjunction, not an average. It requires every declared arm and method to have finite arrays, relative energy drift below $2\times10^{-4}$, signed-charge drift relative to 512 below $2\times10^{-5}$, reflection error below $10^{-10}$, hold-arm RMS-radius drift below $2\%$, uncoupled positive-charge compact comparisons at least $(1-10^{-8})\Omega_\infty Q_\theta$, raw saved-state reconstruction below $10^{-9}$ in the fixed diagnostic units, same-row independent state discrepancy below $10^{-2}$, and every late-mean inter-method, space, domain, and time comparison below $0.05$ in its declared fixed unit.

### 4.1 Domain-invariant clearance comparison

The recorded absolute boundary clearance is

$$C=\\min(R-12,R-|\\zeta_{\\rm centroid}|-12).$$

It remains a hard feasibility condition in the formation predicate: every candidate sample must satisfy $C>16$. The value of $C$ also contains the chosen outer-domain radius, so its absolute difference is not a local dynamical discrepancy when the domain-comparison arm changes $R$ from 112 to 160 at fixed spacing. The domain comparison therefore uses the fixed threshold-deficit metric

$$d_C=\\max(0,16-C),$$

with the declared length scale 12. Raw $C$ differences remain in the receipt under `raw_errors`; the comparison `errors` use $d_C$ only for clearance columns and use the raw differences for every other observable. A zero deficit in both domains records the same feasibility state without removing the absolute clearance gate from $F_{a,g,m}$.

This metric is part of the source-bound protocol. The primary and independent programs must report `comparison_metric=clearance_threshold_deficit_for_clearance_columns` for every late-mean comparison and must retain both raw and transformed errors.

### 4.2 Protocol source amendment

The source identity table and execution manifest bind this clearance contract together with the raw action, profile, grid, state, and decision rules. A fresh run is required after any source or protocol hash changes.


## 5. Decision tree and stopping rule

1. Validate the manifest schema, six source hashes, two report-section hashes, profile receipt, selected profile archive, required row set, and all finite profile arrays. A failure returns `INCONCLUSIVE` without opening trajectory arrays.
2. Run the twelve-profile independent reconstruction. Any failed profile residual, charge, seed, refinement, domain, binding, or raw-array predicate returns `INCONCLUSIVE`; no profile is substituted.
3. Run the ten primary trajectories and ten independent trajectories. Any failed conservation, reflection, hold, uncoupled, finite-state, snapshot, raw reconstruction, state comparison, or late-mean comparison predicate returns `INCONCLUSIVE`.
4. If the complete contract passes, evaluate $N_{\rm split}$. A value of one or two returns `EMERGES—conditional smaller pools from one dispersed pool`; a value of zero returns `DOES NOT EMERGE in the specified pool-dispersal calculation`.
5. The output always records `complete_physical_matter_formation=false`. The conditional pool statistic never upgrades to a microscopic matter-formation verdict.

The calculation stops after the declared $t=32$ schedule. No extension in time, alternate phase impulse, replacement grid, changed domain, altered cutoff, changed threshold, daughter insertion, or post-hoc comparison rule is permitted. The declared clearance-deficit transform is fixed before the fresh execution.


## 6. Required execution artifacts

The run uses fresh directories and refuses overwrite:

```text
runs/20260912_matter_formation_pool_dispersal_recovery1/manifest.json
runs/20260912_matter_formation_pool_dispersal_recovery1/profiles/
runs/20260912_matter_formation_pool_dispersal_recovery1/primary/
runs/20260912_matter_formation_pool_dispersal_recovery1/verification/


```

The profile prerequisite is run first:

```text
python computations/matter_formation_pool_profiles.py \
  --manifest runs/20260912_matter_formation_pool_dispersal_recovery1/manifest.json \
  --output runs/20260912_matter_formation_pool_dispersal_recovery1/profiles


```

The primary evolution then runs once:

```text
python computations/matter_formation_pool_dispersal.py \
  --manifest runs/20260912_matter_formation_pool_dispersal_recovery1/manifest.json \
  --profiles runs/20260912_matter_formation_pool_dispersal_recovery1/profiles \
  --output runs/20260912_matter_formation_pool_dispersal_recovery1/primary


```

The independent verifier runs against the fresh profile and primary directories:

```text
python computations/verify_matter_formation_pool_dispersal.py \
  --manifest runs/20260912_matter_formation_pool_dispersal_recovery1/manifest.json \
  --profiles runs/20260912_matter_formation_pool_dispersal_recovery1/profiles \
  --input runs/20260912_matter_formation_pool_dispersal_recovery1/primary \
  --output runs/20260912_matter_formation_pool_dispersal_recovery1/verification
```

The profile receipt, primary receipt, independent receipt, raw field archives, raw trace archives, source snapshots, section snapshots, environment record, and any prerequisite rejection records are retained. A standalone raw reconciliation reads the archived arrays and receipts without importing either numerical evolution program.

## 7. Physical interpretation boundary

A positive campaign result would show a finite-time two-lobe response of the supplied scalar pool under a supplied directional impulse. It would provide an energetic and dynamical conditional result for the declared collective channel. It would not derive the scalar action from the canonical Cassi density variables, create charge from a quantum vacuum, determine a particle representation, establish a continuum limit, or prove nonaxisymmetric and infinite-time persistence. The complete physical matter-formation flag remains false in every branch.

## References

- `computations/matter-formation-continuum-report.md` §§74–76—fixed action, stationary profile equations, dispersal preparation, diagnostics, schedule, decision tree, and physical boundary.
- `foundations/matter-completion-boundary.md` §§16–18—fixed-charge binding, localization, and stability requirements.
- `computations/matter_formation_pool_profiles.py`—source-bound stationary parent and daughter profile construction.
- `computations/matter_formation_pool_dispersal.py`—primary finite-volume pool-dispersal evolution.
- `computations/verify_matter_formation_pool_dispersal.py`—independent profile and trajectory reconstruction.

# Particle Carrier Resolution-Recovery Preregistration

## Status: Preregistered—September 2026

## Abstract

The direct fixed-charge coordinate produces a physically stationary, nodeless, localized carrier branch on three finite grids, and the larger-domain calculation agrees with the primary box. The finer-grid energy differs from the primary energy by $8.43\%$, above the frozen $5\%$ comparison tolerance. This campaign adds two independently initialized refinements on the same domain and asks whether adjacent energy differences contract while every refined endpoint remains stationary, nodeless, localized, and retained. The protocol, statistics, tolerances, source hashes, stopping rule, and verdict tree are frozen before execution.

## 1. Frozen question

At the selected density-depletion coefficient

$$
h_C=2.9598260763447164
$$

and fixed carrier charge $q_C=4$, does the direct-coordinate stationary branch enter a refined-grid regime in which all adjacent observables agree within the registered tolerances and the energy drift decreases at each refinement?

This calculation tests numerical spatial recovery only. It does not derive or calibrate $h_C$, establish a continuum existence theorem, test real-time persistence, identify the auxiliary carrier charge with an observed quantum number, or add a new action term.

## 2. Frozen source chain

The source result is `runs/20260902_particle_carrier_direct_coordinate_v2/results.json`, SHA-256 `59f39d6e565ab24faab705094ea5ee1001d7ab3939d8a923db091dc903e44c73`. Its independent verification is `runs/20260902_particle_carrier_direct_coordinate_v2/verification.json`, SHA-256 `b858d05df7db577896f6f5ff325efba2922d90cc9359c9a7264631ad1c314629`, with `pass: true` and zero mismatches.

Two same-domain source levels are frozen:

| Level | Domain radius | Points per axis | Spacing | Artifact | SHA-256 |
|---|---:|---:|---:|---|---|
| coarse primary | $4$ | $17$ | $0.5$ | `fields_primary_half_reference_block01.npz` | `c32beb4ee7bc7746a4fc18b63bc04ef7db12cc18505c9bee8ce2d298ddc25837` |
| first refinement | $4$ | $21$ | $0.4$ | `fields_comparison_H_block01.npz` | `8aa65f3c08167c902660f9e8d09c0ce921d43c7f0af152b31aae79db6875810f` |

The larger-domain source at radius $5$ and spacing $0.5$ already passes every registered comparison against the coarse primary. It is not rerun because this campaign isolates spatial resolution on the radius-$4$ domain.

## 3. Frozen action and carrier map

The full dimensionless stationary action and every coefficient remain those of the direct-coordinate source campaign:

$$
(\alpha_{\mathfrak s},u_\rho,u_\varphi,\gamma_x,
\gamma_{\mathfrak s},u_H,k_{Cx},k_{C\mathfrak s},e_C,u_C,q_C,
L_{\mathfrak s},\xi_{\rm gf})
=(1,4,4,1,1,4,1,1,0.75,1,4,1,1).
$$

Only $h_C=2.9598260763447164$ is inserted at evaluation time. The direct carrier coordinate is

$$
c(z)=\sqrt{q_C}\,
\frac{M\mathcal P_{C_4}z}
{\left[\int (M\mathcal P_{C_4}z)^2\,d^3x\right]^{1/2}}.
$$

No positivity map, clipping operation, smoothing term, altered derivative, changed boundary condition, or grid-dependent coefficient is permitted.

## 4. Frozen refinement grids and initialization

The two new levels use the original radius-$4$ domain:

| Label | Domain radius | Points per axis | Spacing |
|---|---:|---:|---:|
| `X1` | $4$ | $25$ | $1/3$ |
| `X2` | $4$ | $29$ | $2/7$ |

Each level begins independently from the deterministic analytic `separated_core` seed on its own grid. The seed is converted to the direct carrier coordinate by taking its physical carrier field as $z$; the direct round-trip must reproduce that field to maximum absolute error $5\times10^{-12}$ or the campaign is inconclusive.

Each level receives the same initial optimization schedule: $800$ Adam steps followed by an L-BFGS call limited to $120$ iterations. It then receives at most eight continuation blocks. Every continuation block uses PyTorch L-BFGS with

- `max_iter = 880`,
- `max_eval = 1100`,
- `history_size = 20`,
- `tolerance_grad = 1e-10`,
- `tolerance_change = 1e-12`,
- `line_search_fn = strong_wolfe`.

All arrays use float64 or complex128 as appropriate. The runtime device is the available ROCm device exposed through PyTorch as `cuda`. No random initialization enters either arm.

## 5. Frozen endpoint conditions

A refinement is numerically qualified only when all of these conditions hold on the stored physical fields:

1. fixed-charge relative error $\le10^{-10}$;
2. exact registered Dirichlet boundary values;
3. gauge-fixing fraction $\le5\times10^{-5}$ and gauge-divergence RMS $\le3\times10^{-3}$;
4. outer magnetic number $\le5\times10^{-2}$ and outer flux RMS $\le3\times10^{-3}$;
5. full fixed-charge physical-gradient RMS $\le1.20\times10^{-4}$.

A qualified refinement counts as the same localized retained branch only when it also satisfies

1. carrier RMS radius $\le2.0$;
2. outer carrier fraction $\le0.08$;
3. maximum density depletion $\ge0.05$;
4. carrier frequency $\widehat\omega_C<0.73$;
5. oriented negative carrier norm fraction $\le10^{-12}$.

The physical-gradient RMS is the full unconstrained first variation projected only onto the fixed-charge tangent space. The optimizer-coordinate gradient is recorded but cannot qualify an endpoint.

## 6. Frozen stopping rule

`X1` and `X2` always run in that order. Each arm stops at the first continuation block that is numerically qualified, or after block eight if none qualifies. A qualified but nonlocalized or sign-changing endpoint stops that arm and records the failed branch condition. The second arm still runs when the first arm fails, so a grid-specific failure cannot terminate the campaign early.

Every completed continuation block writes its physical fields before the next block starts. A missing required artifact, source mismatch, nonfinite value, optimizer exception, manifest mismatch, or independent-verification mismatch makes the scientific verdict inconclusive.

## 7. Frozen comparison statistics

For adjacent levels $A$ and $B$, define

$$
\delta_E(A,B)=\frac{|E_A-E_B|}{\max(|E_A|,|E_B|,10^{-30})},
$$

$$
\delta_r(A,B)=\frac{|r_{C,A}-r_{C,B}|}
{\max(|r_{C,A}|,|r_{C,B}|,10^{-30})},
$$

$$
\Delta_\ell(A,B)=|\ell_{\rm core,A}-\ell_{\rm core,B}|,
\qquad
\Delta_\omega(A,B)=|\widehat\omega_{C,A}-\widehat\omega_{C,B}|.
$$

An adjacent pair agrees when

$$
\delta_E\le0.05,
\qquad
\delta_r\le0.10,
\qquad
\Delta_\ell\le0.75,
\qquad
\Delta_\omega\le0.10.
$$

Let

$$
d_0=|E_{17}-E_{21}|,
\qquad
d_1=|E_{21}-E_{25}|,
\qquad
d_2=|E_{25}-E_{29}|.
$$

The energy drift contracts only when $d_1<d_0$ and $d_2<d_1$. Strict inequalities are frozen; equality does not pass.

## 8. Frozen decision tree

1. If the source chain, manifest, execution, required artifacts, or independent verification fails, report `INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION`.
2. If either new refinement lacks a numerically qualified, nodeless, localized, retained endpoint after its frozen budget, report `DOES NOT EMERGE—NO QUALIFIED REFINED-GRID BRANCH`.
3. If both new refinements qualify but either adjacent comparison fails or the energy differences do not contract twice, report `EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY`.
4. If both new refinements qualify, both adjacent comparisons pass, and the energy differences contract twice, report `EMERGES—THREE-LEVEL RESOLUTION-CONSISTENT LOCALIZED RETAINED BRANCH`.

The strongest verdict means that the $21^3$, $25^3$, and $29^3$ levels form a mutually consistent refined sequence under the frozen metrics, while the $17^3$ to $21^3$ discrepancy behaves as a coarse-grid effect. It does not prove continuum existence or stability beyond the tested grids.

## 9. Independent verification

The verifier must import neither the new primary driver nor any new result helper. It must independently

1. verify every manifest hash and exact frozen value;
2. verify the direct-coordinate source result, verification receipt, and source artifacts;
3. reconstruct the source diagnostics from stored arrays;
4. verify both new artifact schemas, hashes, grids, dtypes, boundary values, and coefficient vectors;
5. recompute every physical diagnostic with the explicit coefficient $h_C$;
6. recompute charge, nodelessness, localization, retention, and physical stationarity;
7. reconstruct the optimizer budget and stopping rule;
8. recompute both adjacent comparisons and all three energy differences;
9. derive the verdict directly from the frozen decision tree;
10. write a machine-readable receipt with zero mismatches for a verified result.

## References

- `computations/particle-carrier-direct-coordinate-report.md`—source result and numerical boundary.
- `computations/particle-carrier-direct-coordinate-receipt-binding.md`—canonical source receipt and terminal-artifact hashes.
- `computations/particle-carrier-direct-coordinate-prereg.md`—direct-coordinate source protocol.
- `computations/particle_carrier_direct_coordinate.py`—frozen direct field map and continuation implementation.
- `computations/verify_particle_carrier_direct_coordinate.py`—independent physical diagnostic implementation.
- `computations/particle_stationary_bvp.py`—stationary action, grids, and analytic seed.

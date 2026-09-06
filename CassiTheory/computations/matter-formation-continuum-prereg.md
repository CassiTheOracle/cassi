# Matter Formation: Continuum and Creation Preregistration

## Status: Preregistered—September 2026

## Abstract

The particle action has a conserved nonnegative carrier number and a localized stationary finite-grid branch with unresolved odd-even structure. This calculation separates carrier creation, smooth fixed-charge self-binding, and discretization effects. A conditional density-trap solution cannot establish physical matter formation, particle identity, or quantum statistics. The full research objective requires a specified microscopic production mechanism, continuum-localized solutions, temporal and nonlinear stability, a formation basin, physical normalization and particle quantum numbers, and independent empirical discrimination.

## 1. Frozen action and questions

The authority is `foundations/particle-stationary-action-closure.md`, PA11–PA12, in its scale-independent, zero-total-magnetic-charge sector. The dimensionless coefficients are $u_\rho=u_\varphi=u_H=4$, $\gamma_x=k_{Cx}=u_C=1$, $e_C=0.75$, and $h_C=2.9598260763447164$. The selected $h_C$ remains Mapped. No scan or physical fit of this coefficient is permitted.

Three questions are independent:

1. Does the first-order carrier equation permit a nonzero carrier field from exactly zero carrier data under closed boundaries?
2. Do the four stored localized fields have smooth-carrier spatial convergence under a nearest-neighbour gradient diagnostic?
3. Does a smooth scalar density-trap sector of the same continuum action support self-binding at the registered charge $Q_C=4$, or at explicitly distinguished prepared charges $16$, $64$, and $256$?

Static minimization is an energy calculation. Its iteration count and convergence are never interpreted as physical formation time or a formation basin.

## 2. Analytic work

Derive the carrier continuity equation, the empty-sector invariant, and the limitations on interpreting $Q_C$ as a signed physical charge. Check whether the static energy infimum can be reduced exactly in the trivial boundary sector by the covariant diamagnetic inequality and a constant composition/gauge representative. The candidate scalar representative is $\Psi=f\Psi_0$, $\Phi=\Phi_0$, $\mathcal A_i=0$, $\chi_C=c\ge0$, with $\|\Psi_0\|=1$ and $\Delta_\varphi=0$.

Its proposed radial functional is

$$
E=4\pi\int_0^R r^2\left[\frac12(f')^2+\frac12(c')^2+\frac{u_\rho}{4}(f^2-1)^2+\bigl(e_C-h_C(1-f^2)\bigr)c^2+\frac{u_C}{2}c^4\right]dr,
\qquad Q_C=4\pi\int_0^R r^2c^2dr.
$$

The analytic worker must verify, qualify, or reject this reduction, including composition stationarity, all omitted field variations, boundary and topology assumptions, and radial rearrangement. A lower-energy trial field proves an upper bound only. Numerical minima alone do not prove global attainment, uniqueness, fission stability, or temporal stability.

## 3. Immutable lattice diagnostic

Read the four existing NPZ artifacts without alteration:

| $N$ | Artifact | Byte-exact SHA-256 |
|---:|---|---|
| 17 | `runs/20260902_particle_carrier_direct_coordinate_v2/fields_primary_half_reference_block01.npz` | `c32beb4ee7bc7746a4fc18b63bc04ef7db12cc18505c9bee8ce2d298ddc25837` |
| 21 | `runs/20260902_particle_carrier_direct_coordinate_v2/fields_comparison_H_block01.npz` | `8aa65f3c08167c902660f9e8d09c0ce921d43c7f0af152b31aae79db6875810f` |
| 25 | `runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X1_block01.npz` | `c75a4255da2008a90268fcda83fcdbdca5a8386f9f580f854737668b664e8393` |
| 29 | `runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X2_block01.npz` | `db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0` |

All have half-width $R=4$ and $Q_C=4$. Recompute charge, the registered carrier high-frequency fraction (FFT power with any axis at least $0.75$ times Nyquist), the eight parity-class carrier norm fractions, and

$$
T_{\rm centered}=\frac{\Delta x^3}{2}\sum_{i,a}|D_{0,a}c_i|^2,
\qquad
T_{\rm edge}=\frac{\Delta x}{2}\sum_{\langle i,j\rangle}|c_i-c_j|^2.
$$

$D_0$ uses the source's centred interior derivative and second-order one-sided boundary rows. The edge diagnostic uses each nearest-neighbour edge exactly once. It is a diagnostic on the stored carrier, not a new full gauge action or a relaxed energy. Record $\Delta x^2T_{\rm edge}$ and $T_{\rm edge}/T_{\rm centered}$.

Controls: a sampled fixed-width Gaussian $c=\exp(-r^2/2)$ with zero outer shell, normalized to $Q_C=4$, on the same grids; and a periodic even-$N=16$, $\Delta x=1$ alternating field, for which $D_0(-1)^i=0$ and the edge gradient is nonzero. A separate implementation must match every scalar and parity fraction to relative tolerance $10^{-10}$, with denominator $\max(1,|x|,|y|)$, and the finest high-frequency fraction to the recorded $0.8744032081$ within $10^{-8}$.

The smooth-carrier interpretation is rejected if the two finest stored fields both have high-frequency fraction above $0.20$, both have $T_{\rm edge}/T_{\rm centered}>4$, and $\Delta x^2T_{\rm edge}$ differs by less than $20\%$ between them. This is evidence of a persistent ultraviolet branch on the measured sequence; it is not an infinite-sequence theorem. Otherwise report INCONCLUSIVE or SUPPORTS only at the measured spatial scope. A numerical-control or identity failure makes the receipt INCONCLUSIVE.

## 4. Continuum-consistent radial calculation

Use a separate cell-centred radial finite-volume variational action. Cell volumes are $V_i=4\pi(r_{i+1/2}^3-r_{i-1/2}^3)/3$ and internal face conductances are $4\pi r_{i+1/2}^2/\Delta r$. The origin has no flux. Outer Dirichlet values are $f(R)=1$, $c(R)=0$, with half-cell boundary conductance $8\pi R^2/\Delta r$. Every derivative and residual must follow this same discrete action and mass inner product. Normalize the nonnegative carrier directly to fixed charge; do not use softplus.

The frozen primary grids are $R=12$ with $192$, $384$, and $768$ cells, and $R=24$ with $768$ cells as a same-spacing larger-domain control. Charges are $4$, $16$, $64$, and $256$. On the coarsest grid use carrier Gaussians of widths $1$, $2$, and $4$, paired with $f=1-0.9\exp[-r^2/(2w^2)]$, and a delocalized carrier $c\propto\cos(\pi r/(2R))$ with $f=1$. Select the lowest-energy numerically qualified endpoint for refinement; preserve every primary basin receipt. Refine by physical-radius interpolation, then fixed-charge normalization. This continuation is declared and cannot count as independent basin evidence.

Use deterministic CPU float64 analytic derivatives and L-BFGS-B, at most $50,000$ iterations and $200,000$ objective calls per endpoint, $\mathtt{ftol}=10^{-15}$, $\mathtt{gtol}=10^{-10}$, and memory $50$. Optimization may stop at its own termination or budget. No retry or coefficient tuning through a result. A completed endpoint qualifies only if charge relative error is below $10^{-10}$, all values are finite, and the mass-weighted stationary residual satisfies both $\|r_f\|_V/\max(1,\|1-f\|_V)<10^{-4}$ and $\|r_c\|_V/\sqrt{Q_C}<10^{-4}$. Here $r_f=(\partial E/\partial f)/V$ and $r_c=(\partial E/\partial c)/(2V)-\omega_Cc$; $\omega_C$ is its carrier Rayleigh multiplier.

Binding requires $E<e_CQ_C-10^{-3}$, $\omega_C<e_C-10^{-3}$, and carrier fraction beyond $R/2$ below $10^{-3}$. Adjacent finest-grid and domain comparisons must agree in energy and carrier RMS radius to $0.5\%$ and in frequency to $10^{-3}$. Report EMERGES only for the charge-specific, qualified, resolved, bound branch. Failure to find a bound branch is DOES NOT EMERGE in the tested basins if numerical qualifications pass, and otherwise INCONCLUSIVE. It never proves nonexistence.

An independent implementation must recompute finite-volume energies, residuals, charge, radius and outer fraction from the raw radial arrays, without importing the primary driver. It must also solve the continuum radial Euler–Lagrange BVP using an independent collocation method for each qualified bound branch. Collocation tolerances are $10^{-7}$ and maximum $20,000$ nodes. Compare its energy, radius and multiplier to the finest finite-volume endpoint under the same $0.5\%$, $0.5\%$, $10^{-3}$ limits. Failure of this check leaves continuum qualification INCONCLUSIVE.

## 5. Evidence and stopping

Primary and independent lattice scripts write `runs/20260906_matter_formation/` receipts. Radial scripts write `runs/20260906_matter_formation_radial/` receipts and NPZ fields. Sources and preregistration use SHA-256 after CRLF-to-LF normalization; NPZ hashes are byte-exact. Scripts must preserve first-execution outputs and refuse silent replacement. Code corrections require a distinct receipt directory and a stated numerical reason; physical inputs and decision thresholds stay frozen.

After these finite computations, integrate results into the current formation boundary and all affected registries. Preserve all empty-sector, quantum, physical-normalization, nonradial, scale-dependent, topology, temporal and empirical qualifications. Neither a passing conditional test nor exhaustion of this protocol completes the overall matter-formation objective.

## References

- `foundations/particle-stationary-action-closure.md`—particle action, carrier charge, and spatial and temporal qualification.
- `foundations/matter-completion-boundary.md`—conditional matter chain and physical boundaries.
- `computations/particle_stationary_bvp.py`—source collocated finite-difference action.
- `computations/particle-carrier-resolution-recovery-report.md`—four immutable stationary fields.
- `computations/particle-localized-physical-hessian-report.md`—measured carrier phase ultraviolet structure.

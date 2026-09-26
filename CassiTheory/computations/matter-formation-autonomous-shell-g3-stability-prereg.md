# Autonomous Incoming-Shell Formation: G3 Finite-Core Stability Protocol

## Status: Hypothesized conditional finite-core protocol—September 2026

This protocol binds the autonomous incoming-shell action, initial data, controls,
observables, thresholds and scope in
`computations/matter-formation-autonomous-shell-g3-prereg.md`. Its executable
identity is separate so the numerical schedule is explicit.

The dimensionless inputs are

$$
(v,\lambda,g,R,A,r_s,w,a_c,T)=(1,\tfrac14,3,16,0.75,4,2,0.5,12),
$$

with the spherical $\kappa=-1$ radial Hamiltonian, finite-volume scalar
operator, local negative-energy initial covariance, normal-ordered
self-consistent scalar source, and incoming-shell data

$$
\sigma_0=v-Ae^{-(r-r_s)^2/(2w^2)},\qquad
\pi_0=A\frac{r-r_s}{w^2}e^{-(r-r_s)^2/(2w^2)}.
$$

The radial connection term in both off-diagonal blocks is the finite-core
regularization

$$
c_{a_c}(r)=\frac{1}{\sqrt{r^2+a_c^2}},\qquad a_c=0.5,
$$

in place of the singular $1/r$ coefficient. This is the declared regulated
radial model; it does not establish the unsmoothed point-core channel.

The fixed output grids are G0 $(N,\Delta r,\Delta t)=(48,1/3,0.004)$,
G1 $(72,2/9,0.002)$ and G2 $(96,1/6,0.001)$, with output times
$0,0.1,\ldots,12$. The controls are `static_vacuum`, `source_off`, and
`zero_covariance` exactly as in the base protocol.

The primary advances each listed output interval with four equal RK4
substeps. The verifier independently integrates the same real first-order
system with DOP853, `rtol=2e-8`, `atol=2e-10`, and `max_step=0.02`. The
primary and verifier compare time, scalar, and scalar-velocity archives with
maximum absolute error $5\times10^{-4}$, and compare the gauge-invariant
occupied covariance projector $P=UU^\dagger$ with maximum absolute error
$10^{-3}$. The occupied-mode matrix archives must still be finite and
shape-consistent; their phase-dependent entries are not physical observables.
Every scalar summary is compared with maximum absolute error $2\times10^{-3}$.
The solver must report `solution.success`, reach the final requested time, and
return finite arrays; the solver message text is not a failure criterion.

Pair-density core probability and pair RMS are defined as zero when the total
pair number is below $10^{-12}$. Bound observables use the physical spectral
window $0<E\le1.5$ from the action protocol and are zero when that window is
empty. The candidate formation predicates, adjacent-grid thresholds,
conservation limits, controls, independent reconstruction requirements, and
scientific verdict vocabulary are those frozen in the G3 action protocol. A
positive result remains conditional on the regulated radial channel and the
finite-energy scalar initial state; it is not a complete Cassi matter-formation
result.

## References

- `computations/matter-formation-autonomous-shell-g3-prereg.md`—G3 action, initial data, controls, bound subspace and scope.
- `foundations/matter-completion-boundary.md`—physical completion boundary.

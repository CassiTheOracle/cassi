# Three-Dimensional Radial Fermion-Bag Capture: Temporal-Resolution Recovery

## Status: Hypothesized conditional mechanism recovery protocol—September 2026

## Abstract

This source-bound recovery protocol repeats the supplied one-fermion, spherical
$\kappa=-1$ Yukawa calculation with a temporal schedule selected to resolve the
fixed-step primary trajectory against the independent DOP853 reconstruction.
The action, radial operator, packet, controls, physical thresholds, numerical
reconstruction tolerances, and stopping rule are inherited explicitly from
`computations/matter-formation-fermion-bag-capture-prereg.md`; only the fixed
time steps are changed before this recovery run. The recovery has its own
source-bound schema and output directory and cannot overwrite the first receipt.

A positive result remains a conditional radial mechanism witness. It does not
establish vacuum creation, all angular sectors, a canonical Cassi microscopic
action, a physical particle identity, or complete physical matter formation.

## 1. Declared model and boundary

Use the dimensionless action

$$
\mathcal L_{\mathrm{bag}}
=\frac12\partial_\mu\sigma\,\partial^\mu\sigma
-\frac{\lambda}{4}(\sigma^2-v^2)^2
+\bar\psi(i\gamma^\mu\partial_\mu-g\sigma)\psi,
$$

with $(v,\lambda,g)=(1,1/4,6)$, spherical radius $R=16$, and one supplied
positive-energy radial state in the $\kappa=-1$ channel. The radial spinor has
$\int_0^R(|G|^2+|F|^2)\,dr=1$. The scalar source is

$$
s_i=\frac{|G_i|^2-|F_i|^2}{4\pi r_i^2},
$$

and the radial Hamiltonian is

$$
H_{-1}(\sigma)=
\begin{pmatrix}
 g\sigma&-D-1/r\\
 D-1/r&-g\sigma
\end{pmatrix},
$$

where $D$ is the declared centered nearest-neighbour skew-adjoint finite-box
operator: $(Du)_0=u_1/(2\Delta r)$, $(Du)_i=(u_{i+1}-u_{i-1})/(2\Delta r)$,
and $(Du)_{N-1}=-u_{N-2}/(2\Delta r)$. The scalar equation uses spherical
finite-volume fluxes, zero inner flux, and fixed $\sigma(R)=v$; $\pi(R)=0$.

At $t=0$, $\sigma=v$, $\pi=0$. The supplied packet is formed on each grid
from $G\propto r\exp[-(r-1.2)^2/(2(0.6)^2)]$, $F=0$, projected onto the positive
spectral subspace of $H_{-1}(v)$, and normalized. No damping, absorber, trap,
external source, clamping, or energy removal is allowed.

## 2. Frozen recovery schedule

The primary uses fixed-step classical RK4. The independent implementation
assembles its own right-hand side and uses adaptive DOP853 with
`rtol=2e-9`, `atol=2e-11`, and `max_step=0.05`, sampling at the primary's
$t=0,0.1,\ldots,24$ archive times. The temporal schedule is frozen here:

| Grid | $N$ | $\Delta r$ | $\Delta t$ | final time |
|---|---:|---:|---:|---:|
| `G0` | 160 | $0.1$ | $0.005$ | $24$ |
| `G1` | 240 | $1/15$ | $0.0025$ | $24$ |
| `G2` | 320 | $0.05$ | $0.00125$ | $24$ |

Every arm archives all state arrays at $0.1$ time-unit intervals and the
initial/final states. The controls are `G1_g_zero` with $g=0$ and the same
packet, and $\Psi=0$. Controls are not candidate rows.

## 3. Frozen qualification

The candidate late window is $16\le t\le24$. On every candidate grid require

$$
\overline{P_4}\ge0.50,\qquad
\overline{E_\psi}\le0.95(gv),\qquad
\overline{R_\psi}\le5,
$$

with $\operatorname{sd}(P_4)\le0.10$, $\operatorname{sd}(R_\psi)\le0.75$,
$\overline{1-\sigma_0}\ge0.05$, relative total-energy drift at most
$2\times10^{-3}$, and outer scalar-energy fraction below $0.10$. Adjacent-grid
late means of $(P_4,R_\psi,E_\psi,1-\sigma_0)$ must differ by at most $0.10$.

The `g_zero` control must have $\max_t|\sigma-v|<10^{-10}$, nonzero fermion
norm, and fail the capture predicate. The `packet_zero` control must have
$\max_t|\sigma-v|<10^{-10}$ and zero fermion norm to the same tolerance.

The independent verifier must agree on source identities, schedules, initial
projections, raw arrays, conservation diagnostics, late observables, controls,
and verdict. Every sampled time and state-array shape must match. The maximum
absolute difference between primary and independent `sigma`, `pi`, `psi_re`,
and `psi_im` arrays is at most $2\times10^{-4}$; every late scalar observable
must agree to $5\times10^{-4}$. These are fixed reconstruction tolerances, not
scientific thresholds.

A candidate failure returns `DOES NOT EMERGE` within this supplied radial model.
A numerical or provenance failure returns `INCONCLUSIVE`. No parameter, grid,
packet, threshold, final time, or verdict rule may be changed after the recovery
run begins. The output directory and exclusive-created receipts are new and
must remain separate from all other attempts.

## 4. Scope

A positive receipt qualifies only localized real-time capture of the supplied
one-fermion degree-zero packet in this explicit spherical partial-wave model.
It is not quantum-vacuum production, an all-sector fermion calculation,
renormalized sea physics, a physical mass assignment, a proof of canonical
Cassi-action selection, or a complete matter-formation result.

## References

- `computations/matter-formation-fermion-bag-capture-prereg.md`—full parent protocol and action boundary.
- `computations/matter-formation-continuum-report.md` §§29, 35–36—microscopic non-identifiability and supplied-model formation boundary.
- `foundations/matter-completion-boundary.md`—completion requirements and residual physical inputs.
- Farhi, Graham, Jaffe and Weigel, [*Searching for Quantum Solitons in a 3+1 Dimensional Chiral Yukawa Model*](https://arxiv.org/abs/hep-th/0112217).
- Friedberg and Lee, [*QCD and the soliton model of hadrons*](https://doi.org/10.1103/PhysRevD.15.1694).

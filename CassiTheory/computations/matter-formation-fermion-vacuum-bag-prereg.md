# Regulated Spatial Vacuum-to-Bag Formation

## Status: Hypothesized conditional mechanism protocol—September 2026

## Abstract

This protocol tests whether a finite, spatially resolved Dirac vacuum can create
and retain a localized fermion pair while a three-dimensional scalar bubble
collapses into a self-consistent bag. It extends the radial Yukawa action used
for supplied-packet capture by replacing the one classical occupied spinor with
a finite-box negative-energy covariance. The covariance, scalar source, normal-
ordered energy, initial scalar pulse, spatial resolutions, controls,
localization observables, and stopping rule are fixed here before execution.

A positive result qualifies a regulated radial vacuum-to-bag mechanism only. The
finite-box lattice is an explicit ultraviolet regulator; the fixed-vacuum
subtraction is a finite-dimensional normal-ordering prescription, not a proof
of continuum renormalization. The calculation does not select a Cassi
microscopic action, establish all angular sectors, assign physical units or
particle identity, or complete physical matter formation.

## 1. Declared action and radial regulator

Use the dimensionless action

$$
\mathcal L_{\mathrm{bag}}
:=\frac12\partial_\mu\sigma\,\partial^\mu\sigma
-\frac{\lambda}{4}(\sigma^2-v^2)^2
+\bar\psi(i\gamma^\mu\partial_\mu-g\sigma)\psi,
$$

with $(v,\lambda,g)=(1,\tfrac14,6)$, spherical radius $R=16$, and the
$3\mathrm D$ radial $\kappa=-1$ channel. The scalar boundary is $\sigma(R)=v$ with
zero outer scalar velocity. There is no absorber, damping, trap, external
source, clamping or post-processing energy removal.

On each grid, use cell centres $r_i=(i+\tfrac12)\Delta r$ and spherical
finite-volume volumes and face areas. The scalar equation is

$$
\dot\sigma=\pi,
\qquad
\dot\pi=\frac1{r^2}\partial_r(r^2\partial_r\sigma)
-\lambda(\sigma^2-v^2)\sigma-gs_{\mathrm{NO}}(r).
$$

The radial Hamiltonian is the Hermitian finite-box operator

$$
H_{-1}(\sigma)=
\begin{pmatrix}
 g\sigma&-D-1/r\\
 D-1/r&-g\sigma
\end{pmatrix},
$$

with the centred skew-adjoint endpoint stencil
$(Du)_0=u_1/(2\Delta r)$,
$(Du)_i=(u_{i+1}-u_{i-1})/(2\Delta r)$ and
$(Du)_{N-1}=-u_{N-2}/(2\Delta r)$.

The finite-box regulator is the complete $2N$-dimensional matrix defined by
this stencil. Let $U_0$ contain every normalized negative-energy eigenvector of
$H_{-1}(v)$ as a column. The regulated vacuum covariance is
$P_0=U_0U_0^\dagger$. Evolve the occupied-mode matrix $U$ by

$$
\dot U=-iH_{-1}(\sigma)U,
\qquad U(0)=U_0.
$$

The source is normal ordered relative to this fixed vacuum:

$$
 s_{\mathrm{NO}}(r_i)
=\frac{\sum_a(|U_{i a}|^2-|U_{N+i,a}|^2)
-\sum_a(|U_{0,i a}|^2-|U_{0,N+i,a}|^2)}{4\pi r_i^2}.
$$

This subtraction makes the undeformed vacuum source exactly zero at finite
regulator size. It is the declared force prescription for this campaign.
The corresponding finite-dimensional conserved energy is

$$
\begin{aligned}
E_{\mathrm{NO}}={}&E_\sigma[\sigma,\pi]
+\Delta r\,\operatorname{Re}\operatorname{Tr}
 \left(U^\dagger H_{-1}(\sigma)U-U_0^\dagger H_{-1}(v)U_0\right)\\
&-g\sum_i V_i s_0(r_i)(\sigma_i-v),
\end{aligned}
$$

where $s_0$ is the un-subtracted initial vacuum source and $E_\sigma$ is the
finite-volume scalar energy. The last term makes the displayed energy's
variation equal to the normal-ordered scalar force. No continuum counterterm
or physical renormalization claim is made.

## 2. Vacuum-to-bag preparation and schedule

At $t=0$, the fermion state is the regulated vacuum $U_0$ and $\pi=0$. The
scalar begins as a degree-zero finite-energy bubble

$$
\sigma_i(0)=v-A\exp\left[-\frac{r_i^2}{2w^2}\right],
\qquad w=2.5.
$$

The amplitude schedule is frozen to $A\in\{1.5,2.0\}$. The two amplitudes are
reported separately; the calculation cannot choose a new amplitude after
execution. The pulse supplies finite scalar energy and is the only initial
energy source. No fermion packet, classical occupied mode or external drive is
present.

Use the following fixed grids:

| Grid | $N$ | $\Delta r$ | $\Delta t$ | final time |
|---|---:|---:|---:|---:|
| `G0` | 48 | $1/3$ | $0.004$ | $12$ |
| `G1` | 72 | $2/9$ | $0.002$ | $12$ |
| `G2` | 96 | $1/6$ | $0.001$ | $12$ |

The primary uses fixed-step RK4 and archives $\sigma$, $\pi$, and the complete
complex occupied-mode matrix $U$ at $t=0,0.1,\ldots,12$. The independent
verifier assembles the matrix operator and normal-ordered force separately and
reconstructs the same schedule with adaptive DOP853 using
`rtol=2e-8`, `atol=2e-10`, and `max_step=0.02`, sampled at those times.
Every state array and grid shape must match.

The fixed reconstruction tolerances are a maximum absolute error of
$5\times10^{-4}$ for every archived float array entry and
$2\times10^{-3}$ for every reconstructed scalar summary. These are numerical
comparison tolerances, not formation thresholds.

The controls are:

- `static_vacuum` on `G1`: $A=0$, full regulated vacuum $U_0$;
- `source_off` on `G1`: $A=1.5$, full regulated vacuum, but the normal-ordered
  source is omitted from the scalar equation while the Dirac covariance still
  evolves;
- `zero_covariance` on `G1`: $A=1.5$, $U=0$, with the scalar source identically
  zero.

Controls are not candidate formation rows. `static_vacuum` must keep
$\sigma=v$ and produce no resolved pair. `zero_covariance` must keep its
covariance norm zero and produce no pair. `source_off` is a dynamical control
for the role of reciprocal backreaction; it is not required to have zero pair
production.

## 3. Formation observables and decision rule

Let $P_+$ and $P_-$ be the positive- and negative-energy projectors of
$H_{-1}(v)$. The produced pair number in this regulated channel is

$$
N_{\mathrm{pair}}=\operatorname{Tr}(P_+UU^\dagger),
$$

and the radial particle density is obtained from the columns of $P_+U$.
Define $P_{4,\mathrm{pair}}$ as the fraction of this density inside $r<4$ and
$R_{\mathrm{pair}}$ as its RMS radius. The late window is $8\le t\le12$.

A candidate amplitude is `CAPTURED` when all three grids satisfy

$$
\overline{N_{\mathrm{pair}}}\ge0.02,
\qquad
\overline{P_{4,\mathrm{pair}}}\ge0.50,
\qquad
\overline{R_{\mathrm{pair}}}\le5,
$$

with late standard deviations
$\operatorname{sd}(N_{\mathrm{pair}})\le0.10$ and
$\operatorname{sd}(R_{\mathrm{pair}})\le0.75$, mean scalar centre deficit
$\overline{1-\sigma_0}\ge0.05$, outer scalar-energy fraction below $0.20$, and
relative $E_{\mathrm{NO}}$ drift at most $5\times10^{-3}$. Adjacent-grid late
means of $(N_{\mathrm{pair}},P_{4,\mathrm{pair}},R_{\mathrm{pair}},1-\sigma_0)$
must differ by at most $0.15$, and particle and hole counts must agree within
$0.10$ in the late mean. The control predicates above are mandatory.

Each amplitude is classified independently. If at least one frozen amplitude
has all three candidate grids captured and every numerical/provenance check
passes, the scientific verdict is
`CAPTURED—conditional regulated radial vacuum-to-bag formation`. If all
checks pass but neither amplitude is captured, the verdict is
`DOES NOT EMERGE—conditional regulated radial vacuum-to-bag formation`. Any
source, raw-array, finite-state, conservation or independent-reconstruction
failure returns `INCONCLUSIVE`.

## 4. Provenance, conservation and scope

The primary writes exclusive-create `result.json`, one raw archive per arm and
an archive of its own source bytes. The verifier writes exclusive-create
`verification.json`, independently reconstructed raw archives and its source
archive. It must reject missing inputs, altered source bytes, omitted arms,
wrong covariance shapes, nonfinite arrays, copied scientific summaries and
changed raw states. The primary and verifier must agree on the source-bound
protocol, action, pulse schedule, initial vacuum projectors, controls, all
archived shapes, conservation diagnostics, late observables and verdict.

The finite-box negative-energy covariance plus normal-ordered force is a
regulated mechanism model. A positive result establishes neither a continuum
limit nor the physical renormalization of the Dirac sea. It also does not
establish all angular sectors, multi-pair interactions, gravitational capture,
a canonical Cassi microscopic action, physical units, spin/statistics
selection or an observable particle map. A numerical or scientific failure
ends this protocol and defines the next boundary; it does not authorize
changing the pulse, regulator, grid, thresholds or stopping rule.

## References

- `computations/matter-formation-fermion-bag-capture-prereg.md`—supplied-carrier radial capture action and boundary.
- `computations/matter-formation-fermion-bag-capture-recovery-prereg.md`—temporal-resolution recovery of the supplied-carrier witness.
- `computations/matter-formation-continuum-report.md` §§14–16, 29, 98—finite-mode production, localization boundary and radial bag evidence.
- `foundations/matter-completion-boundary.md` §§12, 17—physical completion requirements and radial mechanism boundary.
- Farhi, Graham, Jaffe and Weigel, [*Searching for Quantum Solitons in a 3+1 Dimensional Chiral Yukawa Model*](https://arxiv.org/abs/hep-th/0112217)—localized fermion energy and regulated sea boundary.
- Baacke, Heitmann and Pätzold, [*Nonequilibrium dynamics of fermions in a spatially homogeneous scalar background field*](https://arxiv.org/abs/hep-ph/9806205)—semiclassical fermion backreaction and renormalization requirements.

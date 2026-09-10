# QCD-Anchored Chiral Matter-Formation Protocol

## Status: Preregistered—September 2026

## Abstract

This calculation asks whether an empirically established low-energy QCD field can close the degree-zero creation gap in the Cassi matter-formation program. The microscopic authority is the Standard Model QCD action. Its two-flavor low-energy interface is a four-component chiral order parameter with the linear sigma-model potential and the Skyrme stabilizer. A random chirally disordered field relaxes inside a fixed physical-vacuum boundary without a prepared particle, imposed trap, damping well, or selected topological degree.

The protocol separates three claims. A mathematical topology claim identifies zeros of the chiral field as the only continuum events at which its normalized map can change degree. A numerical formation claim tests whether neutral disordered data settle into resolved baryon–antibaryon textures. A cosmological applicability claim compares the QCD relaxation scale with radiation-era cooling. Importing QCD supplies empirically anchored field content and charges; it does not derive QCD from the canonical Cassi two-density state.

<!-- qcd-chiral-formation-protocol:start -->

## 1. Fixed physical interpretation

### 1.1 Microscopic authority

The selected microscopic action is the three-light-flavor QCD sector of the Standard Model,

$$
\mathcal L_{\rm QCD}
=-\frac14G^A_{\mu\nu}G^{A\mu\nu}
+\sum_{f=u,d,s}\bar q_f\left(i\gamma^\mu D_\mu-m_f\right)q_f.
$$

This action fixes color, quark fields, spin, statistics, gauge interactions, and the conserved vector baryon current. It is an empirical input to this calculation. No result below counts as a derivation of QCD from $E_Y,E_I$.

### 1.2 Low-energy formation field

Below the color-confinement scale, use the two-flavor chiral field

$$
\boldsymbol\Phi=f_\pi\,\boldsymbol\phi
=f_\pi\rho\,\hat{\boldsymbol\phi},
\qquad
\boldsymbol\phi\in\mathbb R^4,
\qquad
\hat{\boldsymbol\phi}=\frac{\boldsymbol\phi}{|\boldsymbol\phi|}.
$$

Its components represent the isoscalar and isovector quark condensates. The frozen effective action is the Holzwarth–Klomfass linear $O(4)$ sigma model with its normalized Skyrme term:

$$
\begin{aligned}
\mathcal L_2&=\frac12\partial_\mu\boldsymbol\Phi\cdot
\partial^\mu\boldsymbol\Phi,\\
\mathcal L_4&=-\frac{1}{4e^2}\left[
(\partial_\mu\hat{\boldsymbol\phi}\cdot\partial^\mu\hat{\boldsymbol\phi})^2
-(\partial_\mu\hat{\boldsymbol\phi}\cdot\partial_\nu\hat{\boldsymbol\phi})
(\partial^\mu\hat{\boldsymbol\phi}\cdot\partial^\nu\hat{\boldsymbol\phi})
\right],\\
\mathcal L_0&=-\frac{\kappa^2}{4}
(\boldsymbol\Phi^2-f^2)^2+H\Phi_0.
\end{aligned}
$$

The ordered vacuum is $\boldsymbol\phi_{\rm vac}=(1,0,0,0)$. The explicit symmetry-breaking orientation has been relabeled from component 4 to component 0. In the dimensionless coordinate $\mathbf y=e f_\pi\mathbf x/(\hbar c)$, the static energy in units $f_\pi/e$ is

$$
\begin{aligned}
\mathcal U[\boldsymbol\phi]=\int d^3y\bigg\{&
\frac12\partial_i\boldsymbol\phi\cdot\partial_i\boldsymbol\phi
+\frac12\sum_{i<j}\left[
(\partial_i\hat{\boldsymbol\phi})^2
(\partial_j\hat{\boldsymbol\phi})^2
-(\partial_i\hat{\boldsymbol\phi}\cdot
\partial_j\hat{\boldsymbol\phi})^2
\right]\\
&+\frac{\lambda}{4}(\boldsymbol\phi^2-v^2)^2
-\mu^2\phi_0-C_{\rm vac}\bigg\},
\end{aligned}
$$

where

$$
\mu=\frac{m_\pi}{ef_\pi},\qquad
\lambda=\frac{\kappa^2}{e^2},\qquad
v^2=1-\frac{\mu^2}{\lambda},\qquad
C_{\rm vac}=\frac{\lambda}{4}(1-v^2)^2-\mu^2.
$$

The subtraction makes the physical vacuum energy zero. The dissipative evolution is

$$
\frac{\partial\boldsymbol\phi}{\partial s}
=-\frac{\delta\mathcal U}{\delta\boldsymbol\phi},
\qquad
\frac{d\mathcal U}{ds}
=-\int d^3y\left|\frac{\partial\boldsymbol\phi}{\partial s}\right|^2\le0.
$$

The relaxation coordinate $s$ carries no calibrated conversion to cosmological time.

### 1.3 Topological observable

Where $|\boldsymbol\phi|>0$, the normalized field defines
$\hat{\boldsymbol\phi}:S^3_{\rm space}\to S^3_{\rm chiral}$ and

$$
B=\frac{1}{12\pi^2}\int d^3x\,
\epsilon_{ijk}\epsilon_{abcd}\,
\hat\phi_a\partial_i\hat\phi_b
\partial_j\hat\phi_c\partial_k\hat\phi_d\in\mathbb Z.
$$

A homotopy with a nonvanishing field has fixed degree. A change in $B$ therefore requires at least one spacetime point with $|\boldsymbol\phi|=0$, or a loss of continuum resolution in a lattice representation. The calculation records the minimum modulus and maximum nearest-neighbor target-space angle at every retained time. Degree and texture counts are reported only when the field is nonzero on every site and every edge angle is below $\pi/2$.

## 2. Frozen constants and geometry

Use the parameter set employed for the physical-scale chiral model:

| Quantity | Frozen value | Role |
|---|---:|---|
| $f_\pi$ | $93\ {\rm MeV}$ | condensate scale |
| $m_\pi$ | $138\ {\rm MeV}$ | explicit chiral breaking |
| $e$ | $4.25$ | Skyrme coefficient |
| $\kappa^2$ | $20$ | radial potential coefficient |
| $\Delta/f_\pi$ | $0.3$ | hot-field component width |
| $\hbar c$ | $197.3269804\ {\rm MeV\,fm}$ | unit conversion |

These give

$$
\mu=0.3491461100569260,
\quad
\lambda=1.1072664359861593,
\quad
v^2=0.8899063475546306,
\quad
m_\sigma=604.1556090942134\ {\rm MeV},
$$

and $(ef_\pi)^{-1}=0.4992459972169513\ {\rm fm}$. The finite cube has physical side $L=5\ {\rm fm}$. Its one-cell exterior shell is fixed to $\boldsymbol\phi_{\rm vac}$. Opposite fixed faces make the periodic finite-difference closure continuous.

Two grids represent the same six random physical fields:

| Grid | Sites | Physical spacing | Dimensionless spacing |
|---|---:|---:|---:|
| primary | $30^3$ | $1/6\ {\rm fm}$ | $0.3338367610271302$ |
| refinement | $40^3$ | $1/8\ {\rm fm}$ | $0.2503775707703476$ |

The primary random field is generated on $30^3$ sites and Fourier-resampled to $40^3$ sites before both boundary shells are imposed. This pairs each refinement arm to the same band-limited physical realization. The six fixed NumPy `PCG64` seeds are

$$
104729,\ 104759,\ 104761,\ 104773,\ 104779,\ 104789.
$$

Each of the four Cartesian components is centered and rescaled to standard deviation $0.3$ before the vacuum boundary is written. No field configuration is selected using its later topology.

Array index $j_\alpha\in\{0,\ldots,N-1\}$ represents
$x_\alpha=(j_\alpha-N/2)L/N$. For each seed, `PCG64.standard_normal`
draws the four primary arrays in component-major order. Each complete
$30^3$ component is centered and multiplied by $0.3$ divided by its
population standard deviation. `scipy.signal.resample` then performs real
periodic Fourier resampling from 30 to 40 successively along array axes
$x,y,z$. The refinement field is neither recentered nor rescaled. Only then
is every site with any index equal to $0$ or $N-1$ replaced by the physical
vacuum.

## 3. Discrete energy and evolution

Use forward nearest-neighbor differences for all three spatial directions. The lattice energy is the cell volume times the sum of the displayed continuum density. The normalized field used in $\mathcal U_4$ is

$$
\hat{\boldsymbol\phi}_\epsilon
=\frac{\boldsymbol\phi}{\max(|\boldsymbol\phi|,\epsilon)},
\qquad \epsilon=10^{-6}.
$$

Every site with $|\boldsymbol\phi|\le\epsilon$ is counted. This cutoff is a numerical definition at a singular point of the selected effective action; any retained texture must have zero cutoff hits throughout its qualified persistence interval.

The discrete functional gradient uses the lattice $L^2$ inner product:
if $\mathcal U_{\rm lat}=\Delta y^3\sum_{\mathbf j}u_{\mathbf j}$, then
$$
G_{\mathbf j}=\Delta y^{-3}
\frac{\partial\mathcal U_{\rm lat}}{\partial\boldsymbol\phi_{\mathbf j}}
=\frac{\partial(\sum_{\mathbf j}u_{\mathbf j})}
{\partial\boldsymbol\phi_{\mathbf j}}.
$$
Set $G=0$ on the fixed shell. Omitting $\mathcal U_4$ removes the full
normalized-field term before differentiation.

For each update, start with
$
\delta s=\min[2\times10^{-3},\,s_{\rm next}-s,\,
0.02/\max_{\mathbf j,a}|G_{\mathbf j,a}|]
$, where the last entry is omitted for a zero gradient and $s_{\rm next}$
is the next retained time. Fields with the same grid and action may be
advanced as one batch; the batch uses the smallest bound required by any
member. Accept
$\boldsymbol\phi'=\boldsymbol\phi-\delta s\,G$ only if every member's
energy increase is at most $10^{-9}\max(1,|\mathcal U|)$. Otherwise halve
the shared $\delta s$ and retry, failing if the candidate after 24
successive halvings is still unacceptable. Reapply the exact vacuum shell
before every energy comparison. End exactly at

$$
s=0,\ 0.05,\ 0.10,\ 0.25,\ 0.50,\ 1,\ 2,\ 4,\ 8.
$$

A run stops with a numerical failure on a nonfinite state, a rejected
24th halving, an energy increase beyond tolerance, a boundary change above
$10^{-7}$, or more than 100,000 accepted steps before $s=8$.

The primary dynamics use IEEE float32 on the available PyTorch accelerator. Every retained state is written as float64. An independent NumPy implementation recomputes energy components and all observables from those arrays.

## 4. Arms

### 4.1 Algebra and numerical controls

1. Vacuum on a $16^3$ grid.
2. A deterministic smooth four-component field on a $10^3$ grid. With
   $u_\alpha=j_\alpha/(N-1)$ and
   $w=\prod_\alpha\sin^2(\pi u_\alpha)$, its nonvacuum components are
   $(0.03w\cos 2\pi u_x,\ 0.08w\sin 2\pi u_x,\
   0.07w\cos 2\pi u_y,\ 0.06w\sin 2\pi u_z)$ added componentwise to
   $(1,0,0,0)$. The directional field is
   $w(\sin2\pi(u_y+u_z),\cos2\pi(u_x-u_z),
   \sin2\pi(u_x+u_y),\cos2\pi(u_y-u_z))$, normalized to unit Euclidean
   array norm. Its fixed shell is zero. Compare the automatic directional
   derivative with
   $[\mathcal U(\phi+10^{-5}d)-\mathcal U(\phi-10^{-5}d)]/(2\times10^{-5})$
   in float64.
3. A $16^3$ field with $\phi_0=1$ and
   $\phi_1=0.1(-1)^{j_x+j_y+j_z}$ before writing the vacuum shell, proving
   that the forward-difference energy is nonzero.
4. Prepared $B=+1$ and $B=-1$ hedgehogs on both physical grids, evolved
   through $s=8$.
5. The same prepared hedgehogs with $\mathcal U_4=0$ on the primary grid.

The radial profile for a prepared hedgehog is the regular solution of

$$
F''=\frac{-2rF'
-\sin(2F)\left(F'^2-1-\sin^2F/r^2\right)
+\mu^2r^2\sin F}{r^2+2\sin^2F},
\qquad F(0)=\pi,\quad F(\infty)=0,
$$

solved on $10^{-5}\le r\le64$ with the regular-origin condition
$[\pi-F(r)]-r[-F'(r)]=0$ at the left endpoint and $F(64)=0$.
The numerical profile uses `scipy.integrate.solve_bvp` on 1,201 uniform
initial nodes with relative residual tolerance $10^{-8}$ and at most
100,000 refined nodes. The initial branch is
$\pi-F=2\arctan(r/(1/\sqrt2))$; the retained profile contains 64,001
uniform samples on $0\le r\le64$.
The prepared field is
$(\cos F,\sin F\,\hat{\mathbf x})$; reflection of its first pion
component supplies the opposite orientation. The measured regular-value
degree, rather than the construction label, determines which field is
called $B=+1$. Its modulus starts at one. Prepared controls are excluded
from the formation statistic.

### 4.2 Formation arms

Run all six paired random fields with the complete energy on both grids. Run the same six primary-grid fields with $\mathcal U_4=0$. There is no topological filter, particle template, external trap, absorbing layer, or post-run seed selection.

### 4.3 Cosmological initial-condition calculation

At the measured QCD pseudo-critical temperature $T_c=156.5\pm1.5\ {\rm MeV}$, evaluate

$$
H(T)=1.66\sqrt{g_*}\frac{T^2}{M_{\rm Pl}}
$$

for the deliberately broad bracket $17.25\le g_*\le61.75$, with
$M_{\rm Pl}=1.220890\times10^{19}\ {\rm GeV}$ and
$1\ {\rm GeV}^{-1}=6.582119569\times10^{-25}\ {\rm s}$.
Compare $H^{-1}$ with $0.5$–$2\ {\rm fm}/c$, using
$1\ {\rm fm}/c=3.3356409519815204\times10^{-24}\ {\rm s}$.

## 5. Measurements

For every event and retained time, record:

- total, two-derivative, four-derivative, and potential energies;
- mean and minimum $|\boldsymbol\phi|$;
- cutoff-hit count;
- maximum nearest-neighbor angle of the exactly normalized nonzero field;
- centered-difference $B$, $B_+=\int\max(b,0)d^3x$, and $B_-=\int\max(-b,0)d^3x$;
- fixed-boundary error and accepted-step history.

At $s=4$ and $s=8$, an independent regular-value calculation divides every periodic cube into the fixed six Freudenthal tetrahedra and counts oriented preimages of 16 preregistered target values on $S^3$. A resolved positive-and-negative texture event must satisfy all of:

The piecewise map is defined by linearly interpolating the four
unnormalized vertex vectors within each tetrahedron and then normalizing.
Every periodic cube uses these ordered vertex strings:

```
000 100 110 111
000 110 010 111
000 010 011 111
000 011 001 111
000 001 101 111
000 101 100 111
```

For $m=1,\ldots,16$, the fixed regular target is

$$
\mathbf t_m=
\frac{\sin\!\left(m\sqrt{(2,3,5,7)}+(0.11,0.23,0.37,0.53)\right)}
{\left|\sin\!\left(m\sqrt{(2,3,5,7)}+(0.11,0.23,0.37,0.53)\right)\right|}.
$$

For the $4\times4$ vertex matrix $M$, a target-ray hit satisfies
$M\mathbf c=\mathbf t_m$ with every $c_a>10^{-10}$. Its barycentric
position is $\mathbf c/\sum_a c_a$, and its sign is the product of
$\operatorname{sgn}\det M$ and the oriented spatial tetrahedron sign.
A target is ambiguous when all $c_a>-10^{-9}$ and at least one
$|c_a|\le10^{-9}$, or when a hit has
$|\det M|<10^{-12}$. Matrices with $|\det M|\le10^{-13}$ are excluded
before the solve. The signed global degree is the positive-hit count minus
the negative-hit count.

The physical baryon-density RMS radius uses $|b|$ as its weight, periodic
circular means in each Cartesian index coordinate, and minimum-image
physical distances in the $5\ {\rm fm}$ cube. A vanishing total
$|b|$ has no radius.

1. maximum edge angle below $\pi/2$;
2. zero ambiguous target-face or singular-tetrahedron intersections;
3. at least one positive and one negative preimage for every target;
4. the same signed global degree for all 16 targets;
5. zero cutoff hits from $s=4$ through $s=8$.

This definition can count an event containing several textures. It makes no claim that a particular positive and negative preimage form a permanently bound pair.

## 6. Frozen decisions

### QCF1—action and discretization

`PASS` requires vacuum residual below $10^{-7}$ per component, finite-difference directional-derivative relative error below $3\times10^{-4}$, positive checkerboard energy, monotone accepted-step energy in every arm, fixed-boundary error below $10^{-7}$, and no numerical stop. Otherwise QCF1 is `FAIL`, and all formation verdicts are `INCONCLUSIVE`.

### QCF2—prepared baryon stability

`SUPPORTS` requires both signs on both grids to retain their signed degree at $s=4$ and $s=8$, with no ambiguity, edge angle below $\pi/2$, zero cutoff hits, and centered-difference $|B|\ge0.65$. It also requires at least three of the four complete-action textures to have a physical baryon-density RMS radius in $[0.20,1.20]\ {\rm fm}$ at both times. The verdict is `CONTRADICTS` if a complete-action sign is absent at $s=8$ after QCF1 passes; otherwise it is `INCONCLUSIVE`.

### QCF3—unseeded neutral texture formation

`EMERGES` requires at least four of six complete-action events on each grid to satisfy the resolved positive-and-negative definition at both $s=4$ and $s=8$. The two formation fractions may differ by at most $2/6$. The complete-action endpoint fraction must exceed the no-$\mathcal U_4$ endpoint fraction by at least $3/6$. `DOES NOT EMERGE` applies if no complete-action event on either grid contains a resolved positive and negative texture at $s=8$. Every other outcome is `INCONCLUSIVE`.

### QCF4—degree-zero creation channel

`SUPPORTS` requires at least one complete-action event whose common signed degree is zero and which contains both signs at $s=4$ and $s=8$. It also requires a recorded interval before qualification with $\min|\boldsymbol\phi|\le10\epsilon$ or maximum edge angle at least $\pi/2$, establishing that the route passed through the only allowed degree-change boundary. `CONTRADICTS` applies if every qualified event has nonzero net degree or no boundary interval. Other outcomes are `INCONCLUSIVE`.

### QCF5—cosmological sudden-quench applicability

`CONTRADICTS` requires both the measured crossover classification at physical quark masses and a minimum $H^{-1}/(2\ {\rm fm}/c)>10^{12}$ across the full frozen $T_c,g_*$ bracket. `SUPPORTS` requires a first-order transition under the stated physical conditions and a maximum ratio below $10^3$. Other outcomes are `INCONCLUSIVE`.

### QCF6—physical matter completion

`PASS` requires all five physical requirements below in the retained artifacts:

1. the microscopic QCD action and quantum state arise from a declared Cassi selection rule;
2. conserved quark baryon current is transported through the chiral zero events;
3. late textures have quantized fermionic spin and statistics;
4. physical particle occupation numbers and production probabilities follow from a density operator;
5. the cosmological initial state and cooling history are supplied without a fitted formation outcome.

If any requirement is absent, QCF6 is `FAIL` and `complete_physical_matter_formation=false`. Conditional chiral texture formation may still receive `EMERGES` under QCF3.

## 7. Stopping and evidence rules

Execute every arm once. Code or protocol defects may be repaired only by an amendment that states the defect, preserves all completed raw outputs, changes the protocol hash, and reruns every affected arm. Physical thresholds, seeds, parameters, targets, and decision branches remain fixed. Each primary receipt stores source hashes, protocol bytes and hash, environment information, every retained state hash, and the final verdict inputs. The independent verifier must reconstruct observables from arrays rather than importing primary numerical functions. Missing primary input exits nonzero and yields `INCONCLUSIVE` for QCF1–QCF5 and `FAIL` for QCF6.


### 7.1 Implementation amendment—September 2026

The retained execution at
`runs/20260909_qcd_chiral_matter_formation/primary/` used protocol hash
`31579034a381292afde7e2660916a4e3eb1fb161a626329404d5ffc50185d62b`
and solver hash
`0c8b13a3829cbf18fb44fcdda0b0e46bc92741d06bf2451acd49e2a439774f09`.
It passed the algebraic controls, entered `N30_complete`, and invoked the
frozen numerical stopping rule at
$s=0.03107724709385565$ after 11,609 accepted steps and 76,513 rejected
step halvings. Its partial history is retained with SHA-256
`4a78bcf88671320b00991ce61f9f8acc24c23986c16a97c8867588c9dce213cc`.
No event reached the first nonzero retained time, so this attempt supplies
no formation or persistence classification.

The executable evidence contract uses a group object keyed by arm name,
target indices $1,\ldots,16$, explicit values for every frozen constant
and control scalar consumed by the independent verifier, the full
$s\ge4$ cutoff history in texture qualification, and a nonnegative
maximum energy-tolerance excess. The QCF5 upper comparison uses the
declared $H^{-1}/(2\ {\rm fm}/c)$ ratio. Event types, physical count
ranges, detailed formation summaries, and all QCF1–QCF5 gate inputs are
reconstructed from the retained arrays. QCF6 fails closed because the
five required physical observables are absent from this experiment.
The acceptance energy is evaluated from the float32 state with float64
arithmetic. This resolves an implementation mismatch in which float32
local-energy rounding was compared with the frozen $10^{-9}$ relative
tolerance. The evolved state, functional gradient, Euler update, and all
frozen step bounds remain float32 and unchanged. These corrections make
crash recovery and independent reconstruction unambiguous. They do not
change the action, ensemble, lattice fields, parameters, targets,
evolution rule, retained times, thresholds, or decision tree.

Every affected arm is rerun once from its original initial array into the
fresh `runs/20260909_qcd_chiral_matter_formation/amendment-1/` evidence
directory. A repeated numerical stop is retained as QCF1 `FAIL`, QCF2–QCF5
`INCONCLUSIVE`, and QCF6 `FAIL`; it does not authorize a regulator,
integrator, ensemble, or threshold change. The independent verifier fails
closed on any incomplete primary package and retains the primary and
verification source identities in its failure receipt.

<!-- qcd-chiral-formation-protocol:end -->

## 8. Scope of a positive result

A positive formation result would establish a reproducible classical relaxation route from chirally disordered finite-energy data to resolved Skyrme textures in an empirically anchored QCD effective field. The result would supply a concrete optional matter-formation benchmark for CassiCosmos. It would leave the Cassi-to-QCD reduction, quantum creation probabilities, conserved baryon-current transfer at chiral zeros, spin/statistics, and cosmological baryogenesis open unless QCF6 passes.

## References

- `computations/matter-formation-continuum-report.md` §§29, 32, 36–38, 76–77—formation boundary, constrained chiral dynamics, and conditional massive baryon benchmark.
- `foundations/matter-completion-boundary.md` §§9, 12–13—non-identifiability theorem and physical completion requirements.
- `foundations/unified-lagrangian.md` §4—registered Standard Model gauge and matter sector.
- G. Holzwarth and J. Klomfass, “The Chiral Phase Transition in Dissipative Dynamics,” arXiv:hep-ph/0206228—linear $O(4)$ action, physical parameters, random hot initial fields, lattice scale, and TDGL evolution.
- A. Bazavov et al., “Chiral crossover in QCD at zero and non-zero chemical potentials,” arXiv:1812.08235—continuum-extrapolated physical-mass QCD crossover and $T_c=156.5\pm1.5\ {\rm MeV}$.

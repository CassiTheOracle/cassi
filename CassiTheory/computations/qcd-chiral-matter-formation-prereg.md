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

## 3. Discrete energy and evolution

Use forward nearest-neighbor differences for all three spatial directions. The lattice energy is the cell volume times the sum of the displayed continuum density. The normalized field used in $\mathcal U_4$ is

$$
\hat{\boldsymbol\phi}_\epsilon
=\frac{\boldsymbol\phi}{\max(|\boldsymbol\phi|,\epsilon)},
\qquad \epsilon=10^{-6}.
$$

Every site with $|\boldsymbol\phi|\le\epsilon$ is counted. This cutoff is a numerical definition at a singular point of the selected effective action; any retained texture must have zero cutoff hits throughout its qualified persistence interval.

Advance explicit steepest descent with an attempted step $\Delta s=2\times10^{-3}$. Limit the largest component change in one accepted step to $0.02$. If any event energy increases by more than
$10^{-9}\max(1,|\mathcal U|)$, halve the step and retry; reject after 24 halvings. End exactly at each retained time

$$
s=0,\ 0.05,\ 0.10,\ 0.25,\ 0.50,\ 1,\ 2,\ 4,\ 8.
$$

A run stops with a numerical failure on a nonfinite state, a rejected 24th halving, an energy increase beyond tolerance, a boundary change above $10^{-7}$, or more than 100,000 accepted steps before $s=8$.

The primary dynamics use IEEE float32 on the available PyTorch accelerator. Every retained state is written as float64. An independent NumPy implementation recomputes energy components and all observables from those arrays.

## 4. Arms

### 4.1 Algebra and numerical controls

1. Vacuum on a $16^3$ grid.
2. A smooth small-amplitude four-component field on a $10^3$ grid for a centered finite-difference directional-derivative check of the complete discrete energy.
3. A checkerboard field proving the forward-difference energy is nonzero.
4. Prepared $B=+1$ and $B=-1$ hedgehogs on both physical grids, evolved through $s=8$.
5. The same prepared hedgehogs with $\mathcal U_4=0$ on the primary grid.

The radial profile for a prepared hedgehog solves the massive stationary Skyrme boundary-value equation with $F(0)=\pi$ and $F(\infty)=0$ at the frozen $\mu$. Its modulus starts at one. Prepared controls are excluded from the formation statistic.

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

<!-- qcd-chiral-formation-protocol:end -->

## 8. Scope of a positive result

A positive formation result would establish a reproducible classical relaxation route from chirally disordered finite-energy data to resolved Skyrme textures in an empirically anchored QCD effective field. The result would supply a concrete optional matter-formation benchmark for CassiCosmos. It would leave the Cassi-to-QCD reduction, quantum creation probabilities, conserved baryon-current transfer at chiral zeros, spin/statistics, and cosmological baryogenesis open unless QCF6 passes.

## References

- `computations/matter-formation-continuum-report.md` §§29, 32, 36–38, 76–77—formation boundary, constrained chiral dynamics, and conditional massive baryon benchmark.
- `foundations/matter-completion-boundary.md` §§9, 12–13—non-identifiability theorem and physical completion requirements.
- `foundations/unified-lagrangian.md` §4—registered Standard Model gauge and matter sector.
- G. Holzwarth and J. Klomfass, “The Chiral Phase Transition in Dissipative Dynamics,” arXiv:hep-ph/0206228—linear $O(4)$ action, physical parameters, random hot initial fields, lattice scale, and TDGL evolution.
- A. Bazavov et al., “Chiral crossover in QCD at zero and non-zero chemical potentials,” arXiv:1812.08235—continuum-extrapolated physical-mass QCD crossover and $T_c=156.5\pm1.5\ {\rm MeV}$.

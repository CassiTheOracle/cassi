# Counterflow Resonant Addressing (Wave 1)

## Status: Hypothesized—August 2026

## Abstract

This frozen probe tests a narrow solver-level projection of a proposed cognitive field mechanism: a continuously present Yin–Yang field carries a paired right-up/left-down flow proxy, while an additive probe applies an externally supplied, seed-angle-gated concentration/redistribution pulse to a bubble. The test asks whether the seeded-angle pulse arm produces a larger local density-plane diagnostic response than equal-norm seed-angle-wrong and spatially shuffled controls. Between those supplied pulses it runs the unmodified canonical two-fluid PDE/RK2 evolution in `two-fluid/cassi_two_fluid_3d_gpu.py`; the probe does not turn the pulse, carrier, or trigger into a native PDE mechanism. It does not establish endogenous phase-address selection, a biological circulation, a neural action mechanism, or a full brain model.

The symbols $\theta_i$, $\psi_\mathrm{ref}$, and $\psi$ are finite seed-angle
parameters for the real $(\rho,\varepsilon)$ perturbation and its controls. They
are protocol coordinates for the seeded construction. The canonical derived
density-plane angle is
$\theta_d=\operatorname{atan2}(E_I,E_Y)$; the conversion ODE relaxes this angle
toward the equilibrium ratio. The probe evolves no independent compact periodic
phase.

## 1. Question and scope

The proposed mechanism has four components:

1. a background field supplies energy throughout the domain;
2. a paired-flow proxy rises through one side and descends through the other;
3. the additive probe evaluates a seeded local angle match and, when its threshold is met, supplies a concentrated pulse;
4. the seeded angle labels and checkerboard routing are tested for a larger density-plane diagnostic response under that supplied operator.

The canonical solver has one shared incompressible velocity field. It cannot represent separate Yang and Yin carrier velocities, anatomical boundaries, a physical body loop, or a neural source. This probe therefore uses a periodic paired-stream proxy and records both the shared hydrodynamic velocity and the independent density-plane diagnostic $J_d$. The result is limited to whether this minimal, externally driven construction is dynamically distinguishable in the shipped solver.

The unmodified canonical PDE/RK2 implementation is `two-fluid/cassi_two_fluid_3d_gpu.py`. The additive pulse, trigger, and receipt logic are supplied by `field-experience/counterflow_resonant_addressing_probe.py`; they are not canonical dynamics.

## 2. Frozen field construction

### 2.1 Solver and horizon

Each arm uses a fresh `ExpandingTwoFluid3DGPU` with:

| quantity | value |
|---|---:|
| grid | $48^3$ |
| domain | $L=2\pi$, periodic |
| gate | five-channel Qi gate |
| $\lambda$ | $0.05$ |
| $D$ | $2\times10^{-4}$ |
| $\nu$ | $5\times10^{-4}$ |
| $\chi$ | $0$ |
| timestep | $dt=0.001$ |
| horizon | $t=4.0$ (4,000 RK2 steps) |
| report cadence | 0.05 |

The field begins at the $\varphi$-equilibrium background

$$
\rho_0=1+\varphi^{-1},\qquad \varepsilon=E_Y-\varphi E_I=0.
$$

A finite local checkerboard proxy contains five Gaussian bubbles of width $\sigma=3$ cells at

$$
(12,12,24),\ (12,36,24),\ (24,24,24),\ (36,12,24),\ (36,36,24).
$$

These are the even-parity sites of a $3\times3$ local checkerboard. The target is $(12,12,24)$; its diagonal checkerboard neighbor is $(24,24,24)$. A bubble with center $c_i$ and seed angle $\theta_i$ in the real $(\rho,\varepsilon)$ parameterization contributes

$$
\delta\rho_i=A_B g_i\cos\theta_i,\qquad
\delta\varepsilon_i=A_B g_i\sin\theta_i,
\qquad A_B=0.20,

$$

where $g_i$ is its periodic Gaussian envelope. The real fields are reconstructed as

$$
E_Y=\frac{\varphi\rho+\varepsilon}{1+\varphi},
\qquad
E_I=\frac{\rho-\varepsilon}{1+\varphi}.
$$
The seed angle $\theta_i$ is a finite parameter that encodes the local
$(\delta\rho_i,\delta\varepsilon_i)$ direction. It is not an independently
evolved compact field phase or a prescribed per-rung advance. The derived
canonical angle $\theta_d$ is computed from $(E_Y,E_I)$ after reconstruction.

The right-side bubbles at $x=12$ use seed angle $\theta=+\pi/4$ and the left-side bubbles at $x=36$ use seed angle $\theta=-\pi/4$; the central bubble uses $\theta=0$. A local axial seed-angle modulation has amplitude $0.50$ rad and opposite sign on the right and left bubbles. It supplies a finite initial $J_{d,z}$ for the density-plane diagnostic.

### 2.2 Paired circulation proxy

The background shared velocity is the zero-mean, divergence-free shear

$$
u_z(x)=sU\sin(2\pi x/L),\qquad U=0.12,
$$

with all other components zero and $s\in\{+1,-1,0\}$. Thus the $x=12$ side has $u_z>0$ and the $x=36$ side has $u_z<0$ for $s=+1$. Its periodic closure is a computational proxy for a circulation, not an anatomical model.

The independent density-plane diagnostic is

$$
\mathbf J_d=E_Y\nabla E_I-E_I\nabla E_Y,
\qquad
J_{d,z}=E_Y\partial_zE_I-E_I\partial_zE_Y
=\left(E_Y^2+E_I^2\right)\partial_z\theta_d.
$$

$J_d$ is a spatial density-plane-angle-gradient diagnostic. It has units
distinct from an amplitude current $J_\Psi$, and it acquires no transport
interpretation without a separate constitutive law, projection, and test.

The positive and negative counterflow arms reverse both the shared velocity and the signs of the seeded axial density-plane gradients. The zero-counterflow arm sets both to zero.

## 3. Seed-angle match trigger and pulse

At each fixed cadence event $t_n=n(0.02)$ for $n=1,\ldots,199$, the matched arm measures the target bubble's seeded-angle diagnostic phasor

$$
S_T=\left\langle(\rho-\rho_0)+i\varepsilon\right\rangle_T,
\qquad
M_n=\operatorname{Re}\!\left[\frac{S_T}{|S_T|}e^{-i\psi_\mathrm{ref}}\right],
\qquad
\psi_\mathrm{ref}=\pi/4.
$$

It emits a pulse only when

$$
M_n\geq\cos(\pi/6).
$$

Each accepted pulse is a local increase coupled to a diffuse compensating reservoir. Let $g_T$ be the target Gaussian normalized to unit integral and $r$ the complementary outside-target mask normalized to unit integral. For pulse seed angle $\psi$,

$$
\delta\rho=A(g_T-r)\cos\psi,
\qquad
\delta\varepsilon=A(g_T-r)\sin\psi.
$$

The perturbation is reconstructed into $(\delta E_Y,\delta E_I)$ with the same linear map as the seed and rescaled so that

$$
\sum_{\mathbf x}\left[(\delta E_Y)^2+(\delta E_I)^2\right]=1.0.
$$

The construction therefore preserves global $\rho$ and $\varepsilon$ while keeping the discrete doublet-norm pulse budget identical across arms. It is a concentration/redistribution proxy supplied by the probe, not a source term derived from the canonical PDE.

The matched arm defines the accepted event schedule. Every driven control replays those exact event times and the same norm. This prevents event count or injected norm from becoming a seed-angle control confound; it also means the schedule is imposed rather than an emergent phase clock.

## 4. Frozen arms

| arm | circulation | lattice seed-angle pattern | pulse |
|---|---|---|---|
| `baseline` | $s=+1$ | ordered | none |
| `matched` | $s=+1$ | ordered | seed-angle-triggered, $\psi=+\pi/4$ |
| `phase_wrong` | $s=+1$ | ordered | replayed schedule, $\psi=-\pi/4$ |
| `spatial_shuffled` | $s=+1$ | central and left seed-angle labels swapped | replayed matched pulse |
| `counterflow_reversed` | $s=-1$ | ordered | replayed matched pulse |
| `counterflow_zero` | $s=0$ | ordered | replayed matched pulse |

The $\pm\pi/4$ pulse seed angles are separated by $\pi/2$ while retaining the same positive $\rho$ component before exact doublet-norm normalization. The shuffled arm preserves bubble envelopes and seed-angle magnitudes but disrupts the ordered target-to-diagonal-neighbor code. The frozen `phase_wrong` arm name is retained as a receipt-compatible legacy label for the seed-angle-wrong control. These finite labels and the event trigger are not independently evolved compact phases.

## 5. Quality gates and observables

The run is **INVALID** if any condition fails:

1. the no-op wrapper identity check differs from the direct canonical RK2 loop by any nonzero floating-point value after 100 steps;
2. any arm contains a non-finite value, an $E_Y$ or $E_I$ floor hit, or a target-source pulse with nonzero total $\rho$ or $\varepsilon$ to numerical precision;
3. accepted-pulse norms differ between replayed arms by more than $10^{-12}$;
4. the matched arm accepts fewer than 30 events;
5. the ordered positive-counterflow seed lacks the expected opposite signed $u_z$ and $J_{d,z}$ biases on its $x=12$ and $x=36$ bubbles.

At each pulse event, the probe records the pre-pulse and ten-step-later signed density-plane diagnostic along the target-to-diagonal edge,

$$
j_{d,\parallel}=\left\langle\mathbf J_d\cdot\frac{(1,1,0)}{\sqrt2}\right\rangle_{T\leftrightarrow D},
\qquad
r_n=\frac{j_{d,\parallel}(t_n+0.01)-j_{d,\parallel}(t_n^-)}{J_{d,\mathrm{rms},0}},
$$

where $J_{d,\mathrm{rms},0}$ is the initial edge-window RMS density-plane diagnostic magnitude. The primary statistic is the mean event response $\bar r$ over contiguous blocks of 20 events. The probe reports a fixed-seed 10,000-resample paired block-bootstrap 95% interval for every contrast.

For receipt compatibility, the probe keeps the historical keys `j_edge`,
`j_rms_edge`, `jz_target`, `jz_right`, and `jz_left`. These `j*` labels store
projections or norms of $J_d$; they are legacy labels and do not denote the
amplitude current $J_\Psi$ or transport between cascade scales.

Secondary readouts are target and diagonal diagnostic phasors, seed-angle relation relative to the seeded edge relation, $J_{d,z}$ on right/left bubble masks, right/left mean shared $u_z$, canonical $q$, field minima, total mass, pulse norms, and response histories.

## 6. Frozen decision tree

Let

$$
\Delta_{\mathrm{phase}}=\bar r_{\mathrm{matched}}-\bar r_{\mathrm{phase\_wrong}},
\qquad
\Delta_{\mathrm{space}}=\bar r_{\mathrm{matched}}-\bar r_{\mathrm{spatial\_shuffled}}.
$$

The frozen names $\Delta_{\mathrm{phase}}$ and `phase_wrong` retain the
protocol's historical terminology. Their comparison is a seeded
$(\rho,\varepsilon)$ angle control; it does not compare independently evolved
periodic phases.

A contrast is positive only if its point estimate is at least $0.05$ and its paired 95% block-bootstrap interval has a lower bound above zero.

- **PHASE-SELECTIVE SUPPORT** requires a positive $\Delta_{\mathrm{phase}}$.
- **CHECKERBOARD-ROUTING SUPPORT** requires a positive $\Delta_{\mathrm{space}}$.
- **COUNTERFLOW-DEPENDENCE SUPPORT** requires positive, non-overlapping-zero contrasts of matched against both `counterflow_reversed` and `counterflow_zero`, plus the prescribed $J_{d,z}$ sign reversal.

- **PARTIAL** applies when one or two named contrasts pass their corresponding criteria.
- **NULL** applies when the execution is valid and no named contrast passes.
- **INVALID** applies only through the quality gates above.

The uppercase decision labels are frozen verdict names; **PHASE-SELECTIVE
SUPPORT** means seed-angle selectivity in this construction.

These are protocol feature labels, not repository-level physical inferences. The
`phase_wrong` contrast changes the supplied seeded $(\rho,\varepsilon)$ angle;
`spatial_shuffled` changes the supplied label arrangement; and the reversed and
zero arms change the supplied shared-flow/seeded-gradient conditions. All driven
arms use the matched schedule replay. No arm varies an endogenous phase oscillator
or a native canonical phase-address operator, so a positive branch would not
demonstrate endogenous phase-address selection.

No frequency, amplitude, threshold, geometry, or horizon is tuned after this document. The run stops at $t=4$. A longer $t=40$ persistence experiment requires a separate pre-registration and is warranted only if the present protocol has valid phase-selective and checkerboard-routing support.

## 7. Interpretation boundary

A positive result would show that this particular seed-angle-addressed redistribution construction changes the canonical solver's local $J_d$ density-plane diagnostic response beyond specified controls. It would not identify the source of a neural pulse, validate a biological hemisphere assignment, establish consciousness, or demonstrate a self-sustaining macro-spiral. In particular, it would remain evidence about a supplied operator and its seeded controls, not endogenous phase matching in the PDE.

A null would constrain this frozen construction over its stated short horizon. It would not settle other counterflow geometries, pulse laws, brain couplings, or a solver with separate Yang/Yin carrier velocities.

## References

- `two-fluid/cassi_two_fluid_3d_gpu.py`—canonical two-fluid solver.
- `two-fluid/run_lattice_stack_probe.py`—doublet seed-angle construction and density-plane diagnostics.
- `two-fluid/run_churning_gate.py`—localized pre-RK2 drive seam.
- `two-fluid/run_coherence_budget_contrast.py`—equal-power control pattern.
- `foundations/qi-flow-double-helix.md`—density-plane diagnostic definitions and transport boundary.
- `foundations/bubble-lattice-fabric.md`—staggered checkerboard geometry.
- `consciousness/two-strand-qi-neuroscience.md`—phase/current and neural-mapping boundaries.

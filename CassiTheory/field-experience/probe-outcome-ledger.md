# Field-Experience Probe Outcome Ledger

## Status: Record—September 2026

## Abstract

This ledger indexes the six completed counterflow/source-only field experiments, the independent phase-staggered scale-gap campaign, the conditional Qi-loop mass-cascade campaign, and the three-dimensional toroidal survival, spectral-transfer, and connected-hierarchy campaigns through their frozen protocols, raw receipts, gates, and terminal classifications. The source records retain each construction's scope: the six-wave chain uses finite proxies with externally supplied additive interventions and unmodified canonical PDE/RK2 evolution; the scale-gap campaign tests supplied-wave identities, the distinct second-order CassiCosmos wave branch, and a declared nearest-neighbor chain; the Qi-loop campaign evaluates a supplied compact Hamiltonian; toroidal V5 declares a supplied two-component Schrödinger–Poisson evolution; the transfer diagnosis analyzes frozen V5 fields inside one domain; and the connected hierarchy declares six fields arranged as three labeled scale pairs with a supplied symmetric gravitational graph. The ledger assigns no mechanism beyond those declared boundaries.

The Navier–Stokes controls in §7 concern the original incompressible velocity equation. They reproduce exact transfer identities and test supplied geometric constraints through instantaneous derivatives, with no field-time simulation or singularity search.

## 1. How to read this record

The report and pre-registration links in the table are the source pair for each wave. The `runs/...` entries are the raw receipt paths quoted by the reports; they are intentionally gitignored run artifacts. `EMERGES` and `DOES NOT EMERGE` are frozen feature-level labels for the specified supplied interventions and readouts. The terminal outcome is the report's repository-level classifier and is separate from feature labels; a feature can emerge while the terminal classification remains **INCONCLUSIVE** or **CONTRADICTS**.

## 2. Frozen wave outcomes

| wave | report | pre-registration | raw receipt | decisive discriminator and feature gates | terminal report outcome |
|---|---|---|---|---|---|
| 1—Counterflow Resonant Addressing | `field-experience/counterflow-resonant-addressing-wave-1-report.md` | `field-experience/counterflow-resonant-addressing-pre-registration.md` | `runs/20260818_164007_counterflow_resonant_addressing/results.json` | Protocol-validity **FAIL** at the `$E_Y/E_I$` floor-contact gate: the first contact was at $t=3.501$ in `matched`, `spatial_shuffled`, and `counterflow_reversed`. None of the retained supplied seed-angle/label/flow contrasts reached the frozen $0.05$ response margin or excluded zero; no endogenous phase-address inference is available. | **INCONCLUSIVE** |
| 2—Counterflow Amplitude-Phase Kick | `field-experience/counterflow-amplitude-phase-kick-wave-2-report.md` | `field-experience/counterflow-amplitude-phase-kick-pre-registration.md` | `runs/20260818_165550_counterflow_amplitude_phase_kick/results.json` | Every execution and invariant gate passed, but the registered raw signed-mean response had no qualifying contrast: matched minus carrier-quadrature was $-4.49\times10^{-6}$ and no contrast reached the frozen $0.05$ margin. The externally supplied carrier $(+1,+1,-1,-1)$ cancels in that raw mean; this is the pre-registration's `NULL` branch mapped to repository terminal **DOES NOT EMERGE**, not an endogenous phase-selectivity result. | **DOES NOT EMERGE** |
| 3—Counterflow Carrier Demodulation | `field-experience/counterflow-carrier-demodulation-wave-3-report.md` | `field-experience/counterflow-carrier-demodulation-pre-registration.md` | `runs/20260818_170450_counterflow_carrier_demodulation/results.json` | The imposed matched-carrier projection minus carrier-quadrature coherence was $0.99459$ with interval $[0.98410,0.99984]$ (**PASS**). Matched minus spatial-shuffled was $1.01\times10^{-6}$, reversed-flow $2.44\times10^{-16}$, and zero-flow $-4.59\times10^{-7}$; each **DOES NOT EMERGE**. The pre-registration's `PARTIAL` branch is mapped to repository terminal **INCONCLUSIVE**; the pass is an imposed-operator/readout check, not endogenous phase selection. | **INCONCLUSIVE** |
| 4—Checkerboard Edge Phase Coupling | `field-experience/checkerboard-edge-phase-coupling-wave-4-report.md` | `field-experience/checkerboard-edge-phase-coupling-pre-registration.md` | `runs/20260818_172003_checkerboard_edge_phase_coupling/results.json` | F1 carrier-correlated receiver projection under the supplied corridor kick was $0.99454$ with interval $[0.98411,0.99976]$ (**EMERGES**). F2 diagonal route specificity was $-7.19\times10^{-7}$ and F3 directed-ramp specificity was $-8.24\times10^{-7}$; both **DOES NOT EMERGE**. F1 is an imposed-carrier/readout feature, not endogenous phase selection or route transport. | **INCONCLUSIVE** |
| 5—Source-Only Passive Transfer | `field-experience/source-only-passive-transfer-wave-5-report.md` | `field-experience/source-only-passive-transfer-pre-registration.md` | `runs/20260818_182603_source_only_passive_transfer/results.json`<br>Report excludes stale `runs/20260818_181939_source_only_passive_transfer/`. | With disjoint compact source and receiver supports, the supplied-pulse F1 passive diagonal score was $15.40435$ and F2 diagonal-over-axial normalized score was $15.37575$ (**EMERGES**). F3 supplied phase-arrangement dependence was $E-E_{\rm shuf}=-4.45190$ (**DOES NOT EMERGE**). The diagonal trace was delayed, but the direct diagonal denominator collapses under shuffled labels ($8.23757\times10^{-6}$ to $2.19932\times10^{-9}$), so the fractions are poorly conditioned score labels rather than route evidence. The pre-registration's `HOLD` branch is mapped to repository terminal **INCONCLUSIVE**. | **INCONCLUSIVE** |
| 6—Source-Only Field-Space Timing | `field-experience/source-only-fieldspace-timing-wave-6-report.md` | `field-experience/source-only-fieldspace-timing-pre-registration.md` | `runs/20260818_184621_source_only_fieldspace_timing/results.json` | F1 supplied-pulse diagonal field-space response **EMERGES**. F2 delayed timing **DOES NOT EMERGE** because $k_{50,D}=k_{50,A}=96$ and $p_D=0.9957147<p_A=0.9957239$; $Q_A^{\rm late}$ is about $26.5\times Q_D^{\rm late}$. F3 supplied label-specific timing **DOES NOT EMERGE** because the shuffled timing is unchanged. The formal classifier is **CONTRADICTS**, not a soft unestablished result. | **CONTRADICTS: NO DELAYED-DIAGONAL FIELD-SPACE TIMING IN THIS SOURCE-ONLY PROXY.** |

## 3. Independent phase-staggered scale-gap campaign

| record | report | pre-registration | raw receipt | decisive discriminator and feature gates | terminal outcome |
|---|---|---|---|---|---|
| Parent time-domain probe | `field-experience/phase-staggered-scale-gap-report.md` | `field-experience/phase-staggered-scale-gap-pre-registration.md` | `runs/20260827T093422Z_phase_staggered_scale_gap/results.json`<br>`runs/20260827T093616Z_phase_staggered_scale_gap/results.json` | Stages A/B verify exact adjacent-layer parity, nodes, and unequal-amplitude contrast. E1 gives a zero phase-only gap; E2/E3 give a unit dimerized gap and $4.738\times10^{-6}$ transmission. Both D0 time-domain lock-ins fail sub-gap attenuation ($1.158827$, $1.391807$) because undamped travelling transients remain in the finite windows; a literal all-metrics-finite reading also flags undefined D0/D3 reference and fit fields, so parent Stage D stays **INCONCLUSIVE**. The receipt's C4 residual $4.056\times10^{-11}$ passes the executed $10^{-9}$ Boolean and fails the registered $10^{-12}$ threshold; the source gate now matches the registration and no rerun is introduced. | **INCONCLUSIVE parent certificate; phase-only gap CONTRADICTS; node/link-modulated gap EMERGES CONDITIONAL.** |
| Independent frequency-domain closure | `field-experience/phase-staggered-scale-gap-report.md` | `field-experience/phase-staggered-scale-gap-lock-in-pre-registration.md` | `runs/20260827T093929Z_phase_staggered_scale_gap_lockin/results.json` | All quality and physics gates pass. The sub-gap imbalance decay has $\kappa_{\rm fit}=0.705275510$ and attenuation $3.067\times10^{-6}$; tuned $k_\rho/k_\epsilon=1.618096626$; generic ratio $1.311855471$; valid parent propagating fits agree within $1.319\times10^{-4}$. | **PASS closure; driven additive phase layers EMERGE CONDITIONAL; automatic $\varphi$ selection CONTRADICTS.** |

The combined campaign supports a frequency-supplied, second-order-wave,
additively spaced phase-layer diagnostic. It does not retroactively pass the
parent certificate. Uniform phase staggering supplies no spectral gap, and
the declared link-magnitude modulation remains a conditional control rather
than a PDE-derived node-to-link law. Prediction 51's multiplicative radial
ladder remains `REJECT`.

## 4. Conditional Qi-loop mass-cascade campaign

| record | report | pre-registration | raw receipt | decisive discriminator and feature gates | terminal outcome |
|---|---|---|---|---|---|
| Compact two-fluid ring | `field-experience/qi-loop-mass-cascade-report.md` | `field-experience/qi-loop-mass-cascade-pre-registration.md` | `runs/20260827T120451Z_qi_loop_mass_cascade/results.json`<br>`runs/20260827T120451Z_qi_loop_mass_cascade/verification.json` | Q1–Q5 pass; A/B pass for Fibonacci near closure, positive radial/phase Hessians, stationary nonzero currents, and supplied tension covariance. C3/C4 pass with $1.060031841522592\times10^{-6}$ ratio residual and $2.578928547167112\times10^{-6}$ rung-label residual. C1 finds 1,163 stable primitive modes and C2 has $0.1146965060733196$ rung constitutive span against the $0.01$ gate. | **Closed Qi-loop skeleton EMERGES CONDITIONAL; unique mass positions DO NOT EMERGE.** |

The compact phases, ring topology, normalized coefficients, and tension law
are supplied test architecture. The record retains the canonical scalar
coherence diagnostic $q$ and uses $q_{\mathrm w}$ only for the integer Yin
winding. It provides no open-space binding, topology-formation, or
particle-identification result.

### 4.1 Three-dimensional toroidal survival campaign

| record | report | pre-registration | raw receipt | decisive discriminator and feature gates | terminal outcome |
|---|---|---|---|---|---|
| V1 toroidal double helix | `field-experience/toroidal-coherence-survival-report.md` | `field-experience/toroidal-coherence-survival-pre-registration.md` | `runs/20260831T205711Z_toroidal_coherence_survival/results.json` | G1, G2, and G4 pass. G3 fails because the seeded closed helical order is `0.670671820640564` against the frozen `0.80` floor. The frozen V1 verifier does not handle the preflight-only receipt and reaches `KeyError: 'arms'`. | **INCONCLUSIVE—INVALID INITIALIZATION; no arm evolved.** |
| V2 separated-strand initialization | `field-experience/toroidal-coherence-survival-report.md` | `field-experience/toroidal-coherence-survival-v2-pre-registration.md` | `runs/20260831T210445Z_toroidal_coherence_survival_v2/results.json`<br>`runs/20260831T210445Z_toroidal_coherence_survival_v2/verification.json` | Independent verification passes and reproduces G1/G3/G4 pass with G2 fail. Helical order is `0.8272420763969421`; the Yang/Yin 64-sector coherence floors are `0.1700311303138733` and `0.17034706473350525` against the frozen `0.20` floor. | **INCONCLUSIVE—INVALID INITIALIZATION; no arm evolved.** |
| V3 normalized-phase diagnostic | `field-experience/toroidal-coherence-survival-report.md` | `field-experience/toroidal-coherence-survival-v3-pre-registration.md` | `runs/20260831T214821Z_toroidal_coherence_survival_v3/results.json`<br>`runs/20260831T214821Z_toroidal_coherence_survival_v3/verification.json` | G1–G4 and Q1 pass. Q2 fails on arm J mass drift; Q3 fails on arms E/F energy drift; Q4 fails time-step opposition agreement; Q5 fails resolution agreement. The verifier reproduces those gates and the terminal verdict but returns `pass: false` on raw-metric comparison. | **INCONCLUSIVE—NUMERICAL QUALITY; verification-invalid.** |
| V4 complex128 convergence | `field-experience/toroidal-coherence-survival-report.md` | `field-experience/toroidal-coherence-survival-v4-pre-registration.md` | `runs/20260831T220853Z_toroidal_coherence_survival_v4/results.json`<br>`runs/20260831T220853Z_toroidal_coherence_survival_v4/verification.json` | G1–G4, Q1, Q2, and Q4 pass. Q3 fails on the spherical control's `0.013280009933384629` energy drift; Q5 fails on a `0.387179711030671` opposition difference while radius, core fraction, helical order, windings, and survival directions agree. The verifier reproduces the gates and verdict but returns `pass: false`; the primary diagnostic inherits a float32 kinetic-energy accumulator and exceeds its frozen comparison tolerance. | **INCONCLUSIVE—NUMERICAL QUALITY; verification-invalid.** |
| V5 fourth-order diagnostic precision | `field-experience/toroidal-coherence-survival-report.md` | `field-experience/toroidal-coherence-survival-v5-pre-registration.md` | `runs/20260831T223517Z_toroidal_coherence_survival_v5/results.json`<br>`runs/20260831T223517Z_toroidal_coherence_survival_v5/verification.json` | G1–G4 and Q1–Q5 pass. Maximum energy drift is `0.00026232696068808405`; Q5 radius, core, helical-order, opposed-moment, winding, and survival-direction comparisons pass. S1–S3 fail with Yang winding `+3`, radius ratio `0.4468592782418393`, helical-order retention `0.3459793652013782`, and opposition `0.5518768949443402`. The independent verifier returns `pass: true`, no errors, and maximum normalized metric discrepancy `3.65019126036259e-12`. | **DOES NOT EMERGE; independently verified.** |

V3 and V4 supply complete matrices whose numerical-quality or independent
verification gates fail. V5 closes G1–G4 and Q1–Q5, passes independent
verification, and adopts the finite-time result that the supplied toroidal
double-helix seed does not survive to `t=4`. Its perturbation arm also fails
S1–S3.

### 4.2 Single-domain spectral-transfer diagnosis

| record | report | pre-registration | raw receipt | decisive discriminator and feature gates | terminal outcome |
|---|---|---|---|---|---|
| V5 frozen-field spectral diagnosis | `field-experience/toroidal-multiscale-transfer-report.md` | `field-experience/toroidal-multiscale-transfer-pre-registration.md` | `runs/20260831T232039Z_toroidal_multiscale_transfer/transfer.json`<br>`runs/20260831T232039Z_toroidal_multiscale_transfer/verification.json` | Q1 and Q2 pass. Primary arm A increases its fine modal-mass fraction by `0.4700353507626928` and fine kinetic fraction by `0.7565406294842472`; no-gravity arm B preserves both to floating precision. Q3 fails on the near-zero-activity relative transfer residual `0.9327716406897517`; Q4 fails on arm-I interval error `0.08064316330185473`; Q5 fails only on arm-I integrated flux, while endpoint mass, kinetic, and binding changes converge. The verifier reproduces all gates and the verdict but returns `pass: false` on one ill-conditioned arm-I transfer-conservation comparison. | **INCONCLUSIVE—DIAGNOSTIC QUALITY; verification-invalid.** |

The endpoint redistribution is a measured property of one periodic domain and
one physical hierarchy level. It supplies no independently evolving core,
outer environment, boundary exchange, or connected hierarchy.

### 4.3 Connected three-scale hierarchy campaign

| record | report | pre-registration | raw receipt | decisive discriminator and feature gates | terminal outcome |
|---|---|---|---|---|---|
| core–loop–envelope gravitational graph | `field-experience/toroidal-connected-hierarchy-report.md` | `field-experience/toroidal-connected-hierarchy-pre-registration.md` | `runs/20260831T233830Z_toroidal_connected_hierarchy/results.json`<br>`runs/20260831T233830Z_toroidal_connected_hierarchy/verification.json` | G1–G4 and Q1–Q5 pass. Full arm A has exchange amplitude `1.2025553100905404`; the identical-seed decoupled arm has `1.1863354081760941e-9`; the loop-disconnected control changes loop energy by `-1.465542789391465e-12` and reproduces its final fields exactly. The nearest-neighbor graph differs from full by `0.41492254499549075` in exchange amplitude and fails its frozen sufficiency limit. The independent re-evolution verifier returns `pass: true` with no errors. | **EMERGES—CONNECTED SCALE-ENERGY REDISTRIBUTION.** Secondary labels: **CONTRADICTS NEAREST-NEIGHBOR SUFFICIENCY** and **INCONCLUSIVE—MIXED LOOP RESPONSE**. |

This campaign supplies three labeled scale species on one periodic grid. It
establishes graph-mediated energy redistribution within that declared
multicomponent system. Endogenous scale formation, mass conversion among
levels, nested-domain exchange, and a preferred scale spacing remain open.

## 5. Present-state synthesis

The six-wave counterflow/source-only chain, phase-gap campaign, Qi-loop
campaign, and toroidal campaigns use distinct model boundaries. The first
evolves canonical first-order nonnegative densities. The second uses the
default second-order CassiCosmos wave equation and its derived
density/imbalance normal modes. The third evaluates a supplied compact
Hamiltonian. Toroidal V5 declares a supplied two-component complex
Schrödinger–Poisson evolution and gives a verified finite-time negative for
its seed. The frozen-field diagnosis measures fine-mode endpoint
redistribution and remains `INCONCLUSIVE—DIAGNOSTIC QUALITY`. The connected
extension evolves three labeled scale pairs through a supplied symmetric
gravitational graph and returns
`EMERGES—CONNECTED SCALE-ENERGY REDISTRIBUTION`. It does not define an
endogenous or canonical hierarchy.

### 5.1 Counterflow/source-only synthesis

At the field level, the unmodified canonical PDE evolves two nonnegative real densities, $E_Y$ and $E_I$. The probes form the derived amplitude pair $A=\sqrt{E_Y}$ and $B=\sqrt{E_I}$ for externally supplied bounded amplitude-space $SO(2)$ interventions and for projection-free receiver readouts. Those phase kicks are experimental constructions, and receiver labels, checkerboard corridors, source/probe masks, and carrier signs are supplied protocol coordinates or local diagnostics. They do not define a canonical compact phase or a transport law. The density-plane diagnostic $\mathbf J_d$ is also distinct from the amplitude current $\mathbf J_\Psi$ and has no transport interpretation without a constitutive law.

The chain does establish working bounded-intervention and receiver infrastructure: exact-norm kick construction, pointwise $\rho$ preservation, global-mass checks, positivity-wedge checks, matched-schedule replay, read-only unmodified-canonical-step identity, disjoint source/receiver support, paired $+/-$ cancellation, and field-space receiver traces all pass in the valid runs that use them. The Wave 3 and Wave 4 carrier-sensitive records support imposed-carrier/readout correlations where the reports register them: target-local coherence reaches $0.99459$ and diagonal-receiver coherence reaches $0.99454$, while the spatial, route, phase-arrangement, and counterflow controls do not produce the corresponding feature support. These values do not demonstrate endogenous phase-address selection.

The six-wave chain leaves a canonical four-channel state, a compact phase, route-specific counterflow transport, and delayed diagonal timing unestablished. Wave 5's passive diagonal score is conditioned by its direct-receiver denominator and is not route evidence; Wave 6 formally **CONTRADICTS** its delayed-diagonal timing branch with equal $k_{50}$, $p_D<p_A$, and unchanged shuffled timing. A detectable passive or field-space diagonal response is a finite-proxy observation under supplied operators; it is not evidence of a selected physical edge, finite-speed arrival, a self-maintaining macro-spiral, biological circulation, neural action, or consciousness.

## 6. Next-test boundary

A further transport or timing claim requires a fresh pre-registration rather than relabeling any receipt above. The next construction should keep the source pulse compact and the receiver unforced with exactly disjoint source/receiver support, retain amplitude information in a source-normalized delayed statistic, report direct-calibration denominator conditioning explicitly, and report the immediate FFT/global contribution separately from the post-step dynamic rise. Equal-distance axial, spatially scrambled, and phase-label-shuffled controls must be frozen before execution. Receiver coherence under a distributed supplied drive, direct-receiver calibration fractions, and equal diagonal/axial timing cannot be promoted into route selection or delayed transport without that new discriminator.

Any result would remain a statement about the specified finite index-lattice proxy and the unmodified canonical PDE after supplied interventions. It would not by itself supply a canonical compact phase, a four-channel state, or a biological transport interpretation.

For the phase-layer mechanism, a new experiment requires either a source or
cavity law that selects
$\Omega_*=\varphi^{3/2}\omega_{0,\mathrm{wave}}$, or a constitutive law that
maps destructive nodes into coupling-magnitude modulation. Each proposal
requires its own frozen source law and control arms. The existing receipts do
not authorize either mechanism.

For the compact-loop branch, the three-dimensional V5 campaign closes its
numerical-quality and independent-verification gates and finds that the
declared toroidal seed unwinds, contracts in radius, and loses helical order
by `t=4`. A further spatial-loop claim requires a separately preregistered
seed, coupling, formation mechanism, or field equation with its own controls;
the V5 result remains the terminal classification for the tested realization.
Endogenous topology formation and a mode- or coefficient-selection
discriminator remain required for a physical matter claim.

## 7. Navier–Stokes transfer and stress geometry

The original unforced incompressible equation admits exact stress and critical-norm transfer identities. Fixed smooth initial-data controls test local geometric preservation under the protocol `computations/navier_stokes_stress_geometry_prereg.md`.

| Control | Mathematical record | Raw receipt | Decisive result | Classification and scope |
|---|---|---|---|---|
| Critical transfer and heat correction | `turbulence/navier-stokes-transfer-boundary.md` | `runs/navier_stokes_transfer/verification.json` | All 48 exact checks pass; the quartic remainder has both signs, and an unbounded critical-norm family lies on one corrected-energy level set. | Algebraic **PASS**; arbitrary-data regularity unresolved |
| Pointwise stress isotropy | `turbulence/navier-stokes-stress-geometry.md` §7 | `runs/navier_stokes_stress_geometry/verification.json` | Nine grid/width combinations reproduce $\tau=T I$, $\Pi_\ell=0$, and $\partial_t\Pi_\ell=3Tg^2>0$ at the origin; maximum discrepancy $1.721\times10^{-15}$; minimum derivative $0.02746424201457126$. | **CONTRADICTS** preservation and continued transfer suppression from pointwise isotropy alone |
| Prescribed helix deformation | `turbulence/navier-stokes-stress-geometry.md` §5 | `runs/navier_stokes_stress_geometry/verification.json` | Under the fixed affine strain, the stretching coefficient crosses from $-1/5$ to positive, with zero at $t=\log2/3$. | **CONTRADICTS** sustained protection from the supplied helix shape alone under this deformation |
| Admissible surrounding strain and rescaling | `turbulence/navier-stokes-stress-geometry.md` §§6–7 | `runs/navier_stokes_stress_geometry/verification.json` | The compact curl-potential preserves local vorticity while adding arbitrary symmetric trace-free strain; the Gaussian all-scale norm has exact critical scaling. | Algebraic **PASS**; local vorticity geometry supplies no unique local strain |
| Near-rank full-3D covariance recovery | `turbulence/navier-stokes-near-rank-recovery-obstruction.md` under `computations/navier-stokes-near-rank-recovery-obstruction-prereg.md` | `runs/navier_stokes_near_rank_recovery_obstruction_post_source_cleanup_20260913/verification.json` | 7 of 7 checks pass: the exact determinant polynomial and one-quarter production hold, the declared family has full-rank source, $A_\varepsilon\sim A_*\varepsilon^{2/3}$, and the recovery-only coefficient grows by $102.0867$ across the fixed epsilon set. | **CONTRADICTS** a finite recovery-only coefficient over the bounded family; production-relative occupation control and arbitrary-data regularity remain **UNRESOLVED** |
| Independent long-horizon signed-mode audit | `turbulence/navier-stokes-replica-coherence.md` §7.5; `computations/navier-stokes-galerkin-long-trajectory-audit-prereg.md` | `runs/navier_stokes_galerkin_long_trajectory_audit_20260914/verification.json` | All 10 checks pass: full signed-mode reconstruction, orthogonal Leray projection, direct convolution, alias-free $M=9/13$ products, four $N=2$ production-row reproductions, timestep refinement and a finite $N=2$ versus $N=4$ truncation witness. | `SUPPORTS—independent finite-mode reproducibility diagnostic only`; the cutoff-uniform estimate, production-relative compensation and arbitrary-data regularity remain **UNESTABLISHED** |

All 37 checks in the stress-geometry receipt pass. The isotropy control is pointwise at the initial origin; the affine helix is a prescribed kinematic deformation. These results do not classify every nonlocal or time-integrated geometric condition. The stress, strain, and pressure equations still require a data-controlled all-scale production estimate for an arbitrary-data regularity argument. No Cassi current-to-momentum constitutive map is supplied.

## 8. Fine-scale Navier–Stokes transfer dynamics

The fixed calculation measures the averaged fine-scale transfer and its instantaneous derivative while retaining all modes in the original equation. The Gaussian split changes only the strain factor in the full stress contraction. Its mathematical record is `turbulence/navier-stokes-depletion-dynamics.md`, under `computations/navier-stokes-depletion-prereg.md`; the accepted receipt is `runs/navier_stokes_depletion/qualified_v2/verification.json`.

| Control | Decisive result | Classification and scope |
|---|---|---|
| Zero-transfer cyclic field | $F_f(0)=0$ and $D F_f[B]=(1-e^{-L^2/2})3(\sqrt2-1)/4>0$; the derivative is $0.1222352528$ at $L=1$. | **CONTRADICTS** automatic nonpositive instantaneous response at zero fine transfer |
| Cyclic and planar responses | The fixed rows contain both signs; the planar value at $L=2$ is $-0.2995901414$. | **SUPPORTS** two-sided instantaneous nonlinear response in this control class |
| Fixed multiscale absorption | At amplitude eight, $L=2$ and $\nu=0.01$, $(F_f-\nu Y/2)/\mathcal C=0.029379280637034728>0$. | **CONTRADICTS** viscous-only absorption with the specified $\theta=1/2$ |

All 1,012 checks pass, including 108 spatial rows, 72 quadrature rows, finite values on all 48 absorption rows and a nonempty finite-comparison qualification. The maximum normalized discrepancy is $8.0993\times10^{-15}$ against $10^{-10}$. The current protocol, verifier and retained Fourier helper match the input manifest and source snapshots. These are instantaneous controls; the cyclic field's critical norm initially decreases under viscosity. No time-evolved turbulence or continuum-regularity result is asserted.

Data-controlled cumulative depletion and arbitrary-data regularity remain **UNRESOLVED**. This literal protocol status is a scope limitation, separate from the three measured classifications. The coarse coefficient is bounded by kinetic energy at fixed $L$; no data-controlled time integral for the remaining fine production is established.

The frozen §§44–50 matter comparison retains the distinct constraints behind loaded-core modulation and unwound fixed-population binding. The separate applicability note in `turbulence/navier-stokes-depletion-dynamics.md` §7.4 discusses `computations/matter-formation-continuum-report.md` §37 outside that frozen sourcing. Its conditional linear exterior-response bounds supply no numerical bound on the NS nonlinear forcing.

## 9. Quantitative strain departure

The original Navier–Stokes kinetic-energy and strain-enstrophy budgets give a coupled departure-or-breakdown deadline strictly earlier than Miller's stated energy bound. The analytical proof and its assumptions are in `turbulence/navier-stokes-strain-departure.md`; the fixed verification schedule is `computations/navier-stokes-strain-departure-prereg.md`.

| Control | Decisive result | Qualification and scope |
|---|---|---|
| Projected remainder and budgets | $f'=-3\delta/2$, $E'=f+\nu G$, $K'=-2\nu E$; the coupled comparison derivative is nonnegative while $\delta\le0$. | Algebraic **PASS**; continuum consequence requires the stated smoothness and positive initial amplification |
| Axisymmetric Gaussian moments | $K_v=7\sqrt2\pi^{3/2}/64$, $E_v=9K_v$, $G_v=99K_v$, $-\int\det S_v=8\pi^{3/2}/(81\sqrt3)$. | Exact and independent cylindrical-quadrature **PASS** |
| Deadline quadrature | At amplitude multipliers two and four, $T_{\mathrm{cmp}}/T_*=0.759491556930$ and $0.794430224779$. | Numerical **PASS**; initial perturbative condition **NOT_EVALUATED** for these fixtures |
| Cumulative defect identity | The integrated squared-norm excess is necessary for smooth survival; the analytical corollary gives $\int_0^{K_0/(3\nu E_0)}\delta_+\,dt>2f_0/3$. | Identity **PASS**; necessary lower bound conditional on smooth survival, with no critical-work upper estimate |

All **71 checks pass** with maximum normalized discrepancy $9.633333680505873\times10^{-15}$ against $10^{-10}$. The accepted receipt is `runs/navier_stokes_strain_departure/qualified/verification.json`; its manifest, source snapshots and executable inputs agree. The root-level `runs/navier_stokes_strain_departure/verification.json` is a retained **FAIL** diagnostic with two viscosity-normalization check failures and is excluded from qualification.

Known global regularity removes the breakdown alternative for axisymmetric, swirl-free data. The nonempty class with an initial perturbative window comes from Miller's Proposition 6.2 and Remark 6.5. No Navier–Stokes trajectory or observed exit time is recorded by these departure controls. Data-controlled critical work, bounds under symmetry-breaking perturbations and arbitrary-data regularity remain **UNRESOLVED**.

## 10. Critical remainder and recurrence

Spectral spread bounds the critical work left by enstrophy cancellation. The analytical derivations in `turbulence/navier-stokes-strain-departure.md` §6 give $|W|^2\le(\mathcal V/E)\|\mathcal R\|_2^2$ and the complete-transfer estimate $|F|\le c_{\rm S}\sqrt{\eta\mathcal C}\,Y$, where $\mathcal V=KE-\mathcal C^2/4$ and $\eta=\mathcal V/(KE)$. They also give the exact spread dissipation $\mathcal Q=2KG+2E^2-\mathcal C Y\ge0$ and centered production $\mathscr P_{\mathcal V}=KA-\mathcal C F$. The sharp moment bounds $\mathcal Q\ge2\eta E^2$ and $\mathcal Q\ge\eta\mathcal C Y/2$ convert finite $\int(\mathscr P_{\mathcal V})_+dt$ into Prodi–Serrin continuation. A finite initial-$H^3$-controlled bound on that cumulative production remains open.

The fixed schedule is `computations/navier-stokes-critical-recurrence-prereg.md`. Its **134 checks pass**, with **24 exact velocity rows**, **48 independent FFT rows**, and maximum normalized discrepancy $1.0766942892814768\times10^{-12}$ against $10^{-10}$.

| Control | Decisive result | Frozen classification and scope |
|---|---|---|
| Zero spectral spread | For the cyclic periodic datum, $\mathcal V(0)=\mathcal V'(0)=0$ and $\mathcal V''(0)=9a^6(3-2\sqrt2)/16>0$. | **CONTRADICTS** universal preservation of zero spread on the torus; no exclusion of quantitatively controlled spread |
| Departure and critical growth | No fixed velocity row has $\delta>0$. | **INCONCLUSIVE** for the universal implication $\delta>0\Rightarrow\mathcal C'\le0$ |
| Scalar-budget closure | The fixed positive-moment construction has $\int_0^1E\,dt=4$, $\delta>0$, $f<0$ and $\mathcal C\to\infty$. | **CONTRADICTS** closure from only the listed scalar identities; no Navier–Stokes trajectory or singularity |

One velocity control has $f=-107.52$, $\mathcal C'=15.2427056401649\ldots>0$ and declining $\mathcal V$. Its $\delta=-53287.808$ distinguishes a negative amplification functional from positive departure. This is an instantaneous full-equation calculation.

The accepted receipt is `runs/navier_stokes_critical_recurrence/verification.json`, schema `cassi.navier-stokes.critical-recurrence.verification.v1`, with adjacent input manifest and frozen sources. All four source identities match current executable inputs and snapshots. The known Laplacian interpolation-deficit criterion diverges on the scalar construction. The Sobolev continuation estimates are analytical proofs separate from the finite checks. Initial-$H^3$ control of cumulative positive spread production, recurrence control and arbitrary-data regularity remain **UNRESOLVED**.

The independent analytical reconciliation is retained in `runs/navier_stokes_critical_recurrence/reconciliation.json`. Its accepted continuum argument uses $L^4_tL^6_x$ and keeps the critical dissipation $2\nu Y$ distinct from the higher-order enstrophy dissipation.

## 11. Forced Navier–Stokes concentration budgets

Smooth forcing adds explicit source work to the kinetic, strain, critical and spectral-spread budgets. It also modifies the amplification derivative by $-6\langle M,\nabla_{\rm sym}g\rangle$. The analytical derivation in `turbulence/navier-stokes-strain-departure.md` §8 shows how $\|g\|_{\dot H^{-1/2}}$ bounds critical source work and preserves conditional continuation under a uniform spectral margin below viscosity.

The kinetic estimate also bounds accumulated direct critical source work using only initial energy and prescribed force norms. Finite accumulated excess $(F-\kappa\nu Y)_+$ for a fixed $0\le\kappa<1$ suffices for continuation under the same force assumptions. No bound on that nonlinear accumulation is derived. Conditional on the announced construction's full-flow growth-path estimate, its raw parabolic magnification has divergent velocity at a fixed rescaled point and therefore lacks local $C^0$ compactness there. These are analytical consequences; the source construction's correctness remains outside the verification scope.

The fixed controls have **215 passing checks** in both the immutable preregistered run and the separate post-run qualification specified by `computations/navier-stokes-forced-concentration-prereg.md`. Each has **20 exact forced rows**, **40 independent FFT rows**, a forcing-from-rest control and Gaussian moments with 60-digit quadrature. The exact and spatial rows are identical between these records. The qualification explicitly checks all three source-work signs and the maximum-speed scaling of the scaled Gaussian field. Its maximum normalized numerical discrepancy is $7.275957614183426\times10^{-12}$ against $10^{-10}$.

| Control | Decisive result | Frozen classification and scope |
|---|---|---|
| Forced budgets and strain derivative | All source coefficients agree with full-convolution derivatives and independently reconstructed strain dynamics; gradient forcing is removed by pressure projection | **PASS** for the fixed identities |
| Critical source duality | $I_1^2\le Y\|g\|_{\dot H^{-1/2}}^2$ for all fixed rows; source work has both signs | **PASS** for the controls; the continuum estimate has a separate Cauchy–Schwarz proof |
| Forcing from rest | $K'(0)=\mathcal C'(0)=0$, $K''(0)=3/2$, $\mathcal C''(0)=6$ | **PASS** for the prescribed trigonometric source |
| Euclidean Gaussian concentration | $K[U_\ell]\to0$, $\|U_\ell\|_\infty\to\infty$, $\mathcal C[U_\ell]=8\pi/3$ | **CONTRADICTS** the purely kinematic implication that the first two conditions force critical-norm divergence; no PDE trajectory |
| Rescaled smooth source | Force amplitude has factor $\lambda^3$; its critical squared space-time norm equals the original force integral over a shrinking time interval | **PASS** for scaling arithmetic; a nontrivial unforced limit requires additional compactness |

The selected post-run qualification receipt is `runs/navier_stokes_forced_concentration/qualified_v3/verification.json`, schema `cassi.navier-stokes.forced-concentration.verification.v1`, with adjacent input manifest and frozen sources. Its five input identities match the live source and its snapshots. The preregistered evidence remains frozen at `runs/navier_stokes_forced_concentration/verification.json` with its own manifest, snapshots and source identities. No Navier–Stokes trajectory, singularity search or formal-proof build is run. The announced forced construction's correctness is **NOT_AUDITED**. Data-controlled nonlinear critical production, arbitrary-data regularity, a nontrivial blow-up limit and unforced blow-up remain **UNRESOLVED**.

The qualification's accepted analytical statements, exact source identities, evidence lineage and publication boundary are recorded in `runs/navier_stokes_forced_concentration/qualified_v3/reconciliation.json`. The separate preregistered-run analytical record remains `runs/navier_stokes_forced_concentration/reconciliation.json`.

## 12. Cassi fluid feasibility

The bounded derivation in `turbulence/cassi-fluid-feasibility.md` obtains a
conservative momentum flux, pressure and Hamiltonian energy from the ungauged
positive-density first-order action with a supplied carrier mass. Its exactly
proportional common-phase branch is compatible and locally irrotational.
The canonical density equations separately admit a nonnegativity argument
and a constant-reference relative entropy under smooth common incompressible
advection, equal nonnegative diffusivity and nonnegative conversion.
Neither construction supplies a physical positive viscosity or a closed
thermodynamic identification of the irreversible conversion.

The frozen schedule in `computations/cassi-fluid-feasibility-prereg.md` passes
**246 checks**, including **49 symbolic checks** and **28 native CPU float64
RK2 trajectories**. At $N=16,24$, the flow endpoints agree with exact solutions
or an independent two-thirds-dealiased RK4 reference. The maximum endpoint
error across all 28 trajectories is $1.0078716821608566\times10^{-7}$ against
$2\times10^{-6}$; maximum recorded divergence is
$4.8742777124526794\times10^{-15}$ against $10^{-10}$.
The three-dimensional Taylor–Green control runs to $T=0.05$ and measures local
vortex stretching, nonlinear velocity change and a generated vertical
velocity. This short-time comparison supplies no continuum regularity result.

| Control | Decisive result | Frozen classification and scope |
|---|---|---|
| First-order action reduction and scalar budgets | Pressure, quantum/counterflow momentum flux, energy split, reaction and entropy identities pass | **PASS** for fixed algebra; continuum positivity and entropy retain their analytical assumptions |
| Native periodic force | $\rho=4+\cos x$, $\pi=\sin x$ give projected mean acceleration $\tfrac12 e_x$ without external forcing; $u(t)=\tfrac12t\,e_x$ is reproduced | **CONTRADICTS** closed-fluid internal momentum interpretation |
| Expanding weak-force attenuation | The same positive datum retains nonzero mean acceleration with the fixed attenuation enabled | **CONTRADICTS** restoration of closed-fluid momentum by this factor |
| Ordinary-fluid controls | Decaying shear, two-dimensional Taylor–Green, prescribed forced shear and short-time three-dimensional Taylor–Green agree with their independent references when native self-sourcing is absent | **PASS** for the conditional solver correspondence |
| Density floor | An unforced homogeneous $(Y,I)=(10^{-4},1)$ state changes composition under the expanding step's floor/renormalization while preserving the density sum | **PASS** for recording the numerical intervention; no continuum positivity proof |
| Physical replacement promotion | Closed native force/energy, physical viscosity, normalization and rotational limit remain absent | **REJECT** under the bounded feasibility stopping rule |
| Concentration arrest | No arrest trajectory is run | **NOT_RUN** |

The accepted receipt is
`runs/cassi_fluid_feasibility/qualified/verification.json`, schema
`cassi.fluid-feasibility.verification.v1`, with adjacent input manifest,
frozen sources and `verification.trajectories.npz`.
All seven current input, manifest and snapshot identities match.
Independent reconstruction from the raw arrays recovers all 28 recorded
energies, enstrophies and mean velocities with maximum scalar discrepancy
$1.3322676295501878\times10^{-15}$ and independently reproduces the force means.
The reconciliation is
`runs/cassi_fluid_feasibility/qualified/reconciliation.json`.
The diagnostic `runs/cassi_fluid_feasibility/verification.json` has
**ERROR** status from the harness's missing lowercase coordinate attribute;
its 49 symbolic checks and zero trajectories are excluded from qualification.
The qualified run uses the same frozen protocol, native solver, numerical
fixtures, timestep schedule and tolerances.

## 13. Cassi reacting capillary and thermal fluid

The selected constant-density model in `turbulence/cassi-fluid-feasibility.md`
§7 turns composition-gradient energy into an internal capillary stress and
includes explicit viscous/conversion heating. Its smooth-solution identities
conserve periodic momentum and total energy and produce nonnegative entropy.
Uniform composition follows canonical gated conversion exactly. The
rotational velocity, thermal coefficients and mobility remain declared
constitutive inputs.

The fixed schedule in `computations/cassi-fluid-thermodynamics-prereg.md`
passes **395 checks**, including **12 symbolic identities** and **27 model
trajectories**: six homogeneous-conversion, four shear/heating, four
conduction, four stationary, six coupled three-dimensional, two conservative
capillary-release and one Galilean-boosted evolution. The final time is
$0.2$, with $N=9,15,21$ and the frozen timestep comparisons. A separate
$N=9$ differentiation-matrix/DOP853 reference agrees with the FFT endpoint
to normalized error $2.05688118885\times10^{-15}$.

| Measurement | Result | Classification and scope |
|---|---|---|
| Finest coupled total-energy budget | Maximum drift $4.44089209850\times10^{-16}$ | **PASS**, finite-grid short-time control |
| Finest coupled entropy budget | Increase $4.79447108161\times10^{-4}$; balance-error magnitude $5.62572826865\times10^{-11}$ | **PASS**, declared entropy and trapezoidal production integral |
| Capillary release from rest | Kinetic gain $9.02950778978\times10^{-10}$; exchange defect $2.16840434497\times10^{-19}$ | **PASS**, resolved transfer from composition energy with $\eta=k_T=\lambda=0$ |
| Galilean covariance | Normalized endpoint discrepancy $4.52221248898\times10^{-10}$ | **PASS**, translated reference |
| Sampled state domain | All 27 histories retain $0<c<1$, $T>0$ | **PASS**, distinct from the conditional continuum positivity proof |
| Selected constitutive budgets | Exact mechanical/thermal identities and all fixed controls pass | **SUPPORTS** |
| Physical-fluid replacement, microscopic viscosity, global regularity | No physical normalization, eliminated-state transport derivation or global smoothness theorem | **UNESTABLISHED** |

The receipt is `runs/cassi_fluid_thermodynamics/verification.json`, schema
`cassi.fluid.thermodynamics.verification.v1`, with its adjacent input manifest,
six frozen source files and `verification.trajectories.npz`.
The independent `reconciliation.json` validates all six source identities,
the raw archive hash and keys, 54 endpoint records and 2,127 history rows.
Its maximum absolute reconstructed-observable discrepancy is
$2.08166817117\times10^{-17}$. The CLI smoke in `cli-smoke.npz` has the same
endpoint values as the finest coupled run. The native density/Poisson
solver and the separate §12 feasibility decision are unchanged.

The exact-commit reproduction in
`runs/cassi_fluid_thermodynamics/committed_reproduction/` binds all six source
snapshots byte-for-byte to commit `29969d59` and returns the same 395 passing
checks, 27 trajectories and 82 retained arrays, with every array value, check
row, trajectory row and CLI endpoint identical to the accepted receipt. Five
original source blobs are byte-identical to the commit; the
`foundations/cassi-theory-reference.md` snapshot differs solely by CRLF/LF.
The adjacent `git-source-map.json` and `reconciliation.json` record both
hashes and the value-identical results.

## 14. Unforced cumulative mixing

A decaying shear coupled one-way to a third velocity component gives an
exact globally smooth class of the original unforced periodic
Navier–Stokes equation. For
$u_0=\nu N^3(\sin y,0,\sin x)$ and $t_N=1/(2\nu N^2)$, the continuum
comparison in `turbulence/navier-stokes-strain-departure.md` §9 proves
$$
\frac{\mathcal W_{1/2}(t_N)}{\mathcal C(0)}
\ge\frac N{128}-\frac12.
$$
This excludes every finite amplitude-independent coefficient multiplying
initial squared critical norm on a fixed positive time horizon. Each member also
has the finite upper bound
$\mathcal W_{1/2}(T)\le |A|b^2(1-e^{-3\nu T})/(12\nu)$.
Odd Cartesian phase symmetry persists throughout the evolution.

The fixed schedule in `computations/navier-stokes-mixing-budget-prereg.md`
passes **601 checks**. Eight amplitudes use two Fourier cutoffs each;
one zero-shear control brings the total to 17 numerical evolutions.
Forty independent spatial reconstructions include the full momentum
equation and pressure projection. The maximum normalized discrepancy is
$2.2384929847241164\times10^{-11}$ against $10^{-8}$.
The spread-dissipation and production conclusions below are exact analytical
consequences of the same invariant family; no new trajectory was integrated.

| Control | Decisive result | Classification and scope |
|---|---|---|
| Numerical reduction and budgets | All fixed algebraic, trajectory, spatial and heat checks pass | **PASS**, qualified invariant-class Fourier approximations |
| Unit initial critical budget | At $N=256$, analytical ratio $\ge1.5$ and numerical ratio $19.4393794552309$ | **CONTRADICTS**, exact continuum lower bound plus qualified finite trajectory |
| Amplitude-linear critical-transfer bound at fixed $\nu,T>0$ | The continuum lower ratio grows without bound with $N$ | Excluded by the analytical construction |
| Amplitude-linear cumulative spread-dissipation or cumulative positive-production bound at $\nu=1$ | Each cumulative ratio is at least $(N/64-1)/c_{\rm S}^2$, which diverges linearly with $N$ | Excluded by the analytical construction |
| Nonlinear critical-transfer bound within this family | Explicit finite bound from the critical multiplier difference | Derived for the one-way-coupled invariant class |
| Arbitrary-data cumulative production and global regularity | General three-dimensional feedback remains uncontrolled; no finite initial-$H^3$-controlled bound is known | **UNRESOLVED** |
| Singular solution or formal-proof build | Every constructed solution is globally smooth; no formalization is run | **NOT_RUN** |

The receipt is `runs/navier_stokes_mixing_budget/verification.json`,
schema `cassi.navier-stokes.mixing-budget.verification.v1`, with its
adjacent manifest, source snapshots and `verification.trajectories.npz`.
All four source identities and the raw archive hash match.
The separate `runs/navier_stokes_mixing_budget/reconciliation.json`
records the qualified analytical reviews and raw-array audit, including
its executable source and SHA-256. The reproduction command is in
`turbulence/navier-stokes-strain-departure.md` §7.4.
That audit checks 51 arrays, 17,017 sampled states and eight direct
sine-quadrature endpoints without importing the verifier's helpers.
Its 113 comparisons have maximum normalized discrepancy
$5.920390225714912\times10^{-14}$; no additional trajectories are run.
The master physical parameters, numbered questions and empirical
predictions are unchanged.

## 15. Pure Yang–Mills loop closure

The source-free $SU(2)$ lattice comparison in
`foundations/loop-to-bubble-projection-theorem.md` §§9.4–9.9 derives the
electric excitation threshold $3g^2/(2a)$ on girth-four graphs with Gauss
invariance at every vertex. It also shows that identical projective
bubble data can have distinct Wilson magnetic energies. Every fixed
interacting finite box has a positive physical gap; a weak-bare-coupling
uniform estimate and four-dimensional continuum construction remain open.

The fixed schedule in `computations/yang-mills-loop-gap-prereg.md`
passes **66 primary checks** and **11 independent qualification checks**.
Three finite graph enumerations contain $3,11,1013$ admissible spin
labelings and the same electric threshold. Six couplings use three
character cutoffs; the independent two-sided Prüfer solver evaluates
the equivalent Mathieu/Dirichlet problem without a representation cutoff.

| Control | Decisive result | Classification and scope |
|---|---|---|
| Electric loop identities | Casimir sum $3$ in every graph fixture; complete spin-network proof | **SUPPORTS**, regulated source-free electric theory |
| Autonomous projector-only Hamiltonian | Equal projectors give Wilson energies $0,2,4$ at $g=a=1$ | **CONTRADICTS**, exact finite-regulator closure; enlarged effective marginals remain open |
| Interacting square spectrum | All 24 independent energy/gap comparisons pass; maximum normalized discrepancy $3.44777127772\times10^{-12}$ | **SUPPORTS**, isolated-square reduction |
| Character-cutoff convergence | Maximum normalized $64$-versus-$128$ discrepancy $3.71888228001\times10^{-13}$ | **PASS**, fixed six-coupling schedule |
| Radial quadratic form | Maximum discrepancy $6.22335148571\times10^{-14}$ | **PASS**, fixed eight-function matrix controls |
| Full interacting continuum mass gap and Cassi microscopic identification | Weak-bare-coupling uniform estimate and quantum-field construction absent | **UNRESOLVED** |

The qualified raw pair is
`runs/yang_mills_loop_gap/prufer_recovery/primary.json` and
`runs/yang_mills_loop_gap/prufer_recovery/independent.json`, with the
adjacent manifest and three frozen source snapshots. The top-level
`runs/yang_mills_loop_gap/independent.json` preserves the failed
direct special-function evaluation at $g=1/8$; its misordered energies
and negative gap exclude that receipt from qualification.
The Prüfer computation uses the same eigenproblem, couplings, cutoffs
and tolerances. All primary controls are identical across the evaluator
recovery. `runs/yang_mills_loop_gap/reconciliation.json` binds both
receipt pairs and the accepted source identities. The master physical
parameters and empirical prediction catalog are unchanged.

## 16. Pure Yang–Mills connected blocks

The source-free $SU(2)$ lattice Hamiltonian is tested here through fixed
finite geometry, local operator and remainder controls. The proposed
volume-uniform strong-coupling gap and gauge-invariant finite-depth dressing
carry an unresolved analytical status pending the protocol-required reviews
and reconciliation. The finite receipt records these controls; theorem
constants and adoption remain open.

The fixed schedule in `computations/yang-mills-connected-block-prereg.md`
passes **79 primary checks**. The source-bound receipt is
`runs/yang_mills_connected_blocks/current-verification.json`, with its
adjacent manifest and frozen source snapshots. The protocol-required raw
analytical reviews and separate reconciliation receipt are not present in the
current directory, so these finite controls do not by themselves qualify the
theorem application.

| Control | Decisive result | Classification and scope |
|---|---|---|
| Periodic lattice geometry | Sides $4,6,8$ give $192,648,1536$ links and 24 disjoint-link plaquette layers | **SUPPORTS**, fixed finite inventories and coloring |
| Exact local operator identities | 21 matrix cases; maximum absolute discrepancy $4.97379915032\times10^{-14}$ against $10^{-11}$ | **SUPPORTS**, fixed local rotation and Hamiltonian controls |
| Independent reconstruction | No retained independent receipt or 31-check reconciliation is present in the current directory | **UNAVAILABLE**, primary finite controls only |
| Single-square remainder | Maximum measured $\|R_\square\|/x^2=0.539326266409$; analytic bound $(2+\sqrt2)/3=1.13807118746$ | **SUPPORTS**, fixed points; all-real-$x$ bound follows analytically |
| Volume-uniform interacting gap | Positive theorem gap under $64/g^4\le\beta_{\mathrm Y}$, with symbolic $\beta_{\mathrm Y}>0$ | **UNRESOLVED**, protocol-level analytical review and reconciliation are not currently retained |
| Exact finite-depth dressing | 24 layers, $2^3$ coarse cells, relative coefficient $32|x|/3$ and bounded local remainder $C_Dx^2$ | **UNRESOLVED**, protocol-level analytical review and reconciliation are not currently retained |
| Weak-bare-coupling uniform estimate, continuum theory and mass, Cassi microscopic identification | No construction or bound in these regimes | **UNRESOLVED** |

`runs/yang_mills_connected_blocks/current-verification.json` retains the
source-bound primary arrays, checks and symbolic identities, with its
adjacent input manifest and frozen source snapshots. The expected
`raw_uniform_review.txt`, `raw_dressing_review.txt`, `reconcile.mjs` and
`reconciliation.json` are not present in that directory. Numerical theorem
constants, a critical coupling and continuum masses are unevaluated.
The master physical parameter count and empirical prediction catalog
are unchanged.

## 17. Cassi phase-current hydrodynamics

The phase-bearing first-order action supplies a conditional barycentric
velocity. A normalized Yang/Yin doublet obeys the Mermin–Ho vorticity identity.
An everywhere-positive global chart has exact zero integrated helicity on a
closed domain. A full Hopf doublet crosses component-zero circles and carries
nonzero helicity, while two fixed scale bands realize the periodic Beltrami
field $u=A(\sin z,\cos z,0)$ with positive component populations.

The fixed schedule in `computations/cassi-fluid-phase-current-prereg.md`
passes **227 checks**: 41 exact identities, 83 periodic spatial checks,
three Hopf quadratures, 12 memory checks, 82 independent raw-array
reconstructions and six source-identity checks.

| Control | Decisive result | Classification and scope |
|---|---|---|
| Local doublet vorticity | Periodic shear velocity error $\leq4.44\times10^{-16}$ and curl error $\leq4.18\times10^{-15}$ | **SUPPORTS**, conditional phase-current rotation |
| One positive global chart | Integrated helicity is exactly zero | **CONTRADICTS**, nonzero net helicity in that chart |
| Full Hopf doublet | Helicity $-4\pi^2$ at all three quadrature orders | **SUPPORTS**, topology with component-zero circles |
| Two-band Beltrami field | Velocity error $\leq4.44\times10^{-16}$ and curl error $\leq2.89\times10^{-15}$ | **SUPPORTS**, fixed periodic helical class |
| Fixed-phase scalar diffusion | Evolution error $\leq8.96\times10^{-16}$ with $\partial_tu=D\Delta u$ | **SUPPORTS**, restricted correspondence $\nu=D$ |
| General phase diffusion | Leray-projected commutator norm $0.353553390593274$ | **CONTRADICTS**, general scalar-diffusion/vector-viscosity identification |
| Closed exterior elimination | Kernel recurrence error $7.61\times10^{-34}$ and initial-state derivative split $0.4$ | **CONTRADICTS**, autonomous irreversible finite closed reduction |
| Selected exponential memory | Refinement errors decrease to $8.29\times10^{-5}$ | **SUPPORTS**, mathematical Markov limit; no Cassi-derived coefficient |

The accepted receipt is
`runs/cassi_fluid_phase_current_q1/verification.json`, schema
`cassi.fluid.phase-current.verification.v1`, with its adjacent manifest, six
source snapshots and `verification.arrays.npz`. The archive retains 144 arrays.
The receipt and array hashes are
`a8e8ce036216daca3b60271104f3ab1ec5238b0d33ba585691682cf8fe876f02` and
`435fb7cbd236e06ed81cf6a18ba5329ed5358020f2576bf87ead6d8b6883240c`.

The retained diagnostic at `runs/cassi_fluid_phase_current/verification.json`
records one checker-interface failure from comparing a SymPy zero vector with
scalar zero. The qualified checker tests matrix components. The adjacent
`reconciliation.json` records unchanged equations, fixtures and tolerances;
all 144 arrays and every recorded metric agree with the diagnostic run.

The current-source reproduction at
`runs/cassi_fluid_phase_current_q2/verification.json` also passes all 227
checks. Its receipt hash is
`c69aac6ae0ea7edc9b78f7204b40a2773dcc78b4391410410f90ec3852b65db7`.
The frozen protocol and verifier are unchanged from q1; all 144 arrays are
byte-identical, and every recorded metric and classification agrees. Its
`reconciliation.json` records the six source hashes and the integration-only
changes in the four contextual source documents.
Microscopic positive viscosity, an arbitrary-flow hydrodynamic closure and
arbitrary-data global regularity remain **UNESTABLISHED**. The master physical
parameter count and empirical prediction catalog are unchanged.

## 18. Cassi radiative material closure

The selected radiative-material calculation adds established LTE photon
transfer to the conditional capillary and thermal material. Planck emission,
Kirchhoff detailed balance, piecewise-gray M1 moments, a covariant
matter-radiation source, elastic flux relaxation and the optically thick
diffusion limit define the tested closure. The physical Cassi material map is
outside the calculation.

The frozen comprehensive schedule in
`computations/cassi-radiative-material-prereg.md` records **33 of 34 passing
checks**. It includes symbolic identities, Planck quadrature, physical
emissive-power comparisons, 7,007 M1 tensors, 63 homogeneous slabs, 15 thermal
relaxation trajectories, one stiff source step, 30 scattering controls, 21
diffusion controls, 1,681 photon-entropy pairs and 16 moving-frame source
projections.

| Control | Decisive result | Classification and scope |
|---|---|---|
| Planck and Kirchhoff emission | Planck partition error $1.37\times10^{-16}$; maximum physical emissive-power error $3.96\times10^{-16}$ | **PASS**, supplied LTE photon physics |
| M1 realizability | Maximum trace error $8.88\times10^{-16}$; minimum eigenvalue $-1.86\times10^{-16}$ from roundoff | **PASS**, fixed energy, directions and reduced fluxes |
| Homogeneous slab | Maximum direct error $2.22\times10^{-16}$ and semigroup error $4.44\times10^{-16}$ | **PASS**, constant-source formal solution |
| Thermal exchange | Maximum stored total-energy drift $0$; minimum entropy step $-8.88\times10^{-16}$ | **PASS**, five initial states and three timesteps |
| Elastic scattering and diffusion | Momentum residual $1.11\times10^{-16}$; diffusion residual $1.78\times10^{-15}$ | **PASS**, fixed homogeneous controls |
| Spectral photon entropy | Minimum production integrand $0$ across 1,681 pairs | **PASS**, nonnegative-opacity detailed balance |
| Covariant interaction | Maximum normalized flux orthogonality $8.26\times10^{-16}$; boosted-LTE source $2.34\times10^{-16}$ | **PASS**, fixed velocities and group-gray tensor |
| Comprehensive source accuracy | Finest normalized endpoint error $2.52712195192\times10^{-4}$ at $\Delta t=0.01$, above $5\times10^{-5}$ | **CONTRADICTS**, fixed benchmark timestep |
| Fixed source qualification | Errors decrease to $2.49893979281\times10^{-5}$ at $\Delta t=0.001$ with refinement ratios $2.0050,2.0025$ | **SUPPORTS**, backward-Euler source subcycling for the benchmark |
| Physical Cassi material | Temperature, density, opacity, ionization, current and source energetics remain unsupplied | **UNESTABLISHED** |

The comprehensive receipt is
`runs/cassi_radiative_material/verification.json`, schema
`cassi-radiative-material-verification-v1`, with its adjacent input manifest
and three frozen source snapshots. Its top-level scientific classification is
`CONTRADICTS` because the fixed source-accuracy requirement fails.

The source-step qualification is frozen in
`computations/cassi-radiative-material-qualification-prereg.md`. Its receipt
is `runs/cassi_radiative_material_qualification/verification.json`, schema
`cassi-radiative-material-qualification-v1`, with an adjacent input manifest
and four source snapshots including the comprehensive receipt. It passes all
9 checks, preserves total energy to stored precision, keeps every state
positive and records a positive minimum entropy step. Its scientific
classification is `SUPPORTS-backward-Euler source subcycling`. The model
equation, comprehensive verdict, physical parameter count and empirical
prediction catalog are unchanged by the qualification.


## 19. Pure Yang–Mills exact-vacuum blocks

The source-free $SU(2)$ lattice comparison uses the exact finite-vacuum
measure. The ground-state transform identifies the regulated physical gap
with the gauge-invariant Poincaré rate of that measure. A conditional
full-holonomy block theorem isolates local exact-vacuum rates, an
approximate-tensorization constant and a bounded-overlap cover as sufficient
inputs for uniform control. Weak-bare-coupling bounds for those inputs remain
open.

The immutable schedule in
`computations/yang-mills-vacuum-block-prereg.md` is implemented by
`computations/verify_yang_mills_vacuum_blocks.py`. The source-bound primary
receipt passes **305 checks** over five full-holonomy fixtures, 45 local-energy
rows and ten connected Gaussian rows. The independent Python reconciliation
`computations/reconcile_yang_mills_vacuum_blocks.py` passes **78 checks**,
reconstructs the five fixtures and 45 local-energy rows, and rebuilds the ten
Gaussian rows from the explicit sine basis. Its largest normalized Gaussian
reconstruction discrepancy is $1.81\times10^{-14}$; the largest direct
local-energy difference is zero at the stored precision.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Full-holonomy group, derivative and local-energy controls | Maximum group, gauge, first-derivative and normalized-energy errors are $1.33\times10^{-15}$, $4.44\times10^{-16}$, $6.31\times10^{-13}$ and $3.28\times10^{-8}$ | **SUPPORTS**, fixed finite fixtures and declared local schedule |
| Independent Gaussian reconstruction | The explicit sine-basis reconstruction passes for all ten connected rows; the largest normalized discrepancy is $1.81\times10^{-14}$ | **SUPPORTS**, finite Gaussian controls |
| Exact finite-vacuum identity | The ground-state transform and the displayed gauge-invariant Poincaré formula are the declared finite-regulator identity | **REQUIRES ANALYTICAL RECONCILIATION**, domain and gauge-invariance hypotheses remain part of the proof obligation |
| Full-holonomy block theorem | The displayed tensorization and bounded-overlap assumptions imply the stated sufficient rate | **REQUIRES ANALYTICAL RECONCILIATION**, exact-vacuum fibre rates and uniform constants remain open |
| Equal-weight one-plaquette exponential | The fixed local-energy and same-character controls retain the trial-family obstruction target | **REQUIRES ANALYTICAL RECONCILIATION**, the trial family is not promoted to an interacting-vacuum conclusion |
| Conditional gaps alone | The massless Gaussian sequence has a vanishing global rate while conditional-coordinate rates remain positive | **CONTRADICTS**, a volume-uniform inference from conditional gaps alone |
| Static pure configuration marginal | Coupled Gaussian rows retain a positive discarded momentum term and symplectic eigenvalue above $1/2$ | **CONTRADICTS**, replacing the reduced quantum state by the pure square root of its configuration marginal |
| Weak-coupling continuum mass gap | Uniform exact-vacuum tensorization, local rates, continuum construction and mass identification remain missing | **UNRESOLVED** |

The primary receipt, input manifest and frozen source snapshots are in
`runs/yang_mills_vacuum_blocks_recovery_20260914/verification.json`,
`verification.inputs.json` and `verification.sources/`. The independent
receipt and its source manifest/snapshots are
`verification-independent.json`, `verification-independent.inputs.json` and
`verification-independent.sources/` in the same directory. The receipts bind
the live protocol, primary verifier, shared receipt helper and independent
reconciler by SHA-256. The numerical pair qualifies the finite controls; the
exact-vacuum theorem, interacting tensorization estimate, thermodynamic
limit, continuum construction and physical mass remain open.

## 20. Helical spread and phase-energy coercivity

The signed curl spectrum refines the retained Navier–Stokes radial-spread
analysis by preserving helical polarization. Its $L^2$-optimal scalar
Beltrami residual is

$$
r_B=\omega-\frac{H}{2K}u.
$$

The frozen schedule in
`computations/navier-stokes-helical-spread-prereg.md` is implemented by
`computations/verify_navier_stokes_helical_spread.py`. The retained receipt
`runs/navier_stokes_helical_spread/verification.json` passes all **84
checks**.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Signed moment and pair-spread identities | All exact symbolic residuals vanish; $\mathcal V_B=(K/2)\|r_B\|_2^2\ge0$ and $\mathcal Q_B=E\|r_B\|_2^2+K\|\nabla r_B\|_2^2\ge0$ | **SUPPORTS**, exact smooth-data identities |
| Critical residual continuation | $\int_0^T\|r_B\|_3^2dt<\infty$ gives a finite enstrophy bound | **DERIVED CONDITIONAL REDUCTION**, original Navier–Stokes equation |
| Radial positive-production closure | The same finite critical integral bounds cumulative positive radial-spread production | **DERIVED CONDITIONAL REDUCTION**, closes the earlier conditional hypothesis |
| Beltrami, shear and mixed-helicity triad controls | Exact heat solutions delimit the residual; the triad has $H=J=0$ and $\mathcal A=1/2$ | **SUPPORTS**, exact periodic controls |
| Static first-order positive-doublet coercivity | A smooth one-band family has $\int|\nabla Z_\varepsilon|^2=P_0+\varepsilon P_1$ while $\|\omega_\varepsilon\|_2^2=\kappa_v^2\pi^{3/2}/(128\varepsilon^2)$ and $\|r_{B,\varepsilon}\|_3^2\propto\varepsilon^{-3}$ | **CONTRADICTS**, bounded first-order phase energy does not control the required quantities |
| Arbitrary-data residual bound | No finite initial-data-controlled bound is derived | **UNRESOLVED** |
| Full-bubble dynamical exclusion | Exterior initial correlations and scale-memory remain possible inputs, but no selection or kernel theorem is supplied | **UNRESOLVED** |

No Navier–Stokes trajectory, singular solution or formal-proof build is
produced. The result identifies a critical quantity that the whole-bubble
dynamics would have to control and excludes the current static first-order
phase energy as that control.


## 21. Pure Yang–Mills cylindrical block map

The tracked protocol in
`computations/yang-mills-block-map-prereg.md` and its primary verifier define
the fixed path-holonomy schedule. The source-bound primary receipt in
`runs/yang_mills_block_map_recovery_20260914/verification.json` passes
**53 checks**. The independent Python reconstruction in
`computations/reconcile_yang_mills_block_map.py` passes **9 aggregate checks**
and regenerates the seeded path, electric, genuine-refinement,
pure-subdivision and scale rows without importing the primary verifier. The
largest reconstructed path, electric, refined-block and subdivision errors are
$3.14\times10^{-16}$, $8.88\times10^{-16}$, $4.44\times10^{-16}$ and
$2.37\times10^{-16}$.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Normalized-Haar path pullback | The seeded mixed-orientation paths reconstruct, transform covariantly and cancel internal gauges within $3.14\times10^{-16}$ | **SUPPORTS**, fixed numerical path controls; the general analytical isometry remains a review obligation |
| Electric Casimir compression | Fundamental and adjoint seeded rows reproduce the direct second-derivative compression within $8.88\times10^{-16}$ | **SUPPORTS**, fixed numerical representation controls; the smooth-core statement remains an analytical obligation |
| Genuine $2\times2$ refinement | Four absent-link plaquette characters have zero conditional means, identity Gram matrix and leakage coefficient $2$; the independent Gram discrepancy is $1.11\times10^{-16}$ | **SUPPORTS**, fixed nine-vertex, twelve-link fixture |
| Bare full-Hamiltonian block | The reconstructed dimensionless leakage is $2x_f$ and the physical scale rows reproduce $2/(a_fg_f^2)$ | **REQUIRES ANALYTICAL RECONCILIATION**, exact intertwiner failure is confined to the declared bare map and fixture |
| Pure graph subdivision | The outer face remains unchanged under fibre variation and no elementary face is added | **SUPPORTS**, fixed graph-subdivision control |
| Weak-coupling bare-vacuum shortcut | The fixed diagnostic is $x_f/3=2/(3g_f^4)$ and the scale rows reproduce its divergence pattern | **REQUIRES ANALYTICAL RECONCILIATION**, resolvent-weighted interacting estimates remain outside the receipt |
| Interacting block and continuum mass | No gauge-compatible interacting fibre, generated-term closure, uniform Feshbach-resolvent bound, weak-coupling volume estimate, thermodynamic limit or continuum field is constructed | **UNRESOLVED** |
| Cassi interaction survival | No microscopic Cassi link state, interacting fibre or transfer operator is supplied for this block criterion | **UNRESOLVED** |

The primary receipt, input manifest and frozen source snapshots are in
`runs/yang_mills_block_map_recovery_20260914/`. The accepted independent
receipt is
`verification-independent-repaired.json` with its adjacent manifest and
source snapshots; the directory also retains the first failed independent
receipt as a diagnostic artifact. Both accepted receipts bind the protocol,
primary verifier, shared receipt helper and independent reconciler by
SHA-256. The numerical pair qualifies the declared finite controls. The
interacting fibre, exact cylindrical intertwiner theorem, Feshbach estimate,
thermodynamic limit, continuum construction and physical mass remain open.

## 22. Pure Yang–Mills isolated-square radial Feshbach and character cutoff

The frozen version-3 protocol in
`computations/yang-mills-radial-feshbach-v3-prereg.md` fixes the continuous
$SU(2)$ class-function operator, the exact Schur/Feshbach route, five
character-cutoff schedules and the version-isolation control. Each finite
section requests $q(N)=\min\{3,N+1\}$ low Ritz values; the two scheduled
$N=1$ rows therefore contain levels $0$ and $1$ only. The primary verifier
passes **62 checks**, and the source-independent continuous-angle,
sign-preserving Sturm/bisection, continued-fraction and finite-section
reconstruction passes **20 checks** across 30 cutoff rows and all 88 requested
Ritz values. The
deliberately incompatible version-2 input returns the required `FAIL`. These
receipts qualify the finite numerical controls only. The exact claims and
limits are the analytical results of
`foundations/loop-to-bubble-projection-theorem.md` §§9.18.1–9.18.7; the
receipts retain their analytical-reconciliation fields as `UNRESOLVED`.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Exact radial reduction | Normalized $SU(2)$ characters give a half-line Jacobi operator; the source-independent continuous-angle spectrum reproduces the scheduled low eigenpairs | **ADOPT** as an analytical isolated-square result; **SUPPORTS** for the finite numerical reconstruction |
| Energy-dependent Feshbach transfer | The discarded half-line produces a positive Stieltjes self-energy with exact Schur equivalence, continued-fraction bounds and fixed-window isolation | **ADOPT** analytically at finite cutoff below the tail threshold; the v3 finite controls **SUPPORT** the implemented reconstruction |
| Fixed-level weak-coupling asymptotics | $\lambda_j(h_x)/\sqrt{x}\to4j+3$ for each fixed level; since $\lambda_1-\lambda_0\sim4\sqrt{x}$ and $x=2/g^4$, the first physical spacing tends to $2\sqrt2/a$ | **ADOPT** analytically for the isolated ultraviolet plaquette normalization; continuum mass unresolved |
| Bare character cutoff | Low eigenvalues converge and discarded mass vanishes exactly when $N/x^{1/4}\to\infty$, equivalently $gN\to\infty$ | **ADOPT** analytically for the isolated square; not inferred from finite rows |
| Fixed and finite-scaled schedules | The maximum low-spectrum relative errors are $0.9480003387$ for $N_{\rm fixed}=8$, $0.4780504005$ for $N_C=\lceil2x^{1/4}\rceil$ and $0.0039503578$ for $N_{\rm iso}=\lceil4x^{1/4}\rceil$ on the frozen finite schedule; finite $N/x^{1/4}$ does not give the asymptotic bare limit | **CONTRADICTS** fixed-cutoff and finite-scaled-cutoff bare weak-coupling claims by the theorem; the rows are numerical controls |
| Growing-ratio controls | The `grow` and `half` schedules have maximum frozen-schedule relative error $0.0136990351$ and satisfy the theorem's divergent-ratio condition asymptotically; at $x=1/4$ they retain $N=1$ and request two levels | **SUPPORTS** the finite numerical controls; convergence follows from the theorem |
| Interacting lattice and continuum mass | No gauge-compatible interacting fibre, volume-uniform discarded-sector resolvent bound, thermodynamic limit, four-dimensional continuum field or regulator-independent mass is constructed | **UNRESOLVED** |
| Cassi microscopic identification | No Cassi field variable is identified with the regulated gauge coordinate or its interacting vacuum | **UNRESOLVED** |

Qualified artifacts are in `runs/yang_mills_radial_feshbach_v3/`:
`verification-final.json`, `verification-independent-final.json`,
`v2-rejection-final.json`, the adjacent `verification-final.inputs.json` and
frozen `verification-final.sources/`,
`receipt-audit.json`, `analytical-review-final.json` and `publication.json`.
The audits bind the live source and evidence hashes, check all 30 schedule
rows and 88 reconstructed Ritz values, and preserve the
numerical-versus-analytical scope boundary. The publication seal binds the
theorem, protocol, both verifiers, canonical receipts, audits and public
registries. The result closes the isolated-square radial
operator and cutoff question only; the interacting, volume, thermodynamic,
continuum and Cassi-identification requirements remain open.


## 23. Pure Yang–Mills Poincaré geometry and two-scale recurrence

The frozen v2 protocol in
`computations/yang-mills-poincare-geometry-prereg.md` separates the
round-spatial, fixed-link and interacting-block questions. The primary
verifier passes **118 checks** across exact spectra, Wilson Hessians,
Haar-preserving horizontal transport, conditional-score recurrence and
physical-scaling controls. The implementation-independent JavaScript audit
passes **90 checks**: 84 formula/row reconstructions plus six fixed-tolerance,
per-check, summary and maxima integrity controls. It uses the schedule vectors
and measurements stored in the primary receipt; it is not independent sample
generation or a second scientific execution.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Spatial Poincaré geometry | A closed simply connected spatial three-manifold is topologically $S^3$; the round radius-$R$ regulator has free Maxwell/linearized coexact one-form frequency $2/R$ | **ADOPT** for the stated topology and round regulator; this kinematic frequency is not the interacting Hamiltonian gap and vanishes as $R\to\infty$ |
| Fixed $SU(2)$ link spectrum | In the Casimir metric generated by $i\sigma_A/2$, characters have eigenvalues $n(n+2)/4$ and the first scalar link rate is $3/4$, one quarter of the unit-round scalar value $3$ | **ADOPT** as exact finite-link geometry, distinct from the base coexact spectrum and gauge-quotient rate |
| Wilson-weight pointwise curvature | For the auxiliary one-link concentration $\beta\geq0$, the Bakry–Émery lower bound is $(2-\beta)/4$ | **CONTRADICTS** extension of this pointwise proof through $\beta=2$; no identification of $\beta$ with the Hamiltonian coupling, $x=2/g^4$, or an exact vacuum conditional measure is supplied |
| Haar-preserving path block | The factor-two change of variables has orthogonal horizontal and fibre directions, Jacobian one and exact electric coefficients $2$ and $1/2$ | **ADOPT** as exact regulated geometry |
| Interacting conditional-score recurrence | Exact vacuum disintegration gives the all-function bound $\lambda_f\geq C_*^{-1}$ with $C_*$ determined by $\lambda_c$, $\lambda_{\mathrm{fib}}$ and the transported score covariance $\kappa$; the physical rate obeys $\lambda_{\mathrm{gi}}\geq\lambda_f$ | **ADOPT** as a conditional Poincaré theorem retaining every interaction generated by marginalization |
| Zero-score induction | At $\kappa=0$, $\lambda_f\geq\min\{2\lambda_c,\lambda_{\mathrm{fib}}/2\}$; at the physical factor-two target, nonzero score requires a strict coarse-rate margin when $\lambda_c$ saturates its target | **ADOPT** as the exact induction criterion; no uniform weak-coupling margin is established |
| Frozen finite controls | The primary and implementation-independent receipts pass 118/118 and 90/90 checks with maximum recorded errors below the fixed protocol tolerances | **SUPPORTS** the implementation, normalization and receipt-integrity controls; the second verifier reuses the primary schedule, and no sampled row establishes a uniform analytical estimate |
| Continuum Yang–Mills and Cassi identification | No scale-uniform fibre-rate, transported-score, coarse-margin or thermodynamic/continuum construction is supplied, and no Cassi variable is identified with the gauge field | **UNRESOLVED** |

The qualified receipts are
`runs/yang_mills_poincare_geometry/verification.json` and
`runs/yang_mills_poincare_geometry/verification-independent.json`. They bind their tracked protocol and source
hashes. The result identifies the exact generated-interaction term and the
three estimates a successful weak-coupling induction must control; it does
not establish continuum Yang–Mills existence or a regulator-independent mass
gap.


## 24. Pure Yang–Mills conditional transport score

The frozen v4 protocol
`computations/yang-mills-transport-score-prereg.md` replaces the
$L^2$ transported-score relaxation by the exact conditional $H^{-1}$ norm.
The source-bound Python verifier passes **86 checks**. The independent
JavaScript implementation reconstructs the fixed matrices from the
discrete-sine basis with separate Jacobi and pivoted-solve algorithms and
passes **32 checks**.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Conditional Poisson transport | $\vartheta^2=\operatorname*{ess\,sup}_{V,|\xi|=1}\langle s_{V,\xi},\mathcal L_V^{-1}s_{V,\xi}\rangle$ is the minimum kinetic cost over $-\operatorname{div}_{\nu_V}u=s_{V,\xi}$ | **ADOPT** as a conditional finite-regulator identity on the stated connected form domains |
| Sharpened recurrence | $\lambda_f\geq C_{-1}^{-1}$ with score coefficient $\vartheta$, and $\vartheta^2\leq\kappa^2/\lambda_{\mathrm{fib}}$ | **ADOPT** as no weaker than the covariance recurrence; an exact-vacuum uniform estimate is absent |
| Physical margin transfer | The recurrence certifies output margin $\delta_f$ exactly when $\delta_c,\delta_v\geq\delta_f$ and $\vartheta^2\leq(\delta_c-\delta_f)(\delta_v-\delta_f)/[4(1+\delta_f)(1+\delta_v)]$ | **ADOPT** as the exact conditional induction budget |
| Strict Gaussian fixture | $\vartheta^2=1/9$ versus $\kappa^2/\lambda_{\mathrm{fib}}=1$; bounds $0.961295942106$ versus $0.737912651870$ against exact rate $1$ | **SUPPORTS** strict inverse-generator improvement in the declared finite Gaussian control |
| Even/odd weak-field chains | All 10 rows have comparison factor one within $7.77156117238\times10^{-16}$ and reproduce the exact anisotropic Gaussian rate within $1.66533453694\times10^{-15}$ | **SUPPORTS** exact reconstruction; the inverse norm gives no gain for this chain family |
| Massless infrared branch | At $N=64$, $(\lambda_c,\lambda_{\mathrm{fib}},\vartheta)=(0.188747776607,2.04774351863,0.952799273901)$; the formal infinite symbol has values $(0,2,1)$ for coarse, fibre and transport quantities | **CONTRADICTS** manufacturing a mass from positive fibre control; the unpinned infinite massless symbol is not a normalizable Gaussian probability |
| Frozen finite controls | The v2 primary and independent receipts pass 86/86 and 32/32; both generalized-eigenvalue reconstructions are checked, and the maximum primary matrix/scalar errors are $5.33638658877\times10^{-15}$ and $2.13450577681\times10^{-16}$ | **PASS** for the fixed implementation and Gaussian controls |
| Interacting Yang–Mills target | No vertical transport field, uniform $H^{-1}$ score bound, exact coarse closure, thermodynamic limit or continuum construction is supplied | **UNRESOLVED** |

The qualified receipts are
`runs/yang_mills_transport_score/verification.json` and
`runs/yang_mills_transport_score/verification-independent.json`. They bind
the frozen protocol and both sources. The protocol and theorem audits are
`runs/yang_mills_transport_score/analytical-review.json` and
`runs/yang_mills_transport_score/theorem-review.json`; both return `VALID`.
The analytical theorem is
`foundations/loop-to-bubble-projection-theorem.md` §9.21. The finite Gaussian
rows test its algebra and scope without establishing the interacting
Yang–Mills estimate.


## 25. Pure Yang–Mills residual recovery and score-penalty separation

The frozen v5 protocol
`computations/yang-mills-recovery-gramian-prereg.md` separates the
physical-function residual Gramian from the transported-score operator on
coarse tangent directions. The source-bound Python verifier passes **58
checks**. The independent JavaScript implementation reconstructs the fixed
matrices with a separate Jacobi eigensolver and sine basis and passes **30
checks**.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Residual Gramian | $\mathscr R=\sum_Bw_BR_B$ and $\sum_Bw_B\mathbb E[\operatorname{Var}(f\mid\mathcal F_B)]=\langle f,\mathscr Rf\rangle$ on the centered physical sector | **ADOPT** as the exact finite-regulator recovery identity |
| Optimal tensorization and local coercivity | $A_{\mathrm{AT}}^{\mathrm{opt}}=\gamma_{\mathrm{rec}}^{-1}$ and $\lambda_{\mathrm{gi}}\geq\gamma_{\mathrm{rec}}\lambda_{\mathrm{loc}}/\rho$ under the declared conditional and cover estimates | **ADOPT** as a conditional Poincaré theorem; all three inputs require uniform interacting-vacuum control |
| Score-penalty separation | The score operator maps coarse tangents to conditional $H^{-1}$ data and its norm lowers the certified recurrence rate; a product Gaussian has zero score and positive global rate | **CONTRADICTS** substitution of a lower score Gramian for physical-function recovery |
| Finite rigidity | Near-parallel rank-one residuals have trivial kernel and floor $1-\cos\epsilon\to0$; the quotient fixture has the declared gauge null and physical floor one | **CONTRADICTS** promotion of qualitative kernel rigidity to a uniform spectral floor |
| Gaussian all-chaos control | The coordinate residual floor is $\lambda_{\min}(D^{-1/2}Q_ND^{-1/2})$ on every chaos and gives the optimal all-function tensorization constant; the massless open-chain floor tends to zero | **ADOPT** for each finite Gaussian chain and **CONTRADICTS** a uniform recovery inference from finite common-kernel rigidity |
| Frozen finite controls | The primary and independent receipts pass 58/58 and 30/30; maximum primary matrix/scalar errors are $5.33638658877\times10^{-15}$ and $1.71390679427\times10^{-15}$ | **PASS** for the fixed implementation, normalization and receipt-integrity controls |
| Interacting Yang–Mills target | No scale-uniform residual floor, score upper bound, local exact-vacuum rate, cover control, thermodynamic limit or continuum construction is supplied | **UNRESOLVED** |

The authoritative receipts are
`runs/yang_mills_recovery_gramian/verification.json` and
`runs/yang_mills_recovery_gramian/verification-independent.json`. The final
checker binds the frozen protocol, both sources and the unchanged primary
receipt. The analytical theorem is
`foundations/loop-to-bubble-projection-theorem.md` §9.22. The finite controls
guard its formulas and scope without establishing the interacting recovery or
score estimates.


## 26. SU(2) strip transport expansion and compact-boundary control

The normalized weak-field strip calculation reproduces the leading
transport cost $\Theta_0^2=1/4$ and the first correction
$c_1=-1/(4\kappa)+[|z|^2-(z\cdot\xi)^2]/64$ on all 48 prescribed
coupling, boundary and tangent combinations. The source-bound Python receipt
passes **150/150 checks**, with maximum coefficient error
$5.55111512313\times10^{-17}$. The independent JavaScript reconstruction
passes **60/60 checks**.

| Claim | Classification and scope |
|---|---|
| Local rescaled strip expansion | **SUPPORTS** the declared leading term and first-order coefficient, including the Wilson, Haar and metric contributions |
| Uniformity over compact boundary holonomies | **REJECT_CHART_UNIFORMITY**: substituting $z=\alpha/\sqrt u$ leaves a nonzero transverse contribution of order one |
| Exact interacting vacuum and continuum gap | **UNRESOLVED**: the finite strip law supplies no boundary-uniform estimate for the exact vacuum or its multiscale recovery operator |

The protocol is `computations/yang-mills-su2-transport-expansion-prereg.md`.
The raw receipts are
`runs/yang_mills_su2_transport_expansion/verification.json` and
`runs/yang_mills_su2_transport_expansion/verification-independent.json`.
Their SHA-256 source and protocol bindings match the tracked files.


## 27. Cutoff finite-lattice conditional block spectrum and boundary independence

The frozen first-target protocol
`computations/yang-mills-exact-block-spectral-prereg.md` projects a truncated
spin-network Ritz ground state of the seven-link two-plaquette graph onto a
full-holonomy block and extracts the conditional Poincaré rate of
$d\mu_J^{\mathrm{Ritz}}=|\Omega_J|^2dU$. The retained primary execution
record `runs/yang_mills_exact_block_spectrum/verification.json` evaluates the
schedule at doubled cutoffs $J=1,\ldots,5$ with the $J=6$ extension for the
endpoint residual, couplings $x=1/4,1,4,16$ and nine boundary angles
$\theta=k\pi/8$.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Gauge-orbit reduction and tree-exterior boundary independence | Every block-integrated conditional moment is a function of the gauge orbit of the exterior data. The exterior links $\{4,5,6\}$ form a tree whose orbit fills the configuration space, so the moments are constant on the scheduled slice: the direct seven-link contraction reproduces the boundary-independent algebra with partition deviation $2.2\times10^{-16}$, Gram $1.6\times10^{-15}$, Dirichlet $3.3\times10^{-15}$ and a spread of $2.2\times10^{-16}$ across the slice. A loop-carrying exterior would leave only its loop holonomies | **ADOPT** as an exact finite-regulator identity; the scheduled boundary axis carries no information about the fibre rate, and the boundary-uniform obligation is quantified over exterior holonomies |
| Nodal Ritz obstruction | At $J=1$, $x=1$ the projected ground vector changes sign on the block, with amplitudes $2.094120531213694$ at the identity configuration and $-0.03437408376157869$ on the inverted first link, so the cutoff density has a nodal set and its unrestricted conditional gap is exactly $0$ while the retained test space reports $0.864465200076$ | **CONTRADICTS** use of the projected Ritz density as a surrogate for the exact-vacuum fibre rate |
| Cutoff-qualified rate rows | At $J=5$ the retained rates are $0.754314828716$, $0.817612505009$, $1.38823233618$ and $0.472769320267$ for $x=1/4,1,4,16$; the two smallest couplings have stabilized between the last two cutoffs to $1.1\times10^{-10}$ and $2.9\times10^{-6}$ | cutoff-qualified finite numbers only; no all-boundary, conditional-rate cutoff-removal or continuum implication |
| Frozen qualification | All 180 scheduled boundary rows classify **INCONCLUSIVE**: the restriction rank grows with the cutoff at every coupling, the literal embedded-minimizer and rate-stability tolerances fail, and the endpoint full-space residual is $7.4\times10^{-2}$ at $x=4$ and $3.12$ at $x=16$ against the $10^{-2}$ bound | **INCONCLUSIVE**: no `SUPPORTS_FINITE_BLOCK` row and no conditional-collapse witness |
| Transport score and continuum target | The transport score lies outside the first implementation target, so no score or margin verdict is issued; conditional-rate cutoff removal, uniform interacting recovery, the thermodynamic limit and the continuum gap stay open | **UNRESOLVED** |

The primary receipt records protocol digest
`a2cf6db4c8a82d69982d2df3b9ebd5673c17705dd092969bb161d365a7285446`, helper
digest `83f6ed011fa467ddfe6cd506f71a1168d85326741c115ae72b3cd90e507a4628`
and embedded primary-source digest
`148461e21a4ff1fe5601a44d3de6c4069bc9012fa1a56d912c01e1c12fc15723`. The
live working-tree verifier source hashes to
`8940ec3bad4b55611e7afba70b5f582bb685c59dc589578fbfdfb87e5382a168`, and
no retained source snapshot matches the embedded digest. The primary raw
receipt hash is
`e1ecf4d54d165dceb00a244de7b1c68b3a43dabb5dd345f63c8f846be9921147`.
The finite payload is therefore an execution record with unresolved source
provenance, not a current source-bound receipt.

The independent output
`runs/yang_mills_exact_block_spectrum/verification-independent.json` has raw
SHA-256
`f4a01fefe85ff195bd9d20e2c273291470a0c526d0b99b50812774184756558b`. It
reconstructs the 20 cutoff rows and passes its self-checks, but its schema
contains no source, protocol or primary-receipt hash fields. It is a
standalone numerical reconstruction rather than a sealed independent
verification. The analytical statements are
`foundations/loop-to-bubble-projection-theorem.md` §9.23. The finite controls
guard the algebra and the declared scope without establishing the interacting
vacuum estimate or UFA32.


## 28. Schedule-wide confinement of the nodal Ritz obstruction

The protocol `computations/yang-mills-nodal-family-prereg.md` specifies a
twelve-row extension of the §27 block-path nodal control. The executable
`computations/verify_yang_mills_nodal_family.py` is retained, but
`runs/yang_mills_nodal_family/verification.json` is absent. No receipt, source
snapshot or current numerical classification is available for this schedule.
The §27 control is an execution record with unresolved source provenance, so
the extension has no independently audited conformance result.

The exact regulated vacuum measure, conditional-rate cutoff removal, uniform
interacting recovery, thermodynamic limit and continuum construction remain
open.

## 29. Two-parameter nodal surface search

The protocol `computations/yang-mills-nodal-surface-prereg.md` specifies a
two-parameter torus search over the block links and a conformance check
against the schedule-wide path family. The executable
`computations/verify_yang_mills_nodal_surface.py` is retained, but
`runs/yang_mills_nodal_surface/verification.json` is absent. No receipt or
current numerical classification is available, and no witness-confinement
statement is transferred from this unretained run.

The exact regulated vacuum measure, conditional-rate cutoff removal, uniform
interacting recovery, thermodynamic limit and continuum construction remain
open.

## 30. Loop-carrying exterior bowtie fibre

The protocol `computations/yang-mills-bowtie-fibre-prereg.md` specifies an
eight-link exterior plaquette and its finite boundary schedule. The executable
`computations/verify_yang_mills_bowtie_fibre.py` imports the current
`computations/verify_yang_mills_exact_block_spectrum.py` and
`computations/yang_mills_conditional_algebra.py` at runtime; no frozen source
snapshot accompanies it. The expected receipt
`runs/yang_mills_bowtie_fibre/verification.json` is absent. No current
boundary-sensitivity or retained-rate classification is therefore available.

The exact vacuum fibre rate, transport score, cutoff removal, uniform
interacting recovery, thermodynamic limit and continuum construction remain
open.


## 31. Finite-regulator SU(2) Schwinger-function bridge

The frozen protocol `computations/yang-mills-su2-schwinger-prereg-v2.md` defines a one-plaquette SU(2) class-function Hamiltonian in a finite character basis. The primary constructs the lowest eigenstate of the declared finite matrix and evaluates the connected fundamental-character Euclidean correlator by its spectral decomposition. The independent implementation rebuilds the tridiagonal matrices and correlators with a separate Jacobi eigensolver.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Finite vacuum construction | Twelve rows over doubled cutoffs $N=8,16,24,32$ and $g^2\in\{1/2,1,2\}$ construct the normalized positive lowest state, the first spectral gap and the connected correlator at four Euclidean times | **PASS** for the declared finite character-cutoff matrices |
| Primary verification | `runs/yang_mills_su2_schwinger_bridge/verification-v2.json` passes 96/96 checks, including matrix symmetry, residual, Perron sign certificate, positive gap, correlator positivity, effective-mass ordering and $C(0)\le4$ | **SUPPORTS_FINITE_REGULATOR_BRIDGE** |
| Independent reconstruction | `runs/yang_mills_su2_schwinger_bridge/verification-independent-v2.json` passes 20/20 source, protocol, schedule and row-reconstruction checks; it binds the primary source and receipt hashes | **PASS** for implementation-independent finite reconstruction |
| Perron sign boundary | The exact irreducible real symmetric Z-matrix theorem supplies strict ground-state positivity; the receipt uses the declared scale-aware floating-point sign tolerance for components below binary64 resolution | **DERIVED** finite-matrix fact |
| Cutoff, volume and continuum scope | The schedule has one plaquette and finite character cutoffs. The fixed-graph theorem in §36 removes the cutoff at fixed coupling and eigenvalue index. Section 37 separately gives a volume-uniform fixed-support ground-density bound on periodic cubic lattices; neither theorem controls this correlator through the lattice-spacing limit | **DERIVED** at fixed graph and fixed local support; **UNRESOLVED** continuum limit |

The finite-matrix ground state is obtained directly from the declared Hamiltonian. The schedule records character-cutoff diagnostics separately from the vacuum correlator.

## 32. Finite-volume SU(2) Wilson Schwinger bridge

The corrected protocol
`computations/yang-mills-su2-wilson-2d-prereg-v2.md` defines the
normalized-Haar character and gluing conventions for the periodic
two-dimensional SU(2) Wilson model. Haar orthogonality gives
\(C_n=2nI_n(\beta)/\beta\), and one convolution gives
\(r_n=C_n/n=2I_n(\beta)/\beta\). The primary and independent implementations
evaluate this normalization separately before reconstructing the partition,
tail and transfer-vacuum correlator rows.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Haar normalization and gluing | Adaptive quadrature has maximum relative error \(1.9081\times10^{-11}\); the independent 65,536-point midpoint integral has maximum relative error \(2.0462\times10^{-10}\); the rejected \(r_n/n\) value differs by one half at \(n=2\) in every row | **PASS**, direct coefficient and single convolution quotient |
| Primary verification | `runs/yang_mills_su2_wilson_2d/verification-v2.json` passes 1092/1092 checks over 108 coupling, spatial-length, temporal-length and cutoff rows | **SUPPORTS_NORMALIZATION_CORRECTED_2D_WILSON_BRIDGE** |
| Independent reconstruction | `runs/yang_mills_su2_wilson_2d/verification-independent-v2.json` passes 120/120 source, protocol, schedule and row checks using a positive Bessel series | **PASS** for implementation-independent reconstruction |
| Character-tail certificate | Every 64-term tail probe lies below the corrected analytic bound; the largest recorded relative bound is \(0.00444863262841\) | **DERIVED** finite-area bound |
| Invalidated evidence | The unversioned protocol and unversioned receipts use a second division by \(n\) and carry no active evidence claim | **REJECT** for the standard Wilson transfer normalization |
| Four-dimensional scope | The construction supplies a two-dimensional partition diagnostic and transfer-vacuum benchmark | **UNRESOLVED** for four-dimensional thermodynamics, OS reconstruction, the lattice-spacing limit and physical mass gap |

The corrected transfer spectrum is exact for the declared two-dimensional
model. Its vacuum correlator is distinct from a finite-temperature torus
correlator. A four-dimensional interacting transfer construction remains a
separate obligation.

## 33. Finite open-cube SU(2) gauge basis and Wilson sparsity

The frozen protocol `computations/yang-mills-su2-open-cube-prereg.md` defines
one open $2\times2\times2$ cube with twelve positively oriented links, six
signed cyclic plaquette words, and trivalent gauge-invariant SU(2) labels.
The primary exact contraction program is
`computations/verify_yang_mills_su2_open_cube.py`. Its receipt
`runs/yang_mills_su2_open_cube/verification.json` binds the protocol, source,
and exact-block representation helper by SHA-256.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Oriented graph words | All six frozen plaquette words close under the endpoint walk; the signed words are retained in the Wilson contraction | **PASS** for the declared open-cube graph |
| Gauge-invariant basis | The raw trivalent $3j$ basis has dimensions $32$ at doubled cutoff $C=1$ and $1013$ at $C=2$ | **PASS** for the finite label enumeration |
| Fundamental Wilson support | Every plaquette has $32$ candidate and nonzero directed entries at $C=1$, and $2388$ candidate and nonzero directed entries at $C=2$; no candidate cancellations occur at the $10^{-12}$ threshold | **SUPPORTS_FINITE_OPEN_CUBE_OPERATOR** |
| Operator controls | The maximum Hermiticity and dagger residual is $5.55\times10^{-17}$; 128 forbidden pairs per plaquette have zero magnitude in both cutoffs | **PASS** for the exact finite contractions |
| Cutoff and continuum boundary | The fixed open cube lies within the fixed-graph cutoff theorem of §36. Section 37 gives a volume-uniform fixed-support ground-density bound on periodic cubic lattices, §38 conditionally extracts a locally normal fixed-regulator ground-state subsequence, and §39 conditionally extracts a reflection-positive Euclidean DLR subsequence at fixed $\beta$. Full-sequence convergence, phase uniqueness, clustering, weak-coupling continuum construction, continuum Osterwalder–Schrader/Wightman reconstruction and the physical mass gap remain open | **DERIVED** cutoff removal at fixed graph and fixed local support; **DERIVED CONDITIONAL** Hamiltonian and Euclidean subsequences; **UNRESOLVED** continuum boundary |

The minimum retained matrix magnitude is
$9.76562500000009\times10^{-4}$ at $C=1$ and
$1.33959190672153\times10^{-6}$ at $C=2$. The receipt passes 69/69 frozen
checks. The result supplies a bounded three-dimensional operator layer for
the next finite-volume construction.

## 34. Recovered larger-volume SU(2) Hamiltonian and character tail

The scientific protocol
`computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md` defines the
open $3\times2\times2$ graph with twenty links and eleven plaquettes, the
complete binary-tree intertwiner basis, cutoffs $C=1,2$, and
$x\in\{1/64,1/16,1/4,1\}$. The recovery protocol
`computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md`
adds the spectator-channel identity, a defect-firing witness, plaquette
Parseval bounds, Wilson-spectrum bounds and Hamiltonian positivity.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Spectator-channel recovery | On the frozen $yz_{x0}$ ket, the edge-only candidate set has 80 states and normalized column norm squared $16$; enforcing remote intertwiner equality leaves five states and norm squared $1$. The selected channel-1/channel-3 overlap at vertex 6 and the recovered matrix element are zero | **PASS**, the omitted-channel defect fires and the production support excludes it |
| Complete finite basis and plaquettes | The basis dimensions are 868 and 955835. The largest normalized plaquette-column norm squared is $1$ at $C=1$ and $2$ at $C=2$; all candidate pairs preserve spectator channels | **PASS**, recovered finite construction for the declared graph and cutoffs |
| Wilson sum and Hamiltonian | The Wilson spectra are $\pm5.89211600962$ and $\pm11.1908496223$, within $[-22,22]$. All eight ground energies are nonnegative and decrease under $C=1\to2$; the $C=2$ values run from $0.342854829715$ to $18.5248301195$ | **PASS**, 226/226 finite-construction checks |
| Independent reconstruction | The independent source reconstructs both ordered basis hashes, every plaquette matrix hash and count, both Wilson extrema, every Ritz energy, all shell norms and the recovery witness | **PASS**, 256/256 checks |
| Character-cutoff tails | Only the $C=1$, $x=1/64$ exact-shell row has ratio at most $0.1$; its $C=2$ partner has ratio $0.100890916829$. The $x=1/4$ and $x=1$ separations are negative at both cutoffs | **INCONCLUSIVE**, all four aggregate cutoff qualifications |
| Excluded edge-only evidence | The external primary and independent receipts bound in `runs/yang_mills_continuum_boundary_audit/verification.json` omit spectator-channel Kronecker deltas and admit the firing witness | **REJECT** for Hamiltonian spectra and cutoff-tail interpretation; retained as defect provenance |
| Cutoff and continuum boundary | The frozen separation qualifications remain `INCONCLUSIVE`, while the form theorem in §36 removes the cutoff on this fixed graph without that separation. Section 37 controls fixed-support ground-density errors uniformly over periodic cubic volumes and excludes global norm control from energy density alone. Sections 38 and 39 conditionally extract a locally normal fixed-regulator ground-state subsequence and a reflection-positive Euclidean DLR subsequence at fixed $\beta$. Section 40 proves the separate anisotropic transfer-to-Hamiltonian and semigroup limit on every fixed finite spatial graph. Identification of the fixed-$\beta$ state with that family, spatial-volume uniformity, full-sequence convergence, phase uniqueness, clustering, weak-coupling continuum construction, continuum Osterwalder–Schrader/Wightman reconstruction and the regulator-independent physical mass gap remain open | **DERIVED** fixed-graph cutoff, local cutoff and anisotropic Hamiltonian-limit control; **DERIVED CONDITIONAL** Hamiltonian and Euclidean subsequences; **UNRESOLVED** continuum limit |

The recovered primary receipt
`runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification.json`
passes 234/238 aggregate checks; the four failures are the declared
non-gating tail-separation rows at $x=1/4$ and $x=1$. The independent receipt
`runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification-independent.json`
passes 256/256 checks. Both bind the materialized receipt-bound recovery
protocol snapshot, the scientific protocol, the current source files and the
shared exact representation helper by SHA-256. The 52-check v9
continuum-boundary audit verifies the one-reference relation between that
snapshot and the current recovery protocol and binds the conditional
thermodynamic and Euclidean evidence, the exact fixed-graph anisotropic
transfer-to-Hamiltonian limit, the renormalized volume/gap criterion and the
conditional RG endpoint-to-gap matching theorem.

## 35. Finite-volume SU(2) quantum Schwinger generator

The corrected protocol
`computations/yang-mills-su2-quantum-schwinger-2d-prereg-v2.md` defines the
finite two-dimensional SU(2) transfer model with
\(\beta\in\{1,2,4\}\), spatial lengths \(L_s\in\{1,2,4\}\), character
cutoffs \(N\in\{8,16,24,32\}\), three fusion channels and five Euclidean
times. It requires the current corrected Wilson v2 receipt.

| Protocol component | Decisive result | Classification and scope |
|---|---|---|
| Primary transfer generator | 36 parameter rows, 468 row checks and eight top-level checks pass: 476/476 | **PASS**, normalization-corrected finite two-dimensional transfer model |
| Independent reconstruction | Ten top-level checks pass; all 36 rows reconstruct the coefficient, gluing, transfer, fusion, correlator and effective-mass data | **PASS**, implementation-independent finite reconstruction |
| Haar and positive-series control | The primary and independent Haar maxima are \(1.9081\times10^{-11}\) and \(2.0462\times10^{-10}\); the independent positive Bessel series has scheduled relative tail bounds below \(10^{-16}\) | **DERIVED**, finite coefficient-control diagnostic |
| Double-division control | Every row rejects \(r_n/n\) with relative discrepancy \(1/2\) at \(n=2\) | **PASS**, normalization defect can fire |
| Cutoff and continuum boundary | The corrected Wilson tail controls the fixed-area partition cutoff, and each declared vacuum fusion orbit is contained once \(N\geq4\) | **UNRESOLVED** for four-dimensional spatial-volume control, the lattice-spacing limit and physical mass gap |

The qualified receipts are
`runs/yang_mills_su2_quantum_schwinger_2d/verification-v2.json` and
`runs/yang_mills_su2_quantum_schwinger_2d/verification-independent-v2.json`.
They bind the corrected protocols, current sources and Wilson v2 primary
receipt by SHA-256. The v1 protocol and v1 receipts retain the rejected
double-division model as defect provenance and carry no active evidence claim.

## 36. Fixed-finite-graph SU(2) character-cutoff form lemma

The analytic protocol
`computations/yang-mills-finite-graph-cutoff-form-prereg.md` fixes one
separation-free theorem for the positive Wilson Hamiltonian on an arbitrary
finite connected graph. A rooted spanning tree gives normalized-Haar chord
coordinates with unit Jacobian and the explicit electric-form comparison

$$
\mathcal E_{\mathrm{ch}}
\leq\mathcal E_K
\leq C_{\Gamma,T}\mathcal E_{\mathrm{ch}},
\qquad
C_{\Gamma,T}
=1+\max_c\sum_tM_tr_{tc}.
$$

Peter–Weyl edge cutoffs are therefore a form core. Positivity of the complete
Wilson potential gives the discarded-mass bound

$$
\|Q_Cu\|^2
\leq
\frac{E_m}{\kappa_C}\|u\|^2,
\qquad
\kappa_C=\frac{(C+1)(C+3)}4,
$$

and boundedness of that potential supplies the noncommuting Ritz-error
estimate in `foundations/loop-to-bubble-projection-theorem.md` (YM195).

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Tree-coordinate Haar measure | The square reconstruction errors are below $2.2\times10^{-16}$; both left-trivialized $12\times12$ Jacobians have determinant one within $2.3\times10^{-10}$ and recover $C_{\Gamma,T}=4$ | **PASS**, deterministic control of the declared coordinate identity |
| Character form and tail bounds | The 64-node class-Haar Gram matrix is the identity within $1.4\times10^{-15}$; all 84 general and 84 square-strengthened finite-reference tail inequalities pass | **PASS**, fixed-graph character-mass estimate |
| Noncommuting Ritz bound | All 67 applicable inequalities pass over six couplings, seven cutoffs and two low levels; the two-dimensional positive-potential control rejects deletion of the potential correction | **PASS**, falsifiable min–max control |
| Independent reconstruction | The tridiagonal primary passes 22/22 checks and the dense independent source passes 18/18; all 84 spectral rows agree within $10^{-10}$ | **PASS**, source- and receipt-bound independent reconstruction |
| Clay boundary | Both receipts record `continuum_hypotheses_present=false` and `clay_verdict=NULL`. The constants are not uniform in graph size, coupling or lattice spacing, and no continuum construction is supplied | **NULL**, no Clay conclusion |

The receipts are
`runs/yang_mills_finite_graph_cutoff_form/verification.json` and
`runs/yang_mills_finite_graph_cutoff_form/verification-independent.json`.
They establish cutoff removal only after the graph, coupling and low-energy
index are fixed. Section 37 separately controls every fixed support uniformly
over periodic cubic volumes and proves a global-norm obstruction. Section 38
uses that local estimate in a conditional diagonal-subsequence argument.
Uniform exact-vacuum fibre control, full-sequence convergence, clustering,
weak-coupling convergence, the lattice-spacing limit,
Osterwalder–Schrader reconstruction and a regulator-independent positive mass
remain open.

## 37. Volume-uniform local SU(2) character cutoff

The analytic protocol
`computations/yang-mills-local-cutoff-density-prereg.md` separates
fixed-support approximation from whole-wavefunction norm approximation. On a
periodic cubic lattice, symmetry of the normalized ground-space density and
the constant-state variational bound give

$$
\operatorname{Tr}(\rho_{0,L}K_e)\leq2x,
\qquad
\operatorname{Tr}(\rho_{0,L}Q_{C,S})
\leq
\frac{2x|S|}{\kappa_C},
\qquad
\kappa_C=\frac{(C+1)(C+3)}4.
$$

The resulting error for a unit-norm observable supported on $S$ is at most
$2\sqrt b+b$, where $b=2x|S|/\kappa_C$. This bound is independent of the
periodic volume.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Multi-volume local schedule | All 1,536 rows over eight volumes, six couplings, four support sizes and eight cutoffs are present; 1,152 meet $b<1$, and every fixed-parameter volume spread is zero | **PASS**, volume-uniform fixed-support cutoff estimate |
| Auxiliary joint-cutoff schedule | Seven rows with $x_k=k^4$ and $C_k=k^3$ satisfy $C_k^2/x_k=k^2$ and have strictly decreasing local bounds | **PASS**, sufficient cutoff diagnostic; no weak-coupling field estimate |
| Global product-family obstruction | All 180 rows reconstruct the character tail and electric energy; at $(q,C,N)=(1/2,2,512)$ the discarded norm is $0.9996850695596114$ | **PASS**, bounded electric energy density does not imply volume-uniform whole-wavefunction norm control |
| Independent reconstruction | The Python primary passes 16/16 checks and the JavaScript independent source passes 17/17, with zero maximum difference over all primary rows | **PASS**, source- and receipt-bound independent calculation |
| Clay boundary | Both receipts record `thermodynamic_limit_constructed=false`, `continuum_hypotheses_present=false` and `clay_verdict=NULL` | **NULL**, no continuum or mass-gap conclusion |

The receipts are
`runs/yang_mills_local_cutoff_density/verification.json` and
`runs/yang_mills_local_cutoff_density/verification-independent.json`. They
bind protocol SHA-256
`69fe2a132dbccec4484bb6fc5f3d1b75dc95e88d5de7687774ab17e69c0e6789`;
the independent receipt also binds the current primary source and
primary-receipt hash. The theorem controls local observables of the symmetric
finite-volume ground density and supplies the tightness input used in §38.
The local-cutoff receipts themselves record
`thermodynamic_limit_constructed=false`; phase selection, clustering, the
weak-coupling lattice-spacing limit, Osterwalder–Schrader reconstruction and
a regulator-independent physical mass remain open.


## 38. Fixed-regulator thermodynamic ground-state subsequence

The analytic protocol
`computations/yang-mills-thermodynamic-ground-state-prereg.md` uses the
finite-volume ground densities and the §37 local tail inequality as declared
inputs. For every fixed finite link support $S$, Peter–Weyl compression has
rank

$$
d_C^{|S|},
\qquad
d_C=\frac{(C+1)(C+2)(2C+3)}6,
$$

and lies within trace distance

$$
2\sqrt{\frac{8x|S|}{(C+1)(C+3)}}
$$

of the reduced density. Finite-dimensional compactness therefore makes the
family trace-norm precompact. A Cantor diagonal subsequence over nested
supports yields compatible density matrices. The finite-volume ground
quadratic form passes to the limit on the gauge-invariant local $*$-algebra
whose operators have finite Peter–Weyl matrix support.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Peter–Weyl rank schedule | All 36 rows match the direct sum and closed polynomial exactly; every compressed support rank is finite | **PASS**, finite-dimensional compression identity |
| Compactness cutoff schedule | All 100 rows reach the declared $\varepsilon/2$ compression radius at the least cutoff; the largest is $C=4095$ | **PASS**, conditional consequence of the analytic local-tail input |
| Compatibility and finite ground identities | Nested and direct partial traces differ by $1.1102230246251565\times10^{-16}$; all 12 synthetic finite-matrix quadratic forms are nonnegative, with maximum direct-versus-spectral discrepancy $3.609612342034603\times10^{-15}$ | **PASS**, arithmetic controls; no interacting $SU(2)$ ground state is constructed |
| Implication firing controls | Alternating states retain trace distance $2$ between cluster points; 25 scheduled representation rows escape their fixed cutoff; the ferromagnetic one-magnon upper bound falls to $6.023626075915001\times10^{-4}$ at $L=256$ | **PASS**, full-sequence and uniform-gap implications remain blocked |
| Independent reconstruction | The Python primary passes 18/18 checks and the JavaScript independent source passes 19/19; rank, compactness, escaping-sector and gap schedules agree exactly, and the maximum ground-fixture discrepancy is $1.7763568394002505\times10^{-15}$ | **PASS**, source- and receipt-bound independent calculation |
| Clay boundary | Both receipts record `operator_argument_scope=CONDITIONAL_ON_FINITE_VOLUME_GROUND_DENSITIES_AND_YMT2`, `thermodynamic_state_constructed_by_verifier=false`, `uniform_mass_gap_established=false`, `continuum_hypotheses_present=false` and `clay_verdict=NULL` | **NULL**, no continuum or mass-gap conclusion |

The receipts are
`runs/yang_mills_thermodynamic_ground_state/verification.json` and
`runs/yang_mills_thermodynamic_ground_state/verification-independent.json`.
They bind protocol SHA-256
`200217b92778d4d30551b7a655fa7e1af38ab9dbd7948f7395097ef08874bf87`;
the independent source hash is
`519bc5e8bdc0373b63b8d67e83647d88819ef5f5111378a86b79daa3b084cb07`
and it binds primary-receipt SHA-256
`713849eb0863a5b3e69865388e64d46641d4fa41447cf8d4588e35bb58944e73`.
Conditional on the declared analytic inputs, the operator argument constructs
at least one locally normal fixed-regulator ground-state subsequence.
Full-volume-sequence convergence, uniqueness, clustering, a uniform positive
gap, weak-coupling continuum construction, Osterwalder–Schrader
reconstruction and a regulator-independent physical mass remain open.


## 39. Fixed-regulator Euclidean reflection-positive Gibbs subsequence

The analytic protocol
`computations/yang-mills-euclidean-reflection-positive-prereg.md` fixes the
four-dimensional Wilson measure on even periodic tori. For irreducible
dimension $n\geq1$, its normalized-Haar character coefficient is

$$
C_n(\beta)
=I_{n-1}(\beta)-I_{n+1}(\beta)
=\frac{2nI_n(\beta)}{\beta}>0.
$$

Established finite-lattice reflection and transfer theorems combine this
positivity with a diagonal limit of compact finite-link marginal spaces.
Conditional on those established theorems, the limit is a
translation-invariant, gauge-invariant, reflection-positive Wilson DLR state
at each fixed $\beta>0$ and defines a fixed-regulator
Osterwalder–Schrader Hilbert space.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Primary finite-kernel schedule | All 308 checks pass over 36 coefficient, reflection-Gram, Schur-product and weighted-transfer rows; the maximum adaptive-Haar relative error is $6.578917885036281\times10^{-10}$ | **PASS**, finite normalized-Haar reflection-kernel support |
| Independent reconstruction | All 22 checks pass and all 36 rows reconstruct through a positive Bessel series, compensated 65,536-point midpoint Haar rule and independent Jacobi eigensolver; the maximum Haar relative error is $1.7530111416976028\times10^{-12}$ | **PASS**, source- and receipt-bound independent reconstruction |
| Analytic local-marginal limit | Compatible local marginals have a diagonal weak subsequence; translation, compactly supported gauge symmetry, reflection positivity and the Wilson DLR identity pass on cylinder functions | **DERIVED CONDITIONAL**, fixed regulator and fixed $\beta$ |
| Implication firing controls | A negative highest character coefficient gives minimum Gram eigenvalue $-8.612469317193874$; an asymmetric kernel is rejected; strictly positive two-level transfer matrices have gap $6.023626075915001\times10^{-4}$ at $L=256$ and tend to zero | **PASS**, positivity can fail and positive transfer does not imply a uniform gap |
| Continuum boundary | Both receipts set their fixed-$\beta$ Hamiltonian-equivalence flag, continuum construction, Wightman reconstruction and uniform mass gap false, together with full-sequence convergence, uniqueness and clustering; §40 treats a separate anisotropic fixed-graph family | **NULL**, no continuum or physical mass-gap conclusion |

The qualified receipts are
`runs/yang_mills_euclidean_reflection_positive/verification.json` and
`runs/yang_mills_euclidean_reflection_positive/verification-independent.json`.
The protocol, primary source and independent source SHA-256 values are
`d3a948b2114fad9b757c5005a8adc5f1e953b1353de0d5a99b896ef8c6c9165f`,
`212229883db015655e7f74a3015a8e4e76ae1f00607ae085f4feb091467c6f28`
and
`a72cf5e38d58d0ec1afa34f218371a1426e8383564c5f0a48377e75374efb11c`.
The independent receipt binds primary-receipt SHA-256
`2e63f1eb49670ba87a678e9acfcae5c0574669db94296c4768a83d3c854b128f`.
Full-volume convergence, phase selection, clustering, identification of the
fixed-$\beta$ state with the anisotropic Hamiltonian family, the weak-coupling
lattice-spacing limit, continuum Osterwalder–Schrader reconstruction and a
regulator-independent physical mass remain open.


## 40. Fixed-graph anisotropic Wilson transfer-to-Hamiltonian limit

The frozen protocol
`computations/yang-mills-anisotropic-hamiltonian-limit-prereg.md` separates
the anisotropic temporal-step limit from the fixed-$\beta$ thermodynamic
family. Its character weights are

$$
B_\tau=\frac{4a}{g^2\epsilon},
\qquad
B_\sigma=\frac{2\epsilon}{g^2a}.
$$

Normalized central convolution and symmetric magnetic half-steps define
$T_\epsilon$. On every fixed finite spatial graph,
$(I-T_\epsilon)/\epsilon$ and
$-\epsilon^{-1}\log T_\epsilon$ converge in strong-resolvent sense to the
supplied Kogut–Susskind Hamiltonian, and
$T_{t/N}^{\,N}\to e^{-tH}$ strongly. The exact bare Wilson convention is
$g_W=2^{1/4}g$, $a_\tau=\epsilon/\sqrt2$.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Normalized-Haar character kernel | The primary adaptive-Haar maximum errors are $1.2105410256096666\times10^{-15}$ for the Bessel coefficient and $6.661338147750939\times10^{-16}$ for the half-potential compression | **PASS**, normalization and finite-character matrix identities |
| Difference and logarithmic generators | All 414 primary checks pass over 36 rows and nine $(g^2,C)$ families. Every error decreases; final-to-first ratios are $0.126154$–$0.131896$ and $0.124385$–$0.126598$ | **PASS**, finite-character support for the analytic fixed-graph theorem |
| Semigroup product | At $g^2=a=1$, $C=6$ and $t=1/2$, errors decrease from $2.205924599021739\times10^{-4}$ at $N=64$ to $2.8046955584765558\times10^{-5}$ at $N=512$ | **PASS**, fixed-compression Chernoff-product control |
| Implication firing controls | Both coefficient mutations produce ratio $2$; omission of $C_1(4)$ gives vacuum multiplier $4.879732576852224$; an asymmetric split gives residual $8.500055557561465\times10^{-3}$; a positive two-level family has final-to-first gap ratio $1.0282972921526613\times10^{-3}$ | **PASS**, normalization, symmetry and nonuniform-gap implications can fail |
| Independent reconstruction | All 24 checks pass using separate midpoint integrals and a Jacobi eigensolver; maximum differences from primary character ratios, generator errors and semigroup errors are $2.220446049250313\times10^{-16}$, $5.7048044673629894\times10^{-12}$ and $9.750632410049451\times10^{-13}$ | **PASS**, source- and receipt-bound independent calculation |
| Clay boundary | Both receipts record fixed graph only, with no spatial thermodynamic limit, lattice-spacing limit, continuum reconstruction or uniform physical gap and `clay_verdict=NULL` | **NULL**, no Clay conclusion |

The qualified receipts are
`runs/yang-mills-anisotropic-hamiltonian-limit/verification.json` and
`runs/yang-mills-anisotropic-hamiltonian-limit/verification-independent.json`.
The protocol, primary source and independent source SHA-256 values are
`cfbcfb7140e2c085e86285541ac97517d3b6a021c6967f57189ce5a801abe54e`,
`41f8a69ba2b4a07b2f94735d1f5368069c1a3cdb04b583c23dfb67fabd9acf7f`
and
`d7cd26729c592e6459015f2a7cd733e1042748a8d697cbc31e45a7c58f4f7093`.
The independent receipt binds primary-receipt SHA-256
`bf1ac61a072a2cc24fde30d22df5892d8b27a4dfcba680f81d5cb00b9981dd54`.
Along this family $B_\tau\to\infty$ and $B_\sigma\to0$, so it does not
identify the fixed-$\beta$ Gibbs subsequence of §39. Spatial-volume
uniformity, weak-coupling continuum construction, continuum
Osterwalder–Schrader/Wightman reconstruction and a regulator-independent
positive mass remain open.


## 41. Renormalized weak-coupling gap and volume criterion

The frozen protocol
`computations/yang-mills-renormalized-gap-scaling-prereg.md` fixes the
universal two-loop $SU(2)$ Wilson scale, its exact bare-convention map to the
Hamiltonian normalization, simultaneous cutoff/volume schedules and the
necessary renormalized-gap criterion. It uses

$$
F_W(g_0)
=\exp\!\left[-\frac{1}{2b_0g_0^2}\right]
(b_0g_0^2)^{-51/121},
\qquad
b_0=\frac{11}{24\pi^2}.
$$

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Two-loop scale arithmetic | The six-row schedule spans $g_0^2=0.8$ to $0.05$ and $F_W=5.724856108444617\times10^{-6}$ to $3.896428797701234\times10^{-93}$; direct, logarithmic and $\beta_{\rm lat}=4/g_0^2$ forms agree | **PASS**, universal two-loop reference-scale arithmetic |
| Simultaneous volume condition | Fixed and polynomial $N$ give $NF_W\to0$; $N\asymp F_W^{-1}$ keeps a fixed physical box; $(g_0^2F_W)^{-1}$ and $F_W^{-1}\log(1/F_W)$ give $NF_W\to\infty$ | **DERIVED** necessary schedule classification; no interacting trajectory is constructed |
| Renormalized gap condition | Constant, polynomial and isolated-square lattice gaps have $a\Delta/F_W\to\infty$; $a\Delta=F_Wg_0^2$ vanishes; $a\Delta=(7/4)F_W$ remains finite and positive | **DERIVED** scale classification; no row computes an interacting Yang–Mills eigenvalue |
| Wilson/Hamiltonian convention | $g_W=2^{1/4}g_H$, $H_H=H_W/\sqrt2$, $F_H(g_H)=F_W(2^{1/4}g_H)$ and the normalized eigen-gap is invariant | **PASS**, exact fixed-regulator unit map |
| Independent reconstruction and firing controls | The primary passes 80/80 checks and the independent Node implementation passes 20/20; all six mutations fire, including the wrong beta coefficient, fixed-box misclassification and omitted Hamiltonian time rescaling | **PASS**, source- and receipt-bound implementation controls |
| Clay boundary | Both receipts set the interacting spectrum, coupled trajectory, thermodynamic limit, Osterwalder–Schrader axioms, nontrivial continuum limit and continuum mass gap false and retain `clay_verdict=NULL` | **NULL**, necessary continuum yardstick only |

The qualified receipts are
`runs/yang-mills-renormalized-gap-scaling/verification.json` and
`runs/yang-mills-renormalized-gap-scaling/verification-independent.json`.
The protocol, primary source and independent source SHA-256 values are
`c38ff8d6ace94b8221d6040a60f894cfd5e0a8adea5c45c270b48437e18b7a1c`,
`d8c3b0f94b62c6ef67fb3dc5fee4b2186e3966beb5dbeeed3dc372bafd5ea6d3`
and
`498826b21a7c977d669c7f3697d5267bf61638a525d664263db790e7b97530a8`.
The independent receipt binds primary-receipt SHA-256
`bc77e1cc1a8ccda41240fbaa3d22963679786c11e402923c5898a1356b6d1f44`.
This closes the scale-definition ambiguity. The interacting estimates needed
to realize the criterion and the four-dimensional continuum construction
remain open.


## 42. Conditional RG endpoint-to-gap matching

The frozen protocol
`computations/yang-mills-rg-gap-matching-prereg.md` isolates a sufficient
renormalization-group bridge from the two-loop yardstick in §41 to the
required microscopic spectral scale. With block factor $B$ and

$$
r_k=\log F_W(g_{k+1})-\log F_W(g_k)-\log B,
\qquad
R_n=\sum_{k=0}^{n-1}r_k,
$$

the exact scale identity is
$B^{-n}/F_W(g_0)=e^{R_n}/F_W(g_n)$. A fixed positive endpoint window and
$|R_n|\leq C_{\mathrm{RG}}$ therefore bound this ratio above and below.
Exact time-correlation blocking then gives
$\delta_0=B^{-n}\delta_n$ for the retained observable family.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Exact endpoint schedules | At $g_0^2=(0.8,0.5,0.3,0.2,0.1,0.05)$, the $B=2$ schedules enter $[1/64,1/32)$ after $(12,23,44,69,147,301)$ blocks and satisfy $B^{-n}/F_W=1/F_W(g_n)$ | **PASS**, exact scale-matching arithmetic |
| Bounded cumulative defect | Alternating $r_k=(-1)^k0.025$ gives $R_n\in\{0,0.025\}$ and keeps every synthetic renormalized rate inside $[15.2196707920,131.2403354271]$ | **PASS**, conditional endpoint-to-microscopic rate implication |
| Drift discriminator | Constant $r_k=0.00625$ satisfies the frozen one-step bound but has $R_n>0.025$ in all six rows and is rejected | **PASS**, per-step control is insufficient |
| Volume and blocking depth | The same identity gives $N_n\to\infty$ iff $N_0F_W(g_0)\to\infty$; the matching depth is $n=[2b_0\log B]^{-1}g_0^{-2}+O(\log g_0^2)$ | **DERIVED conditional**, contingent on the supplied trajectory and endpoint window |
| Perturbative flatness | For every real $q$, $F_W(g)/g^q\to0$; the frozen $q=(1,2,4,8)$ rows decrease strictly | **DERIVED** scale property; no Gaussian no-go conclusion |
| Independent reconstruction and firing controls | The primary passes 139/139 checks and the independent Node implementation passes 32/32. All seven mutations fire: two cumulative-defect errors, per-step-only drift acceptance, omitted time rescaling, fixed-box misclassification, zero endpoint rate and deleted observable completeness | **PASS**, source- and primary-receipt-bound arithmetic controls |
| Clay boundary | Endpoint rates are synthetic assumption witnesses. Both receipts set the RG trajectory, exact block map, correlation transport, retained-observable completeness, coarse interacting gap, continuum construction and continuum mass gap false and retain `clay_verdict=NULL` | **NULL**, conditional implication only |

The qualified receipts are
`runs/yang-mills-rg-gap-matching/verification.json` and
`runs/yang-mills-rg-gap-matching/verification-independent.json`.
The protocol, primary source and independent source SHA-256 values are
`d8749326eb0fcf2062302e0afec4cb68dc2dd96ac532962bffdb18c658860f36`,
`712902166378a92f3cbb651fc0a1e5d6e075a1e9d3d95b8eacdd3325b44bd6f2`
and
`fda53344e26e65f7c652ecc1ea0cd01dbcc583fa394af3acb444453ca827cfad`.
The independent receipt binds primary-receipt SHA-256
`ccb8b3e562b047e6fd562bd06cdfce807beb6d7f0d7a4d7c59b0704ccffdc5d4`.
Its own SHA-256 is
`0f1e82b9ad18dde67c3b4802db8038519cb5d39038c921f9eb343073b5052eb5`.
The RG construction, $O(1)$ cumulative defect bound over
$O(g_0^{-2})$ levels, exact correlation-preserving block map, complete
retained physical channels, uniform positive interacting endpoint gap and
continuum Osterwalder–Schrader reconstruction remain open. Balaban's
ultraviolet-stability results do not establish these inputs.


## 43. Finite transfer-correlation criterion and completeness boundary

The frozen protocol
`computations/yang-mills-transfer-completeness-prereg.md` tests the finite
operator content of exact correlation transport without claiming to construct
the Yang–Mills block map. For a positive self-adjoint transfer operator $A$,
an isometric retained map $J$, $P=JJ^*$ and $Q=I-P$, the second retained
correlation defect is

$$
D_2(u)
=\langle Ju,A^2Ju\rangle-\langle u,(J^*AJ)^2u\rangle
=\|QAJu\|^2.
$$

Thus exact second-moment matching for every retained vector is equivalent to
$\operatorname{Ran}J$ reducing $A$, which is equivalent to matching every
later moment in the finite positive self-adjoint setting. Completeness is
separate: an exact reducing retained sector can omit a physical channel and
therefore report a retained rate rather than the full physical gap.

| Fixture or control | Decisive result | Classification and scope |
|---|---|---|
| Complete invariant fixture | Defect $0$; retained and full gaps both $0.3285040669720361$ | **PASS**, exact finite transfer criterion |
| Incomplete invariant fixture | Defect $0$ and exact retained moments; retained gap $0.3285040669720361$, full gap $0.09431067947124129$ from the omitted $0.91$ channel | **PASS**, completeness is not inferred from exact retained correlations |
| Leaky positive fixture | Defect $0.004900000000000001$; $m=2$–$5$ errors are nonzero | **PASS**, second-moment leakage fires |
| Mutation controls | Omitted defect, ignored completeness, compressed/full-gap conflation and forced leakage acceptance all fire; $4/4$ controls activate | **PASS**, checks are non-vacuous |
| Independent reconstruction | Primary `54/54`; independent `55/55`; both activate all four controls | **PASS**, the fifth independent decision is the scheduled primary-receipt source-binding audit; the scientific fixture schedule remains 54 checks |
| Clay boundary | No exact interacting block map, interacting transfer operator, complete observable family, full gap, thermodynamic/continuum construction or mass gap is established | **NULL**, finite criterion only |

The qualified receipts are
`runs/yang-mills-transfer-completeness/verification.json` and
`runs/yang-mills-transfer-completeness/verification-independent.json`.
The protocol, primary source, independent source, primary receipt and
independent receipt SHA-256 values are
`6a34e35376f8af5115a975fb868f13e25cd5d1cd38ae83f02eb6c8af7ec8d9fc`,
`fa470ad179e93bf7f371db0f856b0b3faa8d06509edcc1fac048761eaaecac58`,
`bce9a24511941aa7d18f5318c6c42ba64495b3132aeb54de4fb06d5458d548f1`,
`b073ffe2dd2c98f7dd5c52a2535b58c86c149ea0ae0242305a201294ba1c6140`
and
`c04fced6f75e27b50b1cf2460c1eaf2049ce67b9bbcb48c5aeadb5b2b839fe66`.
The finite criterion sharpens the correlation-preserving map obligation; it
does not supply the map or solve the Clay problem.

## 44. Local gauge-invariant observable completeness

The frozen protocol
`computations/yang-mills-local-observable-completeness-prereg.md` addresses
the retained-observable completeness premise in (YM252) by specifying the full
local gauge-invariant algebra. On a finite connected $SU(2)$ graph, the
unital *-algebra generated by fundamental traces of all closed words is
uniformly dense in the continuous gauge-invariant cylinder algebra. On the
infinite lattice, the union over finite supports is the local algebra, and
centered local GNS vectors are dense in the vacuum-orthogonal subspace.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Tree-gauge reduction | `cycle4`, `theta3` and `bouquet3` reconstruct all tree transports and chord holonomies with maximum quaternion error $1.6653345369377348\times10^{-16}$ | **PASS**, finite graph coordinate control |
| Wilson-word algebra | Simultaneous conjugation, cyclic and inverse-word invariance and the $2\times2$ trace contraction identity pass on all three fixtures; the largest primary residual is $1.5543122344752192\times10^{-15}$ | **PASS**, finite $SU(2)$ word identities |
| Character and invariant-tensor controls | Character recursion through $n=8$ has maximum error $2.3092638912203256\times10^{-14}$, evaluation rank is $9$, and epsilon conjugation is exact to the recorded precision | **PASS**, finite representation controls |
| Orbit separation and domain boundary | The full word family separates the fixed three-loop orientation pair by $0.8639999999999999$, while words of length at most two collide; the finite $\chi_0,\ldots,\chi_3$ family misses $\chi_8$ by $12.822948255619522$ | **PASS**, full word family and centering requirement are non-vacuous |
| Mutation controls | Raw link entries, dropped orientation words, omitted centering and finite-word completeness each fire | **PASS**, $4/4$ controls |
| Analytic completeness statement | Wilson-word density and centered local GNS density follow under the stated compact-$SU(2)$, Peter–Weyl and positive-state hypotheses | **DERIVED CONDITIONAL**, finite and infinite local algebra |
| Uniform-form transfer criterion (YM262)–(YM267) | The exact finite-regulator lower bound, strong recovery-sequence direction, continuum form-core requirement and scale matching required to transfer a physical lower gap are stated explicitly | **DERIVED CONDITIONAL**, criterion only; no uniform bound, recovery construction, form core or continuum representation is supplied |
| Boundary-fibre Haar contraction (UFA18a)–(UFA18d) | The normalized invariant tensor $\iota_\alpha=d_\alpha^{-1/2}\sum_r e_{\alpha,r}\otimes e_\alpha^{\,r}$ gives the finite Peter–Weyl contraction and its isometry under the declared dual orientation | **DERIVED CONDITIONAL**, the finite-graph Hilbert extension and surjectivity are supplied by (UFA19)–(UFA21); the derivative/form compatibility in (UFA22), coarse transport, uniform constants and the continuum bridge remain open |
| Finite boundary-gluing extension (UFA19)–(UFA22; YM275)–(YM278) | Haar projection, Peter–Weyl density and unitary extension hold for each fixed graph; (UFA22) is the separate derivative/boundary-electric core identity whose closure would give the finite form-domain statement | **DERIVED CONDITIONAL**, fixed-regulator Hilbert theorem plus conditional form target; no coarse retained-sector map or regulator-uniform estimate follows |
| Local recovery route (YM268)–(YM273) | Conditional boundary-fibre Poincaré control, discarded-sector coverage and local-energy overlap imply a uniform discarded resolvent through the displayed scale comparison | **DERIVED CONDITIONAL**, exact-vacuum constants and all trajectory quantifiers remain open |
| Residual Schur bridge (YM274) | Uniform positive residual blocks and a bounded residual off-diagonal block give the recovery floor $\gamma_R$; the resulting $A_{Q,*}=\gamma_R^{-1}$ enters the local route | **DERIVED CONDITIONAL**, residual estimates and boundary-compatible transport remain open; Hamiltonian Feshbach roots are a separate finite calculation |
| RG and mass-gap bridge | No retained RG image is identified with the full local algebra, and no matched uniform lower form bound is constructed | **UNRESOLVED**, exact transport and physical spectral lower bound |

The primary receipt
`runs/yang_mills_local_observable_completeness/verification.json` passes
36/36 checks and all four mutation controls. The independent receipt
`runs/yang_mills_local_observable_completeness/verification-independent.json`
passes 41/41 decisions, including the primary-receipt source-binding audit.
The protocol, primary source, independent source and primary receipt hashes
are respectively
`e5e4095a4c4e012aa67b64174c3c86d269ceea86c6c4ab3fda9dc4efc2da2570`,
`78d4f6064030fb49d30e4a9c602d842f8aeeac1b8f04dcc22d66f543fbcd2913`,
`f71ed4bc7a0a60ee16ffe4ce36c79ca76ce3863d1c339dcdacbecd1968d775fb`
and
`5fe7f7197a1b6acb0347714094ea210f489abcd8da0e96853795c8df5beaac82`.
The result identifies the complete local observable core. The conditional
boundary-fibre, finite boundary-gluing, local-recovery and residual-Schur
route is recorded in
`foundations/loop-to-bubble-projection-theorem.md` §§9.34.1–9.34.2 and
`computations/yang-mills-uniform-feshbach-obligation-map.md`
§§UF-A.1–UF-A.2, UF-B.2–UF-B.6. The exact coarse RG map, the
volume- and regulator-uniform lower spectral bound, the strong recovery
transport in (YM265), the scale matching in (YM266), and the continuum
representation required for a physical mass gap remain open.


## 45. Fixed-graph interacting Feshbach resolvent

The frozen protocol
`computations/yang-mills-interacting-feshbach-prereg.md` turns the first
analytic obligation in (YM262) into an explicit finite interacting
Feshbach calculation. It reuses the exact seven-link two-plaquette
representation contractions from
`computations/verify_yang_mills_exact_block_spectrum.py`, with source cutoff
$c_P=1$ for the retained space and $c_Q=3$ for the full space. The raw
spaces contain $4$ and $23$ gauge-invariant states. Projecting out the
computed finite-graph ground vector gives $\dim\mathcal K=22$,
$\dim\mathcal P=4$ and $\dim\mathcal Q=18$.

For the shifted normalized Hamiltonian, the test forms
$A=P(H-E_0)P$, $B=PHQ$ and $D=Q(H-E_0)Q$. With
$\alpha=\lambda_{\min}(A)$, $\delta_Q=\lambda_{\min}(D)$ and
$\beta=\|B\|_2$, it checks

$$
\|(D-\lambda I)^{-1}\|_2\le(\delta_Q-\lambda)^{-1},
\qquad
\|B(D-\lambda I)^{-1}B^*\|_2
\le\frac{\beta^2}{\delta_Q-\lambda},
$$

and the sufficient Schur lower function
$\Phi(\lambda)=\alpha-\lambda-\beta^2/(\delta_Q-\lambda)$. The
tail-floor control evaluates the domain boundary $\lambda=\delta_Q$ and
records that the discarded-sector resolvent is undefined there in every row.

| $x$ | finite gap $\Delta_x$ | $\alpha$ | $\delta_Q$ | $\beta$ | $\beta^2/(\alpha\delta_Q)$ | $\gamma_{\mathrm{Fesh}}$ |
|---:|---:|---:|---:|---:|---:|---:|
| $1/4$ | 3.0231627325 | 3.0234709080 | 7.5667571360 | 0.7285225073 | 0.0231990584 | 2.9095098048 |
| $1$ | 3.3551682618 | 3.3771718906 | 7.9203910621 | 1.3157987531 | 0.0647260568 | 3.0236078690 |
| $4$ | 6.2289507390 | 7.2712618643 | 10.1841717978 | 5.3628682696 | 0.3883816982 | 3.1705937311 |
| $16$ | 14.7507061280 | 27.9439067368 | 22.6573195372 | 22.7838845309 | 0.8198981173 | 2.3639090282 |

The primary receipt
`runs/yang_mills_interacting_feshbach/verification.json` passes $38/38$
checks and classifies the four rows `SUPPORTS_FINITE_FESHBACH`. The separate
arithmetic and provenance audit
`runs/yang_mills_interacting_feshbach/verification-independent.json` passes
$29/29$ checks; it reconstructs the scalar inequalities and source bindings,
while its matrix-reassembly scope is explicitly absent. The protocol, primary
source, exact-block reference, primary receipt, independent source and
independent receipt SHA-256 values are respectively
`df0083d5132944d2d0cb68a5c224eb7664e5be48c4b9aa41a9a12a18213a4ab7`,
`f232859d15718962a9b7ffc94ff7c346aac305be46de96bd696cbdfd2a7a6f7a`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`787c064df8b0ce4bf2bd224b4637aad794597334e857df43e86271e509bc6c29`,
`ac3a633361bf554b4bdb49b3386a9cbce6ff0b1933e77961eec0d793ba82e192`
and
`20c937430e48b180f57026ea80b4f2ec77bba22015f15c79c9cf0a1750a72014`.

The result is confined to this seven-link, finite-cutoff matrix. It supplies
a working finite Schur certificate for the interacting discarded sector. A
constant uniform in lattice spacing, spatial volume and the weak-coupling
trajectory, together with recovery transport and continuum scale matching,
remains the next proof obligation.

## 46. Nested-cutoff interacting Feshbach screen

The frozen protocol
`computations/yang-mills-interacting-feshbach-cutoff-screen-prereg.md`
extends the fixed $(c_P,c_Q)=(1,3)$ calculation over all ten nested pairs
$1\le c_P<c_Q\le5$ on the same seven-link two-plaquette $SU(2)$ graph. The
source dimensions at cutoffs $1,2,3,4,5$ are $4,11,23,42,69$. Each pair is
evaluated at $x\in\{1/4,1,4,16\}$, giving $40$ rows.

The primary execution has status `PASS` with $403/403$ controls passing. Its
scientific classification is `NO_POSITIVE_FAMILY_CERTIFICATE`: $36/40$ rows
have positive Schur roots. The independent arithmetic and source-binding
audit has status `PASS` with $370/370$ checks passing.

| $x$ | positive roots | minimum root | minimum root/gap | maximum $\beta^2/(\alpha\delta_Q)$ | rows without positive root |
|---:|---:|---:|---:|---:|:---|
| $1/4$ | 10/10 | 2.9094856999 | 0.9623980492 | 0.0232040377 | — |
| $1$ | 10/10 | 3.0212793119 | 0.9006418757 | 0.0651026186 | — |
| $4$ | 10/10 | 2.8564483523 | 0.4663584974 | 0.4231527971 | — |
| $16$ | 6/10 | 0.4294699691 | 0.0317119684 | 1.2758330866 | $(1,4),(1,5),(2,5),(3,5)$ |

At $x=16$, the four rows without a positive root have
$\beta^2/(\alpha\delta_Q)$ equal to $1.080183$, $1.210459$, $1.275833$
and $1.024983$. The same outer cutoffs recover positive roots when the
retained cutoff grows: $(2,4)$, $(3,4)$ and $(4,5)$ all qualify. The finite
screen shows retained-cutoff dependence and motivates testing a growth
schedule for this interacting fibre. It leaves the uniform regulator, volume
and continuum constants open.

The source-binding order for the evidence is protocol, primary screen source,
exact-block reference, predecessor Feshbach source, predecessor receipt,
current primary receipt, independent screen source, independent receipt:
`7347dffc5a12299fae84355e42db230c0cf7df739b095556b92966253c54fbe7`,
`ca05675b6e54507c94db6546219206f7f0acf2656fa052c644a97ce17848cdd0`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`f232859d15718962a9b7ffc94ff7c346aac305be46de96bd696cbdfd2a7a6f7a`,
`787c064df8b0ce4bf2bd224b4637aad794597334e857df43e86271e509bc6c29`,
`7cc9e6d5afafb3811da613528b570686a7ba74ff20a297f3a1908c8626a436b8`,
`64e2a7acdd1ffca5873463e56420901c2ffd95d129bd69bb66c9c878b4859b8b`
and
`5e81df731ab80a5bca5046ebd1207873fc3a0847f07732f232107831393a8bfc`.

The next proof obligation is a gauge-compatible retained family whose
$\alpha$, $\delta_Q$ and $\beta$ admit a bound uniform in the outer cutoff,
volume and weak-coupling trajectory. The present rows identify the finite
growth pattern that such a family must accommodate.

## 47. Cutoff-six interacting Feshbach growth family

The frozen protocol
`computations/yang-mills-interacting-feshbach-cutoff6-prereg.md` evaluates all
fifteen nested cutoff pairs $1\le c_P<c_Q\le6$ on the seven-link
two-plaquette $SU(2)$ graph. The source dimensions at cutoffs
$1,2,3,4,5,6$ are $4,11,23,42,69,106$. Every pair is evaluated at
$x\in\{1/4,1,4,16\}$, giving $60$ rows. The adjacent pairs
$c_P=c_Q-1$ are the pre-declared retained growth family.

The primary execution has status `PASS` with $603/603$ controls passing. Its
scientific classification is `SUPPORTS_FINITE_ADJACENT_FAMILY`: the adjacent
sequence has positive Schur roots in all $20/20$ rows. The independent
arithmetic and source-binding audit has status `PASS` with $552/552$ checks
passing.

| $x$ | adjacent positive roots | minimum root | minimum root/gap | maximum $\beta^2/(\alpha\delta_Q)$ |
|---:|---:|---:|---:|---:|
| $1/4$ | 5/5 | 2.9208968479 | 0.9661156707 | 0.0208730474 |
| $1$ | 5/5 | 3.0789676439 | 0.9101955216 | 0.0586762656 |
| $4$ | 5/5 | 4.2963741883 | 0.6539510321 | 0.2931634531 |
| $16$ | 5/5 | 1.7421573070 | 0.1315261595 | 0.8481941983 |

The full nested schedule has $52/60$ positive roots. The eight rows without
a positive root are all at $x=16$, with pairs
$(1,4),(1,5),(2,5),(3,5),(1,6),(2,6),(3,6),(4,6)$. Thus the maximal
one-step retained sequence remains qualified on this finite graph while
coarser retained spaces can fail at strong coupling. The result leaves the
uniform regulator, volume, recovery, continuum and mass-gap bounds open.

The source-binding order for the evidence is protocol, primary source,
independent source, exact-block reference, predecessor source, predecessor
receipt, primary receipt and independent receipt:
`06b2dceade0f5d9ad946ca5c48630da55a1bec7f9f1769eaa535d6ec8bfb76db`,
`729fd1441d8c1446d665dddbc88cbd51d590fe729446bcdb8de1da61d88d74ac`,
`a7edfed29041ac9d144cd9cc95c385af76695ed92733c6ea5eccb2d472fb4562`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`ca05675b6e54507c94db6546219206f7f0acf2656fa052c644a97ce17848cdd0`,
`7cc9e6d5afafb3811da613528b570686a7ba74ff20a297f3a1908c8626a436b8`,
`6970c2f5a7e7922a41f33f145a0260ccb0946ed3218f39e978887ac69d4944c8`
and
`1048c6876853d5216194cc6d25aee5b1bcad8f2e886e5978ba98fbe9aa0d2eef`.

The next proof obligation is a volume-growing construction of the same
gauge-compatible retained family, followed by a bound on
$\alpha$, $\delta_Q$ and $\beta$ that is uniform in the outer cutoff, spatial
volume and weak-coupling trajectory.

## 48. Finite-volume C=0-to-C=1 Feshbach bridge

The frozen protocol
`computations/yang-mills-volume-feshbach-bridge-prereg.md` tests the
constant $C=0$ retained sector against the complete $C=1$ source space on
the seven-link two-plaquette graph and the open $3\times2\times2$ graph. The
outer dimensions are $4$ and $868$. After removing the ground direction and
retained source image, the post-ground-projection Feshbach block ranks are
$\dim\mathcal P=1$, $\dim\mathcal Q=2$ on the small graph and
$\dim\mathcal P=1$, $\dim\mathcal Q=866$ on the large graph. The fixed
coupling schedule is $x\in\{1/64,1/16,1/4,1\}$.

The primary receipt has status `PASS` with $84/84$ controls passing and
classification `SUPPORTS_FINITE_VOLUME_FESHBACH_BRIDGE`. All $8/8$ rows have
positive Schur roots. The independent arithmetic and source-binding receipt
has status `PASS` with $77/77$ checks passing without reassembling either
graph matrix.

| $x$ | small $\gamma/\Delta$ | large $\gamma/\Delta$ | large $\beta^2/(\alpha\delta_Q)$ | $\beta_{\rm large}/\beta_{\rm small}$ |
|---:|---:|---:|---:|---:|
| $1/64$ | 0.9975643387 | 0.9902557756 | 0.0000972544 | 4.0173181867 |
| $1/16$ | 0.9904908196 | 0.9623921662 | 0.0015517108 | 4.0219195972 |
| $1/4$ | 0.9655388367 | 0.8677618274 | 0.0237784983 | 4.0881757096 |
| $1$ | 0.9026891870 | 0.6114247979 | 0.2393160764 | 4.4501924266 |

The large-to-small ratios of $\alpha$ are
$1.0002268173,1.0036145449,1.0543966493,1.4708879563$, while the ratios of
$\delta_Q$ are
$1.0000271164,1.0004313948,1.0063264310,1.0417806625$. At $x=1$ on the
large graph, the receipt labels
$\alpha=5.8626424752$, $\delta_Q=3.7246287552$,
$\beta=2.2859890090$, $\beta^2/(\alpha\delta_Q)=0.2393160764$,
$\Phi(0)=4.4596178806$ and
$\gamma_{\rm Fesh}=2.2700426575$. The finite bridge survives this volume
change, while the constant retained sector has no volume-uniform estimate:
the coupling block grows by approximately four between the two graphs and
the large-graph root-to-gap ratio decreases at stronger coupling. A
volume-adapted retained family and uniform $\alpha$, $\delta_Q$, $\beta$
bounds are required before the volume bridge can enter a continuum
argument. Lattice-spacing, recovery, continuum and mass-gap claims remain
unresolved.

The source-binding order is protocol, primary source, independent source,
exact-block source, large-volume source, scientific large-volume protocol,
recovery protocol, recovered large-volume receipt, primary receipt and
independent receipt:
`43037cb97bfb68e3f3c55d1d5226a1e8ef5ace23261a48edc546dfa229728f58`,
`abba34224e95f3aab52b5cbc04b45997e575bfc615a998d783a8bb7fccac22e5`,
`6980c5418ca6894f8f6b73e99ecbba2eaba7fc7e301b8418a4160cd822aca473`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`87764d365f592b091a8006ed178b13ce9d2da2b519638d19b35d88c3762243af`,
`190081eb42bc82432033fc59f3bfb4386a74760f0f4b951ec46ad461a0f056f7`,
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`,
`914d4ed7da56b7e459a98ff83c08f21a8a7e12a211ace0074afd41d1f3e40837`,
`a86f3cf2fc53fdc0392431524c9b952c437fa468e5a7e292e3c0b593d53df066`
and
`b8ea5734ff2a38ac5a062ea2da8ca6f1ce540d15295f93f67c5dac1f978d8d98`.

The next proof obligation is a volume-adapted gauge-compatible retained
family whose $\alpha$, $\delta_Q$ and $\beta$ admit bounds uniform in spatial
volume, outer cutoff and the weak-coupling trajectory.


- `computations/yang-mills-volume-feshbach-bridge-prereg.md`—frozen finite-volume $C=0\to C=1$ Feshbach bridge protocol.
- `computations/verify_yang_mills_volume_feshbach_bridge.py`—84-check primary two-graph bridge verifier.
- `computations/verify_yang_mills_volume_feshbach_bridge_independent.py`—77-check independent arithmetic and provenance audit.
- `runs/yang_mills_volume_feshbach_bridge/verification.json` and `verification-independent.json`—source-bound finite-volume bridge receipts with positive roots on both graphs and unresolved volume-uniform, continuum and mass-gap bounds.

## 49. All-local-action volume-adapted family rank boundary

The frozen protocol
`computations/yang-mills-volume-adapted-feshbach-prereg.md` retains the
vacuum and every fundamental plaquette action on both graphs. The retained
source ranks are $3$ and $12$. On the seven-link graph the projected space
has dimension $3$, so $\mathcal Q$ has dimension zero at all four couplings.
The large graph has $\dim\mathcal P=12$ and $\dim\mathcal Q=855$.

The primary receipt has status `FAIL`, classification `INCONCLUSIVE`, $50$
controls and $46$ passing controls. Its four failed controls are the
small-graph nonempty-$\mathcal Q$ domain checks. The independent receipt
passes $53/53$ checks by reconstructing the ranks, null diagnostics,
classification and source bindings without matrix assembly. The candidate
remains a rank/domain boundary and supplies no finite Feshbach certificate.

The source-binding order is protocol, primary source, independent source,
primary receipt and independent receipt:
`c60e40885b46b8fe0feeb400b9a1ef7277b8957543a6bf378bdceb70e3c6e29a`,
`c445a6ce30041be632110bc67a5b07a6011996a387958559e00722b5181f49ba`,
`411bb3b004329f64820d2be5c68af2dd9df297363346171a45085ffd0d906b52`,
`78d9f3334a6c02fe5d6acf8ccab71da9d5021be01435968b2712995d911d1bb7`
and
`beee93c05469258ad9beec336f4a29fe04bf5e609fcfbeb2eedbdd52f54776b4`.

## 50. Reserved-plaquette volume-adapted family

The frozen protocol
`computations/yang-mills-volume-adapted-feshbach-v2-prereg.md` retains the
vacuum and every fundamental plaquette action except the final plaquette in
the source ordering. The retained source column counts are $2$ and $11$;
the post-ground-projection Feshbach ranks are $(2,1)$ on the small graph and
$(11,856)$ on the large graph.

The primary receipt has status `PASS` with $84/84$ controls passing and
classification `SUPPORTS_FINITE_VOLUME_RESERVED_PLAQUETTE_FAMILY`. All
$8/8$ rows have positive roots. The independent arithmetic and
source-binding audit passes $85/85$ checks.

| $x$ | large $\gamma/\Delta$ | large $\beta^2/(\alpha\delta_Q)$ | $\beta_{\rm large}/\beta_{\rm small}$ |
|---:|---:|---:|---:|
| $1/64$ | 0.9981978926 | 0.0006332943 | 11.1953568586 |
| $1/16$ | 0.9718452911 | 0.0100503642 | 11.0660830301 |
| $1/4$ | 0.7465837728 | 0.1222042415 | 9.5205046971 |
| $1$ | 0.3161143619 | 0.5343088125 | 5.7412930806 |

The reserved local rank grows with the graph and the finite bridge remains
positive. The coupling norm grows strongly between the two graphs, and the
large-graph strong-coupling ratio reaches $0.5343088125$. A volume-uniform
$\\beta$ bound remains open, as do the lattice-spacing, recovery, continuum
and mass-gap bounds.

The source-binding order is protocol, primary source, independent source,
v1 source, v1 protocol, v1 primary receipt, v1 independent receipt, volume
bridge source, exact source, large source, scientific large-volume protocol,
recovery protocol, recovered large-volume receipt, primary receipt and
independent receipt:
`cdba497b370abeb8fc5f00e3400095f428e8da7419919c203d36eef8e1a6f86a`,
`669af98b0d27a0bfa82255e2d86dde20c7240078746c1c6b96a988d1d9e91827`,
`a235b8b5cc37fe47e31440051835ab46efd8734a3816a080b1fd800a558c9488`,
`c445a6ce30041be632110bc67a5b07a6011996a387958559e00722b5181f49ba`,
`c60e40885b46b8fe0feeb400b9a1ef7277b8957543a6bf378bdceb70e3c6e29a`,
`78d9f3334a6c02fe5d6acf8ccab71da9d5021be01435968b2712995d911d1bb7`,
`beee93c05469258ad9beec336f4a29fe04bf5e609fcfbeb2eedbdd52f54776b4`,
`abba34224e95f3aab52b5cbc04b45997e575bfc615a998d783a8bb7fccac22e5`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`87764d365f592b091a8006ed178b13ce9d2da2b519638d19b35d88c3762243af`,
`190081eb42bc82432033fc59f3bfb4386a74760f0f4b951ec46ad461a0f056f7`,
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`,
`914d4ed7da56b7e459a98ff83c08f21a8a7e12a211ace0074afd41d1f3e40837`,
`e32deff2cc5c5f426d862ea057970065a30af6a1b8763994c66ed9519b8531ef`
and
`5e7a0341aaff8adf1bf1dff5a750b8a6e047e4a7def8947bbbded6b5ebde7cfd`.

The next proof obligation is a collective or block-local retained family
with a coupling norm bounded independently of spatial volume.

## 51. Collective plaquette volume screen

The frozen protocol
`computations/yang-mills-volume-collective-feshbach-prereg.md` retains the
vacuum and the arithmetic sum of every fundamental plaquette action. The
retained source rank is $2$ on both graphs; the post-ground-projection
Feshbach ranks are $(2,1)$ on the seven-link graph and $(2,865)$ on the open
$3\times2\times2$ graph.

The primary receipt has status `PASS` with $83/83$ controls passing and
classification `SUPPORTS_FINITE_VOLUME_COLLECTIVE_PLAQUETTE_FAMILY`. All
$8/8$ rows have positive finite Schur roots. The independent arithmetic and
source-binding audit passes $85/85$ checks.

| $x$ | large $\beta$ | large $\beta^2/(\alpha\delta_Q)$ | large $\gamma_{\rm Fesh}$ |
|---:|---:|---:|---:|
| $1/64$ | 0.6984316229 | 0.0541852424 | 2.3019975663 |
| $1/16$ | 0.7185809145 | 0.0571122893 | 2.2882584639 |
| $1/4$ | 0.9871161559 | 0.1011242513 | 2.1163501686 |
| $1$ | 2.9251978345 | 0.5011164193 | 1.1979260668 |

The small-graph $\beta$ is at the floating-point floor
($2.2\times10^{-16}$ at $x=1/64$ and $1/16$, below
$4.8\times10^{-15}$ at the remaining couplings). The resulting
large-to-small ratios are numerical-floor ratios, not evidence for a
volume-uniform bound. This screen therefore establishes a finite collective
family only; lattice-spacing, recovery, continuum and mass-gap bounds remain
open.

The source-binding order is protocol, primary source, independent source,
v1 source, v1 protocol, v1 primary receipt, v1 independent receipt, volume
bridge source, exact source, large source, scientific large-volume protocol,
recovery protocol, recovered large-volume receipt, primary receipt and
independent receipt:
`6e12006f984e4c50d20879811046f6a61095049baf2d8506c9f00e12d1e667c2`,
`a13a0168e368ad12782f7d357f917a68f85a0cfd6115ff7e5f6d3386c5760c0c`,
`ae7d3f48cbfb77df3cf1bb7bbee4b108a13c01ff6736d70bc58b163d18fc4a47`,
`c445a6ce30041be632110bc67a5b07a6011996a387958559e00722b5181f49ba`,
`c60e40885b46b8fe0feeb400b9a1ef7277b8957543a6bf378bdceb70e3c6e29a`,
`78d9f3334a6c02fe5d6acf8ccab71da9d5021be01435968b2712995d911d1bb7`,
`beee93c05469258ad9beec336f4a29fe04bf5e609fcfbeb2eedbdd52f54776b4`,
`abba34224e95f3aab52b5cbc04b45997e575bfc615a998d783a8bb7fccac22e5`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`87764d365f592b091a8006ed178b13ce9d2da2b519638d19b35d88c3762243af`,
`190081eb42bc82432033fc59f3bfb4386a74760f0f4b951ec46ad461a0f056f7`,
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`,
`914d4ed7da56b7e459a98ff83c08f21a8a7e12a211ace0074afd41d1f3e40837`,
`862995abaae19e31b2e4d739838f0239cf66e624846c7e776475d0f5244f306b`
and
`83bf85c07fb59cce1a683705af7c948386138ae4f982f30899ba740a82c10e93`.

The collective mode does not close the volume bridge: the small-graph
coupling is a numerical zero while the large-graph coupling is nonzero and
grows with the tested coupling.



- `computations/yang-mills-volume-collective-feshbach-prereg.md`—frozen equal-weight collective retained family and finite-volume decision tree.
- `computations/verify_yang_mills_volume_collective_feshbach.py`—83-check primary collective finite-family verifier.
- `computations/verify_yang_mills_volume_collective_feshbach_independent.py`—85-check independent arithmetic and source-binding audit.
- `runs/yang_mills_volume_collective_feshbach/verification.json` and `verification-independent.json`—source-bound finite collective receipts; the small-graph beta is at the numerical floor, so volume-uniform, continuum and mass-gap claims remain unresolved.
- `computations/yang-mills-volume-adapted-feshbach-prereg.md`—all-local-action retained family and explicit rank/domain decision tree.
- `computations/verify_yang_mills_volume_adapted_feshbach.py`—50-control primary rank-boundary receipt.
- `computations/verify_yang_mills_volume_adapted_feshbach_independent.py`—53-check independent audit of the rank-boundary receipt.
- `computations/yang-mills-volume-adapted-feshbach-v2-prereg.md`—reserved-plaquette retained family protocol.
- `computations/verify_yang_mills_volume_adapted_feshbach_v2.py`—84-check primary reserved-plaquette bridge verifier.
- `computations/verify_yang_mills_volume_adapted_feshbach_v2_independent.py`—85-check independent reserved-plaquette arithmetic and provenance audit.
- `runs/yang_mills_volume_adapted_feshbach_v2/verification.json` and `verification-independent.json`—source-bound finite reserved-plaquette receipts with unresolved volume-uniform, continuum and mass-gap bounds.

- `computations/yang-mills-volume-block-local-feshbach-prereg.md`—frozen anchored first-plaquette retained family and finite-volume decision tree.
- `computations/verify_yang_mills_volume_block_local_feshbach.py`—83-check primary anchored block-local finite-family verifier.
- `computations/verify_yang_mills_volume_block_local_feshbach_independent.py`—85-check independent arithmetic and source-binding audit.
- `runs/yang_mills_volume_block_local_feshbach/verification.json` and `verification-independent.json`—source-bound finite anchored block-local receipts; translation, continuum and mass-gap claims remain unresolved.

- `computations/yang-mills-volume-translated-block-feshbach-prereg.md`—frozen all-plaquette translated block sweep and 44-row decision tree.
- `computations/verify_yang_mills_volume_translated_block_feshbach.py`—455-check primary translated sweep verifier.
- `computations/verify_yang_mills_volume_translated_block_feshbach_independent.py`—375-check independent arithmetic and source-binding audit.
- `runs/yang_mills_volume_translated_block_feshbach/verification.json` and `verification-independent.json`—source-bound all-plaquette finite translated-family receipts; larger-volume and continuum claims remain unresolved.

## 52. Anchored block-local plaquette family

The frozen protocol
`computations/yang-mills-volume-block-local-feshbach-prereg.md` retains the
vacuum and the first source-order plaquette on both graphs. The retained source
rank is $2$ on both graphs; the post-ground-projection Feshbach ranks are
$(2,1)$ on the seven-link graph and $(2,865)$ on the open $3\times2\times2$
graph.

The primary receipt has status `PASS` with $83/83$ controls passing and
classification `SUPPORTS_FINITE_VOLUME_ANCHORED_BLOCK_FAMILY`. All $8/8$ rows
have positive finite Schur roots. The independent arithmetic and
source-binding audit passes $85/85$ checks.

| $x$ | large $\beta$ | large $\beta^2/(\alpha\delta_Q)$ | $\beta_{\rm large}/\beta_{\rm small}$ | large $\gamma_{\rm Fesh}$ |
|---:|---:|---:|---:|---:|
| $1/64$ | 0.0390807318 | 0.0001696380 | 4.7455417334 | 2.9614699937 |
| $1/16$ | 0.1563390545 | 0.0026998907 | 4.7447035122 | 2.8524006934 |
| $1/4$ | 0.6263718323 | 0.0399009617 | 4.7317300361 | 2.5059613297 |
| $1$ | 2.5587309590 | 0.3192237962 | 4.5974249526 | 1.9068853539 |

The measured coupling ratio remains in $[4.5974,4.7456]$ across the fixed
two-graph schedule, and the large-graph self-energy ratio remains below
$0.32$. This is a stronger finite-volume signal than the collective screen,
because the retained rank is fixed and the small-graph coupling is not a
numerical floor. Translation coverage, block-shape coverage, lattice-spacing,
recovery, continuum and mass-gap bounds remain open.

The source-binding order is protocol, primary source, independent source,
adapted source, adapted protocol, adapted primary receipt, adapted independent
receipt, volume bridge source, exact source, large source, scientific
large-volume protocol, recovery protocol, recovered large-volume receipt,
primary receipt and independent receipt:
`c8f5a6174d87d34eeb6ff4f03332719ccdde1d84dc26182929cf3d4fec41824f`,
`56cbb14dc965aa683120aa20914e750835348c5adb03740a4feffc36d6b45b2b`,
`8ea270f8109d84a289cd05f6e49353e326025a3e692b61b13b628b3cd7ff411b`,
`c445a6ce30041be632110bc67a5b07a6011996a387958559e00722b5181f49ba`,
`c60e40885b46b8fe0feeb400b9a1ef7277b8957543a6bf378bdceb70e3c6e29a`,
`78d9f3334a6c02fe5d6acf8ccab71da9d5021be01435968b2712995d911d1bb7`,
`beee93c05469258ad9beec336f4a29fe04bf5e609fcfbeb2eedbdd52f54776b4`,
`abba34224e95f3aab52b5cbc04b45997e575bfc615a998d783a8bb7fccac22e5`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`87764d365f592b091a8006ed178b13ce9d2da2b519638d19b35d88c3762243af`,
`190081eb42bc82432033fc59f3bfb4386a74760f0f4b951ec46ad461a0f056f7`,
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`,
`914d4ed7da56b7e459a98ff83c08f21a8a7e12a211ace0074afd41d1f3e40837`,
`fb73f1356fd9f69d2474ec73fa01b0082ced979a1b1756166298ebad22fad01b`
and
`8ba59d04bd286ff2cbdbe48e08ffcba273858036a19da68dc01d409d2ed2e0d3`.

The anchored block-local bridge is a finite positive result, not a continuum
mass-gap proof. The next obligation is to cover translated blocks and increase
the spatial volume without changing the retained rank.


## 53. Translated block-local sweep

The frozen protocol
`computations/yang-mills-volume-translated-block-feshbach-prereg.md` tests
the vacuum plus one plaquette separately for all eleven source-order
plaquettes of the open $3\times2\times2$ graph. Every family has source rank
$2$ and projected ranks $(2,865)$ at each coupling, for $44$ rows.

The primary receipt has status `PASS` with $455/455$ controls passing and
classification `SUPPORTS_FINITE_TRANSLATED_BLOCK_SWEEP`. All $44/44$ rows
have positive finite Schur roots. The independent arithmetic and
source-binding audit passes $375/375$ checks.

The eight $xy$ and $xz$ families are symmetry-equivalent, with maximum
$\\beta=2.5587309590$, maximum self-energy ratio $0.3192237962$ and minimum
certified root $1.9068853539$. The $yz_x1$ family has maximum
$\\beta=2.2721362582$ and minimum root $2.1238035176$. The outer $yz_x0$ and
$yz_x2$ families are worst:

| family | max $\beta$ | max $\beta^2/(\alpha\delta_Q)$ | min $\gamma_{\rm Fesh}$ |
|---|---:|---:|---:|
| $yz_x0$ | 2.6859149786 | 0.3487102889 | 1.8020569942 |
| $yz_x2$ | 2.6859149786 | 0.3487102889 | 1.8020569942 |

Across all eleven families the maximum coupling is $2.6859149786$, the
maximum self-energy ratio is $0.3487102889$, and the minimum root-to-gap ratio
is $0.9863223397$. Translation and orientation coverage therefore closes on
this finite graph without increasing retained rank. Larger spatial graphs,
lattice-spacing control, continuum recovery and the mass-gap theorem remain
open.

The source-binding order is protocol, primary source, independent source,
block-local source, block-local protocol, block-local primary receipt,
block-local independent receipt, adapted source, adapted protocol, adapted
primary receipt, adapted independent receipt, volume bridge source, exact
source, large source, scientific large-volume protocol, recovery protocol,
recovered large-volume receipt, primary receipt and independent receipt:
`41e212622f4b8b913d8a8f6977af08ec6a2ac29a41846fef649953186cc8f7de`,
`5b6c53cb13291172f8a8243b3446d517ef8cf212e2cec1127b2636c4c0b8289f`,
`f76b8417d4c26a94987fb109e4563b79caa254d4beb14a9744d61171918f6691`,
`56cbb14dc965aa683120aa20914e750835348c5adb03740a4feffc36d6b45b2b`,
`c8f5a6174d87d34eeb6ff4f03332719ccdde1d84dc26182929cf3d4fec41824f`,
`fb73f1356fd9f69d2474ec73fa01b0082ced979a1b1756166298ebad22fad01b`,
`8ba59d04bd286ff2cbdbe48e08ffcba273858036a19da68dc01d409d2ed2e0d3`,
`c445a6ce30041be632110bc67a5b07a6011996a387958559e00722b5181f49ba`,
`c60e40885b46b8fe0feeb400b9a1ef7277b8957543a6bf378bdceb70e3c6e29a`,
`78d9f3334a6c02fe5d6acf8ccab71da9d5021be01435968b2712995d911d1bb7`,
`beee93c05469258ad9beec336f4a29fe04bf5e609fcfbeb2eedbdd52f54776b4`,
`abba34224e95f3aab52b5cbc04b45997e575bfc615a998d783a8bb7fccac22e5`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`87764d365f592b091a8006ed178b13ce9d2da2b519638d19b35d88c3762243af`,
`190081eb42bc82432033fc59f3bfb4386a74760f0f4b951ec46ad461a0f056f7`,
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`,
`914d4ed7da56b7e459a98ff83c08f21a8a7e12a211ace0074afd41d1f3e40837`,
`60ea5429e842f75dba21d6c489f1e1b6b3b5b45e20f6e9ec8fcf12b50656a7e2`
and
`dbe8d8d185fa5a8a5e822570fa5fb313035b64c6a5e70c410d7b243e29fab11e`.

The finite translation sweep is evidence for a local retained construction,
not a volume-uniform or continuum mass-gap proof. The open $4\times2\times2$
$C=1$ screen in §54 extends the graph and source schedule, while its declared
test-energy qualification remains `INCONCLUSIVE`. A volume-uniform operator
bound or a residual-aware complement certificate is still required.


## 54. Open 4x2x2 C=1 sparse Feshbach screen

The frozen protocol
`computations/yang-mills-4x2x2-c1-feshbach-prereg.md` evaluates the
vacuum-plus-one-plaquette family on the open $4\times2\times2$ graph at
character cutoff $C=1$. The graph has $28$ links, $16$ vertices, $8$
four-valent sites, $16$ fundamental plaquettes and a complete
gauge-invariant basis of dimension $25{,}676$. The sixteen translated source
families have rank $2$ at each of four couplings, for $64$ rows.

The primary receipt has status `FAIL`, classification `INCONCLUSIVE`, and
$407/423$ controls passing. The independent arithmetic and source-binding
audit passes $531/531$ checks. All $64$ rows report positive conditional
zero-point roots, with values from $1.31898990696$ to $2.95378011172$ and
root-to-gap ratios from $0.3552036049$ to $0.9845023484$.

The sixteen failed primary controls are the declared test-energy conditions
at $x=1$: $\Phi_j(\Delta_x/2)$ ranges from $-2.0146598632$ to
$-0.7508664577$. The positive zero-point roots therefore do not qualify as a
translated-family result under this protocol. The screen provides an
independently audited larger-graph construction and an `INCONCLUSIVE`
conditional Feshbach result. Character-cutoff removal, volume-uniform
control, lattice-spacing control, continuum recovery and the Yang–Mills mass
gap remain unresolved.

The source-binding order is protocol, primary source, independent source,
exact tensor source, recovered large-volume source, recovered large-volume
protocol, primary receipt and independent receipt:
`a0fc940c6be1acde8e5365176471155635916ab54008ad2928c6e4187d282a6a`,
`ff957d5702f6e4c7326189104c163d1acf31a3806379f680833b0365f541c276`,
`06c385bae140ffdfd405e91f93b571aa3782ae4694031239477c117d570a0df7`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`87764d365f592b091a8006ed178b13ce9d2da2b519638d19b35d88c3762243af`,
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`,
`5ff6e3f5444125d0e42c611163fb42608419da71196635b213c30a05d8f39759`
and
`49c9d90848790d2a9f492e61f8be1e4009412ac205bb982f850a9bc4f880e272`.


## 55. Qualified simultaneous translated-block residual Gramian

The frozen protocol
`computations/yang-mills-simultaneous-residual-gramian-prereg.md` constructs
the eleven translated fundamental-plaquette residuals in one common
868-dimensional $C=1$ Hilbert space on the open $3\times2\times2$ graph. The
coupling schedule is $x\in\{1/64,1/16,1/4,1\}$, with equal weights
$w_p=1/11$.

The primary receipt
`runs/yang_mills_simultaneous_residual_gramian/verification-v4.json` passes
$50/50$ checks with classification
`QUALIFIED_FINITE_SOURCE_SECTOR_RECOVERY`. The minimum measured
source-sector floor is
$\gamma_{\min}^{Q,\mathrm{src}}=0.061191332082923884$. The full centered
$Q$ space has dimension $867$; the zero-extended residual family has rank
$11$, full-$Q$ floor $0$, and nullity $856$.

The selected larger-volume source artifact is finite qualified evidence with
$234/238$ checks. Its unresolved rows are
`tail_separation_C1_x0.25`, `tail_separation_C2_x0.25`,
`tail_separation_C1_x1.0`, and `tail_separation_C2_x1.0`, all
`TAIL_UNRESOLVED`. The original larger-volume receipt remains excluded from
this chain because its recovery-protocol binding is
`8ca8b34e5250b798fdb2e196e68d731a2b14f6c4e2b7a0fcf89e0db29f9264e7`; the
selected source artifact binds
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`.

The arithmetic audit
`runs/yang_mills_simultaneous_residual_gramian/verification-independent-v4.json`
passes $30/30$ checks with classification
`PRIMARY_RECEIPT_ARITHMETIC_AUDIT_PASS`. It reconstructs the serialized
primary Gramian, coverage matrix, weighted source spectrum, spatial probes,
and full-$Q$ rank boundary without importing the primary implementation. It
does not perform a second physical Hamiltonian solve.

The result establishes a qualified finite source-sector measurement. Its
scope ends before a full-$Q$ recovery floor, volume-uniform estimate,
thermodynamic limit, continuum construction, or Yang–Mills mass gap. The
continuum boundary audit remains `UNRESOLVED_CONTINUUM_PROBLEM` with Clay
verdict `NULL`.
The tracked manifest
`computations/yang_mills_simultaneous_residual_gramian_manifest.json` records
the hash-matched external source receipt and both generated v4 receipts.

The source-binding order is protocol, primary source, independent source,
larger source, exact helper, scientific larger-volume protocol, recovery
protocol, selected larger-volume receipt, primary receipt and independent
receipt:
`2ad2f0a5e67866bbea9253f14ffdd85e5e7a1f79ef816c3e654190274bbe187e`,
`34d952d1217cf44ccd1bba9e8f84e403e50e95ed66271b477314e7fc14f65ac2`,
`ec6082eea99502043a6c584de2483c632fc292eebc7d85895eb0a47d385e57e5`,
`87764d365f592b091a8006ed178b13ce9d2da2b519638d19b35d88c3762243af`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`190081eb42bc82432033fc59f3bfb4386a74760f0f4b951ec46ad461a0f056f7`,
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`,
`7bdf0c525976e6976ff4a510a429c8febc73a61278216f95cced57a7b0e7120b`,
`54bf58497458cfe59c155e4ad47e846223c5c478bec99197a7a5fd16c26aea68`
and
`2a6fc20fa5de2bd089ef353ba1c692c890544ad0503e14ad35a4069e41a4fb79`.

## 56. Finite plaquette-cyclic coverage screen

The frozen protocol
`computations/yang-mills-plaquette-cyclic-coverage-prereg-v3.md` measures the
cyclic subspace generated by ordered products of the eleven fundamental
plaquette multiplication operators on the recovered open $3\times2\times2$
graph at $C=1$. The complete gauge-invariant basis has dimension $868$, so
the centered $Q$ sector has dimension $867$. The schedule contains every
ordered word through degree three at
$x\in\{1/64,1/16,1/4,1\}$.

The primary receipt
`runs/yang_mills_plaquette_cyclic_coverage/verification-v3.json` records
$32/32$ arithmetic and source checks. Its coverage status is `FAIL` with
classification `PLAQUETTE_CYCLIC_COVERAGE_INCOMPLETE`. The cumulative
degree-three ranks are $665$, $779$, $804$, and $806$, leaving finite
deficiencies $202$, $88$, $63$, and $61$ respectively:

| $x$ | cumulative rank | $Q$ deficiency |
|---:|---:|---:|
| $1/64$ | $665$ | $202$ |
| $1/16$ | $779$ | $88$ |
| $1/4$ | $804$ | $63$ |
| $1$ | $806$ | $61$ |

The independent receipt
`runs/yang_mills_plaquette_cyclic_coverage/verification-independent-v3.json`
passes $20/20$ arithmetic-audit checks with classification
`PRIMARY_RECEIPT_CYCLIC_RANK_AUDIT_PASS`. It audits the serialized rank
arithmetic and performs no second Hamiltonian solve.

The degree-three family extends the tested plaquette source sector while
leaving a positive full-$Q$ deficiency at every scheduled coupling.
Higher-degree words, complete closed Wilson-word families, conditional
residual estimates, volume-uniform control, lattice-spacing control,
continuum construction and the Yang–Mills mass gap remain open.

The source-binding order is protocol, primary source, independent source,
larger source, exact helper, scientific larger-volume protocol, recovery
protocol, selected larger-volume receipt, primary receipt and independent
receipt:
`1c3d21817f6f62870c96a2bc38e02d480449946f7da74657d852a9e9b67da6f0`,
`42f7f6dc4584e15424c745fe5eb61fe8f455e3ae8911b3a1c88bbdf45a58fbdb`,
`02a8eed608e3c6ede449a7d02d147609e8617fe23d38ad48de87b8bd0017dccf`,
`87764d365f592b091a8006ed178b13ce9d2da2b519638d19b35d88c3762243af`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`190081eb42bc82432033fc59f3bfb4386a74760f0f4b951ec46ad461a0f056f7`,
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`,
`7bdf0c525976e6976ff4a510a429c8febc73a61278216f95cced57a7b0e7120b`,
`3eef6ca07115dba073821cb0d6140d1c5d1a86f97ea382299dda15fb2891206f`
and
`60d7410695091d99d2876ebefa656612cf9e9b4badbb8636aa315ef3d2e68172`.
The tracked manifest
`computations/yang_mills_plaquette_cyclic_coverage_manifest.json` records
these source and receipt hashes.

## 57. Finite plaquette-cyclic degree-four coverage

The frozen protocol
`computations/yang-mills-plaquette-cyclic-coverage-prereg-v4.md` measures the
cyclic subspace generated by every ordered product of the eleven fundamental
plaquette multiplication operators through degree four on the recovered open
$3\times2\times2$ graph at $C=1$. The complete gauge-invariant basis has
dimension $868$, so the centered $Q$ sector has dimension $867$. The coupling
schedule is $x\in\{1/64,1/16,1/4,1\}$, with degree word counts
$1,11,121,1331,14641$ and cumulative non-vacuum counts
$0,11,132,1463,16104$.

The primary receipt
`runs/yang_mills_plaquette_cyclic_coverage/verification-v4.json` records
$32/32$ arithmetic and source checks. Its coverage status is `FAIL` with
classification `PLAQUETTE_CYCLIC_COVERAGE_INCOMPLETE`:

| $x$ | degree-four rank | $Q$ deficiency |
|---:|---:|---:|
| $1/64$ | $861$ | $6$ |
| $1/16$ | $863$ | $4$ |
| $1/4$ | $863$ | $4$ |
| $1$ | $863$ | $4$ |

The independent receipt
`runs/yang_mills_plaquette_cyclic_coverage/verification-independent-v4.json`
passes $20/20$ arithmetic-audit checks with classification
`PRIMARY_RECEIPT_CYCLIC_RANK_AUDIT_PASS`. It audits the serialized rank
arithmetic and performs no second Hamiltonian solve.

The degree-four plaquette family reduces the finite deficiency at every
scheduled coupling but does not supply a full-$Q$ retained family. Complete
closed Wilson-word coverage, local conditional residual estimates,
volume-uniform control, lattice-spacing control, continuum construction and
the Yang–Mills mass gap remain open.

The source-binding order is v4 protocol, v4 primary source, v4 independent
source, degree-three baseline protocol, degree-three baseline source, larger
source, exact helper, scientific larger-volume protocol, recovery protocol,
selected larger-volume receipt, v4 primary receipt and v4 independent receipt:
`70a93fb4b1eeb31d674d3c86679193f6ddd9325a42cbb8ca59af0a6c92997bd4`,
`a299400291e2388e46a1e1292317793b2169c2f206b5d8e45ad942759b5c4673`,
`4c485df4ed24458e2c3701fc0c5faffe004558ed61284c92a3e4bb2680a02411`,
`1c3d21817f6f62870c96a2bc38e02d480449946f7da74657d852a9e9b67da6f0`,
`42f7f6dc4584e15424c745fe5eb61fe8f455e3ae8911b3a1c88bbdf45a58fbdb`,
`87764d365f592b091a8006ed178b13ce9d2da2b519638d19b35d88c3762243af`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`190081eb42bc82432033fc59f3bfb4386a74760f0f4b951ec46ad461a0f056f7`,
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`,
`7bdf0c525976e6976ff4a510a429c8febc73a61278216f95cced57a7b0e7120b`,
`0e0e2c01888f9566a20fc51a060409b4052be4acc39139e00c7e06267980e151`
and
`dcd7d3727fe14203ea1da2c69b46b23b801dfcb7a2484c0bbc04f6eb000398b6`.
The tracked lineage manifest
`computations/yang_mills_plaquette_cyclic_coverage_v4_manifest.json` records
the degree-three baseline, the degree-four sources and both finite receipt
sets.

## 58. Finite closed-Wilson simple-cycle coverage

The frozen protocol
`computations/yang-mills-closed-wilson-simple-cycle-coverage-prereg.md`
enumerates every canonical unoriented simple cycle of the recovered open
$3\times2\times2$ graph and adds the resulting variable-length Wilson
multiplication family to the degree-four plaquette products. The complete
$C=1$ basis has dimension $868$, so the centered sector has dimension $867$.
The inventory contains $3880$ rooted directed occurrences and $225$ canonical
classes, with length counts $11,36,72,84,22$ for lengths $4,6,8,10,12$.

The primary receipt
`runs/yang_mills_closed_wilson_simple_cycle_coverage/verification.json` has
status `FAIL` and classification
`CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_INCOMPLETE`. All $40/40$ primary checks
pass: the variable-length assembler agrees with all eleven length-four
plaquette matrices, a direct length-eight network sample agrees at all four
state pairs, and all $225$ matrices are finite and Hermitian. The augmented
family has $16329$ projected columns and ranks:

| $x$ | augmented rank | $Q$ deficiency | first full-rank block |
|---:|---:|---:|---|
| $1/64$ | $865$ | $2$ | none |
| $1/16$ | $867$ | $0$ | plaquette degree four |
| $1/4$ | $867$ | $0$ | plaquette degree four |
| $1$ | $867$ | $0$ | plaquette degree four |

The all-coupling rule therefore returns an incomplete finite family despite
full-$Q$ rank at three scheduled couplings. The independent receipt
`runs/yang_mills_closed_wilson_simple_cycle_coverage/verification-independent.json`
passes $24/24$ arithmetic-audit checks and does not perform a second
Hamiltonian solve. Repeated-edge and self-intersecting closed words remain
outside this family except for the retained plaquette products. Complete
closed-Wilson-word coverage, local recovery, volume-uniform control,
lattice-spacing control, continuum construction and the Yang–Mills mass gap
remain open.

The source-binding order is protocol, primary source, independent source,
degree-three baseline protocol, degree-three baseline source, degree-four
protocol, degree-four source, larger source, exact helper, scientific
larger-volume protocol, recovery protocol, selected larger-volume receipt,
primary receipt and independent receipt:
`d310ebe67f65f02f9dc2d74774b6fa2f2e461a58e8f070925613fb71edd20eb1`,
`36303bbbef83e314e2a9aecc43b60a60e435230f10370d36166dc9bdfcdc0e63`,
`abe11785850dd808c40eb711124364e6d0e0049df4ec6a48fe41397fa0bf2c49`,
`1c3d21817f6f62870c96a2bc38e02d480449946f7da74657d852a9e9b67da6f0`,
`42f7f6dc4584e15424c745fe5eb61fe8f455e3ae8911b3a1c88bbdf45a58fbdb`,
`70a93fb4b1eeb31d674d3c86679193f6ddd9325a42cbb8ca59af0a6c92997bd4`,
`a299400291e2388e46a1e1292317793b2169c2f206b5d8e45ad942759b5c4673`,
`87764d365f592b091a8006ed178b13ce9d2da2b519638d19b35d88c3762243af`,
`b3ed3a4af4b84e787180654fc7e863a61e8f79693c54b9f1efe75346996c8524`,
`190081eb42bc82432033fc59f3bfb4386a74760f0f4b951ec46ad461a0f056f7`,
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`,
`7bdf0c525976e6976ff4a510a429c8febc73a61278216f95cced57a7b0e7120b`,
`07d04859db731ff55de713f4551c41d6e608652928afa52fe0ba740a99ecfe60`
and
`54bdb0c79cef04bfdd75278ae5be23be13656a21413e5c5bd07111f2ad3befc8`.
The tracked lineage manifest
`computations/yang_mills_closed_wilson_simple_cycle_coverage_manifest.json`
records the same source and receipt hashes.

## 59. Finite closed-Wilson repeated-edge coverage

The frozen protocol
`computations/yang-mills-closed-wilson-repeated-edge-coverage-prereg.md`
defines the complete declared cyclically reduced fundamental Wilson family of
lengths $4$, $6$ and $8$, including the $55$ length-eight classes with repeated
edges or repeated vertices. It also includes the simple length-$10$ and
length-$12$ representatives and the ordered plaquette products through degree
four. The inventory has $4672$ declared rooted occurrences, $280$ canonical
representatives, and length counts $11,36,127,84,22$ for lengths
$4,6,8,10,12$. The repeated length-eight sector has $792$ rooted occurrences
and $55$ canonical classes.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Exact repeated-edge construction | The primary retains every loop occurrence at each active link, all bra and ket factors, all spectator intertwiner channels and the complete link-Haar contraction. All $225$ simple and $55$ repeated-edge matrices are finite and Hermitian; the sampled direct-network and reversal residuals are at most $4.44\times10^{-16}$ and $0$ | **PASS**, declared finite $C=1$ matrices |
| Primary verification | `runs/yang_mills_closed_wilson_repeated_edge_coverage/verification.json` has status `FAIL`, classification `REPEATED_EDGE_CLOSED_WILSON_COVERAGE_INCOMPLETE`, and passes all $41/41$ construction and arithmetic controls | **INCOMPLETE**, finite family and coupling schedule |
| Independent reconstruction | `runs/yang_mills_closed_wilson_repeated_edge_coverage/verification-independent.json` independently reconstructs the graph-walk inventory, word family, projected-column schedule, cumulative rank arithmetic, nullities and finite classifications; it passes $24/24$ checks without a second Hamiltonian solve | **PASS**, implementation-independent arithmetic audit |
| Augmented rank | The $16384$-column projected matrix has ranks $865,867,867,867$ at $x=1/64,1/16,1/4,1$, with deficiencies $2,0,0,0$; full rank first appears at the degree-four plaquette block for the last three couplings | **INCOMPLETE** under the all-coupling rule |
| Continuum boundary | The calculation fixes the graph, $C=1$ basis, coupling schedule, rank threshold and word family. It does not establish all-word local recovery, volume-uniform estimates, lattice-spacing control, a continuum construction, thermodynamic control or the Yang–Mills mass gap | **UNRESOLVED**, separate analytical obligations |

Repeated closed words do not remove the finite $1/64$ deficiency in this
declared family. The result ends the fixed stopping rule: no additional word
length, threshold tuning, coupling selection or family is added in response to
the rank. The tracked manifest
`computations/yang_mills_closed_wilson_repeated_edge_coverage_manifest.json`
binds the protocol, source files, reused finite-volume receipt and both new
receipts. The primary receipt SHA-256 is
`eb766044ee94e8eeb85e0a57a9b1c3fbf16d3d0f3de61815a42c9ad57801d7b8`; the
independent receipt SHA-256 is
`52767905974b485a90de899b6965fb95118b28bb0a8bb9cf30f78eb274a98a3f`.

## 60. Helical dynamic depletion stress test

The frozen protocol
`computations/navier-stokes-helical-dynamic-depletion-prereg.md` fixes eight
initial-data families on the $2\pi$-periodic torus at $\nu=1/10$ and horizon
$T=1/2$: the exact Beltrami control, four homochiral interacting modes,
opposite-helicity equal-energy modes, and five helical-tube families (wide,
narrow, tight-pitch, two-scale, opposite-handed). Each family runs at $N=16$
and $N=32$ with 1024 equal RK4 steps in float64, plus a 2048-step $N=32$
refinement: 24 declared executions with checkpoints at $t/T\in\{0,1/4,1/2,3/4,1\}$.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Exact control | The Beltrami field is a curl eigenmode, so the trajectory is the exact heat flow and $P(t)=0$ identically; the measured maximum absolute production over the 4099 recorded state evaluations of its three resolutions is $1.04\times10^{-33}$ with $H/C=1$ at both ends | **PASS**, exact closed-form control |
| Mode-family depletion | Homochiral modes reach $\max_tP=-1.16\times10^{-3}$ and opposite-helicity modes $-1.68\times10^{-2}$; both have $I_P(T)=0$ and stay nonpositive at every checkpoint | **PASS**, finite-horizon nonpositive families |
| Helical-tube families | Wide, narrow, tight-pitch, two-scale and opposite-handed tubes all carry positive signed production at every reported checkpoint from $t=1/8$ onward (from machine-level $P(0)\lesssim10^{-16}$) and end at $2.14\times10^{-3}$, $2.74\times10^{-3}$, $7.16\times10^{-3}$, $2.04\times10^{-3}$ and $6.40\times10^{-3}$ respectively | **CONTRADICTS**, declared finite families |
| Helicity independence | The opposite-handed family carries $H/C$ between $-4.7\times10^{-18}$ and $-9.7\times10^{-18}$, with positive signed production at every reported checkpoint from $t=1/8$ onward; the tight-pitch family crosses from $-2.4\times10^{-2}$ to $+4.5\times10^{-1}$ and is positive at those checkpoints | **CONTRADICTS** sign inheritance from helicity |
| Stressor response | Local positive stretching rises from $7.82\times10^{-2}$ (wide) to $3.94\times10^{-1}$ (narrow) under radius reduction; the tight-pitch family carries the largest initial direction variation ($D_\xi(0)=3.88$) and the largest signed maximum ($2.37\times10^{-2}$) | **PASS** measured, finite viscosity and horizon |
| Integrity | All $24/24$ executions complete: normalization $3.33\times10^{-16}$, divergence $2.86\times10^{-17}$, energy balance $3.55\times10^{-15}$, dissipation $0$, refinement $\le2.13\times10^{-8}$ and direct/spectral production $2.27\times10^{-13}$, against bounds $10^{-9}$ to $10^{-4}$ | **PASS**, declared truncations and step sizes |
| Continuum boundary | The matrix measures one viscosity, one horizon, two cutoffs and eight declared families. It supplies no cutoff-uniform estimate, no blow-up construction and no regularity statement | **UNRESOLVED**, separate analytical obligations |

The final classification is `CONTRADICTS`: coherent helical geometry,
including vanishing signed helicity, does not preserve a negative dynamical
stretching production in the declared families. The receipt
`runs/navier_stokes_helical_dynamic_depletion_20260914/verification.json`
binds protocol revision `A1` and source SHA-256 values
`f79715e30dde6765ee2854cf50e1ba30e4c6aaf1d1248fa2be9f78a460c314c8`,
`35779059e808acb791ce34294956003e4d18facc6d5d0676bf1673ec11624816`
and
`fc65487a5856ae3e4247ef7054ebce2201e9617c48bcf71e2ffaebe4c269e4b3`;
the receipt SHA-256 is
`5f04aa74490e32ca20ce101dafd634c38e6581e2ca3b62a3bb428bfcc21fc2bb`.

## 61. Band split of vortex-stretching production

The frozen protocol
`computations/navier-stokes-strain-band-split-prereg.md` splits the signed
stretching production of six declared families between the spectral strain
bands $|k|\le k_c$ and $|k|>k_c$ at the cutoffs $k_c\in\{2,4\}$, and reads its
classification from the $N=32$ primary run of every helical-tube family. The
schedule declares 18 executions: a primary run at each $N\in\{16,32\}$ and a
2048-step $N=32$ refinement for each family.

| Stage | Decisive result | Classification and scope |
|---|---|---|
| Completed execution | `timeout 12000 python computations/verify_navier_stokes_strain_band_split.py`, run unmodified from the repository root, exited 0 after 10711.57 s with all 18 declared executions and wrote `runs/navier_stokes_strain_band_split/verification.json` at `status=PASS` | `PASS` on the declared truncations and step sizes |
| Integrity | Receipt checks 10 of 10: declared run count 18, kinetic normalization $3.33\times10^{-16}$, Fourier divergence $2.86\times10^{-17}$, band identity $0$, band Parseval $2.08\times10^{-17}$, positive kinetic-energy increment $0$, energy-balance ratio $1.23\times10^{-15}$, timestep-refinement change $4.10\times10^{-7}$ against $10^{-4}$, Beltrami band control $7.10\times10^{-34}$ against $10^{-10}$ | Every gate inside its frozen tolerance |
| Earlier bounded attempt | The same script under a 3300 s bound completed five of the 18 declarations—the three `beltrami` declarations and both `helix_wide` primary declarations—and expired with exit code 124 inside the sixth at the printed progress `helix_wide N=32 time_refined step 1920/2048 (980s, 2.0 states/s)`, writing no receipt and fixing a 11880 s linear floor for the full schedule | No classification; superseded by the completed execution under a 12000 s bound |

The $N=32$ primary ratios, with $r_{\mathrm{high}}$ and
$r_{\mathrm{low}}$ as the protocol defines them:

| Tube family | $r_{\mathrm{high}}$, $k_c=2$ | $r_{\mathrm{low}}$, $k_c=2$ | $r_{\mathrm{high}}$, $k_c=4$ | $r_{\mathrm{low}}$, $k_c=4$ | Family verdict |
|---|---:|---:|---:|---:|---|
| Wide | 0.080289 | 0.919711 | 0.000000 | 1.102017 | SUPPORTS |
| Narrow | 0.493540 | 0.506460 | 0.049856 | 0.986010 | INCONCLUSIVE |
| Tight pitch | 0.874568 | 0.125432 | 0.403669 | 0.596331 | INCONCLUSIVE |
| Two scale | 0.093607 | 0.906393 | 0.000000 | 1.103970 | SUPPORTS |
| Opposite handed | 0.760908 | 0.239092 | 0.008912 | 1.491487 | INCONCLUSIVE |

The terminal classification is `INCONCLUSIVE`. No tube family satisfies
$r_{\mathrm{high}}>0.5$ at both cutoffs, which is what `CONTRADICTS` requires:
the tight-pitch family reads $0.874568$ at $k_c=2$ and $0.403669$ at
$k_c=4$, and the opposite-handed family falls from $0.760908$ to $0.008912$.
The `SUPPORTS` condition of $r_{\mathrm{high}}\le0.1$ and
$r_{\mathrm{low}}\ge0.5$ at both cutoffs holds for the wide and two-scale
families and fails for the other three, so the aggregate rule returns no
classification. Low-band fractions above one follow from the protocol's
normalization of each band by the positive part of the total production. This
record supplies a finite-family pattern at two cutoffs in one truncation pair,
one viscosity and one horizon; it carries no cutoff-uniform estimate, no
data-controlled bound on $\mathcal D_S(T)$, and no continuation claim.

## 62. Cutoff ladder of the vortex-stretching band split

The frozen protocol
`computations/navier-stokes-strain-band-split-cutoff-ladder-prereg.md` reads
the two-cutoff statistic at the ladder $k_c\in\{1,2,3,4,6,8\}$ from one $N=32$
primary trajectory per declared family at $\nu=1/10$, horizon $T=1/2$, grid
$M=193$ and 1024 equal RK4 steps in float64. Six executions carry the ladder,
because the split is a spectral reading of one flow: a further cutoff changes
neither the trajectory nor any other band's accumulation. The declared levels
are the frozen $r_{\mathrm{high}}>0.5$ and $r_{\mathrm{high}}\le0.1$, the
monotonicity tolerance is $0.05$, and the frozen two-cutoff receipt supplies
the reproduction gate.

| Stage | Decisive result | Classification and scope |
|---|---|---|
| Completed execution | `timeout 14400 python computations/verify_navier_stokes_strain_band_split_cutoff_ladder.py`, run unmodified from the repository root, exited 0 after 5447.87 s inside the declared 14400 s bound and wrote `runs/navier_stokes_strain_band_split_cutoff_ladder/verification.json` at `status=PASS` | `PASS` on the declared truncation and step size |
| Integrity | Receipt checks 13 of 13: six declared executions, six readings per accepted state, kinetic normalization $3.33\times10^{-16}$, Fourier divergence $2.63\times10^{-17}$, band identity $0$, band Parseval $4.16\times10^{-17}$, positive kinetic-energy increment $0$, energy-balance ratio $1.05\times10^{-15}$, Beltrami band control $6.50\times10^{-34}$ against $10^{-10}$ | Every gate inside its frozen tolerance |
| Frozen reproduction | Every $r_{\mathrm{high}}$ and $r_{\mathrm{low}}$ at $k_c\in\{2,4\}$ and every Beltrami band integral reproduces `runs/navier_stokes_strain_band_split/verification.json` with a difference of $0$, against tolerances $10^{-9}$ and $10^{-30}$ | The ladder is the frozen statistic read at four further cutoffs |
| Band passage | Every family is high-band dominated at $k_c=1$, from $0.607004$ to $0.973303$, and low-band dominated from $k_c=6$ onward | Finite-family cutoff dependence |
| Located crossovers | Wide and two-scale cross both levels inside the bracket $[1,2]$; narrow crosses the high level inside $[1,2]$ and the low level inside $[3,4]$ with $k_c=3$ intermediate; tight pitch crosses the high level inside $[3,4]$ and the low level inside $[4,6]$ with $k_c=4$ intermediate | Four located crossovers, two single-step and two gradual |
| Reversal | The opposite-handed family falls from $0.879386$ at $k_c=1$ to $0.008912$ at $k_c=4$ and rises to $0.062442$ at $k_c=6$, a rise of $0.053529$ that clears the frozen $0.05$ tolerance by $0.003529$, then falls to $0.001522$ at $k_c=8$ | One `non-monotone` family |
| Continuum boundary | Five declared families, one viscosity, one horizon and one truncation pair. The ladder supplies no cutoff-uniform estimate, no data-controlled bound on $\mathcal D_S(T)$ and no continuation statement | **UNRESOLVED**, separate analytical obligations |

$r_{\mathrm{high}}$ on the ladder:

| Tube family | $k_c=1$ | $k_c=2$ | $k_c=3$ | $k_c=4$ | $k_c=6$ | $k_c=8$ |
|---|---:|---:|---:|---:|---:|---:|
| Wide | 0.607004 | 0.080289 | 0.000000 | 0.000000 | $1.41\times10^{-20}$ | 0.000000 |
| Narrow | 0.836992 | 0.493540 | 0.147895 | 0.049856 | 0.000000 | $2.67\times10^{-18}$ |
| Tight pitch | 0.973303 | 0.874568 | 0.679457 | 0.403669 | 0.020242 | 0.021207 |
| Two scale | 0.625918 | 0.093607 | 0.000000 | 0.000000 | 0.000000 | $1.13\times10^{-19}$ |
| Opposite handed | 0.879386 | 0.760908 | 0.465760 | 0.008912 | 0.062442 | 0.001522 |

$r_{\mathrm{low}}$ on the ladder, with the protocol's normalization by the
positive part of the total production:

| Tube family | $k_c=1$ | $k_c=2$ | $k_c=3$ | $k_c=4$ | $k_c=6$ | $k_c=8$ |
|---|---:|---:|---:|---:|---:|---:|
| Wide | 0.392996 | 0.919711 | 1.144395 | 1.102017 | 1.011395 | 1.000648 |
| Narrow | 0.163008 | 0.506460 | 0.856587 | 0.986010 | 1.101164 | 1.054189 |
| Tight pitch | 0.026697 | 0.125432 | 0.320543 | 0.596331 | 1.100187 | 1.003334 |
| Two scale | 0.374082 | 0.906393 | 1.142274 | 1.103970 | 1.016723 | 1.002196 |
| Opposite handed | 0.120614 | 0.239092 | 0.534240 | 1.491487 | 0.944954 | 1.056591 |

The aggregate verdict read through the protocol's §4 rules is

```text
CONTRADICTS
```

One family carries the `non-monotone` class, the opposite-handed family, whose
rise of $0.053529$ between $k_c=4$ and $k_c=6$ exceeds the frozen $0.05$
tolerance after three earlier drops above it, so its passage is not a single
crossing of the levels and the frozen disagreement between $k_c=2$ and
$k_c=4$ is one segment of a curve that turns back up before it turns down
again. The other four families carry located crossovers: the two families whose
frozen classification agreed at both cutoffs, wide and two-scale, complete both
crossings inside $[1,2]$, so their agreement at $\{2,4\}$ records a crossing
that had already finished below $k_c=2$, while the narrow and tight-pitch
families cross gradually, with $k_c=3$ and $k_c=4$ respectively inside the
intermediate band. The verdict rule requires monotone cutoff dependence for
`EMERGES`, so this ladder returns no such reading; the crossover locations
stand as recorded above.

The ladder carries no $k_c=5$ point, so the shape of the opposite-handed
reversal between $k_c=4$ and $k_c=6$ is unresolved and its margin over the
tolerance is $0.003529$. The tail readings of the wide, narrow and two-scale
families are exact zeros and integrals at or below $10^{-19}$ of $I_P(T)$, so
their descent is a statement about vanishing high-band work rather than about a
measured tail. Low-band fractions above one, up to $1.491487$, follow from the
§1 normalization of each band by the positive part of the total production. No
outcome here changes the status of the active-dose and direction-coherence
obligations of `turbulence/navier-stokes-coherence-dose-criterion.md`, and the
near-field/far-field split of `turbulence/navier-stokes-stress-geometry.md`
§8.1 is a physical-space chart split with its own radius rather than a Fourier
band, so a crossing bracket locates a spectral reading and not a spatial
support.

## 63. The $\varphi$ ray and the conversion rate in the canonical two-fluid solver

The frozen protocol `computations/two-fluid-phi-ray-relaxation-prereg.md`
measures the framework's single postulate in the canonical conversion: the
volume ratio $R=\langle E_Y\rangle/\langle E_I\rangle$ against the fixed ray
$\varphi$, the fitted imbalance-decay rate $r_{\mathrm{fit}}$ against
$(1+\varphi)\lambda$, the conservation residual $\Sigma_{\mathrm{res}}$ and the
per-step closure $C$ of the predicted mean law, which are the structure's own
stated falsifiers. Sixteen declared runs carry two solver modes from five
declared compositions at $N=32$, $\lambda=0.1$, $\Delta t=0.002$ and $T=30$
against the solver `two-fluid/cassi_two_fluid_3d_gpu.py` bound by digest: the
ungated base form `TwoFluid3DGPU` and the $q$-gated static-box form
`ExpandingTwoFluid3DGPU` with `qi_gate=True`, `gate_model='single'`, $H_0=0$,
each with a ray control, plus a frozen-conversion control per mode at
$\lambda=0$, a step refinement, an $N=64$ resolution check, a $T=240$ gated
horizon and an unprojected-velocity sensitivity control. The declared
tolerances are $10^{-3}$ on $R_T/\varphi$, $10^{-4}$ on
$r_{\mathrm{fit}}/((1+\varphi)\lambda)$, $10^{-11}$ on $\Sigma_{\mathrm{res}}$
and $10^{-6}$ on $C$.

| Stage | Decisive result | Classification and scope |
|---|---|---|
| Completed executions | Two invocations of `timeout 10800 python computations/verify_two_fluid_phi_ray_relaxation.py` from the repository root, 2259.5 s and 1762.9 s, writing `runs/two_fluid_phi_ray_relaxation/verification_invocation1.json` at `status=FAIL` and `verification.json` at `status=PASS` | `PASS` on the second invocation; aggregate 4022 s inside the declared 21600 s cap |
| Integrity | Second receipt 11 of 11 gates: every constructed state equals its declared composition to $2.2\times10^{-16}$ relative, the worst initial minimum clears the step floor by a factor 24.2, the solenoidal residual of the fifteen projected runs is at most $1.5\times10^{-16}$, the refinement agrees to $3.4\times10^{-8}$, the mode-A weight identity holds exactly, and the solver digest matches its declared value | Every gate inside its frozen tolerance |
| Reproducibility | The two receipts agree in every recorded run scalar: 0 differences over the sixteen run records, their 2896 series rows, their 14416 fitted samples and their 96 checkpoints | Deterministic at these settings |
| Late readings, from the same two receipts | (i) The volume deviation is the $E_I$-weighted mean of the local $\delta=E_Y/(\varphi E_I)-1$ by identity, and the receipt's openness-weighted companion sits above it in every decisive gated run ($D_w-D$ from $+3.73\times10^{-5}$ at L1 to $+2.23\times10^{-3}$ at B1), identically at zero in the ungated mode and $-1.25\times10^{-2}$ in the frozen control: the departure is carried by the cells the gate weights down. B1's series peaks at $t=26.75$ s at $-2.482\times10^{-3}$ with the frozen horizon 0.5% past it; its lowest-openness quartile retains $0.85$ where its own openness permits $0.61$; L1's late volume rate $0.02955$ equals its gate-weighted $(1+\varphi)\lambda\Xi=0.02946$, its bands decaying in common proportion, and it crosses the ratio tolerance at $t=201$ s. (ii) The pre-amendment decision tree evaluated against the invocation-1 numbers yields `CONTRADICTS` on B1's unchanged $-2.4692\times10^{-3}$, with the two $\lambda=0$ controls additionally named by the old clause ($\{B1,C1,C2\}$ against $\{B1\}$), so the firing set contains B1 under both wordings and the one status an amendment changed is the construction gate, corrected rather than relaxed | Verdict unchanged and amendment-invariant: the gated displacement is a transient of the relaxation with a rate-ordered lag, not a freeze; no amendment touched a tolerance, a horizon, a matrix row or the firing clause, and no per-cell $\delta$ distribution or band mass is recoverable from the receipts. The two invocations are replicates—one measurement, repeated, under a rule extended after the first receipt—not two independent measurements |
| Mode-A ray | A2–A5 end at $R_T/\varphi-1=-1.94\times10^{-4}$, $-3.88\times10^{-4}$, $-5.62\times10^{-4}$ and $+1.74\times10^{-4}$, class `ray` | The fixed ray is confirmed off-ray in both directions at $N=32$, $T=30$ |
| Mode-A rate | All four decisive mode-A rates equal $0.261803387$ against $(1+\varphi)\lambda=0.261803399$, a factor $1-4.6\times10^{-8}$, class `rate_matches`; the near-ray local rate of A1 equals the prediction to $2\times10^{-8}$ | The rate law is confirmed at the projected RK2 bias |
| Mode-A conservation and closure | $\Sigma_{\mathrm{res}}\le1.1\times10^{-15}$ and $C\le1.7\times10^{-8}$, classes `exact` and `closure_holds`; the unprojected control M1 reaches $\Sigma_{\mathrm{res}}=1.24\times10^{-2}$ and $C=7.6\times10^{-4}$ with a solenoidal residual of 1.55 | Equal-and-opposite conversion holds where the velocity is solenoidal and moves where it is not |
| Gated rate | B2–B5 fit $0.0401$, $0.0482$, $0.0543$ and $0.0400$, from $0.153$ to $0.207$ of the prediction, class `rate_below_gated`; L1 at $T=240$ fits $0.031796$ | The gate-weighted mean law holds inside the declared band |
| Gated conservation and closure | $\Sigma_{\mathrm{res}}\le6.5\times10^{-13}$ and $C\le3.1\times10^{-9}$ in every gated run, classes `exact` and `closure_holds` | The gated weight identity holds per step, not only asymptotically |
| Gated ray | B2–B5 end between $-1.34\times10^{-1}$ and $+1.43\times10^{-1}$ of $\varphi$, class `approaching`; L1 reaches $-3.13\times10^{-4}$, class `ray` | The gated ray is reached inside $T=240$ and not inside $T=30$ from these states |
| Gated ray control | B1 starts exactly on the ray at $+2.2\times10^{-16}$ and ends $2.47\times10^{-3}$ below $\varphi$, class `departing`, while the ungated A1 from the same state holds $+2.2\times10^{-16}$ | One firing clause: the gated volume mean is not stationary on the ray at $N=32$ |
| Frozen controls | C1 and C2 hold their composition to $10^{-16}$, class `frozen`, with ratio and rate classes not applicable | The $\lambda=0$ reading is a control and not evidence about the ray |
| Gate sub-question | `gate_does_not_differentiate`: at the L1 final checkpoint the openness spans $0.0697$ to $0.2719$ about a mean of $0.1296$, the quartile local ratios read $1.617049$, $1.617451$, $1.617700$ and $1.618028$, and the weighted ratio sits $2.76\times10^{-4}$ from $\varphi$ | The gate orders the local fixed ratios monotonically without moving any quartile outside the frozen tolerance |
| Registered reference rate | L1's terminal segment rates are $0.02976$ and $0.02960$ against $\Gamma_0=\lambda/3=0.033333$; the receipt's measured weighting $\Xi=\langle w\varepsilon\rangle/\langle\varepsilon\rangle=0.11254$ gives $(1+\varphi)\lambda\Xi=0.029463$ | The registered value is the pointwise reference-density rate, and the volume mean follows the weighted form to $0.5\%$. The $(1+\varphi)$ factor in that form is the trace $\kappa(1+\varphi)$ of the declared conversion block, whose spectrum, characteristic polynomial and relaxation rate are functions of $a+b$ alone while the ratio lives in the null vector (`foundations/loop-rate-selection-candidates.md` §2.2; `foundations/phi-input-or-selection.md:177-181`), so this terminal rate witnesses the declared block's own sum rather than determining the ratio |
| Boundary | One solver mode of each declared form, one resolution with one refinement and one resolution check, one viscosity, horizons 30 and 240, amplitude $0.1$. The retained-band fraction of the imbalance is $1.0000$ at every checkpoint of every run | **UNRESOLVED**: the resolution and amplitude dependence of the gated displacement |

Volume ratio and rate per state, from the second receipt:

| Run | Mode | $R_0$ | $R_T$ | $R_T/\varphi-1$ | $r_{\mathrm{fit}}$ |
|---|---|---|---|---|---|
| A1 | ungated | 1.618034 | 1.618034 | $+2.2\times10^{-16}$ | ray control |
| A2 | ungated | 1.000000 | 1.617720 | $-1.94\times10^{-4}$ | 0.26180339 |
| A3 | ungated | 0.618034 | 1.617406 | $-3.88\times10^{-4}$ | 0.26180339 |
| A4 | ungated | 0.381966 | 1.617125 | $-5.62\times10^{-4}$ | 0.26180339 |
| A5 | ungated | 2.618034 | 1.618315 | $+1.74\times10^{-4}$ | 0.26180339 |
| B1 | gated | 1.618034 | 1.614039 | $-2.47\times10^{-3}$ | ray control |
| B2 | gated | 1.000000 | 1.400640 | $-1.34\times10^{-1}$ | 0.04009123 |
| B3 | gated | 0.618034 | 1.305781 | $-1.93\times10^{-1}$ | 0.04817116 |
| B4 | gated | 0.381966 | 1.266608 | $-2.17\times10^{-1}$ | 0.05428311 |
| B5 | gated | 2.618034 | 1.849493 | $+1.43\times10^{-1}$ | 0.04003847 |
| C1 | ungated, $\lambda=0$ | 2.618034 | 2.618034 | frozen | not applicable |
| C2 | gated, $\lambda=0$ | 0.618034 | 0.618034 | frozen | not applicable |
| R1 | ungated, $\Delta t/2$ | 0.618034 | 1.617406 | $-3.88\times10^{-4}$ | 0.26180340 |
| R2 | gated, $N=64$ | 0.618034 | 1.306061 | $-1.93\times10^{-1}$ | 0.04819081 |
| L1 | gated, $T=240$ | 0.618034 | 1.617527 | $-3.13\times10^{-4}$ | 0.03179604 |
| M1 | ungated, unprojected | 2.618034 | 1.618319 | $+1.76\times10^{-4}$ | 0.26102030 |

The aggregate verdict read through the protocol's §4 rules is

```text
CONTRADICTS
```

and it fires exactly one clause, the ratio clause, through the gated ray
control B1, whose volume ratio ends $2.47\times10^{-3}$ below $\varphi$ against
the frozen $10^{-3}$ tolerance. Every other clause is clear: no decisive
non-control run departs or sits stationary away from the ray, every decisive
mode-A rate is `rate_matches`, no decisive mode-B rate is `rate_above` or
`rate_below_unexplained`, every decisive closure holds, every decisive
conservation class is `exact`, and both frozen-conversion controls are
`frozen`. Of the `SUPPORTS` conditions only `gated_approach` fails, and it
fails on B1.

B1 is readable and the reading is the sub-question's content. Its state starts
exactly on the ray and its displacement grows to a plateau: $-9.0\times10^{-4}$
at $t=3.75$, $-1.51\times10^{-3}$ at $7.5$, $-2.20\times10^{-3}$ at $15$,
$-2.45\times10^{-3}$ at $22.5$, $-2.47\times10^{-3}$ at $30$. Over the same
interval the local imbalance amplitude falls from $1.14\times10^{-1}$ to
$3.83\times10^{-2}$ of $\langle\rho\rangle_0$, so the displacement is largest
while the local excursions are largest, and the gate's pointwise fixed set
$\varepsilon=0$ for every $w\ge0$ is untouched. What moves the volume mean is
the cross-correlation the spatially varying gate makes possible, and the
receipt carries its sign and size: the openness-weighted mean imbalance is
opposite in sign to the volume mean at late times, so
$\Xi=\langle w\varepsilon\rangle/\langle\varepsilon\rangle$ rises from $-0.82$
at $t=3.75$ through zero to $+0.0124$ at $t=30$. The same quantity fixes the
long-horizon rate: L1 reaches the ray at $-3.13\times10^{-4}$ with
$\Xi=0.11254$, and $(1+\varphi)\lambda\Xi$ reproduces its terminal segment rate
to $0.5\%$.

The registered reference-state rate $\Gamma_0=\lambda/3$ is the pointwise
ray-side value at the reference density, and the receipt separates it from the
volume mean: the measured openness at that checkpoint spans a factor of four
about a mean of $0.1296$, and the volume-mean rate is
$(1+\varphi)\lambda\Xi$ with the measured $\Xi$, below $\Gamma_0$ by the factor
$0.884$. Two invocations were needed because the first receipt's
`construction_floor_inactive` gate measured a threshold derived from an
incorrect sentence of the protocol rather than the construction, which carries
no clamp; the five in-place rule changes and the post-execution scope clause
added to §1, the retained first receipt and the reproducibility comparison are
recorded in the protocol's §1, §1.3, §2, §3, §4 and §6, and the second
invocation re-ran the identical matrix under identical tolerances, differing from the first in nothing measured. The provision that
permitted the second invocation was added to the protocol's §2 stopping rule
after the first receipt existed, and it is disclosed there as such: before it,
the rule allowed a re-run only after a timeout that wrote no receipt, under the
same aggregate cap. The two invocations are therefore replicates rather than
independent measurements—one measurement, repeated—and the reproducibility
comparison is what makes that checkable, since the receipts agree in every
recorded run scalar and differ only in the two $\lambda=0$ ratio classes and
the metadata.

No reading here changes the status of the conditional attractor row: the ray
and the rate are confirmed in the ungated form at $N=32$ and $T=30$, and the
gated form carries a measured finite-grid displacement of the volume mean,
$2.5\times10^{-3}$ at the declared horizon and $3.1\times10^{-4}$ at $T=240$,
whose resolution and amplitude dependence this schedule does not settle. The
displacement is transient rather than frozen: it peaks at $t\approx26.8$ s at
$-2.5\times10^{-3}$ and is carried by the cells the gate weights down, the
lowest-openness quarter of the field retaining $0.848$ of its deviation from
$t=3.75$ to $30$ where its own openness permits $0.608$, and the long-horizon
run is inside the $10^{-3}$ tolerance from $t=201$ s onward—so the declared
horizon of $30$ s samples a ray-initialized run at its plateau, and the
crossing near $t\approx58$ s obtained by extrapolating the stored rates is
arithmetic rather than a measurement. The
protocol measures one lattice resolution pair, one viscosity and one amplitude
band, and says nothing about the cascade law, the dark-energy or gravity
mappings, or any other place $\varphi$ appears.

## 64. Loop-carrier projection dynamics in the frozen discrete realization

The frozen protocol `computations/loop-carrier-projection-dynamics-prereg.md`
evolves the four-population law of
`foundations/loop-to-bubble-projection-theorem.md` on the discrete operators of
`computations/verify_loop_to_bubble_projection.py`, bound by digest, and
measures four things: whether the complete loop average of the evolved state
tracks the canonical two-density law at a ground-state and an excited profile
(LB8)--(LB14), whether that average survives repeated exterior transport, an
open and a closed gate and a truncated loop, whether the two declared loop
modes decay at the frozen spectral rates $2g_m$, and whether four controls can
witness a disagreement the probe is able to see. Fifteen declared executions
run at $N_\chi=24$, $\Delta t=0.05$ with halved refinements, exchange $0.6$,
seed imbalance $0.05$ on the three $J$-carrying arms and a composition split
on the covariance arm, each to its own converged horizon ($210.9$ to $1000$),
$232{,}334$ RK2 steps in total, one process, bound $5400$ s.

| Stage | Decisive result | Classification and scope |
|---|---|---|
| Completed execution | One invocation of `timeout 5400 python computations/verify_loop_carrier_projection_dynamics.py` from the repository root, 185 s measured outside and `runtime_seconds` 185.23 inside, writing `runs/loop_carrier_projection_dynamics/verification.json` at `status=FAIL` | Inside the declared bound with a factor 29 of headroom; the single invocation is spent |
| Integrity | 11 of 11 gates: annihilation $4.88\times10^{-15}$, idempotence $2.02\times10^{-16}$, `velocity_split` $0.0$ in nine contract arms, gate spread $0.0$, matched start $8.88\times10^{-16}$, declared shape 15, spectrum re-check at most $4.69\times10^{-16}$ against $10^{-9}$, sensitivity floor $8.51\times10^{-17}$ against $10^{-11}$, one process and no concurrent run | Every gate inside its frozen tolerance |
| Closure arms | $\rho_{\max}\le2.62\times10^{-15}$ and $\rho_{\rm final}\le2.22\times10^{-15}$ in thirteen of the fifteen arms — every arm but `covariance` and `direction_split`, whose disagreement is injected by construction — class `within_budget` | The evolved loop average tracks the canonical law at the arithmetic floor in thirteen of the fifteen arms |
| Refinement pairs | The two declared pairs reduce by $0.999987$ and $1.0000000000000058$ because both members already sit at the floor | Neither pair is `discretization_limited` and no arm is `structural_disagreement` |
| Loop modes | $\Delta_m$ $9.63\times10^{-12}$ and $9.63\times10^{-12}$ on the long arms and $7.28\times10^{-12}$ on the short one, against $10^{-6}$; fitted log-slope errors $2.54\%$ and $0.59\%$ against $10\%$; $w_m(T_{\rm mode})$ $6.79\times10^{-9}$ and $1.26\times10^{-25}$ against $10^{-3}$; $J$ at the horizon $1.49\times10^{-16}$ and $2.97\times10^{-17}$ | The two long arms relax at the frozen rates $2g_m$ |
| Feature F2 | F2 is true and **vacuous**: its condition quantifies over closure arms with $\rho_{\max}>10^{-6}$ and there are none | F2 carries no information about this family |
| Firing controls | `null` fired with $\Delta=0$ exactly and $\rho_{\max}$ $8.51\times10^{-17}$; `persistent_current` fired with $\rho_{\max}$ $1.23\times10^{-14}$ and domain-mean $J$ ratio $1.0000000000000036$ | Two of the four controls fire |
| Non-firing control, covariance | The (LB14) relative residual reads $4.31\times10^{-9}$ against the $10^{-12}$ bound and the terminal deviation $3.38\times10^{-8}$ against the $10^{-4}$ requirement, while the running maximum reaches $2.03\times10^{-3}$, two thousand times the requirement | The declared reading is the terminal state of an attracting relaxation; the relative residual divides by the quantity the control injects |
| Non-firing control, direction split | The terminal deviation reads $1.05\times10^{-14}$ against the $10^{-4}$ requirement, while the running maximum reaches $6.00\times10^{-4}$, six hundred times it | Same reading defect; its class `above_budget_no_partner` is a probe label §5.1 does not define, which is a protocol gap and not a reading |
| Persistent-current prediction | The max-abs current ratio ends at exactly $0.8333333333333374=1/1.2$, the flattened $20\%$ modulation, while the domain mean ends at $1.0000000000000036$ | Section 6A's amended prediction is confirmed, and F4 reads the domain mean |
| Boundary | Four discrete profiles at one rate set and one realization, $N_\chi=24$ with one halved refinement per profile pair, converged horizons $210.9$ to $1000$, one seed amplitude | **UNRESOLVED**: whether a control read on the running maximum rather than the terminal state fires. The successor protocol in §65 answers this in the affirmative on the spent traces themselves |

Projection residual per arm, from the receipt:

| Arm | Role | $\rho_{\max}$ | $\rho_{\rm final}$ | Class |
|---|---|---|---|---|
| `off_ray` | contract | $1.67\times10^{-16}$ | $7.93\times10^{-17}$ | `within_budget` |
| `off_ray_refined` | contract | $1.67\times10^{-16}$ | $0.0$ | `within_budget` |
| `on_ray` | contract | $1.01\times10^{-16}$ | $1.01\times10^{-16}$ | `within_budget` |
| `on_ray_refined` | contract | $1.01\times10^{-16}$ | $0.0$ | `within_budget` |
| `open_gate` | contract | $5.55\times10^{-17}$ | $5.55\times10^{-17}$ | `within_budget` |
| `closed_gate` | contract | $1.65\times10^{-16}$ | $8.88\times10^{-17}$ | `within_budget` |
| `loop_truncated` | contract | $2.76\times10^{-16}$ | $2.02\times10^{-16}$ | `within_budget` |
| `mode1_short` | mode | $3.40\times10^{-16}$ | $3.40\times10^{-16}$ | `within_budget` |
| `mode1_long` | mode | $2.62\times10^{-15}$ | $2.22\times10^{-15}$ | `within_budget` |
| `mode2_long` | mode | $2.22\times10^{-15}$ | $1.82\times10^{-15}$ | `within_budget` |
| `uniform_short` | mode | $8.51\times10^{-17}$ | $8.51\times10^{-17}$ | `within_budget` |
| `null` | control | $8.51\times10^{-17}$ | $8.51\times10^{-17}$ | `within_budget` |
| `covariance` | control | $2.03\times10^{-3}$ | $3.38\times10^{-8}$ | `above_budget_no_partner` |
| `direction_split` | control | $6.00\times10^{-4}$ | $1.05\times10^{-14}$ | `above_budget_no_partner` |
| `persistent_current` | control | $1.23\times10^{-14}$ | $1.05\times10^{-14}$ | `within_budget` |

The aggregate reading is

```text
FAIL
closure_verdict: null
mode_verdict: null
```

because F3 does not emerge, and the protocol withholds both verdicts on that
condition; F1, F2, F4, F5 and F6 are true and issue no verdict either, so none
of the five may be quoted as a verdict for either question. The FAIL is an
**instrument defect, not a theory null**. Both failing controls were built to
read one declared quantity at one declared horizon, and both read a
perturbation that the $\varphi$-ray had already absorbed: the probe's own
running maxima, $2.03\times10^{-3}$ and $6.00\times10^{-4}$, are two thousand
and six hundred times the $10^{-4}$ requirement, and the covariance control's
identity residual is relative to a denominator that shrinks with the content
the control injects, which is why a roundoff-level absolute residual reads
$4.31\times10^{-9}$. Nothing in this entry amends a criterion of the spent
protocol: it records what the run showed and leaves the FAIL standing as
measured.

The closure arms are the reason the entry is worth keeping. Thirteen of the
fifteen arms hold the complete-loop average of the evolved four-population
state on the canonical two-density trajectory at $10^{-16}$--$10^{-15}$ while
the arm list carries repeated exterior transport, an open and a closed gate and
a truncated loop; the two that do not are the controls whose disagreement is
injected by construction. The two long loop modes decay at the
frozen rates $2g_m$ to $2.54\%$ and $0.59\%$. That is an evolved reading where
the earlier evidence was a single-state identity check, and it is the reading a
successor control construction must be able to compare against without
re-deriving it on different machinery. No status moves: the physical carrier
identity, the QF1-to-carrier state map and the phase law remain exactly as
`open-questions-cassi-answers.md` and the theorem's result ledger leave them,
and this protocol measures one finite realization, one rate set and one seed
amplitude.

## 65. Loop-carrier projection relaxation: the repaired witness and the conversion rate

The successor protocol
`computations/loop-carrier-projection-relaxation-prereg.md` re-declares the
closure question of §64 and adds the question §64 could not answer. It runs the
same four-population law of `foundations/loop-to-bubble-projection-theorem.md`
on the same frozen discrete operators of
`computations/verify_loop_to_bubble_projection.py`, bound by digest, in sixteen
declared arms: the thirteen closure arms of the spent protocol with the same
step counts and horizons, and three new relaxation arms carrying the declared
seeds of §1.2 item 6. Two things changed and nothing else. Every arm now
records the witness $\rho_{\max}$, the peak over the whole trace of the relative
projection residual, where the spent protocol recorded only the terminal
$\rho_{\rm fin}$ of a relaxation that an attracting fixed ratio had already
damped; and the (LB14) identity is measured against the fixed absolute bound
$10^{-12}D_0$ with $D_0=\max(1,\langle\kappa^{\rm eff}\rangle_\chi(0)\,
\max_\chi|Z(0)|)$ taken at $t_0$, where the spent protocol divided by a
quantity that decays with the content the control injects. The relaxation
statistic is new: $\nu_{\rm fit}$ is the least-squares log-slope of
$\rho_k$ on $W=\{t_k\ge T/2,\ \rho_k>10^{-12}\}$, compared with the arm's own
conversion bracket $[\ell(c_-),1.1c_+]$ with $c_\pm$ from $\kappa^{\rm eff}$
(LR-A0), and the pair of arms differing in the gate scale $s$ alone tests
whether the rate scales with the conversion scale. Sixteen executions, one per
arm, $282{,}334$ RK2 steps ($132{,}334$ closure, $50{,}000$ each relaxation),
per-execution cap $50{,}000$, total cap $290{,}000$, one process, bound
$1200$ s.

| Stage | Decisive result | Classification and scope |
|---|---|---|
| Completed execution | One invocation of `timeout 1200 python computations/verify_loop_carrier_projection_relaxation.py` from the repository root, $236.4$ s measured outside and `runtime_seconds` $236.09$ inside, writing `runs/loop_carrier_projection_relaxation/verification.json` at `status=PASS` | Inside the bound with a factor $5.1$ of headroom, against the §6 projection of $225$ s; the single invocation is spent and no re-run is permitted |
| Integrity | 12 of 12 gates: annihilation $5.11\times10^{-15}$, idempotence $2.02\times10^{-16}$, `velocity_split` $0.0$ in the thirteen closure arms, closure gate spread $0.0$, matched start $8.88\times10^{-16}$, declared shape 16 with $282{,}334$ steps against $290{,}000$, spectrum re-check at most $4.69\times10^{-16}$ against $10^{-9}$, null-pair witness floor $8.51\times10^{-17}$ against $10^{-11}$ with $\Delta=0$ exactly, gate-11 reachability read before execution, one process and no concurrent run | Every gate inside its frozen tolerance, including the two gates the spent protocol could not have |
| Closure arms | $\rho_{\max}\le1.23\times10^{-14}$ in all thirteen closure arms, class `within_budget`; each reading **bit-identical** to the spent receipt's reading of the same construction | The evolved loop average tracks the canonical law at the arithmetic floor, now with all thirteen arms inside the budget and both verdicts issued |
| Refinement pairs | The two declared pairs agree at ratios $0.9999868475530246$ and $1.0000000000000058$, inside the factor $4$ of G2, with both members at the floor | G2 is not vacuous: it is applied to measured readings on both members of each declared pair, so the closure reading is the mechanism's and not the step size's |
| Repaired witness | `relax_reference` reads $\rho_{\max}$ $2.0326\times10^{-3}$ at $t=11.64$ against the $10^{-4}$ witness floor; `relax_scaled` $1.1055\times10^{-3}$ at $t=14.96$; `relax_split` $5.9981\times10^{-4}$ at $t=8.18$ | All three relaxation arms fire; H1 emerges |
| Repaired identity | (LR4) residuals $2.39\times10^{-18}$, $1.21\times10^{-18}$ and $1.10\times10^{-18}$ against the absolute bound $10^{-12}D_0$, $D_0=1.0$ | The identity that read $4.31\times10^{-9}$ in the spent run under a shrinking normalization now reads roundoff under a bound that cannot shrink |
| Relaxation rate | $\nu_{\rm fit}$ $1.1196\times10^{-2}$ inside (LR-R1) $[3.6411\times10^{-3},2.6284\times10^{-2}]$ for `relax_reference`, and $5.6160\times10^{-3}$ inside $[1.8205\times10^{-3},1.3142\times10^{-2}]$ for `relax_scaled`, each on $25{,}001$ samples of the declared window | H2 emerges: the tail decays inside the arm's own conversion bracket at both gate amplitudes |
| Scale clause | $\nu_{\rm fit}(\text{arm }15)/\nu_{\rm fit}(\text{arm }14)=0.5016205024503622$ against the declared band $[0.45,0.55]$ | H3 emerges: the rate scales with the conversion scale $s$ as the declared channels do, to $0.3\%$ of the factor $2$ the construction tests |
| Terminal-state reading | `relax_reference` ends at $\rho_{\rm fin}$ $3.38\times10^{-8}$ and `relax_split` at $1.05\times10^{-14}$—the spent protocol's own readings, bit for bit | The spent failure was the reading, not the trace: the terminal state of an attracting relaxation carries four orders of magnitude less than its peak |
| Recorded observation, not a criterion | $\nu_{\rm fit}/\ell=2.767368361056627$ and $2.776337415476921$ in the two covariance arms, with $\ell=c_-$ | Recorded only. The protocol nominates no dominant cell of the mixture, and $2.77$ is not $\varphi^2=2.618$ or any other declared constant; it gates nothing |
| Boundary | One finite realization at $N_\chi=24$, one rate set, one seed amplitude, four profiles at one $\chi$-resolution each with one halved refinement; the closure stays conditional on the common projected gate and the common exterior transport, and the four-population law stays the selected minimal member of a family any direction-mixing conversion with unit column sums joins | **RESOLVED**: §64's single unresolved boundary—whether a control read on the running maximum rather than the terminal state fires—is settled in the affirmative. **UNRESOLVED** and untouched: the physical carrier identity, the QF1-to-carrier state map, the phase law, the scale ratio and the quantum statistics |

Projection residual per closure arm, from the receipt (all class
`within_budget`, all bit-identical to §64's table):

| Arm | Role | $\rho_{\max}$ | $\rho_{\rm fin}$ |
|---|---|---|---|
| `off_ray` | contract | $1.665296162182208\times10^{-16}$ | $7.93\times10^{-17}$ |
| `off_ray_refined` | contract | $1.6653180651897577\times10^{-16}$ | $0.0$ |
| `on_ray` | contract | $1.0092936587501317\times10^{-16}$ | $1.01\times10^{-16}$ |
| `on_ray_refined` | contract | $1.0092936587501259\times10^{-16}$ | $0.0$ |
| `open_gate` | contract | $5.551115123125783\times10^{-17}$ | $5.55\times10^{-17}$ |
| `closed_gate` | contract | $1.653758697\times10^{-16}$ | $8.88\times10^{-17}$ |
| `loop_truncated` | contract | $2.758858630\times10^{-16}$ | $2.02\times10^{-16}$ |
| `mode1_short` | mode | $3.400322915\times10^{-16}$ | $3.40\times10^{-16}$ |
| `mode1_long` | mode | $2.622443970\times10^{-15}$ | $2.22\times10^{-15}$ |
| `mode2_long` | mode | $2.218991051\times10^{-15}$ | $1.82\times10^{-15}$ |
| `uniform_short` | contract, null pair | $8.505827589859918\times10^{-17}$ | $8.51\times10^{-17}$ |
| `null` | contract, null pair | $8.505827589859918\times10^{-17}$ | $8.51\times10^{-17}$ |
| `persistent_current` | persistence | $1.2313382636751607\times10^{-14}$ | $1.05\times10^{-14}$ |

The three relaxation arms, from the receipt:

| Arm | $s$ | $\rho_{\max}$ | peak time | $\rho_{\rm fin}$ | $\nu_{\rm fit}$ | (LR-R1) bracket | (LR4) residual |
|---|---|---|---|---|---|---|---|
| `relax_reference` | $1$ | $2.0326187974944866\times10^{-3}$ | $11.64$ | $3.376811012630109\times10^{-8}$ | $1.119569724312185\times10^{-2}$ | $[3.6411\times10^{-3},2.6284\times10^{-2}]$ | $2.39\times10^{-18}$ |
| `relax_scaled` | $\tfrac12$ | $1.1055338816802886\times10^{-3}$ | $14.96$ | $4.486540938158338\times10^{-6}$ | $5.615991276376917\times10^{-3}$ | $[1.8205\times10^{-3},1.3142\times10^{-2}]$ | $1.21\times10^{-18}$ |
| `relax_split` | $1$ | $5.998107249\times10^{-4}$ | $8.18$ | $1.0496654051001292\times10^{-14}$ | not fitted ($0$ samples) | not gated | $1.10\times10^{-18}$ |

The aggregate reading is

```text
PASS
closure_verdict: EMERGES
relaxation_verdict: EMERGES
```

The decisive point is a comparison of identical traces. The two repaired
controls are the spent protocol's two silent ones: `relax_reference` carries
the spent `covariance` construction and `relax_split` the spent
`direction_split` construction, on the same step size, horizon and seeds, and
their $\rho_{\max}$ and $\rho_{\rm fin}$ are bit-identical to the spent
receipt's—$2.0326187974944866\times10^{-3}$ and $3.376811012630109\times10^{-8}$
for the first, $5.998107249\times10^{-4}$ and $1.0496654051001292\times10^{-14}$
for the second. The spent probe had already computed and recorded these peaks;
its criteria read the terminal state instead, where the transient the control
injects has been absorbed, so both controls were silent and both verdicts were
withheld. Nothing in the carrier changed between the two runs: what changed is
that this protocol reads the quantity the witness needs, on a bound that cannot
shrink, and against a bracket declared before execution. The rate reading
follows from that: a deviation injected at the declared seeds peaks at
$2\times10^{-3}$ and its tail decays at $1.12\times10^{-2}$ per unit time,
inside the arm's own conversion bracket, while halving the conversion scale
halves the fitted rate to $0.5016$ of the reference. The mechanism the
canonical two-fluid probe measures and the mechanism this loop-carrier
statistic measures therefore agree in kind at these settings.

No status moves. The closure statement is the conditional one of the theorem:
it holds for this finite realization at one rate set and one seed amplitude,
with the common projected gate and common exterior transport assumed, and the
four-population law remains the selected minimal member of a family whose
columns sum to one, so the closure selects no member and separates no
conversion law. The relaxation statement is the weaker one: some declared
deviation from the canonical trajectory decays at the arm's own conversion
rates and that rate scales with that scale. It does not show that the
$\varphi$-ray's attraction is a property of the loop carrier rather than of the
conversion law the carrier shares, and no reading in this protocol is a value
of $\varphi$ that was not inserted by the protocol's own conversion bracket:
the closure arms sit at $10^{-17}$--$10^{-14}$, the arithmetic floor, and the
fitted rates are $1.12\times10^{-2}$ and $5.62\times10^{-3}$. The physical
carrier identity, the QF1-to-carrier state map, the phase law, the scale ratio
and the quantum statistics read exactly as they did before both protocols, and
the theorem's result ledger and the DQ and GQ physical-identification verdicts
are unchanged.

## 66. Loop-carrier projection split: an inert gate axis, a first-order transport axis

The protocol `computations/loop-carrier-projection-split-prereg.md` takes the
two assumptions §64 and §65 left standing—that both carriers see one common
projected gate and are advected by one shared exterior velocity—and splits one
at a time on the same four-population law, the same frozen discrete operators of
`computations/verify_loop_to_bubble_projection.py`, the same imported successor
code path, and the same seeds. Its statistic is the successor's own
$\rho_{\max}$, and the two split constructions are declared: the gate axis
offsets the two carriers' conversion fields by $\kappa(1\pm\delta_g\cos\chi)$,
the transport axis offsets their exterior velocities by $u(1\pm\delta_u)$, each
swept over six decades with a supersplit arm at $\delta=1$ and one comparability
arm on the successor's own orientation split. Nineteen declared arms, $3{,}450$
RK2 steps against a $6{,}000$ cap, per-execution cap $50{,}000$, one process,
bound $600$ s. This protocol is frozen with its executor: the text of sections
1–7 and the script are bound by digest before any arm is constructed, and the
script refuses to run on a binding mismatch, on an oracle mismatch against §65's
receipt, or on an existing receipt.

| Stage | Decisive result | Classification and scope |
|---|---|---|
| Completed execution | One invocation of `timeout 600 python computations/verify_loop_carrier_projection_split.py` from the repository root, $2$ s measured outside and `runtime_seconds` $2.34736967086792$ inside, writing `runs/loop_carrier_projection_split/verification.json` at `status=FAIL` | Inside the bound with a factor $256$ of headroom, against the §6 projection of $\approx3$ s; the single invocation is spent, and the receipt's existence now refuses a second in code |
| Integrity | 12 of 13 gates: binding exact on all five declared rows, annihilation $2.47\times10^{-15}$, idempotence $1.01\times10^{-16}$, matched start $2.22\times10^{-16}$, finiteness and nonnegativity, schedule conformance with no non-conformant arm, declared shape 19 with $3{,}450$ of $6{,}000$ steps, reference at the floor $5.33\times10^{-16}$ against $10^{-14}$, null pair $8.51\times10^{-17}$ with $\Delta=0$ exactly, cross-executor oracle bit-identical, reachability operands $0.125$ and $0.1868$ against $0.05$ and $0.10$, one process | Gate 11 fails: the gate axis's can-fail control does not fire, so the run ends at `FAIL` |
| Cross-executor oracle | `successor_replication` $2.622443969747147\times10^{-15}$ and `uniform_short` $8.505827589859918\times10^{-17}$, equal to §65's own readings of the same constructions, with $\lambda_{\max}$ $1.0331312281605476$ re-derived rather than read | The imported code path reproduces the successor's arms bit for bit, so the two runs measure the same instrument |
| Gate axis | All seven readings are $5.329147248815693\times10^{-16}$, the `common_reference` reading to the last digit, and so is every arm's terminal $\rho$ and loop content $0.12079677487732632$; $0$ of $6$ levels readable above $10^{-13}$; boundary `BELOW_ALL_LEVELS`, class `within_budget` at every level; the $\delta_g=1.0$ supersplit is the reference | **Measured and explained.** The axis is *inert*, not merely under the floor: with the carriers sharing a velocity, the conversion bracket $B=-\langle f_Y\rangle+\varphi\langle f_I\rangle$ is invariant under every other term of the right-hand side, the `on_ray` seed has $B=0$ exactly, and a split gate multiplies that zero. So this seed cannot measure a gate split at any $\delta_g$, and no order in $\delta_g$ is read. It is not evidence that a split gate is harmless |
| Transport axis | $6.799503171158458\times10^{-8}$ at $\delta_u=10^{-6}$ rising to $6.8205755240104814\times10^{-3}$ at $10^{-1}$, all six levels readable, fit coefficient $6.820388654045467\times10^{-2}$ with exponent $1.000205540897814$ and ratios $0.99694$–$1.00003$ inside the factor $2$ band, boundary `BRACKETED` with crossing $1.4661921053529064\times10^{-5}$ | First order in the declared offset on this realization, and the mechanism is the one the gate axis lacks: the differential velocity is the only term that generates $B$. **No law is issued**: §5's conjunction fails, so this is a recorded sweep, not a verdict, and no threshold was retuned to give it one |
| Supersplits | `supersplit_transport` $6.709984101592009\times10^{-2}$ against the $10^{-4}$ control bound, firing by $671\times$; `supersplit_gate` $5.329147248815693\times10^{-16}$, silent | The control that exists to prove an axis can move the statistic separates the two axes: one fires, one is inert. Its firing is what makes the `FAIL` a finding rather than a missing measurement |
| Comparability | `orientation_split_005` $3.263521392755\times10^{-4}$ against §65's own reading of the same geometry, `relax_split` $5.998107249\times10^{-4}$ at its own horizon $T=1000$ | Recorded, not a criterion: a hundred-step reading of the successor's split geometry is $0.544$ of the successor's, far above the class bound, so the statistic is not deaf to splitting as such—only to this gate split on this seed |
| Boundary | Nineteen arms at $N_\chi=24$, one rate set, one profile, one seed amplitude; the common gate and common transport stay assumed, not derived; the four-population law stays the selected minimal member of a family whose columns sum to one | **RESOLVED** by this run: a split gate on a seed that sits exactly on the conversion ray is invisible at every $\delta_g$, and the can-fail control caught it, so the protocol returned `FAIL` rather than a law about nothing. **UNRESOLVED**: whether a split gate degrades the projection at any level on any seed—not measured and not bounded here; a live measurement needs a seed carrying a nonzero conversion bracket, such as §65's own covariance construction |

The aggregate reading is

```text
FAIL
degradation_gate: null
degradation_transport: null
class: null
```

Neither verdict is issued, and the two nulls are the protocol's own rule rather
than a missing number: §5 makes `status=PASS` a conjunction over the gates and
hence over the features, and with the can-fail feature false the law-label
feature is false with it. `INCONCLUSIVE` is not issued for the gate axis either;
that label belongs to an axis whose readings exist but cannot be fitted, and the
gate sweep has no readable level at all. What the run records there is the
boundary label `BELOW_ALL_LEVELS` and the reason: the declared split multiplies
a conversion channel that carries no current on a seed on the ray.

What stands is narrow and worth stating exactly. The split statistic degrades at
first order in a differential exterior velocity on this finite realization—the
fitted exponent is $1.0002$ and the class bound $10^{-6}$ is crossed between
$\delta_u=10^{-5}$ and $10^{-4}$—and it does not respond at all to a differential
conversion gate on the same seed. The second is a statement about this seed's
placement on the ray, not a tolerance of the projection, since the channel the
split acts on is unloaded. Nothing here measures the conversion ratio, the value
of $\varphi$, the carrier identity, the QF1-to-carrier map, the phase law, the
scale ratio or the quantum statistics: the ratio enters only as the declared
entries of the four-population law, and §65's boundary and the theorem's result
ledger are unchanged.

## 67. Off the ray: a proportional gate axis and a linear load law

The protocol `computations/loop-carrier-gate-load-prereg.md` closes the row §66
left open: whether a split gate degrades the projection on a seed that is *not*
on the conversion ray. It keeps the carrier law, the frozen discrete operators,
the profile, the seed shape, the canonical companion, the integrator, the budget
and the stopping rule fixed, imports the spent protocol's split right-hand side
at a bound digest rather than re-deriving it, and loads the conversion bracket
$B=-\psi_Y+\varphi\,\psi_I$ by a declared, measured relative amount $\ell$
through a pure transfer between the two carriers that preserves the local total
and introduces no new mode. The statistic is the separation between a split arm
and its own unsplit twin, more than six class-bound widths above its own
reference floor by construction, read as a peak with the terminal value beside
it. Twenty-two declared arms: the six gate decades at the largest load, a
supersplit there, the ray seed as a declared $\ell=0$ control, five load levels
at $\delta_g=10^{-2}$, the successor's conversion-law replication and the spent
protocol's own short ray arm. $13{,}934$ classical RK4 steps against a total cap $30{,}000$
and a per-execution cap $50{,}000$, one process, bound $600$ s. This protocol is
frozen with its executor: the text of sections 1–7 and the script are bound by
digest before any arm is constructed, and the script refuses to run on a binding
mismatch, on an oracle mismatch against the two predecessor receipts, or on an
existing receipt.

| Stage | Decisive result | Classification and scope |
|---|---|---|
| Completed execution | One invocation of `timeout 600 python computations/verify_loop_carrier_gate_load.py` from the repository root, $9$ s measured outside and `runtime_seconds` $8.954417705535889$ inside, writing `runs/loop_carrier_gate_load/verification.json` at `status=PASS` | Inside the bound with a factor $67$ of headroom on the §6 projection of $\approx12$ s; the single invocation is spent, and the receipt's existence now refuses a second in code |
| Integrity | $13$ of $13$ gates and all six features: binding exact on all seven declared rows, state $\ge0.14656935329411563$, projection $\ge0.41142274608874574$, annihilation $\le3.26\times10^{-15}$, idempotence $\le1.67\times10^{-16}$, no non-conformant arm at $\Delta t=0.02$, declared shape $22$ with $13{,}934$ of $30{,}000$ steps, zero-split reduction residual $0.0$ exactly, one process | The instrument is licensed before any reading is taken |
| Pre-flight action | At $\delta_g=1$ the split moves the bracket's *rate* by $6.868880495192359\times10^{-3}$ of the right-hand side on the loaded seed against the floor $10^{-3}$, and by $4.199047857243002\times10^{-18}$ on the ray seed against the ceiling $10^{-15}$ | The check §66 lacked: the action, not the operand. Both directions carry more than an order of magnitude of margin, so neither can be satisfied by accident |
| Gate axis | $\sigma_{\rm peak}$ from $6.454373565784\times10^{-9}$ at $\delta_g=10^{-6}$ to $6.466800963652\times10^{-4}$ at $10^{-1}$, all six levels readable, fit coefficient $6.46326845434526\times10^{-3}$ with exponent $1.0001266948985081$ and ratios $0.9993984$–$1.0008385$ inside the factor $2$ band, boundary `BRACKETED` with crossing $\delta^\star=1.5489254257633844\times10^{-4}$ | **`PROPORTIONAL`.** First order in the declared split size on this realization, and the axis §66 called inert is live as soon as the seed is off the ray—the reading is the fix the boundary of §66 asked for |
| Load axis | At $\delta_g=10^{-2}$, $\sigma_{\rm peak}$ from $4.915584889131\times10^{-7}$ at $\ell=4.23\times10^{-3}$ to $6.455612516865\times10^{-5}$ at $3.65\times10^{-1}$, all six levels readable, fit coefficient $1.6438857835609873\times10^{-4}$ with exponent $1.0777928255642235$ and ratios $0.9033$–$1.1650$ inside the band, boundary `BRACKETED` with crossing $\ell^\star=8.791547515527859\times10^{-3}$ | **`LINEAR_IN_LOAD`.** The response per unit load rises monotonically from $1.162289769359\times10^{-4}$ to $1.770545846703\times10^{-4}$, a factor $1.523$ across the span, so the fitted $q$ sits $7.8\%$ above linear inside the declared $0.9\le q\le1.1$ band: the authority of the gate grows with how far the carrier sits off the ray, with a recorded convexity rather than a third law |
| Controls | `supersplit_load` $6.583063281834764\times10^{-3}$ against the $10^{-6}$ bound, firing by $6{,}583\times$; `ray_supersplit` $1.1102230246251565\times10^{-16}$ against the $10^{-14}$ floor; `ray_short` $5.329147248815693\times10^{-16}$ equal to §66's own `common_reference` reading; `successor_replication` $2.622443969747147\times10^{-15}$, terminal $2.219140084394095\times10^{-15}$ and $\lambda_{\max}$ $1.0331312281605476$ equal to §65's `mode1_long` | The can-fail control that failed in §66 now fires by four decades, the zero-load control is silent as declared, and both oracles are bit-identical to their bound receipts, so the two runs measure the same instrument on the same seeds |
| Peak and horizon | $t_{\rm peak}=10.66$ on the six largest-load decades and $10.98$ on the supersplit, against $T=12$; $\sigma_{\rm peak}/\sigma_{\rm terminal}$ $0.996342$ at $\delta_g=10^{-6}$ and $0.996437$ at $10^{-1}$, $0.999945$ at the smallest load | The statistic is a pair by construction: the terminal reading is a mildly late reading of the peak, and the peak is inside the horizon on the arm with the largest separation, so F6 holds and the horizon is not the reading |
| Boundary | Twenty-two arms at $N_\chi=24$, one profile, one seed shape, one split form (the $\cos\chi$ modulation alone), one rate set; the common gate and common transport stay assumed; the load is a single-parameter family of one shape, so its size is not separated from the shape carrying it | **RESOLVED** by this run: off the ray, a split gate's authority is first order in the split size and, to within $8\%$, first order in the bracket load, with both crossings sub-percent in their own axis. **UNRESOLVED**: whether the load law's convexity survives a different load shape, a refined $\chi$-resolution, or a longer horizon; and nothing here separates the load's magnitude from its spatial shape |

The aggregate reading is

```text
PASS
split_law: PROPORTIONAL
load_law: LINEAR_IN_LOAD
```

Both verdicts are issued, and the instrument that carries them is
$(\delta^\star,\ell^\star)=(1.5489254257633844\times10^{-4},\,
8.791547515527859\times10^{-3})$ at the declared floors and horizons: an
orientation-asymmetric gate keeps the separation inside the class bound for
$\delta_g\le1.5\times10^{-4}$ at the largest declared load, and at a fixed
$\delta_g=10^{-2}$ it takes a load of $\ell\ge8.8\times10^{-3}$ to reach it.
Both crossings sit below one percent in their own axis—$0.0155\%$ in the split,
$0.88\%$ in the load—so the projection tolerates about four decimal digits of
gate asymmetry at a strongly off-ray seed and about one and a half at a barely
loaded one.

What stands is narrower than the labels sound. The split coefficient is a
property of the declared block's trace and its own bracket, and $\varphi$ enters
only as the declared entries of the four-population law, which remains the
selected minimal member of a family whose columns sum to one: for a rank-one
conversion block the spectrum and the relaxation rate are functions of $a+b$
alone and the ratio lives in the null vector, so nothing here measures the
conversion ratio, the carrier identity, the QF1-to-carrier map, the phase law,
the scale ratio or the quantum statistics. The load is a departure of the
*carrier state* from the ray, not a physical density, current or field strength,
so the second fit describes this protocol's declared perturbation axis and not
any measured physical quantity. The transport axis is not re-opened: its
exponent $1.000205540897814$ and crossing $\delta_u=1.4661921053529064\times10^{-5}$
stand from §66, and the two axes remain separate readings of one statistic on
one realization.

## 68. The gate moves the loaded attractor; the run that would have certified it ended on a bookkeeping gate

The protocol `computations/loop-carrier-attractor-write-prereg.md` takes the
question §67 left standing: whether an asymmetric gate **moves** the composition
attractor the conversion rate reads, or only **shakes** the state while the ray
pulls it back. §67's readings were state-space separations over a fixed window,
and a window cannot tell a shifted attractor from a transient that has not yet
decayed. This protocol reads one trajectory at five horizons spanning $4.7$
relaxation times and fits

$$D(T)=D_\infty+(D_0-D_\infty)e^{-\nu T}$$

with $\nu$ held at the successor receipt's own fitted rate
$1.119569724312185\times10^{-2}$, so that the **offset**—not a ratio of two
readings—is the discriminator. Because a held rate wrong by a few percent makes
a pure transient look like an offset, every arm is fitted a second time with the
rate free, and a branch is issued only where the two agree; the self-check
exhibits the boundary as a witness, a pure transient $2.4\%$ off the clock whose
held fit reports an offset at $57\%$ of its terminal reading while the free fit
reports none.

| Reading | Value | What it closes |
|---|---|---|
| Branch, seven declared split sizes | all seven `PERSIST`: $\delta_g$ from $10^{-6}$ to $1$ at the largest load, held offsets from $-3.196567330\times10^{-10}$ to $-5.800237159\times10^{-4}$, the terminal reading $96$–$104\%$ offset at every level, free-fit offsets within $1\%$ of the terminal, residuals $0.010$–$0.076$ against a band of $0.25$ | On this realization the gate does not merely perturb: a reading decaying at the realization's own clock falls by a factor $21$ across the horizon pair, and none did—the recorded two-horizon ratios sit at $1.011$–$1.037$ against a transient prediction of $0.0487$ |
| Law and instrument | $|D_\infty|=(4.3424057234641914\times10^{-4})\,\delta_g^{1.0302448806878108}$ over the seven arms, per-level ratios $0.853$–$1.336$, label `PROPORTIONAL`, instrument $\delta_w=4.129022977646817\times10^{-9}$ | The shifted attractor's distance is proportional to the declared split size over seven decades to within three percent; the same fit on the free offsets gives $1.03110$ and on the terminal readings $1.02917$, so the law is not an artifact of which fit was fitted |
| Clock, ray, oracles | anchor's fitted $\rho$ rate $1.1375969997251654\times10^{-2}$ over $[30,450]$, a factor $1.0161$ from the receipt's rate read live from that receipt; `ray_supersplit` $\Delta$ exactly $0.0$ at all five horizons with peak $3.3306690738754696\times10^{-16}$; `ray_short` and `successor_replication` bit-identical to their bound receipts; zero-split reduction exactly $0.0$ | The classification's clock is the realization's own, the ray is inert to the bit at the largest declared split, and both oracles measure the same instrument on the same seeds |
| Verdict | **none.** `status=FAIL`; gate 12 (`anchor at the ray`) read `null`; `verdicts.write`, `verdicts.law` and `verdicts.instrument` all null; fourteen of fifteen gates passed | The protocol's own rule withholds a verdict on a failed gate, and the failed gate is the one that charges an offset to the split rather than to a reference still relaxing |
| The amendment reading | The anchor's $\max|\varepsilon|/\max|\rho|$ at $T_{\max}$, measured outside the run on the same arm, seed, split, schedule and step: $1.3442651683720991\times10^{-3}$, inside the declared tolerance $5\times10^{-3}$ by a factor $3.7$, with the arm's $\rho_{\rm final}$ reproducing the run's own $8.308015639801732\times10^{-4}$ | Read as an amendment and not as a gate value: it says the failure was a slip in the executor—the reader recorded each arm's distance from the ray only for arms carrying a twin, so the reference the sweep is measured against carried none—and not a state that was found off the ray. The corrected executor is re-anchored in §0 beside the digest it had at the invocation, its frozen body is unchanged, and the receipt refuses a second invocation |
| Boundary | Nineteen arms at $N_\chi=24$, one rate set, one profile, one seed and its declared load, five horizons read from one run per arm, one protocol invocation; the common gate and common transport stay assumed, not derived; the load is a departure of the carrier state from the ray, not a physical density or current | **RESOLVED in measurement, not in verdict**: on the declared seeds an asymmetric gate shifts the composition attractor by an amount proportional to the split, and the split is exactly inert on the ray, so the channel §66 found dead on the ray is a *writing* channel off it. **UNRESOLVED**: the certification itself, because the attribution gate was unreadable in the one run this body allows; and whether the shifted offset endures on horizons longer than $5$ relaxation times, which this protocol's declared set does not reach |

What stands is narrower than the labels sound. The offset is the difference of
one coordinate on one finite realization, and for a rank-one conversion block
the spectrum and the relaxation rate are functions of $a+b$ alone while the ratio
lives in the null vector, so nothing here measures the conversion ratio, the
carrier identity, the QF1-to-carrier map, the phase law, the scale ratio or the
quantum statistics; $\varphi$ enters only as the declared entries of the
four-population law. The free fit's rate is at the edge of its declared scan on
all seven persisting arms, which is recorded rather than gated: when an offset
dominates a reading, the free rate is not identified, and it enters only the
transient clause. The instrument $\delta_w$ is a property of this declared axis
on this seed family and not a threshold of the projection. The exponent $1.0302$
is the measured one and not one; on the six decades below the largest split the
design probe measured $1.0051$, and the difference is that one extra level.

## 69. The gate writes, and the carrier keeps it: a certified write and a retained offset

The successor body `computations/loop-carrier-attractor-write-successor-prereg.md` takes
both questions §68 left standing at once. §68 measured a write it could not certify: every
one of its seven declared split sizes persisted at $96$–$104\%$ of its terminal reading
against a transient prediction off by a factor $21$, and the run that measured it ended on
an unreadable attribution gate, so no verdict was issued. The successor keeps that body's
arms, seed family, five horizons, two fits, law, instrument and branch rule, fixes the
reading the gate needed—every arm's own distance from the ray, the anchors included—runs
the two unsplit references over the hold **and** the release span so that one run of each
serves both families as their reference, and puts the second question beside the first:
hold the split to $T_{\rm hold}=450$ (five relaxation times, so the write is established to
below one percent of its own transient), **remove it**, and integrate on for five further
horizons spanning the same $4.7$ relaxation times with the rate held at the successor
receipt's own measured $1.119569724312185\times10^{-2}$. A displacement that survives the
removal is stored; one that decays back at the measured clock is a driven state that exists
only while the gate is held. Seventeen arms, $496{,}934$ steps, one invocation, $321.0$ s of
the declared $900$ s.

| Reading | Value | What it closes |
|---|---|---|
| Write verdict | `WRITES`. All seven declared split sizes `PERSIST` at the largest load, held offsets $-3.1965673301338663\times10^{-10}$ to $-5.8002371593543804\times10^{-4}$, $96.0$–$97.9\%$ of the terminal reading with both fits agreeing, free-fit offsets within $1.4\%$ of the terminal | The gate displaces the composition attractor rather than only shaking the state, now on a run whose attribution gate is readable: the loaded anchor's own distance from the ray is $8.439048206843707\times10^{-6}$ at its final state and $1.3442651683720991\times10^{-3}$ at the hold horizon, the value §68's amendment measured outside its run, so the offset is charged to the split and not to a reference still relaxing |
| Law and instrument | $\lvert D_\infty\rvert=(4.3424057234641914\times10^{-4})\,\delta_g^{1.0302448806878108}$ over the seven arms, per-level ratios $0.8526$–$1.3357$, decade jumps $10.000$–$16.796$, label `PROPORTIONAL`, instrument $\delta_w=4.1290229776468171\times10^{-9}$ | The displaced attractor's distance stays proportional to the declared split over seven decades; the write family is the predecessor's measurement rather than a new one, checked arm by arm—$132$ horizon-indexed readings over twelve arms, $0$ mismatches |
| Retention verdict | `STORES`. All four declared levels `RETAINED`: after the split is removed the offset stands at $1.021414$, $1.039236$, $1.042386$ and $1.042726$ of what family (i) wrote, held and free fits within $4\times10^{-5}$ of each other, residuals $4.7\times10^{-6}$–$8.0\times10^{-6}$ and $5.9\times10^{-8}$–$8.6\times10^{-8}$ against a band of $0.25$ | The new reading: the asymmetry's effect is **not** undone by removing the asymmetry. Over the release window the reading moves by $5.7\times10^{-5}$–$3.9\times10^{-4}$ of itself, where a state decaying at the measured clock would have fallen by a factor $e^{\nu\,420}=110$ |
| Joint label | **`memory`**—`WRITES` with `STORES` | On this realization the gate is not a knob that acts only while it is turned: what it writes, the carrier keeps after the writing stops |
| Controls, both families | `ray_supersplit` $\Delta$ exactly $0.0$ at all five horizons with peak $3.3306690738754696\times10^{-16}$; `retain_ray` exactly $0.0$ in both phases; can-fail peaks $5.9240187127518329\times10^{-4}$ and $5.9244224877041951\times10^{-4}$ | The channel stays exactly inert on the ray in both phases, so the retention family's reading is the split's, and the instrument fires at the largest split in both phases |
| Shared construction | All five retention arms' held-phase readings bit-identical to the write arms' at the same split size ($5$ pairs, $0$ mismatches), and the four retention offsets equal to the design probe's declared literals | The second family is the first family's construction plus a removal, not a second measurement of a second thing—and the design probe's predicted outcome is reproduced by the run rather than asserted |
| Clock, oracles, action | Anchor's $\rho$ rate $1.1375969997251654\times10^{-2}$ (ratio $1.0161$) over $[30,450]$ and $1.1268285328754471\times10^{-2}$ (ratio $1.0065$) over the release window $[480,900]$, both against the receipt's rate read live; `ray_short` and `successor_replication` bit-identical to their bound receipts; the split's action $5.3390731361887128\times10^{-2}$ of the step's own drift at the largest load and exactly $0.0$ on the ray seed; zero-split reduction exactly $0.0$ elementwise | The clock the release is measured against is the realization's own in **both** phases; both oracles measure the same instrument on the same seeds; the axis is live where the sweep reads it and inert where the control says it must be; and the release removes a term rather than swapping in a different dynamics |
| Verdict | `status=PASS`, all twenty-two gates and all thirteen features, the single invocation §0 permits | §68's failure was a bookkeeping slip, and this body carries it as a declared correction rather than as a rescue: the gate that failed there now reads its own run's number and agrees with the amendment at the declared precision |

What is recorded and not gated, because it is a property of this realization rather than of
the claim: the release-phase free fit's rate is $1.71$–$1.80$ times the measured clock—slower
than the clock but inside the declared band—and when an offset dominates a reading the free
rate is not identified, so it enters only the transient clause; the release-phase offsets sit
slightly *above* the write family's own shares because the released trajectory continues its
transient for a while after the removal before it saturates; the receipt also carries a
retention-family law fitted over the four graded levels
($(5.138283027628463\times10^{-4})\,\delta_g^{1.0777123093106087}$, instrument
$8.266215754275881\times10^{-9}$), which §2 does not declare and which enters no verdict
clause; and what is retained is the composition coordinate's difference, a conserved
conversion level rather than a state off the ray—the loaded anchor's own distance from the
ray falls from $1.3442651683720991\times10^{-3}$ to $8.439048206843707\times10^{-6}$ across
the hold and release spans, so the released arms are back on the ray while their composition
coordinate stays displaced.

**RESOLVED in measurement and in verdict**: on the declared seeds an asymmetric gate shifts
the composition attractor by an amount proportional to the split over seven decades, the
split is exactly inert on the ray, and the shift is **not** undone by removing the
asymmetry—five relaxation times after the removal the offset stands at $1.02$–$1.04$ of what
the gate wrote, where a driven state would have fallen by a factor $110$. **Not resolved**:
whether the retained offset endures on horizons longer than five relaxation times, whether
it is readable in any other observable, and whether it means information rather than one
coordinate's displacement. The labels `STORES` and `memory` are branches of a decision rule
on a declared coordinate on one finite realization: one profile, one seed family, one
declared load, one rate set, one common gate and one common transport, both assumed and not
derived. For a rank-one conversion block the spectrum and the relaxation rate are functions
of $a+b$ alone and the ratio lives in the null vector, so nothing here measures the
conversion ratio, the carrier identity, the QF1-to-carrier map, the phase law, the scale
ratio or the quantum statistics; $\varphi$ enters only as the declared entries of the
four-population law.

## 70. One carrier, how many coordinates? The χ-resolved composition profile has one retained writable coordinate

§69 certified that the gate **writes** a retained offset and that the carrier **keeps** it—on a
single conserved conversion level, the exterior mean $A$ of the bounded composition. A
coexistence test read on that scalar can only ever return "it adds": two writes into one
conserved quantity have nowhere else to go. That is the shape of the spent gate axis, which
had no way to act at all, and it would have produced a clean, confident, meaningless
"coexistence confirmed." The body `computations/loop-carrier-composition-coexistence-prereg.md`
therefore reads the carrier where the declaration itself resolves it—the χ-resolved
per-orientation composition profile $c_{s,k}$ over the $24$ declared loop samples, partitioned
by the field's own orientation symmetry into an even group $e_k=(c_{+k}+c_{-k})/2$ and an odd
group $o_k=(c_{+k}-c_{-k})/2$—and writes **two** declared directions into it at the largest
declared magnitude $\delta=1$: **A**, the established write, offsetting the conversion field by
$\delta\cos\chi$ between the two carriers (orientation-blind, group $e$), and **B**, new,
offsetting it by $\delta\,s\cos\chi$ between the two *orientations* of each carrier (group
$o$). Direction A reduces to the successor's own right-hand side term for term
(`array_equal`, checked in the self-check). Before a single trajectory, the executor reads both
directions' action on the loaded seeded state, in both directions, with a no-write null; and if
the two are not distinguishable it reports the reservation and closes there—no re-tuning of the
observable, no hand-built basis the field does not expose. Eight arms, $472{,}600$ steps, one
invocation, $305.6$ s of the declared $900$ s.

| Reading | Value | What it closes |
|---|---|---|
| Pre-flight, both directions, on the seeded state | Live A $2.5753540367077486\times10^{-6}$ even against $6.529026343075532\times10^{-7}$ odd; live B $6.424958490062066\times10^{-7}$ even against $2.547515185086473\times10^{-6}$ odd; cross terms $\le3\times10^{-4}$ of the step; direction cosine $0.24572751316067618$; null exactly $0.0$; the spent scalar action $5.3390731361887128\times10^{-2}$ of the drift at the largest load and exactly $0.0$ on the ray | The two directions *are* distinguishable on the declared coordinates at one declared step, the measure is exactly still when nothing is written, and this body's right-hand side is the spent one on the spent direction—so the reservation that follows is not a failure to build the reading |
| Domain reading at $T_3=1350$, five relaxation times after the drive is removed | A's own group retained at $3.585494912706732\times10^{-3}$ (`fit_held` share $1.0000000000776$, residual $1.29\times10^{-10}$ against a band of $0.25$, release samples moving by $9\times10^{-13}$ of themselves where the measured clock would have taken them down by $\mathrm{e}^{\nu\,450}=155$); B's own group at exactly $0.0$ (`SILENT`, release peak exactly $0.0$); B's whole retained footprint $8.080466\times10^{-5}$ in the **even** group, $2.25\%$ of A's | The second direction is not a second storage coordinate: one step of action is not storage, and the coordinate B acts on is A's |
| Coexistence verdict | `RESERVED_ONE_RETAINED`. Joint's own-coordinate match fails on the odd group (relative gap $0.9779768743087116$) and holds on the even group (gap $0.022781598592640784$, cosine $1.0$) | The honest output the steering asked for: the conserved level has **one retained writable coordinate** on this realization, so multi-item storage has to come from **placement** rather than from the carrier |
| Nonlinear cross term, recorded | Joint and erase arms hold $7.185740\times10^{-8}$ in the odd group at $T_1$—nearly five decades above the readable floor, more than eight above B's own odd reading there, unbounded above A's exactly-$0.0$—then $4.379586\times10^{-10}$ at $T_2$ and exactly $0.0$ at $T_3$ | The odd coordinate is not *unwritable*, it is *unretained*: the pair writes what neither single writes, transiently, and the distinction is reported rather than folded into the verdict |
| Erasure verdict, vector-aware, at $T_2=900$ | `RESERVED_NO_B`: the B-only arm's odd group is $1.468687\times10^{-16}$, unreadable, so the counter-write's effect on B's coordinate is not yet askable. Recorded beside it: the erase arm's even displacement $3.668465\times10^{-3}$ matches the joint's $3.669082\times10^{-3}$ (gap $1.684\times10^{-4}$) and not the B-only arm's (gap $0.9779731662779862$), its own even fit `RETAINED` with share $1.0000000000769$ | A $-2$ change in the χ-cos drive strength, held for a full write phase against a coordinate another write established, did **not** remove it—the non-independence reading is measured, not merely reserved |
| The retained scalar, reported and not gated | $A$(`joint_AB`) $0.8917899977049457$ against the sum of the two singles' displacements $0.8917904951048021$: agreement to $4.97\times10^{-7}$ absolute, $5.6\times10^{-7}$ of $A$, $8.2\times10^{-4}$ of the displacement the singles wrote | The naive reading, measured and deliberately not promoted: two writes into one conserved level read as one addition, exactly as they must, and a coexistence claim taken there could not have been wrong |
| Controls, all firing | `ray_write` in silence at every read time ($4.299875\times10^{-16}$ against a $10^{-14}$ level) with the two ray arms agreeing to the last bits; can-fail `write_A` even $T_1$ $3.578250\times10^{-3}$ against a $10^{-12}$ floor; anchor readable on all five charged arms ($1.326$–$1.344\times10^{-3}$ against the ray arms' $4.6\times10^{-15}$); null exactly $0.0$; the release-window clock $1.1268281516184584\times10^{-2}$ at ratio $1.0064832293591475$ to the rate read live from the relaxation receipt; `step_short`'s ρ maximum bit-identical to the successor's $5.329147248815693\times10^{-16}$ | The write is present where the control says it must be silent; the measure fires at the largest declared magnitude; every charged arm is twelve decades off the ray rather than vacuous; and the clock is the realization's own |
| Verdict, replication and status | `status=PASS`, all fourteen gates, one invocation; the successor's five recorded literals reproduced exactly—$0.8923960494310218$, $0.8918036475597466$, $0.8923974885141087$, $0.0013261506410605264$, $4.615955614456139\times10^{-15}$—with zero mismatches, and the twelve declared design-probe readings likewise | This body's direction A *is* the successor's construction on the same seeds rather than a look-alike, and the answer disclosed before the freeze is the answer the run returned |

What is recorded and not gated, because it is a property of this realization rather than of the
claim: the free fit's rate on a retained group is unidentified by construction—A's even group
fits a free rate $1.88$ times the declared clock, inside the declared factor-$2$ band, on a
series that is nearly flat, so the `RETAINED` label rests on the held fit and the rate enters no
clause; the charged arms' own distance from the ray relaxes across the hold from
$1.3261506410605264\times10^{-3}$ to $4.9787389206375424\times10^{-8}$, so what is retained is
the composition coordinate's displacement—a conserved level—while the state itself comes back
near the ray; both reserved branches sit on a plateau rather than on a threshold, since every
floor in $10^{-15}$–$10^{-6}$ returns the same two verdicts on these readings.

**RESOLVED in measurement and in verdict**: on the declared seeds and at the largest declared
load, the loop carrier's χ-resolved composition profile has exactly **one retained writable
coordinate**. Direction A's offset stands five relaxation times after the drive is removed;
direction B's own coordinate is silent, and B's entire retained effect lands in A's coordinate
at $2.25\%$ of A's magnitude; the pair additionally writes a transient odd component four
decades above the readable floor at the first read time that is gone by the third; and the
counter-write leaves the established coordinate standing. The retained scalar reads additive
throughout ($5.6\times10^{-7}$ of $A$), which is **reported, not gated**—it is the reading that
would have returned "coexistence confirmed" with no way to be wrong. **Not resolved**: whether
any *other* declared modulation reaches a second retained coordinate, whether a second
coordinate exists at a placement the profile does not resolve, whether the single writable
coordinate can hold two items distinguished by anything but magnitude, and whether any of this
survives a change of seed family, load or resolution. The reserve is a bound on one finite
realization under two declared directions, not a statement about the continuum equations.

## 71. The retained coordinate is a conservation law, not a capacity: the closed form at the frozen body's own point, and the reading domain the run actually used

**No entry of theorem 6.3's reduced gap vanishes at the declared parameter point.** At the
equilibrium the frozen module's own constants give $\kappa(1+\varphi)=1.1268281293796237\times
10^{-2}$, $2r=1.2$, and $d+r-\operatorname{Re}\sqrt{r^2-\Omega^2}=2.7276406320767016\times10^{-1}$
(with $d=4.4982698961937725\times10^{-2}$ as that entry's mode-$0$ counterpart), so none of the
three boundaries is reached, and the only zero eigenvalue the frozen generator carries there is
the excluded total-density mode itself. §70's "one retained writable coordinate" is therefore not
a boundary artifact; the audit below reads it against $\dim\ker$ of the frozen `mode_generator` at
the run's own point, and finds the two counts equal—which is the branch the reserved verdict did
not name: the retained coordinate is a **conservation law** of the reduced generator, not a second
storage level.

The tuple is not re-derived from any successor. `computations/loop-carrier-composition-coexistence-prereg.md`
binds the discrete-operator module by digest in its §0 row `bound_module_sha256`, so that module's
constants *are* the declared tuple: $\varphi=1.618033988749895$, $r=\text{EXCHANGE}=0.6$,
$\Omega=V/R=0.4705882352941177$, $d=D_\text{ELL}/R^2=0.044982698961937725$ with
$V=0.8$, $R=1.7$, $D_\text{ELL}=0.13$, and $\lambda=0.04$; the two declared relations close exactly
($V/R-\Omega=0.0$, $D_\text{ELL}/R^2-d=0.0$). The run's own $\kappa$ is state-dependent, so the
audit reports it three ways rather than one: over the loaded seeded state the frozen rate array
runs $\min=5.286063597950403\times10^{-3}$, $\text{mean}=6.544507882556958\times10^{-3}$,
$\max=7.947406903627875\times10^{-3}$ and the scalar $\lambda(1-A_\text{seed})
=6.544507882556952\times10^{-3}$ with $A_\text{seed}=0.8363873029360762$ read from the receipt's own
`load_reference.coordinate.initial`—the two agree to $-6.07\times10^{-18}$, which is the identity
$\text{mean}_x\,\lambda(1-q(x))=\lambda(1-\text{mean}_x\,q(x))$; and at the equilibrium the
reference arm's own final coordinate $A_\text{eq}=0.8923974885141119$ gives
$\kappa=\lambda(1-A_\text{eq})=4.3041004594355226\times10^{-3}$. The seeded point is where the run
started; the equilibrium is where its own reference arm ends, its ray distance having fallen to
$5.297914102411338\times10^{-8}$, and it is the point the linearization is about.

| Entry of the reduced gap | At the seeded point ($\kappa=6.544507882556952\times10^{-3}$) | At the equilibrium ($\kappa=4.3041004594355226\times10^{-3}$) | Dial distance to its boundary |
|---|---|---|---|
| $\kappa(1+\varphi)$ — species composition | $1.7133744076175704\times10^{-2}$ (at $\min_x\kappa$: $1.3839094166127715\times10^{-2}$, the chain's own LB39 gap) | $1.1268281293796237\times10^{-2}$ | $\kappa=4.3041004594355226\times10^{-3}$ |
| $2r$ — uniform direction imbalance | $1.2$ | $1.2$ | $r=0.6$ |
| $d+r-\operatorname{Re}\sqrt{r^2-\Omega^2}$ — loop-nonuniform, direction-symmetric | $2.7276406320767016\times10^{-1}$ (root $3.7221863575426756\times10^{-1}$ on argument $1.3854671280276812\times10^{-1}$) | same, $\kappa$-independent | $\sqrt{d^2+\Omega^2}=4.7273325502140445\times10^{-1}$, $\Omega-r=-1.2941176470588228\times10^{-1}$ |
| minimum over the three, at the equilibrium | — | $1.1268281293796237\times10^{-2}$ | the $\kappa$ entry is the active one |

$\dim\ker$ is computed twice at the equilibrium point, on the frozen `closed_spectrum` and on the
frozen `mode_generator`'s own null space, and the two agree. Mode $0$: spectrum
$\{0,\,-1.2,\,-1.12682812937962\times10^{-2},\,-1.21126828129379\}$, one zero, generator nullity
one, generator's own smallest $|\operatorname{Re}\lambda|=9.06\times10^{-17}$. Modes $1$, $2$, $3$:
spectra $\{-0.272764063208,\,-1.017201334716,\,-0.284032344501,\,-1.02846961601\}$,
$\{-0.779930795848\pm0.725129746176\mathrm{i},\,-0.791199077142\pm0.725129746176\mathrm{i}\}$ and
$\{-1.004844290657\pm1.27792002284\mathrm{i},\,-1.016112571951\pm1.27792002284\mathrm{i}\}$, all with
zero zeros and nullity zero; the realized gaps are $2.7276406320767016\times10^{-1}$,
$7.799307958477508\times10^{-1}$ and $1.0048442906574395$—the loop family $d m^2+r-\operatorname{Re}\sqrt{r^2-m^2\Omega^2}$
is strictly increasing in $m$ from $m=1$, checked to $m=24$, so the minimum over all modes is the
minimum over the three entries and the closed form's $\min$ is realized rather than assumed. The
chain's own `mode_spectrum` reproduces both checked spectra with a maximum difference of exactly
$0.0$. So $\dim\ker$ over the modes the run declared, $\{0,1\}$, is **one**, and after excluding
the total-density mode it is **zero**: no conserved coordinate exists at this point that the drive
cannot address, which is the placement branch the reserve left open and which does not fire here.

The one kernel direction is the theorem's own label, read off the null vector rather than asserted:
in the generator's $(\text{carrier},\text{direction})$ basis the components are proportional to
$(1,1,\varphi^{-1},\varphi^{-1})$, giving a carrier ratio of $1.6180339887498865$ ($\varphi$ to
$1.4\times10^{-14}$), a direction asymmetry of $1.85\times10^{-16}$, and an $\varepsilon=e_Y-\varphi e_I$
residual of $1.03\times10^{-14}$. It is the $\chi$-uniform, orientation-symmetric, $\varepsilon=0$
total-density direction: the equilibrium ratio itself. The degeneracy list is carried forward as a
*predictive* handle and not run here—dial $\kappa\to0$ and the species composition becomes
conserved; $r\to0$ and the uniform direction imbalance does; $d=\Omega=0$ and the loop-nonuniform
direction-symmetric content does; $d=r=0$ and the content is ballistic at $\pm m\Omega$ with zero
real decay.

**What the run read, and what the declaration says it read.** §1.2 declares the reading domain as
$c_{s,k}(t)=\text{mean}_x\,q\big(F_{Y,s}(x,\chi_k),\,F_{I,s}(x,\chi_k)\big)$ with $k=0,\dots,23$: the
reduction is over the exterior axis and the remaining index is the loop sample, $48$ coordinates in
all. The executor's `composition_profile` implements `bounded_q(state[0], state[1]).mean(axis=base.EXTERIOR_AXIS)`,
and because `bounded_q` here takes the state's two carriers it carries three axes, not four, so
`EXTERIOR_AXIS = 2` lands on the *loop* axis: the implemented reduction is over $\chi$ and the
remaining index is the exterior point—the transpose of the declared one, $14$ coordinates, and the
receipt's stored group vectors are $7$ long, which is $N_x$ and not the declared $24$. The audit
proves the transposition on declared-shaped probes rather than by reading the line: a state whose
composition varies only along the loop axis returns an implemented row spread of exactly $0.0$
(the $\chi$-average) against a declared row spread of $7.376815905011214\times10^{-2}$, and a state
that varies only along the exterior axis returns an implemented row spread of
$6.938268539288772\times10^{-2}$ against a declared row spread of exactly $0.0$. The executor's own
`direction_cosine` docstring still calls the concatenated vector a "48-vector" while it concatenates
$2\times7$. This is reported and not repaired: §70's body is frozen and was not re-run. Its
consequence is exact, not approximate—every coordinate the receipt holds is a $\chi$-average, so
the reading can only see the mode-$0$ sector, which is precisely where the closed form says the
single conserved direction lives. The declared $\chi$-resolved domain would have carried the
$\chi$-nonuniform content whose smallest realized rate is $2.7276406320767016\times10^{-1}$.

| Reading | Receipt value | Against the closed form |
|---|---|---|
| Retained even group of write_A, $T_1\to T_2\to T_3$ | $0.0035782503187010394$, $0.0035854949067870424$, $0.003585494912706732$ | Over the $450$-unit release window it moves by $1.65\times10^{-9}$ of itself, where the gap $1.1268281293796237\times10^{-2}$ would have taken it down by $0.9937221428959869$—a factor $6.02\times10^{8}$, i.e. no decay at all |
| Release-window clock, fitted on the reference arm's own $\rho$ | $1.1268281516184584\times10^{-2}$ | The $\kappa$ entry at the equilibrium is $1.1268281293796237\times10^{-2}$: difference $2.22\times10^{-10}$, ratio $1.0000000197357823$. The rate read live from the relaxation receipt, $1.119569724312185\times10^{-2}$, sits at $0.9935585517629607$ of it |
| Own-group readings, $T_1/T_2/T_3$ (450, 900, $1350$) | A even as above; A odd exactly $0.0$, $2.94\times10^{-16}$, exactly $0.0$; B even $8.054468970674446\times10^{-5}\to8.080466456044417\times10^{-5}$; B odd $2.94\times10^{-16}$, $1.47\times10^{-16}$, exactly $0.0$ | Neither single write retains anything in the odd group, and both writes' whole retained footprint lands in the even group—the one kernel direction |
| Joint and erase odd residue | $7.185740297158022\times10^{-8}$ at $T_1$, $4.379586482395071\times10^{-10}$ (erase $4.379025443956683\times10^{-10}$) at $T_2$, exactly $0.0$ at $T_3$ | A rate of $1.1334032054212044\times10^{-2}$ over the $450$ units, $1.005835030090348\times$ the $\kappa$ entry: fast against retention, of the same order as the active entry |
| Pre-flight one-step action | A: even $2.5753540367077486\times10^{-6}$ against odd $6.529026343075532\times10^{-7}$; B: even $6.424958490062066\times10^{-7}$ against odd $2.547515185086473\times10^{-6}$ | B's drive is odd-dominant by $3.97\times$: the odd class *is* reachable, so its silence is not a controllability wall |
| Additivity of the two writes at $T_3$ | cosine $1.0$, relative gap $0.022781598592640784$; the erase arm against the joint $1.6834098570927907\times10^{-4}$ | Two injectors, one conserved coordinate: a perfect cosine is what a degeneracy looks like from the reading side, not evidence of a second level |
| Epsilon excursion of the reference arm | ray distance $5.297914102411338\times10^{-8}$ at $T_3$ and at the end | The composition's sensitivity to the decaying $\varepsilon$ direction is proportional to $\varepsilon$ itself, so that direction cannot be seen in the composition once the state returns to the ray—which is why the retained displacement is the conserved one |
| Binding and status | protocol body `09426b68…`, executor `3852eadb…`, operator module `d687597f…`, receipt `9724143b…`; `status=PASS`, fourteen of fourteen gates, $305.6$ s | The audit reads the bytes the declaration binds, and pins all $115$ numbers it prints against a literal table (`self-check: 115 pinned values agree`) |

**Classification, against the branches fixed before the arithmetic.** Measured retained
coordinates: one (A's even group, and B's retained footprint inside the same group). $\dim\ker$ over
the declared mode content: one. The branch is `equal`—**confirmation**: the retention across five
relaxation times is the conservation law of the frozen generator, the retained coordinate is the
excluded total-density direction read through a composition that is insensitive to everything else
at the equilibrium, and §70's residual, $2.25\%$-in-even footprint is B's own injection landing in
that same direction. The alternate bookkeeping, $\dim\ker=0$ *after* excluding the total-density
mode, would read `measured_larger`; that is not an undercount of the linear theory, because the one
coordinate measured is the excluded mode itself, and the honest statement of the pair is: one
conserved coordinate, two injectors, no second capacity. The odd class is silent in *retention*
while being reachable in *action*, and the audit's numbers separate those two: it is a spectral
statement about a direction with no kernel, not a capacity and not a wall.

The exponent the retained displacement scales with is not a free parameter either: the spent
write body's own recorded law is $|D_\infty|=(4.3424057234641914\times10^{-4})\,\delta_g^{\,1.0302448806878108}$,
labelled `PROPORTIONAL` inside the declared linear band $[0.9,1.1]$, with the free fit's
$1.031104893189443$ and the terminal readings' $1.0291737139778423$ agreeing to $0.2\%$. An exponent
of one within two and a half percent is what the linear response of a conserved coordinate looks
like; it is not evidence of a second level, and §70's additive scalar reading is the same statement
in scalar form.

**The falsifiable continuation this audit does not run**, carried for a later body rather than
tested here: move $\kappa$, $r$, $d$ or $\Omega$ toward its zero and the retained count should rise
by one per degeneracy reached. **Rule forward, for every write-capacity body from here**: a body
that claims writable capacity declares $\dim\ker(\text{mode\_generator})$ at its own parameter point
as its predicted answer *before* it runs, and states its distance to the three boundaries—$\kappa$,
$r$, and $d=\Omega=0$, with $2r$ and the mode-$1$ loop rate as the other two dials; without that
declaration, "two writes coexist" can be a degeneracy mistaken for capacity, exactly as the
retained scalar $A$ would have returned a confident "coexistence confirmed" with no way to be
wrong.

## 72. Two coordinates on purpose: dialing exactly one gap entry to zero, and the injector that is not an inverse

**The rule §71 wrote forward has now been run, and it fired.** §71 ended with: *a body that claims
writable capacity declares $\dim\ker$ over the frozen `mode_generator` at its own parameter point as
its predicted answer before it runs, and states its distance to the three boundaries.* This body
moves exactly one declared coefficient—`exchange`, the $r$ of (LB42) $\partial_tH=-\Omega\partial_\chi
F+d\partial_\chi^2H-2rH$, which LB39 itself names at its boundary—to zero, and declares the answer
before the arithmetic. At $r=0$ the three entries of the reduced gap at the equilibrium are
$\kappa(1+\varphi)=1.1268281293796237\times10^{-2}$, $2r=0$, and
$d+r-\operatorname{Re}\sqrt{r^2-\Omega^2}=d=4.4982698961937725\times10^{-2}$: **exactly one vanishes**,
the second, and the point is reachable inside the declared machinery rather than imposed on it—the
frozen base module already carries an arm at this value (`persistent_current`, horizon key
`mode_zero_exchange`, `ZERO_EXCHANGE = 0.0`) and multiplies the right-hand side by that coefficient.

| Declared, before the run | Measured, from the frozen generator |
|---|---|
| $\dim\ker(\text{mode }0)\big|_{r=0}=2$: one direction-symmetric combination (the equilibrium ratio, which is §70 and §71's retained coordinate) and one direction-antisymmetric, $\chi$-uniform imbalance | nullity $2$, one symmetric and one antisymmetric, carrier residual $2.61\times10^{-16}$; the same generator at $r=0.6$ gives nullity $1$, symmetric alone |

**The reading domain is the declared one this time, and it is proven rather than asserted.** §71 found
that the spent body's `composition_profile` averaged the loop axis and indexed the exterior one—the
transpose of its own §1.2. This body reads $c_{s,k}=\text{mean}_x\,q(F_{Y,s}(x,\chi_k),F_{I,s}(x,\chi_k))$,
$48$ coordinates, and the frozen executor rebuilds the audit's declared-shaped probes in its own gate
path: a state varying only along the loop axis reads a declared row spread of
$7.376815905011214\times10^{-2}$ against exactly $0.0$ on the transposed reader, a state varying only
along the exterior axis reads exactly $0.0$ against $6.938268539288772\times10^{-2}$, and on a state
constant in $\chi$—where the two readers must agree—their reported means agree to exactly $0.0$. The
transposition cannot recur unnoticed, and the readers are tied to each other where physics says they
are.

| Branch | Declared values | Measured |
|---|---|---|
| (a) `present` | four labels on the $T_3$ standing count against the predicted $2$ | `CONFIRMED_TWO`: standing $2$ of predicted $2$ |
| (b) `writable` | live action at or above $10^{-3}$ of one step's own drift, both channels charged | `WRITABLE_BOTH`: live D $1.0168673283524747\times10^{-2}$, live N $8.909301878312713\times10^{-2}$, charges $-9.835534138125102\times10^{-5}$ and $-8.957259285831062\times10^{-5}$ |
| (c) `retained` | share of the $T_2$ charge standing at $T_3$ at or above $0.5$, final-phase movement at or below $0.1$ | `RETAINED_BOTH`: D share $1.0000000019979542$ with movement $2.89\times10^{-10}$, N share $0.9999998175949137$ with movement $2.40\times10^{-8}$ |
| (d) `erased independently` | the counter phase removes the whole charge and the first coordinate stands | `RESIDUAL`: the counter removes $6.60\times10^{-3}$ of N's charge while the D charge holds at $1.0000000019979542$ |

**The counterfactual is measured rather than assumed, and the dial does what the closed form says.**
`write_N_restored` runs the identical drive at the spent point $r=0.6$, read against its own
exchange-matched anchor—an arm with the same load, the same coefficient and no drive, because at that
point the seed's own uniform imbalance is damped and the two parameter points do not share an
odd-group equilibrium. Its charge at $T_2$ is $-5.366331823353221\times10^{-9}$ and nothing of it
stands at $T_3$: share exactly $0.0$, against `counterfactual_factor` $e^{-2r\cdot450}=4.8\times10^{-235}$
and against $0.9999998175949137$ for the same channel at $r=0$. Same drive, same load, same window, one
coefficient moved: the second coordinate is conserved where the gap entry vanishes and is taken down
where it does not, and the exchange term annihilates the antisymmetric part to round-off rather than
merely exponentially.

**What the counter-write cannot do, stated as the finding it is.** The reversed orientation channel
removes $5.675678610428392\times10^{-7}$ of the $8.605157735191993\times10^{-5}$ it wrote—$0.66\%$—so
the injected quantity is not an odd function of the channel's sign. It is a **rate-magnitude** effect:
the channel changes the gate rate by $\pm\delta_N s$, the two orientations approach their common
composition attractor at different speeds, and reversing the sign mirrors the *transient* while the
level that the magnitude wrote is even in $\delta_N$. The reading is taken differentially, against the
arm that carries the same two writes and no counter phase, so that the even channel's own footprint in
the odd group—it exists, because the composition is a nonlinear function of the densities—cancels
exactly. The coordinate is writable and conserved and its injector is **not invertible**; that is a
statement about the orientation channel, not about the kernel, and it is why the branch is recorded as
a reserved outcome rather than repaired away.

**The spent chain's own scalar is a different reduction, and the difference is now a number.** §71's
transposition meant the spent receipt's coordinates are $\chi$-averages. This body's $\bar e$ is the
exterior mean of the *pointwise* composition; the spent scalar is the composition of the *loop-averaged*
projection. They differ by the concavity of $q$ in $\rho$: over $81$ sampled states the gap reaches
$0.2322333653463856$. The declared coordinate is therefore not conflated with the spent one—the
protocol states the difference, gate 2 ties the two readers where they must agree, and the gap is
published rather than absorbed. What *is* compared against the spent receipt are its own scalar on both
anchors, $0.8923974885141064$ and $0.8923974885141089$ against
$0.8923974885141119$ and $0.8923974885141087$ (differences $5.55\times10^{-15}$ and
$2.22\times10^{-16}$), and the seeded family's recorded load transfer, $0.3646114292316331$ within
$9.07\times10^{-14}$ relative.

**One repair, disclosed, with its accounting closed in the record itself.** The first invocation
integrated all nine arms and then failed in the gate path on a latent `KeyError`, writing no receipt;
§6's stopping rule permits exactly one repair after an invocation that wrote no receipt, so the pair was
repaired and re-frozen, and the invocation that produced the receipt ran under that repaired pair. The
repair moved a declared **cost** bound and nothing else, and the three states of the frozen pair are
readable without reconstruction:

| State of the frozen pair | Commit | Bound | Seconds per step | Projected | `frozen_body_sha256` | `executor_sha256` |
|---|---|---|---|---|---|---|
| the first freeze, under which the first invocation ran and wrote no receipt | `c6694976` | `900` | `6.665e-4` | `405.0` | `d16060dd28f5b8d34dbbb542e7a16d4dbccd3d23dabd4f5a0232d8bcc51758a0` | `114fd1876c0a4845060a8fb01e21464b39eec909b707c90dec278e3c6c49fc8c` |
| the re-frozen pair, under which the receipt's own invocation ran | `c88872f2` | `1800` | `1.07e-3` | `650.0` | `a2c6abe2f85b2c9c12e25fd7062ba4d12b8c640ef192c81bb8fc5e5c03c22f33` | `c13afe722904e91528956cd967705238041e963b0d46280b58fff0a54fd2d518` |
| after the post-run amendment recorded in the body's §8.1 | this commit | `1800` | `1.07e-3` | `650.0` | `7fce9e0e3a252eef3e54be3cee016f2e1db453a7e9c25cdae98b873884678fbe` | `671e4a5edbe406f6c1f932d855987d5cc746315b10c13f387291bf15cbf778f0` |

Nothing but the ceiling and the projection moved at that re-declaration: no statistic, threshold,
tolerance, level, arm, gate, feature or decision rule was touched, and the two passages corrected in
place afterwards — §6's bound row set and its invocation sentence — were corrected as *text* with an
in-place marker naming the pre-amendment values, which is why the standing body digest differs from the
executed one while both are published. The first invocation left neither a receipt nor a partial
artifact: `runs/loop_carrier_two_coordinates/` holds exactly the one file the second invocation wrote,
the executor writes only after its gate table is printed and its payload sanitized, and the first
invocation died in the gate stage before any write. A third invocation is refused in code — invoked
again, the executor prints `REFUSING TO RUN: … already exists …`, exits `3`, and leaves the receipt's
digest unchanged — so the body's single reading cannot be quietly replaced. The static pass now
**drives the gate, feature and receipt path on shaped inputs**, so a key that path reads and its
producers do not carry fails in seconds instead of after an integration, and it immediately found a
second latent key (the clock fit's degenerate branch, which gate 13 read by key); the declared bound was
re-derived from the observed $726.1$ seconds rather than kept at the optimistic extrapolation.

| Binding and status | Value |
|---|---|
| Protocol body / executor | `a2c6abe2…` / `c13afe72…`; operator module `d687597f…`, base probe `28d2fd54…`, split `246463f7…`, gate-load `be9f651d…`, audit `0503f109…`, spent executor `3852eadb…`, spent body `09426b68…` |
| Receipt | `runs/loop_carrier_two_coordinates/verification.json`, `46ae3ee2…`, fourteen of fourteen gates, $726.1$ s, `status=PASS` |
| Clock | fitted $1.1268283368545141\times10^{-2}$ against the receipt-declared $1.119569724312185\times10^{-2}$, ratio $1.0064833948120457$ inside the carried band $2.0$ |
| Step rule | the tightest arm is the restored one at $\lambda_{\max}=1.058814$, limit $0.023611$ against $\Delta t=0.02$ |

**Classification, against the branches fixed before the run.** The declared point's prediction is
**confirmed as two retained coordinates**: the carrier channel writes the even group and keeps it, the
orientation channel writes the odd group and keeps it, the two injectors are distinct
($|\cos|=1.77\times10^{-2}$ on the declared $48$ coordinates), each acts on its own coordinate at the
largest declared magnitude while the other's action there is $3.2\times10^{-2}$ and $7.6\times10^{-2}$ of
it, and the counterfactual separates the two parameter points by the whole of the charge. This is the
carrier's first **multi-item memory**: two durable numbers with independent injectors, which is what
§70's reserved branch asked for and what §71's rule made measurable instead of plausible. The open
property is the one the (d) branch records: the second coordinate's injector is even in its own
magnitude, so the channel can write and cannot un-write. Nothing here measures the value of $\varphi$,
the conversion ratio, the carrier identity, the QF1-to-carrier map, the phase law, the scale ratio, the
quantum statistics, or whether any of these is a physical density or current.

## 73. The decay rate *is* the gap entry: a sweep through the crossing, and the injector's own sign

**§72's retention reading was a verdict taken where the entry vanishes, so §73 measures the rate
instead.** A vanished gap entry *is* a zero decay rate: a coordinate that stands still for 450 units
is not distinguishable, by that reading alone, from a coordinate whose window happened to be short.
§72 declared $\dim\ker$ at one point and measured two retained coordinates there; §71 identified the
decay rate with the entry at that same point. What neither could show is that the rate *tracks* the
entry away from it. This body dials the same coefficient—the `exchange` $r$ of (LB42), whose entry in
LB39 is $2r$—to seven declared values through the crossing, $r\in\{-0.01,-0.005,-0.0025,0,0.0025,
0.005,0.01\}$ with entries $2r\in\{\pm0.02,\pm0.01,\pm0.005,0\}$, keeps the state off equilibrium at
every point, and reads one estimator, one stride and one window (150 units, 7500 steps, samples every
250) on the same declared coordinate at all seven, with the **window's own clock** beside it: the load
arm's conversion mode, whose rate is the frozen $\kappa(1+\varphi)=1.1268281293796237\times10^{-2}$
and does not move with $r$.

**The seed is why the sweep can be exact, and the exactness is declared rather than discovered.** The
declared family is $\chi$-uniform and exterior-flat with the *same* imbalance on both carriers,
$f_{a,s}=(E_a/2)(1+s\beta)$ with $\beta=0.01$ and $E_Y:E_I=\varphi:1$, so $\epsilon=e_Y-\varphi e_I$
vanishes to round-off pointwise (largest $1.11\times10^{-16}$), the conversion term of the frozen
right-hand side is correspondingly absent, and the state's swing lies on the equilibrium-ratio
direction $w_0=(\varphi,1)$—the carrier axis's kernel direction—whose eigenvalue in the frozen
generator is the entry and nothing else. On the *complementary* direction the eigenvalue is
$\kappa(1+\varphi)$ alone; the seed's content there is $6.43\times10^{-15}$ over the whole family. So
the entry coordinate's antisymmetric amplitude decays **exactly at the entry** at every declared
point, on both sides of the crossing, and the load arm's drive—the chain's own transfer, which puts
its whole content on the complementary direction—decays exactly at the conversion entry and is
annihilated by the exchange: that is what lets a rate measured at one $r$ serve as the clock for all
seven.

| point | exchange | entry | fitted rate | rate / entry | fit residual | clock rate / its reference |
|---|---|---|---|---|---|---|
| $-0.0100$ | $-0.0100$ | $-0.02$ | $-2.0087210596378125\times10^{-2}$ | $1.004361$ | $8.541\times10^{-3}$ | $0.996199$ |
| $-0.0050$ | $-0.0050$ | $-0.01$ | $-1.0005319983069205\times10^{-2}$ | $1.000532$ | $2.399\times10^{-4}$ | $0.996199$ |
| $-0.0025$ | $-0.0025$ | $-0.005$ | $-5.001058250020064\times10^{-3}$ | $1.000212$ | $2.173\times10^{-5}$ | $0.996199$ |
| $+0.0000$ | $0.0$ | $0$ | $2.4880630605367724\times10^{-17}$ | — | $4.149\times10^{-15}$ | $0.996199$ |
| $+0.0025$ | $+0.0025$ | $+0.005$ | $5.000236194936966\times10^{-3}$ | $1.000047$ | $4.853\times10^{-6}$ | $0.996199$ |
| $+0.0050$ | $+0.0050$ | $+0.01$ | $1.0000265174148837\times10^{-2}$ | $1.000027$ | $1.198\times10^{-5}$ | $0.996199$ |
| $+0.0100$ | $+0.0100$ | $+0.02$ | $2.000022063745508\times10^{-2}$ | $1.000011$ | $2.220\times10^{-5}$ | $0.996199$ |

**Classification, against the branches fixed before the run: `LINEAR_BOTH_SIDES`.** Both signs pass
their bands together with the crossing point; every fit is readable with 31 samples above the $10^{-12}$
floor, one sign throughout, and a residual inside its ceiling; and the rate-to-entry slope of the seven
readings is $1.001724712832028$ with intercept $-1.3266688989497523\times10^{-5}$. The
identification therefore holds not only where the entry vanishes by construction but across a
factor of four in the entry, at both signs: the rate *is* the entry. Two deviations are at issue
and are kept apart here, because they have different referents: the relative $1.7\times10^{-3}$ is
the *slope's* departure from one, while the largest per-point departure of a fitted rate from its
own entry is $4.4\times10^{-3}$, at $r=-0.01$ at the edge of the swept range, inside the declared
band $10^{-2}$.

The crossing's own rate is $2.4880630605367724\times10^{-17}$, and each of its three ratios is
stated against a named referent: $0.005/2.4880630605367724\times10^{-17}=2.0\times10^{14}$ against
the smallest swept entry, $1.0\times10^{-6}/2.4880630605367724\times10^{-17}=4.0\times10^{10}$
against the crossing's own declared ceiling, and
$4.0534467309636227\times10^{-10}/2.4880630605367724\times10^{-17}=1.6\times10^{7}$ against the
two-coordinate receipt's own rate bound on its window (the standing share $0.9999998175949137$
over 450 units reads $-\ln(\text{share})/450=4.053\times10^{-10}$).

**The window is stated with the entry it is applied to, entry by entry rather than remembered.**
The counterfactual factor an entry predicts over *this* body's $150$-unit window is
$\exp(-\lvert\text{entry}\rvert\cdot150)$. The seven declared points carry, each beside its own
entry: $1.0$ at $r=0$, whose entry is $0$; $e^{-0.75}=0.472$ at entries $\pm0.005$
($r=\pm0.0025$); $e^{-1.5}=0.223$ at entries $\pm0.01$ ($r=\pm0.005$); and
$e^{-3}=4.98\times10^{-2}$ at entries $\pm0.02$ ($r=\pm0.01$). The amount of decay is therefore
*not* what carries across the range, and it does not read as orders of magnitude: over the window
the smallest swept entry's charge falls by about a factor of two and the largest by a factor of
twenty, and the entry $0.04$ -- from which $e^{-6}=2.48\times10^{-3}$ would follow -- is not among
the declared points at all. What carries across the range is the *rate*, read to
$1.7\times10^{-3}$ relative at both signs and at the crossing against a clock that does not move
with the entry. The orders-of-magnitude separation belongs to the crossing alone, whose own rate
sits $4.0\times10^{10}$ below the declared ceiling it must fall under and $1.6\times10^{7}$ below
the two-coordinate receipt's own rate bound.

**The law does not rest on a single estimator or a friendly window.** The can-fail arm runs the same
estimator on a $5$-unit window -- $250$ steps, against the seven swept points' $7500$ -- at
$r=+0.5$, whose entry $1.0$ is fifty times the largest swept entry $0.02$: it reads
$1.0000059865642859$ against its declared $1.0$. The extrapolation witness at $r=+0.25$, whose
entry $0.5$ is twenty-five times the largest swept entry, reads $0.5000075974138588$ against
$0.5$. At the other extreme the clock is
identical to the last bit at every point—$1.1282357172592223\times10^{-2}$ seven times—and sits within
$1.0\times10^{-2}$ relative of the conversion entry measured at its own seed, ratio $0.996199$; against
the chain's recorded $1.119569724312185\times10^{-2}$ it stands at $1.0115857423209142$, inside the
carried factor-band $2.0$. Every ray arm is fixed point for fixed point and the same fixed point at
every parameter value; the reader reproduces the two-coordinate body's own domain probes bit for bit
(loop-only spread $7.376815905011214\times10^{-2}$ against the transposed reader's exactly $0.0$;
exterior-only exactly $0.0$ against $6.938268539288772\times10^{-2}$), and the kernel prediction
declared before the run is confirmed at every declared point: $\dim\ker(\text{mode }0)=2$ with one
direction-symmetric and one direction-antisymmetric direction at $r=0$, and $1$ with the antisymmetric
direction absent at $r=\pm0.0025,\pm0.005,\pm0.01$, at $0.6$, at $0.5$ and at $0.25$, every closed-form
multiset residual at or below $2.3\times10^{-16}$.

**The injector's law, stated as one sentence: the orientation drive writes a signed charge, not a
magnitude.** At both declared points the response's even part is exactly $0.0$ to the last bit and its
odd part is the whole response—$-1.4358387617779411\times10^{-3}$ at $r=0$ and
$-1.2646830210309101\times10^{-2}$ at $r=-0.01$—so reversing the drive reverses what the coordinate
stores, and the coordinate is not a monotone store. This does not contradict §72's even-magnitude
finding, and the two readings are about different objects: §72 measured the *level* a counter-write
leaves behind, which is even in the drive's magnitude, whereas this body's differential reading takes
the difference of two arms whose drives have opposite signs against one common baseline, so any level
common to both cancels and only the sign-odd part survives. The schedule and the window are named
with each reading rather than shared between them. On this body's own -- three phases of $2500$
steps, $50$ units each at $\Delta t=0.02$, inside the declared $150$-unit window -- the reversed
channel **removes** $0.7715799746327933$ of what it wrote at $r=0$ and $0.3690299651437342$ at
$r=-0.01$, leaving $0.22842002536720674$ and $0.6309700348562658$ standing. §72's counter is the
other way round in magnitude and is not smoothed into it, being read on *its* schedule in *its*
$450$-unit channel window: it removed $6.60\times10^{-3}$ of the charge it wrote, leaving $0.9934$
of that charge standing. The two fractions are not one channel's efficiency at two dial settings;
the bodies differ in seed, schedule and window. Neither writes an inverse, so *the channel can write and cannot un-write* stands, and it
now stands beside the statement that the net charge is odd in the sign; the reversed drive here is
the more effective of the two. The protocol's §8.1 also carries the ruling that bounds an instrument
repair and its two deciding conditions — derivability without run data, and pre-freeze catchability —
and this body meets both.

**Two binding rows moved after this body ran, and they are named rather than left to a bare
"above": the `two_coordinate_executor_sha256` row and this body's own `executor_sha256` row, both
standing in this section's `Binding and status` table at its end and both mirrored by the protocol's
section 0. The reason is one sentence in the body it continues.** At the user's instruction, section 6
of the two-coordinate protocol gained a sentence stating that its cost bound is enforced by the
`timeout` wrapper on its invocation line and that its projection rows are estimates and not bounds —
the reconciliation of the 405 s projection, the 900 s pre-amendment bound and the 726.1 s observation.
Its own §8.1 carries the fourth state of its frozen pair, and its executor's body-digest constant was
re-anchored to match, so the standing row for `two_coordinate_executor_sha256` reads `7f782440…` while
this body's receipt and its archived first invocation both record `671e4a5e…`, the bytes both
invocations actually ran against. This body's own executor was re-anchored the same way so its row
could follow, from `c1a8d490…` to `b4b6aea7…`. No declared value in either body moved at that
re-anchoring; the rows the two invocations here actually ran against are the ones the receipts
record.

**One repair, disclosed, with the pair's states readable without reconstruction.** The first invocation
integrated all twenty-nine arms in 71.0 s and wrote a receipt with `status=FAIL`, gate 8 its only
failing gate—on readings that satisfy that gate's bound as it now stands (complementary-direction content
$6.43\times10^{-15}$ against $10^{-12}$; pointwise epsilon $1.11\times10^{-16}$ against $10^{-14}$;
load epsilon against the transfer's own value $1.94\times10^{-15}$ against $10^{-13}$). The predicate,
not the sweep, was wrong: it applied the pointwise-epsilon condition to every recorded seed, including
the load arms whose declared purpose is to carry the transfer's $\epsilon$ and to be the clock. The
gate's sentence said "on every sweep seed"; the code read every seed. The first receipt stands byte for
byte at `runs/loop_carrier_rate_entry_sweep/first-invocation-verification.json`,
`cdfb45468af1ebdcf1bfc21828f78a502d396c9dd484251114814db340dcd6ec`, bound as a section-0 row; the
amendment of §4 and §6 moves **no statistic, threshold, tolerance, arm, schedule, gate or decision
rule**—the two thresholds set from the design probe were fixed *before* the first freeze—and permits
exactly one further invocation against the amended pair. The states:

| State of the frozen pair | Invocation against it | `frozen_body_sha256` | `executor_sha256` |
|---|---|---|---|
| the first freeze | invocation 1: `FAIL`, receipt `cdfb4546…`, preserved | `f81a4776f736d91d6724d08c10fbdb14ca81f775934dc38ab03c0f76775224d5` | `e70007614ab45d83b9eb835297354bd8465b6a9abc89986dc19b4b329fd22b7d` |
| the amended pair, as invoked | invocation 2: `PASS`, receipt `318a2ac6…` | `97f8bf764dbfb7f2da845a465c1102c0b84143f7e353354aa97c1d30dfc92f2e` | `c1a8d490bc85792507a2fef654a70a9efd4fe2545c0a8b53ca4861513aa03777` |

A third invocation is refused in code—invoked after the second, the executor prints `REFUSING TO RUN:
… already exists; this body is invoked once per freeze and a further invocation is refused outright.`
—and the amended guard additionally refuses to run at all when the archived first invocation is absent
or does not match its bound row, so neither receipt can be quietly replaced. The checks that make the
body's readings load-bearing were shown to fire rather than assumed to: gate 8 fails with either of its
two ceilings set to zero, gate 7 fails with one declared probe reading moved by $10^{-6}$ (naming the
position), the binding refuses on a single flipped byte in the bound archive, and gate 9 carries the
control that shows the state digest separates a fixed point from a moving arm (the first entry arm's own
first and last digests differ). The static pass also catches, in seconds, the class of defect that cost
this body its first invocation: removing the per-point `clock_rate` key makes it report
`KeyError: 'clock_rate'` from the gate, feature and receipt path.

|| Binding and status | Value |
|---|---|
|| Protocol body / executor | `97f8bf76…` / `b4b6aea7…` standing, `c1a8d490…` the bytes the invocation ran against; operator module `d687597f…`, base probe `28d2fd54…`, split `246463f7…`, gate-load `be9f651d…`, audit `0503f109…`, write body `740d0fc0…`, two-coordinate executor `7f782440…` standing, `671e4a5e…` the bytes this body ran against |
|| Receipt | `runs/loop_carrier_rate_entry_sweep/verification.json`, `318a2ac6…`, fourteen of fourteen gates, $69.8$ s of a $600$ s cost bound, `status=PASS`, branch `LINEAR_BOTH_SIDES`, injector `SIGN_DEPENDENT` |
|| Budget | $29$ executions -- twenty-seven of $7500$ steps and two short arms of $250$ -- $203000$ steps against caps $10000$/$250000$; step rule satisfied on every arm at $\Delta t=0.02$ |
|| First invocation | `first-invocation-verification.json`, `cdfb4546…`, one failing gate, kept as the record of the amendment |

**§71's identification is now a measurement, not a reading at the one point where it is free.** What
this body identifies is that on the frozen (LB6) line, restricted to the declared seed family, the
declared coordinate's decay rate equals the gap entry linearly, at both signs through the crossing,
against a clock that does not move with the entry. What it does **not** identify: that any physically
realized memory exists; that the removed fraction -- or its complement, the fraction left standing
-- is a storage efficiency; or that the linearity extends
outside this family—a seed with content on the complementary direction mixes the two eigenvalues and
reads a rate between them. The rule it writes forward: **a retention reading is published as a rate
against the dialled entry, with the window's own clock beside it** — a standing charge at a point where
the entry vanishes by construction is not a measurement of storage, and neither is a rate quoted without
the clock that says what the window was.

## 74. Wound carrier loop in the corrected transverse tube

The frozen protocol
`computations/matter-formation-wound-loop-gap-prereg.md` carries the corrected
transverse-tube functional into the closed-loop mechanism the Yang–Mills
program needs. It solves nineteen radial profiles on $(M,R_{\max})=(200,8)$
with spacing and domain comparisons at $n=2,4,8$, minimizes the thin-loop mass
over the charge schedule $Q\in\{16,64,128,256\}$ at $w=1$, evaluates the exact
torus metric at the smallest admissible radius $R=8$, and assembles the
generalized transverse Hessian at the recomputed trial profile.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Straight-tube profile family | All $19$ primary profiles converge with worst residual $1.3691\times10^{-8}$ against $10^{-7}$; worst relative spacing and domain discrepancies in $e(n)$ are $1.6997\times10^{-5}$ and $2.1146\times10^{-4}$ against $5\times10^{-4}$ | **PASS**, finite radial grid $(M,R_{\max})=(200,8)$ with $(400,8)$ and $(400,16)$ comparisons |
| Binding threshold | The finite-domain crossing lies in $n\in(1.875,1.90625)$ against the infinite-plane Townes onset $1.7307557357$; the schedule-resolved loop threshold is $\lvert Q/w\rvert_{\rm bind}=41.1173021501$ at $n=4.3260504663$ with $e(n)=4.5039640307$ | **PASS**, measured density interpolation |
| Reduced loop minima | $Q=64,128,256$ are bound with $\Omega_\infty Q-M_*=13.589900,66.776483,198.920322$ at $n_*=7.147844,12.637748,23.103097$; every radius $R_*=1.4229,1.6491,1.8481$ violates the transported-profile gate $R\ge8$ | **BOUND**, outside the thin-tube domain |
| Admissible transported trial | At $Q=256$, $w=1$, $R=8$ the freshly solved $n=5$ profile gives $M^{\rm tor}=2159.6354486$ against $\Omega_\infty Q=2231.7562591$, margin $72.12081046$, tail fraction $2.8574\times10^{-6}$ | **BOUND** at the smallest qualified radius |
| Loop-radius direction | The one-sided derivative is $dM^{\rm tor}/dR=+8.6921788545$: energy falls toward radii below the validated domain | **NO STATIONARY THIN LOOP** |
| Transverse spectrum | Generalized eigenvalues give a soft $m=1$ translation mode $\omega^2=0.0025671838$ and positive non-symmetry modes $12.7261387878,17.7075102178,19.9381383240$ at $m=2,3,4$ | **PASS**, shape stability in the measured sector |
| Primary verification | `runs/20260921_matter_formation_wound_loop_gap_recovery/primary.json` passes $12/12$ checks; the preserved first receipt records the completed calculation and the manifest-path defect | **PASS** with the protocol-authorized recovery |
| Independent reconstruction | `runs/20260921_matter_formation_wound_loop_gap_recovery/independent.json` passes $17/17$ checks and reproduces every number with worst spectral normalized error $4.03\times10^{-12}$ | **PASS**, source-independent |
| Mutation controls | A $10^{-3}$ energy change trips the mass comparison at normalized error $2.3274\times10^{-5}$; a sign flip of one positive eigenvalue moves the stability minimum from $+12.7661775631$ to $-12.7661775631$ | **FIRES**, both can-fail controls |
| Continuum boundary | The carrier is neutral under $SU(2)_Q$; $Q$ and $w$ have no derived Wilson or electric-flux identification; the stationary loop lies inside core overlap | **UNRESOLVED**, `clay_verdict=NULL` |

The classification is `BOUND_THIN_TRIAL_NO_THIN_STATIONARY_RADIUS`. The
mechanism supplies the corrected tube's binding, its width selection, the
longitudinal winding pressure and a positive transverse spectrum, and the same
calculation locates the missing piece: an inverse-length term built from
gauge-invariant Yang–Mills data and a controlled thick-core completion. The
result ends the frozen stopping rule. Densities, charges, grids, thresholds
and the decision tree were fixed before the scientific receipt; the single
recovery is recorded with the defect and the preserved failed receipt. The
receipt SHA-256 values are
`fbe2ec4ca9a39be31ebb0c4574c9ff12536d6ba6e8d2a4feaf0ef996d11125bd`
for the preserved first receipt and
`a58a7532bb4364faabb6739bed22aa7e462e4a361be5fdead5fe14d5ff49288f` and
`aad299784a97f95624ef029fdbe2e6b0e7ecbc385df1c03d5f033fff71fe5648`
for the recovery primary and independent receipts.

## References

- `computations/yang-mills-anisotropic-hamiltonian-limit-prereg.md`—frozen normalized-character, anisotropic coefficient, generator, semigroup and claim-boundary protocol.
- `computations/verify_yang_mills_anisotropic_hamiltonian_limit.py`—414-check primary finite-character generator and product receipt.
- `computations/verify_yang_mills_anisotropic_hamiltonian_limit_independent.mjs`—24-check independent midpoint-integral and Jacobi reconstruction.
- `runs/yang-mills-anisotropic-hamiltonian-limit/verification.json` and `verification-independent.json`—source-bound fixed-graph receipts with `NULL` Clay verdicts.
- `computations/yang-mills-renormalized-gap-scaling-prereg.md`—frozen two-loop scale, simultaneous-volume, renormalized-gap and claim-boundary protocol.
- `computations/verify_yang_mills_renormalized_gap_scaling.py`—80-check standard-library scale and schedule verifier.
- `computations/verify_yang_mills_renormalized_gap_scaling_independent.mjs`—20-check independent Node reconstruction and receipt audit.
- `runs/yang-mills-renormalized-gap-scaling/verification.json` and `verification-independent.json`—source-bound scaling receipts with `NULL` Clay verdicts.
- `computations/yang-mills-rg-gap-matching-prereg.md`—frozen conditional RG endpoint, cumulative-defect, transfer-rate, volume and flatness protocol.
- `computations/verify_yang_mills_rg_gap_matching.py`—139-check source-bound exact, bounded-defect, drift-control and gap-matching verifier.
- `computations/verify_yang_mills_rg_gap_matching_independent.mjs`—32-check independent reconstruction with seven firing mutations.
- `runs/yang-mills-rg-gap-matching/verification.json` and `verification-independent.json`—source- and primary-receipt-bound conditional arithmetic receipts with `NULL` Clay verdicts.
- `computations/yang-mills-transfer-completeness-prereg.md`—frozen finite
  positive-transfer second-moment, reducing-subspace and completeness
  criterion.
- `computations/verify_yang_mills_transfer_completeness.py`—54-check primary
  verifier with four firing mutation controls.
- `computations/verify_yang_mills_transfer_completeness_independent.mjs`—55-check
  independent reconstruction with the scheduled source-binding audit.
- `runs/yang-mills-transfer-completeness/verification.json` and
  `verification-independent.json`—source-bound finite-transfer receipts with
  `PASS` finite criterion and `NULL` Clay verdict.

- `field-experience/counterflow-resonant-addressing-wave-1-report.md`—Wave 1 execution record.
- `field-experience/counterflow-resonant-addressing-pre-registration.md`—Wave 1 frozen protocol and decision tree.
- `field-experience/counterflow-amplitude-phase-kick-wave-2-report.md`—Wave 2 execution record.
- `field-experience/counterflow-amplitude-phase-kick-pre-registration.md`—Wave 2 frozen bounded-kick protocol and raw-mean decision tree.
- `field-experience/counterflow-carrier-demodulation-wave-3-report.md`—Wave 3 carrier-demodulated execution record.
- `field-experience/counterflow-carrier-demodulation-pre-registration.md`—Wave 3 frozen carrier metric and decision tree.
- `field-experience/checkerboard-edge-phase-coupling-wave-4-report.md`—Wave 4 receiver and route result.
- `field-experience/checkerboard-edge-phase-coupling-pre-registration.md`—Wave 4 frozen corridor and receiver protocol.
- `field-experience/source-only-passive-transfer-wave-5-report.md`—Wave 5 source-only passive-transfer record.
- `field-experience/source-only-passive-transfer-pre-registration.md`—Wave 5 frozen source-only construction and discriminator.
- `field-experience/source-only-fieldspace-timing-wave-6-report.md`—Wave 6 projection-free timing record.
- `field-experience/source-only-fieldspace-timing-pre-registration.md`—Wave 6 frozen field-space timing protocol.
- `field-experience/phase-staggered-scale-gap-report.md`—phase-gap campaign synthesis and terminal claim table.
- `field-experience/phase-staggered-scale-gap-pre-registration.md`—parent supplied-wave, radial, and chain protocol with post-execution integrity record.
- `field-experience/phase-staggered-scale-gap-lock-in-pre-registration.md`—independent steady-frequency closure protocol.
- `field-experience/qi-loop-mass-cascade-pre-registration.md`—frozen compact-ring protocol and decision tree.
- `field-experience/qi-loop-mass-cascade-report.md`—one-run compact-ring receipt, mass-sufficiency gates, and independent verification.
- `field-experience/toroidal-coherence-survival-pre-registration.md`—V1 frozen open-space survival protocol.
- `field-experience/toroidal-coherence-survival-v2-pre-registration.md`—frozen V2 initialization protocol.
- `field-experience/toroidal-coherence-survival-v3-pre-registration.md`—frozen normalized-phase diagnostic and complete arm matrix.
- `field-experience/toroidal-coherence-survival-v4-pre-registration.md`—frozen complex128 convergence protocol.
- `field-experience/toroidal-coherence-survival-v5-pre-registration.md`—frozen fourth-order diagnostic-precision protocol and verdict tree.
- `field-experience/toroidal-coherence-survival-report.md`—V1–V5 receipts and adopted campaign verdict.
- `field-experience/toroidal-multiscale-transfer-pre-registration.md`—frozen single-domain spectral-transfer diagnosis and decision tree.
- `field-experience/toroidal-multiscale-transfer-report.md`—spectral endpoint measurements, failed quality gates, and connected-scale boundary.
- `field-experience/toroidal-connected-hierarchy-pre-registration.md`—frozen three-scale graph, controls, convergence gates, and decision tree.
- `field-experience/toroidal-connected-hierarchy-report.md`—verified connected energy redistribution and graph-attribution result.
- `foundations/qi-loop-mass-cascade.md`—conditional compact-ring algebra and framework boundary.
- `computations/navier_stokes_stress_geometry_prereg.md`—fixed Navier–Stokes identities, controls, tolerances, and stopping rule.
- `turbulence/navier-stokes-transfer-boundary.md`—critical transfer, heat correction, and corrected-energy level-set obstruction.
- `turbulence/navier-stokes-stress-geometry.md`—exact stress dynamics, helical covariance assumptions, and measured control classifications.
- `computations/navier-stokes-near-rank-recovery-obstruction-prereg.md`—fixed near-rank determinant-scale and recovery-only schedule.
- `computations/verify_navier_stokes_near_rank_recovery_obstruction.py`—7-check near-rank source-bound verifier.
- `turbulence/navier-stokes-near-rank-recovery-obstruction.md`—full-rank approximants and recovery-only obstruction.
- `computations/navier-stokes-depletion-prereg.md`—fixed fine-scale transfer-response and viscous-absorption controls.
- `turbulence/navier-stokes-depletion-dynamics.md`—exact split, measured response signs, cumulative proof requirement, and matter-binding comparison.
- `computations/navier-stokes-strain-departure-prereg.md`—fixed projected-budget, Gaussian and deadline controls.
- `turbulence/navier-stokes-strain-departure.md`—quantitative departure, spectral-spread estimates and unresolved dynamical control.
- `computations/navier-stokes-critical-recurrence-prereg.md`—fixed critical-remainder and scalar-budget controls.
- `computations/verify_navier_stokes_critical_recurrence.py`—exact derivatives and independent FFT evidence.
- `computations/navier-stokes-forced-concentration-prereg.md`—fixed source budgets, magnification and kinematic concentration controls.
- `computations/verify_navier_stokes_forced_concentration.py`—exact forced derivatives and independent FFT/quadrature evidence.
- `turbulence/cassi-fluid-feasibility.md`—qualified conservative reduction, native-force obstruction and physical-completion decision.
- `computations/cassi-fluid-feasibility-prereg.md`—fixed analytical and actual-flow schedule.
- `computations/verify_cassi_fluid_feasibility.py`—native RK2 controls, independent RK4 reference and immutable receipts.
- `computations/cassi-fluid-thermodynamics-prereg.md`—selected constitutive equations and frozen thermal controls.
- `computations/cassi_fluid_thermodynamics.py`—reacting capillary/thermal evolution.
- `computations/verify_cassi_fluid_thermodynamics.py`—395-check receipt, model trajectories and independent numerical reference.
- `computations/navier-stokes-mixing-budget-prereg.md`—fixed invariant-family analytical and trajectory schedule.
- `computations/verify_navier_stokes_mixing_budget.py`—601-check cumulative mixing receipt and independent spatial reconstruction.
- `computations/navier-stokes-helical-spread-prereg.md`—fixed signed-moment, residual, flow-control and phase-concentration checks.
- `computations/verify_navier_stokes_helical_spread.py`—84-check exact helical-spread and phase-coercivity verifier.
- `computations/navier-stokes-helical-dynamic-depletion-prereg.md`—frozen eight-family helical stress-test schedule, observables and decision rules.
- `computations/verify_navier_stokes_helical_dynamic_depletion.py`—24-run signed-production, alignment and direction-diagnostic verifier.
- `turbulence/navier-stokes-helical-dynamic-depletion.md`—finite helical families and the contradicted universal sign depletion.
- `computations/navier-stokes-strain-band-split-prereg.md`—frozen six-family spectral band-split schedule, decision rules and post-execution record.
- `computations/verify_navier_stokes_strain_band_split.py`—18-run band-split verifier with the packed-strain path, band identity and Parseval checks.
- `runs/navier_stokes_strain_band_split/verification.json`—completed 18-run receipt at `status=PASS` with the five family verdicts and the `INCONCLUSIVE` classification (gitignored run artifact).
- `runs/navier_stokes_strain_band_split/probe.log` and `probe_completed.log`—captured combined stdout and stderr of the bounded attempt and of the completed execution (gitignored run artifacts).
- `computations/navier-stokes-strain-band-split-cutoff-ladder-prereg.md`—frozen six-cutoff ladder schedule, crossing brackets, decision rules and post-execution record.
- `computations/verify_navier_stokes_strain_band_split_cutoff_ladder.py`—six-run ladder verifier that binds the frozen band machinery by digest and reproduces the frozen two-cutoff values exactly.
- `runs/navier_stokes_strain_band_split_cutoff_ladder/verification.json`—completed six-run ladder receipt at `status=PASS` with the `CONTRADICTS` verdict, the ladder table and the crossing brackets (gitignored run artifact).
- `computations/navier-stokes-curvature-clock-prereg.md`—frozen kinematic-identity, closed-form-control and tube-family clock schedule with its decision rules and stopping rule.
- `computations/navier_stokes_curvature_clock.py`—the producer: three closed-form controls of (KC1) and the coherence margin at the vorticity core of the retained helical families.
- `computations/verify_navier_stokes_curvature_clock.py`—125-check source-bound verifier: closed forms re-derived inside the verifier, raw-tensor recomputation, content digest and mutation control.
- `computations/navier-stokes-curvature-clock-saturation-prereg.md`—frozen four-times-horizon saturation window with its reporting and resolution rules.
- `computations/navier_stokes_curvature_clock_saturation.py`—the window producer: rate series, decay classification, projected limit and enstrophy-tail diagnostic.
- `computations/verify_navier_stokes_curvature_clock_saturation.py`—34-check verifier that rebuilds the series, the classification and the projection and anchors the window's initial checkpoint against the clock receipt.
- `runs/20260921_curvature_clock/curvature_clock_receipt.json`—clock receipt at `status=PASS`: identity closed at round-off, margin below the pole over the declared horizon (gitignored run artifact).
- `runs/20260921_curvature_clock_saturation/curvature_clock_saturation_receipt.json`—saturation receipt at `status=PASS`: the tight-pitch margin arrests and reverses below the pole, its late enstrophy tail declared under-resolved, the two resolved families still climbing (gitignored run artifact).
- `computations/navier-stokes-curvature-budget-prereg.md`—frozen enstrophy-budget protocol: the frame closure, the enstrophy form of the margin's rate, the computable cap, the lattice and refinement schedule, the decision rules H0–H9 and the stopping rule.
- `computations/navier_stokes_curvature_budget.py`—the producer: point evaluation of the velocity derivatives at the tracer, its carried position and the field core, the three rate balances, the interval integrals and the advective/unsteady split.
- `computations/verify_navier_stokes_curvature_budget.py`—26-check verifier that recomputes the frame orthonormality, the closure, (KC2)–(KC4), the interval integrals, the split and the cap deficit from the stored values, with content digest and mutation control.
- `runs/20260921_curvature_budget/curvature_budget_receipt.json`—budget receipt at `status=PASS`: cap deficit exactly zero at every evaluated point, (KC2) integrated within the declared bound and refined to a measured finite-difference floor, enstrophy identity at round-off, advective share below one percent (gitignored run artifact).
- `computations/yang-mills-connected-block-prereg.md`—fixed connected-block geometry and local operator schedule.
- `computations/verify_yang_mills_connected_blocks.py`—79-check source-bound connected-block receipt.
- `turbulence/cassi-fluid-phase-current-hydrodynamics.md`—phase-current rotation, helicity topology and viscosity projection boundary.
- `computations/cassi-fluid-phase-current-prereg.md`—fixed current, topology, diffusion and memory schedule.
- `computations/verify_cassi_fluid_phase_current.py`—227-check exact, Fourier, Hopf, memory and raw-array verifier.
- `turbulence/cassi-radiative-material-closure.md`—LTE transfer derivation, material coupling and CassiCosmos implementation boundary.
- `computations/cassi-radiative-material-prereg.md`—fixed comprehensive radiative-material schedule and decision tree.
- `computations/cassi_radiative_material.py`—Planck, M1, slab, source, scattering and diffusion kernels.
- `computations/verify_cassi_radiative_material.py`—33/34 comprehensive source-bound receipt generator.
- `computations/cassi-radiative-material-qualification-prereg.md`—fixed source-step accuracy qualification.
- `computations/verify_cassi_radiative_material_qualification.py`—9-check source-subcycling qualification.
- `computations/yang-mills-vacuum-block-prereg.md`—fixed full-holonomy, exact-vacuum and Gaussian block schedule.
- `computations/verify_yang_mills_vacuum_blocks.py`—305-check primary exact-vacuum block receipt.
- `computations/yang-mills-block-map-prereg.md`—fixed path-holonomy, refined-block and unit-transport schedule.
- `computations/verify_yang_mills_block_map.py`—53-check source-bound cylindrical block-map receipt generator.
- `computations/yang-mills-radial-feshbach-v3-prereg.md`—fixed isolated-square radial, Feshbach, weak-coupling, variable-Ritz and character-cutoff schedule.
- `computations/verify_yang_mills_radial_feshbach_v3.py`—62-check source-bound radial Feshbach receipt generator.
- `computations/verify_yang_mills_radial_feshbach_v3_independent.mjs`—20-check source-independent continuous-angle, continued-fraction, finite-section and cutoff-metric reconstruction.
- `computations/yang-mills-poincare-geometry-prereg.md`—frozen v2 spatial/link geometry, conditional-score recurrence, physical-scaling and receipt-integrity protocol.
- `computations/verify_yang_mills_poincare_geometry.py`—118-check source-bound geometry and recurrence receipt generator.
- `computations/verify_yang_mills_poincare_geometry_independent.mjs`—90-check implementation-independent formula and receipt-integrity audit over the fixed primary schedule.
- `computations/yang-mills-transport-score-prereg.md`—frozen v4 conditional Poisson, transport-score, margin-transfer and Gaussian-control protocol.
- `computations/verify_yang_mills_transport_score.py`—86-check source-bound transport-score and Gaussian verifier.
- `computations/verify_yang_mills_transport_score_independent.mjs`—32-check independent discrete-sine, Jacobi and pivoted-solve reconstruction.
- `computations/yang-mills-su2-schwinger-prereg-v2.md`—finite one-plaquette SU(2) Schwinger-function protocol with scale-aware Perron sign certificate.
- `computations/verify_yang_mills_su2_schwinger_bridge_v2.py`—96-check source-bound finite-regulator vacuum and correlator receipt generator.
- `computations/verify_yang_mills_su2_schwinger_bridge_independent_v2.mjs`—20-check independent matrix, spectral and source-binding reconstruction.
- `runs/yang_mills_su2_schwinger_bridge/verification-v2.json`—96-check source-bound finite-regulator vacuum and correlator receipt.
- `runs/yang_mills_su2_schwinger_bridge/verification-independent-v2.json`—20-check independent receipt binding the primary source and receipt.
- `computations/yang-mills-su2-wilson-2d-prereg-v2.md`—normalization-corrected finite-volume two-dimensional Wilson transfer and tail protocol.
- `computations/verify_yang_mills_su2_wilson_2d.py`—1092-check source-bound Wilson bridge receipt generator.
- `computations/verify_yang_mills_su2_wilson_2d_independent.mjs`—120-check independent Bessel-series, Haar-integral and receipt reconstruction.
- `runs/yang_mills_su2_wilson_2d/verification-v2.json`—1092-check normalization-corrected Wilson bridge receipt.
- `runs/yang_mills_su2_wilson_2d/verification-independent-v2.json`—120-check independent receipt binding both sources and the primary receipt.
- `computations/yang-mills-su2-quantum-schwinger-2d-prereg-v2.md`—normalization-corrected finite two-dimensional SU(2) quantum Schwinger protocol.
- `computations/verify_yang_mills_su2_quantum_schwinger_2d.py`—476-check primary finite transfer and correlator receipt generator.
- `computations/verify_yang_mills_su2_quantum_schwinger_2d_independent.mjs`—ten-check independent reconstruction over all 36 rows.
- `runs/yang_mills_su2_quantum_schwinger_2d/verification-v2.json`—476-check source-bound corrected quantum Schwinger receipt.
- `runs/yang_mills_su2_quantum_schwinger_2d/verification-independent-v2.json`—ten-check independent receipt binding the corrected Wilson and quantum sources and receipts.
- `computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md`—finite $3\times2\times2$ Hamiltonian and character-tail schedule.
- `computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md`—spectator-channel recovery and operator-bound protocol.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`—226-check recovered finite construction.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian_independent.py`—256-check independent reconstruction.
- `computations/yang-mills-finite-graph-cutoff-form-prereg.md`—fixed finite-graph Haar, form-core, tail and noncommuting Ritz protocol.
- `computations/verify_yang_mills_finite_graph_cutoff_form.py`—22-check tridiagonal finite-graph cutoff-form verifier.
- `computations/verify_yang_mills_finite_graph_cutoff_form_independent.py`—18-check independent dense reconstruction and receipt audit.
- `runs/yang_mills_finite_graph_cutoff_form/verification.json`—primary fixed-graph form and spectral-control receipt.
- `runs/yang_mills_finite_graph_cutoff_form/verification-independent.json`—independent source- and receipt-bound reconstruction.
- `computations/yang-mills-local-cutoff-density-prereg.md`—frozen
  multi-volume local cutoff and global-obstruction protocol.
- `computations/verify_yang_mills_local_cutoff_density.py`—16-check
  source-bound local-density verifier.
- `computations/verify_yang_mills_local_cutoff_density_independent.mjs`—17-check
  independent reconstruction and receipt audit.
- `runs/yang_mills_local_cutoff_density/verification.json`—primary
  local-cutoff-density receipt.
- `runs/yang_mills_local_cutoff_density/verification-independent.json`—independent
  source- and receipt-bound reconstruction.
- `computations/yang-mills-thermodynamic-ground-state-prereg.md`—frozen
  fixed-regulator compactness, compatibility and implication-boundary
  protocol.
- `computations/verify_yang_mills_thermodynamic_ground_state.py`—18-check
  finite-identity verifier for the conditional thermodynamic bridge.
- `computations/verify_yang_mills_thermodynamic_ground_state_independent.mjs`—19-check
  independent schedule and receipt reconstruction.
- `runs/yang_mills_thermodynamic_ground_state/verification.json`—primary
  thermodynamic finite-identity receipt with a `NULL` Clay verdict.
- `runs/yang_mills_thermodynamic_ground_state/verification-independent.json`—independent
  source- and receipt-bound reconstruction.
- `computations/yang-mills-euclidean-reflection-positive-prereg.md`—frozen
  finite Wilson reflection, local-marginal compactness, DLR passage and
  implication-boundary protocol.
- `computations/verify_yang_mills_euclidean_reflection_positive.py`—308-check
  source-bound finite-kernel and compactness-control verifier.
- `computations/verify_yang_mills_euclidean_reflection_positive_independent.mjs`—22-check
  independent positive-series, midpoint-Haar, Jacobi-spectrum and receipt
  reconstruction.
- `runs/yang_mills_euclidean_reflection_positive/verification.json`—primary
  finite-kernel support receipt with a `NULL` Clay verdict.
- `runs/yang_mills_euclidean_reflection_positive/verification-independent.json`—independent
  source- and receipt-bound reconstruction.
- `runs/yang_mills_continuum_boundary_audit/verification.json`—52-check v9 hash-bound audit receipt covering recovered finite evidence, fixed-graph cutoff removal, volume-uniform local cutoff control, conditional thermodynamic and Euclidean evidence, the exact fixed-graph anisotropic Hamiltonian limit, the renormalized volume/gap scaling criterion, the conditional RG endpoint-to-gap theorem, excluded defect provenance and the unresolved continuum boundary.
- `computations/verify_yang_mills_continuum_boundary_audit.py`—52-check hash-bound finite-evidence, fixed-graph Hamiltonian-limit, renormalized-scaling, conditional RG-matching and continuum-boundary audit.
- `computations/yang-mills-su2-transport-expansion-prereg.md`—fixed local strip and compact-boundary schedule.
- `computations/verify_yang_mills_su2_transport_expansion.py`—150-check normalized transport expansion.
- `computations/verify_yang_mills_su2_transport_expansion_independent.mjs`—60-check independent coefficient and receipt reconstruction.
- `computations/yang-mills-exact-block-spectral-prereg.md`—frozen v6 seven-link boundary fixtures, cutoff schedule, convergence and qualification rules.
- `computations/verify_yang_mills_exact_block_spectrum.py`—exact Ritz,
  conditional-moment, boundary and nodal-control verifier for the retained
  local execution record.
- `computations/yang_mills_conditional_algebra.py`—shared representation,
  Haar-contraction and conditional-moment helper used by the finite
  diagnostic.
- `computations/yang-mills-nodal-family-prereg.md`—retained twelve-row
  block-path specification, resolution rule and decision tree.
- `computations/verify_yang_mills_nodal_family.py`—schedule-wide nodal family
  verifier; its expected receipt is absent.
- `computations/yang-mills-nodal-surface-prereg.md`—retained two-parameter
  torus specification, conformance angles and decision tree.
- `computations/verify_yang_mills_nodal_surface.py`—surface verifier; its
  expected receipt is absent.
- `computations/yang-mills-bowtie-fibre-prereg.md`—retained eight-link
  loop-carrying exterior specification and qualification rules.
- `computations/verify_yang_mills_bowtie_fibre.py`—conditional-fibre
  verifier; its expected receipt is absent.
- `computations/yang-mills-4x2x2-c1-feshbach-prereg.md`—frozen open
  $4\times2\times2$ graph, rank-two translated source, test-energy and
  conditional-root schedule.
- `computations/verify_yang_mills_4x2x2_c1_feshbach.py`—source-bound
  423-control larger-graph sparse Feshbach receipt generator.
- `computations/verify_yang_mills_4x2x2_c1_feshbach_independent.py`—531-check
  independent sparse-matrix, root and receipt-binding audit.
- `runs/yang_mills_4x2x2_c1_feshbach/verification.json` and
  `verification-independent.json`—primary `FAIL`/`INCONCLUSIVE` and
  independent `531/531` receipts for the open $4\times2\times2$ screen.
- `computations/two-fluid-phi-ray-relaxation-prereg.md`—frozen sixteen-run schedule for the $\varphi$ ray, the imbalance rate, the conservation and closure statistics and the gate sub-question, with the post-execution record.
- `computations/verify_two_fluid_phi_ray_relaxation.py`—probe revision `P1a`: sixteen-run verifier binding the canonical solver by digest and reading the ratio, rate, conservation, closure and openness statistics from it.
- `runs/two_fluid_phi_ray_relaxation/verification.json`—verdict-bearing receipt at `status=PASS` with the `CONTRADICTS` verdict, the per-state table, the gate sub-question and the reproducibility record (gitignored run artifact).
- `runs/two_fluid_phi_ray_relaxation/verification_invocation1.json`—retained first-invocation receipt at `status=FAIL` on the gate amended in place, the baseline of the reproducibility comparison (gitignored run artifact).
- `computations/loop-carrier-projection-dynamics-prereg.md`—frozen fifteen-execution schedule for the evolved complete-loop average, the repeated-context, gate and truncation arms, the loop-mode spectral rates and the four control requirements, with the post-execution record.
- `computations/verify_loop_carrier_projection_dynamics.py`—probe binding the frozen discrete operators and rate constants by digest and reading the projection residual, the mode energies and the four controls from the evolved traces.
- `runs/loop_carrier_projection_dynamics/verification.json`—source-bound receipt at `status=FAIL` with both verdicts null, the eleven gates, the fifteen arm readings and the section 6A seed-invariance readings (gitignored run artifact).
- `runs/loop_carrier_projection_dynamics/invocation.log`—stdout and stderr of the single invocation (gitignored run artifact).
- `computations/loop-carrier-projection-relaxation-prereg.md`—frozen sixteen-execution schedule for the relaxed closure arms, the peak witness, the scale-stable identity and the conversion-rate statistic, with the post-execution record.
- `computations/verify_loop_carrier_projection_relaxation.py`—probe binding the frozen discrete operators and rate constants by digest and reading the peak projection residual, the absolute identity residual, the fitted rate, the arm bracket and the four controls.
- `runs/loop_carrier_projection_relaxation/verification.json`—source-bound receipt at `status=PASS` with both verdicts, the twelve gates, the sixteen arm readings, the relaxed witness and identity readings and the fitted rates with their windows (gitignored run artifact).
- `runs/loop_carrier_projection_relaxation/invocation.log`—stdout and stderr of the single invocation (gitignored run artifact).
- `computations/loop-carrier-projection-split-prereg.md`—frozen split protocol carrying its executor in the same commit, the gate and transport constructions, the six-decade levels, and the post-execution record at `status=FAIL` with both verdicts null.
- `computations/verify_loop_carrier_projection_split.py`—executor binding the protocol body, the frozen discrete operators, the successor's probe and its receipt by digest, with the nineteen-arm static self-check and the refusal path of §0.
- `runs/loop_carrier_projection_split/verification.json`—source-bound receipt of the single invocation at `status=FAIL`, the thirteen gates, the nineteen arm readings, one empty and one first-order sweep, and both withheld verdicts (gitignored run artifact).
- `computations/loop-carrier-gate-load-prereg.md`—frozen gate-load protocol carrying its executor in the same commit, the declared load family, the separation statistic, the two fits and the pre-flight action check, with the post-execution record at `status=PASS` and both verdicts issued.
- `computations/verify_loop_carrier_gate_load.py`—executor binding the protocol body, the spent split executor, the successor's probe and both predecessor receipts by digest, with the idempotent twenty-two-arm self-check and the refusal path of §0.
- `runs/loop_carrier_gate_load/verification.json`—source-bound receipt of the single invocation at `status=PASS`, the thirteen gates, the twenty-two arm readings, the proportional split sweep, the linear load law with its recorded convexity, and the instrument $(\delta^\star,\ell^\star)$ (gitignored run artifact).
- `computations/loop-carrier-attractor-write-prereg.md`—frozen attractor-write protocol carrying its executor in the same commit, the five-horizon two-parameter offset fit with its held rate, the free-rate corroboration, the fragility witness and the branch rule, with the post-execution record at `status=FAIL`, both verdicts null, and the amendment reading measured outside the run.
- `computations/verify_loop_carrier_attractor_write.py`—executor binding the protocol body, the spent gate-load executor, the successor's probe and all three predecessor receipts by digest, with the static self-check, the refusal path of §0, and the corrected per-arm ray-distance reading.
- `runs/loop_carrier_attractor_write/verification.json`—source-bound receipt of the single invocation at `status=FAIL`, the fifteen gates with the unreadable attribution gate, the twelve arm readings over five horizons, the two fits' offsets per arm, the proportional law, the instrument and the ray and oracle controls (gitignored run artifact).
- `computations/loop-carrier-attractor-write-successor-prereg.md`—frozen successor body carrying its executor in the same commit, the two families in one run, the held-and-removed split with its four-level retention rule, the twenty-two gates and thirteen features, and the post-execution record at `status=PASS` with `WRITES`, `STORES` and the joint label `memory`.
- `computations/verify_loop_carrier_attractor_write_successor.py`—executor binding the protocol body, the predecessor attractor-write executor and its body and receipt, the spent gate-load executor and its body and receipt, the split executor, the successor probe and the frozen discrete operators by digest, with the design-probe mode, the converged binding self-check and the refusal path of §0.
- `runs/loop_carrier_attractor_write_successor/verification.json`—source-bound receipt of the single invocation at `status=PASS`, the twenty-two gates with the readable attribution gate and the reproduced amendment reading, the seventeen arm readings over both phases, the two families' fits, offsets and branches, the recorded retention law, the shared-construction and design-probe checks, and the two clocks (gitignored run artifact).
- `computations/loop-carrier-composition-coexistence-prereg.md`—frozen coexistence body: the χ-resolved per-orientation composition profile and its even/odd partition declared coordinate by coordinate, the two gate directions and the counter-write phase, the four pre-flight readings with the null, the eight declared arms, the fourteen gates against the fifteen reported features, the two verdicts with their reserved branches, and the design probe disclosed before the freeze.
- `computations/verify_loop_carrier_composition_coexistence.py`—executor binding the protocol body, the attractor-write executor and its body and receipt, the successor executor and its body and receipt, the spent gate-load and split executors, the relaxation probe, the frozen discrete operators and the successor's short-horizon oracle by digest, with the design-probe mode, the binding can-fail flags, the term-for-term reduction of direction A to the spent right-hand side, and the refusal path of §0.
- `runs/loop_carrier_composition_coexistence/verification.json`—source-bound receipt of the single invocation at `status=PASS`: the fourteen gates, the pre-flight readings in both directions with the exactly-zero null, the eight arms' group-resolved displacements and fits, the two verdicts `RESERVED_ONE_RETAINED` and `RESERVED_NO_B`, the reported-not-gated composition block, the five replicated successor literals with zero mismatches, the twelve design-probe readings, and the two clocks (gitignored run artifact).
- `computations/verify_loop_carrier_kernel_dimension.py`—the closed-form kernel-dimension audit: binds the frozen body, its executor, the bound operator module, the spent write body and the coexistence receipt by digest, reads the declared tuple from the bound module and the run's own arm coordinates, evaluates theorem 6.3's three entries and `dim ker` of the frozen `mode_generator` at the seeded and equilibrium points, proves the reading domain's transposition on declared-shaped probes, and pins all $115$ numbers it prints against a literal table.
- `computations/verify_loop_to_bubble_projection.py`—the frozen discrete operators, bound by the coexistence protocol's §0 row `bound_module_sha256`, carrying the declared tuple (PHI, EXCHANGE, V, R, D_ELL, LAM, OMEGA, D_LOOP) together with the `mode_generator`/`closed_spectrum` pair this audit evaluates for the kernel dimension and the mode spectra.
- `computations/loop-carrier-attractor-write-prereg.md`—the spent write body's recorded offset law $|D_\infty|=(4.3424057234641914\times10^{-4})\,\delta_g^{\,1.0302448806878108}$ labelled `PROPORTIONAL` inside the declared band $[0.9,1.1]$, the exponent §71 reads as the response of a conserved coordinate.
- `computations/loop-carrier-two-coordinate-prereg.md`—the frozen two-coordinate protocol: the declared $r=0$ point, the predicted $\dim\ker=2$, the declared reading domain and the two channel magnitudes.
- `computations/verify_loop_carrier_two_coordinates.py`—its executor: the two channels, the nine arms, the domain probes, the shaped-input dry run and the gate table.
- `runs/loop_carrier_two_coordinates/verification.json`—the receipt: fourteen of fourteen gates, `CONFIRMED_TWO`, `WRITABLE_BOTH`, `RETAINED_BOTH` and the reserved `RESIDUAL`.
- `computations/loop-carrier-rate-entry-sweep-prereg.md`—frozen rate-entry sweep protocol: seven declared points through the crossing, one estimator, the window's own clock, declared `dim ker` per point, and the section-8 record of both invocations and the one amendment.
- `computations/verify_loop_carrier_rate_entry_sweep.py`—the executor: 29 declared arms in one process, fourteen gates, the four branch labels.
- `runs/loop_carrier_rate_entry_sweep/verification.json`—the receipt: fourteen of fourteen gates, `LINEAR_BOTH_SIDES`, `SIGN_DEPENDENT`.
- `runs/loop_carrier_rate_entry_sweep/first-invocation-verification.json`—the archived first invocation of the same body, bound as a section-0 row: `FAIL`, gate 8, on readings that satisfy the amended bound; preserved as the record of the amendment.

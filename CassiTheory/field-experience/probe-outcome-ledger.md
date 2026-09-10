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

Spectral spread bounds the critical work left by enstrophy cancellation. The analytical derivations in `turbulence/navier-stokes-strain-departure.md` §6 give $|W|^2\le(\mathcal V/E)\|\mathcal R\|_2^2$ and the complete-transfer estimate $|F|\le c_{\rm S}\sqrt{\eta\mathcal C}\,Y$, where $\mathcal V=KE-\mathcal C^2/4$ and $\eta=\mathcal V/(KE)$. The latter gives conditional continuation while its coefficient stays below viscosity. Dynamical control of that coefficient is open.

The fixed schedule is `computations/navier-stokes-critical-recurrence-prereg.md`. Its **134 checks pass**, with **24 exact velocity rows**, **48 independent FFT rows**, and maximum normalized discrepancy $1.0766942892814768\times10^{-12}$ against $10^{-10}$.

| Control | Decisive result | Frozen classification and scope |
|---|---|---|
| Zero spectral spread | For the cyclic periodic datum, $\mathcal V(0)=\mathcal V'(0)=0$ and $\mathcal V''(0)=9a^6(3-2\sqrt2)/16>0$. | **CONTRADICTS** universal preservation of zero spread on the torus; no exclusion of quantitatively controlled spread |
| Departure and critical growth | No fixed velocity row has $\delta>0$. | **INCONCLUSIVE** for the universal implication $\delta>0\Rightarrow\mathcal C'\le0$ |
| Scalar-budget closure | The fixed positive-moment construction has $\int_0^1E\,dt=4$, $\delta>0$, $f<0$ and $\mathcal C\to\infty$. | **CONTRADICTS** closure from only the listed scalar identities; no Navier–Stokes trajectory or singularity |

One velocity control has $f=-107.52$, $\mathcal C'=15.2427056401649\ldots>0$ and declining $\mathcal V$. Its $\delta=-53287.808$ distinguishes a negative amplification functional from positive departure. This is an instantaneous full-equation calculation.

The accepted receipt is `runs/navier_stokes_critical_recurrence/verification.json`, schema `cassi.navier-stokes.critical-recurrence.verification.v1`, with adjacent input manifest and frozen sources. All four source identities match current executable inputs and snapshots. The known Laplacian interpolation-deficit criterion diverges on the scalar construction. The Sobolev continuation estimate is an analytical proof separate from the finite checks. Data-controlled critical production, recurrence control and arbitrary-data regularity remain **UNRESOLVED**.

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
checks, 27 trajectories, 82 array values, check rows, trajectory rows and CLI
endpoint. Five original source blobs are byte-identical to the commit; the
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

| Control | Decisive result | Classification and scope |
|---|---|---|
| Numerical reduction and budgets | All fixed algebraic, trajectory, spatial and heat checks pass | **PASS**, qualified invariant-class Fourier approximations |
| Unit initial critical budget | At $N=256$, analytical ratio $\ge1.5$ and numerical ratio $19.4393794552309$ | **CONTRADICTS**, exact continuum lower bound plus qualified finite trajectory |
| Amplitude-linear bound at fixed $\nu,T>0$ | The continuum lower ratio grows without bound with $N$ | Excluded by the analytical construction |
| Nonlinear bound within this family | Explicit finite bound from the critical multiplier difference | Derived for the one-way-coupled invariant class |
| Arbitrary-data critical work and global regularity | General three-dimensional feedback remains uncontrolled | **UNRESOLVED** |
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
interacting finite box has a positive physical gap; a volume-uniform
bound and four-dimensional continuum construction remain open.

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
| Full interacting continuum mass gap and Cassi microscopic identification | Uniform vacuum-subtracted estimate and quantum-field construction absent | **UNRESOLVED** |

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

## References

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

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

The source-free $SU(2)$ lattice Hamiltonian has a volume-uniform
vacuum-subtracted gap at sufficiently strong bare coupling by application
of Yarotsky's stability theorem. A gauge-invariant finite-depth unitary
removes first-order electric-vacuum loop creation while retaining full
holonomies and an exact bounded local quadratic remainder.
`foundations/loop-to-bubble-projection-theorem.md` §§9.10–9.12 supplies
the theorem hypotheses, local form estimate and connected remainder proof.

The fixed schedule in `computations/yang-mills-connected-block-prereg.md`
passes **79 primary checks**. The separate raw-artifact reconciliation
passes **31 checks**, including direct local matrix reconstruction and
an independent Jacobi evaluation of the remainder norms. The two analytical
reviews and their mathematical reconciliation qualify the theorem
application separately from these finite controls.

| Control | Decisive result | Classification and scope |
|---|---|---|
| Periodic lattice geometry | Sides $4,6,8$ give $192,648,1536$ links and 24 disjoint-link plaquette layers | **SUPPORTS**, fixed finite inventories and coloring |
| Exact local operator identities | 21 matrix cases; maximum absolute discrepancy $4.97379915032\times10^{-14}$ against $10^{-11}$ | **SUPPORTS**, fixed local rotation and Hamiltonian controls |
| Independent reconstruction | Maximum matrix discrepancy $4.44089209850\times10^{-16}$ and remainder-norm discrepancy $3.46944695195\times10^{-18}$ | **PASS**, complete raw local matrix schedule |
| Single-square remainder | Maximum measured $\|R_\square\|/x^2=0.539326266409$; analytic bound $(2+\sqrt2)/3=1.13807118746$ | **SUPPORTS**, fixed points; all-real-$x$ bound follows analytically |
| Volume-uniform interacting gap | Positive theorem gap under $64/g^4\le\beta_{\mathrm Y}$, with symbolic $\beta_{\mathrm Y}>0$ | **ADOPT**, established theorem applied at sufficiently strong bare coupling |
| Exact finite-depth dressing | 24 layers, $2^3$ coarse cells, relative coefficient $32|x|/3$ and bounded local remainder $C_Dx^2$ | **ADOPT**, regulated operator identity; exact remainder retained |
| Weak-bare-coupling uniform estimate, continuum theory and mass, Cassi microscopic identification | No construction or bound in these regimes | **UNRESOLVED** |

`runs/yang_mills_connected_blocks/verification.json` retains the full
arrays, checks and symbolic identities, with its adjacent input manifest
and frozen source snapshots. The same directory contains
`raw_uniform_review.txt`, `raw_dressing_review.txt`, the independent local
`reconcile.mjs` and the final `reconciliation.json`, which binds the raw
receipt, review and source bytes by SHA-256. Numerical theorem constants,
a critical coupling and continuum masses are unevaluated.
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
`computations/verify_yang_mills_vacuum_blocks.py`. The primary Python receipt
passes **305 checks** over five full-holonomy fixtures, 45 local-energy rows
and ten connected Gaussian rows. The final independent JavaScript
reconciliation passes **120 checks**.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Full-holonomy group, derivative and local-energy controls | Maximum group, gauge, first-derivative and normalized-energy errors are $1.33\times10^{-15}$, $4.44\times10^{-16}$, $6.31\times10^{-13}$ and $3.28\times10^{-8}$ | **SUPPORTS**, fixed finite fixtures and declared local schedule |
| Independent Gaussian reconstruction | Maximum matrix and scalar discrepancies are $1.77\times10^{-14}$ and $9.77\times10^{-13}$ | **SUPPORTS**, ten connected Gaussian controls |
| Exact finite-vacuum identity | $\Delta_{\mathrm{phys}}=(g^2/2a)\lambda_{\mathrm{gi}}$ by the ground-state transform | **ADOPT**, every finite regulated theory under the displayed domain conditions |
| Full-holonomy block theorem | $\lambda_{\mathrm{gi}}\ge\lambda_{\mathrm{loc}}/(A_{\mathrm{AT}}\rho)$ under exact-vacuum fibre rates, approximate tensorization and cover assumptions | **ADOPT CONDITIONAL**, sufficient theorem; weak-coupling estimate open |
| Equal-weight one-plaquette exponential | Rejected as the exact interacting vacuum for $x>0$ on the stated even periodic $L\ge4$ and open-box families | **CONTRADICTS**, the trial product state remains only a control |
| Conditional gaps alone | No volume-uniform rate follows without variance reconstruction or an equivalent global estimate | **CONTRADICTS**, proposed shortcut |
| Static pure configuration marginal | In the coupled Gaussian control, $Q_{RE}\ne0$ gives a mixed reduced state with momentum covariance missing from the pure square root of the configuration marginal; exact spectral reduction is energy-dependent through the Feshbach–Schur resolvent | **CONTRADICTS**, exact quantum block reduction |
| Weak-coupling continuum mass gap | Uniform exact-vacuum tensorization, local rates, continuum construction and mass identification remain missing | **UNRESOLVED** |

The primary receipt, input manifest, frozen source snapshots, two analytical
reviews and reconciliation chain are in
`runs/yang_mills_vacuum_blocks/`. `publication.json` seals the current theorem,
fixed protocol, bound verifier, independent checker and receipt hashes without
rerunning the scientific schedule. The retained audit failures are
`reconciliation.json`, `reconciliation_recovery.json`,
`reconciliation_recovery2.json` and `reconciliation_recovery3.json`. They
respectively expose a complex-generator implementation error, non-invariant
componentwise gradient comparison, cancellation-sensitive absolute finite
differences and an omitted $m^2$ in the independent Gaussian scale. The
qualified independent sources are `reconcile_recovery4.mjs` and
`reconciliation_recovery4.json`.

Independent analytical reviews verify the approximate-tensorization
Rayleigh-compression proof, finite-lattice quantifier, conditional
density-ratio comparison and real left-invariant derivative convention. They
find no remaining line-level mathematical faults in §§9.13–9.16. The physical
parameter count, empirical prediction catalog and QF/DQ/GQ
microscopic-identification verdicts are unchanged.


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
the fixed path-holonomy schedule. The generated
`runs/yang_mills_block_map/` directory, primary receipt, independent checker,
analytical reviews and publication seal are not present in this checkout. The
reported 53 primary and 169 independent checks are retained as
documentation-only provenance; they are not current artifact-backed
execution evidence and are not rerun by this correction.

The table below preserves the stated analytical dispositions of the documented
schedule. Its numerical entries do not carry a current receipt claim.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Normalized-Haar path pullback | Nonempty edge-simple, pairwise edge-disjoint paths push product Haar to product Haar; $J^*J=I$, endpoint gauge covariance holds and internal transformations cancel | **ADOPT**, finite graphs under the stated path and representative hypotheses |
| Electric Casimir compression | On the smooth cylindrical core, $\mathcal E_fJ=J\sum_c n_c\mathcal E_c^{(c)}$ for either path orientation; fixed fundamental and adjoint errors are at most $8.89\times10^{-16}$ | **ADOPT**, isotropic bi-invariant independent-link Casimirs under the stated hypotheses |
| Genuine $2\times2$ refinement | Four absent-link plaquette characters have zero conditional means and identity Gram matrix; the measured moment/Gram errors are at most $2.23\times10^{-16}$ and $1.12\times10^{-16}$ | **SUPPORTS**, fixed nine-vertex, twelve-link fixture |
| Bare full-Hamiltonian block | $\|Qh_fJ1\|_2=2x_f$ and $\|QH_fJ1\|_2=2/(a_fg_f^2)$; no coarse operator can remove this orthogonal component on the constant state | **CONTRADICTS**, exact intertwining by this bare cylindrical map on the fixed genuine refinement only |
| Pure graph subdivision | Retaining one outer face adds no elementary spatial faces and gives $QW_f=0$ | **SUPPORTS** the control; path length $b>1$ alone does not determine leakage |
| Weak-coupling bare-vacuum shortcut | The fixed electric-vacuum ratio is $x_f/3=2/(3g_f^4)$ and diverges as $g_f\to0$ | **CONTRADICTS**, an $x_f$-uniform unweighted small-perturbation argument for this bare map; resolvent-weighted estimates are not excluded |
| Interacting block and continuum mass | No gauge-compatible interacting fibre, generated-term closure, uniform Feshbach-resolvent bound, weak-coupling volume estimate, thermodynamic limit or continuum field is constructed | **UNRESOLVED** |
| Cassi interaction survival | The hypothesized Cassi scale law supplies no microscopic link state, interacting fibre or transfer operator to which the block criterion can be applied | **UNRESOLVED**; no microscopic Cassi identification follows |

The fixed-refinement formulas and the scope boundary remain explicit in
`foundations/loop-to-bubble-projection-theorem.md` §9.17. A fresh source-bound
execution and independent reconstruction would be required before the
53/169 counts or publication disposition could be used as current evidence.
The analytic result still rejects the bare-map shortcut at the declared
refinement and identifies the interacting fibre or equivalent Feshbach
transfer operator as the next mathematical target; it does not establish a
continuum Yang–Mills theory or mass gap.


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
$d\mu_J^{\mathrm{Ritz}}=|\Omega_J|^2dU$. The source-bound receipt
`runs/yang_mills_exact_block_spectrum/verification.json` executes the
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

The receipt binds the protocol, the source and the shared representation
helper by SHA-256, with source digest
`fcca48a2c2721f5c9068eff65245ba7752e7d659e27b37efeeca9f7cc47f24fd` and
protocol digest
`a2cf6db4c8a82d69982d2df3b9ebd5673c17705dd092969bb161d365a7285446`. The
analytical statements are
`foundations/loop-to-bubble-projection-theorem.md` §9.23. The finite controls
guard the algebra and the declared scope without establishing the interacting
vacuum estimate.


## 28. Schedule-wide confinement of the nodal Ritz obstruction

The frozen protocol `computations/yang-mills-nodal-family-prereg.md` extends
the §27 nodal control from one row to the twelve scheduled rows of the
seven-link block. The source-bound receipt
`runs/yang_mills_nodal_family/verification.json` evaluates the normalized
Ritz wavefunction along two 49-point block paths that rotate one block link
through $e^{i\varphi\sigma_3/2}$, with the other block links and the exterior
at the identity, and counts resolved sign changes under the frozen
$10^{-10}$ resolution rule.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
|| Sealed-control reproduction | The path endpoints at $J=1$, $x=1$ reproduce $2.094120531213694$ and $-0.03437408376157869$ to $4.4\times10^{-16}$, and the path amplitudes are real to $8.5\times10^{-18}$ relative | **ADOPT** as the conformance control of the extension against the sealed analytic nodal control |
|| Path sign changes | Seven of twelve rows carry a resolved sign change, five with odd parity and two at $J=2$, $x=4,16$ with even parity and negative excursions of resolved modulus $1.2\times10^{-2}$ and $4.8\times10^{-3}$; five rows carry none | **CONFINED** to the strong-coupling half of the schedule; the witness-free rows bound neither the surrogate's gap nor its sign constancy |
|| Onset with cutoff | The obstruction appears at $x=1$ at $J=1$ and only at $x=4$ at $J=2,3$; the $x=1/4$ rows are witness-free at every cutoff with path minima $0.675$, $0.706$ and $0.704$ | measurement, not proof: a one-parameter path can miss a codimension-one nodal set |
|| Frozen decision tree | The preregistered rules return **NODAL_CONFINED**: not every row shows an odd number of resolved sign changes and rows with zero resolved sign changes exist | **NODAL_CONFINED**; the raw count of nodal witnesses is not the verdict |
|| Vacuum and continuum | The exact regulated vacuum measure remains strictly positive by the exact criterion, and no row of this extension constrains it | **UNRESOLVED**: the exact-vacuum fibre rate, conditional-rate cutoff removal, uniform interacting recovery, thermodynamic limit and continuum construction stay open |

The receipt binds the protocol, the source, the §27 source and the shared
helper by SHA-256, with source digest
`908150965c6672a022aba4596b9515acaf839c91500a0698c8d6ff52894ced7c`. The
analytical statements are
`foundations/loop-to-bubble-projection-theorem.md` §9.23.


## 29. Two-parameter nodal surface search

The frozen protocol `computations/yang-mills-nodal-surface-prereg.md`
replaces the one-parameter block paths by a two-parameter torus family that
rotates block links $0$ and $1$ independently on a $33\times33$ grid. Its
source-bound receipt `runs/yang_mills_nodal_surface/verification.json`
searches all 66 grid lines of each of the twelve scheduled rows for resolved
sign changes and cross-checks the two one-parameter lines against the sealed
one-parameter receipt on the seventeen common angles.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
|| Conformance to the one-parameter receipt | Both one-parameter lines reproduce the sealed path tables at the common angles to $7.1\times10^{-15}$ or better | **ADOPT** as the conformance control on the two-parameter family |
|| Grid-line witnesses | Seven rows carry resolved sign changes on 12–62 of the 66 grid lines, with 16–162 total changes; the remaining five rows carry none on any line | **CONFINED**: the witness boundary of the one-parameter family is stable under the two-parameter family |
|| Silent rows | The $x=1/4$ rows at every cutoff and the $x=1$ rows at $J=2,3$ keep grid minima $0.675$, $0.706$, $0.704$, $0.277$ and $0.201$ over 1089 grid points each | no positivity or sign-constancy proof: a finite grid cannot certify a sign |
|| Frozen decision tree | At least one row shows no resolved sign change on any grid line | **WITNESS_CONFINED** |
|| Vacuum and continuum | The exact regulated vacuum measure remains strictly positive and the conditional-rate cutoff-removal obligations are untouched | **UNRESOLVED** |

The receipt binds the protocol, the source, the one-parameter protocol,
source and receipt, the §27 source and the shared helper by SHA-256, with
source digest
`6f215f5961fad3b654830392d18b8ce33464660893a5f5ad346f218ad1d97f77`. The
analytical statements are
`foundations/loop-to-bubble-projection-theorem.md` §9.23.

## 30. Loop-carrying exterior bowtie fibre

The frozen protocol `computations/yang-mills-bowtie-fibre-prereg.md` replaces
the seven-link tree exterior with an eight-link exterior plaquette attached to
the block at one vertex. It schedules doubled cutoffs $J=1,2,3$, couplings
$x\in\{1/4,1,4,16\}$ and $\theta=k\pi/8$ for $k=0,\ldots,8$. The
source-bound receipt `runs/yang_mills_bowtie_fibre/verification.json` contains
108 rows and binds `computations/verify_yang_mills_bowtie_fibre.py`, the
protocol, `computations/verify_yang_mills_exact_block_spectrum.py` and
`computations/yang_mills_conditional_algebra.py` by SHA-256.

| Control or claim | Decisive result | Classification and scope |
|---|---|---|
| Analytic and receipt controls | State-space dimension, kinetic labels, normalization, gauge-orbit invariance, Hermiticity, positivity and exclusive receipt creation all pass | **PASS** for the declared finite contraction and receipt controls |
| Loop-holonomy boundary response | Every one of the twelve $(J,x)$ blocks exceeds the orbit threshold, with $\min_{J,x}\max_\theta|\log Z(\theta)|=0.2995170783$; at $J=1$, $x=1$, $Z$ ranges from $0.9160251472$ to $2.3613249509$ | **SUPPORTS_BOUNDARY_SENSITIVITY** for the finite loop-carrying exterior |
| Retained-rate qualification | All 108 rows classify **INCONCLUSIVE**: 36 fail only the full-space residual bound, 27 fail only the nested restriction-rank rule and 45 fail both; the maximum residual is $15.2349853487$ against the $10^{-2}$ bound | **INCONCLUSIVE**: the retained numbers supply no uniform fibre-rate estimate |
| Exact vacuum and continuum target | The exact-vacuum fibre rate, transport score, cutoff removal, uniform interacting recovery, thermodynamic limit and continuum construction remain unsupplied | **UNRESOLVED** |

The source digest is
`19e3208831ce4af966cd6de8e0079e083ea55602e0d3fb1f132b71227bfb63ef` and the
protocol digest is
`b71f184c0c45c9eacb58e0756758baacca825bf18c951ffb651591dd76d714ae`. The
analytical interpretation is `foundations/loop-to-bubble-projection-theorem.md`
§9.24.


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
The result removes the ambiguity of an arbitrarily selected finite observable
list. It does not construct the exact RG map, the volume- and
regulator-uniform lower spectral bound, the strong recovery transport in
(YM265), the scale matching in (YM266), or the continuum representation
required for a physical mass gap.


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


- `computations/yang-mills-volume-adapted-feshbach-prereg.md`—all-local-action retained family and explicit rank/domain decision tree.
- `computations/verify_yang_mills_volume_adapted_feshbach.py`—50-control primary rank-boundary receipt.
- `computations/verify_yang_mills_volume_adapted_feshbach_independent.py`—53-check independent audit of the rank-boundary receipt.
- `computations/yang-mills-volume-adapted-feshbach-v2-prereg.md`—reserved-plaquette retained family protocol.
- `computations/verify_yang_mills_volume_adapted_feshbach_v2.py`—84-check primary reserved-plaquette bridge verifier.
- `computations/verify_yang_mills_volume_adapted_feshbach_v2_independent.py`—85-check independent reserved-plaquette arithmetic and provenance audit.
- `runs/yang_mills_volume_adapted_feshbach_v2/verification.json` and `verification-independent.json`—source-bound finite reserved-plaquette receipts with unresolved volume-uniform, continuum and mass-gap bounds.

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
- `computations/verify_yang_mills_exact_block_spectrum.py`—sealed exact Ritz, conditional-moment, boundary and nodal-control receipt generator.
- `computations/yang_mills_conditional_algebra.py`—shared representation, Haar-contraction and conditional-moment helper bound by receipt hash.
- `computations/yang-mills-nodal-family-prereg.md`—frozen twelve-row block-path family, resolution rule and confinement decision tree.
- `computations/verify_yang_mills_nodal_family.py`—source-bound schedule-wide nodal family verifier and receipt generator.
- `computations/yang-mills-nodal-surface-prereg.md`—frozen two-parameter torus family, conformance angles and confinement decision tree.
- `computations/verify_yang_mills_nodal_surface.py`—source-bound grid-line nodal surface verifier and receipt generator.
- `computations/yang-mills-bowtie-fibre-prereg.md`—frozen eight-link
  loop-carrying exterior schedule and qualification rules.
- `computations/verify_yang_mills_bowtie_fibre.py`—source-bound bowtie
  conditional-fibre verifier and analytic-control receipt generator.

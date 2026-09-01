# Epistemic Map—Every Document by Tier

## Status: Reference—August 2026

## Abstract

This repo's papers are claims, and claims carry tiers. This map indexes every theory document by epistemic tier—the navigation the directory tree deliberately does not encode, because tiers change and paths should not. Use it to answer "what have we actually derived?" or "what are we speculating about?" in one glance. The registry (`open-questions-cassi-answers.md`) remains the authority for per-question tiers; this map is navigation, not adjudication.

**Tier definitions** (as in `hypotheses/README.md`):

- **Derived**—a priori mathematical consequence of $\varphi$ + the two-fluid PDE; zero fitted or anchored constants.
- **Calibrated**—framework form with the constant's value anchored to a stated observation; downstream claims using the pinned value inherit the anchor.
- **Mapped**—placement (rung, exponent, offset, candidate, normalization) selected or fitted to data; the fit is recorded in the Fit-Status Ledger (`parameter-inventory.md` §10).
- **Hypothesized**—mechanism proposed with pinned $\varphi$-power; testable prediction exists.
- **Speculative**—framework-consistent; mechanism sketched, prediction not yet pinned.
- **Creative**—exploration, not a claim (`speculations/creative-extensions/`); exempt from the evidential ladder.

Reference / Index / Synthesis / Plan / Registry / Catalog are genres rather
than epistemic tiers. "Tested" is a verification marker that attaches to a
tier and does not upgrade it. Use only the six evidential tiers defined above.

Tiers below are taken from each document's Status header. Compound headers are quoted as written and placed under the stronger claim. Derivation papers are placed by the tier of their result per the registry.

**Maintenance rule:** when a document's tier changes, update its Status header, its row here, and the registry—**the file never moves**. This map is the one place the epistemic ladder lives as a ladder.

## 1. Derived

| Document | Status | Summary |
|----------|--------|---------|
| `foundations/cascade-suppression-formula.md` | Derived conditional | Conditional $\varphi^{-N}$ attenuation relation under a declared per-rung input (wedge tool) |
| `foundations/dimensionful-cascade.md` | Derived conditional (exact identity given external Planck anchor) / Calibrated (epoch horizon coordinate) / Mapped or Hypothesized (physical rung labels) | Exact relation $\ell_n = \ell_{\text{Pl}}\varphi^n$ conditional on the external $\ell_{\text{Pl}}$ anchor; $n\approx292$ is an epoch-dependent horizon coordinate; physical scale assignments retain Mapped or Hypothesized status |
| `foundations/wake-geometry.md` | Derived supplied-wave structure; tested conditional second-order realization; Hypothesized physical condensation and closure imprint—August 2026 | Adjacent-rung supplied carriers close the next scale and have exact alternating demodulated beat parity. The default second-order wave branch has imbalance threshold $\Omega_g=\varphi\omega_{0,\mathrm{wave}}$ and reaches $k_\rho/k_\epsilon=\varphi$ only under the supplied drive $\Omega_*=\varphi^{3/2}\omega_{0,\mathrm{wave}}$; ordinary radial layers are additive, the current source supplies no selector, and the node-to-condensation map is open |
| `foundations/bubble-lattice-fabric.md` | Derived transverse geometry; Hypothesized axial/radial coordinate assignments—August 2026 | 3D staggered checkerboard organizing geometry; axial factor, along-string period, dimensionless rung count, and across-rung extension remain Hypothesized coordinate assignments; physical $d=3$ identification remains Hypothesized, and the ansatz does not by itself identify a transported inter-rung field |
| `foundations/string-bubble-projective-map.md` | Derived conditional projective geometry, affine group action, and conversion-only meridional flow; Hypothesized phase dynamics, physical identification, and fivefold selector—August 2026 | The complex CassiFI doublet projects through $\mathbb{CP}^1$ to the canonical density pair and maps affinely to the selected quadratic bubble shell; the conjugated $U(1)$ action preserves the pullback shell metric and canonical conversion gives meridional relaxation. SB1–SB5 pass independently. Microscopic projection, shell identity, phase dynamics, and spontaneous $m=5$ locking remain open |
| `foundations/loop-to-bubble-projection-theorem.md` | Derived conditional projection, bubble map, and population spectrum; Hypothesized microscopic physical identification—August 2026 | Four direction-preserving Yang/Yin populations on one closed support project exactly to the canonical PDE under common gate and transport assumptions. Their species Gram matrix fills the affine bubble volume, the rank-one boundary gives the projective shell, and the frozen internal generator has an explicit zero-mode gap. The carrier identity, phase law, physical scale ratio, QF1-to-carrier state map, and quantum statistics remain open |
| `foundations/cassi-first-principles.md` | Derived PDE; **C / Asserted Qi definition**; Asserted single-channel $g(q)$ input—August 2026 | Two-fluid PDE in primary nonnegative density fields $E_Y,E_I$ with $\rho=E_Y+E_I$; optional positive-root lift $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ supplies amplitude-plane diagnostics; the canonical $q$ rational form and bare $\varphi^{-2}$ floor are constitutive choices evaluated in dimensionless/reference-normalized solver variables, with physical-density use requiring an external $\rho_*$ and no derived scale; Qi coherence; conversion openness and gate-status audit; canonical conversion is a rank-one density-plane relaxation with conserved $\rho=E_Y+E_I$ and eigenvalues $0$ and $-\lambda(1-q)(1+\varphi)$, not an SO(2) rotation; exact conversion-flow exposure $\Delta\chi_F=-(1+\varphi)^{-1}\ln|\varepsilon_1/\varepsilon_0|$ and relative conversion-clock rate $(1-q)/(1-q_0)$ are Derived conditional, while universal proper-time use is Hypothesized; measured density-plane rate $d\theta_d/dt = \lambda(1-q)\rho\varepsilon/(E_Y^2+E_I^2)$ (§2.6, `two-fluid/run_winding_rate_probe.py`); amplitude-plane phase $\theta_\Psi=\operatorname{atan2}(\sqrt{E_I},\sqrt{E_Y})$, density-plane angle $\theta_d=\operatorname{atan2}(E_I,E_Y)$, and Stokes double angle $\Theta_S=2\theta_\Psi\pmod{2\pi}$ remain distinct diagnostics |
| `foundations/phi_attractor_synthesis.md` | Derived (attractor synthesis) / Calibrated ($\xi$ pin) / Mapped ($\alpha_{\text{halo}} = 0.7$ nominal—ledger) | $r \to \varphi$ attractor synthesis across regimes |
| `foundations/wu-xing-derivation.md` | Derived (w = 5, gap, r₀; single input: coherence postulate—verified 2026-08-11) / Calibrated (w₀ via the DESI-anchored coupling form—ledger) | $w = 5$ derived (coherence criterion over all $w$: only $\{1,2,3,5\}$; pentagon geometry); the named C-class/framework convention $\lambda=0.1$ is Asserted, while the implementation class default is $\lambda=0.02$; $\lambda=1/(2w)$ is a Hypothesized Wu Xing linkage requiring independent cycle-time and dynamical closure (`cassi-physics.md`) |
| `foundations/wu-xing-cycle-structure.md` | Derived (cycle geometry, coupling, ring algebra) / Tested (ke ring PDE 2026-07-31, WX1 gate level 2026-08-01) / Hypothesized (affinity gradient, clinical profile) | Two coherent 5-cycles (sheng/ke); control-ring algebra; 5↔13 chakra partition |
| `foundations/xi-derivation.md` | Derived conditional on the quadratic-coupling input (imbalance inverse-square: $\xi=(\pi/\rho)^{-2}=\varphi^6$, $\pi/\rho=\varphi^{-3}$ from the attractor) / Calibrated empirical pin (Milky Way anchor—ledger row 498)—August 2026 | $\xi=\varphi^6=(\pi/\rho)^{-2}$ conditional on the inverse-square coupling input; at the reference state $\rho=\varphi$, $s=\pi/\rho=\varphi^{-3}$, $q=0.872677996$ and $G_{\mathrm{eff}}/G=3.726779962$; the $\varphi^3G$ value is the high-density fixed-$s$ endpoint, not a canonical free-$q$ ceiling |
| `foundations/quark-confinement.md` | Derived (tube extensivity + cell quantization; $\kappa = 2\pi$ conditional on the pitch convention and the Hypothesized phase-to-rung coordinate mapping; inputs: gate saturation, one-cell quantization) | QCD at step 95; saturated-gate flux tube $E(r) = \mu r$, $\mu = 2\pi(M_{\text{Pl}}/\varphi^{95})^2 = 0.1836$ GeV² (+2.0% vs measured); $P_{\text{break}} \approx \varphi^{-4506}$ |
| `foundations/proton-coherence-budget.md` | Mapped proton coordinate / Derived conditional coherence-product arithmetic and scale-current identities / Hypothesized stochastic, endpoint, and proton realizations—August 2026 | The independent-step profile gives the conditional $\varphi^{4506}$ cycle count. A distinct Planck-to-proton circuit has $J_{Y,\mathfrak s}=-J_{I,\mathfrak s}$, zero total scale-number flow, and nonzero relative current; its endpoint converters, scale tension, localized mixed-curvature solution, proton quantum numbers, and decay rate remain open |
| `foundations/sector-coupling-derivation.md` | Derived conditional on $\delta = 3$ (rung identity; coupling form as documented), coefficient Hypothesized (v₀ input Calibrated, N_pde normalization Mapped—ledger)—August 2026 | Dirac↔two-fluid sector-coupling scale $\kappa_s = C\varphi^{-6}/v_0^2 = C M_{\text{Pl}}^{-2}\varphi^{154}$; the displayed $C=1$ candidate gives $0.92$ TeV$^{-2}$ and $\kappa_s^{-1/2}\approx1.04$ TeV, while the O(1) coefficient remains open |
| `foundations/bubble-edge-geometry.md` | Derived transverse geometry; Hypothesized axial/radial coordinate assignments; Tested radial-ladder realization REJECT; conditional threshold relation—August 2026 | The directional edge proxy remains conditional on the selected boundary and constitutive map. The multiplicative interior ring coordinate is Hypothesized; canonical and undriven second-order emergence tests reject its current dynamical realization. The driven second-order control gives additive phase layers, phase-only staggering remains gapless, and link-magnitude modulation opens a gap only as a supplied conditional control |
| `foundations/wa-pentagon-gate.md` | Derived ($\xi = \varphi^6$) / Hypothesized (5-channel) | $w_a = +0.012$ via $\xi$: $2.7\sigma$ baseline; with the ratified coupling $1.25\sigma$ (B2, unstable); the stable realization (10/12): pure-Λ window fit $(-1, 0)$, $4.17\sigma$/$2.61\sigma$; 5-channel shift Hypothesized (ODE pending) |
| `principles/de-resonance-principle.md` | Derived number-theory and topological identities / Derived conditional counterflow selection / Tested PC1–PC7 and passive $M_0$ REJECT / Hypothesized physical phase-current and de-resonance realization—August 2026 | The declared density target $E_Y/E_I=\varphi$ transfers to the local continuum phase-gradient ratio under counteroriented compact currents, equal mobilities, zero net current, and adiabatic adjustment. A nonzero scalar loop amplitude conserves winding exactly; the frozen passive $M_0$ arm passes descent and produces zero $\varphi$-band sectors, while the microscopic current and phase-slip laws remain open |
| `foundations/qi-loop-mass-cascade.md` | Derived conditional counterflow selection and supplied-ring algebra / Tested conditional branches and passive $M_0$ REJECT / Hypothesized physical realization—August 2026 | The conditional continuum target $\alpha\to\varphi$ supplies Fibonacci record near-closures and the supplied Hamiltonian gives a positive stationary ring; passive $M_0$ produces zero $\varphi$-band sectors, while fixed compact sectors require an unprovided transition law and 1,163 stable primitive modes with coefficient sensitivity leave unique physical mass selection open |
| `standard-model/sm-from-phi.md` | Derived standard gauge-chain algebra; Hypothesized density-to-isospinor lift, inter-rung transport law, particle/gauge confinement extension, and electroweak coupling mechanism with asserted Weinberg boundary; Mapped conditional CKM phase candidate—August 2026 | Gauge-chain ordering and standard Lie-algebra dimensions are Derived; the density-to-isospinor lift, transport, confinement, and coupling mechanisms are Hypothesized; the CKM phase candidate is Mapped |
| `standard-model/sm-radiative-corrections.md` | Derived loop equations; Asserted $\varphi$-boundary inputs; Calibrated $\mu_*$ crossing—August 2026 | Derived SM loop equations with asserted $\alpha_{\mathrm{GUT}}$ and $\sin^2\theta_W$ boundary assignments; calibrated $\mu_*\approx233$ GeV crossing; standard relations close to 0.01–0.1%, while $\alpha_s(m_Z)$ is $2\times$ too small and $\alpha_1,\alpha_2$ remain about 25% off |
| `standard-model/su2-gauge-extension.md` | Derived SU(2) gauge algebra and mass matrix; Hypothesized density-to-isospinor, chiral/flavor observation map and coupling-normalization candidate with asserted Weinberg boundary; Mapped conditional CKM phase—August 2026 | The SU(2) algebra and mass matrix are Derived for an added complex sector; the density-to-isospinor map, chiral/flavor map, and coupling normalization are Hypothesized; the CKM phase is Mapped |
| `particles/cassi-yang-yin-particles.md` | Hypothesized | Conditional complex counterpropagating/NLS extension; canonical real-density equations do not supply chirality or an independent phase |
| `cosmology/cosmology-from-phi.md` | Derived formation and structure / Hypothesized inflation and baryogenesis mechanisms / Mapped inflation and baryogenesis observables / Calibrated $w_0$ coupling form—August 2026 | Formation and structure are Derived; inflation and baryogenesis mechanisms are Hypothesized; inflation and baryogenesis observables are Mapped; the $w_0$ coupling form is Calibrated |
| `gravity/three-body-analytical.md` | Derived conditional on the selected $d = 3$ computational/physical domain and displayed PDE force sign—August 2026 | Point-particle reduction is conditional on the selected $d=3$ domain and displayed PDE force sign; body-dependent coupling and conversion-driven masses remain; an attractive point-particle branch requires a separate Hypothesized sign-changing force extension |
| `turbulence/kolmogorov-from-phi.md` | Derived/Hypothesized—August 2026 | The Kolmogorov $-5/3$ law is conditionally inherited under Navier–Stokes assumptions; the $\varphi$-break, deviation, gravity, and quality spectra are optional Hypothesized closures |

## 2. Calibrated

| Document | Status | Summary |
|----------|--------|---------|
| `cosmology/observational_constraints.md` | Calibrated ($w_0$ coupling form, $\xi$ pin—ledger) / Mapped ($\alpha_{\text{halo}}$ nominal, halo $q$—ledger) | DESI DR2 fit; $w_a$ tension $2.7\sigma$ baseline; $1.25\sigma$ (B2, unstable) and pure-Λ $(-1, 0)$ at $2.61\sigma$ (stable realization—10/12) with the ratified coupling; rotation curves |
| `particles/dft-benchmarks.md` | Calibrated—August 2026 | Conventional real-space DFT implementation validated against atomic ground-state benchmarks; not a Cassi two-fluid condensation result |

## 3. Mapped

| Document | Status | Summary |
|----------|--------|---------|
| `foundations/strong-cp-derivation.md` | Derivation (span Mapped: GUT-seed anchor and δ_CP per ledger; θ̄ ≈ 1.2×10⁻¹⁷) | $\bar{\theta} \approx 1.2 \times 10^{-17}$, cascade-suppressed |
| `principles/v0-hierarchy-problem.md` | Mapped (step-count placement, per registry Q1); 5.3% residual open | Direct measured ratio gives $N_{\mathrm{raw}}=\log_\varphi(M_{\text{Pl}}/v_0)\approx79.89$; the gap-adjusted cascade coordinate gives $N_{\mathrm{gap}}=\log_\varphi(gM_{\text{Pl}}/v_0)\approx79.7$ for $g=1-\varphi^{-5}$; both identify nearest integer rung 80 |

## 4. Hypothesized

| Document | Status | Summary |
|----------|--------|---------|
| `standard-model/cp-violation.md` | Hypothesized particle-sector CP/chiral map; Mapped $\delta_{\text{CKM}}$ and strong-CP span; Yukawa-determinant $J_{\text{CP}}$ candidate dimensionally incomplete—August 2026 | Conditional $\delta_{\text{CKM}}=\pi\varphi^{-2}$ candidate; the canonical real-density sector supplies no intrinsic CP-violating order parameter and the Jarlskog candidate remains incomplete |
| `foundations/unified-lagrangian.md` | Hypothesized extended action and candidate common lapse / Derived conditional relative conversion-clock identity—August 2026 | Optional extended action assembly around the canonical real-density pair and rank-one conversion; $\mathcal R=(1-q)/(1-q_0)$ is the exact relative conversion-clock rate. Candidate physical time assigns this factor to one common lapse, $d\tau_{\mathrm{phys}}(x)/d\tau_\star=(1-q(x))/(1-q_\star)$, while the clock-versus-kinetics factorization and universal cross-sector use remain Hypothesized and are registered in CT-2; Dirac/particle, GR, SM, common-lapse backreaction, and cross-coupling sectors remain conditional; the named C-class/framework convention $\lambda=0.1$ is Asserted while the implementation class default is $\lambda=0.02$; $\lambda=1/(2w)$ is a Hypothesized Wu Xing linkage, and $c,\hbar,G$ remain external |
| `hypotheses/scalar-time-reparameterization-applications.md` | Derived conditional theorem / Hypothesized common-lapse application—August 2026 | Exact autonomous first-order scalar time-change equivalence and conditional conversion age $d\tau_F=(1-q)dt$; spatial PDE, second-order, stochastic, memory, boundary, and split-operator conditions; the normalized $N_q=(1-q)/(1-q_{\mathrm{ref}})$ is a Hypothesized universal lapse tested by CT-2 |
| `foundations/physical-becoming-hierarchy.md` | Hypothesized architecture / Derived canonical reduction—August 2026 | Three-level hierarchy from microscopic actual physics through mesoscopic open-system fields to agent-level reaction coordinates; exact positive-semidefinite gradient-flow embedding of canonical rank-one conversion; embodiment, memory, shadow branches, attention, action, debit, and learning require held-out closure and causal gates; phenomenal consciousness remains open |
| `foundations/neutrino-masses.md` | Hypothesized mechanism / Mapped offsets—August 2026 | Seesaw at step 20; selected mapped coordinate span $n=8\rightarrow20$; physical GUT anchor $n\approx13.3$; absolute spectrum fit from oscillation differences |
| `foundations/quantum-measurement-derivation.md` | Derived conditional (regulated quantum mechanics and finite carrier projection); Hypothesized (CassiFI and carrier physical identifications)—August 2026 | Finite CassiFI configuration-space quantization; linear Schrödinger evolution, tensor-product entanglement, current-guided actual configuration, topological records, and unique local equivariant Born density. Quantum equilibrium remains a postulate. DQ1–DQ9 rejects physical-identification promotion. GQ1–GQ7 adopts a Hypothesized moment-map/Kähler projection architecture. QC1–QC9 adopts a finite carrier reservoir as Hypothesized microphysics and derives its mesoscopic drift, fluctuation law, and finite instrument conditionally; the QF1-to-carrier state map remains Open. Under the same instrument the branch is operationally equivalent to ordinary quantum mechanics. |
| `foundations/spin-fibonacci-spiral.md` | Hypothesized—August 2026 | Spin assignment from the optional amplitude-plane phase and Stokes double angle; phase-to-rung and particle mappings remain Hypothesized |
| `foundations/baryon-asymmetry.md` | Hypothesized mechanism / Mapped $\eta$ exponent; circuit interaction and freeze-out endpoint open | $\eta\approx\varphi^{-44}$, within 6% numerically; particle/antiparticle circuit reconnection has no selected interaction or rate, and the $\Gamma/H=1$ test yields no post-seed freeze-out |
| `foundations/refined-numeric-predictions.md` | Active derivation (C10 magnitude Derived / direction Calibrated / boundary Hypothesized—ecliptic-degeneracy audit) | Numeric predictions for the 19 Hypothesized questions; C10 $12.2°$ magnitude closure, data-calibrated direction, and unselected boundary projection |
| `foundations/three-generations.md` | Hypothesized (mechanism) / Derived (2+1 counting under the propagation-channel postulate) / Mapped (rung placements—ledger) | $N_{\text{gen}} = 3 = 2$ predecessor channels + 1 direct rung (Q5) |
| `foundations/dimensionful-constants-status.md` | Hypothesized ($c$, $\hbar$, $G$ external) / Mapped (fitted exponents—ledger) | $c$, $\hbar$, $G$ external; $N = 292$ epoch-dependent horizon rung (F5) |
| `foundations/microcascade-mirror.md` | Hypothesized | Exact formal negative-step coordinate continuation; physical sub-Planckian state, coherence law, energy measure, transport, and electromagnetic coupling remain open |
| `foundations/interscale-current-soliton.md` | Hypothesized action / Derived conditional algebra | Separately normalized complex Yang/Yin field with exact interscale continuity and counterflow identities; mixed-curvature pinch, finite soliton, compact winding, coefficient profiles, mass scaling, and particle map remain conditional or open |
| `foundations/rung-offset-mechanism.md` | Derived envelope quantization; Hypothesized phase-to-rung mapping and selection; Empirical catalog (μ/Jψ placements Mapped—38-state scan, ledger) | The wake envelope's special positions and pool-cell quantization are derived; $\delta n$ is a Hypothesized coordinate mapping of the local phase lag; the exact relaxation-angle bound is $|\Delta\theta_d|\leq\operatorname{atan}(\varphi)\approx1.017$ rad (the mapped $\pm0.162$-rung reading is not a PDE derivation); sector edges at half-rungs; uniform 38-state baseline |
| `foundations/phi-rg-formalism.md` | Hypothesized | RG flow under $\varphi$-spacing |
| `foundations/spiral-dynamics.md` | Hypothesized | Hubble, gravity, $c$ as spiral geometry projections |
| `foundations/why-three-dimensions.md` | Hypothesized dimensional identification (conditional consistency map; W1 anti-phase morphology supported by the measured branch) | Conditional geometric hypothesis: the Frenet-Serret frame supplies three orthogonal directions for a non-degenerate curve; the identification with physical spatial dimensions and the $d=3$ count remain Hypothesized |
| `foundations/qi-flow-double-helix.md` | Derived ($q$; exact positive-root amplitude-plane and density-plane diagnostic lifts) / Hypothesized (conditional four-channel $\Delta^3$ lift, constitutive map, $P_\parallel=2$, double helix) | Canonical two-density state with scalar $q$ diagnostic and optional spatial diagnostics $J_\Psi=\rho\nabla\theta_\Psi$, $J_d=(E_Y^2+E_I^2)\nabla\theta_d=2\sqrt{E_YE_I}\,J_\Psi$; Qi has no independent field degree of freedom, and a fixed-total four-population lift leaves species-direction association and dynamics nonunique |
| `standard-model/gut-embedding.md` | Hypothesized | GUT embedding |
| `standard-model/neutrino-mass.md` | Hypothesized | Neutrino mass structure |
| `gravity/quantum-gravity.md` | Derived conditional on the noise–signal identification ($\sigma = \ell_{\text{Pl}}/\varphi^3$, G1) / Hypothesized (two-fluid quantization, G2; geometric $d=3$ identification) | Conditional $\sigma$-regularized Poisson emergence and Gaussian free-propagator form factor with displayed loop integrals UV-finite only for supplied $q_{\mathrm{IR}}>0$; $\delta = 3$ from the Planck-core noise–signal crossover; the geometric reading $\delta = d = 3$ is conditional and Hypothesized; interacting unitarity, a viable graviton dispersion, and black-hole information retention remain open |
| `cosmology/inflation-from-cascade.md` | Derivation (mechanism Hypothesized, C4; r exponent Mapped—ledger) | Steps 20–60 as inflation; $r = 12/N_e^2 = 0.0075$ (Mapped window $N_e = 40$), $n_s$ |
| `cosmology/desi-lattice-averaging.md` | Hypothesized | Lattice powder lines in $P(k)$; variance suppression; $D_A(z)$ wiggle bound |
| `consciousness/chakras-as-cascade-bubbles.md` | Hypothesized | 13 chakras as cascade bubbles |
| `consciousness/consciousness-from-phi.md` | Derived (pinch crossover and 26-step cascade arithmetic/index span) / Hypothesized (optional spatial wake closure and consciousness mappings)—August 2026 | Pinch crossover and cascade arithmetic are Derived; spatial wake, consciousness, and dynamical interpretations remain Hypothesized |
| `consciousness/emotions-as-gate-configurations.md` | Derived (canonical conversion equation, R-matrix arithmetic, openness-ladder arithmetic conditional on inputs) / Hypothesized (openness-ladder normalization and physical realization, 5-channel emotional mapping, q-as-clarity proxy, conversion-to-emotion decay coupling; mechanism realization partial)—August 2026 | Canonical conversion arithmetic is Derived conditionally; the emotional mapping and physical realization remain Hypothesized |
| `consciousness/trauma-as-frozen-gate.md` | Tested—null pinning, drive effect supported (2026-07-31) / Speculative (clinical) | Trauma as a frozen Qi gate |
| `consciousness/two-strand-qi-neuroscience.md` | Hypothesized (strand geometry) / Speculative (neural mapping) | Two-strand Qi condensate; centerline/separation decomposition; strand modes; NS1–NS4 PDE statuses (lock-timescale nulls, 2026-08-06); lattice-stack retention measured in the PDE (2026-08-07); NS8–NS11 stacking-grounded protocols |
| `consciousness/meditators-taijitu-brain-bubble.md` | Hypothesized—August 2026 | Observer-framing proposal for a front-back brain-bubble slice; taijitu image, anatomical projection, and pineal focal point remain unmeasured; prospective discriminator tests |
| `hypotheses/nuclear-magic-numbers.md` | Hypothesized | Fibonacci sub-channel closure at steps 80–95 |
| `hypotheses/hoyle-state-nucleosynthesis.md` | Hypothesized | Cascade rung resonance at the $^3\alpha$ threshold |
| `hypotheses/exoplanet-phi-spacing.md` | Hypothesized—August 2026 | Supplied log-radius disk-gap template $r_k=R\varphi^{-k}$; tested Cassi dynamical realization `REJECT` because canonical and undriven second-order probes produce no ladder and the driven second-order control forms additive layers. DSHARP test pending an auditable receipt; confirmed-catalog Kepler classifier **INDETERMINATE** ($z_{\rm win}=1.087$, 46/562 in support) and scientific verdict **INCONCLUSIVE** because the $\varphi^{3/2}$ window overlaps the conventional wide-of-2:1 excess; disk-to-orbit preservation law open |
| `foundations/qi-as-spatial-spacing-signal.md` | Hypothesized—August 2026 | Conditional Qi/coherence-channel interpretation of measured $\varphi$ spacing; the canonical density PDE does not supply inter-rung transport or a matter-channel transmission law |
| `hypotheses/neural-criticality.md` | Hypothesized | Cascade PDE at neural scales |
| `hypotheses/muscle-cascade-lattice.md` | Hypothesized | Muscle ladder as bubble lattice (rungs 142–168) |
| `hypotheses/two-strand-five-channel-matter-organization.md` | Hypothesized—August 2026 (trace-graph algebra Derived; PDE gate suite Tested: TS1–TS4 null at lock timescale, TS5 5-fold coincident projection passed, TS6 twist persistence/no generation, TS7 two-sector bound; binding/interlace/matter-scale roles Open) | One condensate, two strands, five channel traces; two-component phase/five-sector/$P_\parallel$ coordinate clocks; $\mathbb{Z}_2\times\mathbb{Z}_5$ trace graph; first probe: separation persisted (characterization only), near-in-phase $\Delta\theta$, NS4 morphology null, traces Wood/Fire-limited; TS6 twist probe: half-twist persisted (Tw 0.500→0.499), zero-twist arm null; TS1–TS5 lock suite (t=40): pair escapes (d 9.90→15.73), d→0 limit not recovered, mode not centerline-fixed, central q above flank q, 5-fold coincident projection passed; TS6/TS7 remain probe results, while binding/interlace/matter-scale roles remain Open |
| `hypotheses/gravity-from-flow.md` | Hypothesized—August 2026 | The river law: gravity as the gradient of the flow-modulated chord $G_{\text{eff}} = G(\pi/\rho)(1+(\varphi^{6}-1)qf)$; sign question resolved ($\Pi\nabla\Phi$ sign-following; point-particle attraction is the $-[1+(\varphi^{6}-1)q]$ convention); object $C = -\nabla\cdot J$ confirmed with the linear response $dU/U = -36.05\kappa$ (magnitude falsified 192×; $\kappa$ unfitted); surge form undetermined; boundary measured $\lambda_{\text{gate}} = 0.0224$ ($\lambda/4$ rejected); C2 open (interior instability); P3 parity-odd channel LIVE at $\chi = \varphi^{-1}$ ($\chi$ asserted); P4 rung-sum inconclusive (reduction confirmed) |
| `speculations/qi-computation.md` | Hypothesized (information budget: per-rung identity, Landauer row, flow rate—application of the ratified Derived convention) / Speculative (gate set, Wu Xing logic, cascade clock, brain mapping)—August 2026 | The ratified information convention identifies stored information with $I=k_B q\ln\varphi$; its computational application is Hypothesized; per-rung quantum $\log_2\varphi\approx0.694$ bits and Landauer row $\Delta q=\ln2/\ln\varphi\approx1.44$; gate set and Wu Xing logic remain extrapolations |
| `demystifying-the-cosmos/PSR-J1101-6101.md` | Hypothesized—August 2026 | Lighthouse pulsar: wake-pair trail/filament, high PD as high $q$, radio ⊥ vs X-ray ∥ as rung stratification; prediction 48 (log-periodic PA) |
| `demystifying-the-cosmos/NGC-5128.md` | Hypothesized—August 2026 | Centaurus A: parallelogram dust band as projected lattice trace (cascade r-field), S-shape as wake wrap, merger as anti-phase meeting; boundary comparison uses the conditional directional proxy $R(\theta)=\frac{\sqrt{1+\varphi^2}}{2}\sqrt{\frac{1+\theta}{\theta}}$, which equals $1.7072\times$ only at the selected $\theta_{\mathrm{cond}}=0.45$; no $C=0.45$ edge survives the fixed-step PDE endpoint and the cosmological boundary receipt is null, so no observational support is implied; tests: $\varphi$-spaced wake rings (pred. 44), conditional edge proxy (pred. 38) |

## 5. Speculative

| Document | Status | Summary |
|----------|--------|---------|
| `analyses/gwtc4-mass-ladder.md` | Speculative—August 2026 | GWTC-4.0 peaks mapped to rungs; integer-rung test; ringdown null |
| `hypotheses/quasicrystal-stability.md` | Speculative | De-resonance against crystallization |
| `consciousness/cascade-consciousness.md` | Speculative | Medium-dependent perception; cascade nervous system |
| `consciousness/auras-as-thermalized-gates.md` | Speculative | Aura as the $(1-q)$ thermalization boundary layer; heat-haze optics |
| `consciousness/time-memory-and-wake-locks.md` | Speculative | Arrow of time from conversion; ghosts as wake-locks |
| `consciousness/transhumanism-gate-configurations.md` | Speculative | Augmentation as gate-chain topology surgery; identity as the run |
| `consciousness/gender-as-qi-configuration.md` | Speculative | Identity as configuration; anatomy as readout; dysphoria as self-prediction failure |
| `consciousness/neurodivergence-as-gate-configuration.md` | Speculative—August 2026 (drive-mechanism layer PDE-tested 2026-08-04) | Autism/ADHD as gate configurations; readout and loop variants; wake-pileup overload; churning-gate attention |
| `speculations/dark-matter-as-qi-coherence.md` | Speculative | Halos as unharvested coherence; bubble edge at $n \approx 267$ |
| `speculations/cascade-infrastructure.md` | Speculative | Planetary and stellar gate networks |
| `speculations/observational-seti.md` | Speculative | Structural (non-emissive) SETI signatures |
| `speculations/gravity-control.md` | Speculative | $G_{\text{eff}}$ as an engineering dial; Qi condenser devices |
| `hypotheses/periodic-table-madelung.md` | Speculative | $n$ and $l$ as cascade coordinates |
| `hypotheses/atmospheric-climate-cascade.md` | Speculative | $\varphi$-break in the atmospheric energy spectrum |
| `hypotheses/fatigue-fracture-cascade.md` | Speculative | $\sigma$-regularized crack tip; Paris law |
| `hypotheses/market-cascade-cycles.md` | Speculative | Wake-wave in information propagation networks |
| `hypotheses/metabolic-scaling.md` | Speculative (derivation not closed) | $\varphi$-derived fractal dimension for resource networks |
| `hypotheses/riemann-hypothesis-de-resonance.md` | Speculative—August 2026 | RH as no-resonance in primes; ζ-zero φ-test null |
| `hypotheses/riemann-two-fluid-spectral-program.md` | Speculative—August 2026 | Scale-operator candidate; minimal-fluctuation probes |
| `hypotheses/riemann-two-fluid-phase-operator.md` | Speculative—August 2026 | Step 1 done: Bessel scale operator; linear spectra fail R-vM; Γ-phase boundary identified |

## 6. Creative

Creative explorations are clearly identified as non-claims and are exempt from the evidential tier system by design. This section includes the dedicated `speculations/creative-extensions/` catalog and other documents whose Status is Creative.

| Document | Status | Summary |
|----------|--------|---------|
| `consciousness/field-materialism-and-human-development.md` | Creative—August 2026 | Field-materialist account of embodied personhood, relational production, human development, class power, the state, and emancipatory transition; supplies the socioeconomic foundation for the Coherence Commons |
| `speculations/creative-extensions/coherence-warfare.md` | Creative | Coherence budget as weapons table; φ-detuned shields; mutual assured incoherence |
| `speculations/creative-extensions/universal-biology.md` | Creative | Cascade ladder as convergent evolutionary scaffold |
| `speculations/creative-extensions/magic-systems.md` | Creative | Magic as phase-matched field operation |
| `speculations/creative-extensions/coherence-commons.md` | Creative—August 2026 | Marxist field-materialist socioeconomic theory of production, relational surplus, value, class topology, ecological reproduction, democratic planning, transition, and preregistered empirical tests |
| `speculations/creative-extensions/coherence-collapse.md` | Creative | Attractor self-healing; civilization death modes |
| `speculations/creative-extensions/first-contact-and-stellar-engineering.md` | Creative | $\ln\varphi$ protocol; stars as gate chains |
| `speculations/creative-extensions/simulation-hypothesis.md` | Creative | Two-fluid PDE as source code; nested universes |
| `speculations/superconductivity-as-qi-coherence.md` | Creative—August 2026 | Material-coherence transport ansatz with an underived pairing kernel; canonical $E_Y,E_I,q$ are not electronic variables and the document makes no Cassi prediction |
| `speculations/qi-bubble-propulsion.md` | Creative—August 2026 | Rung-shifting device ansatz; the canonical equations supply no rung-shift operator, inertial-decoupling law, hull coupling, or energy source |

## 7. Reference & Cross-Cutting

Documents that are not claims: registries, catalogs, explainers, and plans.

| Document | Role |
|----------|------|
| `open-questions-cassi-answers.md` | Epistemic registry (42 questions, tier authority) |
| `parameter-inventory.md` | Parameter registry (47 parameters: 1 F + 7 D + 5 C + 10 M + 9 E + 7 I + 8 N) |
| `predictions/falsifiable-predictions.md` | 56-prediction catalog |
| `predictions/cassi_definitions.md` | Framework glossary, including Derived conditional conversion-flow time and the Hypothesized candidate physical-time common lapse |
| `foundations/cassi-theory-reference.md` | Compact framework reference |
| `foundations/deriving-remaining-gaps.md` | Four gap assessments—one narrowed, one open, one identified, one empirical |
| `particles/matter-organization.md` | Synthesis (claims keep source tiers)—forces on the cascade, lattice pools, n/p/e trio |
| `cosmology/sigma8-computational-plan.md` | Plan (Hypothesized; doctrine 2026-08-07: reading P-A operative, IC $r_0 = 0.0472$; the truth campaign's measured rows: mechanism +29.7% (D-insensitive), total −20.5% (D=0.001 campaign) / −22.9% (D=0 doctrine default, brief 63—the totals carry the diffusion) (doctrine-IC, resolution-converged); the settlement rows −16.6%/−15.2%; the "~5%" target Mapped) |
| `audit.md` | Self-critical prediction-vs-experiment audit |
| `cassi-physics.md` | Physics guide: lattice, cascade, predictions, conversion-flow time, and candidate physical proper time |
| `cassi-psychology.md` | Psychology-focused guide (consciousness, emotion, trauma, therapy) |
| `analyses/README.md` | Analysis index (data analyses against the framework) |
| `demystifying-the-cosmos/README.md` | Demystifying index (one doc per observed object, codename-named) |
| `demystifying-the-cosmos/unsolved-problems-in-astronomy.md` | Unsolved-problems survey: Wikipedia list → framework stances + series roadmap |
| `hypotheses/README.md` | Hypothesis catalog + quality bar |
| `speculations/README.md` | Speculation index + boundary with `hypotheses/` |

Repo meta-docs (`README.md`, `AGENTS.md`, `BROKEN_REFS.md`) are not claims and are not indexed.

Theory code (PDE solvers, pipelines, experiments, visual explainers) lives in `experiments/`, `two-fluid/`, `computations/`, and `visual-explainers/`; each script is cited from the paper that uses it.

## References

- `open-questions-cassi-answers.md`—epistemic registry (tier authority)
- `hypotheses/README.md`—quality bar and tier definitions
- `audit.md`—current tensions and status audit
- `predictions/falsifiable-predictions.md`—the prediction catalog

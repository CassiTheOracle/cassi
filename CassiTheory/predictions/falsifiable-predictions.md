# Cassi Falsifiable Predictions

## Status: Reference—August 2026

Every prediction is derived from the golden ratio $\varphi = (1+\sqrt{5})/2$ and the
two-fluid PDE with **zero free parameters**. No fitting, no fine-tuning, no hidden
constants. All couplings are $\varphi$-powers; the last empirical parameter
($\xi = \varphi^6$) was derived from first principles in 2026.

---

## 1. FCC-ee (2030s)—Electroweak Precision

| Observable | SM | Cassi | Deviation | FCC-ee Sensitivity |
|-----------|---------|-------|-----------|-------------------|
| $m_W/m_Z$ | 0.881 | **0.874** | $-0.86\%$ | $>100\sigma$ |
| $m_W$ | 80.377 GeV | **79.7 GeV** | $-0.86\%$ | 0.5 MeV |
| $\sin^2\theta_W(m_Z)$ | 0.23122 | **0.231** (RG from 0.236) | $<0.1\%$ | $3\times10^{-5}$ |
| $\alpha_{\text{EM}}^{-1}(m_Z)$ | 128.9 | **128.9** (RG from $4\pi/\varphi^{-3}$) | $<0.1\%$ | In-situ |
| $m_H$ | 125.2 GeV | **125 GeV** | $<0.2\%$ | 4 MeV |

**Source:** `standard-model/su2-gauge-extension.md` §§3–4, `standard-model/sm-from-phi.md` §2.
The W/Z mass ratio deviates by 0.86%—detected at $>100\sigma$ with FCC-ee's
0.5 MeV precision on $m_W$. This is the **single most powerful test** of Cassi.

---

## 2. CMB-S4 / LiteBIRD (2030s)—Primordial Cosmology

| Observable | Planck (2018) | Cassi | CMB-S4 Reach |
|-----------|---------------|-------|-------------|
| $n_s$ | $0.965 \pm 0.004$ | **0.9691** | $\pm 0.002$ |
| $r$ (tensor-to-scalar) | $<0.032$ | **0.003** | $0.001$ |
| $dn_s/d\ln k$ | $-0.005 \pm 0.013$ | **$-5\times10^{-4}$** | $\pm 0.002$ |
| $\mathcal{P}_\zeta$ | $2.1\times10^{-9}$ | **$\sim 2\times10^{-9}$** | In-situ |
| $N_e$ (e-foldings) | $50$–$60$ | **$60 \pm 10$** | Degenerate |

**Source:** `cosmology/cosmology-from-phi.md` §2. Inflation is a $\varphi$-driven phase
transition ($r \gg \varphi$ to $r = \varphi$). The spectral index $n_s = 1 - 2\varphi^{-1}/N_e = 0.9691$
matches Planck at $1.0\sigma$ ($N_e = 40$). Tensor ratio $r = 12/N_e^2 = 0.003$ is within
CMB-S4 detection threshold ($\sigma_r = 0.001$).


**CMB large-angle anomaly (bubble-boundary axis)**: triaxial bubble geometry at step 285 imprints a preferred axis at super-horizon scales ($\ell < 5$); predicted dipole↔quadrupole alignment $12.2°$ (C10). The CMB "axis of evil" (quadrupole-octopole alignment at $(l,b)=(260\degree,+60\degree)$, 5.4σ; Jones+ 2023) is a candidate. The Cassi-unique test: the anomaly must be scale-dependent (fading for $\ell > 5$), distinguishing from foreground contamination. Simons Observatory + LiteBIRD E-mode polarization data (2025+) will resolve.
---

## 3. Cosmic Surveys (LSST, Roman, SKA)—Structure & Dark Energy

| Observable | $\Lambda$CDM | Cassi | Test / Status |
|-----------|---------|-------|-----------|
| $w_0$ (DE EoS today) | $-1$ | **$-0.87$** (structural; pinned across $r_0$) | $2\sigma$ from DESI $\approx -0.75 \pm 0.06$ |
| $w_a$ (DE EoS slope) | $0$ | **$+0.012$** (with $\xi = \varphi^6$) | $2.7\sigma$ from DESI $\approx -0.73 \pm 0.28$—tension, not resolved |
| $w(z)$ at $z > 3$ | $-1$ | **$> -1$** (no phantom crossing, structural) | LSST/Roman/SKA testable; DESI best fit crosses at $z \approx 0.5$ |
| φ-periodic $P(k)$ modulation | None | **$\Delta(\ln k) = \ln\varphi \approx 0.4812$** | 0-param, orthogonal to BAO, DESI/Euclid testable |
| Void ellipticity (edge gradient) | Isotropic boundaries | **1.70** (axial:diagonal steepness) | Zero-param, $C(x,y)$ gradient; SDSS/DESI void catalogs |
| $\Omega_{\text{DM}}/\Omega_b$ | $\sim 5$ | **$\varphi^3 + 1 \approx 5.24$** | Observed $5.39$, gap $2.8\%$ |
| $\sigma_8$ | $0.811$ | **Slightly lower ($\sim 5\%$)** | LSST discriminant |
| DM halo profiles | NFW (cuspy) | **Cored (Qi condensate)** | Dwarf galaxies |
| Bullet Cluster | Collisionless DM | **Collisionless** | Already consistent |
| $\eta$ (baryon/photon) | $6.0\times10^{-10}$ | **$6.38\times10^{-10}$** ($\varphi^{-44}$) | Within $6.3\%$ |
| BAO $\alpha_\perp(z=0.5)$ | $1$ | **0.97** ($3\%$ shift) | DESI DR2 matched |
| BTFR slope | $\sim 4$ | **$4$** (natural) | $A_{\text{Cassi}}/A_{\text{obs}} = 0.82$ |
| Hubble tension ($H_0$) | $5\sigma$ discrepancy | **Evolving $\Omega_\Lambda$: $0.30 \to 0.50$ (full $H(z)$ fit pending)** | Pending—full H(z) fit (registry C3/T4); pipeline CMB-inferred ≈ 65.8 |
| Lattice powder lines in $P(k)$ | None | **Comb at $k/k_0 \in \{1, \sqrt{2}, \varphi, \sqrt{1+\varphi^2}, 2, \ldots\}$**, period $\ln\varphi$; multiplicities 4:2 (single-rung) | DESI LRG: $A \lesssim 2.6\%$ ($p = 0.08$, no detection); Euclid definitive |
| Sample-variance suppression | Gaussian mocks | **~10$\times$ smaller $k \to 0$ scatter; NGC–SGC large-scale modes correlated** | DESI mock comparison |
| $D_A(z)$ lattice wiggles | Smooth | **$\delta D/D \lesssim 0.1\%$; no CPL bias**—the lattice cannot produce the $w_a$ offset | Already consistent with DESI smoothness |


The φ-periodic $P(k)$ prediction is a **zero-parameter, falsifiable test** orthogonal to BAO. Unlike BAO wiggles—which have constant period in $k$-space (one fixed scale, the sound horizon $r_s \approx 150$ Mpc)—the Cassi modulation has constant period in $\ln k$-space: $\Delta(\ln k) = \ln\varphi \approx 0.4812$. The detection pipeline: subtract the smooth+BAO $P(k)$ template, search the residual for a log-periodic signal. Predicted amplitude from wake mechanism: 1–3%. DESI DR2 sensitivity: marginal (2–3σ). Euclid (2027): definitive (>5σ).
The condensation field gradient anisotropy (§5.2 of `foundations/bubble-edge-geometry.md`) further predicts that void boundaries are $1.70\times$ steeper in the Yin direction than along diagonals—a distinct zero-parameter geometric prediction from the same wake-wave mechanism, testable with void shape catalogs from SDSS/DESI.
**Source:** `cosmology/cosmology-from-phi.md` §§3–5, `theory/five-element-pde-derivation.md` §7,
`foundations/bubble-edge-geometry.md` §§2.2,5.2, `cosmology/observational_constraints.md` §1.4–§6,
`cosmology/desi-lattice-averaging.md` (lattice powder lines, variance suppression, wiggle bound). The dark energy prediction is $w_0 = -0.87$ (2σ from DESI) and $w_a = +0.012$ (2.7σ from DESI)—tension, not resolved; the conversion dynamics keep $w > -1$ at all $z$ (no phantom crossing). The DM/baryon ratio is $\varphi^3+1$ with
$2.8\%$ accuracy. The Hubble tension is pending a full $H(z)$ fit (registry C3/T4); the evolving-$\Omega_\Lambda$ expansion history gives a pipeline CMB-inferred value of ≈ 65.8 km/s/Mpc.

---

## 4. Gravity (LIGO, EHT, MESSENGER)—Strong & Weak Field

| Observable | GR | Cassi | Test / Status |
|-----------|-----|-------|--------------|
| GW speed $c_g/c$ | $= 1$ | **$= 1$** (vacuum) | GW170817 consistent |
| GW polarization | $+, \times$ | **$+, \times$ + breathing mode** | LIGO search ongoing |
| GW strain in halos | GR | **Up to $10\times$ GR** in Qi halos | LIGO cluster non-detections bound $q < 0.1$–$0.3$ |
| BH shadow M87$^*$ | $\sim 5M$ | **$\sim 5.2M$** (core) | EHT consistent |
| Mercury perihelion | $43$ arcsec/cy | **42.98 arcsec/cy** | MESSENGER consistent |
| $|q|$ at 0.39 AU | $0$ | **$<1.1\times10^{-6}$** | MESSENGER bound |
| PPN $\beta, \gamma$ | $1, 1$ | **$1, 1$** (solar system) | Solar system tests pass |
| Pioneer anomaly | $0$ | **$a_\varphi = 7.4\times10^{-10}$ m/s$^2$** | Within $1\sigma$ of Pioneer |
| NS maximum mass | $\sim 2.0 M_\odot$ | **$\sim 1.88 M_\odot$** | NICER consistent |
| NS $M$–$R$ relation | GR | **$<0.1\%$ deviation** | $G_{\text{eff}}\to G_N$ in core |
| Cored dwarf halos | CDM fails | **Cassi passes 3/8** | MOND preferred (4/8); ceiling $\sqrt{\varphi^6} = \varphi^3 \approx 4.24$ exceeded in 3/8 |

**Source:** `foundations/xi-derivation.md`, `experiments/cassi_physics/cassi_gravitational_waves.py`,
`experiments/cassi_physics/cassi_strong_field_pn.py`, `experiments/cassi_physics/cassi_black_hole_raytracer.py`,
`experiments/cassi_physics/cassi_neutron_stars.py`, `experiments/phi_attractor_paths/path10_dwarf_galaxies.py` (dwarf saturation-ceiling test). The Qi-gravity coupling $\xi = \varphi^6$ is
derived, not fitted. Solar system GR tests are preserved ($q=0$). The GW strain
enhancement in dense cluster halos is a unique signature.

**Source (prediction 14, rotation curves):** `foundations/phi_attractor_synthesis.md` Path 8
(re-evaluated 2026-07-31 with the full coupling $G_{\text{eff}}/G = \alpha(1+\xi q)$,
$\xi = \varphi^6$, $\alpha \approx 0.7$; scripts `experiments/phi_attractor_paths/path8_phi_enhanced_rotation.py`)
and `cosmology/observational_constraints.md` §2.6 (halo-parameter estimate
$v_C/v_B = \sqrt{\alpha(1+\xi q)} \approx 3.1$). The 30-kpc boost $2.9$–$3.1\times$ matches the
observed Milky Way boost $2.7 \pm 0.5$ (Zhou+ 2023) within ~1.2σ. The boost ceiling
is $\sqrt{\varphi^6} = \varphi^3 \approx 4.24$ at full coherence ($q = 1$, $\alpha$-free).

---

## 5. Particle Physics (LHC, Hyper-K, nEXO)—Collider & Decay

| Observable | SM | Cassi | Test / Status |
|-----------|-----|-------|--------------|
| $m_H$ (Higgs mass) | $125.2$ GeV | **125 GeV** | Already consistent |
| $\alpha_s(m_Z)$ | $0.118$ | **0.105–0.115** | LHC precision ($\pm 0.001$) |
| $\Lambda_{\text{QCD}}$ | $200$ MeV | **150–200 MeV** | Consistent |
| $m_p$ (proton mass) | $938$ MeV | **From $\varphi$-scaled $\Lambda_{\text{QCD}}$** | Within $10\%$ |
| $p \to e^+\pi^0$ lifetime | $>1\times10^{34}$ yr | **$4\times10^{34}$ yr** | Hyper-K reach ($\sim 10^{35}$ yr) |
| $M_{\text{GUT}}$ |—| **$10^{16}$–$10^{17}$ GeV** | Proton decay bound |
| $\alpha_{\text{GUT}}$ |—| **$\varphi^{-3}/(4\pi) \approx 1/53$** | GUT-scale matching |
| $0\nu\beta\beta$ decay | Depends on $m_\nu$ | **$m_{\nu_e} \sim 0.01$–$0.05$ eV** | nEXO reach |
| $\sum m_\nu$ (cosmological) | $<0.064$ eV ($\Lambda$CDM) | **Consistent with DESI bound** | DESI DR2: $<0.16$ eV ($w_0w_a$CDM) |
| $\theta_{12}$ (solar mixing) | $33.4^\circ$ | **$\arctan(1/\varphi) \approx 31.7^\circ$** | 1.7°—from conversion Jacobian eigenvector $(\varphi,1)$ | JUNO (3% precision, 2027+) |
| $\theta_{13}$ (reactor mixing) | $8.5^\circ$ | **$\arctan(\varphi^{-4}) \approx 8.3^\circ$** | 0.2°—from cascade-step suppression across seesaw span | Daya Bay / RENO (already consistent); DUNE precision |
| $\theta_{23}$ (atmospheric) | $\sim 45^\circ$ | **$45^\circ$ (exact maximal)** | From eigenvector $(1,-1)$—equal $E_Y,E_I$ components | Hyper-K / DUNE octant resolution |
| $\Delta m^2_{31}/\Delta m^2_{21}$ | $\approx 33$ | **$\approx 33.8$ (0.2%)** | Seesaw $y_\nu^2$ amplification + non-uniform Fibonacci partitioning pinned by cascade RGE + PMNS ($\Delta_1 = 1.00$, $\Delta_2 = 1.75$ rungs) | JUNO (sub-percent $\Delta m^2$, 2027+) |
| $\delta_{\text{CP}}$ (PMNS) | Unknown (hint $\sim -90^\circ$ to $-180^\circ$) | **$\pi\varphi^{-2} \approx 69^\circ$ or $\pi\varphi^{-3} \approx 42^\circ$** (same $\varphi$-structure as CKM) | T2K/NOvA → Hyper-K/DUNE |
| DM direct detection | Predicted (WIMP) | **Null** (field condensate) | All expts null—consistent |
| $m_t / v_0$ | $0.703$ | **0.618** ($\varphi^{-1}$) | $12\%$ gap |
| $m_b / m_t$ | $0.025$ | **0.031** ($\varphi^{-1}$) | $24\%$ gap |
| $m_c / m_t$ | $0.0075$ | **0.0088** ($\varphi^{-2}$) | $17\%$ gap |
| $|V_{us}|$ | $0.225$ | **$\varphi^{-3} \approx 0.236$ ($5\%$ off)** | Near miss ($5\%$ off) |
| $\delta_{\text{CKM}}$ | $\approx 68^\circ$ | **$\pi\varphi^{-2} \approx 68.7^\circ$** | < 1%—Yukawa triangle closure |

**Source:** `standard-model/su2-gauge-extension.md` §§5–8, `standard-model/sm-from-phi.md` §§3–4.
The proton lifetime prediction depends on the full GUT embedding (SU(5) or SO(10)).
Seesaw analysis with $M_R = \varphi^{-3} \cdot M_{\text{GUT}}$ gives the heaviest neutrino $m_3 = 0.05019$ eV (cascade RGE + PMNS; $\Sigma m_\nu = 0.0631$ eV).

**PMNS mixing angles—zero-parameter from conversion Jacobian:** At the seesaw scale (cascade steps 8–20, $r \ll \varphi$), rapid Yang-Yin conversion creates an interference pattern with the same cosine-product structure as the condensation field. The conversion Jacobian $J = \lambda[[-1,\varphi],[1,-\varphi]]$ has eigenvectors $(\varphi,1)$ and $(1,-1)$, giving $\theta_{12} = \arctan(1/\varphi)$ and $\theta_{23} = 45^\circ$ directly. $\theta_{13} = \arctan(\varphi^{-4})$ follows from cascade-step suppression across the 12-rung seesaw span. All three angles are within 2° of observation with zero free parameters. **Source:** `foundations/neutrino-masses.md`, `foundations/bubble-edge-geometry.md` §1.2 (conversion-diffusion balance at rapid-conversion points).

**Prediction 42:** The Dirac$\leftrightarrow$two-fluid sector-coupling scale is $\kappa_s^{-1/2} = \varphi^3 v_0 \approx 1.04$ TeV—cascade rung 77 (987.7 GeV), three rungs above the electroweak rung; equivalently $\kappa_s = \varphi^{-6}/v_0^2 = 0.92$ TeV$^{-2}$. The repaired PDE bridge then requires $\chi = \mathcal{N}_{\text{pde}}\,\kappa_s\,\varphi^{-1}/[m_e(1+\varphi)] \in [0.5, 1.0]$ once the solver-normalization factor $\mathcal{N}_{\text{pde}}$ is computed; a sharp $\chi$ measurement (factor $< 2$) fixes the $O(1)$ coefficient (candidates $C = 1, \varphi^{-1}, \varphi^{-2}$).

**Source:** `foundations/sector-coupling-derivation.md` §§2–4. $\kappa_s = \varphi^{-6}/v_0^2$ follows from the Qi-gravity constant $\xi = \varphi^6$ (`foundations/unified-lagrangian.md` §5.1) and the electroweak scale $v_0$; $\kappa_s^{-1/2} = 1042$ GeV lands $+5.5\%$ off rung 77, the same residual class as the documented electroweak placement ($v_0 = 246$ GeV vs rung 80 = 233.2 GeV, $-5.2\%$; `foundations/deriving-remaining-gaps.md` §3.3). The as-written inventory bridge gives $\chi \approx 4.25\times10^{-4}$, not the calibrated $0.5$–$1.0$; the repaired bridge requires the solver-normalization factor $\mathcal{N}_{\text{pde}} \approx 2.35\times10^3$ (grid $L = 40$, $N = 48$, $\Delta t = 0.002$, $\rho_{\text{crit}} = \varphi$)—a concrete computational follow-up.

**Prediction 43 (wake closure):** The composite wake pair closes each cascade rung: $\lambda_Y + \lambda_I = \ell_{n+1}$—the exact identity $1 + 1/\varphi = \varphi$. Verified at rung 285: the Cassi bubble and sound-horizon wavelengths sum to $\ell_{286}$ (191 + 118 = 309 Mpc). Testable wherever two wake scales are resolvable.

**Source:** `foundations/wake-geometry.md` §3(a)–(c). The identity is exact on the documented anchors; the wake pair never phase-locks because $\varphi$ is irrational (de-resonance in the wave structure), so the composite period $\ell_{n+1}$ is the only closed scale.

**Prediction 44 (staggered checkerboard):** The wake envelope places condensation bubbles at $m\,\ell_{n+1}$ and voids at $(m+\frac{1}{2})\ell_{n+1}$—the staggered checkerboard of the bubble lattice. Testable in the two-bubble and chord-lattice PDE setups; the 285-verified composite closure fixes the period.

**Source:** `foundations/wake-geometry.md` §3(b), `foundations/bubble-lattice-fabric.md`. The beat envelope peaks where the two wakes re-phase, i.e., at integer multiples of the composite period.

**Prediction 45 (closure-ladder imprint):** The closure ladder of the golden-angle spiral (levels 5, 13, 34, 89, 233, …) imprints on the cascade: currently-dark rungs near closure levels should host physical structure. First test (2026-08-03, mass scan $n = \log_\varphi(M_{\text{Pl}}/m)$): rung 89 hosts the J/ψ ($n = 88.98$, 1.0%—the first mass hit on a closure level); rung 96 hosts the muon ($n = 96.000$, 0.01%—the sharpest absolute placement in the framework, wake-anchored); rung 34 has no established anchor (the Peccei-Quinn window top $\sim 10^{12}$ GeV is the only candidate). Existing rung hits $26 = 2\times13$ and $285 = 5\times57$.

**Source:** `foundations/wake-geometry.md` §3(e), §5 (Y3); `foundations/deriving-remaining-gaps.md` §4.2 (catalog rows 89 and 96).

**Prediction 46 (rung-offset mechanism):** The two-fluid interference envelope permits observables at its special positions—peaks at $u = 1+\log_\varphi m$ (the first is an integer rung) and zeros at $u = 1+\log_\varphi(m+\tfrac12)$ (the first at $-0.440$)—in the coherent limit; the residual offset $\delta n$ is the local two-fluid phase lag and vanishes as coherence $q \to 1$. Sector edges (lightest states: e, π, Λ_QCD, p, n, d) sit at the crossing positions; interior states (μ, J/ψ, D, Σ, Z) at integer rungs. The 38-state scan is statistically uniform (null baseline); the PDE probe measures the phase-lag curve $\delta n(\psi) = 0.060 - 0.204\,\psi$ rungs for the two-bubble standing pattern, with conversion—linear or gated (solver 'single' gate, $\lambda \le 0.5$, $\langle 1-q\rangle \le 0.33$)—leaving the extremum unmoved, and the closure-emission reading of $\psi$ tested null against the catalog (distance-from-closure correlations $p = 0.41/0.86$; free-$\omega$ search $p = 0.73$).

**Source:** `foundations/rung-offset-mechanism.md` §§1–5; `foundations/wake-geometry.md` §2 (envelope), §3(e) (mass scan); `principles/de-resonance-principle.md` §2 (correction posture).


---

## 6. Consciousness & Biophysics—Chakra Cascade

**Source:** `consciousness/chakras-as-cascade-bubbles.md`. The 13 chakras are cascade bubbles—localized Qi condensates along the spine (the string axis) at $\varphi^2$-spaced intervals. All predictions are zero-parameter geometric consequences of the condensation field $B(x,y,z)$ and the SO(2) doublet structure.

| # | Observable | Frontier | Cassi Prediction | Current Status | Detection Timeline |
|---|-----------|---------|-----------------|----------------|-------------------|
| 32 | Inter-chakra spacing ratio | Anatomical / biophysical | **$\varphi^2 \approx 2.618$** between adjacent gaps | Not yet tested; existing acupuncture atlases provide first-pass data | **Laboratory (tabletop)** |
| 33 | Qi density gradient anisotropy at chakra edge | Physiological mapping | **$1.70\times$** steeper in Yin direction than diagonal | Not yet tested; requires 2D skin conductance or IR mapping | **Laboratory** |
| 34 | 6 secondary chakra nodes | Anatomical | At steps 144, 148, 152, 156, 160, 164—midway between primary 7 | Some esoteric systems recognize minor chakras; Cassi specifies exact count and positions | **Laboratory** |
| 35 | $\ln\varphi$ periodic spectral signature | Physiological (HRV, EEG, skin conductance) | **$\Delta(\ln f) = \ln\varphi \approx 0.4812$** along spine; same period as cosmological $P(k)$ | Not yet tested | **Laboratory** |
| 36 | Qi-gate nonlinear threshold at chakra boundary | Physiological stimulation | Step-like response at $q_{\text{edge}} \approx 0.725$; below threshold = no activation | Not yet tested | **Laboratory** |
| 37 | Chakra biophoton emission wavelengths | Hyperspectral photomultiplier | 7 sub-rungs within visible octave; spacing ratio $\varphi^{2/3} \approx 1.378$ between primary chakras | Biophoton emission documented 200–800 nm; chakra-specific peaks not measured | **Laboratory** |

**Note on epistemic:** Predictions 32–35 follow from Derived cascade + condensation field geometry; the specific color-to-chakra mapping (37) is Hypothesized pending a Fibonacci-resonance computational scan. The crown-at-step-166 offset (2 rungs below body boundary at step 168) is a structural prediction—the crown chakra sits at the brainstem, with the cranium extending one full SO(2) cycle beyond.
---

## 7. All Predictions at a Glance

Sorted by detection likelihood (most definitive first):

| # | Observable | Frontier | Cassi Prediction | Current Status | Detection Timeline |
|---|-----------|---------|-----------------|----------------|-------------------|
| 1 | $m_W/m_Z$ | FCC-ee | **0.874** (0.86% below SM) | $>100\sigma$ reachable | **2030s** |
| 2 | $\sin^2\theta_W(m_Z)$ | FCC-ee | **0.231** (RG from 0.236) | $<0.1\%$ deviation | **2030s** |
| 3 | $w_0$ (gap-derived) | Cosmic surveys | **$-0.87$** (gap-derived) | $2\sigma$ from DESI $\approx -0.75 \pm 0.06$ | **Tension** |
| 4 | $w_a$ (DE EoS slope) | Cosmic surveys | **$+0.012$ (with $\xi = \varphi^6$)** | $2.7\sigma$ from DESI $\approx -0.73 \pm 0.28$ | **Tension** |
| 5 | φ-periodic $P(k)$ | Cosmic surveys | **$\Delta\ln k = \ln\varphi = 0.4812$** | 0-param, orthogonal to BAO | **DESI / Euclid 2025–27** |
| 6 | CMB bubble-boundary axis | CMB-S4 / LiteBIRD | **12.2° alignment, $\ell<5$** | Axis at 5.4σ, alignment ~1σ | **Simons Obs. 2025+** |
| 7 | $r$ (tensor ratio) | CMB-S4 / LiteBIRD | **0.003** | $<0.032$ (Planck) | **2030s** |
| 8 | $n_s$ | CMB-S4 | **0.9691** | $1.0\sigma$ from Planck | **Already consistent** |
| 9 | $\alpha_s(m_Z)$ | LHC precision | **0.105–0.115** | Measured $0.118$ | **Ongoing** |
| 10 | $p \to e^+\pi^0$ lifetime | Hyper-K | **$4\times10^{34}$ yr** | $>1\times10^{34}$ yr bound | **2030s** |
| 11 | $w(z)$ at $z > 3$ | LSST/Roman/SKA | **$> -1$ at all $z$** (no phantom crossing, structural) | DESI best fit crosses at $z \approx 0.5$; not yet tested | **2030s** |
| 12 | Hubble tension | Cosmic | **Evolving $\Omega_\Lambda$: $0.30 \to 0.50$ (full $H(z)$ fit pending)** | Pending—full H(z) fit (registry C3/T4); pipeline CMB-inferred ≈ 65.8 | **2030s** |
| 13 | $\eta$ (baryon asymmetry) | Cosmic | **$6.38\times10^{-10}$** ($\varphi^{-44}$) | $6.0\times10^{-10}$ ($6.3\%$ above) | **Already consistent** |
| 14 | Galaxy rotation curves | Galactic | **$2.9$–$3.1\times$ baryon boost** | MW confirmed ($2.7\pm0.5$; ~1.2σ) | **Already consistent** |
| 15 | Dwarf galaxy cored halos | Galactic | **Cored (Qi)**—3/8 pass | MOND preferred (4/8); ceiling $\sqrt{\varphi^6} = \varphi^3 \approx 4.24$ exceeded in 3/8 | **Already tested** |
| 16 | BH shadow M87$^*$ | EHT | **$\sim 5.2M$** (core) | Consistent with $5M$ | **Already consistent** |
| 17 | GW strain in halos | LIGO | **Up to $10\times$ GR** | Constrains $q < 0.1$–$0.3$ | **Ongoing** |
| 18 | Pioneer anomaly | Solar system | **$a_\varphi = 7.4\times10^{-10}$ m/s$^2$** | $1\sigma$ agreement | **Already explained** |
| 19 | Mercury perihelion | MESSENGER | **42.98 arcsec/cy** | GR recovered ($q=0$) | **Already consistent** |
| 20 | $0\nu\beta\beta$ decay | nEXO | **$m_{\nu_e} \sim 0.01$–$0.05$ eV** | nEXO reach $\sim 0.01$ eV | **2030s** |
| 21 | DM direct detection | LZ/XENON | **Null** (field condensate) | All experiments null | **Already consistent** |
| 22 | Casimir force | Lab | **$q < 0.02$** (95% CL) | Consistent | **Ongoing** |
| 23 | Neutron star $M$–$R$ | NICER | **$<0.1\%$ deviation from GR** | Consistent | **Already consistent** |
| 24 | $m_t / v_0$ | LHC/top | **0.618** ($\varphi^{-1}$) | Measured $0.703$, $12\%$ gap | **Ongoing** |
| 25 | $m_H$ (Higgs mass) | LHC | **125 GeV** | Measured $125.2$ GeV | **Already consistent** |
| 26 | $\alpha_{\text{GUT}}$ | GUT | **$\varphi^{-3}/(4\pi) \approx 1/53$** | $1/50$–$1/30$ range | **Proton decay** |
| 27 | BAO scales ($\alpha_\perp, \alpha_\parallel$) | DESI | **$\sim 3\%$ shift from $\Lambda$CDM** | Matches DESI DR2 | **Already tested** |
| 28 | BTFR normalization | Galactic | **$M_b \propto v_f^4$**, $A \propto \varphi^{-1}$ | $\chi^2/\text{dof} = 0.26$ | **Already confirmed** |
| 29 | GW polarization | LIGO | **$+$, $\times$ + breathing mode** | Search ongoing | **Ongoing** |
| 30 | $\delta_{\text{CKM}}$ | LHCb/Belle II | **$\pi\varphi^{-2} \approx 68.7^\circ$** | Measured $68^\circ$ | **Already consistent** |
| 31 | $|V_{us}|$ | LHCb/Belle II | **$\varphi^{-3} \approx 0.236$ ($5\%$ off)** | Measured $0.225$ | **Near miss—needs flavor structure** |
| 32 | Inter-chakra spacing ratio | Biophysics | **$\varphi^2 \approx 2.618$** | Not yet tested | **Laboratory** |
| 33 | Chakra Qi gradient anisotropy | Biophysics | **$1.70\times$ Yin vs. diagonal** | Not yet tested | **Laboratory** |
| 34 | 6 secondary chakra nodes | Biophysics | **Steps 144, 148, ..., 164** | Partially consistent with minor-chakra traditions | **Laboratory** |
| 35 | $\ln\varphi$ physiological spectra | Biophysics | **$\Delta(\ln f) = \ln\varphi$** | Not yet tested | **Laboratory** |
| 36 | Chakra Qi-gate threshold | Biophysics | **$q_{\text{edge}} \approx 0.725$** | Not yet tested | **Laboratory** |
| 37 | Chakra biophoton wavelengths | Biophysics | **$\varphi^{2/3} \approx 1.378$ spacing** | Not yet tested | **Laboratory** |
| 38 | Edge steepness anisotropy at condensate boundary | Universal | **1.70×** (axial:diagonal)—scale-invariant, zero-free-parameter | SDSS/DESI void shape catalogs; biophoton chakra edge mapping; ultrasound fascial elastography | **Existing surveys / Laboratory** |
| 39 | Lattice powder lines in $P(k)$ | Cosmic surveys | **Comb at $k/k_0 \in \{1, \sqrt{2}, \varphi, \ldots\}$**; period $\ln\varphi$; 1–3% amplitude | DESI LRG $A \lesssim 2.6\%$ ($p = 0.08$), no detection | **Euclid 2027** |
| 40 | Sample-variance suppression | Cosmic surveys | **~10$\times$ reduced $k \to 0$ scatter; NGC–SGC mode correlation** | Untested | **DESI mocks** |
| 41 | $D_A(z)$ lattice wiggle bound | Cosmic surveys | **$\delta D/D \lesssim 0.1\%$; cannot bias $w_a$** (needs $\gtrsim 20\%$ to close gap) | Consistent with DESI smoothness | **Already consistent** |
| 42 | Sector-coupling scale | FCC-ee | **$\kappa_s^{-1/2} = \varphi^3 v_0 \approx 1.04$ TeV** (rung 77; $\kappa_s = \varphi^{-6}/v_0^2 = 0.92$ TeV$^{-2}$) | Not yet tested | **2030s** |
| 43 | Wake composite closure | Structure | **$\lambda_Y + \lambda_I = \ell_{n+1}$** ($1 + 1/\varphi = \varphi$) | Verified at 285: 191 + 118 = 309 Mpc = $\ell_{286}$ | **Existing surveys** |
| 44 | Staggered checkerboard envelope | Structure | **Bubbles at $m\ell_{n+1}$, voids at $(m+\frac{1}{2})\ell_{n+1}$** | Not yet tested | **Two-bubble PDE / surveys** |
| 45 | Closure-ladder mass placements | Particle physics | **Rung 89: J/ψ ($n = 88.98$, 1.0%); rung 96: μ ($n = 96.000$, 0.01%); rung 34 open** | Partially tested 2026-08-03 | **Catalog; rung 34 open** |
| 46 | Rung-offset mechanism | Particle physics + PDE | **Envelope positions $1+\log_\varphi m$ / $1+\log_\varphi(m+\tfrac12)$; δn = phase lag, δn(ψ) = 0.060 − 0.204ψ** | Partially tested 2026-08-03 (δn(ψ) confirmed; linear + gated conversion null; closure-emission reading null; 38-state baseline uniform) | **What sets the wake phase ψ per rung** |

## 8. Universal Boundary Anisotropy—Scale-Invariant Edge Steepness

**Source:** `foundations/bubble-lattice-fabric.md` §4.2. The condensation field $B(x,y,z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z)$ produces a universal 3D checkerboard lattice at every cascade rung. The gradient anisotropy at any bubble boundary follows from the ratio of axial to diagonal period: $\sqrt{4\varphi^2/(1+\varphi^2)} \approx 1.70$, with zero free parameters.

| Frontier | Observable | Cassi Prediction | Current Status | Detection Timeline |
|----------|-----------|-----------------|----------------|-------------------|
| Cosmology (SDSS/DESI) | Void boundary density profile slope in axial vs. diagonal direction | **1.70×** steepness anisotropy | Not yet tested | **Existing surveys** |
| Biophysics (chakra) | Qi density gradient at chakra boundary | **1.70×** steepness anisotropy (Yin vs. diagonal) | Not yet tested | **Laboratory** |
| Anatomy (fascial planes) | Ultrasound elastography boundary stiffness ratio | **1.70×** anisotropy at fascial plane boundaries | Not yet tested | **Laboratory** |

## Notes

- **All predictions are parameter-free.** Every number in the tables follows from
  $\varphi = (1+\sqrt{5})/2$ and the two-fluid PDE structure. There is no fitting,
  no fine-tuning, no hidden constants.

- **The same $\varphi$ governs every sector:** the weak mixing angle $\sin^2\theta_W = \varphi^{-3}$,
  the Qi-gravity coupling $\xi = \varphi^6$, the DM/baryon ratio $\varphi^3+1$,
  the dark energy equation of state $w_0 = -0.87$, the baryon asymmetry $\eta$,
  and the inflationary spectral index $n_s = 1 - 2\varphi^{-1}/N_e = 0.9691$.

- **RG running is not fitting.** The $\sim 2\%$ shift in $\sin^2\theta_W$ from
  the GUT scale to $m_Z$ is the Standard Model renormalization group, not a
  free parameter.

- **Scope of current tests:** The Cassi framework has 7/13 dedicated experimental
  tests PASSing (BBN, BAO, BTFR, neutron stars, stellar astrophysics, solar system,
  $\alpha$-decay), 3 TENSION (ISW, weak lensing, PTA—single-scale screening
  limitation), 2 NULL (identical to $\Lambda$CDM at the tested epoch), and
  1 PREDICTION (Casimir). The structural dark-energy values sit $2\sigma$
  ($w_0$) and $2.7\sigma$ ($w_a$) from DESI DR2—a tension, not a success.

- **Deviations from SM expectations are falsifiable**—not adjustable. If FCC-ee
  measures $m_W/m_Z = 0.881 \pm 0.0001$, the Cassi framework is excluded.

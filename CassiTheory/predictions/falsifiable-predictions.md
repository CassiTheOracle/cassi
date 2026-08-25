# Cassi Falsifiable Predictions

## Status: Reference—August 2026

The catalog separates parameter-free structural predictions from predictions that depend on optional extensions, declared inputs, Mapped placements, or Calibrated normalizations. The parameter-free structural subset is derived from the golden ratio $\varphi = (1+\sqrt{5})/2$ and the canonical two-fluid PDE under its stated assumptions. Framework couplings are often expressed as $\varphi$-powers, while observationally anchored quantities carry the Calibrated or Mapped flag with a Fit-Status Ledger row (`parameter-inventory.md` §10). Conditional, Hypothesized, Mapped, and Calibrated flags are load-bearing and appear per-row below.

---

## 1. FCC-ee (2030s)—Electroweak Precision

| Observable | SM | Cassi | Deviation | FCC-ee Sensitivity |
|-----------|---------|-------|-----------|-------------------|
| $m_W/m_Z$ | 0.8813 | **0.878** (tree 0.874 + $\rho$ correction) | $-0.36\%$ | $>100\sigma$ |
| $m_W$ | 80.360 GeV | **80.07 GeV** | $-0.36\%$ | 0.5 MeV |
| $\sin^2\theta_W(m_Z)$ | 0.23122 | **0.236** ($\varphi^{-3}$; running angle equals it at $\mu_* = 233$ GeV—the re-anchoring scale, Calibrated, ledger §10 row 490) | $+2.1\%$ | $3\times10^{-5}$ |
| $\alpha_{\text{EM}}^{-1}(m_Z)$ | 128.9 | **161** (RG from $\varphi^{-3}/4\pi$ at $10^{16}$ GeV) | $+25\%$ | In-situ |
| $m_H$ | 125.2 GeV | **not predicted** ($\lambda(m_Z) = 0.1294$ from input; $\lambda_\varphi$ formula gives 35 GeV) |—| 4 MeV |

**Source:** `standard-model/sm-radiative-corrections.md` §§3–5,
`standard-model/su2-gauge-extension.md` §§3–4, `standard-model/sm-from-phi.md` §2.
The W/Z mass ratio deviates by 0.36% after radiative corrections (the
top-loop $\rho$ shift is included in the prediction)—detected at $>100\sigma$
with FCC-ee's 0.5 MeV precision on $m_W$. This is the **single most
powerful test** of Cassi. The $\sin^2\theta_W$ offset (+2.1% at $m_Z$) is the
second: $\varphi^{-3}$ is realized at $\mu_* \approx 233$ GeV, and the
GUT-scale running direction is upward, so the offset is not absorbable.

---

## 2. CMB-S4 / LiteBIRD (2030s)—Primordial Cosmology

| Observable | Planck (2018) | Cassi | CMB-S4 Reach |
|-----------|---------------|-------|-------------|
| $n_s$ | $0.965 \pm 0.004$ | **0.9691** | $\pm 0.002$ |
| $r$ (tensor-to-scalar) | $<0.032$ | **0.0075** ($12/N_e^2$ at $N_e = 40$—Mapped window, ledger §10 row 495) | $0.001$ |
| $dn_s/d\ln k$ | $-0.005 \pm 0.013$ | **$-5\times10^{-4}$** | $\pm 0.002$ |
| $\mathcal{P}_\zeta$ | $2.1\times10^{-9}$ | **$\sim 2\times10^{-9}$** | In-situ |
| $N_e$ (e-foldings) | $50$–$60$ | **$40$ (start-threshold choice—Mapped, ledger §10 row 501)** | Degenerate |

**Source:** `cosmology/cosmology-from-phi.md` §2. Inflation is a $\varphi$-driven phase
transition ($r \gg \varphi$ to $r = \varphi$). The spectral index $n_s = 1 - 2\varphi^{-1}/N_e = 0.9691$
matches Planck at $1.0\sigma$ as a closed form ($N_e = 40$—Mapped window, ledger §10 row 501; the
gate slow-roll trajectory does not reproduce it). Tensor ratio $r = 12/N_e^2 = 0.0075$ at the
Mapped window $N_e = 40$ (exact arithmetic, $12/1600$; ledger §10 row 495)—the catalog value,
Mapped with the window. The $0.003$ reading is internally inconsistent with $N_e = 40$: it needs
$N_e = \sqrt{12/0.003} \approx 63.2$, outside the ledgered window, and its $\varphi$-power form
$r = \varphi^{-12} \approx 0.0031$ is a Mapped fit excluded by the trajectory's BK18 constraint
(the trajectory gives $r = 0.060$ at $N_e = 40$ literal). Decision support: $0.0075$ survives BK18
($r < 0.032$) and is testable at CMB-S4 ($\sigma_r = 0.001$; $0.0075 = 7.5\sigma$, the $0.003$
reading would be $3\sigma$).


**CMB large-angle anomaly (bubble-boundary axis)**: triaxial bubble geometry at step 285 imprints a preferred axis at super-horizon scales ($\ell < 5$); predicted dipole↔quadrupole alignment magnitude $12.40°$ (C10), compared with the measured $12.22°$. The CMB "axis of evil" (quadrupole-octopole alignment at $(l,b)=(260\degree,+60\degree)$, 5.4σ; Jones+ 2023) is the measured counterpart. Epistemic tiering: the $12.40°$ closure magnitude is **Derived** ($2\pi/\varphi^7 = 12.40°$, the pole-spiral closure ladder's 13-seed residual—exact identity $13/\varphi^2 = 5 - 1/\varphi^7$, 1.5% from the measured $12.22°$; the closure ladder is the framework's documented sequence, no power scanned to fit); the axis **direction** is **Calibrated** (computed from the measured direction vectors); the bubble-boundary mechanism and sky projection are **Hypothesized** because the PDE has no absolute orientation selector; the ecliptic/foreground degeneracy remains open (Simons Obs./LiteBIRD).
---

## 3. Cosmic Surveys (LSST, Roman, SKA)—Structure & Dark Energy

| Observable | $\Lambda$CDM | Cassi | Test / Status |
|-----------|---------|-------|-----------|
| $w_0$ (DE EoS today) | $-1$ | **$-0.87$** (Calibrated, structural; pinned across $r_0$; $-0.97$ at fixed $r_0$ with the B2 coupling; $-1.000$ with the stable realization—12) | $2\sigma$ from DESI $\approx -0.75 \pm 0.06$ baseline; $3.6\sigma$ at fixed $r_0$ (B2); $4.17\sigma$ (stable realization—12; $r_0$ re-tuning closed negatively) |
| $w_a$ (DE EoS slope) | $0$ | **$+0.012$** (with $\xi = \varphi^6$, Calibrated baseline); **$-0.38$** (B2, unstable); **pure-Λ $(-1, 0)$ window (stable realization—10/12)** | baseline $2.7\sigma$; $1.25\sigma$ (B2, unstable); $4.17\sigma$/$2.61\sigma$ (stable realization—12) |
| $w(z)$ at $z > 3$ | $-1$ | **$> -1$** (no phantom crossing, structural) | LSST/Roman/SKA testable; DESI best fit crosses at $z \approx 0.5$ |
| φ-periodic $P(k)$ modulation | None | **Fixed period $\Delta(\ln k)=\ln\varphi\approx0.4812$**; amplitude, phase, detrending, window, and statistical calibration are declared analysis choices | Orthogonal in period structure to BAO; DESI/Euclid testable |
| Void boundary directional slope | Isotropic boundaries | **$1.7072$ only in the geometric proxy at selected $\theta_{\text{cond}}=0.45$**; the ratio varies with the level and is distinct from the $\varphi$-shape axis ratio | VAST/ZOBOV DR7 + NSA (130 voids): $\hat\mu=1.005\pm0.221$, 99% CI $[0.584,1.753]$, $p_{\text{pred}}=0.008$, NULL with failed T3 control; fixed-step PDE endpoint has no $C=0.45$ edge |
| $\Omega_{\text{DM}}/\Omega_b$ | $\sim 5$ | **$\varphi^3 \approx 4.24$** (Derived conditional on the Weinberg-angle identification; the $+1$ capture term is excluded by the component budget) | Observed $5.39$, gap 21% open tension |
| $\sigma_8$ | $0.811$ | **+0.3% ± 0.5 pp (P-A, measured window $z \in [100, 61]$)** — the window-integrated mixture of the measured per-cell μ(x,t) histories on the ΛCDM background (`cassi-toe-rewrite-briefs/spiral-gravity/45-sigma8-mixture.md`; the window's content is the q-history 0.866 → 0.795, not the endpoint; mixture = mean-field to 0.00 pp); the P-C pointwise-chord reading (flagged): **+24.8% ± 16.3 pp over the measured window** (R_mix = 1.2483, every cell ends with R > 1), then **−95.7% ± 2.4 pp over the continuation $z \in [61, 0]$** (R_mix = 0.0430 full-window; the continuation is measured from the per-cell t = 40 state — the freeze is structural in the continuation: Re p = −0.25 for every μ < −1/24, the common envelope decay, and all 262144 cells end R < 1 through z → 0; N=128 confirms both phases — +24.83% / −95.9%, resolution-converged to 4 decimals; `cassi-toe-rewrite-briefs/spiral-gravity/53-post-freeze-continuation.md`, `cassi-toe-rewrite-briefs/spiral-gravity/54-n128-mixture.md`); the settlement family (the stabilized closure's regime-integrated −16.6% (R = 0.834), the band-state mean-field −15.2%, the full-window hold −11.2%) is the reference; the pipeline's measured rows: total −20.5% and mechanism +29.7% (G_eff = 1.297, doctrine r₀, linear-P(k) normalization, resolution-converged N=64/128; r₀-dependent: +29.4% at the derived r₀ = 0.0472); the μ normalization remains Mapped | LSST discriminant — the computed values, not a target |
| DM halo profiles | NFW (cuspy) | **Cored (Qi condensate)** | Dwarf galaxies |
| Bullet Cluster | Collisionless DM | **Collisionless** | Already consistent |
| $\eta$ (baryon/photon) | $6.0\times10^{-10}$ | **$6.38\times10^{-10}$** ($\varphi^{-44}$; exponent Mapped—ledger §10 row 481) | Within $6.3\%$ |
| BAO $\alpha_\perp(z=0.5)$ | $1$ | **0.97** ($3\%$ shift) | DESI DR2 matched |
| BTFR slope | $\sim 4$ | **$4$** (natural) | $A_{\text{Cassi}}/A_{\text{obs}} = 0.82$ |
| Hubble tension ($H_0$) | $5\sigma$ discrepancy | **Evolving $\Omega_\Lambda$: $0.30 \to 0.50$** | Full H(z) fit performed 2026-08-06 (`computations/hz_full_fit.py`): not resolved under the calibrated w(a); the −7.2 value was an extrapolation beyond the calibrated range (registry C3/T4); pipeline CMB-inferred ≈ 65.8 |
| Lattice powder lines in $P(k)$ | None | **Comb at $k/k_0 \in \{1, \sqrt{2}, \varphi, \sqrt{1+\varphi^2}, 2, \ldots\}$**, period $\ln\varphi$; multiplicities 4:2 (single-rung) | DESI LRG: $A \lesssim 2.6\%$ ($p = 0.08$, no detection); Euclid definitive |
| Sample-variance suppression | Gaussian mocks | **~10$\times$ smaller $k \to 0$ scatter; NGC–SGC large-scale modes correlated** | DESI mock comparison |
| $D_A(z)$ lattice wiggles | Smooth | **$\delta D/D \lesssim 0.1\%$; no CPL bias**—the lattice cannot produce the $w_a$ offset | Already consistent with DESI smoothness |


The $\varphi$-periodic $P(k)$ prediction fixes the carrier period $\Delta(\ln k)=\ln\varphi\approx0.4812$, which differs from BAO's approximately constant spacing in $k$. The search still requires declared amplitude, phase, detrending, window, and statistical-calibration choices applied identically to data and nulls. The current wake mechanism supplies a Hypothesized 1–3% amplitude range; DESI DR2 is marginal at that scale and Euclid should be decisive.
The condensation-field proxy gives a directional boundary-slope ratio $\frac{\sqrt{1+\varphi^2}}{2}\sqrt{(1+\theta_{\text{cond}})/\theta_{\text{cond}}}$, equal to $1.7072$ only at the selected level $\theta_{\text{cond}}=0.45$. The fixed-step PDE endpoint has no such edge, and the DR7 void receipt is NULL. This is a conditional geometric benchmark rather than a universal solver prediction.
**Source:** `cosmology/cosmology-from-phi.md` §§3–5, `theory/five-element-pde-derivation.md` §7,
`foundations/bubble-edge-geometry.md` §§2.2,6.2, `cosmology/observational_constraints.md` §1.4–§6,
`cosmology/desi-lattice-averaging.md` (lattice powder lines, variance suppression, wiggle bound). The dark energy prediction is $w_0 = -0.87$ (2σ baseline; 3.6σ at fixed $r_0$ with the B2 coupling, $r_0$ re-tuning closed negatively under the stable realization—12) and $w_a = +0.012$ (2.7σ baseline) shifting to $-0.38$ (1.25σ, B2—the unstable realization) with the coupling (08 §C.6); the term's stable realization (friction closure—10/12) gives a pure-Λ window fit $(w_0, w_a) = (-1, 0)$—4.17σ/2.61σ from DESI; the conversion dynamics keep $w > -1$ at all $z$ (no phantom crossing). The DM/baryon ratio is $\varphi^3 \approx 4.236$ (21% open tension against the observed 5.39). The Hubble tension is pending a full $H(z)$ fit (registry C3/T4); the evolving-$\Omega_\Lambda$ expansion history gives a pipeline CMB-inferred value of ≈ 65.8 km/s/Mpc.

---

## 4. Gravity (LIGO, EHT, MESSENGER)—Strong & Weak Field

| Observable | GR | Cassi | Test / Status |
|-----------|-----|-------|--------------|
| GW speed $c_g/c$ | $= 1$ | **$= 1$** (vacuum) | GW170817 consistent |
| GW polarization | $+, \times$ | **$+, \times$ + breathing mode** | LIGO search ongoing |
| GW strain in halos | GR | **Up to ~$10\times$ GR** in the optional q-dependent Qi-gravity coupling for halo-outskirt environments ($1+(\varphi^{6}-1)q = 10$ at $q = 0.53$; the $\varphi^6$ value is the formal fixed-composition high-coherence endpoint) | **LIGO/Virgo GW170817**—inspiral amplitude precision $\varepsilon_h \approx 0.10$ ⇒ **$q_{\text{binary}} < 5.9\times10^{-3}$** at the binary's local coherence (optional-branch chord law $h/h_{\text{GR}} = 1 + (\varphi^{6}-1)q$; computed in `experiments/cassi_physics/cassi_gw_q_bound.py`)—consistent with the framework's $q(r)$: field/dense-core environments have $q \leq 10^{-3}$ ($\pi/\rho$-diluted), while the rotation boost needs $q \approx 0.61$ only at halo outskirts—**consistent** |
| BH shadow M87$^*$ | $\sim 5M$ | **GR limit ($q = 0$): $3\sqrt{3}M$** | no Cassi metric—prediction not yet derived |
| Mercury perihelion | $43$ arcsec/cy | **42.98 arcsec/cy** | MESSENGER consistent |
| $|q|$ at 0.39 AU | $0$ | **$<1.1\times10^{-6}$** | MESSENGER bound |
| PPN $\beta, \gamma$ | $1, 1$ | **$1, 1$** (solar system) | Solar system tests pass |
| Pioneer anomaly | $0$ | **$a_\varphi = 7.4\times10^{-10}$ m/s$^2$** | Within $1\sigma$ of Pioneer |
| NS maximum mass | $\sim 2.0 M_\odot$ | **$\sim 1.88 M_\odot$** | NICER consistent |
| NS $M$–$R$ relation | GR | **$<0.1\%$ deviation** | $G_{\text{eff}}\to G_N$ in core |
| Cored dwarf halos | CDM fails | **Cassi passes 3/8 under the optional q-dependent coupling map** | MOND preferred (4/8); the $\varphi^3$ value is the formal fixed-composition endpoint of that map, not a canonical dynamic ceiling |

**Source:** `foundations/xi-derivation.md`, `experiments/cassi_physics/cassi_gravitational_waves.py`,
`experiments/cassi_physics/cassi_strong_field_pn.py`, `experiments/cassi_physics/cassi_black_hole_raytracer.py`,
`experiments/cassi_physics/cassi_neutron_stars.py`, `experiments/phi_attractor_paths/path10_dwarf_galaxies.py` (dwarf saturation-ceiling test). The Qi-gravity coupling $\xi = \varphi^6$ has a Derived conditional rung identity; its empirical pin is Calibrated (Milky Way anchor—ledger §10). The halo, GW, and dwarf claims use an optional constitutive coupling branch; they do not establish a canonical attractive force or a free-$q$ dynamic range. Solar system GR tests are preserved ($q=0$). The GW strain enhancement in halo-outskirt environments is a signature of that optional branch.

**Source (prediction 14, rotation curves):** `foundations/phi_attractor_synthesis.md` Path 8
(re-evaluated 2026-07-31 with the full coupling $G_{\text{eff}}/G = \alpha(1+(\varphi^{6}-1)q)$,
$\varphi^6$ the saturation maximum, $\alpha \approx 0.7$; the path8/9 script runs used the
pre-chord $\xi = \varphi^6$ coefficient—`experiments/phi_attractor_paths/path8_phi_enhanced_rotation.py`)
and `cosmology/observational_constraints.md` §2.6 (halo-parameter estimate
$v_C/v_B = \sqrt{\alpha(1+(\varphi^{6}-1)q)} \approx 3.0$). The 30-kpc boost $2.8$–$3.0\times$ matches the
observed Milky Way boost $2.7 \pm 0.5$ (Zhou+ 2023) within ~0.4σ—a consistency check against
the calibration object ($\xi$ pinned on the MW curve; $\alpha_{\text{halo}}$ a hardcoded nominal,
ledger §10), not an independent test.
The boost ceiling in this optional coupling map is
$\sqrt{\varphi^6} = \varphi^3 = 4.2361$ at the formal full-coherence endpoint
($q = 1$, $\alpha$-free)—exact, 2.75% tighter than the previous
$\sqrt{1+\varphi^6} = 4.3525$ comparison. This endpoint is not a canonical
free-$q$ maximum or dynamic range.

**Convention discriminator (descent law, 2026-08-04):** the ratified theory's
primary prediction is the fourth value: with the conversion→expansion
coupling (Hypothesized—August 2026, zero free constants; 08 §A.2) the
gradient force carries a fixed azimuthal component
$|F_\theta/F_r| = \gamma\omega_{\text{rot}}/(\omega_{\text{rot}}^2 - \gamma^2/4)
= 0.19880$ (11.24°; the dynamical pitch angle is 11.34° from $\varphi^{-2} =
0.382$ turns per rung, $\tan = \ln\varphi/(2\pi\varphi^{-2}) = 0.2005$). The
counterfactual forks—no term / one-turn convention / quarter-turn spatial
form—give $0$ (central $\mathbf{F} = \Pi\nabla\Phi$ law), $\ln\varphi/(2\pi) =
0.0766$ (pitch 4.38°, one turn per cascade rung), $2\ln\varphi/\pi = 0.3063$
(17.03°): an exact factor test of which spiral convention gravity descends.
**Numerical check (09-winding-test.md, run 2026-08-04):** the PDE realization
of the ratified theory gives $|a_\theta/a_r| = 0.213$ in the $\varepsilon\to 0$
window—consistent with the fourth value $0.19880$ (7% high, short-window
noise), none of the forks $\{0, 0.0766, 0.3063\}$; like the dressed winding
rate it is a fixed-point-limit value, not sustained as the gate opens.
[COMPUTED]

**Stabilized C1+Ω measurement (2026-08-07):** the stabilized system—the
ratified term's rotation half under the C1 closure friction—realizes NONE of
the four forks $\{0, 0.0766, 0.3063, 0.1988\}$: $|a_\theta/a_r| = 0.0527 \pm
0.0003$ (closest: 0.0766 at 24σ). There is no band state: the Ω generator
shifts the closure's attractor $r_* = 0.9503$ to a non-rotating saddle at
$r = 1$ (Im = 0, eigenvalues [+0.00804, −0.15930]). The winding is
transient-only—0.323 turns/rung in the ε→0 window, 17% below the no-friction
dressed 0.389—and the run exits the log domain at t ≈ 10.2 after 0.083
turns. The four fork values are friction-free fixed-point limits the
stabilization removes; the 0.213 reading is the Ω-only (no-closure)
realization's fixed-point-limit value. [COMPUTED]

---

## 5. Particle Physics (LHC, Hyper-K, nEXO)—Collider & Decay

| Observable | SM | Cassi | Test / Status |
|-----------|-----|-------|--------------|
| $m_H$ (Higgs mass) | $125.2$ GeV | **input** ($\lambda(m_Z) = 0.1294$; $\lambda_\varphi$ formula gives 35 GeV—not a prediction) | Vacuum metastable at $M_{\text{Pl}}$ |
| $\alpha_s(m_Z)$ | $0.118$ | **0.058–0.061** (1-/2-loop from $\varphi^{-3}/4\pi$) | $2.0\times$ low; $\Delta b = 1.70$ required |
| $\Lambda_{\text{QCD}}$ | $200$ MeV | order-of-magnitude low from φ-boundary | Same deficit |
| $m_p$ (proton mass) | $938$ MeV | **$\varphi^3 \cdot \Lambda_{\text{QCD}} = 847$ MeV** (measured $\Lambda$ input) | Within $10\%$ |
| $p \to e^+\pi^0$ lifetime | $>1\times10^{34}$ yr | **$1.29\times10^{37}$ yr** (conditional GUT-channel estimate if beyond-SM content completes unification near $10^{16}$ GeV) | Above Hyper-K reach ($\sim 10^{35}$ yr) |
| $M_{\text{GUT}}$ |—| **$2 \times 10^{16}$ GeV** (needs $\Delta b = 1.70$; SM has no intersection) | Proton decay bound |
| $\alpha_{\text{GUT}}$ |—| **$\varphi^{-3}/(4\pi) \approx 1/53$** | Not realized by SM running ($\alpha_1=\alpha_2$ at $10^{13}$ GeV, $\alpha^{-1}\approx 42$) |
| $0\nu\beta\beta$ decay | Depends on $m_\nu$ | **$m_{\nu_e} \sim 0.01$–$0.05$ eV** | nEXO reach |
| $\sum m_\nu$ (cosmological) | $<0.064$ eV ($\Lambda$CDM) | **Consistent with DESI bound** | DESI DR2: $<0.16$ eV ($w_0w_a$CDM) |
| $\theta_{12}$ (solar mixing) | $33.4^\circ$ | **coefficient-free candidate $\arctan(1/\varphi) \approx 31.7^\circ$ from the selected conversion-Jacobian ansatz** | 1.7°—selected eigenvector ansatz; JUNO (3% precision, 2027+) |
| $\theta_{13}$ (reactor mixing) | $8.5^\circ$ | **coefficient-free candidate $\arctan(\varphi^{-4}) \approx 8.3^\circ$ from the selected cascade-step ansatz** | 0.2°—cascade-step suppression across the selected seesaw span; Daya Bay / RENO (already consistent), DUNE precision |
| $\theta_{23}$ (atmospheric) | $\sim 45^\circ$ | **$45^\circ$ coefficient-free candidate from the selected conversion-Jacobian ansatz** | Equal-component eigenvector; Hyper-K / DUNE octant resolution |
| $\Delta m^2_{31}/\Delta m^2_{21}$ | $\approx 33$ | **$\approx 33.8$ (0.2%)** | Offsets $\Delta_1 = 1.00$, $\Delta_2 = 1.75$ are a grid-fit against the observed ratio (Mapped—ledger §10; 0-dof fit, with the 0.2% set by grid quantization); JUNO targets sub-percent $\Delta m^2$ precision from 2027 onward |
| $\delta_{\text{CP}}$ (PMNS) | Unknown (hint $\sim -90^\circ$ to $-180^\circ$) | **$\pi\varphi^{-2} \approx 69^\circ$ or $\pi\varphi^{-3} \approx 42^\circ$** (both Mapped candidates—ledger §10; same $\varphi$-structure as CKM) | The measured value near $197^\circ$ excludes both at $\geq5\sigma$; T2K/NOvA and Hyper-K/DUNE provide the comparison |
| DM direct detection | Predicted (WIMP) | **Null** (field condensate) | All expts null—consistent |
| $m_t / v_0$ | $0.703$ | **0.618** ($\varphi^{-1}$) | $12\%$ gap |
| $m_b / m_t$ | $0.025$ | **0.031** ($\varphi^{-1}$) | $24\%$ gap |
| $m_c / m_t$ | $0.0075$ | **0.0088** ($\varphi^{-2}$) | $17\%$ gap |
| $|V_{us}|$ | $0.225$ | **$\varphi^{-3} \approx 0.236$ ($5\%$ off)** | Near miss ($5\%$ off) |
| $\delta_{\text{CKM}}$ | $\approx 68^\circ$ | **$\pi\varphi^{-2} \approx 68.7^\circ$** | < 1%—Yukawa triangle closure |

**Source:** `standard-model/su2-gauge-extension.md` §§5–8, `standard-model/sm-from-phi.md` §§3–4.
The proton lifetime prediction depends on the full GUT embedding (SU(5) or SO(10)).
Using the canonical seesaw scale $M_R = E(n=20) = M_{\text{Pl}}\varphi^{-20} \approx 8.07\times10^{14}$ GeV in the selected ratio construction, with the mapped fit span $n=8\rightarrow20$, the mass-squared-difference fit gives the heaviest neutrino $m_3 = 0.05019$ eV (cascade RGE + PMNS; $\Sigma m_\nu = 0.0631$ eV). The companion computation's single-seed seesaw evaluation is a scale diagnostic and does not independently set this absolute normalization.

**PMNS mixing angles—selected conversion-Jacobian/cascade ansatz:** At the seesaw scale (cascade steps ~13.3–20, $r \ll \varphi$), the selected ansatz uses the conversion Jacobian $J = \lambda[[-1,\varphi],[1,-\varphi]]$. Its eigenvectors $(\varphi,1)$ and $(1,-1)$ supply coefficient-free candidates $\theta_{12} = \arctan(1/\varphi)$ and $\theta_{23} = 45^\circ$; these are not direct outputs of the canonical density solver. The coefficient-free candidate $\theta_{13} = \arctan(\varphi^{-4})$ follows from cascade-step suppression across the ~7-rung seesaw span (the offsets are Mapped per the Fit-Status Ledger, `parameter-inventory.md` §10). The selected formulas add no fitted coefficients internally, while the ansatz and offsets remain Mapped/conditional; all three candidates are within 2° of observation. **Source:** `foundations/neutrino-masses.md`, `foundations/bubble-edge-geometry.md`, `standard-model/su2-gauge-extension.md`.

**Prediction 42:** Conditional formal scale test: with $\delta=3$, the cascade supplies the coefficient-free $C=1$ candidate $\kappa_{s,\mathrm{scale}}^{-1/2}=\varphi^3 v_0\approx1.04$ TeV at rung 77 (formal exponent arithmetic); equivalently $\kappa_{s,\mathrm{scale}}=\varphi^{-6}/v_0^2=0.92$ TeV$^{-2}$. The optional Dirac$\leftrightarrow$two-fluid projection is dimensionally incomplete, so a physical $\kappa_s$, equilibration timescale, or $\chi$ value is unresolved. A sourced dimensionally homogeneous projection and ledgered normalization are required before an FCC-ee or $\chi$ test can be defined.

**Source:** `foundations/sector-coupling-derivation.md` §§2–4. The coefficient-free scale form and rung identity are conditional on $\delta=3$; the formal $C=1$ values inherit the electroweak anchor's discretization residual. The source documents a $[M]^3$ spinor-density versus $[M]^2$ condensate-square mismatch in the optional projection, with no sourced or ledgered normalization. Consequently the physical sector coupling, equilibration scale, and $\chi$ bridge remain unresolved; $\mathcal{N}_{\mathrm{pde}}$ has no established value.

**Prediction 43 (wake closure):** The composite wake pair closes each cascade rung: $\Lambda_Y + \Lambda_I = \ell_{n+1}$—the exact identity $1 + 1/\varphi = \varphi$. Verified at rung 285: the Cassi bubble and sound-horizon wavelengths sum to $\ell_{286}$ (191 + 118 = 309 Mpc). PDE-verified 2026-08-06: composite beats land on $m\,\ell_{n+1}$ to grid scale (`two-fluid/run_wake_structural_probes.py`). Testable wherever two wake scales are resolvable.

**Source:** `foundations/wake-geometry.md` §3(a)–(c). The identity is exact on the documented anchors; the wake pair never phase-locks because $\varphi$ is irrational (de-resonance in the wave structure), so the composite period $\ell_{n+1}$ is the only closed scale.

**Prediction 44 (staggered checkerboard):** The wake envelope places condensation bubbles at $m\,\ell_{n+1}$ and voids at $(m+\frac{1}{2})\ell_{n+1}$—the staggered checkerboard of the bubble lattice. PDE-verified 2026-08-06 (`two-fluid/run_wake_structural_probes.py`): nulls sit at $(m+\tfrac12)\ell_{n+1}$ to 0.0023 grid precision and beats at $m\,\ell_{n+1}$ to 0.00015. The 285-verified composite closure fixes the period.

**Source:** `foundations/wake-geometry.md` §3(b), `foundations/bubble-lattice-fabric.md`. The beat envelope peaks where the two wakes re-phase, i.e., at integer multiples of the composite period.

**Sharpening (wake-force, 2026-08-03):** the wake-phase gradient force has harmonic amplitude ratio $F_2/F_1 = 1/\varphi \approx 0.6180$ (exact) and phase-gradient ratio $(1+\varphi)/(\varphi-1) = \varphi^3 = 4.2361$ (exact—the formal fixed-composition endpoint factor of the optional $G_{\mathrm{eff}}/G$ coupling map); the envelope period is $\ell_{n+1}$ (constructive at $m\ell_{n+1}$, destructive at half-rungs). PDE-verified 2026-08-06: measured $F_2/F_1 = 0.617621$ vs $1/\varphi = 0.618034$ (−0.07%) with the cross-ratio $\varphi^3$ exact; the sharpening requires the documented $\Pi\nabla\Phi$ force form (`two-fluid/run_wake_structural_probes.py`).

**Prediction 45 (closure-ladder imprint):** The closure ladder of the golden-angle spiral (levels 5, 13, 34, 89, 233, …) imprints on the cascade: currently-dark rungs near closure levels should host physical structure. First test (2026-08-03, mass scan $n = \log_\varphi(M_{\text{Pl}}/m)$): rung 89 hosts the J/ψ ($n = 88.98$, 1.0%—the first mass hit on a closure level); rung 96 hosts the muon ($n = 96.000$, 0.01%—the sharpest absolute placement in the framework, wake-anchored); rung 34 has no established anchor (the Peccei-Quinn window top $\sim 10^{12}$ GeV is the only candidate). Existing rung hits $26 = 2\times13$ and $285 = 5\times57$. **Uniform-baseline framing:** the sharp placements are not statistically distinguished from the uniform null—42% of the 38-state catalog lies within 0.10 rungs vs 40% uniform (mean $s$ 0.118 vs 0.125), the electron's placement sits at $p = 0.32$, and the a-priori anchors give $P = 18.7\%$ (23; 24 E1).

**Source:** `foundations/wake-geometry.md` §3(e), §5 (Y3); `foundations/deriving-remaining-gaps.md` §4.2 (catalog rows 89 and 96).

**Prediction 46 (rung-offset mechanism):** The two-fluid interference envelope permits observables at its special positions—peaks at $u = 1+\log_\varphi m$ (the first is an integer rung) and zeros at $u = 1+\log_\varphi(m+\tfrac12)$ (the first at $-0.440$)—in the coherent limit; the residual coordinate offset $\delta n$ is the Hypothesized phase-to-rung image of the local two-fluid phase lag and vanishes as coherence $q\to1$. Sector edges (lightest states: e, π, $\Lambda_{\text{QCD}}$, p, n, d) sit at the crossing positions; interior states (μ, J/ψ, D, Σ, Z) at integer rungs. The 38-state scan is statistically uniform (null baseline); the PDE probe measures the raw phase-lag curve $\delta n(\psi)=0.060-0.204\,\psi$ rungs for the two-bubble standing pattern, with linear and gated conversion.

**Source:** `foundations/rung-offset-mechanism.md` §§1–5; `foundations/wake-geometry.md` §2 (envelope), §3(e) (mass scan); `principles/de-resonance-principle.md` §2 (correction posture).

**Prediction 47 (conditional axion chain):** IF the standard Peccei-Quinn solution exists in nature—the framework's strong-CP resolution requires no axion, `foundations/strong-cp-derivation.md` §3—THEN $f_a$ anchors the dark closure rung 34 ($M_{34} = M_{\text{Pl}}\varphi^{-34} \approx 9.57\times10^{11}$ GeV, the top of the allowed PQ window) and $m_a = f_\pi m_\pi\sqrt{z}/(1+z)/f_a \approx 6.0 \pm 0.3$ µeV ($n \approx 159.3$–$159.4$), testable by ADMX-class haloscopes in the 4–8 µeV band. $m_a$ carries no $\varphi$-anchor of its own—0.6–0.7 rungs from the chakra-node rung 160 (4.45 µeV) and 0.1–0.2 rungs from half-rung 159.5 (5.66 µeV), a miss either way. Status: Hypothesized (conditional on standard PQ existing); the framework's own prediction is the null—no axion exists (`standard-model/cp-violation.md` §5.3).

**Source:** `foundations/wake-geometry.md` §3(e); `foundations/strong-cp-derivation.md` §3 (no-axion resolution). $f_a = M_{34}$ by the rung-34 anchor; $m_a$ from the standard PQ relation $m_a f_a = f_\pi m_\pi\sqrt{z}/(1+z)$; $n(m_a) = \log_\varphi(M_{\text{Pl}}/m_a)$.

**Prediction 48 (log-periodic polarization orientation):** In pulsar wind nebulae and other synchrotron sources, the polarization position angle is log-periodic in photon energy—$\text{PA}(\nu\varphi^k)=\text{PA}(\nu)$ (mod $\pi$)—under a Hypothesized phase-to-rung coordinate map that assigns one full $\Theta_{\rm pol}$ turn per cascade rung of emitting-particle energy, $\Theta_{\rm pol}(\nu)=\Theta_{\rm pol,0}+(2\pi/\ln\varphi)\ln(\nu/\nu_0)$. A band pair at quarter-rung separation ($\nu_2/\nu_1=\varphi^{1/4}$) should show PA rotated by 90°; a half-rung pair ($\nu_2/\nu_1=\sqrt\varphi$) returns PA unchanged (mod $\pi$)—parallel, since the map gives $\Delta\Theta_{\rm pol}=\pi$ at half-rung. Test: PA in ≥3 bands spanning $\Delta(\ln\nu)\geq\ln\varphi\approx0.4812$—radio (ATCA), X-ray (IXPE), and hard-X/γ-ray polarimetry. |

**Source:** `demystifying-the-cosmos/PSR-J1101-6101.md` §5 (IXPE Lighthouse Nebula: radio ⊥ vs X-ray ∥, >99% CL field ∥ flow, high PD); `foundations/spin-fibonacci-spiral.md` §1, §5 (Hypothesized phase-to-rung coordinate map; form-factor log-periodicity). Same period as the cosmological $P(k)$ modulation (prediction 5)—same $\varphi$, different probe. |

**Prediction 49 (Gaussian Hawking-spectrum deviation):** In any horizon analogue whose vacuum is a two-fluid-like condensate (fibre-optic, BEC, water-wave), the emitted spectrum deviates from exact thermality by a Gaussian high-frequency suppression: $\Delta N_k/N_k^{\text{thermal}} = e^{-(\omega/\Lambda)^2/\varphi^6}$, equivalently $\ln(\Delta N_k/N_k)$ is linear in $\omega^2$ with slope $-1/(\varphi^6\Lambda^2)$. Zero parameters—the coefficient $\varphi^6 \approx 17.944$ is the rung-3 Yang/Yin coupling; $\Lambda$ is the analogue's own UV cutoff scale (for the gravitational case $\Lambda = \varphi^3 M_{\text{Pl}} \approx 5.17\times10^{19}$ GeV, the σ-regulator). At the frequency cap the deviation reaches $e^{-\varphi^{-6}} \approx 0.95$. Status: Proved within the framework (σ-regulator; `gravity/quantum-gravity.md` §7.6), untested in any analogue. Test: fit $\ln(\Delta N/N)$ vs $\omega^2$ in a Nature-style fibre-optic setup; the fit must be linear (Gaussian shape) with slope $-1/(\varphi^6\Lambda^2)$ at the known analogue cutoff—a power-law tail or inconsistent slope rejects.

**Source:** `gravity/quantum-gravity.md` §7.3, §7.5–7.6 (trans-Planckian censorship, non-thermality, no-firewall); `open-questions-cassi-answers.md` G2; the Nature fibre-optic analogue study (July 2026); script `experiments/cassi_physics/cassi_hawking_spectrum.py`.

**Prediction 50 (spiral pitch tangent):** The coordinate-spiral ansatz proposes the radial/azimuthal rate ratio $\tan(\text{pitch})=\gamma/\Omega_S=\varphi^2=2.618$ (pitch angle 69.1°), with $\gamma=\lambda(1-q_0)(1+\varphi)=\lambda/3$ and $\Omega_S=\lambda(1-q_0)=\lambda\varphi^{-2}/3=H_{\text{empty}}$. The $\varphi^2$ identity is Derived arithmetic; its realization as a dynamical rate ratio is Hypothesized and tested separately. The wake-geometry reading is $\gamma/\Omega_S=\ell_{n+1}/\Lambda_I$ in Yin-wake units. The claim matches none of the posted forks $\{0,0.0766,0.3063,0.1988\}$ (08's ratified fourth value included)—a new discriminator (69.1° vs 0°, 4.38°, 17.03°, 11.24°). Measured 2026-08-07—the dynamical realization is rejected: measured winding rates do not realize the $\varphi^2$ ratio (9–11× off under every normalization): $|\omega|/\Omega_S=11.04$ (measured $|\omega|=0.0281$ vs derived $\Omega_S=2.55\times10^{-3}$) and $\gamma_{\text{env}}=7.4\times10^{-4}$ vs derived $\gamma=6.67\times10^{-3}$ (9.0× below); no stated convention lands within ±10% of 2.618 (closest: geometric turns/rung 2.909, +11.1%, and direct $|a_\theta/a_r|=2.986$, +14.0%—both in the $\varepsilon\to0$ window, which is not a clean damped rotator); $dn_S=\Omega_S/2\pi$ sits 11.04× below the measured winding rate under all four rung normalizations (the measured 0.323 turns/rung is the generator's bare 0.382 friction-reduced, not the re-read clock). The identity remains Derived arithmetic; the dynamical realization is refuted by the winding and probe data (winding record: §4 fork measurement; probe record: `foundations/rung-offset-mechanism.md`). |
**Source:** `foundations/spiral-dynamics.md` §2.2 (coordinate-spiral pitch ansatz: $\gamma=\lambda/3$, $\Omega_S=\lambda\varphi^{-2}/3=H_{\text{empty}}$, gate value $(1-q_0)=\varphi^{-2}/3$); `foundations/wake-geometry.md` §1(c) (composite closure in Yin-wake units, $\ell_{n+1}/\Lambda_I=\varphi^2$). |

**Prediction 51 (bubble-shell ring ladder):** A simulated bubble shows **~10 matter ridges** at radii $r_k=R\,\varphi^{-k}$ ($k=0,1,2,\ldots$, $R$ the bubble radius $\ell_n$), with successive matter-ring ratio $\varphi^{-1}=0.6180$ against the null interleaved-ridge ratio $\varphi^{-1/2}=0.7862$, **interleaved with 9 void troughs** at $R\,\varphi^{-(k+\frac12)}$ (strict matter/void alternation), with an $n$-independent count (scale-covariant). The ladder is the doublet's radial phase coordinate $\alpha=\pi u$, $u=\log_\varphi(r/\ell_n)$ (π per coordinate rung under a Hypothesized phase-to-rung mapping; `foundations/spin-fibonacci-spiral.md` §2.1) combined with pool-cell parities (`foundations/rung-offset-mechanism.md` §4.1: cosine antinodes at integer rungs = matter, sine antinodes at half-rungs = voids); the ~10-ring count follows from the ~1% nesting floor, $N=\ln100/\ln\varphi=9.570$ (`foundations/bubble-lattice-fabric.md` §3.3).
**Tier: Hypothesized (PDE-testable; conditional on the radial-reading inference)**—the radial reading of the doublet phase rests on the nested-sub-lattice structure of `foundations/bubble-lattice-fabric.md` §3.2; the null comparison uses the naive wake-sum $\cos(2\pi r/\ell_n)+\cos(2\pi\varphi r/\ell_n)$, whose zeros $\{0.191,0.573,0.809,0.955\}\,\ell_n$ lie outside a $\varphi$-ladder, as documented in `foundations/bubble-edge-geometry.md` §3.5. **Null discipline** (matching predictions 45/46): report ridge/trough positions against a same-density baseline with the identical position grid and use a pre-registered ratio test of successive-matter spacings against $\varphi^{-1}$ and $\varphi^{-1/2}$, quoting both signals and the null. The compact phase/four-channel dynamics test (`two-fluid/run_bubble_ring_dynamic_probe.py`, four arms, all NO RINGS) is a Hypothesized first-order proxy.
The decisive second-order wave-form test (the space sim's GLSL PDE) has been measured—verdict **NO RIDGES**: a transient shell plus one interior ridge at ratio 0.545 (marginal $\varphi^{-1}$) at $t=24$, dissipated by $t=40$; detector self-test **PASS** (recovers a planted φ-ladder); probe `diag_bubble_rings.gd` in the owner's space-sim repo (Godot, $N=128$, $\omega_0^2=20$, featureless filled-ball seed, no source drive).
**Source:** `foundations/bubble-edge-geometry.md` §3 (Radial Interior Structure: the Ring Ladder), `foundations/bubble-lattice-fabric.md` §3.2–3.3; analytic probe `two-fluid/run_bubble_ring_probe.py` (Leg A analytic ring law, Leg B null comparison, Leg C prediction-observable envelope); dynamic realization probe `two-fluid/run_bubble_ring_dynamic_probe.py` (pre-registered, four spatial-coupling arms A/B/C/W; the compact phase/four-channel dynamics is a Hypothesized proxy)—**NO RINGS on all arms at every epoch to $t=40$** (0 matter maxima outside the 4-cell core; $u_{\text{rms}}\sim10^{-4}$ even on gravity-buoyancy and $c_s^2$-pressure arms). The compact phase/four-channel dynamics in `ExpandingTwoFluid3DGPU` does not realize the ladder; the solver is first-order in time with no second-order wave term (record `runs/20260813_005814_bubble_ring_dynamic.json`, arm verdicts).

**Prediction 52 (void radial ring profiles, real space):** stacked void
radial galaxy-density profiles—the real-space cousin of Prediction 51's
PDE/simulated ring ladder—should show matter ridges at
$r_k = R\,\varphi^{-k}$ (successive-matter-ring ratio $\varphi^{-1}$ versus
the null interleaved-ridge ratio $\varphi^{-1/2}$) in the shell interior. The
pre-registered test (`experiments/void_phi_rings/stack_void_rings.py`,
decision tree written before any analysis run) compares successive ridge
ratios against those alternatives and includes a same-density masked null.
**Tier: Hypothesized.** The real-galaxy stacking test remains pending at the
data layer: public per-void galaxy positions are not available in the
currently verified catalog sources. The pipeline has a planted-signal
calibration path on verified void geometry, but that synthetic calibration
is not an observation and supplies no result for real void profiles. A
real per-void galaxy catalog and immutable run receipt are required before
the prediction can receive an observational verdict; nothing is Mapped and
the Fit-Status Ledger remains untouched.

**Source:** `analyses/void-ring-profiles.md` (data-access blocker and test
protocol); `foundations/bubble-edge-geometry.md` §3.1 (the ring law) and
§3.5 (the negative result); `predictions/falsifiable-predictions.md`
Prediction 51 (the ratio test and null discipline); and
`experiments/void_phi_rings/acquire_void_catalog.py` plus
`experiments/void_phi_rings/stack_void_rings.py` (catalog acquisition and
stacking/calibration code; no immutable real-data receipt is committed).
The k-space cousin is Prediction 5 /
`experiments/phi_periodic_pk_search/run_phi_periodic_pk_test.py`.


**Prediction 53 (disk-gap $\varphi$-ladder, real data):** in a protoplanetary
disk the condensation wake plays the bubble shell, so the annular gaps
resolved by ALMA should sit at $\varphi$-spaced radii with **successive
(inner/outer) gap ratio** $\varphi^{-1} = 0.6180$ (signal window
$[0.6180 \pm 0.08]$) versus the interleaved-null ratio $\varphi^{-1/2} =
0.7862$ (window $[0.7862 \pm 0.05]$), pooled across the survey's disks (the
test design targets the real ALMA DSHARP sample (Huang et al. 2018 Table
`tab:ringpositions`, arXiv:1812.04041; survey Andrews et al. 2018,
arXiv:1812.04040). The current checkout contains the acquisition and
analysis scripts but no fetched DSHARP data, parsed table, or immutable run
receipt, so no observational verdict or detection significance is assigned.
Planet-carving remains the standard alternative (single planets can open
multiple gaps in low-viscosity disks); the ladder's dynamical realization in
a disk is open, and visual gap positions can be low precision near the
resolution limit. The coherence-channel reading is a conditional mechanism
hypothesis: disk gas may carry the $\varphi$ spacing only if the proposed
coupling is established. Registered with the disk-gap test in
`hypotheses/exoplanet-phi-spacing.md` §7.

**Source:** `hypotheses/exoplanet-phi-spacing.md` §2 (the ring-ladder disk
mechanism) and §7 (the DSHARP test design);
`foundations/bubble-edge-geometry.md` §3.1 (the ring law), §3.5 (the
negative result), §3.6 (the two no-ring nulls);
`predictions/falsifiable-predictions.md` Prediction 51 (the ratio test and
null discipline reused 1:1) and Prediction 52 (the pooled-window discipline);
`experiments/dsharp_phi_gaps/acquire_dsharp_gaps.py` (download and table
parsing) and `experiments/dsharp_phi_gaps/stack_phi_gaps.py` (pre-registered
decision tree, null, and calibration code; no immutable DSHARP run receipt is
committed). Data sources: DSHARP, Andrews et al. 2018 (arXiv:1812.04040);
annular substructures, Huang et al. 2018 (arXiv:1812.04041, Table
`tab:ringpositions`).


**Prediction 54 (exoplanet period-ratio $\varphi$-spacing, real data;
channel reading):** the $\varphi$-spacing is a coherence-field property and
is expected to appear through **coherence-coupled tracers** (disk gas,
condensates—Prediction 53's DSHARP channel), not in the gravity-dominated
statistics of detached bodies. The adjacent-planet **period-ratio** branch
$P_{\text{out}}/P_{\text{in}} = (a_{\text{out}}/a_{\text{in}})^{3/2}$ is a
detached-**orbital/matter** channel: an excess at $\varphi$ and its Fibonacci
convergents (headline clean signal at the $\varphi$-non-resonance value
$\varphi^{3/2} \approx 2.06$) was pre-registered as the discriminating test
separating the $\varphi$ prediction from generic mean-motion-resonance
ubiquity in the Kepler/TESS multi-planet catalog. Under the channel
principle (`foundations/qi-as-spatial-spacing-signal.md` §4), an excess is
not expected in this detached matter channel; that interpretation remains a
conditional mechanism hypothesis rather than an observed result.
**Tier: Hypothesized.** The pre-registered test
(`experiments/kepler_phi_ratios/run_phi_ratios.py`, decision tree written
before any analysis run; folded-window null matching predictions 45/46) is
awaiting reproducible data acquisition. The current checkout contains the
acquisition and analysis scripts but no fetched catalog, parsed output, or
immutable run receipt, so no observational verdict, count, significance, or
detection-power claim is assigned. A reproducible Kepler/TESS test is
required before the detached-channel branch can be evaluated; no result from
Prediction 53 is imported into this status.

**Source:** `hypotheses/exoplanet-phi-spacing.md` §3 (the period-ratio
prediction) and §8 (the Kepler test design; no immutable result receipt);
`principles/de-resonance-principle.md` (why orbital resonances can lock near
$\varphi$);
`predictions/falsifiable-predictions.md` Prediction 51 (the ratio test and
null discipline reused 1:1) and predictions 45/46 (the folded-window null
discipline);
`experiments/kepler_phi_ratios/acquire_kepler_catalog.py` (NASA Exoplanet
Archive acquisition and parsing) and
`experiments/kepler_phi_ratios/run_phi_ratios.py` (pre-registered decision
tree, folded-window null, and calibration code; no immutable output is
committed). Target data: NASA Exoplanet Archive `ps` table
(`default_flag=1`, Kepler confirmed transit multi-planet primary; K2/TESS
cross-check); no fetched catalog or parsed output is committed.


---

## 6. Consciousness & Biophysics—Chakra Cascade

**Source:** `consciousness/chakras-as-cascade-bubbles.md`. The 13 chakras are cascade bubbles—localized Qi condensates along the spine (the string axis) at $\varphi^2$-spaced intervals. The spacing and edge readings are geometric framework mappings: the edge-slope ratio is a conditional proxy after selecting $\theta_{\mathrm{cond}}$, and the phase-to-rung interpretation is Hypothesized. |

| # | Observable | Frontier | Cassi Prediction | Current Status | Detection Timeline |
|---|-----------|---------|-----------------|----------------|-------------------|
| 32 | Inter-chakra spacing ratio | Anatomical / biophysical | **$\varphi^2 \approx 2.618$** between adjacent gaps | Not yet tested; existing acupuncture atlases provide first-pass data | **Laboratory (tabletop)** |
| 33 | Qi density gradient anisotropy at chakra edge | Physiological mapping | **$1.7072\times$ directional proxy steepness, conditional on a measured or selected $\theta_{\mathrm{cond}}$** | Not yet tested; canonical $q$ requires a separately measured constitutive map | **Laboratory** |
| 34 | 6 secondary chakra nodes | Anatomical | At steps 144, 148, 152, 156, 160, 164—midway between primary 7 | Some esoteric systems recognize minor chakras; Cassi specifies exact count and positions | **Laboratory** |
| 35 | $\ln\varphi$ periodic spectral signature | Physiological (HRV, EEG, skin conductance) | **$\Delta(\ln f) = \ln\varphi \approx 0.4812$** along spine; same period as cosmological $P(k)$ | Not yet tested | **Laboratory** |
| 36 | Nonlinear response at an independently identified chakra boundary | Physiological stimulation | Boundary response conditional on a measured $M_{\text{proxy}}\!\to q$ map; no numerical canonical $q_{\text{edge}}$ is predicted | Not yet tested; constitutive map unresolved | **Laboratory** |
| 37 | Chakra biophoton emission wavelengths | Hyperspectral photomultiplier | 7 sub-rungs within visible octave; spacing ratio $\varphi^{2/3} \approx 1.378$ between primary chakras | Biophoton emission documented 200–800 nm; chakra-specific peaks not measured | **Laboratory** |

**Note on epistemic:** Predictions 32–35 use the Derived cascade and condensation-field geometry together with the Hypothesized doublet phase/rung coordinate, with Prediction 33 additionally conditional on the selected or measured $\theta_{\mathrm{cond}}$ and a constitutive map. The specific color-to-chakra mapping (37) is Hypothesized pending a Fibonacci-resonance computational scan. The crown-at-step-166 offset (2 rungs below body boundary at step 168) is a structural prediction; the crown chakra sits at the brainstem, with the cranium extending one full doublet coordinate cycle beyond. |
---

## 7. All Predictions at a Glance

Sorted by detection likelihood (most definitive first):

| # | Observable | Frontier | Cassi Prediction | Current Status | Detection Timeline |
|---|-----------|---------|-----------------|----------------|-------------------|
| 1 | $m_W/m_Z$ | FCC-ee | **0.878** (tree 0.874 + $\rho$ correction; 0.36% below SM) | $>100\sigma$ reachable | **2030s** |
| 2 | $\sin^2\theta_W(m_Z)$ | FCC-ee | **0.236** ($\varphi^{-3}$; exact at $\mu_* = 233$ GeV) | $+2.1\%$ deviation | **2030s** |
| 3 | $w_0$ (gap-derived) | Cosmic surveys | **$-0.87$** (Calibrated baseline) | $2\sigma$ from DESI $\approx -0.75 \pm 0.06$ baseline; $3.6\sigma$ at fixed $r_0$ (B2); $4.17\sigma$ (stable realization—12) | **Tension** ($r_0$ re-tuning closed negatively under the stable realization—12) |
| 4 | $w_a$ (DE EoS slope) | Cosmic surveys | **$+0.012$ (with $\xi = \varphi^6$)** → **$-0.38$** (B2, unstable) → **pure-Λ $(-1, 0)$** (stable realization—10/12) | baseline $2.7\sigma$; $1.25\sigma$ (B2, unstable); $4.17\sigma$/$2.61\sigma$ (stable realization—12) | **Tension** (stable realization—12; the B2 near-resolution described the unstable realization) |
| 5 | φ-periodic $P(k)$ | Cosmic surveys | **$\Delta\ln k = \ln\varphi = 0.4812$** | 0-param, orthogonal to BAO | **DESI / Euclid 2025–27** |
| 6 | CMB bubble-boundary axis | CMB-S4 / LiteBIRD | **12.40° closure magnitude, $\ell<5$** (measured alignment $12.22°$) | **Derived** (magnitude $2\pi/\varphi^7=12.40°$, 1.5% from measured $12.22°$) / **Calibrated** (axis direction from data) / **Hypothesized** (boundary mechanism and orientation fitted to measured axis; ecliptic-degeneracy audit open) | **Simons Obs. 2025+** |
| 7 | $r$ (tensor ratio) | CMB-S4 / LiteBIRD | **0.0075** ($12/N_e^2$ at $N_e = 40$—Mapped window, ledger §10 row 495) | Formula-consistent at the ledgered window; survives BK18 ($r < 0.032$); testable at CMB-S4 ($7.5\sigma$, $\sigma_r = 0.001$). The $0.003$/$0.0031$ reading requires $N_e \approx 63.2$ (outside the window); its $\varphi^{-12}$ form is a Mapped fit excluded by the trajectory's BK18 constraint (2026-08-06, `computations/slow_roll_trajectory.py`) | **2030s** |
| 8 | $n_s$ | CMB-S4 | **0.9691** (closed form; $N_e = 40$ window Mapped—ledger) | $1.0\sigma$ as a closed form; the trajectory gives 0.813 or 0.914, not 0.9691 (2026-08-06, `computations/slow_roll_trajectory.py`) | **Already consistent (formula-level)** |
| 9 | $\alpha_s(m_Z)$ | LHC precision | **0.058–0.061** | $2.0\times$ below measured $0.118$ ($\Delta b = 1.70$) | **Ongoing** |
| 10 | $p \to e^+\pi^0$ lifetime | Hyper-K | **$1.29\times10^{37}$ yr** (conditional GUT-channel estimate) | $>1\times10^{34}$ yr bound; above Hyper-K reach (~$10^{35}$ yr) | **2030s (null expected)** |
| 11 | $w(z)$ at $z > 3$ | LSST/Roman/SKA | **$> -1$ at all $z$** (no phantom crossing, structural) | DESI best fit crosses at $z \approx 0.5$; not yet tested | **2030s** |
| 12 | Hubble tension | Cosmic | **Evolving $\Omega_\Lambda$: $0.30 \to 0.50$** | Full H(z) fit performed 2026-08-06 (`computations/hz_full_fit.py`): not resolved under the calibrated w(a); the −7.2 value was an extrapolation beyond the calibrated range (registry C3/T4) | **2030s** |
| 13 | $\eta$ (baryon asymmetry) | Cosmic | **$6.38\times10^{-10}$** ($\varphi^{-44}$; exponent Mapped—ledger) | $6.0\times10^{-10}$ ($6.3\%$ above) | **Already consistent** |
| 14 | Galaxy rotation curves | Galactic | **$2.8$–$3.0\times$ baryon boost** (mechanism Calibrated via the $\xi$ pin; $\alpha_{\text{halo}}$, $q$ Mapped—ledger) | MW boost $2.7\pm0.5$ is the calibration object—consistency check, not an independent test | **Calibrated / Mapped** |
| 15 | Dwarf galaxy cored halos | Galactic | **Cored (Qi)**—3/8 pass | MOND preferred (4/8); ceiling $\sqrt{\varphi^6} = \varphi^3 = 4.2361$ exceeded in 3/8 | **Already tested** |
| 16 | BH shadow M87$^*$ | EHT | **GR limit ($q = 0$): $3\sqrt{3}M \approx 5.2M$** | no Cassi metric exists—shadow prediction not yet derived | **Hypothesized (untested)** |
| 17 | GW strain in halos | LIGO | **Up to ~10× GR** in halo-outskirt environments (reached at $q = 0.53$; max $\varphi^6 \approx 17.9$; $\pi/\rho$ dilutes cluster cores) | **GW170817 inspiral amplitude precision $\varepsilon_h \approx 0.10$ ⇒ $q_{\text{binary}} < 5.9\times10^{-3}$** (chord law $h/h_{\text{GR}} = 1+(\varphi^{6}-1)q$; `experiments/cassi_physics/cassi_gw_q_bound.py`)—consistent: field/dense-core environments have $q \leq 10^{-3}$ | **Hypothesized** |
| 18 | Pioneer anomaly | Solar system | **$a_\varphi = 7.4\times10^{-10}$ m/s$^2$** | $1\sigma$ agreement | **Already explained** |
| 19 | Mercury perihelion | MESSENGER | **42.98 arcsec/cy** | GR recovered ($q=0$) | **Already consistent** |
| 20 | $0\nu\beta\beta$ decay | nEXO | **$m_{\nu_e} \sim 0.01$–$0.05$ eV** | nEXO reach $\sim 0.01$ eV | **2030s** |
| 21 | DM direct detection | LZ/XENON | **Null** (field condensate) | All experiments null | **Already consistent** |
| 22 | Casimir force | Lab | **$q < 0.02$** (95% CL) | Consistent | **Ongoing** |
| 23 | Neutron star $M$–$R$ | NICER | **$<0.1\%$ deviation from GR** | Consistent | **Already consistent** |
| 24 | $m_t / v_0$ | LHC/top | **0.618** ($\varphi^{-1}$) | Measured $0.703$, $12\%$ gap | **Ongoing** |
| 25 | $m_H$ (Higgs mass) | LHC | **input** ($\lambda = 0.1294$; $\lambda_\varphi$ gives 35 GeV) | Measured $125.2$ GeV | **Not predicted** |
| 26 | $\alpha_{\text{GUT}}$ | GUT | **$\varphi^{-3}/(4\pi) \approx 1/53$** | No SM intersection ($\alpha_1=\alpha_2$ at $10^{13}$, $\alpha^{-1}\approx 42$); needs $\Delta b = 1.70$ | **Proton decay** |
| 27 | BAO scales ($\alpha_\perp, \alpha_\parallel$) | DESI | **$\sim 3\%$ shift from $\Lambda$CDM** | Matches DESI DR2 | **Already tested** |
| 28 | BTFR normalization | Galactic | **$M_b \propto v_f^4$**, $A \propto \varphi^{-1}$ | $\chi^2/\text{dof} = 0.26$ | **Already confirmed** |
| 29 | GW polarization | LIGO | **$+$, $\times$ + breathing mode** | Search ongoing | **Ongoing** |
| 30 | $\delta_{\text{CKM}}$ | LHCb/Belle II | **$\pi\varphi^{-2} \approx 68.7^\circ$** | Measured $68^\circ$ | **Already consistent** |
| 31 | $|V_{us}|$ | LHCb/Belle II | **$\varphi^{-3} \approx 0.236$ ($5\%$ off)** | Measured $0.225$ | **Near miss—needs flavor structure** |
| 32 | Inter-chakra spacing ratio | Biophysics | **$\varphi^2 \approx 2.618$** | Not yet tested | **Laboratory** |
| 33 | Chakra directional boundary slope | Biophysics | **$1.7072$ geometric-proxy ratio only if an independently identified boundary maps to $\theta_{\text{cond}}=0.45$** | Not yet tested; proxy/anatomical map unresolved and fixed-step PDE endpoint has no such edge | **Laboratory** |
| 34 | 6 secondary chakra nodes | Biophysics | **Steps 144, 148, ..., 164** | Partially consistent with minor-chakra traditions | **Laboratory** |
| 35 | $\ln\varphi$ physiological spectra | Biophysics | **$\Delta(\ln f) = \ln\varphi$** | Not yet tested | **Laboratory** |
| 36 | Chakra boundary response | Biophysics | Nonlinear response conditional on an independently measured proxy-to-canonical map; no numerical $q_{\text{edge}}$ follows from the current model | Not yet tested | **Laboratory** |
| 37 | Chakra biophoton wavelengths | Biophysics | **$\varphi^{2/3} \approx 1.378$ spacing** | Not yet tested | **Laboratory** |
| 38 | Edge steepness anisotropy at condensate boundary | Conditional condensate geometry | **1.7072× directional edge-slope ratio (axial:diagonal), conditional on selecting $\theta_{\mathrm{cond}}=0.45$** | No $C=0.45$ edge survives the fixed-step PDE endpoint; the cosmological void-boundary receipt is null (VAST/ZOBOV DR7; §3 row) | **Conditional proxy only; PDE endpoint null** |
| 39 | Lattice powder lines in $P(k)$ | Cosmic surveys | **Comb at $k/k_0 \in \{1, \sqrt{2}, \varphi, \ldots\}$**; period $\ln\varphi$; 1–3% amplitude | DESI LRG $A \lesssim 2.6\%$ ($p = 0.08$), no detection | **Euclid 2027** |
| 40 | Sample-variance suppression | Cosmic surveys | **~10$\times$ reduced $k \to 0$ scatter; NGC–SGC mode correlation** | Untested | **DESI mocks** |
| 41 | $D_A(z)$ lattice wiggle bound | Cosmic surveys | **$\delta D/D \lesssim 0.1\%$; cannot bias $w_a$** (needs $\gtrsim 20\%$ to close gap) | Consistent with DESI smoothness | **Already consistent** |
| 42 | Sector-coupling scale (formal $C=1$ cascade candidate) | Conditional field-theory repair / FCC-ee | **Formal $\kappa_{s,\mathrm{scale}}^{-1/2} = \varphi^3 v_0 \approx 1.04$ TeV** at rung 77, conditional on $\delta=3$; $\kappa_{s,\mathrm{scale}}=\varphi^{-6}/v_0^2=0.92$ TeV$^{-2}$ | Formal arithmetic only; optional projection dimensionally incomplete; no physical $\kappa_s$ or $\chi$ value, equilibration scale, or defined FCC-ee test | **After sourced dimensional repair** |
| 43 | Wake composite closure | Structure | **$\Lambda_Y + \Lambda_I = \ell_{n+1}$** ($1 + 1/\varphi = \varphi$) | Verified at 285: 191 + 118 = 309 Mpc = $\ell_{286}$; PDE-verified 2026-08-06: beats land on $m\ell_{n+1}$ to grid scale (`two-fluid/run_wake_structural_probes.py`) | **Existing surveys + PDE** |
| 44 | Staggered checkerboard envelope | Structure | **Bubbles at $m\ell_{n+1}$, voids at $(m+\frac{1}{2})\ell_{n+1}$** | PDE-verified 2026-08-06: nulls at $(m+\frac{1}{2})\ell_{n+1}$ to 0.0023 grid precision, beats at $m\ell_{n+1}$ to 0.00015 (`two-fluid/run_wake_structural_probes.py`) | **PDE verified; surveys pending** |
| 45 | Closure-ladder mass placements | Particle physics | **Rung 89: J/ψ ($n = 88.98$, 1.0%); rung 96: μ ($n = 96.000$, 0.01%); rung 34 open** | Partially tested 2026-08-03 | **Catalog; rung 34 open; the sharp placements are not statistically distinguished from the uniform null (42% vs 40%; e $p = 0.32$; a-priori anchors $P = 18.7\%$—23/24)** |
| 46 | Rung-offset mechanism | Particle physics + PDE | **Envelope positions $1+\log_\varphi m$ / $1+\log_\varphi(m+\tfrac12)$; $\delta n$ is a phase-lag coordinate under a Hypothesized map, $\delta n(\psi)=0.060-0.204\psi$; multi-rung phasor sum** | Partially tested 2026-08-03 ($\delta n(\psi)$ confirmed; multi-rung superposition verified; linear + gated conversion null; closure-emission, closure-in-sum, cumulative, $\psi$-map structure, lattice-frame all null; energy pool pinned; closure-crossing flow read: pools near-static, $u\le1.5\%$, conversion flux outward $\le0.1\%$; 38-state baseline uniform) | **What sets the wake phase $\psi$ per rung** |
| 47 | Conditional axion chain (PQ cross-check) | Particle physics (haloscopes) | **IF PQ exists: $f_a$ at rung 34 ($9.57\times10^{11}$ GeV); $m_a \approx 6.0 \pm 0.3$ µeV ($n \approx 159.3$–$159.4$; no $\varphi$-anchor)** | Untested; framework predicts the null axion | **ADMX-class, 4–8 µeV** |
| 48 | Log-periodic polarization orientation | Synchrotron polarimetry | **PA($\nu\varphi^k$) = PA($\nu$) (mod $\pi$); period $\Delta(\ln\nu)=\ln\varphi\approx0.4812$ under the Hypothesized phase-to-rung map**; 90° flip at quarter-rung separation ($\nu_2/\nu_1=\varphi^{1/4}$); half-rung pair ($\nu_2/\nu_1=\sqrt\varphi$) predicts parallel PA | Tested 2026-08-06 (`experiments/demystifying_cosmos/pa_logperiodic_test.py`): NULL at face value—Crab mm-band PA constant (~138–142°; $\Delta\ln\nu=1.26=2.6$ rungs), 0/10 band pairs within 3σ, spiral excluded vs uniform-angle null ($p=0.77$) | **Tested—null; XL-Calibur / LEAP-class next** |
| 49 | Gaussian Hawking-spectrum deviation | Analogue horizons (fibre-optic, BEC) | **$\ln(\Delta N/N)$ linear in $\omega^2$, slope $-1/(\varphi^6\Lambda^2)$**; deviation reaches $e^{-\varphi^{-6}} \approx 0.95$ at the cap | Untested—framework-internal proof (σ-regulator); Nature 2026 analogue consistent with direct emission | **Nature-style fibre-optic spectra** |
| 50 | Spiral pitch tangent | Two-fluid winding dynamics | **Hypothesized coordinate-spiral rate-ratio claim: $\tan(\text{pitch})=\gamma/\Omega_S=\varphi^2=2.618$** (69.1°); both rates are φ-algebra-derived; wake reading $\ell_{n+1}/\Lambda_I$; matches none of the posted forks $\{0,0.0766,0.3063,0.1988\}$ | Measured 2026-08-07—dynamical realization rejected: measured winding rates do not realize $\varphi^2$ (9–11× off under every normalization; no convention within ±10%); the identity remains Derived arithmetic | **Tested—rejected (identity Derived)** |
| 51 | Bubble-shell ring ladder | Bubble simulation (two-fluid PDE) | **~10 matter ridges at $r_k=R\varphi^{-k}$** (successive matter-ring ratio $\varphi^{-1}=0.6180$ vs null $\varphi^{-1/2}=0.7862$), 9 void troughs at $R\varphi^{-(k+\frac12)}$, strict alternation, $n$-independent count | Hypothesized (PDE-testable; conditional on the radial-reading inference; null comparison: naive wake-sum zeros $\{0.191,0.573,0.809,0.955\}\cdot\ell_n$ lie outside a $\varphi$-ladder; dynamic realization test 2026-08-13 = **NO RINGS on all four arms** (conversion-only/diffusion/gravity-buoyancy/cs²-pressure) to $t=40$) | **Hypothesized—analytic probe `two-fluid/run_bubble_ring_probe.py`; dynamic probe `two-fluid/run_bubble_ring_dynamic_probe.py` = four-arm null** |
| 52 | Void radial ring profiles | Cosmic surveys (void stacking) | **Successive matter-ring ratio $\varphi^{-1}$ versus null $\varphi^{-1/2}$; first resolvable rungs near $0.618R$ and $0.382R$** | Pre-registered pipeline; planted-signal calibration is synthetic and is not an observation; real-galaxy stacking is pending because no verified per-void galaxy-position catalog or immutable run receipt is available | **Hypothesized—observational verdict pending** |
| 53 | Disk-gap $\varphi$-ladder | Protoplanetary disks (ALMA) | **Successive gap ratio $\varphi^{-1}$ versus null $\varphi^{-1/2}$, pooled across disks** (a conditional gas/condensation channel) | DSHARP acquisition and analysis scripts are present, but no fetched data, parsed table, or immutable run receipt is committed; no pooled verdict or significance is assigned; planet-carving remains an alternative | **Hypothesized—real-data test pending** |
| 54 | Exoplanet period-ratio $\varphi$-spacing | Multi-planet catalogs (Kepler/TESS) | **Adjacent $P_{\text{out}}/P_{\text{in}}$ at $\varphi$ plus Fibonacci convergents; a conditional detached-orbital/matter channel** | Kepler/TESS acquisition and analysis scripts are present, but no fetched catalog, parsed output, or immutable run receipt is committed; no observational verdict, count, significance, or detection-power claim is assigned | **Hypothesized—reproducible test pending** |

## 8. Conditional Boundary Anisotropy—Selected Edge Proxy

**Source:** `foundations/bubble-lattice-fabric.md` §4.2 and `foundations/bubble-edge-geometry.md` §§2.2, 9. The constructed condensation proxy has a **1.7072× directional edge-slope ratio only after selecting $\theta_{\mathrm{cond}}=0.45$**. That selection is a phenomenological map input, not a canonical/PDE output. No $C=0.45$ edge survives the fixed-step PDE endpoint, so the ratio is not a universal or parameter-free prediction of the canonical solver.

| Frontier | Observable | Cassi Prediction | Current Status | Detection Timeline |
|----------|-----------|------------------|----------------|-------------------|
| Cosmology (SDSS/DESI) | Void boundary density profile slope in axial vs. diagonal direction | **1.7072×** directional proxy steepness, conditional on $\theta_{\mathrm{cond}}=0.45$ | Fixed-step PDE endpoint has no $C=0.45$ edge; VAST/ZOBOV DR7 receipt is null (catalog §3 row) | **Existing surveys** |
| Biophysics (chakra) | Qi density gradient at chakra boundary | **1.7072×** directional proxy steepness, conditional on a measured or selected $\theta_{\mathrm{cond}}$ | Not yet tested; canonical $q$ requires a separately measured constitutive map | **Laboratory** |
| Anatomy (fascial planes) | Ultrasound elastography boundary stiffness ratio | **1.7072×** directional proxy anisotropy, conditional on a measured or selected $\theta_{\mathrm{cond}}$ | Not yet tested; canonical-field identification is not supplied | **Laboratory** |

## Notes

- **No canonical parameter-free prediction is assigned.** The ratio is a geometric proxy conditional on the selected threshold and the stated coordinate construction; the Fit-Status Ledger records anchored quantities (`parameter-inventory.md` §10).


- **The same $\varphi$ governs every sector:** the weak mixing angle $\sin^2\theta_W = \varphi^{-3}$,
  the Qi-gravity coupling $\xi = \varphi^6$, the DM/baryon ratio $\varphi^3 \approx 4.236$ (21% open tension),
  the dark energy equation of state $w_0 = -0.87$, the baryon asymmetry $\eta$,
  and the inflationary spectral index $n_s = 1 - 2\varphi^{-1}/N_e = 0.9691$.
  Their tiers differ: $w_0$ is **Calibrated** (ledger row 496); $\xi$'s rung
  identity, $\eta$'s exponent, $\varphi^3$, $n_s$'s $N_e$, and $r$ are
  **Mapped** or conditional (ledger rows 498, 481, 502, 501, 495); only the
  $w = 5$ and gap forms carry a closed framework derivation; the $\sin^2\theta_W$
  value is an exact $\varphi$ identity with an asserted coupling boundary. The
  missing normalization bridge is documented in
  `standard-model/su2-gauge-extension.md` §3.2.1; the full VEV mass matrix
  retains the standard photon null direction.

- **RG running is not fitting.** The running of the couplings between the
  φ-boundary and $m_Z$ is the Standard Model renormalization group, computed
  in full by `computations/sm_radiative_corrections.py`. It does **not**
  erase the φ-anchored residuals: $\sin^2\theta_W = \varphi^{-3}$ is exact at
  $\mu_* \approx 233$ GeV and +2.1% at $m_Z$ (the angle runs *upward* with
  energy), $\alpha_s(m_Z)$ comes out $2.0\times$ low, and $\alpha_1$,
  $\alpha_2$, $\alpha_{\text{em}}$ come out ~25% weak. Those residuals are the
  theory's testable content, not adjustable parameters.

- **Scope of current tests:** The Cassi framework has 7/13 dedicated experimental
  tests PASSing (BBN, BAO, BTFR, neutron stars, stellar astrophysics, solar system,
  $\alpha$-decay), 3 TENSION (ISW, weak lensing, PTA—single-scale screening
  limitation), 2 NULL (identical to $\Lambda$CDM at the tested epoch), and
  1 PREDICTION (Casimir). The structural dark-energy values sit $2\sigma$
  ($w_0$) and $2.7\sigma$ ($w_a$) from DESI DR2—a tension, not a success.

- **Deviations from SM expectations are falsifiable**—not adjustable. If FCC-ee
  measures $m_W/m_Z = 0.881 \pm 0.0001$, the Cassi framework is excluded
  (the predicted value is 0.878 after radiative corrections).

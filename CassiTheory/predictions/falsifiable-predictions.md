# Cassi Falsifiable Predictions

## Status: Reference—September 2026

The catalog separates parameter-free structural predictions from predictions that depend on optional extensions, declared inputs, Mapped placements, or Calibrated normalizations. The parameter-free structural subset is derived from the golden ratio $\varphi = (1+\sqrt{5})/2$ and the canonical two-fluid PDE under its stated assumptions. Framework couplings are often expressed as $\varphi$-powers, while observationally anchored quantities carry the Calibrated or Mapped flag with a Fit-Status Ledger row (`parameter-inventory.md` §10). Conditional, Hypothesized, Mapped, and Calibrated flags govern how each row may be read.

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
| $\sigma_8$ | $0.811$ | **+0.3% ± 0.5 pp (P-A, measured window $z \in [100, 61]$)**—the window-integrated mixture of the measured per-cell μ(x,t) histories on the ΛCDM background (`cassi-toe-rewrite-briefs/spiral-gravity/45-sigma8-mixture.md`; the window's content is the q-history 0.866 → 0.795, not the endpoint; mixture = mean-field to 0.00 pp); the P-C pointwise-chord reading (flagged): **+24.8% ± 16.3 pp over the measured window** (R_mix = 1.2483, every cell ends with R > 1), then **−95.7% ± 2.4 pp over the continuation $z \in [61, 0]$** (R_mix = 0.0430 full-window; the continuation is measured from the per-cell t = 40 state—the freeze is structural in the continuation: Re p = −0.25 for every μ < −1/24, the common envelope decay, and all 262144 cells end R < 1 through z → 0; N=128 confirms both phases—+24.83% / −95.9%, resolution-converged to 4 decimals; `cassi-toe-rewrite-briefs/spiral-gravity/53-post-freeze-continuation.md`, `cassi-toe-rewrite-briefs/spiral-gravity/54-n128-mixture.md`); the settlement family (the stabilized closure's regime-integrated −16.6% (R = 0.834), the band-state mean-field −15.2%, the full-window hold −11.2%) is the reference; the pipeline's measured rows: total −20.5% and mechanism +29.7% (G_eff = 1.297, doctrine r₀, linear-P(k) normalization, resolution-converged N=64/128; r₀-dependent: +29.4% at the derived r₀ = 0.0472); the μ normalization remains Mapped | LSST discriminant—the computed values, not a target |
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
| GW speed $c_g/c$ | $= 1$ | **Undetermined:** the optional Qi-gravity extension has no covariant wave equation | No Cassi propagation-speed prediction yet |
| GW polarization | $+, \times$ | **Optional extension:** an additional breathing mode is proposed | Hypothesized; requires a metric-perturbation derivation |
| GW strain in halos | GR | **Sensitivity scenario:** $h/h_{\mathrm{GR}}=1+(\varphi^6-1)q$ in the optional saturation-chord branch | For a declared $\varepsilon_h=0.10$, the algebra gives $q_{\text{binary}}<5.9\times10^{-3}$ (`experiments/cassi_physics/cassi_gw_q_bound.py`); the precision input lacks an event-level citation and the branch lacks a waveform derivation |
| BH shadow M87$^*$ | $\sim 5M$ | **GR limit ($q = 0$): $3\sqrt{3}M$** | No Cassi metric—prediction not yet derived |
| Mercury perihelion | $43$ arcsec/cy | **$42.98$ arcsec/cy in an optional metric/force closure** | Conditional GR-consistency receipt; the canonical branch supplies neither attraction nor a metric |
| $|q|$ at 0.39 AU | $0$ | **Undetermined:** no canonical Solar-System $q(r)$ profile | The quoted $1.1\times10^{-6}$ bound has no registered derivation |
| PPN $\beta, \gamma$ | $1, 1$ | **$1+\mathcal{O}(\xi q^2)$ in an optional metric/sign closure** | Derived conditional; no Cassi PPN constraint yet |
| Pioneer anomaly | $0$ | **No Cassi prediction registered** | Thermal recoil accounts for the measured acceleration; catalog claim rejected |
| NS maximum mass | $\sim 2.0 M_\odot$ | **Undetermined:** no Cassi equation-of-state/TOV closure | Not predicted |
| NS $M$–$R$ relation | GR | **Undetermined:** no Cassi equation-of-state/TOV closure | Not predicted |
| Dwarf-galaxy mass discrepancy | GR plus unseen mass | **Nominal fixed-$M_\star/L_V=1$ proxy screen:** the optional pure-$G$ endpoint $\varphi^3=4.2361$ is exceeded by 7/8 central ratios and 6/8 lower propagated $\sigma_{\text{los}}/R_e$ bounds | Diagnostic only; stellar-mass posteriors, membership/binary models, equilibrium cuts, and a population likelihood remain open |

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

**Source:** `foundations/wake-geometry.md` §1(a)–(c). The identity is exact on the documented anchors; the wake pair never phase-locks because $\varphi$ is irrational (de-resonance in the wave structure), so the composite period $\ell_{n+1}$ is the only closed scale.

**Prediction 44 (staggered checkerboard template):** For supplied adjacent-rung wake carriers, envelope antinodes lie at $m\,\ell_{n+1}$, nodes lie at $(m+\frac{1}{2})\ell_{n+1}$, adjacent demodulated antinodes have correlation $-1$, and next-nearest antinodes have correlation $+1$. The structural locations were PDE-verified 2026-08-06 (`two-fluid/run_wake_structural_probes.py`): nodes to 0.0023 grid precision and antinodes to 0.00015. The 2026-08-27 phase-gap certificate verifies the exact parity, node, and unequal-amplitude contrast laws. Assigning physical bubbles and voids to those locations remains Hypothesized because the current dynamics supplies no node-to-condensation map.

**Source:** `foundations/wake-geometry.md` §2, `foundations/bubble-lattice-fabric.md`, and `field-experience/phase-staggered-scale-gap-report.md`. The beat identity is conditional on the supplied carriers; ordinary radial beating has additive spacing.

**Sharpening (wake-force, 2026-08-03):** the wake-phase gradient force has harmonic amplitude ratio $F_2/F_1 = 1/\varphi \approx 0.6180$ (exact) and phase-gradient ratio $(1+\varphi)/(\varphi-1) = \varphi^3 = 4.2361$ (exact—the formal fixed-composition endpoint factor of the optional $G_{\mathrm{eff}}/G$ coupling map); the envelope period is $\ell_{n+1}$ (constructive at $m\ell_{n+1}$, destructive at half-rungs). PDE-verified 2026-08-06: measured $F_2/F_1 = 0.617621$ vs $1/\varphi = 0.618034$ (−0.07%) with the cross-ratio $\varphi^3$ exact; the sharpening requires the documented $\Pi\nabla\Phi$ force form (`two-fluid/run_wake_structural_probes.py`).

**Prediction 45 (closure-ladder imprint):** The closure ladder of the golden-angle spiral (levels 5, 13, 34, 89, 233, …) imprints on the cascade: currently-dark rungs near closure levels should host physical structure. First test (2026-08-03, mass scan $n = \log_\varphi(M_{\text{Pl}}/m)$): rung 89 hosts the J/ψ ($n = 88.98$, 1.0%—the first mass hit on a closure level); rung 96 hosts the muon ($n = 96.000$, 0.01%—the sharpest absolute placement in the framework, wake-anchored); rung 34 has no established anchor (the Peccei-Quinn window top $\sim 10^{12}$ GeV is the only candidate). Existing rung hits $26 = 2\times13$ and $285 = 5\times57$. **Uniform-baseline framing:** the sharp placements are not statistically distinguished from the uniform null—42% of the 38-state catalog lies within 0.10 rungs vs 40% uniform (mean $s$ 0.118 vs 0.125), the electron's placement sits at $p = 0.32$, and the a-priori anchors give $P = 18.7\%$ (23; 24 E1).

**Source:** `foundations/wake-geometry.md` §3(e), §5 (Y3); `foundations/deriving-remaining-gaps.md` §4.2 (catalog rows 89 and 96).

**Prediction 46 (rung-offset mechanism):** The two-fluid interference envelope permits observables at its special positions—peaks at $u = 1+\log_\varphi m$ (the first is an integer rung) and zeros at $u = 1+\log_\varphi(m+\tfrac12)$ (the first at $-0.440$)—in the coherent limit; the residual coordinate offset $\delta n$ is the Hypothesized phase-to-rung image of the local two-fluid phase lag and vanishes as coherence $q\to1$. Sector edges (lightest states: e, π, $\Lambda_{\text{QCD}}$, p, n, d) sit at the crossing positions; interior states (μ, J/ψ, D, Σ, Z) at integer rungs. The 38-state scan is statistically uniform (null baseline); the PDE probe measures the raw phase-lag curve $\delta n(\psi)=0.060-0.204\,\psi$ rungs for the two-bubble standing pattern, with linear and gated conversion.
The 2026-08-27 driven-wave campaign sharpens this boundary: the tuned second-order channel pair forms additively spaced phase layers, while its generic-frequency control does not select the $\varphi$ wavenumber ratio. This does not supply a multiplicative rung map or change the 38-state null.

**Source:** `foundations/rung-offset-mechanism.md` §§1–5; `foundations/wake-geometry.md` §2 (envelope), §3(e) (mass scan); `principles/de-resonance-principle.md` §2 (correction posture).

**Prediction 47 (conditional axion chain):** IF the standard Peccei-Quinn solution exists in nature—the framework's strong-CP resolution requires no axion, `foundations/strong-cp-derivation.md` §3—THEN $f_a$ anchors the dark closure rung 34 ($M_{34} = M_{\text{Pl}}\varphi^{-34} \approx 9.57\times10^{11}$ GeV, the top of the allowed PQ window) and $m_a = f_\pi m_\pi\sqrt{z}/(1+z)/f_a \approx 6.0 \pm 0.3$ µeV ($n \approx 159.3$–$159.4$), testable by ADMX-class haloscopes in the 4–8 µeV band. $m_a$ carries no $\varphi$-anchor of its own—0.6–0.7 rungs from the chakra-node rung 160 (4.45 µeV) and 0.1–0.2 rungs from half-rung 159.5 (5.66 µeV), a miss either way. Status: Hypothesized (conditional on standard PQ existing); the framework's own prediction is the null—no axion exists (`standard-model/cp-violation.md` §5.3).

**Source:** `foundations/wake-geometry.md` §3(e); `foundations/strong-cp-derivation.md` §3 (no-axion resolution). $f_a = M_{34}$ by the rung-34 anchor; $m_a$ from the standard PQ relation $m_a f_a = f_\pi m_\pi\sqrt{z}/(1+z)$; $n(m_a) = \log_\varphi(M_{\text{Pl}}/m_a)$.

**Prediction 48 (log-periodic polarization orientation):** In pulsar wind nebulae and other synchrotron sources, the polarization position angle is log-periodic in photon energy—$\text{PA}(\nu\varphi^k)=\text{PA}(\nu)$ (mod $\pi$)—under a Hypothesized phase-to-rung coordinate map that assigns one full $\Theta_{\rm pol}$ turn per cascade rung of emitting-particle energy, $\Theta_{\rm pol}(\nu)=\Theta_{\rm pol,0}+(2\pi/\ln\varphi)\ln(\nu/\nu_0)$. A band pair at quarter-rung separation ($\nu_2/\nu_1=\varphi^{1/4}$) should show PA rotated by 90°; a half-rung pair ($\nu_2/\nu_1=\sqrt\varphi$) returns PA unchanged (mod $\pi$)—parallel, since the map gives $\Delta\Theta_{\rm pol}=\pi$ at half-rung. Test: PA in ≥3 bands spanning $\Delta(\ln\nu)\geq\ln\varphi\approx0.4812$—radio (ATCA), X-ray (IXPE), and hard-X/γ-ray polarimetry. |

**Source:** `demystifying-the-cosmos/PSR-J1101-6101.md` §5 (IXPE Lighthouse Nebula: radio ⊥ vs X-ray ∥, >99% CL field ∥ flow, high PD); `foundations/spin-fibonacci-spiral.md` §1, §5 (Hypothesized phase-to-rung coordinate map; form-factor log-periodicity). Same period as the cosmological $P(k)$ modulation (prediction 5)—same $\varphi$, different probe. |

**Prediction 49 (Gaussian Hawking-spectrum deviation):** The $\sigma$-regularized free propagator suggests a Gaussian high-frequency suppression ansatz for horizon-analogue spectra: $\Delta N_k/N_k^{\text{thermal}} = e^{-(\omega/\Lambda)^2/\varphi^6}$, equivalently $\ln(\Delta N_k/N_k)$ linear in $\omega^2$ with slope $-1/(\varphi^6\Lambda^2)$. This is a **conditional transfer ansatz**: the coefficient $\varphi^6 \approx 17.944$ is the rung-3 Yang/Yin coupling, but $\Lambda$ is an independently fixed UV cutoff (for the gravitational case the natural scale is the $\sigma$-regulator $\Lambda = \varphi^3 M_{\text{Pl}} \approx 5.17\times10^{19}$ GeV, with no energy cap derived), and the mapping from the flat-space propagator to a curved-horizon Hawking flux is not specified. The Nature fibre-optic analogue (Procopio et al., *Nature* **655**, 336–341 (2026)) is an optical backreaction test-bed only—**not** evidence for the Cassi Gaussian form. **Status: not a derived gravity prediction until the curved-horizon transfer is specified.**

**Source:** `gravity/quantum-gravity.md` §7 (free-propagator analysis; S-matrix/Page curve/capacity/no-firewall all open—no curved-horizon transfer derived); `open-questions-cassi-answers.md` G2; the Nature fibre-optic analogue study (July 2026)—optical test-bed only, not a gravitational measurement; script `experiments/cassi_physics/cassi_hawking_spectrum.py`.

**Prediction 50 (spiral pitch tangent):** The coordinate-spiral ansatz proposes the radial/azimuthal rate ratio $\tan(\text{pitch})=\gamma/\Omega_S=\varphi^2=2.618$ (pitch angle 69.1°), with $\gamma=\lambda(1-q_0)(1+\varphi)=\lambda/3$ and $\Omega_S=\lambda(1-q_0)=\lambda\varphi^{-2}/3=H_{\text{empty}}$. The $\varphi^2$ identity is Derived arithmetic; its realization as a dynamical rate ratio is Hypothesized and tested separately. The wake-geometry reading is $\gamma/\Omega_S=\ell_{n+1}/\Lambda_I$ in Yin-wake units. The claim matches none of the posted forks $\{0,0.0766,0.3063,0.1988\}$ (08's ratified fourth value included)—a new discriminator (69.1° vs 0°, 4.38°, 17.03°, 11.24°). Measured 2026-08-07—the dynamical realization is rejected: measured winding rates do not realize the $\varphi^2$ ratio (9–11× off under every normalization): $|\omega|/\Omega_S=11.04$ (measured $|\omega|=0.0281$ vs derived $\Omega_S=2.55\times10^{-3}$) and $\gamma_{\text{env}}=7.4\times10^{-4}$ vs derived $\gamma=6.67\times10^{-3}$ (9.0× below); no stated convention lands within ±10% of 2.618 (closest: geometric turns/rung 2.909, +11.1%, and direct $|a_\theta/a_r|=2.986$, +14.0%—both in the $\varepsilon\to0$ window, which is not a clean damped rotator); $dn_S=\Omega_S/2\pi$ sits 11.04× below the measured winding rate under all four rung normalizations (the measured 0.323 turns/rung is the generator's bare 0.382 friction-reduced, not the re-read clock). The identity remains Derived arithmetic; the dynamical realization is refuted by the winding and probe data (winding record: §4 fork measurement; probe record: `foundations/rung-offset-mechanism.md`). |
**Source:** `foundations/spiral-dynamics.md` §2.2 (coordinate-spiral pitch ansatz: $\gamma=\lambda/3$, $\Omega_S=\lambda\varphi^{-2}/3=H_{\text{empty}}$, gate value $(1-q_0)=\varphi^{-2}/3$); `foundations/wake-geometry.md` §1(c) (composite closure in Yin-wake units, $\ell_{n+1}/\Lambda_I=\varphi^2$). |

**Prediction 51 (bubble-shell ring ladder)—REJECT for tested dynamical realization:** The registered target is **~10 matter ridges** at radii $r_k=R\,\varphi^{-k}$, interleaved with 9 void troughs at $R\,\varphi^{-(k+\frac12)}$, strict matter/void alternation, and an $n$-independent count. The successive matter-ring ratio $\varphi^{-1}=0.6180$ must be distinguished from the null interleaved-ridge ratio $\varphi^{-1/2}=0.7862$. The coordinate template $\alpha=\pi\log_\varphi(r/\ell_n)$ remains a Hypothesized radial-reading inference; its tested endogenous realization is `REJECT`.

The pre-registered first-order dynamic probe finds **NO RINGS** on all four spatial-coupling arms at every epoch to $t=40$ (0 matter maxima outside the 4-cell core). The decisive undriven second-order space-sim probe also finds **NO RIDGES**: a transient shell plus one interior ridge at ratio 0.545 at $t=24$ dissipates by $t=40$, while the detector self-test recovers a planted $\varphi$ ladder. The 2026-08-27 driven-wave campaign does not rescue the target: its harmonic two-channel realization has additive spacing $2\pi/|k_\rho-k_\epsilon|$, its generic control gives $k_\rho/k_\epsilon=1.311855471$, and uniform phase staggering remains gapless. A supplied log-radius coordinate can place the target radii by construction; no tested Cassi dynamics generates that coordinate.

**Source:** `foundations/bubble-edge-geometry.md` §3; `two-fluid/run_bubble_ring_probe.py`; pre-registered `two-fluid/run_bubble_ring_dynamic_probe.py`; `diag_bubble_rings.gd` in the owner's space-sim repo; and `field-experience/phase-staggered-scale-gap-report.md`. A new canonical or second-order mechanism requires a fresh preregistration before this terminal verdict can change.

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


**Prediction 54 (exoplanet period-ratio $\varphi$-spacing, real-data audit;
channel reading):** a conditional disk-to-orbit preservation map gives the
specific detached-orbit target
$P_{\text{out}}/P_{\text{in}}=(a_{\text{out}}/a_{\text{in}})^{3/2}
=\varphi^{3/2}=2.058171$. The registered classifier tests an equal-width
window around this value against a folded-window density reference and
non-$\varphi$ resonance controls. The explicitly confirmed NASA Exoplanet
Archive primary Kepler sample contains 476 multi-planet systems, 1,212
planets, 736 adjacent period ratios, and 562 ratios inside the fixed support
$[1,3]$. The headline window contains 46 ratios and has descriptive
standardized window-density score $z_{\rm win}=1.087$, so the formal
classifier result is **INDETERMINATE**. The K2/TESS cross-check gives
$z_{\rm win}=2.120$, but it is secondary and the score is neither a sampling
significance nor a mechanism-specific likelihood ratio.

The headline interval overlaps the registered 2:1 interval across $41.8\%$
of its width and occupies the known excess immediately wide of the 2:1
mean-motion resonance. The catalog therefore supplies no mechanism-specific
evidence for a $\varphi$ field signal. Under the channel principle
(`foundations/qi-as-spatial-spacing-signal.md` §4), disk gas and condensates
are the coherence-coupled channel, while detached orbital bodies need not
preserve the disk ladder. The disk-to-orbit transmission law remains
unspecified.

**Tier: Hypothesized.** The scientific verdict is **INCONCLUSIVE** for Cassi,
and the current broad window is rejected as a clean discriminator from
standard orbital dynamics. Prediction 53's disk-gap test remains a separate
pending channel and contributes no result to this verdict.

**Source:** `hypotheses/exoplanet-phi-spacing.md` §3 and §8;
`experiments/kepler_phi_ratios/kepler-period-ratio-report.md` (data receipt,
counts, diagnostics, and verdict);
`experiments/kepler_phi_ratios/acquire_kepler_catalog.py` (NASA Exoplanet
Archive acquisition, disposition validation, parsing, and SHA-256 manifests);
`experiments/kepler_phi_ratios/run_phi_ratios.py` (registered classifier,
folded-window density reference, sensitivity calculation, and diagnostic
resonance-overlap partition);
`principles/de-resonance-principle.md` (orbital resonance context);
Prediction 51 (ratio-test and null discipline) and Predictions 45/46
(folded-window reference discipline).

**Prediction 55 (q-gated imbalance drift-and-diffusivity curve):** In the selected $q$-gated open-system completion of the physical-becoming hierarchy (`foundations/physical-becoming-hierarchy.md` §§4.4–4.5), at fixed total density $\rho=\varphi$ the imbalance obeys $\varepsilon=E_Y-\varphi E_I\in[-\varphi^2,\varphi]$ (the positivity wedge $E_Y,E_I\ge0$). The normalized deterministic drift curve and the normalized stochastic diffusivity each scale with the conversion rate $c=\lambda(1-q)$ and predict the same no-free-shape curve
$$
R_Q(\varepsilon)=\frac{3\bigl(1+\varphi^2\varepsilon^2\bigr)}{3+\varepsilon^2},
\qquad
\varepsilon=E_Y-\varphi E_I,\quad
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2}\Big|_{\rho=\varphi}.
$$
Because $c(\varepsilon)/c(0)$ reduces to the form above, $R_Q(\varepsilon)$ is the predicted normalized drift curve (deterministic, no bath required) and, under the Gaussian Markov completion, also the normalized diffusivity/covariance curve (bath-conditional). The formal $|\varepsilon|\to\infty$ asymptote $3\varphi^2\approx7.854$ is unreachable inside the wedge; the accessible range is $R_Q\in[1,\,5.767427]$, with $R_Q(0)=1$, $R_Q(-\varphi^2)=5.767427$ at the $E_Y\!\to\!0$ boundary, and $R_Q(\varphi)=4.194048$ at the $E_I\!\to\!0$ boundary. Probes should sample interior points that exclude reflecting-boundary effects.
This is a three-arm discriminator:
- **Q (q-gated arm):** the selected $q$-gated conversion $c=\lambda(1-q)$ makes the deterministic drift coefficient $(1+\varphi)c$ proportional to $c$; normalizing it by its $\varepsilon=0$ value gives the drift curve $R_Q(\varepsilon)=c(\varepsilon)/c(0)$. In the Gaussian Markov completion the same factor normalizes the diffusivity/covariance—but that diffusivity reading is bath-conditional (see tier), whereas the drift curve is not.
- **C (constant-mobility control):** a matched arm with fixed mobility, flat ($R_C=1$) by construction.
- **N (no-conversion arm):** $c=0$, giving zero conversion drift and zero conversion diffusivity ($R_N=0$).

The three arms share the same fixed-$\rho$ preparation, stochastic convention, and boundary rule; only the conversion law differs. The deterministic Q-arm drift curve versus the flat C baseline is a no-free-shape discriminator of the $q$-gate that requires no bath.

**Secondary conditional checks** (reported only if the primary Q/C/N discriminator resolves): the rank-one Yang/Yin increment covariance $\mathbb B_{\mathrm{TF}}\mathbb B_{\mathrm{TF}}^{\mathsf T}=2k_{\mathrm B}T_{\mathrm{bath}}\mathbb R_{\mathrm{TF}}$ of (OS2) (equal-and-opposite channel noise, $(1,1)\mathbb B_{\mathrm{TF}}=0$, $\rho$ exactly conserved; the physical FDT carries the bath temperature $T_{\mathrm{bath}}$ since $\mathbb B_{\mathrm{TF}}$ is not rescaled) and the drift-to-diffusivity ratio satisfying the fluctuation–dissipation relation (OS1). Both are conditional on the same bath/convention assumptions and do not independently rescue a failed primary discriminator.

**Tier: Hypothesized/conditional (split).** The deterministic Q-arm drift curve $R_Q(\varepsilon)$ is conditional only on the deterministic $q$-gated PDE (the (OS3) drift at fixed $\rho=\varphi$), the positivity wedge $\varepsilon\in[-\varphi^2,\varphi]$, and a fixed boundary rule (minimal choice: reflecting, zero-normal-flux); it requires **no** bath and is the most robust arm of the test. The diffusivity/covariance reading of the same curve and the secondary checks (rank-one increment covariance (OS2), fluctuation–dissipation ratio (OS1)) are additionally conditional on (i) a Gaussian Markov bath for the imbalance coordinate, (ii) a fixed stochastic convention (Itô/Stratonovich) recorded before the probe, and (iii) the absence of independent bath-scale blockers (finite bath correlation time, memory-kernel non-Markovianity, and substrate preparation fidelity) that would mask the $\varepsilon$-dependence. The Gaussian Markov bath and noise are a modeling choice; they are **not** derived from the canonical scalar action and are not claimed to be (the closed action fixes neither the dissipative tensor, the $(1-q)$ rate, the bath spectrum, nor the noise amplitude).

**Source:** `foundations/physical-becoming-hierarchy.md` §§4.4–4.5 ((OS1)–(OS6)); `computations/verify_physical_becoming_reduction.py` (exact conversion, mobility, covariance null mode, and response eigenmodes).

**Prediction 56 (minimal-singlet fluctuation spectrum):** In the minimal $V_{\mathrm{vac}}$ of the two-singlet EFT (`foundations/physical-becoming-hierarchy.md` §7.3, (EFT6c)–(EFT6d)), with canonical kinetic terms, negligible portal and curvature contributions, and the $(+,+)$ vacuum representative, the Hessian diagonalizes into two orthonormal modes
$$
h_R:=\frac{\sqrt{\varphi}\,\delta\chi_Y+\delta\chi_I}{\varphi},
\qquad
h_A:=\frac{\delta\chi_Y-\sqrt{\varphi}\,\delta\chi_I}{\varphi},
\qquad
h_R\cdot h_A=0,
$$
with masses $m_R^2=2g_4\rho_\chi=2\mu_\chi^2$ and $m_A^2=4\varphi\lambda_A\rho_\chi$ (here $\rho_\chi=\mu_\chi^2/g_4$ and $\mu_\chi^2$ is the free tachyonic coefficient), giving the ratio $m_A^2/m_R^2=2\varphi\lambda_A/g_4$. The radial mode makes an angle $\theta_R$ with the $\delta\chi_Y$ axis satisfying $|\tan\theta_R|=\varphi^{-1/2}\approx0.786151$, hence $\theta_R\approx38.1727^\circ$. The other $\mathbb Z_{2,Y}\times\mathbb Z_{2,I}$ sign-related vacua flip the eigenvector components but preserve the masses and $|\tan\theta_R|$.

**Tier: Derived conditional / Hypothesized.** Derived conditional within the stated minimal-vacuum ansatz at a declared matching scale: $g_4$, $\lambda_A$, and $\mu_\chi$ remain free, so the result fixes neither absolute scalar masses nor a universal mass ratio outside this restricted action and its negligible-portal/curvature limit. The restricted $\varphi$ surface is **not** RG invariant—(RG3) shows the flow leaves it immediately for $\lambda_A>0$, so the spectrum cannot be advertised as scale-independent without an explicit protecting symmetry or independently demonstrated fixed manifold ((RG3); §7.3). Physical realization (that the minimal vacuum with canonical kinetics and negligible portal/curvature is the realized one) is Hypothesized.

**Source:** `foundations/physical-becoming-hierarchy.md` §7.3 ((EFT6c)–(EFT6d), (RG3)); `computations/verify_physical_becoming_eft.py` (vacuum, Hessian eigenmodes, and mass spectrum).



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
| 15 | Dwarf-galaxy pure-$G$ endpoint | Galactic | **Nominal fixed-$M_\star/L_V=1$ proxy screen**—7/8 central $v_{\text{obs}}/v_{\text{Newt}}$ ratios exceed $\varphi^3=4.2361$; 6/8 lower propagated $\sigma_{\text{los}}/R_e$ bounds exceed it | The endpoint belongs to the optional fixed-composition branch; object-level likelihoods and stellar-population systematics remain open, and no Cassi/MOND verdict is assigned | **Conditional catalog screen** |
| 16 | BH shadow M87$^*$ | EHT | **GR limit ($q = 0$): $3\sqrt{3}M \approx 5.2M$** | no Cassi metric exists—shadow prediction not yet derived | **Hypothesized (untested)** |
| 17 | GW strain in halos | LIGO | **Optional sensitivity scenario:** $h/h_{\mathrm{GR}}=1+(\varphi^6-1)q$ | A declared $\varepsilon_h=0.10$ gives $q_{\text{binary}}<5.9\times10^{-3}$ algebraically (`experiments/cassi_physics/cassi_gw_q_bound.py`); the input is not event-level sourced and no waveform closure exists | **Hypothesized** |
| 18 | Pioneer anomaly | Solar system | **No Cassi prediction registered** | Thermal recoil accounts for the measured acceleration | **Rejected** |
| 19 | Mercury perihelion | MESSENGER | **$42.98$ arcsec/cy in an optional metric/force closure** | Conditional reproduction of the GR value; no canonical metric | **Derived conditional** |
| 20 | $0\nu\beta\beta$ decay | nEXO | **$m_{\nu_e} \sim 0.01$–$0.05$ eV** | nEXO reach $\sim 0.01$ eV | **2030s** |
| 21 | DM direct detection | LZ/XENON | **Null** (field condensate) | All experiments null | **Already consistent** |
| 22 | Casimir force | Lab | **No registered Cassi prediction or likelihood** | The quoted $q<0.02$ bound has no source derivation | **Not predicted** |
| 23 | Neutron star $M$–$R$ | NICER | **No Cassi equation-of-state/TOV closure** | Quantitative relation undetermined | **Not predicted** |
| 24 | $m_t / v_0$ | LHC/top | **0.618** ($\varphi^{-1}$) | Measured $0.703$, $12\%$ gap | **Ongoing** |
| 25 | $m_H$ (Higgs mass) | LHC | **input** ($\lambda = 0.1294$; $\lambda_\varphi$ gives 35 GeV) | Measured $125.2$ GeV | **Not predicted** |
| 26 | $\alpha_{\text{GUT}}$ | GUT | **$\varphi^{-3}/(4\pi) \approx 1/53$** | No SM intersection ($\alpha_1=\alpha_2$ at $10^{13}$, $\alpha^{-1}\approx 42$); needs $\Delta b = 1.70$ | **Proton decay** |
| 27 | BAO scales ($\alpha_\perp, \alpha_\parallel$) | DESI | **$\sim 3\%$ shift from $\Lambda$CDM** | Matches DESI DR2 | **Already tested** |
| 28 | BTFR normalization | Galactic | **$M_b \propto v_f^4$**, $A \propto \varphi^{-1}$ | $\chi^2/\text{dof} = 0.26$ | **Already confirmed** |
| 29 | GW polarization | LIGO | **Optional extension proposes $+$, $\times$, and a breathing mode** | No covariant perturbation derivation | **Hypothesized** |
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
| 44 | Staggered checkerboard envelope | Supplied-wave structure | **Antinodes at $m\ell_{n+1}$, nodes at $(m+\frac{1}{2})\ell_{n+1}$; adjacent/next-nearest demodulated parity $-1/+1$** | Structural locations PDE-verified 2026-08-06; exact parity, nodes, and unequal-amplitude contrast verified 2026-08-27. Physical bubble/void condensation map remains Hypothesized | **Supplied-wave structure verified; constitutive map open** |
| 45 | Closure-ladder mass placements | Particle physics | **Rung 89: J/ψ ($n = 88.98$, 1.0%); rung 96: μ ($n = 96.000$, 0.01%); rung 34 open** | Partially tested 2026-08-03 | **Catalog; rung 34 open; the sharp placements are not statistically distinguished from the uniform null (42% vs 40%; e $p = 0.32$; a-priori anchors $P = 18.7\%$—23/24)** |
| 46 | Rung-offset mechanism | Particle physics + PDE | **Envelope positions $1+\log_\varphi m$ / $1+\log_\varphi(m+\tfrac12)$; $\delta n$ is a phase-lag coordinate under a Hypothesized map, $\delta n(\psi)=0.060-0.204\psi$; multi-rung phasor sum** | Partially tested 2026-08-03: phase-lag curve and superposition verified; 38-state baseline uniform. The 2026-08-27 driven-wave control forms additive layers and supplies no endogenous $\varphi$ selector or multiplicative rung map | **What sets the wake phase $\psi$ and scale map per rung** |
| 47 | Conditional axion chain (PQ cross-check) | Particle physics (haloscopes) | **IF PQ exists: $f_a$ at rung 34 ($9.57\times10^{11}$ GeV); $m_a \approx 6.0 \pm 0.3$ µeV ($n \approx 159.3$–$159.4$; no $\varphi$-anchor)** | Untested; framework predicts the null axion | **ADMX-class, 4–8 µeV** |
| 48 | Log-periodic polarization orientation | Synchrotron polarimetry | **PA($\nu\varphi^k$) = PA($\nu$) (mod $\pi$); period $\Delta(\ln\nu)=\ln\varphi\approx0.4812$ under the Hypothesized phase-to-rung map**; 90° flip at quarter-rung separation ($\nu_2/\nu_1=\varphi^{1/4}$); half-rung pair ($\nu_2/\nu_1=\sqrt\varphi$) predicts parallel PA | Tested 2026-08-06 (`experiments/demystifying_cosmos/pa_logperiodic_test.py`): NULL at face value—Crab mm-band PA constant (~138–142°; $\Delta\ln\nu=1.26=2.6$ rungs), 0/10 band pairs within 3σ, spiral excluded vs uniform-angle null ($p=0.77$) | **Tested—null; XL-Calibur / LEAP-class next** |
| 49 | Gaussian Hawking-spectrum deviation (conditional transfer ansatz) | Analogue horizons (fibre-optic, BEC) | **$\ln(\Delta N/N)$ linear in $\omega^2$, slope $-1/(\varphi^6\Lambda^2)$**; $\Lambda$ independently fixed, no energy cap | Not a derived gravity prediction until curved-horizon transfer specified; Nature 2026 analogue an optical test-bed only (not evidence for the Cassi Gaussian form) | **Analogue-horizon spectra** |
| 50 | Spiral pitch tangent | Two-fluid winding dynamics | **Hypothesized coordinate-spiral rate-ratio claim: $\tan(\text{pitch})=\gamma/\Omega_S=\varphi^2=2.618$** (69.1°); both rates are φ-algebra-derived; wake reading $\ell_{n+1}/\Lambda_I$; matches none of the posted forks $\{0,0.0766,0.3063,0.1988\}$ | Measured 2026-08-07—dynamical realization rejected: measured winding rates do not realize $\varphi^2$ (9–11× off under every normalization; no convention within ±10%); the identity remains Derived arithmetic | **Tested—rejected (identity Derived)** |
| 51 | Bubble-shell ring ladder | Bubble simulation (two-fluid PDE) | **~10 matter ridges at $r_k=R\varphi^{-k}$** (successive matter-ring ratio $\varphi^{-1}=0.6180$ vs null $\varphi^{-1/2}=0.7862$), 9 void troughs at $R\varphi^{-(k+\frac12)}$, strict alternation, $n$-independent count | **REJECT tested dynamical realization:** first-order four-arm probe = `NO RINGS`; undriven second-order probe = `NO RIDGES`; 2026-08-27 driven-wave control gives additive phase layers, generic ratio $1.311855471$, and a phase-only zero gap. The log-radius coordinate remains a Hypothesized supplied template | **Tested—REJECT; new mechanism requires fresh preregistration** |
| 52 | Void radial ring profiles | Cosmic surveys (void stacking) | **Successive matter-ring ratio $\varphi^{-1}$ versus null $\varphi^{-1/2}$; first resolvable rungs near $0.618R$ and $0.382R$** | Pre-registered pipeline; planted-signal calibration is synthetic and is not an observation; real-galaxy stacking is pending because no verified per-void galaxy-position catalog or immutable run receipt is available | **Hypothesized—observational verdict pending** |
| 53 | Disk-gap $\varphi$-ladder | Protoplanetary disks (ALMA) | **Successive gap ratio $\varphi^{-1}$ versus null $\varphi^{-1/2}$, pooled across disks** (a conditional gas/condensation channel) | DSHARP acquisition and analysis scripts are present, but no fetched data, parsed table, or immutable run receipt is committed; no pooled verdict or significance is assigned; planet-carving remains an alternative | **Hypothesized—real-data test pending** |
| 54 | Exoplanet period-ratio $\varphi$-spacing | Multi-planet catalogs (Kepler/TESS) | **Conditional detached-orbit target $P_{\text{out}}/P_{\text{in}}=\varphi^{3/2}=2.058171$; Fibonacci-convergent windows are secondary diagnostics** | Confirmed primary Kepler sample: 476 systems, 1,212 planets, 736 adjacent ratios, 562 in $[1,3]$; headline $N=46$, descriptive $z_{\rm win}=1.087$, formal classifier **INDETERMINATE**; target window overlaps the conventional wide-of-2:1 excess across $41.8\%$ of its width, so the scientific verdict is **INCONCLUSIVE** and no mechanism-specific field signal is established | **Tested—classifier INDETERMINATE; broad window rejected as a clean discriminator** |
| 55 | q-gated imbalance drift-and-diffusivity curve $R_Q(\varepsilon)$ | Field-experience / mesoscopic open-system (laboratory) | **$R_Q(\varepsilon)=3(1+\varphi^2\varepsilon^2)/(3+\varepsilon^2)$** at fixed $\rho=\varphi$, $\varepsilon\in[-\varphi^2,\varphi]$ (positivity wedge; formal $3\varphi^2$ asymptote unreachable; accessible range $[1,5.767427]$); deterministic Q-arm drift curve (no bath) vs flat C control vs null N arm; rank-one Yang/Yin increment covariance + FDT ratio as secondary checks (bath-conditional) | Hypothesized/conditional (split): deterministic drift curve conditional on the $q$-gated PDE + wedge + boundary rule; diffusivity/covariance + secondary checks additionally conditional on Gaussian Markov bath, stochastic convention, fixed $\rho=\varphi$, and absence of bath-scale blockers; PASS/FALSE/NULL vs Q/C/N arms | **Laboratory / controlled two-channel response** |
| 56 | Minimal-singlet fluctuation spectrum ($h_R$, $h_A$, $\theta_R$, $m_A^2/m_R^2$) | Two-singlet EFT (minimal vacuum; collider / precision frontier) | **$h_R=(\sqrt{\varphi}\,\delta\chi_Y+\delta\chi_I)/\varphi$, $h_A=(\delta\chi_Y-\sqrt{\varphi}\,\delta\chi_I)/\varphi$** (orthogonal, $(+,+)$ vacuum); $|\tan\theta_R|=\varphi^{-1/2}\approx0.786151$, hence $\theta_R\approx38.1727^\circ$; $m_R^2=2g_4\rho_\chi=2\mu_\chi^2$, $m_A^2=4\varphi\lambda_A\rho_\chi$, ratio $m_A^2/m_R^2=2\varphi\lambda_A/g_4$ | Derived conditional within minimal-vacuum ansatz at a declared matching scale ($g_4$, $\lambda_A$, $\mu_\chi$ free; no absolute mass or universal ratio); restricted $\varphi$ surface not RG invariant ((RG3)); physical realization Hypothesized | **Declared matching-scale relation; RG drift requires protecting mechanism** |

## 8. Conditional Boundary Anisotropy—Selected Edge Proxy

**Source:** `foundations/bubble-lattice-fabric.md` §4.2 and `foundations/bubble-edge-geometry.md` §§2.2, 9. The constructed condensation proxy has a **1.7072× directional edge-slope ratio only after selecting $\theta_{\mathrm{cond}}=0.45$**. That selection is a phenomenological map input, not a canonical/PDE output. No $C=0.45$ edge survives the fixed-step PDE endpoint, so the ratio is not a universal or parameter-free prediction of the canonical solver.

| Frontier | Observable | Cassi Prediction | Current Status | Detection Timeline |
|----------|-----------|------------------|----------------|-------------------|
| Cosmology (SDSS/DESI) | Void boundary density profile slope in axial vs. diagonal direction | **1.7072×** directional proxy steepness, conditional on $\theta_{\mathrm{cond}}=0.45$ | Fixed-step PDE endpoint has no $C=0.45$ edge; VAST/ZOBOV DR7 receipt is null (catalog §3 row) | **Existing surveys** |
| Biophysics (chakra) | Qi density gradient at chakra boundary | **1.7072×** directional proxy steepness, conditional on a measured or selected $\theta_{\mathrm{cond}}$ | Not yet tested; canonical $q$ requires a separately measured constitutive map | **Laboratory** |
| Anatomy (fascial planes) | Ultrasound elastography boundary stiffness ratio | **1.7072×** directional proxy anisotropy, conditional on a measured or selected $\theta_{\mathrm{cond}}$ | Not yet tested; canonical-field identification is not supplied | **Laboratory** |

## 9. Quantum-Sector Compatibility—Sodium-Nanoparticle Interference

| ID | Observable | Conditional Cassi result | Current status | Falsifier |
|----|------------|--------------------------|----------------|-----------|
| CT-1 | Talbot-Lau harmonic multiplier for a 172 kDa sodium nanoparticle | $R_\ell^{\mathrm{CassiFI}}=1$ for every integer $\ell$ before ordinary environmental and apparatus factors; therefore the same visibility as linear quantum mechanics under the same calibrated grating model | **Derived conditional** on QF1-QF4; compatible with the 2026 observed visibilities $0.10\pm0.01$ and $0.08\pm0.01$ and the reported macrorealist bound $\tau_e\geq2.84\times10^{15}$ s ($\mu=15.45$). This is a compatibility constraint rather than a Cassi-specific deviation. | Any intrinsic CassiFI localization term producing a reproducible $R_\ell\neq1$, or failure of the regulated Hamiltonian to reproduce $E=\hbar^2k^2/(2M)$ |

**Configuration-bridge boundary:** The DQ9 audit registers no Cassi-specific,

no-fit quantum observable. CT-1 is a compatibility constraint shared with
linear quantum mechanics. The DQ1–DQ9 campaign therefore yields `REJECT` for
promotion of the CassiFI physical-field identification to Derived; DQ3 and
DQ6 pass only under their declared quantum premises.

**Finite-completion boundary.** The QC1–QC9 closure campaign separately
`ADOPT`s a finite carrier reservoir as Hypothesized microphysics. Its
carrier-to-mesoscopic drift, binomial fluctuation, transport-noise kernel, and
finite quantum instrument are Derived conditional on the declared premises.
The completion does not change CT-1: under QF4 and the same completely positive
instrument, it remains operationally equivalent to ordinary quantum mechanics.
The physical state map between the QF1 complex field and the carrier
occupations is Open, so no carrier-derived Cassi-specific discriminator is
registered.

**Geometric boundary:** GQ7 certifies generic integer $U(1)$ winding and finds
no source-derived Cassi-specific connection or no-fit holonomy. The projective
shell construction now executes a finite part of the adopted moment-map/Kähler
direction and registers the conditional SB tests below. It supplies no
additional quantum-sector discriminator or physical-identification promotion.

**Source:** `foundations/quantum-measurement-derivation.md` §§7–8;
`computations/quantum-closure-pre-registration.md`;
`computations/verify_quantum_closure.py`;
`computations/quantum-geometric-bridge-pre-registration.md`;
`computations/verify_quantum_geometric_bridge.py`;
`computations/quantum-configuration-bridge-pre-registration.md`;
`computations/verify_quantum_configuration_bridge.py`;
`computations/cassifi-quantum-bridge-pre-registration.md`;
`computations/verify_cassifi_quantum_bridge.py`; “Quantum interference of
sodium nanoparticles,” *Nature* (2026),
https://doi.org/10.1038/s41586-025-09917-9.

## 10. Candidate Physical-Time Cross-Clock Test

| ID | Observable | Conditional Cassi result | Current status | Falsifier |
|----|------------|--------------------------|----------------|-----------|
| **CT-2** | Normalized rates of a canonical conversion clock and at least two independently calibrated non-conversion clocks across a frozen coherence contrast | Use the canonical bounded coherence $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$ and reference $q_\star<1$. For each independent phase clock $a$, $\mathcal C_a=(1/\omega_a)d\Theta_a/d\tau_\star$; conversion supplies $\mathcal C_F=-[(1+\varphi)\lambda\varepsilon]^{-1}d\varepsilon/d\tau_\star$. Candidate physical time predicts $\mathcal C_a=\mathcal C_F=(1-q)/(1-q_\star)$ for every clock. | **Conditional discriminator; untested.** Freeze the $q$ definition, physical-density normalization $\rho_\star$, reference worldline, intrinsic clock calibrations, gate-memory choice, transport subtraction, resolution, and uncertainty budget before a run. Require a resolved $q$ contrast and nonzero phase accumulation. **SUPPORTS** only when the conversion receipt and at least two independent clock sectors share the predicted ratio within the preregistered uncertainty; **CONTRADICTS** when any resolved independent sector reproducibly disagrees while conversion isolation passes; **INCONCLUSIVE** when the contrast, branch, phase resolution, transport isolation, or calibration gate fails. Conversion-only agreement is an identity check. | A reproducible cross-clock disagreement at the same bounded $q$ and frozen reference. A sector-selective insertion of $(1-q)$ tests implementation wiring rather than universality. |

**Source:** `foundations/unified-lagrangian.md` §1.7;
`foundations/cassi-first-principles.md` §2.6;
`predictions/cassi_definitions.md` §6;
`hypotheses/scalar-time-reparameterization-applications.md`.

## 11. Conditional String-Bubble Projective Tests

| ID | Observable | Conditional Cassi result | Current status | Falsifier |
|----|------------|--------------------------|----------------|-----------|
| **SB-1** | Simultaneous normalized shell position and Yin/Yang density composition | With $D$ fixed by the observed or declared quadratic shell, $\mathbf n=D^{-1}\mathbf X$ obeys $\|\mathbf n\|=1$ and $n_z=(E_Y-E_I)/(E_Y+E_I)$ | **Derived conditional; untested physically.** Frozen verifier SB1 passes; the shell identification is Hypothesized | No single fixed diagonal $D$ closes the sampled states on a unit sphere, or the measured composition disagrees with $n_z$ beyond uncertainty |
| **SB-2** | Shell trajectory under a controlled relative-phase advance at fixed density composition | $G(\Delta)=D R_z(\Delta)D^{-1}$ preserves $\mathbf X^T D^{-2}\mathbf X$, composes additively, and carries one meridian through a latitude ellipse | **Derived conditional; untested physically.** Frozen verifier SB2 passes | A controlled phase cycle changes the pullback shell norm or fails group composition after transport and dissipation are removed |
| **SB-3** | Five selected phase sectors at one interior latitude | In normalized coordinates, the step-two/step-one chord ratio is $\varphi$ and each pentagram diagonal is divided as $\varphi^{-2}:\varphi^{-3}:\varphi^{-2}$; the collinear fractions survive the affine shell map | **Derived conditional geometry.** Frozen verifier SB3 passes; spontaneous selection of the five sectors is Hypothesized | The selected sectors fail either normalized ratio, or the affine map changes the collinear division fractions |
| **SB-4** | Homogeneous conversion-only evolution of density composition | For $\rho>0$ and $0<\vartheta<\pi$, $\dot\rho=0$ and $\dot\vartheta=\kappa(\varphi^2\cos\vartheta-\varphi^{-1})/\sin\vartheta$, with $\kappa=\lambda(1-q)$ and $\cos\vartheta=(E_Y-E_I)/\rho$; $\dot s=-2\kappa\varepsilon/\rho$ is endpoint-safe | **Derived conditional; solver-level identity.** Frozen verifier SB4 passes | A homogeneous conversion-only run conserves neither $\rho$ nor the displayed meridional law |
| **SB-5** | Projective phase loop around the attractor latitude | $\oint\mathcal A=\pi(1-\varphi^{-3})$ and five equal phase steps each contribute one fifth of the loop value | **Derived generic $\mathbb{CP}^1$ geometry.** Frozen verifier SB5 passes; a physical Cassi holonomy remains Open | A realized state map and measured connection disagree with the loop relation after gauge convention and uncertainty are fixed |

The pure phase action also supplies a selector null:
$a_m(t)=e^{-im\Omega t}a_m(0)$, so an absent $m=5$ mode remains absent.
Amplification would require dynamics beyond that pure action; its absence would
not establish the physical shell identification.

**Source:** `foundations/string-bubble-projective-map.md`;
`computations/verify_string_bubble_projective_map.py`.

## 12. Conditional Loop-to-Bubble Tests

These tests apply only if the shared-support carrier variables are physically
identified. They test that realization without promoting the open
QF1-to-carrier map or assigning a universal loop-to-bubble spatial ratio.

| ID | Observable | Conditional Cassi result | Current status | Falsifier |
|----|------------|--------------------------|----------------|-----------|
| **LP-1** | Direction-resolved Yang/Yin populations and their complete-loop averages | With one common projected gate and common exterior transport, $E_a=\sum_s\langle f_{a,s}\rangle_\chi$ obeys the canonical two-density PDE exactly; internal circulation, loop diffusion, and symmetric direction exchange leave no residual in the zero mode | **Derived conditional; untested physically.** Frozen verifier LB1–LB3 passes; carrier identity and shared support are Hypothesized | A resolved common-support realization leaves a projected drift or flux covariance outside calibrated error after the declared operators are included |
| **LP-2** | Undriven decay rates of loop Fourier, direction-imbalance, and species-imbalance perturbations | The passive generator has $\Lambda_{m,c,\pm}=-dm^2+c-r\pm\sqrt{r^2-m^2\Omega^2}$ with $c\in\{0,-\kappa(1+\varphi)\}$ and $g_{\rm int}=\min\{\kappa(1+\varphi),2r,d+r-\operatorname{Re}\sqrt{r^2-\Omega^2}\}$ | **Derived conditional; untested physically.** Frozen verifier LB5 passes | No common $(d,\Omega,r,\kappa)$ fits the resolved passive mode spectrum, or an undriven persistent mode remains where the fitted gap is positive |
| **LP-3** | Coherence-sensitive bubble coordinates at fixed projected densities | The normalized species Gram matrix is positive, so $|c|^2\leq E_YE_I$ and $\|\mathbf n\|\leq1$; rank-one states lie on the projective shell, while phase decorrelation contracts the transverse coordinate into the affine bubble interior | **Derived conditional coordinate geometry; untested physically.** Frozen verifier LB4 and LB6 pass; the observable map from $c$ is Open | A physical $c$-sensitive map violates the coherence bound, places a rank-one state inside the normalized ball, or remains unchanged under every controlled phase change at fixed $(E_Y,E_I)$ |
| **LP-4** | Coarse transverse visibility of $K$ equal-weight layers with successive mean phase difference $\pi$ | $\zeta_K=K^{-1}\sum_{j=0}^{K-1}(-1)^j$, hence $\zeta_{2N}=0$ and $|\zeta_{2N+1}|=1/(2N+1)$; unequal opposite-phase weights leave $|w_+-w_-|/(w_++w_-)$ | **Derived conditional projection law; untested physically.** Frozen verifier LB4 passes; layer production and spacing are Open | The measured residual lies outside independently calibrated phase and weight errors |
| **LP-5** | Accuracy of the projected bubble description across an internal-relaxation sweep | When $g_{\rm int}T_B\gg1$ and $R/L_B\ll1$, unforced nonzero loop modes relax before the bubble fields change and the zero-mode PDE becomes dynamically autonomous after the transient | **Derived sufficient coarse-graining criterion; untested physically.** No universal threshold value or spatial ratio is assigned | Resolved nonzero modes produce a persistent projected-state dependence in the stated asymptotic regime after common-gate and common-transport conditions are verified |
| **LP-6** | Visibility of five supplied phase sectors at the attractor composition | Every normalized transverse radius and chord scales linearly with $\eta_c$; for $\eta_c>0$, $L_{\rm step\,2}^{\rm norm}/L_{\rm step\,1}^{\rm norm}=\varphi$, while all five points coincide at $\eta_c=0$ | **Derived conditional geometry.** Frozen verifier LB7 passes; selection of five sectors and their rotation law remain Hypothesized | A realized five-sector map violates linear visibility scaling or the normalized chord ratio after the affine metric and uncertainty are fixed |

The projection supplies a scale switch by state reduction and the
rate-controlled criterion in LP-5. It does not predict the radial layer
spacing, $R/L_B$, a $\varphi$-spaced spatial jump, spontaneous $w=5$
selection, or a phase-rotation law.

**Source:** `foundations/loop-to-bubble-projection-theorem.md` §§2–10;
`computations/loop-to-bubble-projection-pre-registration.md`;
`computations/verify_loop_to_bubble_projection.py`.


## 13. Conditional Counterflow De-Resonance Tests

These tests apply only after a physical compact phase and its signed current
have been identified independently of the density ratio. They do not promote
the declared density target or the physical de-resonance proposal.

| ID | Observable | Conditional Cassi result | Current status | Falsifier |
|----|------------|--------------------------|----------------|-----------|
| **DR-1** | Simultaneous $E_Y/E_I$, phase-gradient magnitudes $k_I/k_Y$, effective mobilities, and net through-current | The declared current law gives $\alpha=(\mu_Y/\mu_I)(E_Y/E_I)-J_0/(\mu_IE_Ik_Y)$. Under independently verified $\mu_Y=\mu_I$, $J_0=0$, and adiabatic adjustment, $\alpha=E_Y/E_I$ and obeys $\dot\alpha=-\kappa(1+\alpha)(\alpha-\varphi)$ during homogeneous conversion | **Derived conditional; untested physically.** PC1–PC6 verify the algebra, transient, exposure, and controls; compact phases and the current law remain Hypothesized | With every closure premise independently satisfied, either the current identity or the displayed transient fails beyond calibrated uncertainty |
| **DR-2** | Complex loop amplitude and integer winding before, during, and after a compact-sector change | A jointly continuous nonzero scalar amplitude on an unchanged $S^1$ domain conserves $w=(2\pi i)^{-1}\oint\psi^{-1}d\psi$; a sector change requires an amplitude zero, changed boundary or topology, or gauge-bundle holonomy | **Derived topological identity; physical realization untested.** This theorem determines necessity, not slip rate or direction | A fully resolved sector change occurs while the scalar amplitude remains nonzero on the complete space-time cylinder and the boundary, topology, and bundle remain unchanged |
| **DR-3** | Phase locking or resonant spectral transfer under a preregistered ratio sweep with fixed forcing, dissipation, exposure, and boundary data | The physical de-resonance hypothesis requires the $\varphi$ target to produce a reproducible suppression relative to matched rational controls and other preregistered irrational targets without parameter refitting | **Hypothesized physical discriminator.** The canonical density law and PC1–PC7 do not predict a suppression magnitude; the microscopic phase-current law, statistic, comparison set, and stopping rule must be frozen before execution | The frozen sweep does not distinguish $\varphi$, places it above the preregistered suppression threshold, or another target outperforms it under the same controls |
| **DR-4** | Stable compact winding sectors during slow conversion toward the continuum target | If the physical sector cost is dominated by bounded-denominator phase mismatch, the record candidates are $(p,q_{\rm w})=(F_n,F_{n+1})$; sector changes must obey DR-2 | **Derived conditional arithmetic / Hypothesized selector.** PC7 verifies the record sequence; no energy or transition law selects it physically | With the mismatch-only selector and cutoff independently established, the stable record sequence is non-Fibonacci, or physical sectors systematically select non-record ratios |

**Source:** `principles/de-resonance-principle.md` §§1.3–1.5;
`computations/phi-counterflow-selection-pre-registration.md`;
`computations/verify_phi_counterflow_selection.py`;
`computations/phi-counterflow-selection-report.md`.

## 14. Conditional Geometric-Manifold Completion Tests

These checks apply to the declared stratified metric-graph completion. They
test its compatibility and reduction contracts without promoting the ansatz
to physical microphysics.

| ID | Observable | Conditional Cassi result | Current status | Falsifier |
|----|------------|--------------------------|----------------|-----------|
| **GM-1** | Positive Yang/Yin coherence matrix and its normalized Bloch coordinate | $\det\Gamma=\rho^2(1-\|\mathbf n\|^2)/4$, so positive matrices fill the cone over $B^3$ and rank-one states lie on $S^2$ | **Derived linear algebra.** The checker verifies full-rank and rank-one samples | A matrix satisfying the declared positive-fibre premises violates the determinant identity or leaves the Bloch ball |
| **GM-2** | Canonical real-density and zero-extension limits of the graph-bundle continuity equation | With $c=0$, no scale current, no relative connection, no endpoint channel, canonical spatial fluxes, and zero noise, every added-sector term vanishes separately and the diagonal equations reproduce the canonical two-fluid PDE exactly | **Derived conditional reduction.** The checker computes connection, scale, endpoint, and bath terms from their neutral inputs, asserts their component residuals separately, and evaluates the assembled zero-extension residual. Active endpoint and bath dynamics remain unspecified and unverified | Any computed neutral-input component survives, the assembled added-sector residual is nonzero, or the remaining population operator differs from canonical conversion |
| **GM-3** | Undriven transverse coherence and composition relaxation in the minimal two-jump lift | $\gamma_c=\gamma_\varepsilon/2$; at the gated reference state, $(\gamma_\varepsilon,\gamma_c)=(\lambda/3,\lambda/6)$ | **Derived within the minimal lift; physically untested.** A carrier-to-$c$ observable and an independently identified undriven regime remain open | Under the declared two-jump generator and controlled undriven conditions, measured coherence fails the half-rate relation beyond calibrated uncertainty |
| **GM-4** | Topology and holonomy of the cross-glued Yang/Yin scale rails | Two vertices and two edges give $b_1=1$, circumference $2L_{\mathfrak s}$, and $\int(\nu_Y-\nu_I)d\mathfrak s+\delta_-+\delta_+=2\pi m$, where $\delta_-+\delta_+$ is the dressed endpoint contribution | **Derived graph geometry conditional on gauge-covariant endpoint gluing.** Physical charged endpoint fields or equivalent dressing remain Hypothesized | The declared quotient has a different first Betti number or its oriented circuit phase fails the displayed holonomy after the endpoint contribution is made gauge invariant |
| **GM-5** | Projective winding under a continuous path through full-rank coherence states | The rank-one shell has $\pi_2(S^2)=\mathbb Z$, while the full normalized fibre $B^3$ is contractible, so shell winding can unwind through the interior unless another invariant protects it | **Derived topology.** Physical access to and control of the coherence interior remain untested | A continuous contraction is impossible in the full declared Bloch ball after independent gauge flux and boundary invariants are excluded |

**Source:** `foundations/geometric-manifold-completion.md`;
`computations/geometric_manifold_completion_check.py`.


## 15. Conditional Endpoint and Localization Tests

These checks apply to the declared relative-connection and metric-graph
endpoint sector. They register algebraic and topological boundaries without
assigning a particle realization.

| ID | Observable | Conditional Cassi result | Current status | Falsifier |
|----|------------|--------------------------|----------------|-----------|
| **EL-1** | Relative-frame transformation and Yang/Yin source at a coherent scale vertex | A charge-$-g_Q$ section makes $\Upsilon_v^*\psi_Y^*\psi_I+\mathrm{c.c.}$ invariant and gives $\dot E_Y=-\dot E_I$, so vertex conversion conserves total Yang-plus-Yin density | **Derived conditional representation and source algebra.** Physical endpoint field and normalization remain Hypothesized | The link transforms nontrivially or violates total-density conservation under the declared charge assignments |
| **EL-2** | Frozen and first-order source-action charged-endpoint response with the closed-current boundary | For a declared species-port identification, common trace normalization, and frozen background $\Upsilon_{v,0}=u_ve^{i\alpha_v}$, the rail-rail Hessian is $\Lambda_{\mathrm{link},v}=2\kappa_vu_vM(\alpha_v)$. A dressed quarter-turn phase and $2\kappa_vu_v/(K_{\mathfrak s}k_\star)=\tau_\varphi:=r_\varphi/(1+t_\varphi)$ give $S_{\mathrm{link}}(k_\star)=S_{\varphi,\epsilon}$; the same frozen link has $a(k)=(k_\star/k)\tau_\varphi$. Unbiased proton-current capacity with positive fixed-amplitude phase stiffness requires $k_\star>0.0964640362$. Every closed homogeneous conservative time-harmonic endpoint extremum has $\mathcal I_{\mathrm{link}}=0$. Around a nonzero rail background, first-order source-action elimination gives $\mathbb\Lambda_{\mathrm{eff}}^R=\mathbb\Lambda_0-\mathcal C^\dagger(\mathcal K^R)^{-1}\mathcal C=\mathbb\Lambda_0+\mathcal C^\dagger(\mathcal D^R)^{-1}\mathcal C$, with $\mathcal K^R=-\mathcal D^R$. With fields proportional to $e^{-i\omega t}$, the retarded poles are $\omega=\pm\sqrt{A_v^2-|B_v|^2}/\mathcal Z_v-i\gamma_v$ and the advanced poles carry $+i\gamma_v$; $\gamma_v\to0$ gives the conservative branch. At the symmetric zero background, the eliminated source action begins at quartic rail order with a positive coefficient when $\mu_{v,0}:=W_v'(0)>0$; physical energy, stress, inertial mass, and stability signs remain open | **Derived conditional frozen-link, current, first-order response, order, and pole algebra.** The frozen-link receipt passes ER1–ER5 with covariance residual $1.110\times10^{-16}$, selected-match residual $1.173\times10^{-16}$, $k_{\min,1}=0.096464036203895$, and off-match difference $0.227151634836$. The frozen AR1–AR6 source-action receipt passes with zero $\mathcal K/\mathcal D$ residual, elimination residual $1.511\times10^{-17}$, constant-frame kernel-covariance residual $2.220\times10^{-16}$, and anomalous-block norm $0.390450933151$; its $m_{v,0}=1.1$ is protocol notation for $\mu_{v,0}$. The DR receipt remains **FAIL** because its DR5 endpoint block has the opposite source-action sign. The physical port identification, trace normalization, endpoint potential and background, dressed-phase selection, $k_\star$, microscopic damping channel, temporal relative-gauge connection, doubled port-flux law, and full coupled spectrum remain open | No consistent species-port trace map exists; the inferred frozen $\Lambda$ is non-Hermitian in a declared closed elastic sector; the dressed-phase, coupling, current-capacity, or off-match Cayley law fails; a closed homogeneous conservative extremum supports nonzero steady conversion current; the first-order source-action endpoint Hessian, pole law, Schur complement, constant-frame covariance, quartic scaling or source-action sign under $\mu_{v,0}>0$, or retarded/advanced relation fails; or the selected physical background is unstable |
| **EL-3** | Off-diagonal endpoint coherence under an undriven one-way channel | Each donor jump gives $\dot c=-\gamma_vc/2$ | **Derived within the declared Lindblad channel.** A coherent drive or different reservoir may change the result | The declared undriven one-jump dissipator preserves or amplifies nonzero $c$ |
| **EL-4** | State-only and connection-bundle topology | $\mathcal C_2^+\setminus\{0\}\simeq\mathbb R_{>0}\times B^3$ is contractible. An independent compact connection has $N_G=(g_Q/4\pi)\int_\Sigma G\in\mathbb Z$, while $H^2(\mathbb R^3\times S^1_{\mathfrak s};\mathbb Z)=0$ on the smooth object base | **Derived topology.** Removing a spatial core at every scale gives a scale-worldtube with an $S^2$ link and a candidate $\mathbb Z$ sector; its physical core remains open | A nontrivial state-only homotopy class exists in the full positive fibre, or a nonzero first Chern class exists on the declared smooth base without a cycle, defect, boundary, or topology change |
| **EL-5** | Spatial Derrick scale in the smooth zero-Chern endpoint sector | With $\mathcal B=0$, $\mathcal A>0$, $\mathcal C\geq0$, and $\mathcal D\geq0$, $E'(R)=\mathcal A+\mathcal D/R^2+3\mathcal C R^2>0$; no finite positive stationary radius exists | **Derived minimal-sector localization no-go.** This excludes the point-core, fixed-flux, higher-derivative, and nonlocal sectors from its premises | A finite stationary radius occurs while every declared premise, including absence of independent $1/R$ support, remains satisfied |
| **EL-6** | Point-flux exterior support and reduced radius | $\mathcal B_G=2\pi N_G^2\int d\mathfrak s/e_x^2$ is the sharp fixed-flux exterior coefficient. For $\mathcal A>0$, $\mathcal C>0$, and $\mathcal Q_N=\mathcal B_G-\mathcal D>0$, $R_*^2=[-\mathcal A+\sqrt{\mathcal A^2+12\mathcal C\mathcal Q_N}]/(6\mathcal C)$ and $E''(R_*)=2\mathcal A/R_*+12\mathcal C R_*>0$; for $\mathcal C=0$, $\mathcal A>0$, and $\mathcal Q_N>0$, $R_*^2=\mathcal Q_N/\mathcal A$ | **Derived conditional exterior and reduced-profile algebra.** The registered Abelian action cannot smooth the core and its nonzero condensate has divergent isolated-flux angular energy. The auxiliary adjoint $SU(2)_Q$ branch smooths the local core only in its decoupled sector; coupling the registered condensate confines flux and supplies no persistent finite-separation object | The fixed-flux gauge energy violates the displayed coefficient or gauge-normalization invariance; either radius branch fails its stated stationary-minimum conditions; the auxiliary core fails its BPS identities or exterior matching; or the condensate-coupled branch admits finite-energy isolated flux without changing the declared action |
| **EL-7** | Auxiliary smooth magnetic core and confined-defect boundary | In the adjoint-only Prasad-Sommerfield branch, $K=X/\sinh X$, $H=\coth X-1/X$, $\Phi_G=4\pi N_G/g_Q$, and $M_{\mathrm{BPS}}=4\pi L_{\mathfrak s}v_Q\lvert N_G\rvert/(\mu_xg_Q)$. With the registered nonzero doublet, $H_{\mathrm{full}}=\{1\}$, $\pi_2(SU(2)_Q)=0$, $\kappa_L^2=e_x^2K_x\rho_0/\varphi^3>0$, and the long-distance monopole-antimonopole string energy has $E'(L)>0$ | **Derived conditional on a Hypothesized internal $SU(2)_Q$ completion.** The exact BPS branch is adjoint-only; the condensate-coupled branch has no isolated magnetic sector or registered persistent pair. No Standard Model identification or numerical particle prediction is assigned | The profile fails the first-order equations or unit energy integral; the residual flux or exterior coefficient mismatches EL-6; the displayed full-vacuum stabilizer or topology is wrong for the declared fields; the London mass vanishes at $\rho_0>0$ without changing an input; or the stated asymptotic pair slope is nonpositive with positive tension and attraction |
| **EL-8** | Core-trapped conserved-charge support | A neutral carrier with a bound transverse mode and positive effective line coupling $\Lambda_C$ gives $A_C=\Lambda_CQ_C^2/2$. For $A_C>C_Q$, the reduced confined-pair energy has exactly one stationary separation satisfying $\sqrt{(A_C-C_Q)/\sigma_Q}<L_*<\sqrt{A_C/\sigma_Q}$ and $E''(L_*)>0$. Carrier retention independently requires $\hbar\omega_C<\varepsilon_{C,\rm out}$, and thin-tube validity requires $A_C-C_Q>\sigma_QL_{\rm match}^2$ | **Derived conditional in the Hypothesized carrier branch.** No physical coefficient values or particle identification are selected | The declared reduced energy under all displayed support, retention, and matching premises lacks a unique positive root, has nonpositive length curvature, or places the carrier chemical potential at or above the bulk threshold |
| **EL-9** | Source-free temporal particle action and fixed-$Q_C$ stationary closure | Direct local gauging of the first-order Yang/Yin time term gives a nonzero fundamental-condensate Gauss source with $S^aS^a=\rho^2$. The separate second-order charged-field branch is covariant under time-dependent local $SU(2)_Q$, has positive temporal curvature terms, and makes $\mathcal A_0=0$ with static charged fields Gauss-compatible. Its stationary functional is $E_P-\hbar\omega_CQ_C$ | **Derived conditional action algebra / Tested one-point numerical campaign.** The registered point returns `INCONCLUSIVE—NUMERICAL QUALITY`: all twelve primary/domain arms fail Q2, and no high-resolution arm is eligible. Stationary existence, the spectrum, physical coefficient calibration, and the particle map remain open | The Pauli identity fails, the first-order source vanishes for a nonzero fundamental condensate without added charge, the selected action fails local temporal covariance or Gauss variation, the static ansatz violates Gauss's law, or its source units and dimensionless groups fail closure |
| **EL-10** | Stationary charged-endpoint spatial flux and closed-domain zero mode | The action gives $\partial_t|\Upsilon_v|^2+\nabla\cdot\mathbf J_{\Upsilon,v}=\Gamma_v=-\mathcal I_{\mathrm{link},v}/2$. Every periodic, no-flux, or sufficiently localized stationary endpoint domain has $\int\Gamma_vd^3x=0$. On a constant-amplitude periodic cube with $K_v\ne0$ and $u_v>0$, each zero-mean source has $\alpha_{v,\mathbf k}=-\hbar\Gamma_{v,\mathbf k}/(K_vu_v^2|\mathbf k|^2)$; for $K_v>0$ its cost $H_{\nabla\Upsilon,v}=(\hbar^2V/2K_vu_v^2)\sum_{\mathbf k\ne0}|\Gamma_{v,\mathbf k}|^2/|\mathbf k|^2$ is positive | **Derived conditional and SF1–SF6 tested.** The frozen receipt passes at one normalized point with $K_v=2.3$ and $u_v=0.9$. The coupled rail background, boundary or inter-vertex transport, physical coefficients, and particle interpretation remain open | The registered action violates the local source identity or time-independent gauge covariance; a periodic divergence supports a nonzero source mean; or the direct and Fourier gradient costs disagree under the frozen conventions |

**Source:** `foundations/endpoint-link-and-localization-boundary.md`;
`foundations/point-core-flux-sector.md`;
`foundations/nonabelian-magnetic-core-boundary.md`;
`foundations/core-trapped-charge-support.md`;
`computations/endpoint_link_localization_check.py`;
`computations/endpoint_robin_link_prereg.md`;
`computations/endpoint_dynamical_response_prereg.md`;
`computations/endpoint_dynamical_response_check.py`;
`computations/endpoint_dynamical_response_report.md`;
`computations/endpoint_action_response_prereg.md`;
`computations/endpoint_action_response_check.py`;
`computations/endpoint_action_response_report.md`;
`computations/endpoint_spatial_flux_prereg.md`;
`computations/endpoint_spatial_flux_check.py`;
`computations/endpoint_spatial_flux_report.md`;
`computations/point_core_flux_check.py`;
`computations/magnetic_core_completion_check.py`;
`computations/core_trapped_charge_check.py`;
`foundations/particle-stationary-action-closure.md`;
`computations/particle-stationary-bvp-pre-registration.md`;
`computations/particle_stationary_bvp.py`;
`computations/verify_particle_stationary_bvp.py`;
`computations/particle-stationary-bvp-report.md`; and
`computations/particle_action_closure_check.py`.


---

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

- **Scope of current tests:** test status is tracked per row and in `audit.md`.
  The catalog mixes parameter-free consequences, conditional calculations,
  fitted or calibrated comparisons, null results, rejected entries, and open
  hypotheses. Rows without a registered derivation are marked **Not
  predicted**; no aggregate success count is assigned across those classes.
- **Conditional test rows (CT-n, SB-n, LP-n, DR-n, GM-n, and EL-n):**
  these rows are unnumbered conditional discriminators outside the 1–N
  numbered prediction sequence and do not alter its count. EL-1–EL-6 register
  endpoint gauge covariance, coherent capacity, the open-channel rate and
  coherence laws, full-fibre and bundle topology, the smooth-sector
  localization no-go, and the conditional supported radius.

- **Deviations from SM expectations are falsifiable**—not adjustable. If FCC-ee
  measures $m_W/m_Z = 0.881 \pm 0.0001$, the Cassi framework is excluded
  (the predicted value is 0.878 after radiative corrections).

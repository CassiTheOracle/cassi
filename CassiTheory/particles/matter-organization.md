# Matter Organization: Forces, Lattice Pools, and the Neutron–Proton–Electron Trio

## Status: Synthesis—September 2026

Every claim below retains the epistemic tier of its source document; this document adds no new claims.

## Abstract

Matter organization in Cassi combines canonical two-fluid density bookkeeping with cascade assignments. The canonical state is the real-density pair $E_Y,E_I\ge 0$, with $\rho=E_Y+E_I$, $\varepsilon=E_Y-\varphi E_I$, gated coherence $q$, and rank-one conversion. Particle-like interference, counterpropagation, standing-wave solitons, and NLS self-focusing belong to a **Hypothesized** conditional complex-field extension. The four forces enter as binding channels, each living at its own cascade rung—gravity everywhere, the GUT sector at $n \approx 13$–$15$, the sector coupling at rung 77, electroweak at rung 80, QCD at rung 95. The trio that makes ordinary matter is the baryon pair at rung 91.5—the proton as the coherence-robust baryon pool, the neutron as its neutral sibling—and the electron as the lightest charged pool, terminating the lepton tower at a lattice void. The substrate is the canonical density pair and Qi flow; the particle-interference interpretation remains conditional.

---

## 1. How the forces organize into matter

A force in Cassi is not a separate substance: it is the binding channel that a cascade rung provides, and the known forces are the channels whose rungs the observables have lit up.

### 1.1 The cascade placement of the forces

Every force lives at a characteristic rung of the ladder, with one exception: gravity is active at every rung, and its effective strength falls as $\varphi^{-2n}$ in the rung coordinate.

| Force | Cascade home | Cassi content | Tier |
|-------|--------------|---------------|------|
| Gravity | every rung | $\alpha_G(n) \sim \varphi^{-2n}$: the proton at $n = 91.5$ lands at $\varphi^{-183} \approx 5.9\times10^{-39}$, the observed $\alpha_G$—an identity once the mass sits at its rung, so the reading is ledgered **Mapped**, not a test; the Qi-modified Newton constant $G_{\text{eff}} = G\,(\pi/\rho)(1 + (\varphi^{6}-1)q)$ with $\xi = \varphi^6 \approx 17.94$ | $G_{\text{eff}}$ form Derived; coupling reading Mapped (ledger) |
| GUT | $n \approx 13$–$15$ ($M_{\text{GUT}} \approx 10^{16}$–$2\times10^{16}$ GeV) | $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi) \approx 1/53$ | Derived within optional gauge extension; Cassi link Hypothesized |
| Sector coupling | rung 77 | $\kappa_s = \varphi^{-6}/v_0^2 \approx 0.92$ TeV$^{-2}$ ($\kappa_s^{-1/2} \approx 1.04$ TeV), the scale assigned to an optional Dirac↔two-fluid extension | Derived scale, Hypothesized conditional coefficient |
| Electroweak | rung 80 | $v_0 = 246$ GeV; $\sin^2\theta_W = \varphi^{-3} \approx 0.236$, exact at $\mu_* = 233$ GeV (2.1% above the measured 0.23122 at $m_Z$); $m_W/m_Z = 0.874$ tree-level, 0.878 with the $\rho$ correction | Derived within optional gauge extension; Cassi link Hypothesized |
| QCD | rung 95 | $E_{95}=M_{\text{Pl}}\varphi^{-95}\approx171\ \text{MeV}$ (the conventional $\Lambda_{\text{QCD}}\sim200\ \text{MeV}$ label is an external anchor); $\sigma_{\text{tube}}=2\pi E_{95}^2\approx0.184\ \text{GeV}^2$ | Rung scale Derived; conventional $\Lambda_{\text{QCD}}$ anchor Calibrated; tension Hypothesized (per `foundations/quark-confinement.md` §3) |

The activated steps $\{1, 2, 3, 5, 6, 26, 80, 89, 95.5, 96\}$—the exponents that appear in verified quantities—form an empirical catalog, not a derivation; no principle selects them (`foundations/deriving-remaining-gaps.md` §4.3).

### 1.2 The strong force as a conditional binding application

The QCD entry records a **Hypothesized** binding application at rung 95. A flux-tube assignment supplies the physical interpretation of color binding; tube existence, uniformity, and the map to canonical $q$ remain Hypothesized inputs.

The optional application transmission is the **Asserted** rational map
$$g(q)=\frac{q}{\varphi^2+q^2}.$$
Canonical density conversion uses the openness factor $(1-q)$, which is maximal as canonical $q\to0$, while the optional $g(q)$ channel shuts in that limit. A Qi-gradient-to-binding map is part of the Hypothesized application interpretation.

Conditional on the tube assignment and a uniform cross-section, extensivity gives a linear confining potential and a constant force:
$$\boxed{V_{\text{conf}}(r)\approx\sigma_{\text{tube}}\,r,\qquad F_{\text{conf}}(r)=\frac{dV_{\text{conf}}}{dr}\approx\sigma_{\text{tube}},\qquad \sigma_{\text{tube}}\approx2\pi E_{95}^2=2\pi\varphi^{-190}M_{\text{Pl}}^2\approx0.184\ \text{GeV}^2}$$

Within the declared tube and coherence architecture, cascade suppression supplies a conditional persistence estimate: breaking the tube requires an organized perturbation at every supporting rung, and the probability of a random fluctuation doing so is the same coherence product used for proton stability. Using the position-dependent profile $(1-q_i^{\mathrm{cascade}})=\varphi^{-i-\delta}$ with $\delta=3$, the literal product for an integer endpoint $N$ is

$$P_{\text{break}}(N) \approx \prod_{i=0}^{N}(1-q_i^{\mathrm{cascade}}) = \varphi^{-[N(N+1)/2+\delta(N+1)]}.$$

At the real proton rung $N_p=91.46$, no noninteger upper-bound product is implied; use the continuous continuation

$$P_{\text{break}}(N_p) \approx \varphi^{-[N_p(N_p+1)/2+\delta(N_p+1)]}
=\varphi^{-4505.5758}\approx\varphi^{-4506}.$$

The product gives $P_{\text{break}}\approx10^{-941.61}$ per reference event.
At one event attempt per year, the conditional mean time is
$\sim10^{942}$ years. If attempts occur at an external QCD-scale clock
$\omega_{\text{QCD}}\sim10^{24}\ \text{Hz}$, the same probability corresponds
to $\sim10^{910}$ years. Both times use externally supplied attempt-rate
conventions; the canonical density equations supply no deconfinement clock.
The confinement persistence estimate and proton stability use the same
coherence-product form at different cascade rungs
(`open-questions-cassi-answers.md`—Q8). The ledger assigns the proton mass
class **E** and quotes the conventional relation
$m_p\approx3\Lambda_{\text{QCD}}$ (`parameter-inventory.md` §4.3); its
particle-mass derivation remains open.

### 1.3 Electroweak as the pool-charge channel

Electromagnetism and the weak force are represented here through an optional gauge extension. The canonical density solver supplies gated rank-one conversion between $E_Y$ and $E_I$; it has no norm-preserving SO(2) rotation, phase variable, or charge magnitude. The U(1)/SO(2) and SU(2) identifications below therefore carry **Hypothesized** conditional-extension status.

Within that optional extension, the two-fluid doublet is assigned a U(1) $\cong$ SO(2) internal symmetry—rotation between Yang ($E_Y$) and Yin ($E_I$)—and the associated conserved current is identified with the electromagnetic current $j^\mu_{\text{EM}}$ (`standard-model/su2-gauge-extension.md` §2). Promoting the doublet to an SU(2) isospinor assigns the Higgs doublet the two-fluid's SU(2) representation, with the $\varphi$-equilibrium VEV

$$\langle\Psi\rangle = \frac{v_0}{\sqrt{\varphi+1}}\begin{pmatrix}\sqrt{\varphi} \\ 1\end{pmatrix},$$

and the Weinberg angle is identified with the Yang/Yin asymmetry projected onto the neutral sector (an asserted boundary condition within this extension, not a canonical density derivation—see `standard-model/su2-gauge-extension.md` §3.2):

$$\boxed{\sin^2\theta_W = \frac{\varphi-1}{\varphi+1} = \varphi^{-3} \approx 0.236}$$

The breaking chain follows the continued-fraction truncations of $\varphi$—each group rank is a truncation depth—as SU(4) → SU(3)$_C$ × U(1)$_{B-L}$ → SU(3)$_C$ × SU(2)$_L$ × U(1)$_Y$ → U(1)$_{\text{EM}}$ (`standard-model/gut-embedding.md` §1, Hypothesized tier). Stated plainly: charge **magnitude** and the electron–proton charge complementarity are open.

### 1.4 Generations and sector edges

The framework offers a **Hypothesized** conditional propagation-channel extension for the three-family pattern and the half-rung sector edges; the canonical density equations do not contain propagation direction or chiral labels.

Within that optional extension, three generations follow from the Fibonacci decomposition plus a direct propagation-channel postulate: $\varphi^n = \varphi^{n-1} + \varphi^{n-2}$ gives two predecessor channels (2D solution space), and the direct rung adds $N_{\text{gen}} = 2 + 1 = 3$ sub-rung channels (`foundations/three-generations.md` §2.3; mechanism Hypothesized, rung placements Mapped—ledger). The catalog's boundary pattern: the lightest state of each terminated sector sits at a half-rung, while interior stable states sit at integer rungs.

| Sector edge | State | Half-rung | Residual |
|-------------|-------|-----------|----------|
| Lepton tower, lightest | e | 26.5 (Yukawa ladder) | 1.4% |
| Lepton tower, heaviest | τ | 9.5 (Yukawa ladder) | +1.2% (v0-pole frame; top-anchored +0.5%, MS-bar-top −4.8%) |
| Quark sector, heaviest | b | 8.5 (Yukawa ladder) |—|
| Hadron tower, lightest | π | 95.5 | 3.9% |
| Confinement boundary | Λ_QCD | 94.5 | 2.1% |
| Baryon tower, lightest | p, n | 91.5 | 1.9–2.0% |
| Quark sector, lightest | d | 102.5 | 0.9% |

Interior stable states at integer rungs: μ (96.000), J/ψ (89), D (90), Σ (91), Z (82); the mean |residual| of the sector-edge set is 0.038 rungs (`foundations/rung-offset-mechanism.md` §4.1). The half-rung is the antinode of the fundamental mode of the terminal cell (pool-cell quantization), and the identification of the catalog's sector edges with those sine modes is Hypothesized within the conditional extension, not Derived. The free-wake test is likewise extension-specific: T10-E1 places the terminal-cell extremum at $u \approx -1.15$ ($\delta n \approx -0.65$), while the terminal-cell boundary conditions remain open.

### 1.5 What is not yet organized

Three gaps keep the force sector from being a closed account: the strong coupling runs 2.0× low, the Higgs mass is not predicted, and the quark hierarchy is off by a factor of ~20.

- $\alpha_s(m_Z)$: the framework's RGE running from $\alpha_{\text{GUT}}$ gives 0.058–0.061 against the measured 0.118—2.0× low; the required shift $\Delta b = 1.70$ is a beyond-SM deficit, **Mapped** per the Fit-Status Ledger, and the particle content that supplies it is not determined (`foundations/deriving-remaining-gaps.md` §1).
- $m_H$: not predicted; the Higgs sits at $n = 81.291$ with no special point (10.6% residual in the catalog).
- Quark hierarchy: the bare Fibonacci spacing gives $m_c/m_u = 29$ ($\varphi^7$) against the observed 588—a factor of ~20 that survives CKM mixing and SM RGE running (`foundations/three-generations.md` §3).
- Charge magnitude: no derivation (open, §1.3).
- Compact-loop mass selection: the conditional two-fluid ring retains many stable primitive modes per cascade cell and a coefficient-sensitive low-winding branch; a physical particle selector remains open (`foundations/qi-loop-mass-cascade.md` §5).

---

## 2. How energy pools on the lattice

Energy pooling is discussed here in two layers. The canonical solver evolves
$E_Y$ and $E_I$ with gated rank-one conversion and supplies no complex phase,
propagation direction, compact coordinate, or NLS self-interaction. The
standing-wave pooling construction below is a **Hypothesized** conditional
complex-field/NLS extension.

### 2.1 From interference to soliton (Hypothesized conditional extension—August 2026)

The following construction is conditional and is the same optional
focusing-NLS extension specified in
`particles/cassi-yang-yin-particles.md` §5. It adds complex fields, a selected
coordinate $s$, phase, counterpropagation, and attractive NLS self-interaction
to the canonical density state.

$$I_\Psi(s) = |\Psi_Y + \Psi_I|^2
 = A_Y^2 + A_I^2 + 2A_Y A_I \cos(2ks)$$

Within this extension, selecting the amplitude ratio $A_I/A_Y = \varphi^{-1}$
gives the contrast

$$\frac{I_{\Psi,\max}}{I_{\Psi,\min}} = \varphi^6 \approx 17.94,$$

and the selected NLS trial uses the peak-intensity rule

$$
\boxed{I_{\Psi,\mathrm{peak}} = A_Y^2\varphi^2 > \theta_{\mathrm{cond}}.}
$$

A compatible bright-soliton trial is

$$
\Psi(s,t)=\sqrt{\frac{2\mu}{g}}\,
\operatorname{sech}\!\left[
\frac{\sqrt{2m_{\mathrm{eff}}\mu}}{\hbar_{\mathrm{eff}}}
(s-s_0-v_gt)\right]e^{i(k_0s-\omega_0t)}.
$$

The threshold is an experiment-selected localization label within this
extension. The corresponding NLS intensity norm is

$$
\boxed{M_\Psi = \int_{-\infty}^{+\infty} |\Psi(s,t)|^2\,ds
 = \frac{4\hbar_{\mathrm{eff}}}{g}
\sqrt{\frac{\mu}{2m_{\mathrm{eff}}}}.}
$$

It is an extension norm, not a canonical mass or density integral.

### 2.2 From assigned masses to ladder (Empirical)

Given an assigned or observed mass, the cascade bookkeeping places it on the ladder by $n = \log_\varphi(M_{\text{Pl}}/m)$ with $M_{\text{Pl}} = 1.2209\times10^{19}$ GeV, and the full PDG scan yields the 38-state catalog (Empirical). The anchor rungs are EW at 80, QCD at 95, and the Bohr radius at 117. The catalog's statistics, stated plainly: the mean distance to the nearest integer or half-integer rung is $\bar{s} = 0.118$ against 0.125 uniform, and 42% of states sit within 0.10 rungs of a special point against 40% uniform—**the full catalog shows no clustering at $\{0, \tfrac{1}{2}\}$ beyond chance**. The muon's placement ($n = 96.000$, 0.01%) is the only individually improbable event, at ~0.8% over the catalog; borderline, worth taking seriously, not yet evidence (`foundations/rung-offset-mechanism.md` §3). Frame choice is itself open: the muon is the dual citizen, 96.000 on the Compton ladder and 15.39 on the Yukawa ladder, and no principle selects which ladder a state belongs to (§4.1).

### 2.3 The lattice frame

Within the conditional 3D geometry extension, the cascade is read as a 1D slice of a 3D checkerboard; in that reading, the checkerboard's nodes and voids give a second, sharper ruler for masses.

The coordinate-defined field expression is

$$B(x,y,z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z)$$

The product above is Derived as a coordinate-defined algebraic field expression; its physical interpretation as a universal 3D bubble lattice at every rung is **Hypothesized—August 2026** (`foundations/bubble-lattice-fabric.md`). The ladder $\ell_n = \ell_{\text{Pl}}\,\varphi^n$ is scale bookkeeping. Within the conditional complex-field extension, the wake pair closes each rung, $\Lambda_Y + \Lambda_I = \ell_{n+1}$ (prediction #43), and its envelope places bubbles at $m\,\ell_{n+1}$ and voids at $(m+\tfrac{1}{2})\ell_{n+1}$ (prediction #44); the golden-angle closure ladder is $\{5, 13, 34, 89, 233, 610\}$ (prediction #45). These wake and envelope relations are extension diagnostics. In this frame the envelope positions read as a mass law: a mass assignment at node $k$ of rung $j$ sits at $n = j + \log_\varphi k$, i.e.

$$\boxed{m = \frac{m_j}{k}, \qquad k \in \mathbb{Z}_{>0}\ \text{(node)}, \qquad k \in \mathbb{Z}_{\ge 0}+\tfrac{1}{2}\ \text{(void)}}$$

with $m_j = M_{\text{Pl}}/\varphi^j$ the rung mass. The law is **Hypothesized** and null against the same-density baseline (T9: mean $s = 0.0147$ vs $0.0154 \pm 0.0019$, $p = 0.35$)—it is a mass-frame restatement whose weight rests on individual placements. The sharpest individual readings: $\mu = m_{96}$ (0.01%), $\Xi^* = m_{89}/2$ (0.13%), J/ψ $= m_{84}/11$ (0.14%), $e = m_{102}/11.5$ (0.19%—the sharpest **void** reading: the $k = 11.5 = 23/2$ sub-lattice void at $n = 107.075$, inside the electron's own cell $[107, 108]$), and $u = m_{99}/11.5$ (0.40%—the same void family, three rungs up the cascade).

### 2.4 The pooling dynamics (Hypothesized conditional extension—August 2026)

The standing-wave crossing point and its pooling probes belong to the same conditional complex-field/NLS extension. The descent that would feed that crossing remains an open dynamical question.

Within the conditional extension, the coherent-limit interference extremum is pinned at the first envelope zero, $u = 1 - \log_\varphi 2 = -0.4404$—0.06 rungs above the naive half-rung—and the probe measures how a relative wake phase $\psi$ shifts it (analytic, PDE-verified to $10^{-3}$ rungs):

$$\boxed{\delta n(\psi) = 0.060 - 0.204\,\psi \ \text{rungs}, \qquad A_0 = 1.5 - \log_\varphi 2 = 0.0596, \qquad B_0 = 1/\omega_0 = 0.2044, \qquad \omega_0 = 2\pi\varphi\ln\varphi = 4.892\ \text{rad/rung}}$$

Within the conditional extension, the coherent crossing sits at $\psi^* = A_0/B_0 = 0.2941$ rad, where $\delta n = 0$. The descent probes then test whether energy flows down the spiral into pools: (T11) the real extension amplitude $\Psi_Y^{\mathrm{ext}}$ gives a deposit $D_{\Psi_Y}^{\mathrm{ext}}(x)=\int_0^t[(\Psi_Y^{\mathrm{ext}}(x,\tau))^2-(\Psi_Y^{\mathrm{ext}}(0,\tau))^2]\,d\tau$ that stays pinned at the standing crossing ($+0.060 \pm 0.01$ rungs for $u \le 0.2$) under advective drag, while the mass-like conversion pool responds weakly ($\Delta\delta n \approx 1.6\,u$ rungs, $u \le 0.1$); (T12) closure-crossing emission is in phase with near-static pools ($u \le 1.5\%$ of the wave speed); (T13) conversion alone transports energy **outward**, down the cascade, at $u_{\text{flux}} \approx 0.01$–$0.1\%$ of the wave speed—the expansion trickle, with no measured inward descent. The standing probes support the outward conversion result; a potential-gradient probe for inward descent remains absent.

### 2.5 The pools that are nuclei

Between the muon and the electron the ladder holds no particle at all—only the nuclear binding energies live there, and the shell structure that organizes them is still Hypothesized.

The band $n = 97$–$106$ (masses 65.3 MeV down to 0.86 MeV) is a lepton desert: confinement floors the hadron spectrum at the pions ($n \approx 95.4$–$95.5$), and only the muon ($n = 96.000$) and electron ($n = 107.08$) bracket it. Its only occupants are nuclear binding energies: total binding energies span $n \approx 98.7$–$104.0$ (⁴He 28.3 MeV to the deuteron 2.22 MeV), and the binding-per-nucleon plateau (7.07–8.79 MeV/nucleon, $A = 4$–$60$) spans $n \approx 101.2$–$101.6$, astride the half-rung 101.5 (⁴He 0.12 rungs above it, ⁵⁶Fe 0.33 rungs below)—a loose structural observation, not a placement (`foundations/deriving-remaining-gaps.md` §4.3). The nuclear magic numbers are **Hypothesized**, and the closure arithmetic is open: 0 of 7 rows close (cumulative sums 8, 20, 38, 54, 78, 108, 144 vs the claimed 2, 8, 20, 28, 50, 82, 126); the independent $\varphi$-power level-spacing prediction $\Delta E_{j \to j+1} \propto \varphi^{-j}\Lambda_{\text{QCD}}$ remains testable, as does the island of stability at $N = 184$, $Z \approx 114$–$120$ (`hypotheses/nuclear-magic-numbers.md` §4, §6).

---

## 3. Neutrons, protons, and electrons

Ordinary matter is three mass-assigned pools—two heavy baryons that differ by a hair in mass and one light lepton—and the cascade bookkeeping records where each sits, while the conditional particle interpretation remains open.

### 3.1 The baryon pair at rung 91.5

The proton sits at $n = 91.462$ ($\delta n = -0.038$ from the half-rung) and the neutron at $n = 91.459$ ($\delta n = -0.041$): the lightest baryon sector-edge pair, both within ~2% of the half-rung 91.5 ($s = 0.038$ and 0.041 rungs, residuals 1.9% and 2.0%). The corresponding $\psi$ labels belong to the conditional complex-field extension. The proton's Compton-ladder placement is $n=\log_\varphi(\lambda_p/\ell_{\text{Pl}})=91.46$ with $\lambda_p=\hbar c/m_p$ (`foundations/proton-coherence-budget.md` §1); interpreting the proton as a condensed standing wave at that step belongs to the conditional complex-field/NLS extension. The quark content uud/udd has **no Cassi-structural statement anywhere** in the framework—stated plainly, it is open.

### 3.2 Proton stability

The proton's stability is a coherence budget: dephasing requires the simultaneous loss of coherence at every supporting rung, and the product of per-rung dephasing probabilities is exponentially suppressed.
Using the same position-dependent profile with $\delta=3$:
For an integer endpoint $N$, the literal indexed product is

$$N_{\text{max}}(N) = \prod_{i=0}^{N} \frac{1}{1-q_i^{\mathrm{cascade}}}
= \varphi^{\,N(N+1)/2+\delta(N+1)}.$$

At the registered budget coordinate $N_p^{\mathrm{budget}}=91.46$, no noninteger upper-bound product is implied; use the continuous continuation

$$\boxed{N_{\text{max}}(N_p)
=\varphi^{\,N_p(N_p+1)/2+\delta(N_p+1)}
\big|_{N_p=91.46,\ \delta=3}
=\varphi^{4505.5758}\approx\varphi^{4506}\approx10^{942}\ \text{cycles}}$$

At $N_p^{\mathrm{budget}}=91.46$, the product gives a conditional $\sim10^{942}$-cycle budget. Converting it to $\sim10^{910}$ years additionally declares one independent transition trial per Compton cycle; the field action supplies no fluctuation law or matrix element for that map. The distinct Planck-to-proton scale circuit has zero total scale-number flow and nonzero relative current. Charged coherent and one-way open endpoint equations are explicit, while their physical normalization and scale tension remain open. The smooth zero-Chern endpoint sector has no finite Derrick radius; an independent core, supported proton solution, quantum numbers, and winding-changing rate remain required (`foundations/endpoint-link-and-localization-boundary.md`; `foundations/proton-coherence-budget.md` §10). Current null searches are compatible with these candidates and select neither one.

### 3.3 The neutron

The neutron is the neutral sibling at $n=91.459$. Its $\sim1.3$ MeV mass excess over the proton is **not derived**: the isospin formalism is explicitly open—"isospin dependence (proton vs. neutron cascade offset) needs a formalism for how the Yang-Yin ratio $r=E_Y/E_I$ couples to isospin $T_z$" (`hypotheses/nuclear-magic-numbers.md` §7). Standard $\beta$-decay uses the established weak-interaction matrix element; no Cassi correction or independent rate is selected (`foundations/proton-coherence-budget.md` §6). Its proposed nuclear role is the Hypothesized magic-number shell structure and island-of-stability mapping, with closure arithmetic open (§2.5).

### 3.4 The electron

The electron carries three placements, in three frames:

1. **Compton near-miss.** On the $M_{\text{Pl}}$-anchored ladder, $n = 107.079$—3.9% off rung 107, the rung of the reduced Compton wavelength ($\ell_{107} = 3.72\times10^{-13}$ m vs $\hbar/m_ec = 3.86\times10^{-13}$ m, 3.7% off). Not a catalog hit, unlike the muon (0.01%) and J/ψ (1.0%).
2. **Yukawa half-rung.** In the mass-generation frame, $n = \log_\varphi\big((v_0/\sqrt2)/m_e\big) = 26.47 \approx 26.5$, 1.4%—but class **E**: the half-step is solved from the observed mass, a fit, not a prediction (`foundations/deriving-remaining-gaps.md` §2.2). Within the conditional extension, pool-cell quantization assigns half-rung positions wave-mechanical status through a fundamental-mode antinode; it leaves the cell placement open, so why $[26, 27]$ and not $[25, 26]$ remains empirical.
3. **Lattice void.** The sharp placement: $e = m_{102}/11.5$ at 0.19%—the sharpest void reading in the catalog, the $k = 11.5 = 23/2$ sub-lattice void at $n = 107.075$ inside the electron's own Compton cell $[107, 108]$. The lepton tower terminates at a void rather than a node, and the up quark sits on the same void family three rungs up ($u = m_{99}/11.5$, 0.40%): the two lightest first-generation fermions share the void index.

Within the conditional complex-field extension, the implied wake phase is $\psi = (A_0 - \delta n)/B_0 = -0.095$ rad (the catalog table rounds to −0.09); the canonical density state has no phase variable.

### 3.5 Differences and purposes

| Property | Proton | Neutron | Electron |
|----------|--------|---------|----------|
| Rung $n = \log_\varphi(M_{\text{Pl}}/m)$ | 91.462 | 91.459 | 107.079 |
| Sector | baryon tower | baryon tower | lepton tower |
| Placement | sector-edge pair at 91.5 (1.9%) | sector-edge pair at 91.5 (2.0%) | sharpest void, $k = 23/2$ (0.19%) |
| Stability channel | coherence budget (Q9) | no framework account—β-decay open | no framework account |
| Charge | no canonical charge derivation; optional gauge extension open | no canonical charge derivation; optional gauge extension open | no canonical charge derivation; optional gauge extension open |
| Role | anchor pool of baryonic matter | neutral sibling; lets nuclei grow beyond the proton (Hypothesized) | lightest charged pool; lattice-void placement, with charge complementarity open |

The synthesis reading, explicitly this document's reading rather than a derivation: the proton is the coherence-robust anchor pool that concentrates baryonic matter at its rung; the neutron is the neutral pool that lets nuclei grow beyond the proton, via the magic-number shells (Hypothesized); the electron is the lightest charged pool placed at the lattice void. Charge complementarity and the mass hierarchy among the trio are open content.

---

## 4. What the framework does not yet say

The inventory of what remains open is short and precise: the masses themselves, the neutron's extra mass, charge, atomic binding, β-decay, the strong-coupling gap, the activation steps, and the descent.

- **The masses themselves.** $e$, $p$, $n$ are all class **E** in the ledger ($m_e$: partial, ~25% off at integer rungs; $m_p$: not derivable, QCD scale). The ladder places them; nothing generates them.
- **The n−p mass difference** (~1.3 MeV). Isospin $T_z$ coupling is open (§3.3).
- **Charge magnitude and complementarity.** No derivation anywhere (§1.3).
- **EM binding in Cassi terms.** Atomic orbitals at rung 117 are reproduced by conventional DFT numerics only (`particles/dft-benchmarks.md`); the benchmark carries implementation and atomic-reference evidence, while an analytical atomic potential from the canonical two-fluid dynamics remains open.
- **β-decay and neutron stability.** Explicitly outside the framework (§3.3).
- **The α_s gap.** 2.0× low; $\Delta b = 1.70$ Mapped; the mechanism and particle content are open (§1.5).
- **The activation steps.** Empirical catalog; no selection principle (§1.1).
- **The descent/pooling dynamics.** Conditional standing-wave probes report outward conversion flux and no measured inward descent; a potential-gradient probe for inward descent remains absent (§2.4).
- **Proton decay.** The SU(5)-type prediction (#10) and the coherence budget disagree; the framework does not resolve them (§3.2).

---

## 5. Epistemic boundaries

**Derived conditional.** Conditional on the Hypothesized flux-tube application, uniform cross-section, one-cell assignment, and pitch convention, tube extensivity gives the confinement force $F \approx \sigma_{\text{tube}} r$; the tension value $\sigma_{\text{tube}} \approx 2\pi E_{95}^2 = 2\pi\varphi^{-190}M_{\text{Pl}}^2 \approx 0.184\ \text{GeV}^2$ is Hypothesized per that doc. The coherence-budget product structure is combinatorial, with the rung exponent Mapped in the ledger. The coordinate-defined product $B(x,y,z)$ is algebraic (Derived conditional on declared coordinates); its physical 3D bubble-lattice identification is **Hypothesized—August 2026** (`foundations/bubble-lattice-fabric.md`). The 38-state catalog numbers are Empirical. The conventional gauge formulas $\sin^2\theta_W = \varphi^{-3}$ and $\alpha_{\text{GUT}} = \varphi^{-3}/4\pi$ are Derived within the optional gauge extension; their Cassi link is Hypothesized. $G_{\text{eff}}$ and the $\kappa_s$ scale retain the statuses recorded in `foundations/unified-lagrangian.md` ($\kappa_s$ coefficient Hypothesized). The optional $g(q)$ transmission is Asserted, and the canonical conversion gate is the openness $(1-q)$; the physical binding map and tube permanence remain Hypothesized.
**Hypothesized—August 2026.** The conditional complex-field/NLS extension
supplies the standing pattern, contrast $\varphi^6\approx17.94$, condensation
threshold, NLS norm $M_\Psi=\int|\Psi|^2\,ds$, and selected amplitude-ratio
stability condition (`particles/cassi-yang-yin-particles.md` §4–7).
Experiment 8v2 is a numerical receipt for that extension. Its relative-wake
phase-lag curve $\delta n(\psi)=0.060-0.204\psi$ with exact $A_0$, $B_0`;
wake closure $\Lambda_Y+\Lambda_I=\ell_{n+1}$ (#43); and envelope checkerboard
(#44) are extension diagnostics. The canonical density equations supply none
of these phase, propagation, selected-coordinate, or NLS structures.

**Hypothesized.** Three generations ($N_{\text{gen}} = 3$; rung placements Mapped—ledger). Sector-edge selection at half-rungs (T10-E1: the free wakes do not produce the placement; boundary conditions open). The lattice mass law $m = m_j/k$ (T9 null—weight rests on individual placements). Nuclear magic numbers and the island of stability (closure arithmetic open). The neutron's nuclear role. The GUT breaking chain from continued-fraction truncations.

**Open.** Everything in §4: the masses, the n−p difference, charge, atomic binding, β-decay, the $\alpha_s$ gap, the activation steps, the descent, and the proton-decay tension.

---

## References

- `foundations/rung-offset-mechanism.md`—38-state catalog, conditional $\delta n(\psi)$ phase-lag curve, sector-edge selection, lattice frame, T9–T13 probes
- `foundations/quark-confinement.md`—QCD at step 95; conditional Qi flux-tube application; coherence-persistence estimate
- `foundations/proton-coherence-budget.md`—coherence budget $N_{\text{max}} \approx \varphi^{\,n(n+1)/2+\delta(n+1)} \approx \varphi^{4505.6}$; annihilation pathway; β/α boundary
- `foundations/dimensionful-cascade.md`—the $\varphi$-ladder; EW/QCD/Bohr anchors; activated steps
- `foundations/three-generations.md`—$N_{\text{gen}} = 3$ from Fibonacci partitioning; quark-hierarchy gaps
- `foundations/wake-geometry.md`—wake pair, envelope, closure ladder, mass scan
- `foundations/unified-lagrangian.md`—assembled action; gauge couplings; $\kappa_s$
- `foundations/cassi-theory-reference.md`—compact reference (Qi gate, $G_{\text{eff}}$, cascade, coherence budget)
- `foundations/deriving-remaining-gaps.md`—electron mass class E; activated-step catalog; lepton desert
- `particles/cassi-yang-yin-particles.md`—conditional Hypothesized soliton formation from complex-field/NLS interference
- `particles/dft-benchmarks.md`—conventional DFT numerics for atomic orbitals; benchmark evidence boundary
- `hypotheses/nuclear-magic-numbers.md`—magic numbers, island of stability, isospin open
- `standard-model/su2-gauge-extension.md`—optional gauge extension: U(1) $\cong$ SO(2) current, SU(2) promotion, Weinberg angle
- `standard-model/gut-embedding.md`—breaking chain from continued-fraction truncations
- `open-questions-cassi-answers.md`—Q8 (confinement), Q9 (proton lifetime)
- `predictions/falsifiable-predictions.md`—#10, #43, #44, #45, #46
- `parameter-inventory.md`—parameter classes (E); Fit-Status Ledger
- `cassi-physics.md`—physics guide; gravitational coupling and proton stability

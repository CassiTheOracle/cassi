# Cassi Parameter Inventory

## Status: Reference—August 2026

## Classification Legend

| Label | Meaning | Count |
|-------|---------|-------|
| **F** | **Fundamental axiom**—the declared scale-separation input for the framework | 1 |
| **D** | **Derived**—mathematical consequence of $\varphi$ and the PDE structure, zero freedom | 7 |
| **C** | **Convention / calibrated model output**—solver conventions and calibrated model outputs whose provenance lies beyond $\varphi$ + the canonical PDE; distinct from the epistemic tier **Calibrated** | 5 |
| **M** | **Mapped**—selected, fit-dependent, or optional-extension quantities whose physical identification lies beyond $\varphi$ + the canonical PDE | 10 |
| **E** | **External / empirically determined**—empirical or inherited quantities supplied by calibration or external physics, plus lattice parameters not yet derived from $\varphi$ | 9 |
| **I** | **Initial condition**—free initial values that evolve dynamically, not fixed by theory | 7 |
| **N** | **Numerical**—computational parameters with no physical significance | 8 |
| | **Total** | **47** |
Counts are mechanical: count one primary parameter-table row per quantity in §§1–6 with an explicit F/D/C/E/M/I/N class symbol; the §3.4 recap is not counted again. The classification legend, §7 summary, canonical symbol table (§9), fit-status ledger (§10), and descriptive-only solver status entries are excluded.

---

## 1. The Single Postulate

| Parameter | Value | Class | Status |
|-----------|-------|-------|--------|
| $\varphi = (1+\sqrt{5})/2$ | $1.618033989\ldots$ | **F** | Mathematical constant, the universal scale-separation axiom |

---

## 2. Derived Constants ($\varphi$-Powers)

Section 2 records the dimensionless quantities fixed as $\varphi$-power identities or conditional derived values. Other dimensionless couplings and normalizations retain their registered C/M/E/etc. status in §§3–8; the inventory's class counts account for those rows.

### 2.1 Pure Powers (Mathematical Identities)

| Parameter | Expression | Value | Class | Derivation |
|-----------|-----------|-------|-------|-----------|
| $\varphi^{-1}$ | $\varphi - 1$ | $0.618033989$ | **D** | Identity: $\varphi^2 = \varphi + 1$ |
| $\varphi^{-2}$ | $1 - \varphi^{-1}$ | $0.381966011$ | **D** | $= 2 - \varphi$ |
| $\varphi^{-3}$ | $(\varphi-1)/(\varphi+1)$ | $0.236067978$ | **D** | Fixed-point imbalance $\alpha_0=\pi/\rho$ |
| $\varphi^{-6}$ | $(\varphi^{-3})^2$ | $0.055728090$ | **D** | Square of the fixed-point imbalance $\alpha_0^2$ |
| $\varphi^{4}$ | $\varphi^3 + \varphi^2$ | $6.854101966$ | **D** | Four-interaction scale |
| $\varphi^{5}$ | $\varphi^4 + \varphi^3$ | $11.09016994$ | **D** | Wu Xing cycle scale |
| $\varphi^{6}$ | $\varphi^5 + \varphi^4$ | $17.94427191$ | **D** | Qi-gravity coupling $\xi$ |

### 2.2 Physical Couplings and Conditional Extensions

| Parameter | Expression | Value | Class | Provenance / physical role |
|-----------|-----------|-------|-------|--------------------------------------|
| $\xi$ (Qi-gravity) | $\varphi^{6}$ | $17.94427191$ | **C** | Calibrated MW pin; $\varphi^6$ is a Derived conditional identity once the quadratic field-coupling input is supplied (ledger row 528) |
| $\sin^2\theta_W$ (at $m_Z$) | $\varphi^{-3}$ (at the selected boundary; exact at $\mu_* = 233$ GeV) | $0.23607$ | **M** | Selected electroweak boundary; the current gauge action leaves $g$ and $g'$ independent. The curvature–orbit candidate requires an added field-space metric and orbit-matching rule; the full VEV mass matrix has a photon null direction (`standard-model/su2-gauge-extension.md` §3.2.1, `computations/weinberg_coupling_origin_audit.py`). The $\mu_*$ crossing is Calibrated (ledger row 490) |
| $\sin^2\theta_W$ (at $\mu_* = 233$ GeV) | running MS-bar angle crosses $\varphi^{-3}$ | $0.23607$ | **C** | Calibrated running output where the $\varphi$-point value is realized; the angle runs upward, so the GUT scale is not the boundary (ledger row 520) |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3} / 4\pi$ | $1/53 \approx 0.01887$ | **M** | Selected gauge-boundary assignment; the coupling is free in SU(5)/SO(10), and SM running does not realize this value |
| $m_W/m_Z$ | $\sqrt{1-\varphi^{-3}}$ | $0.874$; $0.878$ with $\rho$ | **M** | Conditional mass-ratio construction from the selected Weinberg-angle boundary; the $\rho$ correction is an extension input; candidate for FCC-ee |
| $\alpha_{\text{em}}^{-1}(m_Z)$ | from $\varphi^{-3}/(4\pi)$ at $M_{\text{GUT}}$ | $161$ (vs measured $128.9$) | **M** | Conditional running output from the selected $\varphi^{-3}$ gauge boundary; the SM value $128.9$ closes via $\alpha(0)+\Delta\alpha$ (`standard-model/sm-radiative-corrections.md` §3–4) |
| $\delta_{\text{CKM}}$ (CP phase) | $\pi\varphi^{-2}$ | $1.199$ rad $(68.7^\circ)$ | **M** | Selected CKM-phase map via the unitarity triangle from $\varphi$-scaled CKM elements; the four-candidate scan and promoted winner are recorded in ledger row 512 |
| $\chi_Y$ (Yang chemotaxis) | $\chi/\varphi$ | $\chi \cdot 0.618$ | **E** | Empirical $\chi$ inherited by the ratio; $\chi_Y$ is the algebraic conversion of the calibrated mobility (ledger row 517) |
| $w_0$ (DE equation of state) |—| $-0.87$ | **C** | ODE calibrated to the hardcoded `TARGET_W0` (DESI-anchored; ledger §10 row 496); 2σ baseline from DESI $w_0 \approx -0.75 \pm 0.06$ ($3.6\sigma$ at fixed $r_0$ with the B2 coupling; $r_0$ re-tuning closed negatively under the stable realization—12) |
| $w_a$ (DE running) |—| $+0.012$ (with $\xi = \varphi^6$); $-0.38$ (with the ratified coupling, B2—unstable); **$(w_0, w_a) = (-1, 0)$ pure-Λ window (stable realization—10/12)** | **C** | Yang-fraction-weighted $\xi = \varphi^6$ prediction at the Calibrated $w_0$ baseline (ledger §10 row 496); verified via `two-fluid/calibrate_initial_ratio_xi_v2.py`; $2.7\sigma$ baseline; $1.25\sigma$ with the coupling (B2, 08 §C.6—unstable); $4.17\sigma$/$2.61\sigma$ for the stable realization's pure-Λ fit (12) |
| $n_s$ (spectral index) |—| $0.9691$ | **M** | From $n_s = 1 - 2\varphi^{-1}/N_e$ with $N_e = 40$—a Mapped start-threshold window (ledger §10 row 501); the trajectory does not reproduce the closed form |
| $r$ (tensor-to-scalar) |—| $0.0075$ ($12/N_e^2$ at $N_e = 40$—Mapped window, ledger §10 row 495; the 0.003 reading needs $N_e = 63.2$, outside the window) | **M** | Formula-consistent at the ledgered window; survives BK18; the trajectory's $r$ (0.060) is excluded |
| $K_{fw}$ (Wu Xing coeff) | $\varphi^{-1}$ | $0.618$ | **M** | Optional selected five-cycle coefficient; the $\varphi^{-1}$ identity is Derived conditional on that extension; Water damps Fire |
| $K_{ring}$ (ke ring gain) | $\varphi^{-3}$ | $0.236$ | **M** | Optional selected five-cycle control-ring gain; the $\varphi^{-3}$ identity is Derived conditional on that extension (`foundations/wu-xing-cycle-structure.md` §2.3) |
| $\kappa_s$ (sector coupling) | $\varphi^{-6}/v_0^2$ | $0.92$ TeV$^{-2}$ | **M** | Optional selected Dirac↔two-fluid sector-coupling candidate; $\varphi^{-6}/v_0^2$ is a formal $C=1$ arithmetic scale conditional on the sector construction, not a physical $\kappa_s$ or equilibration timescale; the optional projection bracket is dimensionally incomplete (`foundations/sector-coupling-derivation.md`) |

## 3. PDE Solver Parameters (Numerical Conventions)

These four named entries describe solver conventions or empirical/optional
couplings. They carry no fundamental-constant status. The canonical solver
also exposes $D$ as scalar density diffusion; its run values are listed in
§6 with the other numerical controls. The implementation class default in
`two-fluid/cassi_two_fluid_3d_gpu.py` is $\lambda=0.02$. The C-class/framework
convention $\lambda=0.1$ is selected explicitly by named callers and receipts;
the cosmology, galaxy, atomic, and Mercury rows below use that convention,
while the separately listed Three-body run retains its recorded
$\lambda=0.01$ value. These solver choices are not hidden $\varphi$
derivations.
| # | Parameter | Value | Role | Status |
|---|-----------|-------|------|--------|
| 1 | $\lambda$ (conversion) | $0.1$ (named C-class convention) | $\varphi$-attractor timescale | **C**—asserted framework normalization/timescale convention. The implementation class default is $\lambda=0.02$; named calculations may pass $\lambda=0.1$. The cycle linkage $\lambda=1/(2w)$ at $w=5$ is **Hypothesized**, not derived; equal-and-opposite conversion, potential-coefficient normalization, and “one event per cycle” do not determine a rate or its units. All existing calculations conditioned on $\lambda=0.1$ retain that value; the Three-body row in §8 remains its recorded $\lambda=0.01$ case. |
| 2 | $\chi$ (chemotaxis) | $0.5$–$1.0$ | Density-focusing mobility | **Empirical**—no independent derivation |
| 3 | $c_s^2$ (sound speed) | $0.01$ | Effective pressure | **Empirical**—shared solver pressure coefficient; no independent microscopic derivation |
| 4 | $\nu$ (velocity viscosity) | $10^{-4}$–$10^{-3}$ | Shared-velocity dissipation | **Numerical**—solver-stability setting with no physical interpretation |

### 3.1 $\lambda$: Electroweak Consistency Check—solver convention; cycle linkage Hypothesized

The Lagrangian has the $\varphi$-attractor coupled to the Higgs quartic:

$$V_{\text{Higgs}} = \frac{g}{4}|\Psi|^4 + \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2$$

At the minimum $\Psi_0^2 = \varphi\Psi_1^2$, the field-space Hessian has two
eigenvalues that determine the physical scalar masses; they mix through the
off-diagonal term $g - 2\lambda\varphi$. The computation is in
`computations/sm_radiative_corrections.py` §5.5: with the fixed-point value
$g = \varphi^{-3} \approx 0.236$ (the fixed-point imbalance
$\alpha_0=\pi/\rho$) and $\lambda=0.1$ under the asserted solver convention,
the two eigenmodes of the $\varphi$-point potential are

$$m = 198.1\ \text{GeV}\quad\text{and}\quad169.2\ \text{GeV}.$$

Their geometric mean is $183.1\ \text{GeV}$, $46.2\%$ above the measured
$m_H=125.25\ \text{GeV}$. The harmonic, geometric, arithmetic, and
energy-weighted poolings are respectively $182.5$, $183.1$, $183.6$, and
$184.8\ \text{GeV}$; no simple pooling reproduces $m_H$, and the two modes
do not bracket it. The result is a consistency check of the selected
potential, not a Higgs-mass derivation.

The same one-loop receipt gives $\lambda(10^{10}\ \text{GeV})=0.0008$ and
$\lambda(M_{\text{Pl}})=-0.0116$ when $y_t$ is run; using the pole-$y_t$
sensitivity gives $\lambda(M_{\text{Pl}})=-0.0729$. The stability-line Higgs
mass is $129.0\ \text{GeV}$ at one loop and $129.2\ \text{GeV}$ at NNLO for
$m_t=172.69\ \text{GeV}$. These loop-level comparisons retain their
source-specific assumptions and do not derive $\lambda=0.1$ or $m_H$.

**Summary:** The Higgs route cannot derive $\lambda=0.1$ without fixing $g$;
the asserted solver convention gives a selected-potential mode check whose
values lie above the measured Higgs mass. The Wu Xing construction supplies a
**Hypothesized** cycle linkage only: $\lambda=1/(2w)=1/10$ at $w=5$
(`foundations/dimensionful-constants-status.md` §2.1,
`foundations/wu-xing-derivation.md` §7). Equal-and-opposite conversion,
potential-coefficient normalization, and “one event per cycle” do not derive
a rate or its units.

### 3.2 $c_s^2$ as an Empirical Solver Pressure

The PDE coefficient $c_s^2$ sets the effective barotropic pressure response
used by the named finite solvers. The regulated CassiFI quantum bridge derives
the centre-of-mass Schrödinger kinetic operator
$-\hbar^2\nabla^2/(2M)$, but it supplies no local barotropic closure for the
coarse real-density PDE.

The value

$$
c_s^2=0.01
$$

is therefore an empirical solver coefficient under the listed field and grid
normalizations. Atomic, galactic, and cosmological physical sound speeds
require their own constitutive matching even when a numerical receipt uses the
same solver value.

### 3.3 $\chi$: The Sector-Coupling Bridge; $D$ and $\nu$: Spatial Solver Coefficients

**$\chi$ (chemotactic mobility)** couples the two-fluid density gradient to the
gravitational potential:

$$\partial_t E_I \supset +\chi\,\nabla\cdot(E_I\nabla\Phi)$$

A proposed, optional Dirac-to-two-fluid projection ansatz introduces a formal
sector scale $\kappa_s$ in the unified Lagrangian:

$$\chi = \frac{\kappa_s}{m_e} \cdot \frac{\varphi^{-1}}{(1+\varphi)}$$

The sector construction supplies only a formal $C=1$ arithmetic scale
candidate, conditional on the external $v_0$ anchor and the stated rung
selection:
$\kappa_s = \varphi^{-6}/v_0^2 = 0.92$ TeV$^{-2}$ (see
`foundations/sector-coupling-derivation.md`). The optional projection bracket
is dimensionally incomplete, so no physical $\kappa_s$ or equilibration
timescale is established.
The as-written bridge above is dimensionally inconsistent as it stands—with
$\kappa_s = 0.92$ TeV$^{-2}$ and $m_e = 5.11\times10^{-4}$ GeV it gives
$\chi \approx 4\times10^{-4}$, not the calibrated $0.5$–$1.0$. The repaired
bridge

$$\chi = \frac{\mathcal{N}_{\text{pde}}\,\kappa_s\,\varphi^{-1}}{m_e(1+\varphi)}$$

needs the PDE normalization factor $\mathcal{N}_{\text{pde}} \approx 2.35\times10^{3}$
(solver conventions: grid $L=40$, $N=48$, $\Delta t=0.002$, $\rho_{\text{crit}}=\varphi$)—a
concrete computational follow-up, not derived here.

**$D$ and $\nu$ (scalar density diffusion and velocity viscosity)** are
numerical solver coefficients. In the canonical equations, $D\nabla^2E_{Y/I}$
acts on the density fields, while $\nu\nabla^2\mathbf u$ acts on the shared
velocity. `TwoFluid3DGPU` defaults are $D=0$ and $\nu=0.001$; named runs may
select nonzero $D$ or other viscosity values for their numerical regime. These
coefficients vary with solver resolution and timestep and have no
$\varphi$-derived or physical value in this inventory. An optional
amplitude/action extension may introduce a fourth-order coefficient
$\kappa_4$, which is separate from the canonical solver coefficients.

### 3.4 Summary: What These Parameters ACTUALLY Are

| Parameter | True status | If it's a constant, which one? |
|-----------|-------------|-------------------------------|
| $\lambda = 0.1$ | **C**—asserted solver normalization/timescale convention; the cycle linkage $\lambda = 1/(2w)$ at $w=5$ is **Hypothesized**, not derived. Equal-and-opposite conversion, potential-coefficient normalization, and “one event per cycle” do not determine a rate or its units; $m_H^2\varphi/4v_0^2 \approx 0.104$ remains a consistency check (§3.1) | The Higgs quartic's orthogonal mode coupling |
| $\chi \approx 1.0$ | **Formal bridge unresolved**—$\kappa_s = \varphi^{-6}/v_0^2$ is a formal $C=1$ arithmetic scale candidate only; the dimensionally incomplete projection leaves physical $\kappa_s$ and its equilibration timescale unresolved; PDE-normalization factor $\mathcal{N}_{\text{pde}}$ pending | $\chi = \mathcal{N}_{\text{pde}}\kappa_s\varphi^{-1}/[m_e(1+\varphi)]$ |
| $c_s^2 \approx 0.01$ | **Empirical**—shared solver pressure coefficient under the named normalizations | No $\varphi$ formula or quantum derivation |
| $\nu \sim 10^{-4}$–$10^{-3}$ | **Numerical**—shared-velocity viscosity setting | No $\varphi$ formula; implementation default $\nu=0.001$ |

The listed values across the cosmology, galaxy, and atomic rows are solver
consistency settings rather than universal physical constants. The same grid
scale $L=40$, $N=48$, $\Delta t=0.002$ is used in those rows, while the
separately recorded Three-body run uses $\lambda=0.01$ as shown in §8. If a
sector requires a different resolution or timestep, $D$, $\nu$, and $c_s^2$
must be retuned for that numerical regime.

---

## 4. External Constants—Attempted $\varphi$ Derivation

The registry's nine external/empirical entries comprise six dimensionful
constants inherited from standard physics, the empirically determined
along-string bubble period, the unset breath coupling/frequency, and empirical
$\chi_Y$. The six inherited constants are
dimensionful quantities that set the absolute scales of the universe:
$\{G, c, \hbar, m_e, m_p, \alpha_s(M_Z)\}$. $\varphi$ alone cannot determine a
dimensionful number—it constrains dimensionless ratios among these constants;
the additional entries retain the statuses shown below and in §2.2.

| Parameter | Symbol | Value | Class | Derivation Status |
|-----------|--------|-------|-------|-------------------|
| Newton's constant | $G$ | $6.67430\times10^{-11}$ m$^3$/kg/s$^2$ | **E** | Not derivable (dimensionful) |
| Speed of light | $c$ | $299792458$ m/s | **E** | Not derivable (unit conversion) |
| Planck constant | $\hbar$ | $1.054571817\times10^{-34}$ J$\cdot$s | **E** | Not derivable (unit conversion) |
| Electron mass | $m_e$ | $0.511$ MeV | **E** | Partial: $m_e \approx \varphi^{-26} v_0/\sqrt2$ (~25% off) |
| Proton mass | $m_p$ | $938$ MeV | **E** | Not derivable (QCD scale) |
| Strong coupling | $\alpha_s(M_Z)$ | $0.118$ | **E** | Partial: RGE from $\alpha_{\text{GUT}}$ needs particle content |
| Along-string bubble period | $P_\parallel(n)$ | $P_\parallel(285)=1$, $P_\parallel(142\text{–}168)=2$ | **E** | Empirically determined at two rungs; $n$-dependence not yet derived from PDE. Source: `foundations/bubble-lattice-fabric.md` §2.3 |
| Breath coupling / frequency | $A_B$, $\omega_Y$ | Unset | **E** | External dimensionful, unset—the breath term's constants (the localization—21, Hypothesized: the phases carried by each region's rung-clock; the composite reading, 21 §2.4, would eliminate them) |

### 4.1 $G$, $c$, $\hbar$—The Unit System

These three constants define the system of physical units. In natural units
($\hbar = c = 1$), $G = 1/M_{\text{Pl}}^2$ where $M_{\text{Pl}} \approx
1.22\times10^{19}$ GeV is the Planck mass. The question "derive $G$" is
equivalent to "derive $M_{\text{Pl}}$"—a single dimensionful scale.

$\varphi$ is dimensionless. It cannot determine a dimensionful scale without
a reference. The Cassi framework does not provide such a reference—every
other dimensionful quantity ($v_0$, $m_e$, $m_p$) traces back to $M_{\text{Pl}}$
or to the Higgs VEV, which is itself empirical.

**The ratio $v_0/M_{\text{Pl}}$** is dimensionless and approaches a $\varphi$-power:

$$v_0 \approx 246\ \text{GeV},\quad
M_{\text{Pl}} \approx 1.22\times10^{19}\ \text{GeV}$$

$$\frac{v_0}{M_{\text{Pl}}} \approx 2.0\times10^{-17} \approx \varphi^{-80}$$

$\varphi^{80} = 1.618^{80} \approx 5.2\times10^{16}$, giving
$v_0/M_{\text{Pl}} \approx 1/5.2\times10^{16} \approx 1.9\times10^{-17}$.
This is within $5\%$ of the observed $2.0\times10^{-17}$—a notable
numerical coincidence, but not a derivation.

### 4.2 $m_e$—The Electron Mass

In the Cassi Yukawa hierarchy (sm-from-phi.md §4.1), the electron Yukawa
coupling $y_e$ is a $\varphi$-power suppressed:

$$m_e = \frac{y_e v_0}{\sqrt{2}},\qquad
y_e = \varphi^{-n_e}$$

Solving for $n_e$ from the observed $m_e = 0.511$ MeV:

$$n_e = -\frac{\ln(\sqrt{2}\,m_e/v_0)}{\ln\varphi}
      = -\frac{\ln(1.414\times0.511\times10^{-3}/246)}{\ln 1.618}
      = \frac{12.75}{0.481} = 26.5$$

The half-integer exponent $26.5$ suggests $n_e = 26 + 1/2$. The pool-cell
quantization gives half-integer positions a wave-mechanical status (the
terminal-cell fundamental antinode, `foundations/rung-offset-mechanism.md`
§4.1), but the cell placement is empirical. The nearest
integer predictions:

| Exponent | $y_e$ | Predicted $m_e$ | Error |
|----------|-------|-----------------|-------|
| 26 | $\varphi^{-26} = 3.7\times10^{-6}$ | $0.64$ MeV | $+25\%$ |
| 27 | $\varphi^{-27} = 2.3\times10^{-6}$ | $0.40$ MeV | $-22\%$ |
| **Observed** |—| **$0.511$ MeV** |—|

**Status:** The electron mass is not derivable from $\varphi$ to better than
$25\%$ through a simple Yukawa $\varphi$-power. The Yukawa ratio $y_\mu/y_e$
deviation (predicted $\varphi^4\approx 6.85$, observed $207$) is even worse,
confirming that generation-mixing dynamics dominate the absolute Yukawa values.
On the $M_{\text{Pl}}$-anchored mass ladder ($n = \log_\varphi(M_{\text{Pl}}/m)$,
`foundations/wake-geometry.md` §3) the electron sits at $n = 107.08$—a 3.9%
near-miss of rung 107, the rung of the reduced Compton wavelength (3.7% off,
`foundations/dimensionful-cascade.md`)—a near-miss rather than a catalog hit,
unlike the muon ($n = 96.000$, 0.01%) and J/ψ ($n = 88.98$, 1.0%).

### 4.3 $m_p$—The Proton Mass

The proton mass is dominated by QCD: $m_p \approx 3\Lambda_{\text{QCD}}$,
where $\Lambda_{\text{QCD}} \sim 200$ MeV is the scale at which
$\alpha_s$ becomes strong. $\Lambda_{\text{QCD}}$ is determined by the RGE
running of $\alpha_s$ from $M_{\text{GUT}}$ to the IR:

$$\alpha_s^{-1}(\mu) = \alpha_{\text{GUT}}^{-1} + \frac{b_s}{2\pi}
                      \ln\frac{M_{\text{GUT}}}{\mu}$$

where $b_s$ is the QCD beta-function coefficient (depends on
$\#$ of quark flavors). Setting $\alpha_s^{-1}(\Lambda_{\text{QCD}}) = 0$:

$$\Lambda_{\text{QCD}} = M_{\text{GUT}}
                        \exp\!\left(-\frac{2\pi}{b_s\alpha_{\text{GUT}}}\right)$$

With $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi) \approx 1/53.2$ and
$b_s = 7$ (SM, 6 flavors):

$$\Lambda_{\text{QCD}} = M_{\text{GUT}}
                        \exp\!\left(-\frac{2\pi}{7}\times 53.2\right)
                      \approx M_{\text{GUT}}\,e^{-47.8}
                      \approx M_{\text{GUT}}\times 4.9\times10^{-21}$$

For $M_{\text{GUT}} \approx 10^{16}$ GeV:
$\Lambda_{\text{QCD}} \approx 10^{16} \times 4.9\times10^{-21}
                        \approx 5\times10^{-5}\ \text{GeV} \approx 50\ \text{keV}$

This is $4000\times$ too small. The proton mass would be $\sim 150$ keV,
not $938$ MeV—unless $b_s$ or $M_{\text{GUT}}$ are different.

**Status:** $m_p$ cannot be derived from $\varphi$ without fixing the
particle content (flavor number, SUSY threshold) that determines the QCD
beta function and the GUT scale.

### 4.4 $\alpha_s(M_Z)$—The Strong Coupling

The Cassi GUT coupling is $\alpha_{\text{GUT}}^{-1} = 4\pi/\varphi^{-3} \approx 53.2$.
The RGE running from $M_{\text{GUT}}$ down to $M_Z$:

$$\alpha_s^{-1}(M_Z) = \alpha_{\text{GUT}}^{-1} - \frac{b_s}{2\pi} \ln\frac{M_{\text{GUT}}}{M_Z}$$

with $\ln(M_{\text{GUT}}/M_Z) = \ln(10^{16}/91.2) \approx 32.3$.

With the SM $b_s = 7$ ($n_f = 6$):

$$\alpha_s^{-1}(M_Z) = 53.2 - \frac{7}{2\pi} \times 32.3 = 53.2 - 36.0 = 17.2$$

$$\alpha_s^{\text{SM}}(M_Z) = \frac{1}{17.2} \approx \mathbf{0.058}$$

This is $2.0\times$ smaller than the observed $0.118$ (not $11\times$—the
discrepancy resulted from an RGE sign error and an
incorrect $\ln$ factor of 37.8). The required effective beta function for
matching is:

$$b_{\text{eff}} = \frac{(53.2 - 8.47) \times 2\pi}{32.3} = \mathbf{8.70}$$

The shift from the SM: $\Delta b = b_{\text{eff}} - b_{\text{SM}} = 1.70$.

This modest shift requires approximately **1 vector-like colored fermion
pair** ($\Delta b = +4/3$) plus **2 colored scalars** ($\Delta b = +1/3$),
or **3 KK levels** of SM fields. The particle content between $M_Z$ and
$M_{\text{GUT}}$ is not determined by $\varphi$ alone—it is an additional
specification of the theory.

**Status:** $\alpha_s(M_Z)$ is $2.0\times$ too small given SM particle content.
The gap is narrowed from the $11\times$ discrepancy (which used a sign
error in the RGE). Closing the remaining $2.0\times$ gap requires $\Delta b =
1.70$ from new physics thresholds between $M_Z$ and $M_{\text{GUT}}$. The
specific particle content is not derivable from $\varphi$ alone. See
`foundations/deriving-remaining-gaps.md` §1 for the full analysis.

### 4.5 What IS Derivable from $\varphi$

Although absolute values are not derivable, the following DIMENSIONLESS
RATIOS involving these constants are $\varphi$-powers:

| Ratio | $\varphi$ Expression | Value | Error |
|-------|---------------------|-------|-------|
| $\alpha_0=\pi/\rho$ (at fixed point) | $\varphi^{-3}$ | $0.236$ | Exact |
| $v_0/M_{\text{Pl}}$ | $\varphi^{-80}$ | $1.9\times10^{-17}$ | $5.3\%$ (closest integer power) |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi)$ | $1/53.2$ | Exact (definition) |
| $\alpha^{-1}(\text{GUT})$ | $4\pi/\varphi^{-3}$ | $53.2$ | Exact (definition) |
| $m_{\nu_e}/m_e$ (seesaw) | $\varphi^{-11}$ | $0.013$ | Consistent |

The Cassi registry carries **9 external/empirical rows, 0 a-priori-derived**; the
current fit-status ledger contains 29 Calibrated or Mapped quantities. The six
inherited entries match the Standard Model's usual dimensionful input set
($\{G, c, \hbar, m_e, m_p, \alpha_s(M_Z)\}$); $\chi_Y$ carries the
empirical mobility input, while $P_\parallel(n)$ and $(A_B,\omega_Y)$ retain
their external statuses. Every dimensionful quantity must eventually be set by
experiment in a theory that lacks a mechanism for generating it.

**The registry currently marks 7 parameter rows as $\varphi$-derived—the seven
pure $\varphi$-powers.** Physical couplings that retain $\varphi$ expressions
are conditional, selected, calibrated, or empirical as detailed in §2.2; their
C, M, or E classes carry that provenance. Dimensional scale-setting is a
separate problem shared by all current physical theories.

## 5. Initial Conditions (Free Inputs)

Most initial-condition parameters, including the primordial Yang-Yin ratio
$r_0$, must be specified for any Cassi simulation. The conditional Wu Xing
construction selects the reference value shown below, while the canonical
two-fluid equations do not fix $r_0$. The optional $\lambda=1/(2w)$ cycle
linkage does not derive it. The remaining initial conditions are likewise not
fixed by the theory.

| Parameter | Typical Value | Class | Physical Meaning |
|-----------|--------------|-------|-----------------|
| $r_0 = E_{Y,0}/E_{I,0}$ | $0.0472$ (cosmology; $E_I/E_Y \approx 21$), $\varphi$ (atoms) | **I** | Initial Yang/Yin ratio; the displayed reference values are selected under the conditional Wu Xing gap construction $g = 1-\varphi^{-5}$ with the organizing-cycle choice $w=5$. The canonical two-fluid solver treats $r_0$ as an input; the optional $\lambda=1/(2w)$ linkage does not derive it. |
| $a_0$ | $0.01$-$1.0$ | **I** | Initial scale factor (expanding universe) |
| $H_0$ | $0.05$-$1.0$ | **I** | Initial Hubble parameter |
| $N_{\text{blobs}}$ | $2$-$3$ | **I** | Number of density peaks |
| $M_j$ (blob masses) | $200$ (typical) | **I** | Individual blob masses |
| $\sigma_j$ (blob width) | $3.0$-$4.0$ a$_0$ | **I** | Gaussian density profile width |
| $\mathbf{X}_j$, $\mathbf{V}_j$ | varies | **I** | Initial positions and velocities |

At the $\varphi$-fixed point, $r = \varphi$ and the specific initial ratio
becomes irrelevant—the conversion term $\lambda=0.1$ under the asserted solver
convention drives all configurations toward the equilibrium.
---


## 6. Numerical Parameters (No Physical Significance)

| Parameter | Typical Value | Class | Purpose |
|-----------|--------------|-------|---------|
| $N$ (grid points) | $32$, $48$, $64$ | **N** | Fourier grid resolution |
| $L$ (box size) | variable | **N** | Physical domain size |
| $\Delta t$ (timestep) | $0.0005$–$0.002$ | **N** | Numerical stability |
| $\epsilon_{\text{soft}}$ (Coulomb softening) | $0.02$ a$_0$ | **N** | Removes $1/r$ singularity |
| $\text{grav\_sigma}$ | $0.2$ | **N** | $|\nabla\Phi|$ saturation for N-body |
| $h_{\text{smooth}}$ | $0.1$ | **N** | Hubble parameter EMA smoothing |
| $D$ (diffusion) | $0.0$ | **N** | Solver parameter, not a physics constant: momentum-space numerical viscosity (the spectral $Dk^2$ damping). $D=0$ is the canonical conservation-exact setting—the per-cell closure's $\dot\rho \equiv 0$ premise verified exactly on the structured IC (44, `runs/44-truth-campaign/`; the D=0.001 diffusion was the entire Eulerian eroder); $D>0$ runs are the diffusion-bound conservative readings. The $\sigma_8$ target sits in no branch under either setting (44) |
| $\tau_{\text{qi}}$ (IIR memory) | $\varphi^{-1} \approx 0.618$ | **N** | Qi memory EMA timescale (reduced in slow regimes) |

## 7. Summary by Category

| Category | Label | Count | Description |
|----------|-------|-------|-------------|
| Fundamental axiom | **F** | 1 | $\varphi$ itself |
| $\varphi$-derived | **D** | 7 | The seven pure $\varphi$-power rows; conditional identities in §2.2 retain their stated algebraic expressions and provenance |
| Convention / calibrated model output | **C** | 5 | $\lambda$, $w_0$, $w_a$, $\xi$, and $\sin^2\theta_W(\mu_*)$—solver convention, calibrated outputs, and calibrated physical pin |
| Mapped quantity | **M** | 10 | $\sin^2\theta_W(m_Z)$, $\alpha_{\text{GUT}}$, $m_W/m_Z$, $\alpha_{\text{em}}^{-1}(m_Z)$, $\delta_{\text{CKM}}$, $K_{fw}$, $K_{ring}$, $\kappa_s$, $n_s$, and $r$—selected boundaries, optional-extension quantities, and mapped windows |
| External constant | **E** | 9 | $G$, $c$, $\hbar$, $m_e$, $m_p$, $\alpha_s(M_Z)$, $P_\parallel(n)$, $(A_B,\omega_Y)$, and $\chi_Y$ |
| Initial condition | **I** | 7 | $r_0$, $a_0$, $H_0$, $N_{\text{blobs}}$, $M_j$, $\sigma_j$, and $\mathbf{X}_j/\mathbf{V}_j$ |
| Numerical parameter | **N** | 8 | $N$, $L$, $\Delta t$, $\epsilon_{\text{soft}}$, $\text{grav\_sigma}$, $h_{\text{smooth}}$, $D$, $\tau_{\text{qi}}$ |
| **Total** | | **47** | |

### Free-Parameter Accounting

The rows below list the registry's $\varphi$ linkages with their current provenance. A $\varphi$ expression can be a conditional identity, selected boundary, calibrated output, or mapped extension, with the class shown in §2.2. The C-class/framework conversion convention is $\lambda=0.1$; the implementation class default is $\lambda=0.02$. The $\lambda=1/(2w)$ relation at $w=5$ is a **Hypothesized** cycle linkage; the conversion structure and cycle wording do not determine a rate or its units.

| Quantity | $\varphi$ expression / linkage | Current provenance / sector |
|--------------------------|---------------------------|--------|
| $\sin^2\theta_W$ | $\varphi^{-3}$ at the selected $m_Z$ boundary; exact at $\mu_* = 233$ GeV | Selected electroweak boundary—**M** |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi)$ | Selected gauge-boundary assignment—**M**; GUT unification |
| $\delta_{\text{CKM}}$ | $\pi\varphi^{-2}$ | Selected CKM-phase map—**M**; CP violation |
| $\xi$ (Qi-gravity) | $\varphi^{6}$ | Derived conditional identity with a calibrated MW pin—**C**; modified gravity |
| $\Lambda$ (cosmological constant) | $\lambda\varphi^{-2}/3$—the 1/3 is **Derived conditional** on the isotropic $d=3$ assumption ($\nabla\cdot u = dH$ steady state; `cosmology/cosmology-from-phi.md` §1, `computations/verify_h_form_one_third.py`); the $\lambda\varphi^{-2}$ rate remains **Asserted** under the C-class solver convention $\lambda=0.1$; $T_{00}$ at equilibrium gives 0 or $(g/4)\varphi^2$, never $\lambda\varphi^{-2}/3$; the ratified conversion→expansion term's vacuum half is this same $\lambda\varphi^{-2}/d$ (08 §A.2); identified with the frozen coherent-phase energy (16-qi-field.md): per-cell constant under the friction closure ⟹ w ≡ −1 exactly; the coherent phase carries 78% of the expansion rate | Dark energy |
| Conversion→expansion coupling $V_{\text{new}}$ | $\lambda\tilde{h}(E_Y,E_I) + \lambda\varphi^{-2}/d$—**Hypothesized—August 2026** (uses the asserted C-class solver convention $\lambda=0.1$; vacuum half = the $\Lambda$ row above; source half = the $\varphi$-metric gradient of the explicit logarithmic potential $\tilde{h}$; not implemented in the solver; three postulates remain: the term's form, the spiral clock, the pitch convention). **Winding-test verdict (09):** rotation half PDE-verified (dressed 0.389 turns/rung realized in the $\varepsilon\to 0$ limit, measured 0.3868 ± 0.0001; bare $\varphi^{-2}$ = generator ratio; 1.0 rejected); source half's field-level realization unstable (saddle at $(1,\varphi^{-1})$, density blow-up, log-domain exit at 0.108 turns)—r-level content stands ($\Delta w_a = -0.393$, §C.6). **Stable realization (10/12, run 2026-08-04):** the C1 Hubble-friction closure (the framework's own comoving-density structure, $H = S/(d\rho) = H_{\text{conv}}$) freezes $\rho$ at $\varphi$ exactly and realizes the source at the $r_*$ attractor: $r_* = 0.9502528427\ldots$ (the fixed-point equation is **transcendental**—the log terms vanish only at $r = \varphi$, the unique algebraic point, a repeller with $f'(\varphi) = +0.12723$ exact; 12 §1.2–1.4); the collapse is fast ($z \approx 61$ cosmologically; the spatial ratio-field collapses in 1.2τ into a $\rho$-dependent band $dr_*/d\rho \approx -0.38$ in which the density structure survives and amplifies—11); the cosmological consequence is a **pure-Λ DESI-window fit $(w_0, w_a) = (-1, 0)$** (4.17σ/2.61σ from DESI—12 §4.1); the full ratified term with $\Omega$ still runs away on the grid (log-domain exit at $t = 8.07$—11 §5) | Dark energy / spiral dynamics |
| DM halo concentration | $q$-dependent $G_{\text{eff}}$ | Galaxy dynamics |
| Inflation parameters | $n_s = 0.9691$, $r = 0.0075$ ($12/N_e^2$ at $N_e = 40$) | Early universe |

The four PDE solver parameters ($\lambda$, $\chi$, $c_s^2$, $\nu$) are
recorded with shared conventions across the main validation rows; the
Three-body row is the explicit $\lambda=0.01$ exception. The table values are
passed run inputs rather than the `TwoFluid3DGPU` constructor defaults
($\lambda=0.02$). These are solver choices, not fundamental constants.

---

## 8. Validation: Parameter Universality

A key consistency test is whether a shared set of PDE solver parameters works
across the main validation rows; the Three-body row is recorded separately
with $\lambda=0.01$.

| Sector | $\lambda$ | $\chi$ | $c_s^2$ | $\nu$ | Validated? |
|--------|-----------|--------|---------|-------|-----------|
| Cosmology (DESI DR2) | $0.1$ | $1.0$ | $0.01$ | $10^{-4}$ | $w_0 = -0.87$, $w_a = +0.012$ (2σ/2.7σ baseline); with the ratified coupling: $w_a$ $1.25\sigma$ (B2, unstable), $w_0$ $3.6\sigma$ at fixed $r_0$; the stable realization (10/12): pure-Λ $(w_0, w_a) = (-1, 0)$, $4.17\sigma$/$2.61\sigma$ |
| MW rotation curve | $0.1$ | $1.0$ | $0.01$ | $10^{-4}$ | $v_C/v_B = 2.9$–$3.1\times$ (matches $2.7\pm0.5$ within ~1.2σ) |
| Dwarf spheroidals (8) | $0.1$ | $1.0$ | $0.01$ | $10^{-4}$ | Nominal fixed-$M_\star/L_V=1$ proxy screen: 7/8 central ratios exceed the optional $\varphi^3$ endpoint; 6/8 lower propagated $\sigma_{\text{los}}/R_e$ bounds exceed it; no model verdict without object-level likelihoods |
| He DFT (LDA, N=64) | $0.1$ | $1.0$ | $0.01$ | $10^{-4}$ | 0.8% error (chemical accuracy) |
| Three-body Lagrange | $0.01$ | $1.0$ |—| $10^{-4}$ | Stable triangle, 500+ steps |
| Mercury precession | $0.1$ |—|—|—| 42.98''/cy (GR recovered) |

The table preserves the recorded solver values: the cosmology, galaxy, atomic,
and Mercury rows use $\lambda=0.1$, while the Three-body row uses $\lambda=0.01$.
This is a consistency record, not a derivation of $\lambda$ from $\varphi$.

---

## 9. Canonical Symbol Table

Symbols used framework-wide that are not parameter rows above (or names for rows that are). Bare $\alpha$ is prohibited repo-wide; always subscript.

| Symbol | Canonical meaning | Value / expression | Notes |
|---|---|---|---|
| $\varphi$ | universal scale-separation constant | $(1+\sqrt{5})/2 = 1.618033989$ | F-class axiom (§1) |
| $\alpha_0$ | fixed-point imbalance $\pi/\rho$ | $\varphi^{-3} \approx 0.236$ | At the $\varphi$-fixed point, $\alpha_0$ is the density-imbalance ratio, while the Yang density fraction is $E_Y/\rho=\varphi^{-1}$. The fixed-point value gives $G_{\mathrm{eff}}/G=\alpha_0[1+(\varphi^{6}-1)q_{\mathrm{eq}}]\approx3.73$ with $q_{\mathrm{eq}}\approx0.873$ at the reference density (ledger §10) |
| $\alpha_{\mathrm{ST},0}$ | Einstein-frame scalar-tensor coupling at the reference background | $-\frac{M_{\mathrm{Pl}}}{2}\left.\frac{d\ln F}{d\phi_E}\right|_0$ | **Hypothesized/conditional** GR7 coupling; distinct from the fixed-point density imbalance $\alpha_0=\pi/\rho=\varphi^{-3}$ and constrained by unscreened Cassini bounds; not counted in §7 |
| $\alpha_{\text{halo}}$ | galactic/halo Yang fraction (SPARC fits) | $\approx 0.7$ | hardcoded nominal (path8:65); no SPARC fit of $\alpha$ in repo—real v9 fits peak at 0.17–0.53 (ledger §10) |
| $\alpha_w$ | attractor conversion weight | $\varphi^{-1} \approx 0.618$ | = $r/(1+r)$ at $r = \varphi$ in $H_{\text{eff}}^2$; row in §2.1 |
| $\varepsilon$ | field deviation | $\varepsilon = E_Y - \varphi E_I$ | core physics (governing-equation pair); keep $\varepsilon$ |
| $\omega_{0,\mathrm{wave}}$ | default CassiCosmos second-order imbalance restoring frequency | $\sqrt{\texttt{omega0\_sq}}$ in the live shader | Distinct from the first-order conversion rate $\lambda$ and from papers that use $\omega_0=\lambda$ as a local convention. It belongs to the `ham_completion = 0` second-order wave branch and is not counted as a new fitted parameter here |
| $\Omega_g$ | imbalance-channel propagation threshold | $\varphi\omega_{0,\mathrm{wave}}$ | **Derived** from the default second-order normal-mode decomposition; below this frequency the driven imbalance channel is evanescent |
| $\Omega_*$ | drive frequency giving $k_\rho/k_\epsilon=\varphi$ | $\varphi^{3/2}\omega_{0,\mathrm{wave}}$ | **Derived conditional** frequency. It is not selected by the current live source path and is not an independent parameter |
| $k_\rho,k_\epsilon$ | density- and imbalance-channel radial wavenumbers | $\Omega/c,\ \sqrt{\Omega^2-\Omega_g^2}/c$ for $\Omega>\Omega_g$ | Second-order wave-branch quantities; the first-order canonical density PDE has no compact wave phase. See `field-experience/phase-staggered-scale-gap-report.md` |
| $\varepsilon_{\text{soft}}$ | Coulomb softening (numerical) | $0.02\,a_0$ | numerical (§6 row); distinct from the field deviation $\varepsilon$ |
| $\sigma$ | regularization scale | $\ell_{\text{Pl}}/\varphi^3$ | conditional softened-kernel scale and Gaussian free-propagator form factor; this does not by itself establish physical gravity cores or an interacting UV-finite quantum-gravity theory. **Derived conditional** on the noise–signal identification, the Hypothesized cascade-dephasing family ($d_i=\varphi^{-i-\delta}$), and the selected $d=3$ computational/physical domain; only the $\varphi^{-3}$ arithmetic follows once $\delta=3$ is selected by the noise–signal criterion. Registry G1; no ledger row (not Calibrated/Mapped) |
| $\sigma_r$ | spatial ratio dispersion | dynamic state variable | consciousness master variable (registry M4) |
| $\theta_{\text{cond}}$ | condensation threshold | $0.45$ (at $R \approx 0.093$) | calibrated to phenomenology at step 285 (ledger §10); not an a-priori fixed point |
| $\mathcal{M}_{jk}$ | apparatus-record distinguishability | $1-|\langle A_kE_k|A_jE_j\rangle|^2\in[0,1]$ | **Derived conditional** diagnostic in the regulated quantum sector: $\mathcal M_{jk}\simeq0$ means the alternatives retain overlapping records; $\mathcal M_{jk}\simeq1$ means orthogonal retained records. Its inputs are the apparatus/environment states (`foundations/quantum-measurement-derivation.md` §5.3) |
| $\mathcal{M}_i^{\mathrm{attack}}$ | classical attack-overlap coefficient used by Creative extensions | $[0,1]$ | **Hypothesized constitutive label** for organized pattern forcing; no universal PDE derivation or measured scattering map. Its inputs are a proposed classical drive and target (`foundations/proton-coherence-budget.md` §5.2) |
| $Q^A,\mathcal C,G_{AB}$ | finite regulated CassiFI quantum configuration, its configuration space, and positive metric | $Q^A=\{\operatorname{Re}D,\operatorname{Im}D,\operatorname{Re}C,\operatorname{Im}C\}_{s,j}$ | **QF1 postulate / Hypothesized physical identification.** DQ1 finds rank-two positive-root section, zero symplectic pullback, and a two-dimensional phase fibre; no canonical lift from $(E_Y,E_I)$ is derived (`foundations/quantum-measurement-derivation.md` §8.1) |
| $\mathcal I_F[\varrho]$ | configuration-space Fisher functional | $\int_{\mathcal C}d\mu_G\,\varrho G^{AB}\partial_A\ln\varrho\,\partial_B\ln\varrho$ | Required with coefficient $\hbar^2/8$ for the reverse-Madelung route. DQ2 finds physical-space Qi gradients and ensemble Fisher gradients independent; the coefficient remains a quantum-sector premise |
| $\rho_Q$ | preparation density for actual regulated configurations | $|\Psi|^2$ under QF4 | **QF4 postulate.** Equivariance preserves this density and every transported nonequilibrium ratio; DQ5 finds no canonical preparation or relaxation derivation |
| $\mu_{\mathrm{dens}}$ | candidate lower modulus/moment projection from complex Yang/Yin amplitudes to canonical densities | $\mu_{\mathrm{dens}}(\mathcal E_Y,\mathcal E_I)=(|\mathcal E_Y|^2,|\mathcal E_I|^2)$ | **Hypothesized microscopic-to-mesoscopic architecture.** GQ1 finds the discarded phase fibre causally active and GQ3 finds no closed source-derived projection to the canonical PDE (`foundations/quantum-measurement-derivation.md` §8.3) |
| $\vartheta_\varphi,n_z$ | Bloch latitude of the normalized complex Yang/Yin pair at the $\varphi$ attractor | $n_z=\cos\vartheta_\varphi=\varphi^{-3}=0.236067977500$; $\vartheta_\varphi=76.345415254^\circ$ | **Derived conditional** on the complex-spinor representation. The density pair fixes latitude and leaves relative-phase longitude free |
| $g_W,\omega_W,J$ | finite CassiFI Kähler metric, two-form, and complex structure | $g_W=\operatorname{Re}(u^\dagger Wv)$, $\omega_W=\operatorname{Im}(u^\dagger Wv)$, $Ju=iu$ | **Derived conditional** within the declared finite complex configuration. A complex-linear refinement with $I^\dagger W'I=W$ preserves all three; this does not establish physical identification |
| $\mathfrak F_\Psi$ | conserved quantum Qi-flow object for a declared split $Q=(Q_A,Q_B)$ | $(\rho_\Psi,J_A,J_B)$ with $\rho_\Psi=|\Psi|^2$ | **Derived conditional** on QF1-QF3 and the product metric. A separable pure state obeys $\rho_\Psi=\rho_A\rho_B$, $J_A=\rho_BJ_A^{(A)}$, and $J_B=\rho_AJ_B^{(B)}$; the converse holds on connected nonnodal product support. Schmidt rank or reduced-state purity remains the exact global criterion across disconnected support (`foundations/quantum-measurement-derivation.md` §4.5) |
| $\Xi^{(R)}_{a\beta},\Xi^{(S)}_{a\beta}$ | local amplitude- and phase-cross-flow tensors | $\nabla_a\nabla_\beta\ln R,\ \nabla_a\nabla_\beta S$ | **Derived conditional** local entanglement diagnostics. A nonzero tensor is sufficient on its support; disconnected nodal domains still require the global Schmidt or reduced-state criterion |
| $\mathcal E_{A:B},\mu_A$ | pure-state bipartite entanglement entropy and reduced purity | $-\operatorname{Tr}(\rho_A\ln\rho_A),\ \operatorname{Tr}\rho_A^2$ | Standard quantum diagnostics applied to the regulated CassiFI wavefunctional; $\mathcal E_{A:B}>0$ or $\mu_A<1$ for an entangled pure global state |
| $g_{Z,s}$ | reciprocal CassiFI coupling for $Z\in\{C,D\}$ between sheets $s$ and $s+1$ | positive declared model input | **Hypothesized/declared** link strength. The scalar identity-metric audit writes $g_{\mathrm{link}}:=w_Zg_{Z,s}$. Audit values are dimensionless checks, do not enter the 47 numerical parameters in §7, and are distinct from the Wu Xing gap $g=1-\varphi^{-5}$ |
| $P_s$ | CassiFI reciprocal map from sheet $s$ to $s+1$ | finite declared linear map | The nonzero singular directions of $\widetilde P_s=W_{s+1}^{1/2}P_sW_s^{-1/2}$ enumerate the mode pairs directly coupled by $w_Zg_{Z,s}\|Z_{s+1}-P_sZ_s\|_{W_{s+1}}^2/2$. This rank statement is **Derived conditional** and introduces no numerical parameter |
| $k_{a,n},N_{\rm car},\eta,E^{\rm car}_{a,n}$ | finite carrier occupations, conserved total carrier count, per-carrier density increment, and carrier-projected cell density | $k_{a,n}\in\mathbb N_0$; $\sum_{n,a}k_{a,n}=N_{\rm car}$; $E^{\rm car}_{a,n}=\eta k_{a,n}$ | The finite carrier reservoir is **Hypothesized microphysics**. Its occupation algebra is finite and exact, but the carrier identity, $N_{\rm car}$, and $\eta$ are not derived or measured. $E^{\rm car}_{a,n}$ is distinct from the QF1 candidate density $\mu_{\rm dens}(Q)_n$ unless an additional state map is supplied (`foundations/quantum-measurement-derivation.md` §8.4) |
| $\gamma_{a,n},r^{YI}_n,r^{IY}_n$ | carrier jump, conversion, and hopping rates | $r^{YI}_n=\varphi\lambda(1-q_n)k_{Y,n}$; $r^{IY}_n=\lambda(1-q_n)k_{I,n}$; nearest-neighbour hopping uses the declared finite-volume rates | **Derived conditional** generator once the canonical $\lambda$, $q_n$, transport coefficients, lattice, and carrier projection are supplied. Positivity, conservation, and the projected first-moment law are certified by QC1–QC9; no new fitted drift coefficient is introduced |
| $f_{a,s},R,v,D_\ell,r$ | shared-support Yang/Yin direction populations and loop transport data | $f_{a,s}\geq0$; $R>0$; $\Omega=v/R$; $d=D_\ell/R^2$; $r,D_\ell\geq0$ | The four-population law is a **Derived conditional mesoscopic construction** whose complete loop average gives the canonical two-fluid PDE under common exterior transport and a projected gate. The physical carrier identity, loop embedding, and coefficient values are **Hypothesized/open**. $\Omega$, $d$, and the spectral gap $g_m$ are derived combinations, not additional parameters; verifier values are examples and are not counted in §7 (`foundations/loop-to-bubble-projection-theorem.md`) |
| $\operatorname{Var}(E^{\rm car}_{I,n}),\epsilon^{\rm var}_{a,n}$ | exact finite-carrier binomial fluctuation and declared transport-noise variance | $\eta^2N_c\,\varphi^{-3}(1-\varphi^{-3})$ at local conversion equilibrium; $\epsilon^{\rm var}_{a,n}$ sets the finite transport-noise power | **Derived conditional** fluctuation law for the fixed carrier process; $\epsilon^{\rm var}_{a,n}$ is a declared regulator/noise input. Neither quantity is a universal constant or included in the §7 numerical totals |
| $\tau_{\rm bath}$ | bath correlation time required for a physical Markov reduction | positive time, not fixed | **Hypothesized/open physical input**. The finite Lindblad generator is mathematically defined without identifying a natural bath; physical use requires a measured or derived separation between $\tau_{\rm bath}$ and the resolved carrier timescales |
| $\mathcal K_{Z,s\to s+1}$ | classical signed phase-charge transfer across a reciprocal CassiFI link | $-w_Zg_{Z,s}\operatorname{Im}\langle P_sZ_s,Z_{s+1}-P_sZ_s\rangle_{W_{s+1}}$ | Antisymmetric current ledger for $Z\in\{C,D\}$. It measures the semiclassical exchange quadrature. Entanglement uses $\mathfrak F_\Psi$, Schmidt coefficients, reduced purity, or $\mathcal E_{A:B}$ |
| $\Gamma,c,\eta_c,\mathbf n,\mathbf X$ | loop species coherence matrix, cross moment, normalized coherence, Bloch-ball coordinate, and affine bubble point | $\Gamma=\begin{psmallmatrix}E_Y&c^*\\c&E_I\end{psmallmatrix}$; $\eta_c=|c|/\sqrt{E_YE_I}$; $\mathbf X=D\mathbf n$ | **Derived conditional coordinate map.** Positivity gives $\|\mathbf n\|\leq1$; rank one gives the projective shell; phase decorrelation fills its interior. The positive affine axes $D=\operatorname{diag}(a_x,a_y,a_z)$ belong to the existing conditional bubble geometry and remain physically unset. These are state diagnostics, not new fitted parameters or §7 counts (`foundations/loop-to-bubble-projection-theorem.md`; `foundations/string-bubble-projective-map.md`) |
| $g$ | Wu Xing freeze-out gap | $1 - \varphi^{-5} \approx 0.9098$ | derived identity |
| $\Lambda_Y$, $\Lambda_I$ | wake wavelengths | $\ell_n$ and $\ell_n/\varphi$ | distinct from the conversion rate $\lambda$ (`foundations/wake-geometry.md`) |
| $\lambda$ | conversion rate | $0.1$ (asserted C-class/framework convention; implementation class default $\lambda=0.02$) | Named calculations may select $\lambda=0.1$. The relation $\lambda=1/(2w)$ at $w=5$ is a **Hypothesized** cycle linkage, not a $\varphi$-derived rate; equal-and-opposite conversion, potential-coefficient normalization, and “one event per cycle” do not determine its rate or units. Keep—do not reuse $\lambda$ for wavelengths or the C1 mechanism scale ($\kappa_{\text{DE}} = 3\varphi^2 H_0$) |
| $\Gamma_0$ | reference-state gated composition-relaxation rate | $\lambda/3$ at $(E_Y,E_I)=(1,\varphi^{-1})$; ungated $\varphi^2\lambda$ | **Derived conditional**—from $\Gamma_0=(1+\varphi)\lambda(1-q_{\mathrm{eq}})$, $q_{\mathrm{eq}}=\varphi^2/3$, and $1+\varphi=\varphi^2$; not an independent parameter and not counted in §7. The fixed-$\rho=\varphi$ nonlinear rate is physically restricted to $-\varphi^2\le\varepsilon\le\varphi$; see `computations/verify_physical_becoming_reduction.py` |
| $T_p$ | prospective-branch allocation temperature | score units in the branch-value objective | **Hypothesized controller convention**—sets entropy regularization in branch allocation; not $\varphi$-derived and not counted in §7 |
| $\tau_p$ | prospective-branch allocation timescale | positive time | **Hypothesized controller convention**—matches the $1/\mathrm{time}$ replicator term in equation (21); not $\varphi$-derived and not counted in §7 |
| $T_\Theta$ | attention allocation temperature | cost units in the attention objective | **Hypothesized controller convention**—sets entropy regularization in finite attention; not $\varphi$-derived and not counted in §7 |
| $N_a$ | prospective branch count | positive integer | **Hypothesized controller convention**—finite action/shadow count selected before a run; not counted in §7 |
| $N_g$ | sensed attention-channel count | positive integer | **Hypothesized controller convention**—finite channel count selected with masks before a run; not counted in §7 |
| $T_f$ | branch forecast horizon | time units | **Hypothesized controller convention**—held fixed for forecast and held-out error tests; not counted in §7 |
| $\epsilon_{\mathrm{aut}}$ | autonomy conditional-dependence bound | dimensionless threshold | **Hypothesized/conditional controller convention**—frozen bound in the autonomy test; not $\varphi$-derived and not counted in §7 |
| $R_{\mathrm{cl}}$ | normalized closure residual | dimensionless residual ratio | **Hypothesized/conditional observable**—defined by the held-out closure test; its threshold is frozen before evaluation and it is not counted in §7 |
| $g_4,\lambda_A$ | optional microscopic radial and attractor quartics | free dimensionless Wilson coefficients | **Hypothesized** coordinates on the restricted two-singlet matching surface in `foundations/physical-becoming-hierarchy.md` §7.3; they are not the PDE rate $\lambda$, are not fixed to $\varphi$-powers, and are not counted in the §7 parameter totals |
| $m^2_{ab},\mu_{abc},\lambda_{abcd},c_a,\eta_{ab}$ | general renormalizable two-singlet potential and Higgs-portal coefficients | free EFT Wilson coefficients | **Hypothesized** microscopic extension; the unrestricted tensors are required for power-counting closure unless a declared symmetry forbids components; not counted in the §7 parameter totals |
| $\zeta_a,\xi_{ab},\xi_H,Z_a,M_{\mathrm{match}},\rho_*$ | linear and quadratic curved-space singlet/Higgs couplings plus the P1→P2 density bridge | $\zeta_a$ is dimensionful and linear in $\chi_a$; $\xi_{ab}$ and $\xi_H$ are dimensionless quadratic curvature couplings; $Z_a$ is dimensionless; $M_{\mathrm{match}}$ and $\rho_*$ are external matching scales | **Hypothesized** microscopic/coarse-graining quantities; $E_a^{\mathrm{phys}}=Z_aM_{\mathrm{match}}^2\langle\chi_a^2\rangle$ and $E_a^{\mathrm{solver}}=E_a^{\mathrm{phys}}/\rho_*$ are dimensional matching definitions rather than consequences of the canonical PDE; not counted in the §7 parameter totals |
| $T_{\mathrm{bath}},\mathcal K_{\mathrm{bath}}(\omega),\mathbb R_{\mathrm{TF}},\mathbb B_{\mathrm{TF}}$ | Markovian bath temperature, spectral/covariance kernel, dissipative tensor, and noise factor | external bath/matching data; in physical units $\mathbb B_{\mathrm{TF}}\mathbb B_{\mathrm{TF}}^{\mathsf T}=2k_{\mathrm B}T_{\mathrm{bath}}\mathbb R_{\mathrm{TF}}$ under the OS2 FDT normalization | **Hypothesized** open-system inputs for OS1–OS5; the canonical PDE fixes none of them and they are not counted in the §7 numerical totals |
| $F(\chi),K_{AB}(\chi),U(\chi)$ | covariant scalar–tensor gravity functions (GR1) | $[F]=M^2$, $[K_{AB}]=1$, $[U]=M^4$ | **Hypothesized** free functions constrained by $F>0$, $\mathcal K^E\succ0$, and a viable screened GR limit; they are not $\varphi$-derived predictions and are not counted in the §7 numerical totals |
| $\chi_{\mathrm{circ}}$ | twist-chi scratch-layer coupling (TS6 generation leg, `hypotheses/two-strand-five-channel-matter-organization.md` §3.2) | free constant, not a $\varphi$-power | Hypothesized; not counted in the §7 totals (scratch-layer parameter under test); ledger §10 |
| $q$ | Qi coherence diagnostic | $\rho^2/(\rho^2 + \varphi^{-2} + \varepsilon_{\mathrm{eff}}^2)$ | **C / Asserted** canonical local gate diagnostic under the model's reference normalization; the rational form and bare $\varphi^{-2}$ floor are constitutive choices, not consequences derived from $\varphi$ + the PDE. Here $\varepsilon_{\mathrm{eff}}^2=\varepsilon^2$ by default; optional default-off `qi_memory` replaces it with $\bar{\varepsilon}^2$ using $\tau=\varphi^{-1}$ when enabled. The bounds and $q_{\mathrm{eq}}\approx0.873$ at the stated reference state are **Derived conditional** on this definition and normalization. The solver fields are dimensionless/reference-normalized; if $E_Y,E_I$ denote physical energy densities, an external reference density $\rho_*$ is required: with $e_Y=E_Y/\rho_*$, $e_I=E_I/\rho_*$, $\tilde\rho=\rho/\rho_*$, and $\tilde\varepsilon_{\mathrm{eff}}=\varepsilon_{\mathrm{eff}}/\rho_*$, use $q=\tilde\rho^2/(\tilde\rho^2+\varphi^{-2}+\tilde\varepsilon_{\mathrm{eff}}^2)=\rho^2/(\rho^2+\varphi^{-2}\rho_*^2+\varepsilon_{\mathrm{eff}}^2)$. No $\rho_*$ scale is derived or counted as a framework parameter. It carries no spatial-current or inter-rung-transport meaning |
| $\theta_\Psi$ | amplitude-plane phase coordinate | $\operatorname{atan2}(\Psi_1,\Psi_0)$; positive-root lift $\operatorname{atan2}(\Psi_1^{(+)},\Psi_0^{(+)})=\operatorname{atan2}(\sqrt{E_I},\sqrt{E_Y})\in[0,\pi/2]$ | **Derived** exact coordinate diagnostic of the real two-component field for $\rho>0$; the positive-root specialization uses $\Psi_0^{(+)}=\sqrt{E_Y}$ and $\Psi_1^{(+)}=\sqrt{E_I}$. Treating $\theta_\Psi$ as an independent compact physical phase requires an optional signed or complex extension and is **Hypothesized** |
| $\theta_d$ | density-plane angle | $\operatorname{atan2}(E_I,E_Y)$ | **Derived** state variable of the canonical two-density pair; conversion relaxes it monotonically toward the $\varphi$-line with local rate $\lambda(1-q)\rho\varepsilon/(E_Y^2+E_I^2)$; it supplies no periodic $2\pi$ phase clock or fixed per-rung pitch |
| $\chi_F,\tau_F,N_q,\tau_{\mathrm{phys}}$ | conversion-flow exposure, conversion age, normalized openness lapse, and candidate physical proper time | $\Delta\chi_F=-(1+\varphi)^{-1}\ln|\varepsilon_1/\varepsilon_0|=\int\lambda(1-q)\,dt$; $\Delta\tau_F=\Delta\chi_F/\lambda=\int(1-q)\,dt$; $N_q(x\mid x_\star)=(1-q(x))/(1-q_\star)$; $d\tau_{\mathrm{phys}}=N_q\,d\tau_\star$ | **Derived conditional / Hypothesized interpretation**—the conversion age and relative rate are exact under the canonical rank-one law; universal common-lapse use is Hypothesized. $q_\star$ is a reference-clock gauge choice, not a fitted parameter; the candidate adds no parameter and physical seconds require external clock calibration (`foundations/unified-lagrangian.md` §1.7; CT-2). This symbol row is not counted in §7. |
| $\Theta_S$ | Stokes double-angle coordinate, distinct from $\theta_\Psi$ and $\theta_d$ | $\Theta_S\equiv2\theta_\Psi\pmod{2\pi}$; $\operatorname{atan2}(2\Psi_0\Psi_1,E_Y-E_I)$ (positive-root lift: $\operatorname{atan2}(2\sqrt{E_YE_I},E_Y-E_I)=2\theta_\Psi^{(+)}\in[0,\pi]$) | **Derived** exact coordinate identity on the positive quadrant; treating $\Theta_S$ as an independent compact physical phase is **Hypothesized**, requires an optional signed or complex extension, and is not supplied by canonical conversion |
| $\mathbf{J}_\Psi$ | foundational spatial phase current | $\Psi_0\nabla\Psi_1-\Psi_1\nabla\Psi_0=\rho\nabla\theta_\Psi$; on the positive-root lift $\rho=(\Psi_0^{(+)})^2+(\Psi_1^{(+)})^2=E_Y+E_I$ | **Derived** exact local identity with density/length units, distinct from $\mathbf{J}_d$; a named spatial projection such as $J_{\Psi,\parallel}$ supplies a chosen spatial component, while inter-rung or cascade transport interpretation is **Hypothesized** and requires a constitutive map |
| $J_{\Psi,\parallel}$ | optional named spatial projection | $\hat{\mathbf t}\cdot\mathbf{J}_\Psi$ for specified unit direction $\hat{\mathbf t}$ | **Derived** named spatial projection identity of the positive-root diagnostic; physical directional-current or transport interpretation is **Hypothesized** and requires a separate constitutive map and test, with sign tied to the chosen spatial direction |
| $\mathbf{J}_d$ | positive-root density-lattice diagnostic | $\mathbf{J}_d=E_Y\nabla E_I-E_I\nabla E_Y=(E_Y^2+E_I^2)\nabla\theta_d=2\sqrt{E_YE_I}\,\mathbf{J}_\Psi$ | **Derived** canonical spatial density-plane diagnostic with density$^2$/length units, distinct from the foundational $\mathbf{J}_\Psi$; a named component such as $J_{d,z}$ is not automatically an inter-rung or cascade current, which requires a constitutive map |
| $\Delta\theta_d$ | density-plane relaxation | $\operatorname{atan}(1/\varphi)-\operatorname{atan}((\rho-\varepsilon_0)/(\rho\varphi+\varepsilon_0))$ | **Derived** relaxation accumulated from $\varepsilon_0$ to the $\varphi$-line; $|\Delta\theta_d|\le\operatorname{atan}(\varphi)\approx1.017$ rad |
| $\delta n_{\mathrm{map}}$ | **Hypothesized** fractional rung coordinate mapping | $\Delta\theta_d/(2\pi)$ | **Hypothesized** coordinate/geometric mapping; not a PDE-derived rung offset or physical rung transport; half-steps belong to a separate parity structure |

---

## 10. Fit-Status Ledger

Every claim whose value is anchored to an observation (**Calibrated**) or whose
placement—rung, exponent, offset, candidate, normalization—was selected or
fitted to data (**Mapped**) must have a row here. A fitted quantity may stay in
the framework, but it may not be labeled Derived, and its fit must be on
record. Rows are receipts from the referee memos
(`cassi-toe-rewrite-briefs/referee/01-core.md`, `02-sm.md`, `03-cosmo.md`,
`04-grav.md`, `06-hyp.md`). A Mapped or Calibrated claim without its ledger row
fails the quality bar. Tier definitions: `open-questions-cassi-answers.md`
§Epistemic Tiers.

| Quantity | Current status | Fit source | Data anchored | Referee receipt (memo:line) | Ledger tier |
|---|---|---|---|---|---|
| $\eta$ exponent ($-44$) | Mapped numerical fit; freeze-out endpoint open | $\log_\varphi(1/\eta_{\text{obs}})=44.09$–$44.13$; the $\Gamma/H=1$ test has a unique post-seed crossing only as a thaw ($r_f=1.3495$), while the radiation-era crossing is pre-seed; no rate-based freeze selects the 44-rung endpoint (`computations/eta_gamma_h_freezeout_check.py`) | $\eta_{\text{obs}} \approx 6.0\times10^{-10}$ (PDG $6.104\pm0.058\times10^{-10}$) | 01-core.md:124-126; 02-sm.md:71-75; `foundations/baryon-asymmetry.md` §4.7 | Mapped |
| $\delta_{\text{CKM}} = \pi\varphi^{-2} \approx 68.8°$ | Catalog "✅ Within MoE" | 4-candidate search table (π−arccos(φ⁻¹) = 128° No; πφ⁻³ = 42.5° No; 2πφ⁻³ = 85° Close; πφ⁻² = 68.8° **Yes**); the winner is promoted to "the Cassi prediction" | CKM phase $\sim 69.2° \pm 3.0°$ (repo anchor; PDG 2024: $65.55° \pm 1.55°$, +2.07σ) | 01-core.md:223-225; 02-sm.md:88-89 | Mapped |
| Neutrino offsets $\Delta_1 = 1.00$, $\Delta_2 = 1.75$ | "pinned" (registry Q3) | Quarter-rung grid scan over $\Delta_1 \in \{0.25,\dots,2.0\}$ and $\Delta_2 \in \{0.5,\dots,4.25\}$ sorted by $\|R_{\text{pred}} - R_{\text{obs}}\|$ ("← BEST"); script prints "match by construction"; 2 parameters, 2 data points, 0 dof; $m_1$ solved from data; selected mapped coordinate span is $n=8\rightarrow20$ ($N_\nu=12$), while the physical GUT-to-seesaw interval is $n\approx13.3\rightarrow20$ (about 7 rungs); $\Delta_2 = 1.75$ breaks the framework's own 2:1 rule | $\Delta m^2_{21} = 7.41\times10^{-5}$, $\Delta m^2_{31} = 2.511\times10^{-3}$ eV² | 02-sm.md:39-53, 166; 01-core.md:128-130 | Mapped |
| $\alpha_{\text{halo}} \approx 0.7$ | Hardcoded nominal (path8:65, path9:60); registry says "(SPARC fits)" | Hardcoded `ALPHA_HALO = 0.7`; no SPARC fit of α in repo; the real v9 Yang fractions peak at 0.17–0.53 | (claimed) SPARC rotation curves | 04-grav.md:16, 160; 01-core.md:164 | Mapped |
| Halo $q \approx 0.7$ (0.61–0.71) | $q \approx 0.67$ (registry G-series); GW row constrains $q < 0.1$–$0.3$ | $q(\rho)$ law with environment-tuned $\rho_{\text{ref}}$ (free per environment); boost $v_C/v_B = \sqrt{\alpha(1+\xi q)}$ needs $q = 0.61$–$0.71$ | MW rotation-curve boost $2.7 \pm 0.5$ | 04-grav.md:29-58, 159 | Mapped |
| $\theta_{\text{cond}} = 0.45$ | "fixed point, not a free parameter" (§9 symbol table) | Calibrated to ~0.45 at step 285 using phenomenology; the P(k) wake-wave amplitude band (1–3%) is set by it | Bubble-edge condensation phenomenology; DESI P(k) amplitude | 01-core.md:164; 03-cosmo.md:92 | Calibrated |
| $\chi$ (sector-coupling mobility) | C-class solver parameter ($\chi = 1.0$); "Empirical—no independent derivation" | Value set empirically (range 0.5–1.0); no derivation | PDE solver phenomenology | 01-core.md:164; 02-sm.md:148-150 | Calibrated |
| $N_{\text{pde}} \approx 2.35\times10^3$ | Back-solved normalization | Chosen so the $\kappa_s \to \chi$ bridge lands in the calibrated band: $4.254\times10^{-4} \times 2.35\times10^3 = 0.9997$; bridge check 2026-08-05 (`computations/n_pde_bridge_check.py`): the convention is underdetermined—closes in $[0.5, 1.0]$ only under the $N^2$ (2D section) reading ($\chi = 0.980$); the literal 3D count gives $\chi = 47$; the "exact closure" 2350.6 is a back-solved constant rearrangement ($m_e v_0^2 \varphi^9$); the documented $L/dt$ values appear in no run script; code-default $N=64$ gives $\chi = 1.74$ (out of band) | Calibrated $\chi$ band $[0.5, 1.0]$ | 02-sm.md:148-150 | Mapped |
| $\Delta b = 1.70$ | "Ongoing" (catalog row 9) | Free beyond-SM particle content chosen to close the $\alpha_s$ gap: ~1 vector-like colored fermion pair + 2 colored scalars, or ~3 KK levels—three incompatible options, none chosen; the same content is reused for $M_{\text{GUT}}$, the quark-mass gaps, and the proton lifetime | $\alpha_s(M_Z) = 0.118$ | 02-sm.md:79-83; 01-core.md:110, 149 | Mapped |
| $\mu_* = 233$ GeV | $\sin^2\theta_W$ crossing output | Measured Z-pole couplings plus SM one-loop beta functions and asserted $\varphi^{-3}$ give $\mu_* = 232.6$–$251.1$ GeV across threshold/scheme conventions; the EW rung-80 placement is a calibrated consistency check, not an independent selection (`computations/mu_star_crossing_audit.py`) | Measured running $\sin^2\theta_W(\mu)$ | 02-sm.md:11-23; 01-core.md:149 | Calibrated |
| μ, J/ψ rung placements ($n = 96.000$, 89) | "Prediction 45 (closure-ladder mass placements)" | Discovered by the 2026-08-03 38-state mass scan; the muon's $\delta = -0.0002$ is the sharpest of ~40 draws ($P(\text{any within } \pm 0.0002) \approx 1.5\%$); $n = 96$ is not on the closure ladder | 38 measured masses (PDG) | 01-core.md:76-80; 02-sm.md:108-140 | Mapped |
| $m_e$/$m_\mu$/$m_\tau$ rung placements | $m_e$ "Partial (~25% off)"; $m_\mu$, $m_\tau$ miss by 335×/9104× | $m_e$ exponent $n_e = 26.5$ solved from the observed mass; μ/τ placements read off measured masses | $m_e$, $m_\mu$, $m_\tau$ | 01-core.md:147, 196-212; 02-sm.md:160 | Mapped |
| $M_{\text{GUT}} \approx 2\times10^{16}$ GeV | "GUT rung $n = 13.33$" in the cascade table | Scale set by RGE running with the free $\Delta b = 1.70$ content; rung addresses unified at $n = 13.33$ (2026-08-03 arithmetic sweep; $2\times10^{16}$ GeV falls between integer rungs: $n = 13.33$) | Gauge-coupling running; proton-decay bound | 02-sm.md:103, 172; 01-core.md:97 | Mapped |
| Proton-lifetime exponent ($n = 91.5$, $N = 4506$; GUT-channel $\tau_p \approx 1.29\times10^{37}$ yr; coherence-budget $\tau_p \approx 10^{910}$ yr) | "Derived (from the coherence budget); not testable" (registry Q9) | Rung fixed to the repo's own mass ladder ($n = 91.46$); per-rung survival $q_i = 1 - \varphi^{-i-\delta}$ is Hypothesized ("alternative scalings possible"); the GUT-channel inputs $M_{\text{GUT}}=2\times10^{16}$ GeV, $\alpha_{\text{GUT}}=1/53$, and the displayed $M^4/m^5$ expression yield $\tau_p = 1.29\times10^{37}$ yr; the separate coherence-budget chain ($N_{\text{max}} = \varphi^{4505.79} \to \tau_p \approx 10^{910}$ yr) is self-consistent | Proton mass; Super-K bound | 02-sm.md:101-106; 01-core.md:120-122 | Mapped |
| $r = 12/N_e^2 = 0.0075$ ($N_e = 40$, Mapped window) | Catalog "✅ Within bound" | Adopted 2026-08-11 as the only internally-consistent reading: $12/40^2 = 0.0075$ exactly; the 0.003 value requires $N_e = \sqrt{12/0.003} \approx 63.2$ (outside the window) and $\varphi^{-12} \approx 0.0031$ is a post-hoc exponent with no surviving formula (all three of the doc's own formulas fail: $\varphi^{-6} = 0.0557$; $12/40^2$; $(16/\pi)\xi q/\varphi^{40} = 2\times10^{-7}$); trajectory test 2026-08-06 (`computations/slow_roll_trajectory.py`) confirms: the trajectory's $r$ (0.060 at $N_e = 40$ literal) is excluded by BK18; 0.0075 survives BK18 and is 7.5σ-testable at CMB-S4 | Planck+BICEP $r < 0.032$ (95%) | 03-cosmo.md:18, 99-100 | Mapped (value at the Mapped window) |
| $w_0$ coupling form ($-0.87$) | Calibrated baseline; tension remains | ODE coupling form is anchored to the current DESI comparison at $w_0=-0.87$; baseline remains 2σ/2.7σ from DESI, while the ratified conversion→expansion coupling has Hypothesized B2 and stable C1 realizations documented in `foundations/wa-pentagon-gate.md` | DESI DR2 ($w_0\approx-0.75\pm0.06$, $w_a$) | 03-cosmo.md:18-25, 157 | Calibrated |
| $\kappa_{\text{DE}} = 3\varphi^2 H_0$ | "Calibrated" (open-questions C1); 2σ tension, not resolved | Calibrated via the $w_0$ coupling anchored to DESI (2σ tension); $3\varphi^2 = K_{md}$ is a Wu Xing coefficient (Derived), but $\kappa_{\text{DE}}$ as a whole has no independent derivation—a Calibrated fit, no free parameters beyond the anchoring | DESI DR2 ($w_0 \approx -0.75 \pm 0.06$, $w_a$) | 03-cosmo.md:18-25, 157 | Calibrated |
| $\xi = \varphi^6 \approx 17.944$ | "Derived—ξ within 0.3% of empirical" (registry C2/G4) | Rung identity Derived conditional on the quadratic-coupling input: $\xi = (\pi/\rho)^{-2} = (\varphi^{-3})^{-2}$—exponent 3 from the attractor's fixed-point imbalance, $-2$ the quadratic degree (`foundations/xi-derivation.md` §2); the Fibonacci decomposition $\varphi^6 = \varphi^5 + \varphi^4$ is arithmetic, not an origin; empirical pin $\xi \approx 18$ calibrated on the Milky Way rotation curve; the MW "Already consistent" row is the calibration object re-read | Milky Way rotation curve ($r = 7$ kpc) | 04-grav.md:17-25; 01-core.md:141 | Calibrated (rung identity Derived conditional) |
| $v_0/M_{\text{Pl}}$ exponents $N_{\mathrm{raw}}\approx79.89$, $N_{\mathrm{gap}}\approx79.7$ | Mapped step-count placement (registry Q1) | $N_{\mathrm{raw}}=\log_\varphi(M_{\text{Pl}}/v_0)\approx79.89$ uses the direct measured ratio; $N_{\mathrm{gap}}=\log_\varphi(gM_{\text{Pl}}/v_0)\approx79.7$ uses $g=1-\varphi^{-5}$ in the cascade coordinate; both identify nearest integer rung 80. The suppression doc quotes $N=72$ for the same gap (factor 45 off) | $v_0 = 246$ GeV; $g=1-\varphi^{-5}$ | 01-core.md:112-114 | Mapped |
| $G_{\text{eff}}$ π/ρ ↔ $\alpha_0$ equality ($\varphi^{-3}$) | Rejected equality: the fixed-point $G_{\text{eff}}$ carries the equilibrium Qi boost | Relabel: at the $\varphi$-fixed point the Yang fraction is $\varphi^{-1}$, not $\varphi^{-3}$; three α values (0.236, 0.618, 0.7) share one symbol; and with the canonical $q$, $G_{\text{eff}}/G = \alpha_0(1+(\varphi^{6}-1)q_{\text{eq}}) \approx 3.73$ at the fixed point—$\alpha_0$ is the imbalance, not $G_{\text{eff}}/G$ | Fixed-point ratio (derived); value selected | 04-grav.md:121-125 | Mapped (relabel) |
| $n_s$: $N_e=40$ window | Mapped start-threshold choice | The 40-rung window spans 19.25 physical e-folds by the ladder formula; the closed form is not reproduced by the repo's trajectory ($N_{\text{eff}}=43.22$), and $r=12/N_e^2=0.0075$ is the formula-consistent value at the ledgered window | Planck $n_s=0.9649\pm0.0042$ | 03-cosmo.md:53, 108-113; 01-core.md:182-186 | Mapped |
| $\Omega_{\text{DM}}/\Omega_b = \varphi^3$ base | $+1$ capture interpretation excluded | Base $\varphi^3 = \alpha_0^{-1} = \xi\cdot\sin^2\theta_W$ is Derived conditional on the Weinberg-angle identification; the $+1$ term is a calibration artifact that double-counts $\Omega_b$ and requires $f_{\text{cap}}=1.00$ against the census 0.10–0.20 (`computations/dm_baryon_component_budget.py`) | $\Omega_{\text{DM}}/\Omega_b = 5.39$ (Planck) | `cosmology/cosmology-from-phi.md` §4.2; `06-hyp.md` | Derived conditional (base) / Mapped artifact excluded |
| CMB $C_2$ normalization | "Fibonacci ratio" in the axis pipeline | $C_2$ calibrated to the observed 200 μK² | Observed CMB power | 03-cosmo.md:81 | Calibrated |
| CMB axis alignment $12.2°$ (C10) | Magnitude closure; direction and boundary orientation open | Magnitude $2\pi/\varphi^7=12.40°$ matches the measured 12.22°; direction is calibrated from data vectors and is nearly ecliptic-degenerate (axis ecliptic latitude +0.81°, dipole −11.40°), while the absolute bubble orientation is unselected (`computations/cmb_axis_direction_selector_check.py`) | Planck CMB dipole and quadrupole-octopole directions | 03-cosmo.md:81; refined-numeric-predictions.md §2.3; wake-geometry.md §3b | Derived (magnitude) / Calibrated (direction) / Hypothesized (projection) |
| $r_d$ half-step 284.5 = 150.0 Mpc | Mapped interpolation | The half-step convention places the measured rung at 284.46; predicted 150.0 vs $147.1\pm0.26$ Mpc | BAO ruler $r_d=147.1\pm0.26$ Mpc | 03-cosmo.md:101 | Mapped |
| Milky Way bubble-edge rung $n \approx 267$ | "Bubble edge" label (dark-matter doc) | Rung number = the coordinate map of the measured size ($\ell_{267} = $ MW diameter); a label, not a prediction | Milky Way diameter | 06-hyp.md:179-180 | Mapped |
| Dark-matter "0.1% match" ($\varphi^{-183} \approx \alpha_G$) | "Most precisely verified prediction" (dark-matter doc) | Exponent read off the measured proton mass: $\varphi^{-2n} \equiv (m_p/M_{\text{Pl}})^2 \equiv \alpha_G$ by definition; as written the value is 3.7% off $\alpha_G$ | $m_p$, $M_{\text{Pl}}$ | 06-hyp.md:168-174, 222 | Mapped |
| Wolfenstein $A = 0.810$ | $\|V_{cb}\|$, $\|V_{ub}\|$ "Consistent" | $A$ fixed from data; $\|V_{cb}\|$, $\|V_{ub}\|$ not predicted ($\lambda = \varphi^{-3}$ assumed) | CKM magnitudes | 02-sm.md:95 | Calibrated |
| $\sigma_8$: $\mu(k,a)$ normalization | "Slightly lower ~5%" claim (Mapped target); the measured rows: total −22.9% (D=0, the doctrine default, brief 63) / −20.5% (the campaign's D=0.001—the totals carry the diffusion), mechanism +29.7% (D-insensitive) (doctrine $r_0$, linear-P(k) normalization) | Plan target row labeled "target, matching observations" ($\mu = 0.980 \to -5.3\%$); free $\mu$ normalization and $q(k,a)$ machinery; the truth campaign 2026-08-07 (`runs/44-truth-campaign/`): with the linear-P(k) IC normalization (pk_norm ≡ 1—the N-dependent tophat-field fudge, 8e-5 at N=32 / σ₈_field 0.0068/0.0011/0.0002 at N=32/64/128 for a σ₈_Pk = 0.8 IC, replaced by the P(k)-integral convention) the total is −20.5% (resolution-converged N=32/64/128; σ₈_ΛCDM 0.9917 vs σ₈_Cassi 0.7884)—the D=0 re-measurement (2026-08-08, brief 63, N=128) reads −22.9% (σ₈_Cassi 0.7649): the totals carry the diffusion—and the mechanism row +29.7% (D-insensitive: Δμ 0.02 pp across D ∈ {0, 0.001}) (G_eff = 1.297, q 0.30 → 0.41—the doctrine r₀'s deep-Yin window rises; r₀-dependent: +29.4% at the derived r₀ = 0.0472; resolution-converged 0.1 pp); "~5%" is a Mapped target; **doctrine 2026-08-07: reading P-A operative; IC $r_0 = 0.0472$ (derived, Wu Xing) / 1/23 (operational, DESI-anchored) / 1/3 (pipeline state, non-doctrinal); computed rows: −16.6% (closure, regime-integrated, R = 0.834), −15.2% (band-state mean-field), +29.7% (mechanism, doctrine-IC, truth campaign)** | Low-z weak lensing $\sigma_8$ | 03-cosmo.md:139 | Mapped |
| GWTC-4 near-hit catalog entries | Mapped catalog correspondences | Point-estimate near-hits occur among ~200 events with an expected count of ~12 at the catalog density; the posterior-weighted test is null | GWTC-4 compact-object masses | 06-hyp.md:78-82 | Mapped |
| Pinch two-point correlation peaks (consciousness-from-phi §2.1) | "Testable prediction" | Test run 2026-08-05 (`two-fluid/run_pinch_correlation.py`): field crosses the pinch cleanly (t_c = 8.8, r̄ 0.5→1.19) but no φ-scaled correlation peaks post-crossing; pre/post indistinguishable; above-pinch counterfactual featureless | PDE run record not retained in this checkout; regenerate with `two-fluid/run_pinch_correlation.py` | `two-fluid/run_pinch_correlation.py` | Null (tested) |
| Two-bubble revival at $d \geq 31$ (consciousness-from-phi §3) | "Weak-to-moderate signal" (2026-07-19) | Decisive gate scan 2026-08-05 (`two-fluid/run_two_bubble_gate_scan.py`): gate-independent (max per-sep delta 0.0003), static from initialization (corr(t=0)==corr(t=1000)); {31,34,37} wrap under periodic BCs to {17,14,11}; aggregate 3.83×/3.44×/2.97× reproduce but the φ-set occupies smaller physical distances (distance-matched 1.1–1.7×) | PDE run record not retained in this checkout; regenerate with `two-fluid/run_two_bubble_gate_scan.py` | `two-fluid/run_two_bubble_gate_scan.py` | Null on dynamics (static-geometry protocol feature) |
| R-matrix sheng redistribution in the solver (emotions-as-gate-configurations §4.2) | "Derived arithmetic" | Realization test 2026-08-05 (`two-fluid/run_rmatrix_redistribution.py`): gate_model='five' realizes it only for Wood closure, allocated by ACTIVE openness $b_i w_i$; measured Wood blend (0, 0, 0.5, 0.309, 0.191) vs R-row (0, 0.447, 0.276, 0.171, 0.106)—ordering matches, proportions don't; rows 2–5 have no gate term; Earth cannot close (w₃ ≡ 1) | PDE run record not retained in this checkout; regenerate with `two-fluid/run_rmatrix_redistribution.py` | `two-fluid/run_rmatrix_redistribution.py` | Partial (Wood only) |
| Five-channel $w_a$ shift (wa-pentagon-gate §4) | "→ 0⁻ (potential flip)" | PDE test 2026-08-06 (`two-fluid/run_pde_wa_5channel.py`): w_a = −0.425 ± 0.1 vs single-channel −0.09 ± 0.10 (−0.44 ± 0.15 toward DESI; ~1.1σ from DESI w_a = −0.73 ± 0.28); measured Δ(1−q) ≈ ±0.01, not the documented +0.055—the shift is gate-structure dynamics, not control-release; pentagon gate NaN at a ≈ 0.38–0.66 at the default cap; five_ke inconclusive | PDE run record not retained in this checkout; regenerate with `two-fluid/run_pde_wa_5channel.py` | `two-fluid/run_pde_wa_5channel.py` | Partial-support (mechanism mismatch) |
| H₀ full H(z) fit (registry C3/T4) | "full H(z) fit pending" | Fit 2026-08-06 (`computations/hz_full_fit.py`): not resolved under the calibrated w(a) (w₀ = −0.87, w_a = +0.012 baseline / −0.38 coupling); dark energy negligible at z~1000–1100, R_cmb = 1.00000, χ² ≈ 25.1 = ΛCDM (anchor separation 5.0σ); ΔH₀ = −7.2 comes from the ODE pipeline's right-clamp at +0.37 for z > 99—extrapolation beyond the calibrated range (a ≥ 0.01) | Planck/SH0ES anchors | hz_full_fit.py | Not resolved |
| Slow-roll trajectory (n_s, r) | "1.0σ from Planck" / "within bound" | Trajectory test 2026-08-06 (`computations/slow_roll_trajectory.py`): (n_s, r) = (0.813, 0.188) under 1 step = 1 e-fold; (0.914, 0.060) with N_e = 40 literal (1 step = ln φ physical e-folds); n_s 12–36σ from Planck; r excluded by BK18; the two claimed numbers do not coexist on the trajectory; N_e = 40 is a start-threshold choice, not a derived count | Planck 2018 n_s; BK18 r | slow_roll_trajectory.py | Mapped confirmed (trajectory evidence) |
| Q7 real-density organized-vs-random branch-selection ansatz | “$\mathcal M\approx1$ → definite outcome” in the Q7 real-density ansatz | Contrast test 2026-08-06 (`two-fluid/run_coherence_budget_contrast.py`): no organized drive (uniform, anti-phase, single-path) selects a branch of the symmetric two-branch state; equal-power random drive rectifies both branches into a same-sign phase lock; protocol caveat: the state has no fast coherent oscillation ($P_0$ is an FFT artifact), so the proposed phase-matching channel was unreachable at $t=4$. This null constrains the canonical real-density ansatz. It does not test the regulated configuration-space wavefunctional, quantum-equilibrium postulate, or topological apparatus sectors registered in Q7. | PDE run (`runs/q7_coherence_budget/`) | `two-fluid/run_coherence_budget_contrast.py` | Null (tested real-density ansatz) |
| TR3 phase-matched trigger (cassi-psychology §17) | "Hypothesized, untested" | Test 2026-08-06 (`two-fluid/run_trigger_wx2_tests.py`): Fire trigger re-locks a released Fire site (23× control)—phase-matched re-lock confirmed; Wood trigger re-activates the released site into Wood (39× control)—reactivation is channel-selective, not lock-memory-specific | PDE run (runs/20260806_001658_trigger_wx2/) | run_trigger_wx2_tests.py | Partial |
| WX2 κ³ damping signature (wu-xing-cycle-structure WX2) | "κ³ = 23.6% per cycle" | Test 2026-08-06 (same script): per-P0 retention 0.944 vs 0.764 predicted; gate-level mean 0.389 vs 0.764; sub-critical direction holds (decay, no self-sustain); ke ring adds no locked-channel damping (Δγ < 0.001) | PDE run (runs/20260806_001658_trigger_wx2/) | run_trigger_wx2_tests.py | Not matched |
| Wake structural trio (P44 checkerboard, P43 closure, F₂/F₁ sharpening) | "Not yet tested" (catalog rows 43–44) | Probes 2026-08-06 (`two-fluid/run_wake_structural_probes.py`, commit 168a11a): P44 nulls at (m+½)ℓ_{n+1} to 0.0023 grid precision, beats at m·ℓ_{n+1} to 0.00015; P43 beats land on m·ℓ_{n+1} to grid scale; F₂/F₁ = 0.617621 vs 1/φ = 0.618034 (−0.07%), cross-ratio φ³ exact, requires the documented Π∇Φ force form | PDE probes (commit 168a11a) | run_wake_structural_probes.py | Supported (PDE-verified) |

| $\chi_{\mathrm{circ}}$/$\chi_{\mathrm{ax}}$ (twist-chi scratch coupling) | Hypothesized—free coupling under test, not fitted | No fit performed: axial component $g=(\nabla\times J)_x$ in the solver label frame $=-(\nabla\times J)_z$ in box labels ($\chi_{\mathrm{ax}}$ multiplies $-(\nabla\times J)_z$; the sketch's $\chi_{\mathrm{circ}}=-\chi_{\mathrm{ax}}$), t = 4 ramp $\chi \in \{0, \pm0.25, \pm0.5, \pm1, \pm2\}$ on the TS6 helix, 2026-08-07 (`two-fluid/run_twist_chi_axial_ramp.py`): max $\|\Delta\mathrm{Tw}\| = 5.0\times10^{-6}$ (generation null; response even in $\chi$, mirror identity $d\mathrm{Tw}(\chi,-\Omega_0)=-d\mathrm{Tw}(\chi,+\Omega_0)$ to $4\times10^{-7}$); t = 40 lock legs ($\Omega_0 \in \{2\pi/N, 4\pi/N\}$): $\Delta\mathrm{Tw} = -1.0\times10^{-4}$ / $+2.8\times10^{-3}$ at $\chi=1$, no lock; $J_{\mathrm{scale}} = \max\|g\|$ at t = 0 = 0.1718 at both seeds (see `hypotheses/two-strand-five-channel-matter-organization.md` §3.2) |—(no data anchor; $J_{\mathrm{scale}}$ is an initialization convention, not a fit) | `two-fluid/run_twist_chi_axial_ramp.py`; run records not retained in this checkout; regenerate with that script | Hypothesized |

**Row count: 40.** A row here records the quantity's epistemic status. Each
entry carries the tier the claim must bear (Calibrated or Mapped) until an
independent derivation replaces the fit; the status propagates to documents
that cite the quantity.

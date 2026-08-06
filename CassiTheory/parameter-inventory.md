# Cassi Parameter Inventory

## Classification Legend

| Label | Meaning | Count |
|-------|---------|-------|
| **F** | **Fundamental axiom**—the single postulate from which everything follows | 1 |
| **D** | **Derived**—mathematical consequence of φ and the PDE structure, zero freedom | 24 |
| **C** | **PDE solver convention**—simulation conventions, no calibrated constants | 0 |
| **E** | **External / empirically determined**—standard physics constants inherited by the framework, plus lattice parameters not yet derived from $\varphi$ | 7 |
| **I** | **Initial condition**—free initial values that evolve dynamically, not fixed by theory | 6 |
| **N** | **Numerical**—computational parameters with no physical significance | 8 |
| | **Total** | **46** |

---

## 1. The Single Postulate

| Parameter | Value | Class | Status |
|-----------|-------|-------|--------|
| $\varphi = (1+\sqrt{5})/2$ | $1.618033989\ldots$ | **F** | Mathematical constant, the universal scale-separation axiom |

---

## 2. Derived Constants ($\varphi$-Powers)

All dimensionless coupling constants in the Cassi framework are $\varphi$-powers. No free parameters.

### 2.1 Pure Powers (Mathematical Identities)

| Parameter | Expression | Value | Class | Derivation |
|-----------|-----------|-------|-------|-----------|
| $\varphi^{-1}$ | $\varphi - 1$ | $0.618033989$ | **D** | Identity: $\varphi^2 = \varphi + 1$ |
| $\varphi^{-2}$ | $1 - \varphi^{-1}$ | $0.381966011$ | **D** | $= 2 - \varphi$ |
| $\varphi^{-3}$ | $(\varphi-1)/(\varphi+1)$ | $0.236067978$ | **D** | Equilibrium Yang fraction |
| $\varphi^{-6}$ | $(\varphi^{-3})^2$ | $0.055728090$ | **D** | Square of Yang fraction |
| $\varphi^{4}$ | $\varphi^3 + \varphi^2$ | $6.854101966$ | **D** | Four-interaction scale |
| $\varphi^{5}$ | $\varphi^4 + \varphi^3$ | $11.09016994$ | **D** | Wu Xing cycle scale |
| $\varphi^{6}$ | $\varphi^5 + \varphi^4$ | $17.94427191$ | **D** | Qi-gravity coupling $\xi$ |

### 2.2 Physical Couplings (Derived from $\varphi$)

| Parameter | Expression | Value | Class | This was a free parameter: |
|-----------|-----------|-------|-------|--------------------------------------|
| $\xi$ (Qi-gravity) | $\varphi^{6}$ | $17.94427191$ | **D** | MOND interpolating function / DM halo concentration |
| $\sin^2\theta_W$ (at $m_Z$) | $\varphi^{-3}$ | $0.23607$ | **D** | Weak mixing angle (free in SM); +2.1% at $m_Z$, exact at $\mu_* = 233$ GeV (`standard-model/sm-radiative-corrections.md`) |
| $\sin^2\theta_W$ (at $\mu_* = 233$ GeV) | running MS-bar angle crosses $\varphi^{-3}$ | $0.23607$ | **D** | Where the φ-point value is realized; the angle runs upward, so the GUT scale is not the boundary |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3} / 4\pi$ | $1/53 \approx 0.01887$ | **D** | GUT coupling (free in SU(5)/SO(10)); not realized by SM running alone |
| $m_W/m_Z$ | $\sqrt{1-\varphi^{-3}}$ | $0.874$; $0.878$ with $\rho$ | **D** | Prediction for FCC-ee |
| $\alpha_{\text{em}}^{-1}(m_Z)$ | from $\varphi^{-3}/(4\pi)$ at $M_{\text{GUT}}$ | $161$ (vs measured $128.9$) | **D** | φ-boundary running gives +25%; the SM value $128.9$ closes via $\alpha(0)+\Delta\alpha$ (`standard-model/sm-radiative-corrections.md` §3–4) |
| $\delta_{\text{CKM}}$ (CP phase) | $\pi\varphi^{-2}$ | $1.199$ rad $(68.7^\circ)$ | **D** | Via unitarity triangle from $\varphi$-scaled CKM elements |
| $\beta$ (Bohm QP exponent) | $\varphi^{-1}/2$ | $0.309$ | **D** | Quantum potential scaling exponent |
| $\chi_Y$ (Yang chemotaxis) | $\chi/\varphi$ | $\chi \cdot 0.618$ | **D** | Ratio fixed, absolute value calibrated ($\chi$) |
| $w_0$ (DE equation of state) |—| $-0.87$ | **D** | From $\lambda$ and $\varphi$; 2σ baseline from DESI $w_0 \approx -0.75 \pm 0.06$ ($3.6\sigma$ at fixed $r_0$ with the B2 coupling; $r_0$ re-tuning closed negatively under the stable realization—12) |
| $w_a$ (DE running) |—| $+0.012$ (with $\xi = \varphi^6$); $-0.38$ (with the ratified coupling, B2—unstable); **$(w_0, w_a) = (-1, 0)$ pure-Λ window (stable realization—10/12)** | **D** | $\xi = \varphi^6$ in $H(a)$; verified via `two-fluid/calibrate_initial_ratio_xi_v2.py`; $2.7\sigma$ baseline; $1.25\sigma$ with the coupling (B2, 08 §C.6—unstable); $4.17\sigma$/$2.61\sigma$ for the stable realization's pure-Λ fit (12) |
| $n_s$ (spectral index) |—| $0.9691$ | **D** | From $n_s = 1 - 2\varphi^{-1}/N_e$ with $N_e = 40$ |
| $r$ (tensor-to-scalar) |—| $0.003$ | **D** | From inflation in Cassi framework |
| $K_{fw}$ (Wu Xing coeff) | $\varphi^{-1}$ | $0.618$ | **D** | Water damps Fire |
| $K_{ring}$ (ke ring gain) | $\varphi^{-3}$ | $0.236$ | **D** | One-cycle attenuation of the control ring (`foundations/wu-xing-cycle-structure.md` §2.3) |
| $\kappa_s$ (sector coupling) | $\varphi^{-6}/v_0^2$ | $0.92$ TeV$^{-2}$ | **D** | Dirac↔two-fluid equilibration scale (`foundations/sector-coupling-derivation.md`) |


## 3. PDE Solver Parameters (Numerical Conventions)

These four parameters control the PDE solver's numerical behavior. They are
**not fundamental physical constants**—they are dimensionless simulation
parameters set by grid resolution, timestep stability, and the natural energy
density scale of the system under study. Their universal values across all
simulations reflect consistent solver conventions, not a hidden $\varphi$
derivation for each individually.
| # | Parameter | Value | Role | Status |
|---|-----------|-------|------|--------|
| 1 | $\lambda$ (conversion) | $0.1 = 1/(2w)$ | $\varphi$-attractor timescale | Derived—$\lambda = 1/(2w)$ with $w=5$ derived (`foundations/wu-xing-derivation.md`) |
| 2 | $\chi$ (chemotaxis) | $0.5$–$1.0$ | Density-focusing mobility | **Empirical**—no independent derivation |
| 3 | $c_s^2$ (sound speed) | $0.01$ | Effective pressure | **Empirical**—set by Bohm scale + normalization (see §3.2) |
| 4 | $\nu$ (hyperviscosity) | $10^{-4}$–$10^{-3}$ | Grid-scale dissipation | **Numerical**—set by Nyquist stability, not physical |

### 3.1 $\lambda$: The Electroweak Consistency Check (the Wu Xing Route Derives $\lambda$)

The Lagrangian has the $\varphi$-attractor coupled to the Higgs quartic:

$$V_{\text{Higgs}} = \frac{g}{4}|\Psi|^4 + \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2$$

At the minimum $\Psi_0^2 = \varphi\Psi_1^2$, the field-space Hessian has two
eigenvalues that determine the physical scalar masses; they mix through the
off-diagonal term $g - 2\lambda\varphi$. The computation is in
`computations/sm_radiative_corrections.py` §5.5: with the equilibrium
$g = \varphi^{-3} \approx 0.236$ (the equilibrium Yang fraction) and
$\lambda = \lambda_{\text{WX}} = 0.1$, the two eigenmodes of the
$\varphi$-point potential are

$$m = 157.6\ \text{GeV} \quad\text{and}\quad 116.6\ \text{GeV}
  \qquad (|\Psi|^2_{\min} = v^2),$$

bracketing the observed 125 GeV mode. This is **not a derivation** but a
nontrivial consistency check: $\lambda = 0.1$ is the right order of
magnitude for the electroweak scale, and the measured Higgs mass lies
between the two φ-anchored mode frequencies
(`standard-model/sm-radiative-corrections.md` §6.2).

**Summary:** The Higgs route cannot derive $\lambda = 0.1$ without fixing $g$; the value is consistent with the Higgs mass/VEV within a factor of 2. The derivation comes from the Wu Xing route: $\lambda = 1/(2w) = 1/10$ with $w = 5$ derived (`foundations/dimensionful-constants-status.md` §2.1, `foundations/wu-xing-derivation.md`).

### 3.2 $c_s^2$ from the Bohm Quantum Potential

The sound speed in the PDE is NOT a fundamental constant—it is the effective
pressure response of the two-fluid system. From the Lagrangian's Bohm quantum
potential (Section 1.3):

$$\mathcal{L}_{\text{QP}} = -\frac{\hbar^2}{2m^2}
                            \frac{\nabla^2 M^\beta}{M^\beta}\Psi_\alpha$$

The effective sound speed from this term at the atomic scale is:

$$c_s^2 \sim \frac{\hbar^2}{m_e^2 a_0^2} \cdot \frac{\varphi^{-2}}{1+\varphi}
          \approx 1.0\ \text{a.u.} \times 0.146 \approx 0.146$$

The PDE solver uses $c_s^2 = 0.01$ because the field normalization in
simulation units absorbs most of the physical scale factor. The remaining
$c_s^2 = 0.01$ is a **residual** that accounts for the ratio between the
Bohm pressure and the full kinetic energy density of the DFT system.

For cosmological systems, the PHYSICAL sound speed is different (set by the
dark matter velocity dispersion), but in simulation coordinates the same
numerical $c_s^2 = 0.01$ is used—this is a **unit conversion** from atomic
to simulation units, not a universal physical constant.

### 3.3 $\chi$: The Sector-Coupling Bridge; $\nu$: Numerical

**$\chi$ (chemotactic mobility)** couples the two-fluid density gradient to the
gravitational potential:

$$\partial_t E_I \supset +\chi\,\nabla\cdot(E_I\nabla\Phi)$$

This term originates from the Dirac-to-two-fluid sector coupling $\kappa_s$ in the
unified Lagrangian:

$$\chi = \frac{\kappa_s}{m_e} \cdot \frac{\varphi^{-1}}{(1+\varphi)}$$

The sector-coupling scale is now scale-derived rather than free:
$\kappa_s = \varphi^{-6}/v_0^2 = 0.92$ TeV$^{-2}$ (see `foundations/sector-coupling-derivation.md`).
The as-written bridge above is dimensionally inconsistent as it stands—with
$\kappa_s = 0.92$ TeV$^{-2}$ and $m_e = 5.11\times10^{-4}$ GeV it gives
$\chi \approx 4\times10^{-4}$, not the calibrated $0.5$–$1.0$. The repaired
bridge

$$\chi = \frac{\mathcal{N}_{\text{pde}}\,\kappa_s\,\varphi^{-1}}{m_e(1+\varphi)}$$

needs the PDE normalization factor $\mathcal{N}_{\text{pde}} \approx 2.35\times10^{3}$
(solver conventions: grid $L=40$, $N=48$, $\Delta t=0.002$, $\rho_{\text{crit}}=\varphi$)—a
concrete computational follow-up, not derived here.

**$\nu$ (hyperviscosity)** is purely numerical. In the Lagrangian:

$$\mathcal{L}_{\text{kin}} \supset -\frac{\nu}{2}(\nabla^2\Psi_\alpha)^2$$

In the PDE solver, $\nu$ is set to the smallest value that damps grid-scale
oscillations at resolution $N=48$:

$$\nu \sim \frac{\Delta x^4}{\Delta t} \sim \frac{(L/N)^4}{\Delta t}
      \approx \frac{(40/48)^4}{0.002} \approx 1.5 \times 10^{-4}$$

consistent with the solver's $\nu = 10^{-4}$. No physical content.

### 3.4 Summary: What These Parameters ACTUALLY Are

| Parameter | True status | If it's a constant, which one? |
|-----------|-------------|-------------------------------|
| $\lambda = 0.1$ | **Derived** via Wu Xing ($\lambda = 1/(2w)$, $w=5$—`foundations/dimensionful-constants-status.md` §2.1); $m_H^2\varphi/4v_0^2 \approx 0.104$ is a consistency check (§3.1) | The Higgs quartic's orthogonal mode coupling |
| $\chi \approx 1.0$ | **Scale-derived**—$\kappa_s = \varphi^{-6}/v_0^2$ (coefficient Hypothesized); PDE-normalization factor $\mathcal{N}_{\text{pde}}$ pending | $\chi = \mathcal{N}_{\text{pde}}\kappa_s\varphi^{-1}/[m_e(1+\varphi)]$ |
| $c_s^2 \approx 0.01$ | **Emergent**—Bohm pressure + normalization choice | $c_s^2 \propto \hbar^2/(m_e^2 a_0^2) \cdot \varphi^{-2}$ |
| $\nu \approx 10^{-4}$ | **Numerical**—Nyquist stability at $N=48$ | $\nu \approx (L/N)^4 / \Delta t$ |

The "universality" of these four values across cosmology, galaxy dynamics, and
atomic physics is not a mysterious conspiracy—it's a **solver consistency
test**: the SAME grid scale $L=40$, $N=48$, $\Delta t=0.002$ works well for
all three domains, so the same numerical parameters suffice. If any sector
required different values (e.g., $N=256$ for cosmological cluster simulations),
$\nu$ and $c_s^2$ would need to be rescaled proportionally.

---

## 4. External Constants—Attempted $\varphi$ Derivation

The six external constants inherit from standard physics. Unlike the coupling
constants (which are dimensionless $\varphi$-powers), these are DIMENSIONFUL
quantities that set the absolute scales of the universe. $\varphi$ alone cannot
determine a dimensionful number—it constrains dimensionless ratios among
these constants.

| Parameter | Symbol | Value | Class | Derivation Status |
|-----------|--------|-------|-------|-------------------|
| Newton's constant | $G$ | $6.67430\times10^{-11}$ m$^3$/kg/s$^2$ | **E** | Not derivable (dimensionful) |
| Speed of light | $c$ | $299792458$ m/s | **E** | Not derivable (unit conversion) |
| Planck constant | $\hbar$ | $1.054571817\times10^{-34}$ J$\cdot$s | **E** | Not derivable (unit conversion) |
| Electron mass | $m_e$ | $0.511$ MeV | **E** | Partial: $m_e \approx \varphi^{-26} v_0/\sqrt2$ (~25% off) |
| Proton mass | $m_p$ | $938$ MeV | **E** | Not derivable (QCD scale) |
| Strong coupling | $\alpha_s(M_Z)$ | $0.118$ | **E** | Partial: RGE from $\alpha_{\text{GUT}}$ needs particle content |
| Along-string bubble period | $P_\parallel(n)$ | $P_\parallel(285)=1$, $P_\parallel(142\text{–}168)=2$ | **E** | Empirically determined at two rungs; $n$-dependence not yet derived from PDE. Source: `foundations/bubble-lattice-fabric.md` §2.3 |

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

This is $2.0\times$ smaller than the observed $0.118$ (not $11\times$ —
the discrepancy resulted from an RGE sign error and an
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
| $G_{\text{eff}}/G$ (at fixed point) | $\varphi^{-3}$ | $0.236$ | Exact |
| $v_0/M_{\text{Pl}}$ | $\varphi^{-80}$ | $1.9\times10^{-17}$ | $5.3\%$ (closest integer power) |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi)$ | $1/53.2$ | Exact (definition) |
| $\alpha^{-1}(\text{GUT})$ | $4\pi/\varphi^{-3}$ | $53.2$ | Exact (definition) |
| $m_{\nu_e}/m_e$ (seesaw) | $\varphi^{-11}$ | $0.013$ | Consistent |

The Cassi framework's external-constant status: **6 inputs, 0 a-priori-derived;
29 fitted or selected quantities are ledgered as Calibrated or Mapped in §10.**
This matches the Standard Model (which also takes $\{G, c, \hbar, m_e, m_p,
\Lambda_{\text{QCD}}\}$ as inputs) and is not a weakness—all dimensionful
quantities must eventually be set by experiment in any theory that lacks a
mechanism for generating them.

**The Cassi framework improves the SM by deriving 24 parameters from $\varphi$ (7 pure $\varphi$-powers + 16 physical couplings + $r_0$).** This is its achievement. Dimensional
scale-setting is a separate problem shared by all current physical theories.
---

## 5. Initial Conditions (Mostly Free, One Now Derived)

Most initial-condition parameters must be specified for any Cassi simulation. The primordial Yang-Yin ratio $r_0$ is the exception: it is now **derived** from $w = 5$ via the cascade coherence criterion + $\varphi$-geometry (`foundations/wu-xing-derivation.md`). The remaining initial conditions are not fixed by the theory.

| Parameter | Typical Value | Class | Physical Meaning |
|-----------|--------------|-------|-----------------|
| $r_0 = E_{Y,0}/E_{I,0}$ | $0.0472$ (cosmology; $E_I/E_Y \approx 21$), $\varphi$ (atoms) | **D** | Initial Yang/Yin ratio; derived from Wu Xing gap $g = 1-\varphi^{-5}$, with $w=5$ now derived from cascade dynamics + Fibonacci identity (`foundations/wu-xing-derivation.md`). $w_0 = -0.87$, $2\sigma$ from DESI. |
| $a_0$ | $0.01$-$1.0$ | **I** | Initial scale factor (expanding universe) |
| $H_0$ | $0.05$-$1.0$ | **I** | Initial Hubble parameter |
| $N_{\text{blobs}}$ | $2$-$3$ | **I** | Number of density peaks |
| $M_j$ (blob masses) | $200$ (typical) | **I** | Individual blob masses |
| $\sigma_j$ (blob width) | $3.0$-$4.0$ a$_0$ | **I** | Gaussian density profile width |
| $\mathbf{X}_j$, $\mathbf{V}_j$ | varies | **I** | Initial positions and velocities |

At the $\varphi$-fixed point, $r = \varphi$ and the specific initial ratio
becomes irrelevant—the conversion term $\lambda$ drives all configurations
toward the equilibrium.

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
| $D$ (diffusion) | $0.001$ | **N** | Can be set to zero (energy-conserving) |
| $\tau_{\text{qi}}$ (IIR memory) | $\varphi^{-1} \approx 0.618$ | **N** | Qi memory EMA timescale (reduced in slow regimes) |

---

## 7. Summary by Category

| Category | Label | Count | Description |
|----------|-------|-------|-------------|
| Fundamental axiom | **F** | 1 | $\varphi$ itself |
| $\varphi$-derived | **D** | 24 | 24 derived parameters (7 pure $\varphi$-powers + 16 physical couplings + $r_0$) |
| PDE solver convention | **C** | 0 | No calibrated constants ($\chi$, $c_s^2$, $\nu$ are Empirical/Derived/Numerical) |
| External constant | **E** | 7 | $G$, $c$, $\hbar$, $m_e$, $m_p$, $\alpha_s(M_Z)$, $P_\parallel(n)$ |
| Initial condition | **I** | 6 | $a_0$, $H_0$, $N_{\text{blobs}}$, positions, velocities, masses |
| Numerical parameter | **N** | 8 | $N$, $L$, $\Delta t$, $\epsilon_{\text{soft}}$, $\text{grav\_sigma}$, $h_{\text{smooth}}$, $D$, $\tau_{\text{qi}}$ |
| **Total** | | **46** |

### Historical Reduction

The Cassi framework eliminates free parameters:

| Free parameter | Derived from $\varphi$ | Sector |
|--------------------------|---------------------------|--------|
| $\sin^2\theta_W$ | $\varphi^{-3}$ (at $m_Z$; exact at $\mu_* = 233$ GeV) | Electroweak |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi)$ | GUT unification |
| $\delta_{\text{CKM}}$ | $\pi\varphi^{-2}$ | CP violation |
| $\xi$ (Qi-gravity) | $\varphi^{6}$ | Modified gravity |
| $\Lambda$ (cosmological constant) | $\lambda\varphi^{-2}/3$—**Asserted** (postulate): the 1/3 is the 3D continuity reading; $T_{00}$ at equilibrium gives 0 or $(g/4)\varphi^2$, never $\lambda\varphi^{-2}/3$; Lagrangian derivation open; the ratified conversion→expansion term's vacuum half is this same $\lambda\varphi^{-2}/d$ (08 §A.2) | Dark energy |
| Conversion→expansion coupling $V_{\text{new}}$ | $\lambda\tilde{h}(E_Y,E_I) + \lambda\varphi^{-2}/d$—**Hypothesized—August 2026** (zero free constants; vacuum half = the Λ row above; source half = the φ-metric gradient of the explicit logarithmic potential $\tilde{h}$; not implemented in the solver; three postulates remain: the term's form, the spiral clock, the pitch convention). **Winding-test verdict (09):** rotation half PDE-verified (dressed 0.389 turns/rung realized in the $\varepsilon\to 0$ limit, measured 0.3868 ± 0.0001; bare $\varphi^{-2}$ = generator ratio; 1.0 rejected); source half's field-level realization unstable (saddle at $(1,\varphi^{-1})$, density blow-up, log-domain exit at 0.108 turns)—r-level content stands ($\Delta w_a = -0.393$, §C.6). **Stable realization (10/12, run 2026-08-04):** the C1 Hubble-friction closure (the framework's own comoving-density structure, $H = S/(d\rho) = H_{\text{conv}}$) freezes $\rho$ at $\varphi$ exactly and realizes the source at the $r_*$ attractor: $r_* = 0.9502528427\ldots$ (the fixed-point equation is **transcendental**—the log terms vanish only at $r = \varphi$, the unique algebraic point, a repeller with $f'(\varphi) = +0.12723$ exact; 12 §1.2–1.4); the collapse is fast ($z \approx 61$ cosmologically; the spatial ratio-field collapses in 1.2τ into a $\rho$-dependent band $dr_*/d\rho \approx -0.38$ in which the density structure survives and amplifies—11); the cosmological consequence is a **pure-Λ DESI-window fit $(w_0, w_a) = (-1, 0)$** (4.17σ/2.61σ from DESI—12 §4.1); the full ratified term with $\Omega$ still runs away on the grid (log-domain exit at $t = 8.07$—11 §5) | Dark energy / spiral dynamics |
| DM halo concentration | $q$-dependent $G_{\text{eff}}$ | Galaxy dynamics |
| Inflation parameters | $n_s = 0.9691$, $r = 0.003$ | Early universe |

The four PDE solver parameters ($\lambda$, $\chi$, $c_s^2$, $\nu$) are consistent
across all simulations—a solver-consistency test that the framework passes,
not fundamental constants.

---

## 8. Validation: Parameter Universality

A key consistency test: the same four PDE solver parameters
work in every sector.

| Sector | $\lambda$ | $\chi$ | $c_s^2$ | $\nu$ | Validated? |
|--------|-----------|--------|---------|-------|-----------|
| Cosmology (DESI DR2) | $0.1$ | $1.0$ | $0.01$ | $10^{-4}$ | $w_0 = -0.87$, $w_a = +0.012$ (2σ/2.7σ baseline); with the ratified coupling: $w_a$ $1.25\sigma$ (B2, unstable), $w_0$ $3.6\sigma$ at fixed $r_0$; the stable realization (10/12): pure-Λ $(w_0, w_a) = (-1, 0)$, $4.17\sigma$/$2.61\sigma$ |
| MW rotation curve | $0.1$ | $1.0$ | $0.01$ | $10^{-4}$ | $v_C/v_B = 2.9$–$3.1\times$ (matches $2.7\pm0.5$ within ~1.2σ) |
| Dwarf spheroidals (8) | $0.1$ | $1.0$ | $0.01$ | $10^{-4}$ | 3/8 pass; MOND preferred (4/8); ceiling exceeded in 3/8 |
| He DFT (LDA, N=64) | $0.1$ | $1.0$ | $0.01$ | $10^{-4}$ | 0.8% error (chemical accuracy) |
| Three-body Lagrange | $0.01$ | $1.0$ |—| $10^{-4}$ | Stable triangle, 500+ steps |
| Mercury precession | $0.1$ |—|—|—| 42.98''/cy (GR recovered) |

No sector requires different values. This universal consistency is a nontrivial
check that Cassi is not over-parameterized.

---

## 9. Canonical Symbol Table

Symbols used framework-wide that are not parameter rows above (or names for rows that are). Bare $\alpha$ is prohibited repo-wide; always subscript.

| Symbol | Canonical meaning | Value / expression | Notes |
|---|---|---|---|
| $\varphi$ | universal scale-separation constant | $(1+\sqrt{5})/2 = 1.618033989$ | F-class axiom (§1) |
| $\alpha_0$ | equilibrium Yang fraction ($\pi/\rho$ at the $\varphi$-fixed point) | $\varphi^{-3} \approx 0.236$ | = $G_{\text{eff}}/G$ at fixed point; relabel—the true fixed-point Yang fraction is $\varphi^{-1}$ (ledger §10) |
| $\alpha_{\text{halo}}$ | galactic/halo Yang fraction (SPARC fits) | $\approx 0.7$ | hardcoded nominal (path8:65); no SPARC fit of $\alpha$ in repo—real v9 fits peak at 0.17–0.53 (ledger §10) |
| $\alpha_w$ | attractor conversion weight | $\varphi^{-1} \approx 0.618$ | = $r/(1+r)$ at $r = \varphi$ in $H_{\text{eff}}^2$; row in §2.1 |
| $\varepsilon$ | field deviation | $\varepsilon = E_Y - \varphi E_I$ | core physics (governing-equation pair); keep $\varepsilon$ |
| $\varepsilon_{\text{soft}}$ | Coulomb softening (numerical) | $0.02\,a_0$ | numerical (§6 row); distinct from the field deviation $\varepsilon$ |
| $\sigma$ | regularization scale | $\ell_{\text{Pl}}/\varphi^3$ | gravity cores, UV-finite propagator; **Derived** (rung identity $\ell_{\text{Pl}}/\varphi^3$), registry G1; no ledger row (not Calibrated/Mapped) |
| $\sigma_r$ | spatial ratio dispersion | dynamic state variable | consciousness master variable (registry M4) |
| $\theta_{\text{cond}}$ | condensation threshold | $0.45$ (at $R \approx 0.093$) | calibrated to phenomenology at step 285 (ledger §10); not an a-priori fixed point |
| $\mathcal{M}$ | phase-matching factor | $\approx 1$ organized / $\approx 0$ random | quantum-measurement derivation (Q7) |
| $g$ | Wu Xing freeze-out gap | $1 - \varphi^{-5} \approx 0.9098$ | derived identity |
| $\Lambda_Y$, $\Lambda_I$ | wake wavelengths | $\ell_n$ and $\ell_n/\varphi$ | distinct from the conversion rate $\lambda$ (`foundations/wake-geometry.md`) |
| $\lambda$ | conversion rate | $1/(2w) = 0.1$ | keep—do not reuse $\lambda$ for wavelengths or the C1 mechanism scale ($\kappa_{\text{DE}} = 3\varphi^2 H_0$) |

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
| η exponent (−44) | "Derived" claimed by baryon-asymmetry.md §4; registry Hypothesized | Nearest-integer $\varphi$-power to $\eta_{\text{obs}}$ chosen from a search table over exponents 43–46 (exact log = 44.13); freeze-out step 52 = 60 − 8 assembled backwards | $\eta_{\text{obs}} \approx 6.0\times10^{-10}$ (PDG $6.104 \pm 0.058 \times 10^{-10}$) | 01-core.md:124-126; 02-sm.md:71-75; 03-cosmo.md:117-123 | Mapped |
| $\delta_{\text{CKM}} = \pi\varphi^{-2} \approx 68.8°$ | Catalog "✅ Within MoE" | 4-candidate search table (π−arccos(φ⁻¹) = 128° No; πφ⁻³ = 42.5° No; 2πφ⁻³ = 85° Close; πφ⁻² = 68.8° **Yes**); the winner is promoted to "the Cassi prediction" | CKM phase $\sim 69.2° \pm 3.0°$ (repo anchor; PDG 2024: $65.55° \pm 1.55°$, +2.07σ) | 01-core.md:223-225; 02-sm.md:88-89 | Mapped |
| Neutrino offsets $\Delta_1 = 1.00$, $\Delta_2 = 1.75$ | "pinned" (registry Q3) | Quarter-rung grid scan over $\Delta_1 \in \{0.25,\dots,2.0\}$, $\Delta_2 \in \{0.5,\dots,4.25\}$ sorted by $\|R_{\text{pred}} - R_{\text{obs}}\|$ ("← BEST"); script prints "match by construction"; 2 parameters, 2 data points, 0 dof; $m_1$ solved from data; $\Delta_2 = 1.75$ breaks the framework's own 2:1 rule | $\Delta m^2_{21} = 7.41\times10^{-5}$, $\Delta m^2_{31} = 2.511\times10^{-3}$ eV² | 02-sm.md:39-53, 166; 01-core.md:128-130 | Mapped |
| $\alpha_{\text{halo}} \approx 0.7$ | Hardcoded nominal (path8:65, path9:60); registry says "(SPARC fits)" | Hardcoded `ALPHA_HALO = 0.7`; no SPARC fit of α in repo; the real v9 Yang fractions peak at 0.17–0.53 | (claimed) SPARC rotation curves | 04-grav.md:16, 160; 01-core.md:164 | Mapped |
| Halo $q \approx 0.7$ (0.61–0.71) | $q \approx 0.67$ (registry G-series); GW row constrains $q < 0.1$–$0.3$ | $q(\rho)$ law with environment-tuned $\rho_{\text{ref}}$ (free per environment); boost $v_C/v_B = \sqrt{\alpha(1+\xi q)}$ needs $q = 0.61$–$0.71$ | MW rotation-curve boost $2.7 \pm 0.5$ | 04-grav.md:29-58, 159 | Mapped |
| $\theta_{\text{cond}} = 0.45$ | "fixed point, not a free parameter" (§9 symbol table) | Calibrated to ~0.45 at step 285 using phenomenology; the P(k) wake-wave amplitude band (1–3%) is set by it | Bubble-edge condensation phenomenology; DESI P(k) amplitude | 01-core.md:164; 03-cosmo.md:92 | Calibrated |
| $\chi$ (sector-coupling mobility) | C-class solver parameter ($\chi = 1.0$); "Empirical—no independent derivation" | Value set empirically (range 0.5–1.0); no derivation | PDE solver phenomenology | 01-core.md:164; 02-sm.md:148-150 | Calibrated |
| $N_{\text{pde}} \approx 2.35\times10^3$ | Back-solved normalization | Chosen so the $\kappa_s \to \chi$ bridge lands in the calibrated band: $4.254\times10^{-4} \times 2.35\times10^3 = 0.9997$ | Calibrated $\chi$ band $[0.5, 1.0]$ | 02-sm.md:148-150 | Mapped |
| $\Delta b = 1.70$ | "Ongoing" (catalog row 9) | Free beyond-SM particle content chosen to close the $\alpha_s$ gap: ~1 vector-like colored fermion pair + 2 colored scalars, or ~3 KK levels—three incompatible options, none chosen; the same content is reused for $M_{\text{GUT}}$, the quark-mass gaps, and the proton lifetime | $\alpha_s(M_Z) = 0.118$ | 02-sm.md:79-83; 01-core.md:110, 149 | Mapped |
| $\mu_* = 233$ GeV | $\sin^2\theta_W$ "exact at $\mu_*$" | Matching scale chosen as the crossing point where the measured running $\sin^2\theta_W$ equals $\varphi^{-3}$; $\mu_* = F_{13}$—a re-anchoring, not a prediction | Measured running $\sin^2\theta_W(\mu)$ | 02-sm.md:11-23; 01-core.md:149 | Calibrated |
| μ, J/ψ rung placements ($n = 96.000$, 89) | "Prediction 45 (closure-ladder mass placements)" | Discovered by the 2026-08-03 38-state mass scan; the muon's $\delta = -0.0002$ is the sharpest of ~40 draws ($P(\text{any within } \pm 0.0002) \approx 1.5\%$); $n = 96$ is not on the closure ladder | 38 measured masses (PDG) | 01-core.md:76-80; 02-sm.md:108-140 | Mapped |
| $m_e$/$m_\mu$/$m_\tau$ rung placements | $m_e$ "Partial (~25% off)"; $m_\mu$, $m_\tau$ miss by 335×/9104× | $m_e$ exponent $n_e = 26.5$ solved from the observed mass; μ/τ placements read off measured masses | $m_e$, $m_\mu$, $m_\tau$ | 01-core.md:147, 196-212; 02-sm.md:160 | Mapped |
| $M_{\text{GUT}} \approx 2\times10^{16}$ GeV | "GUT rung $n = 13.33$" in the cascade table | Scale set by RGE running with the free $\Delta b = 1.70$ content; rung addresses unified at $n = 13.33$ (2026-08-03 arithmetic sweep; $2\times10^{16}$ GeV falls between integer rungs: $n = 13.33$) | Gauge-coupling running; proton-decay bound | 02-sm.md:103, 172; 01-core.md:97 | Mapped |
| Proton-lifetime exponent ($n = 91.5$, $N = 4506$; boxed $\tau_p \approx 4\times10^{34}$ yr) | "Derived (from the coherence budget); not testable" (registry Q9) | Rung fixed to the repo's own mass ladder ($n = 91.46$, 2026-08-03 arithmetic sweep); per-rung survival $q_i = 1 - \varphi^{-i-\delta}$ is Hypothesized ("alternative scalings possible"); the boxed formula with its own inputs gives $1.3\times10^{37}$ yr, 323× the boxed number | Proton mass; Super-K bound | 02-sm.md:101-106; 01-core.md:120-122 | Mapped |
| $r = \varphi^{-12} \approx 0.003$ | Catalog "✅ Within bound" | Exponent matched post-hoc: all three of the doc's own formulas fail ($\varphi^{-6} \neq 0.003$; $12/40^2 = 0.0075$; $(16/\pi)\xi q/\varphi^{40} = 2\times10^{-7}$) | Planck+BICEP bound $r < 0.03$ | 03-cosmo.md:59-62, 163 | Mapped |
| $w_0$ coupling form ($-0.87$) | "Derived—2σ from DESI" (registry T1); tension labeled | ODE calibrated to the hardcoded `TARGET_W0` (synced to −0.87 on 2026-08-03; formerly −0.838) cited as "the DESI measurement"; coupling form revised toward DESI (−0.838 → −0.856 → −0.862 → −0.872 → −0.87); still 2σ/2.7σ tension at the Calibrated baseline; with the ratified conversion→expansion coupling (Hypothesized—08): $w_a$ → $1.25\sigma$ (B2, unstable), $w_0$ → $3.6\sigma$ at fixed $r_0$; the stable realization (friction closure—10/12) gives the pure-Λ window fit $(w_0, w_a) = (-1, 0)$ (4.17σ/2.61σ; $w_0$ pinned at $-1$ for every $r_0 \in [0.01, 1.1]$—$r_0$ re-tuning closed negatively, 12 §4.1) | DESI DR2 ($w_0 \approx -0.75 \pm 0.06$, $w_a$) | 03-cosmo.md:18-25, 157 | Calibrated |
| $\kappa_{\text{DE}} = 3\varphi^2 H_0$ | "Calibrated" (open-questions C1); 2σ tension, not resolved | Calibrated via the $w_0$ coupling anchored to DESI (2σ tension); $3\varphi^2 = K_{md}$ is a Wu Xing coefficient (Derived), but $\kappa_{\text{DE}}$ as a whole has no independent derivation—a Calibrated fit, no free parameters beyond the anchoring | DESI DR2 ($w_0 \approx -0.75 \pm 0.06$, $w_a$) | 03-cosmo.md:18-25, 157 | Calibrated |
| $\xi = \varphi^6 \approx 17.944$ | "Derived—ξ within 0.3% of empirical" (registry C2/G4) | Rung identity Derived ($\varphi^6 = \varphi^5 + \varphi^4$); empirical pin $\xi \approx 18$ calibrated on the Milky Way rotation curve; the MW "Already consistent" row is the calibration object re-read | Milky Way rotation curve ($r = 7$ kpc) | 04-grav.md:17-25; 01-core.md:141 | Calibrated (rung identity Derived) |
| $v_0/M_{\text{Pl}}$ exponent $N \approx 79.7$ | "Derived" (registry Q1); inventory: "notable numerical coincidence, but not a derivation" | $N = \log_\varphi(M_{\text{Pl}}/v_0)$ is the log of the measured ratio (79.89); the suppression doc quotes $N = 72$ for the same gap (factor 45 off) | $v_0 = 246$ GeV | 01-core.md:112-114 | Mapped |
| $G_{\text{eff}}$ π/ρ ↔ $\alpha_0$ equality ($\varphi^{-3}$) | "Equilibrium Yang fraction" ($\alpha_0$) | Relabel: at the $\varphi$-fixed point the Yang fraction is $\varphi^{-1}$, not $\varphi^{-3}$; three α values (0.236, 0.618, 0.7) share one symbol | Fixed-point ratio (derived); value selected | 04-grav.md:121-125 | Mapped (relabel) |
| $n_s$: $N_e = 40$ window | "Gate correction Closed—1.0σ from Planck" | E-fold window (steps 20–60) labeled after the fact: 40 rungs = 19.25 e-folds by the ladder's own formula; the closed form is not reproduced by the repo's own script (its §7 integrates $N_{\text{eff}} = 43.22$); $r = 12/N_e^2$ needs $N_e = 63.2$ | Planck 2018 $n_s = 0.9649 \pm 0.0042$ | 03-cosmo.md:53, 108-113; 01-core.md:182-186 | Mapped |
| $\Omega_{\text{DM}}/\Omega_b = \varphi^3 + 1 \approx 5.24$ | "zero free parameters" (observational-seti.md) | Hand-added +1 term; combination selected from $\{\varphi^3, \xi, \varphi^2, \varphi^4, \varphi^3 \pm 1\}$ after $\varphi^3$ alone came in 21% off | $\Omega_{\text{DM}}/\Omega_b = 5.39$ (Planck) | 06-hyp.md:161-166 | Mapped |
| CMB $C_2$ normalization | "Fibonacci ratio" in the axis pipeline | $C_2$ calibrated to the observed 200 μK² | Observed CMB power | 03-cosmo.md:81 | Calibrated |
| $r_d$ half-step 284.5 = 150.0 Mpc | Catalog "PASS"; "an 11σ near-miss" | Half-step interpolation convention chosen after the measurement (measured rung 284.46); predicted vs observed 150.0 vs $147.1 \pm 0.26$ Mpc | BAO ruler $r_d = 147.1 \pm 0.26$ Mpc | 03-cosmo.md:101 | Mapped |
| Milky Way bubble-edge rung $n \approx 267$ | "Bubble edge" label (dark-matter doc) | Rung number = the coordinate map of the measured size ($\ell_{267} = $ MW diameter); a label, not a prediction | Milky Way diameter | 06-hyp.md:179-180 | Mapped |
| Dark-matter "0.1% match" ($\varphi^{-183} \approx \alpha_G$) | "Most precisely verified prediction" (dark-matter doc) | Exponent read off the measured proton mass: $\varphi^{-2n} \equiv (m_p/M_{\text{Pl}})^2 \equiv \alpha_G$ by definition; as written the value is 3.7% off $\alpha_G$ | $m_p$, $M_{\text{Pl}}$ | 06-hyp.md:168-174, 222 | Mapped |
| Wolfenstein $A = 0.810$ | $\|V_{cb}\|$, $\|V_{ub}\|$ "Consistent" | $A$ fixed from data; $\|V_{cb}\|$, $\|V_{ub}\|$ not predicted ($\lambda = \varphi^{-3}$ assumed) | CKM magnitudes | 02-sm.md:95 | Calibrated |
| $\sigma_8$: $\mu(k,a)$ normalization | "Slightly lower ~5%" claim; pipeline gives −43% | Plan target row labeled "target, matching observations" ($\mu = 0.980 \to -5.3\%$); free $\mu$ normalization and $q(k,a)$ machinery | Low-z weak lensing $\sigma_8$ | 03-cosmo.md:139 | Mapped |
| GWTC-4 "coincidences" (3 near-hits) | "Worth recording" (gwtc4-mass-ladder.md) | Point-estimate near-hits selected after the fact from ~200 events (expectation of 0.03-rung hits over the catalog ≈ 12); the posterior-weighted test is null | GWTC-4 compact-object masses | 06-hyp.md:78-82 | Mapped |

**Row count: 29.** A row here does not settle the quantity's physics—it settles
its honesty. Each entry carries the tier the claim must bear (Calibrated or
Mapped) until the fit is replaced by an independent derivation; the re-tier
stage propagates these labels to the documents that cite the quantities.

# Closing the Gaps: Derivation of Residual Parameters

## Status: Reference—August 2026

## Abstract

The remaining underived quantities in the Cassi two-fluid framework are
cataloged, classified, and bounded, closing the parameter-inventory gaps
documented in `parameter-inventory.md`. Each derivation is assessed for
whether it fully resolves the gap, partially narrows it, or identifies an
irreducible barrier.

---

## 1. $\alpha_s(M_Z)$—The Strong Coupling at the Z Pole

### 1.1 Current Status

The Cassi framework predicts the GUT coupling:

$$\alpha_{\text{GUT}} = \frac{\varphi^{-3}}{4\pi} \approx \frac{1}{53.2} \approx 0.0188$$

The strong coupling at $M_Z = 91.2$ GeV is determined by RGE running:

$$\alpha_s^{-1}(M_Z) = \alpha_{\text{GUT}}^{-1} - \frac{b_{\text{eff}}}{2\pi} \ln\frac{M_{\text{GUT}}}{M_Z}$$

where $b_{\text{eff}}$ is the effective QCD beta-function coefficient between
$M_Z$ and $M_{\text{GUT}}$.

### 1.2 Correction: The 11× Claim

The parameter-inventory states $\alpha_s(M_Z)$ is $11\times$ too small due to
an incorrect RGE sign. The correct calculation:

For SM SU(3) with $n_f = 6$ flavors: $b_{\text{SM}} = 11 - \frac{2}{3}n_f = 7$.

$$\alpha_s^{-1}(M_Z) = 53.2 - \frac{7}{2\pi} \times 32.3 = 53.2 - 36.0 = 17.2$$

$$\alpha_s^{\text{SM}}(M_Z) = \frac{1}{17.2} = \mathbf{0.058}$$

**The gap is $2.0\times$**, not $11\times$. The observed $\alpha_s(M_Z) = 0.118$
requires $\alpha_s^{-1}(M_Z) = 8.47$.

### 1.3 Required $b_{\text{eff}}$

$$b_{\text{eff}} = \frac{(53.2 - 8.47) \times 2\pi}{32.3} = \mathbf{8.70}$$

The difference from SM: $\Delta b = b_{\text{eff}} - b_{\text{SM}} = 1.70$.

### 1.4 Physical Origin of $\Delta b$

Each additional colored degree of freedom between $M_Z$ and $M_{\text{GUT}}$
shifts $b$:

| Particle type | $\Delta b$ per flavor/multiplet |
|---------------|-------------------------------|
| Dirac fermion (3) | $+4/3 \approx +1.33$ |
| Complex scalar (3) | $+1/6 \approx +0.17$ |
| Vector-like fermion pair | $+4/3$ |
| KK mode (5D, one level) | multiple of above |

**To get $\Delta b = 1.70$**: approximately **1 vector-like colored fermion
pair** ($+1.33$) plus **2 colored scalars** ($+0.34$), or **3 KK levels**
of the SM fields.

### 1.5 Derivation Status

| Aspect | Status |
|--------|--------|
| $\alpha_{\text{GUT}}$ from $\varphi$ | **Derived**—$\varphi^{-3}/(4\pi)$ |
| $b_{\text{eff}}$ from $\varphi$ | **Not derivable**—requires particle content between EW and GUT scales |
| $\Delta b = 1.70$ | **Narrowed**—gap reduced from $11\times$ to $2.0\times$; the $1.70$ shift is modest, consistent with SUSY/KK thresholds |
| Full derivation | **Partial**—the coupling at $M_Z$ follows from $\varphi$ **given** the particle content. $\varphi$ does not determine the particle content; this is a separate specification. |

**Conclusion**: $\alpha_s(M_Z)$ is NOT derivable from $\varphi$ alone. The gap
is a factor of 2.0, consistent with threshold corrections from new physics
between the EW and GUT scales. The specific particle content that would close
the gap ($\Delta b = 1.70$) is modest and plausible but not uniquely determined.

---

## 2. $m_e/v_0$—The Electron-to-Electroweak Mass Ratio

### 2.1 Current Status

In the Cassi Yukawa hierarchy, the electron Yukawa is a $\varphi$-power:

$$y_e = \varphi^{-n_e}, \qquad m_e = \frac{y_e v_0}{\sqrt{2}}$$

The nearest integer exponents:

| $n_e$ | $m_e$ (MeV) | Error |
|-------|-------------|-------|
| 26 | 0.641 | $+25\%$ |
| 27 | 0.396 | $-22\%$ |
| **Observed** | **0.511** |—|

The half-integer $n_e = 26.5$ gives $m_e = 0.504$ MeV ($-1.4\%$).

### 2.2 The Half-Integer Exponent Is a Fit, Not a Mechanism

The exponent $n_e = 26.5$ in §2.1 is **solved from the observed mass**—
$n_e = \ln((v_0/\sqrt2)/m_e)/\ln\varphi$—so the 1.4% agreement at
$\varphi^{-26.5}$ is a rearrangement of the input, not a prediction. The
geometric-mean identity

$$y_e = \sqrt{\varphi^{-26} \cdot \varphi^{-27}} = \varphi^{-26.5}$$

holds for any fractional exponent, so it does not select $26.5$: a mechanism
would have to predict the half-step offset without inputting $m_e$. The
pool-cell quantization (`foundations/rung-offset-mechanism.md` §4.1) gives
half-integer positions a wave-mechanical status—the fundamental-mode antinode
of the terminal cell—but it does not place the cell: why $[26, 27]$ and not
$[25, 26]$ remains empirical, so $n_e = 26.5$ is still solved from the
observed mass.

The charged leptons do not sit on integer rungs of the $v_0/\sqrt2$ ladder at
all. Solving $n = \ln((v_0/\sqrt2)/m)/\ln\varphi$ from the observed masses:

| Lepton | $n$ (v$_0$ ladder) | Nearest half-step | Mass at nearest integer rung |
|--------|---------------------|-------------------|------------------------------|
| $\tau$ | 9.53 | 9.5 | rung 9: 2.29 GeV (+29%) |
| $\mu$ | 15.39 | 15.5 | rung 15: 127 MeV (+20%) |
| $e$ | 26.47 | 26.5 | rung 26: 0.64 MeV (+25%) |

Every charged lepton lands within $\pm 0.25$ steps of some half-integer, which
is automatic for any continuous placement; the residuals (1.2%, −5.0%, −1.5%
at the nearest half-steps) carry no ladder structure. The "truncation at the
lightest state" story predicts the position class (the half-rung, via the
pool-cell quantization of `foundations/rung-offset-mechanism.md` §4.1) but
nothing about where the cells sit.

The sharper reference frame is the $M_{\text{Pl}}$-anchored mass ladder
(`foundations/wake-geometry.md` §3, $n = \log_\varphi(M_{\text{Pl}}/m)$). There
the electron sits at $n = 107.08$—a 3.9% near-miss of rung 107, the rung that
`foundations/dimensionful-cascade.md` lists as the electron's reduced Compton
wavelength ($\ell_{107} = 3.72\times10^{-13}$ m vs $\hbar/m_ec = 3.86\times10^{-13}$ m,
3.7% off). Unlike the muon ($n = 96.000$, 0.01%) and J/ψ ($n = 88.98$, 1.0%),
the electron is a near-miss rather than a catalog hit.

### 2.3 Qi Gate Boundary Condition (Hypothesized)

The half-step can be parameterized as a Qi-gate correction to the integer-rung
Yukawa:

$$y_e^{\text{eff}} = \varphi^{-26} \times f(q_e), \qquad f(q) = \varphi^{-q}$$

with $q_e = 0.5$ reproducing the observed mass. This is a restatement of the
fit, not a derivation: $q_e = 0.5$ is set to match $m_e$, and no PDE or gate
calculation fixes the gate opening at the electron scale. A formal derivation
would have to produce $q_e = 0.5$ from the two-fluid dynamics at the base of
the lepton hierarchy; none exists yet.

### 2.4 Derivation Status

| Aspect | Status |
|--------|--------|
| $m_e$ from $\varphi^{-26}$ alone | **Not derivable**—25% gap at integer rungs 26/27 |
| $m_e$ from $\varphi^{-26.5}$ (half-step) | **Not derivable**—$n_e = 26.5$ is solved from the observed mass; the half-rung position is the pool-cell fundamental antinode (Hypothesized, `foundations/rung-offset-mechanism.md` §4.1) but the cell placement is empirical; the 1.4% agreement is a fit, not a prediction |
| $m_e$ on the $M_{\text{Pl}}$ mass ladder | **Near-miss**—$n = 107.08$ vs rung 107 (3.9%), the rung of the reduced Compton wavelength (3.7% off); not a catalog hit |
| $q_e = 0.5$ (Qi gate boundary) | **Hypothesized**—set to match the fit; awaits formal PDE derivation |

**Conclusion**: The electron mass is not derivable from $\varphi$. It misses
the integer rungs of the $v_0/\sqrt2$ ladder by $\pm 25\%$, sits 3.9% off rung
107 of the $M_{\text{Pl}}$ mass ladder, and the 1.4% half-step agreement is a
fit to the observed mass rather than a prediction. The electron mass remains
an external input (`parameter-inventory.md` §4.2, class **E**).

---

## 3. $v_0/M_{\text{Pl}}$—The Electroweak-to-Planck Ratio

### 3.1 Current Status

The dimensionful cascade predicts scale ratios as $\varphi$-powers:

$$\frac{E_n}{E_{\text{Pl}}} = \varphi^{-n}$$

For the electroweak scale ($v_0 = 246$ GeV, $E_{\text{Pl}} = 1.22 \times 10^{19}$ GeV):

$$\frac{v_0}{E_{\text{Pl}}} = 2.02 \times 10^{-17}$$

The nearest integer cascade step is $n = 80$:

$$\varphi^{-80} = 1.91 \times 10^{-17}$$

Gap: $\frac{2.02}{1.91} - 1 = 5.3\%$.

### 3.2 Cascade Discretization Residual

The exact cascade exponent is:

$$n_{\text{EW}} = \frac{\ln(E_{\text{Pl}} / v_0)}{\ln\varphi} = \frac{38.44}{0.4812} = 79.89$$

The residual $\delta n = 80 - 79.89 = 0.11$ steps corresponds to a factor
of $\varphi^{0.11} = 1.053$, exactly matching the 5.3% gap.

**This is not a failure of the $\varphi$-cascade—it is a direct consequence
of the cascade being a continuous spectrum with $\varphi$-spacing.** The
electroweak scale sits at $n = 79.89$, not exactly at the integer $n = 80$.
The cascade does not force integer $n$; it forces $\varphi$-spacing. Any
physical scale is at some $n$, and $n$ is not constrained to be an integer.

### 3.3 Why $n = 79.89$?

The electroweak scale is the **boundary** between two cascade regimes:
- Above: GUT-scale physics (steps ~0 to ~79)
- Below: low-energy physics (steps ~80 to ~292)

The boundary condition at this interface could produce a fractional step
offset, but the specific value $\delta n = 0.11$ is not derived from it—it is
read off the observed $v_0$, and §3.2 already accounts for it as a
continuous-spectrum residual. The electron's $\delta n = 0.50$ carries no
predictive weight here: that offset is itself fit to observation (§2.2).

### 3.4 Derivation Status

| Aspect | Status |
|--------|--------|
| $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ | **Consistent**—5.3% residual at the closest integer power; a numerical coincidence, not a derivation (`parameter-inventory.md` §4.1) |
| $\delta n = 0.11$ offset | **Identified**—cascade discretization residual |
| Physical mechanism for $\delta n = 0.11$ | **Plausible**—EW-scale boundary between cascade regimes |
| Exact derivation of $\delta n$ | **Not derivable**—would require full cascade boundary dynamics |

**Conclusion**: The $v_0/M_{\text{Pl}}$ ratio is consistent with $\varphi^{-80}$
at 5.3%—a small residual from the cascade discretization. The exact offset
$\delta n = 0.11$ is understood as the EW scale sitting between integer cascade
nodes, but the specific value awaits formal cascade boundary dynamics.

---

## 4. The Activated Step Set $\{1, 2, 3, 5, 6, 26, 80\}$

### 4.1 What "Activated" Means

In the dimensionful cascade, each step $n$ corresponds to a physical scale
$\ell_n = \ell_{\text{Pl}} \times \varphi^n$. Most steps are **dark**—they
exist mathematically but do not correspond to independently observable
phenomena. "Activated" steps are those where the $\varphi$-power exponent
appears in a **verified physical quantity**.

### 4.2 The Catalog

| Step $n$ | $\varphi^n$ | Physical Quantity | Verification |
|----------|-------------|-------------------|-------------|
| 1 | 1.618 | Fundamental ratio $r = E_Y/E_I$ | Postulate |
| 2 | 2.618 | Qi gate normalization denominator | PDE structure |
| 3 | 4.236 | $\sin^2\theta_W = \varphi^{-3}$, Yang fraction $\varphi^{-3}$ | 2.1% (tree) |
| 3 | 4.24 | $\kappa_s^{-1/2} = \varphi^3 v_0 \approx 1.04$ TeV (sector coupling) | 5.5% (vs rung 77); coefficient $C$ open |
| 5 | 11.09 | Wu Xing scale, gap $g = 1-\varphi^{-5}$ | $w_0 = -0.87$ ($2\sigma$ from DESI $\approx -0.75 \pm 0.06$ [INF]) |
| 6 | 17.94 | $\xi = \varphi^6$ (Qi-gravity coupling) | $v_C/v_B = 2.9$–$3.1$ (~1.2σ) |
| 26 | $2.7\times 10^5$ | $m_e/v_0 \approx \varphi^{-26}$ (human cascade depth) | 25% (integer rung 26); the half-step 26.5 is a fit to the observed mass, not a derivation (§2.2) |
| 80 | $5.2\times 10^{16}$ | $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ | 5.3% |
| 89 | $3.94\times 10^{18}$ | $M_{\text{Pl}}/m_{J/\psi} \approx \varphi^{89}$ (charmonium ground state) | 1.0% (2026-08-03, closure level) |
| 96 | $1.16\times 10^{20}$ | $M_{\text{Pl}}/m_\mu \approx \varphi^{96}$ (muon mass) | 0.01% (2026-08-03, sharpest placement) |

### 4.3 Why These and Not Others?

The set $\{1, 2, 3, 5, 6, 26, 80, 89, 96\}$ is **not derivable from $\varphi$**.
It is an **empirical catalog**—the subset of $\varphi$-powers that happen to
correspond to observable quantities in our universe.

Steps $\{4, 7, 8, \ldots, 25, 27, \ldots, 79, 81, \ldots, 88, 90, \ldots, 95, 97, \ldots\}$ are **dark** —
they exist in the cascade spectrum but do not (yet) correspond to independently
measured physical couplings or scale ratios. They may correspond to:
- Unobserved particles or forces
- Sub-dominant corrections to known quantities
- Scales that have not been probed experimentally
- Pure mathematical scaffolding connecting activated nodes

### 4.4 Activated vs Fibonacci

The first four activated steps $\{1, 2, 3, 5\}$ are the first four Fibonacci
numbers. Step 6 is the product of Fibonacci primes $2 \times 3$. The larger
steps (26, 80, 96) are not Fibonacci-related in any obvious way—they emerge
from the cascade depth rather than number-theoretic properties. Step 89 is
Fibonacci ($F_{11}$) and a golden-angle closure level: the J/ψ placement at
$n = 88.98$ (1.0%, 2026-08-03) is the first mass-catalog hit on a closure
level (`foundations/wake-geometry.md` §3).

The Fibonacci pattern at low $n$ is likely coincidental: $\varphi^n$ for
small integer $n$ naturally approximates Fibonacci ratios $\varphi^n \approx
F_{n+1} / F_n$ with increasing accuracy as $n$ grows, but this is a
mathematical identity, not a physical selection mechanism.

### 4.5 Derivation Status

| Aspect | Status |
|--------|--------|
| Which steps are activated | **Empirical**—observed from verified $\varphi$-power predictions |
| Why $\{1, 2, 3, 5\}$ and not $\{4, 7, 8\}$ | **Not derivable**—these are the exponents that happen to map to observable couplings in our universe |
| Fibonacci coincidence at low $n$ | **Mathematical identity**—$\varphi^n \approx F_{n+1}/F_n$, not a physical selection |
| Dark steps (4, 7, 8-25, 27-79, 81-88, 90-95, 97+) | **Prediction**—these correspond to unobserved scales/couplings; their darkness is a testable feature (89 and 96 were dark until the 2026-08-03 mass scan placed J/ψ and μ) |

**Conclusion**: The activated step set is an empirical catalog, not a
$\varphi$-derivation. It tells us which $\varphi$-powers correspond to
observable physics in our universe. A different universe could have a
different set of activated steps while sharing the same underlying
$\varphi$-cascade.

---

## 5. Summary

| Parameter | Original Gap | Resolution | New Status |
|-----------|-------------|-----------|------------|
| $\alpha_s(M_Z)$ | $11\times$ (claimed), $2.0\times$ (actual) | RGE sign corrected; $\Delta b = 1.70$ from new physics thresholds | **Narrowed**: factor 2.0, requires particle content | 
| $m_e/v_0$ | $25\%$ (integer exponent 26) | Pool-cell quantization gives half-rung positions (Hypothesized mechanism, §2.2); cell placement empirical; $\varphi^{-26.5}$ fit to the observed mass; M$_{\text{Pl}}$-ladder rung 107 misses by 3.9% | **Open**: remains External (**E**) |
| $v_0/M_{\text{Pl}}$ | $5.3\%$ (integer exponent 80) | Cascade discretization residual ($\delta n = 0.11$, EW boundary) | **Identified**: mechanism understood, exact value not derived |
| Activated step set | No derivation | Empirical catalog of $\varphi$-powers in verified quantities | **Empirical**: not derivable, catalog of our universe |

### Classification: No Registry Changes

None of the four assessments reclassifies a parameter. The registry
(`parameter-inventory.md` §5) holds the accurate classes:

| Parameter | Class | Rationale |
|-----------|-------|-----------|
| $\alpha_s(M_Z)$ | **E** | Partial: RGE from $\alpha_{\text{GUT}}$ needs particle content (§1) |
| $m_e/v_0$ | **E** | $\varphi^{-26}$ misses by 25%; the half-step 26.5 is a fit, not a derivation (§2; pool-cell half-rung mechanism Hypothesized, `foundations/rung-offset-mechanism.md` §4.1) |
| $v_0/M_{\text{Pl}}$ | **E** | $\varphi^{-80}$ within 5.3% is a numerical coincidence, not a derivation |
| $\kappa_s$ (sector coupling) | **D** | Already derived: $\varphi^{-6}/v_0^2$ (coefficient Hypothesized) |
| Activated steps | **E** | Empirical catalog of observables that happen to be $\varphi$-powers |

Legend: **F1 / D24 / C0 / E7 / I6 / N8 / Total 46**.

The assessments narrow the gaps without moving classes: $\alpha_s$ requires a
specific particle content between the EW and GUT scales, and $m_e$ and
$v_0/M_{\text{Pl}}$ remain empirical near-misses (25% and 5.3% on the nearest
integer rungs; 3.9% for $m_e$ on the $M_{\text{Pl}}$ ladder). The dimensionful
constants ($G$, $c$, $\hbar$) cannot be derived from a dimensionless
constant—this is a feature of any theory, not a bug.

---

## References

- `parameter-inventory.md` §4—parameter classes (F/D/C/E/I/N)
- `foundations/dimensionful-constants-status.md`—status of $c$, $\hbar$, $G$
- `foundations/wake-geometry.md` §3—$M_{\text{Pl}}$-anchored mass ladder
- `foundations/dimensionful-cascade.md`—cascade table, rung labels
- `foundations/xi-derivation.md`—$\xi = \varphi^6$ derivation
- `foundations/wu-xing-derivation.md`—$w = 5$, gap $g$

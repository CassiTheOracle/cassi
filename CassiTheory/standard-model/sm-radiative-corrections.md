# Standard Model Radiative Corrections from the φ-Boundary

## Status: Derived loop equations; Asserted φ-boundary inputs; Calibrated $\mu_*$ crossing—August 2026

## Abstract

The Standard Model's precision program is a network of loop corrections: the
running of the gauge couplings, photon vacuum polarization, electroweak
corrections to $\mu$ decay, and the Higgs-quartic running. The loop equations
are Derived from the Standard Model inputs; the Cassi values
$\alpha_{\text{GUT}}=\varphi^{-3}/4\pi$ and
$\sin^2\theta_W=\varphi^{-3}$ are boundary assignments. The calculation
reports the numerical status: standard relations close to 0.01–0.1%
($\bar\alpha(m_Z)=1/128.95$, $m_W=80.36$ GeV,
$\sin^2\theta_W^{\text{eff}}=0.23149$), while the φ-boundary comparison leaves
$\alpha_s(m_Z)$ $2\times$ too small, $\alpha_1$ and $\alpha_2$ about 25% off,
and the asserted $\varphi^{-3}$ value 2.1% above the Z-pole value. The crossing
$\mu_*\approx233$ GeV is Calibrated from the measured running trajectory.
All statements trace to `computations/sm_radiative_corrections.py`.

---

## 1. Why Radiative Corrections Matter for Cassi

The Cassi framework fixes couplings at the $\varphi$-point and must compare
them with Z-pole measurements. That comparison is not a tree-level one: the
measured observables ($\alpha_s(m_Z)$, $\sin^2\theta_W(m_Z)$, $m_W$) receive
loop corrections of 1–10% from the Standard Model itself. This document
performs the full computation. Two directions are needed:

- **Direction A (prediction):** the φ-anchored boundary conditions at
  $M_{\text{GUT}}$ are run *down* to $m_Z$ with the full SM radiative
  corrections, producing predictions for the Z-pole observables.
- **Direction B (consistency):** the measured Z-pole values are run *up* to
  test unification claims ($\alpha_1 = \alpha_2$ at $M_{\text{GUT}}$,
  $\sin^2\theta_W(M_{\text{GUT}}) = \varphi^{-3}$).

Both directions are computed at one loop with decoupling thresholds (top quark,
W/Z/H), two-loop QCD for $\alpha_s$, the hadronic vacuum polarization for
$\alpha$, and the compact one-loop-plus-leading-two-loop formula of Ferroglia,
Ossola, Passera and Sirlin for the $W$ mass. All numbers below are printed by
`computations/sm_radiative_corrections.py`.

The precision program is over-constrained: with the six inputs $\alpha$, $G_F$,
$m_Z$, $m_t$, $m_H$, $\alpha_s$, the SM predicts ~20 observables. Any residual
discrepancy in a Cassi comparison is therefore *not* absorbable into the
radiative corrections—it is a genuine test.

---

## 2. The Radiative-Correction Program

### 2.1 What the corrections are

The one-loop corrections fall into three topological classes:

1. **Self-energies** (vacuum polarizations): $\gamma$, $W$, $Z$, and Higgs
   propagator insertions. The photon self-energy makes $\alpha$ scale
   dependent (the running of $\alpha$); the $W$/$Z$ self-energies shift the
   mass ratio (the $\rho$ parameter).
2. **Vertex corrections:** fermion–gauge couplings receive loop form factors;
   for the $Z$ they shift the effective weak mixing angle measured in
   asymmetries.
3. **Box diagrams:** in $\mu$ decay, $WW$ boxes and $\gamma$–$W$ boxes.

Two renormalization schemes are in common use (Sirlin & Ferroglia,
Rev. Mod. Phys. 85, 263 (2013)):

- **On-shell (OS):** parameters are physical masses and couplings;
  $\sin^2\theta_W = 1 - m_W^2/m_Z^2$ *by definition*. The radiative corrections
  to $\mu$ decay are encoded in a single quantity $\Delta r$.
- **MS-bar:** couplings run with scale; $\sin^2\hat\theta_W(\mu)$ is the
  running angle that enters grand-unification analyses.

The three mixing parameters relevant here are the OS value
$\sin^2\theta_W = 0.22338(21)$ (from $m_W = 80.360(11)$ via
$s^2 = 1 - m_W^2/m_Z^2$; `computations/sm_radiative_corrections.py` §4), the
MS-bar value $\sin^2\hat\theta_W(m_Z) = 0.23122(4)$, and the effective
leptonic value $\sin^2\theta_{\text{eff}}^{\text{lept}} = 0.23153(16)$
(Z-pole asymmetries).
They differ by precisely calculable loop effects; quoting one against another
without the conversion is a scheme error.

### 2.2 Input parameters

| Input | Value |
|-------|-------|
| $\alpha(0)$ | $1/137.036$ |
| $G_F$ | $1.1663788 \times 10^{-5}$ GeV$^{-2}$ |
| $m_Z$ | $91.1876$ GeV |
| $m_t$ | $172.69(30)$ GeV |
| $m_H$ | $125.25(17)$ GeV |
| $\alpha_s(m_Z)$ | $0.1180(9)$ |
| $\Delta\alpha_{\text{had}}^{(5)}$ | $0.02761(11)$ |

---

## 3. Gauge-Coupling Running: The Two Directions

### 3.1 The β-functions

With GUT-normalized couplings $\alpha_1 = (5/3)\alpha_Y$ and
$\mathrm{d}\alpha_i/\mathrm{d}t = (b_i/2\pi)\alpha_i^2$,
$t = \ln\mu$, the one-loop coefficients for the SM (one Higgs doublet, six
flavors) are

$$b = \left(+\frac{41}{10},\; -\frac{19}{6},\; -7\right),$$

so $\alpha_1$ grows with energy while $\alpha_2$ and $\alpha_3$ are
asymptotically free. Below $m_t$ the top decouples in the formal threshold
bookkeeping used by the computation:
$b_1 = 41/10 - 17/30 = 53/15 \approx 3.53$ and
$b_3 = -7 + 2/3 = -19/3 \approx -6.33$ (same sign convention). For
$\alpha_s$ the two-loop coefficient
$b_1^{\text{QCD}} = 102 - 38n_f/3$ is included.

### 3.2 Direction A: the φ-boundary run down

With the unified boundary $\alpha_1 = \alpha_2 = \alpha_3 = \varphi^{-3}/4\pi$
at $M_{\text{GUT}} = 10^{16}$ GeV (the canonical continuous value of
`parameter-inventory.md` §4.4), the one-loop running with thresholds gives at
$m_Z$:

| Quantity | φ-boundary prediction | Measured | Deviation |
|----------|----------------------|----------|-----------|
| $\alpha_1^{-1}(m_Z)$ | 74.3 | 59.0 | +26% |
| $\alpha_2^{-1}(m_Z)$ | 36.9 | 29.6 | +25% |
| $\alpha_3^{-1}(m_Z)$ | 17.3 | 8.47 | +104% |
| $\alpha_s(m_Z)$ (1-loop / 2-loop QCD) | 0.058 / 0.061 | 0.1180 | $2.0\times$ too small |
| $\sin^2\theta_W(m_Z)$ | 0.2299 | 0.23122 | −0.6% |
| $\alpha_{\text{em}}^{-1}(m_Z)$ | 161 | 128.9 | +25% |

Three remarks.

1. **The $\alpha_s$ deficit is the documented one.** $\alpha_s(m_Z) = 0.058$
   (2-loop: 0.061) reproduces the canonical value already registered in
   `parameter-inventory.md` §4.4 and `audit.md` §1.4: closing the $2\times$
   gap requires $\Delta b = 1.70$ of beyond-SM colored content. One
   conditional cascade mapping tests a vector-like quark doublet at the
   Fibonacci precursor position (`computations/cascade_gut_ew_rge.py`), but
   the particle content that supplies the shift remains unselected. The
   radiative corrections themselves do not close this gap.

2. **The $\alpha_2$ (and $\alpha_1$) deficit is large.** The correct running
   of the unified boundary $\alpha_2 = 1/53.2$ at $10^{16}$ GeV down to
   $m_Z$ gives $\alpha_2^{-1}(m_Z) = 36.9$ (25% high). The claimed
   unification $\alpha_1 = \alpha_2 = 1/53$ at $2 \times 10^{16}$ GeV does not
   occur in the SM (see §3.3).

3. **The Weinberg angle is accidentally close.** Because $\alpha_1$ and
   $\alpha_2$ miss in the *same* direction, their ratio—and hence
   $\sin^2\theta_W = \alpha_Y/(\alpha_Y + \alpha_2)$—comes out within 0.6% of
   the measured value even though both couplings individually fail by 25%.
   This is a cancellation, not a prediction that survives scrutiny:
   $\sin^2\theta_W(m_Z)$ from the φ-boundary is 0.2299 vs 0.23122 (−0.6%),
   while $\alpha_2$ itself is 25% off. Any claim that "RG running closes the
   gap" for the Weinberg angle must confront this: the running closes the
   *ratio* gap only because it preserves the ratio, and it leaves the
   underlying couplings wrong by 25%.

### 3.3 Direction B: the measured couplings run up

Running the measured MS-bar values
$(\alpha_1^{-1}, \alpha_2^{-1}, \alpha_3^{-1}) = (59.0, 29.6, 8.47)$ at $m_Z$
upward, the one-loop intersections are:

$$\alpha_1 = \alpha_2 \;\text{at}\; \mu = 1.0 \times 10^{13}\ \text{GeV}
  \quad (\alpha^{-1} = 42.4),$$

$$\alpha_2 = \alpha_3 \;\text{at}\; \mu = 1.0 \times 10^{17}\ \text{GeV}
  \quad (\alpha^{-1} = 47.1),$$

$$\alpha_1 = \alpha_3 \;\text{at}\; \mu = 2.4 \times 10^{14}\ \text{GeV}
  \quad (\alpha^{-1} = 40.3).$$

The couplings do **not** meet at a single point: in the SM, $\alpha_1$ and
$\alpha_2$ meet near $10^{13}$ GeV while $\alpha_2$ and $\alpha_3$ meet near
$10^{17}$ GeV—the classic "SM unification fails" pattern. The failure is
generic to unification-scale boundary conditions, not specific to the
$\varphi$-boundary: forcing $\alpha_3$ through the $\alpha_1 = \alpha_2$ point
predicts $\alpha_s(m_Z) \approx 0.07$ (0.071 at one loop;
`computations/sm_radiative_corrections.py` §2)—a $1.7\times$ deficit in the
same direction as the $\varphi$-boundary's $2.0\times$. The boundary
$\alpha_{\text{GUT}} = \varphi^{-3}/4\pi = 1/53.2$ is not realized
simultaneously by all three SM couplings at any scale below $M_{\text{Pl}}$;
an individual coupling can cross that value, but there is no common
intersection. A common intersection near $2 \times 10^{16}$ GeV requires
beyond-SM content between $m_Z$ and $M_{\text{GUT}}$—the same $\Delta b = 1.70$
deficit that rescues $\alpha_s(m_Z)$ (`parameter-inventory.md` §4.4).

The Weinberg angle at high scale follows from the couplings:
$\sin^2\theta_W(\mu) = \alpha_Y(\mu)/(\alpha_Y(\mu) + \alpha_2(\mu))$. With the
measured inputs,

$$\sin^2\theta_W(10^{16}\ \text{GeV}) = 0.421,
  \qquad \sin^2\theta_W(2 \times 10^{16}\ \text{GeV}) = 0.426
  \qquad \text{(SM)},$$

$$\sin^2\theta_W(2 \times 10^{16}\ \text{GeV}) = 0.381
  \qquad \text{(MSSM variant, } b = (33/5, 1, -3) \text{ above 1 TeV)}.$$

The weak mixing angle runs **upward** with energy (it approaches the
unification value $3/8$). Starting from $\sin^2\theta_W = 0.236$ at
$2 \times 10^{16}$ GeV and running down gives $\sin^2\theta_W(m_Z) \approx
0.15$ (SM) / 0.20 (MSSM), not 0.231; the value $\varphi^{-3}$ is realized in
the *upward* running of the measured angle, at

$$\boxed{\mu_* = 233\ \text{GeV}, \qquad \sin^2\theta_W(\mu_*) = \varphi^{-3} =
  0.23607.}$$

That is, the Yang/Yin asymmetry angle is realized about one e-fold above
the Z-pole, rather than at the GUT scale; at $m_Z$ itself $\varphi^{-3}$
overshoots the MS-bar value by 2.1%. This is the accurate form of the
Weinberg-angle comparison, and it is the number FCC-ee would test at
$>100\sigma$ precision (a 2.1% offset is enormous on the $3\times10^{-5}$
measurement scale—the prediction is falsifiable).

### 3.4 What fixes $\mu_*$: input provenance and the selection constraint

The crossing scale is not a fit: with the measured Z-pole couplings
$\alpha_1^{-1}(m_Z) = 59.0$, $\alpha_2^{-1}(m_Z) = 29.6$ and the one-loop SM
β-function coefficients, the condition $\sin^2\theta_W(\mu) = \varphi^{-3}$
reduces to a closed-form equation,
$\sin^2\theta_W = 3\alpha_2^{-1}/(3\alpha_2^{-1} + 5\alpha_1^{-1})$, so

$$\frac{\alpha_2^{-1}(\mu_*)}{\alpha_1^{-1}(\mu_*)} =
  \frac{5\varphi^{-3}}{3(1-\varphi^{-3})} = 0.51503,$$

whose solution is $\mu_* = 232.6$ GeV (analytic; 233.4 GeV on the grid of
`computations/sm_radiative_corrections.py` §2). Every input classifies
explicitly (`computations/mu_star_crossing_audit.py`):

| Input | Value | Provenance |
|-------|-------|------------|
| $\alpha_1^{-1}(m_Z)$, $\alpha_2^{-1}(m_Z)$ | 59.0, 29.6 (from $\hat\alpha^{-1} = 127.955$, $\sin^2\hat\theta_W = 0.23122$) | Calibrated (measured MS-bar) |
| β-function coefficients $b_1$, $b_2$ | 41/10, −19/6 | Derived (SM content) |
| $\sin^2\theta_W = \varphi^{-3} = (\varphi-1)/(\varphi+1)$ | 0.23607 | Asserted boundary (blocking step: no action-level mechanism for $(g/g')^2 = 2\varphi$; `standard-model/su2-gauge-extension.md` §3.2.1) |
| $\mu_*$ | 233 GeV | output of the RGE plus the selection; no additional fit parameter after the measured inputs and asserted boundary are supplied |

$\mu_* = 233$ GeV therefore follows from the RG equations in a limited sense:
given the measured trajectory and the asserted $\varphi$ value, the scale is
determined. It does not follow from Cassi dynamics alone. Three checks make
the anchoring explicit:

1. **Scheme sensitivity.** The value 233 sits at the low edge of the
   convention band. Full-precision MS-bar inputs give $\mu_* = 239.7$ GeV;
   adding the flavor-threshold treatment (5 flavors below $m_t$, 6 above)
   gives 243.6–251.1 GeV. The band is 232.6–251.1 GeV (±8%); propagated
   input uncertainties contribute ±1%. The 233 GeV value uses the rounded
   inputs with six flavors everywhere above $m_Z$.
2. **Rung placement.** The crossing sits at
   $n(\mu_*) = \log_\varphi(M_{\text{Pl}}/\mu_*) = 79.9\text{–}80.0$: at the
   framework's EW rung $E_{80} = M_{\text{Pl}}\varphi^{-80} = 233.2$ GeV
   (−0.2% to +7.7% across the convention band). This is a consistency
   cross-check, not an independent selection: rung 80 is a calibrated anchor
   ($n(v_0) = 79.89 \approx 80$, 5.3% residual open,
   `principles/v0-hierarchy-problem.md`; ledger row 499), and the full
   convention band places $\mu_*$ inside the same 5%-residual class as the
   VEV placement.
3. **Contrast with the φ-boundary run.** The unified-boundary trajectory
   (Direction A) has $\alpha_1^{-1}(m_Z) = 74.3$, $\alpha_2^{-1}(m_Z) = 36.9$;
   its own $\varphi^{-3}$ crossing sits at $\mu_* = 451$ GeV. The 233 GeV
   value is a property of the measured trajectory, not of the φ-boundary run
   (whose couplings miss by ~25%).

The unit-dependent reading of 233 as the Fibonacci closure number
(233 ∈ {5, 13, 34, 89, 233, 610}, `foundations/wake-geometry.md` §3b) is
rejected as a selection: the closure ladder is a dimensionless
angular-return set, and $\mu_*$ in GeV is an artifact of human units (in
natural units the crossing is at $1.9\times10^{-17}\,M_{\text{Pl}}$, i.e.
rung 80).

**Selection-constraint verdict.** The φ-selection $\sin^2\theta_W =
\varphi^{-3}$ fixes a unique scale along the measured trajectory (no free
parameter), but no two-fluid/Yin–Yang dynamics fixes that scale
independently of the measured couplings and the asserted boundary. $\mu_*$
remains a Calibrated output (ledger row 490): the running-angle crossing
locates the boundary condition's realization scale; it does not derive it.

---

## 4. The Running of α: $\bar\alpha(m_Z)$ from $\alpha(0)$

The archetypal radiative correction. The fine-structure constant at the Z
scale is

$$\bar\alpha^{-1}(m_Z) = \alpha^{-1}(0)\left(1 - \Delta\alpha\right),$$

$$\Delta\alpha = \Delta\alpha_{\text{lept}} + \Delta\alpha_{\text{had}}^{(5)}
  + \Delta\alpha_{\text{top}} = 0.03150 + 0.02761 - 0.00007 = 0.05904,$$

where the leptonic piece is known to three loops, the hadronic piece is
obtained from $e^+e^- \to$ hadrons data via dispersion relations, and the top
piece is perturbative and negative. The result,

$$\boxed{\bar\alpha^{-1}(m_Z) = 128.95
  \quad\text{(OS)},\qquad
  \hat\alpha^{-1}(m_Z) = 127.955
  \quad\text{(MS-bar)}}$$

reproduces the measured value 128.9 at the 0.05% level. This is a pure SM
closure, independent of φ. Running the φ-boundary coupling
$\alpha_{\text{GUT}} = \varphi^{-3}/4\pi$ down from $10^{16}$ GeV gives
$\alpha_{\text{em}}^{-1}(m_Z) = 161$ (25% high, §3.2): the value 128.9 is
derived from $\alpha(0)$ plus the vacuum polarization, not from the GUT
boundary.

---

## 5. Δr and the W Mass

### 5.1 The master relation

The Fermi constant measured in $\mu$ decay is related to the gauge sector by
the on-shell relation (Sirlin 1980; modern convention as in Sirlin &
Ferroglia 2013, footnote 8):

$$\boxed{s^2 c^2 = \frac{\pi\alpha(0)}{\sqrt{2}\,G_F m_Z^2}\,(1 + \Delta r),
  \qquad s^2 = 1 - \frac{m_W^2}{m_Z^2}}$$

with $\Delta r$ the complete electroweak correction to $\mu$ decay. With the
measured $m_W = 80.360(11)$ GeV this yields $\Delta r = 0.0379$. The famous
decomposition is

$$\Delta r = \Delta\alpha - \frac{c^2}{s^2}\,\Delta\rho + \Delta r_{\text{rem}},$$

$$\Delta\rho = \frac{3G_F m_t^2}{8\pi^2\sqrt{2}} = 0.00935,
  \qquad \Delta\rho^{\text{QCD}} = 0.00834,$$

$$\frac{c^2}{s^2}\Delta\rho = 0.0311, \qquad
  \frac{c^2}{s^2}\Delta\rho^{\text{QCD}} = 0.0277, \qquad
  \Delta r_{\text{rem}} = +0.0064,$$

For the numerical decomposition, $c^2/s^2$ uses the MS-bar angle from §2.1,
while $s^2$ in the master relation remains the on-shell quantity. The
remainder is defined against the QCD-corrected product,
$\Delta r_{\text{rem}} = \Delta r - \Delta\alpha +
(c^2/s^2)\Delta\rho^{\text{QCD}}$ (`computations/sm_radiative_corrections.py`
§4). The identity then closes on the FOPS value:
$\Delta r = 0.05904 - 0.0277 + 0.0064 = 0.0377$, vs 0.0379 from the measured
$m_W$—the 0.0002 spread is the 3 MeV gap between the measured and FOPS
$m_W$ values, well inside the ±11 MeV measurement error (§5.2). And
$\Delta r - \Delta\alpha = -0.021$: the electroweak corrections *beyond* the
running of $\alpha$ are a measured effect at the 20+$\sigma$ level (26$\sigma$
in Sirlin & Ferroglia's own analysis, §III.I)—the loop corrections are not a
fudge factor, they are the physics. The remainder $+0.0064$ is dominated by
the bosonic (W, Z, H) loops, whose existence is separately established at
$14\sigma$ via $\Delta r_{\text{eff}}$ (Sirlin & Ferroglia 2013, §III.9).

### 5.2 The W-mass prediction

Using the compact formula of Ferroglia, Ossola, Passera & Sirlin
(PRD 65, 113002 (2002); complete one-loop + two-loop $(m_t^2/m_W^2)^n$
enhancements) with modern inputs ($m_t = 172.69$, $m_H = 125.25$,
$\Delta\alpha_{\text{had}} = 0.02761$, $\alpha_s = 0.118$):

$$\boxed{m_W = 80.363\ \text{GeV}
  \quad\text{(FOPS)},\qquad
  m_W = 80.354 \pm 0.006\ \text{GeV}
  \quad\text{(PDG global fit)},
  \qquad m_W^{\text{exp}} = 80.360 \pm 0.011\ \text{GeV}.}$$

The 9 MeV spread between the 2002-era formula and the current full two-loop
fit is the known higher-order scheme spread; both close on the measurement at
the 0.01% level. This is the same machinery that predicted the top quark mass
($m_t = 177 \pm 11$ GeV, EWWG 1994, before discovery) from the $m_t^2$
sensitivity of $\Delta r$.

### 5.3 The φ-tree W/Z ratio after radiative corrections

The Cassi tree-level ratio $m_W/m_Z = \sqrt{1 - \varphi^{-3}} = 0.8740$
(→ $m_W = 79.70$ GeV) receives its leading radiative correction from the
$\rho$ parameter: $m_W/m_Z = c\,\sqrt{1 + \Delta\rho}$, giving

$$\frac{m_W}{m_Z} = 0.8781, \qquad m_W = 80.07\ \text{GeV},$$

vs measured $m_W/m_Z = 0.8813$. The radiative corrections halve the gap
(−0.82% → −0.36%) but do **not** close it: the residual −0.36% is the
Weinberg-angle offset $\varphi^{-3}$ vs 0.2312 (§3.3) propagated through the
master relation. FCC-ee would still see the deviation at $>100\sigma$; the
expectation value is 80.07 GeV.

---

## 6. The Higgs Sector: λ Running and Vacuum Stability

The Higgs quartic at the Z scale is fixed by the measured mass:

$$\lambda(m_Z) = \frac{m_H^2}{2v^2} = 0.1294, \qquad v = \frac{1}{(\sqrt{2}
  G_F)^{1/2}} = 246.22\ \text{GeV}.$$

Its one-loop β-function (with the top Yukawa from the running top mass,
$y_t(m_Z) = 0.939$) drives it to

$$\lambda(10^{10}\ \text{GeV}) = 0.0008, \qquad
  \lambda(M_{\text{Pl}}) = -0.0116
  \quad\text{(1-loop, running } y_t \text{)},$$

$$\lambda(M_{\text{Pl}}) = -0.0729
  \quad\text{(1-loop, pole } y_t \text{)}.$$

A separate NNLO Standard Model calculation reports
$\lambda(M_{\text{Pl}})=-0.011$ (Degrassi et al. 2012,
arXiv:1205.6497). The local one-loop result is input-sensitive, as shown by
the running- versus pole-mass top Yukawa choices. These calculations give a
metastable Standard Model vacuum: the Higgs potential turns over at high
field values, while the decay rate remains negligible (lifetime $\gg$ the age
of the universe). The NNLO value is an external reference, and the
$\varphi$-anchored stability interpretation remains a conditional comparison.

The quartic formula $\lambda_\varphi = (\varphi^{-2}/2)(g^2/8)$ gives
$\lambda_\varphi = 0.0101$ with $g = g_2(m_Z)$, i.e. $m_H = v\sqrt{2\lambda_\varphi}
= 35$ GeV—not 125 GeV. The Higgs mass is an input to the radiative-correction
program, not yet an output of the φ-framework; the quartic
$\lambda(m_Z) = 0.1294$ follows from the measured $m_H$, and its radiative
corrections (running, metastability) are standard physics.

### 6.2 The φ-anchored mass formulas: candidates and consistency tests

Within the conditional two-fluid picture, the Higgs is modeled as a mode of
the broken condensate: the isospinor's norm and Yang/Yin imbalance modes of
the $\varphi$-attractor potential. Quarks and leptons can be treated as
additional modes only after a particle-sector extension supplies the
relevant field content. The formulas below are candidate mode frequencies of
the φ-point potential, tested against $m_H = 125.25$ GeV
(`computations/sm_radiative_corrections.py` §5.5). The canonical numerical
$\lambda=0.1$ remains the asserted solver convention. Rows that use
$\lambda_{\text{WX}}$ insert the Hypothesized linkage
$\lambda_{\text{WX}}=1/(2w)=0.1$ at $w=5$ as a conditional consistency-test
input; their masses and residuals are consequences of that conditional
construction.

| Formula | $m_H$ | vs 125.25 | Verdict |
|---|---|---|---|
| $\lambda_\varphi = (\varphi^{-2}/2)(g_2^2/8)$ | 35.1 GeV | −72% | fails ($\times 3.6$) |
| $m_H^2\varphi/(4v_0^2) = \lambda_{\text{WX}} = 1/(2w)$, $w = 5$ | 122.4 GeV | −2.3% | Conditional consistency test—built from the Hypothesized linkage $\lambda_{\text{WX}}=1/(2w)$ at $w=5$; residual in the 2–5% de-resonance band, mechanism open |
| $\lambda(M_{\text{Pl}}) = 0$ (stability line) | 129.0 (1-loop) / 129.2 GeV (NNLO reference, $m_t=172.69$) | +3.0% / +3.2% | Stability-boundary outputs; both lie above the measured mass and are input/order sensitive |
| two-fluid eigenmodes ($g = \varphi^{-3}$, $\lambda = \lambda_{\text{WX}}$) | 198.1 / 169.2 GeV | +58.2% / +35.1% | Conditional consistency test—both modes remain far above 125.25 GeV; normalization convention remains open |
| $m_H = v\sqrt{2(2\lambda_{\text{WX}}/\varphi)(1+\varphi^{-3}/w)}$, $w = 5$ | 125.28 GeV | +0.02% | Conditional consistency test—built from the Hypothesized linkage $\lambda_{\text{WX}}=1/(2w)$ at $w=5$, with the Yang-fraction-$w$ correction; mechanism open |
| $m_H = m_t\,\varphi^{-2/3}$ (top chain) | 125.30 GeV | +0.04% | mechanism target—2/3-rung separation has no Cassi origin yet |
| $m_H = \sqrt{2}\,y_t(m_Z)\,v\,\varphi^{-2}$ | 124.90 GeV | −0.28% | Hypothesized—top-loop pooling, $\lambda(m_Z) = y_t^2(m_Z)\varphi^{-4}$ |
| $m_Z\,\varphi^{2/3}$, $v\,\varphi^{-7/5}$ | 125.7 / 125.5 GeV | +0.34% / +0.22% | rejected as fits—no mechanism produces these fractional rungs (the pool-cell quantization covers half-rungs only, §6.3; the $m_e$ half-step 26.5 fit-rejection precedent, `foundations/deriving-remaining-gaps.md` §2.2) |

**Collision pooling.** The scan tests whether simple pooling of the
two-fluid eigenmodes can reproduce the measured mass
(`computations/sm_radiative_corrections.py` §5.6). The harmonic, geometric,
arithmetic, and energy-weighted combinations are 182.5, 183.1, 183.6, and
184.8 GeV, respectively, or +45.7%, +46.2%, +46.6%, and +47.5% above
125.25 GeV. These outputs remain conditional mode tests; a pooled-zone Higgs
mode requires additional dynamics. A separate numerical relation is
$\lambda(m_Z)=y_t^2(m_Z)\,\varphi^{-4}$ (−0.55% in λ), whose mechanism and
status remain open.

**The top chain.** The same production path anchors the top mass itself:
$y_t(\text{pole}) = 1 - \varphi^{-10} = 2g - g^2$ with $g = 1-\varphi^{-5}$
the derived Wu-Xing gap (`cassi-physics.md`), i.e.

$$\boxed{m_t = \frac{v}{\sqrt{2}}\,(1 - \varphi^{-10}) = 172.688\ \text{GeV}
  \quad\text{vs}\quad 172.69(30)}$$

—the sharpest coincidence in the framework (−0.001%). Its structure,
$1-(1-g)^2$ (two-step gap survival), is the first candidate mechanism for the
$m_t/m_H = \varphi^{2/3}$ separation that carries the chain from the top to
the Higgs.

**Look-elsewhere discipline.** Three independent candidates land within
0.05% ($m_t$ chain 0.001%, conditional Wu-Xing consistency test+$\varphi^{-3}/5$ 0.02%,
$m_t\varphi^{-2/3}$ 0.04%). Per the repo standard none is a derivation until
a mechanism produces its structure; the entries above are ranked mechanism
targets, and the $m_t$ chain is the priority: a two-step gap (Wu Xing)
producing $y_t = 2g - g^2$ would promote the top mass and the Higgs mass
together from coincidence to prediction.

### 6.3 The 2g−g² mechanism and the Yukawa ladder

The top-chain coincidence of §6.2 has a framework-native reading. The canonical
Yang/Yin variables in this real two-fluid sector are real density/field
components. A particle-sector extension may assign them to chiral projectors
$\hat P_{Y/I} = (1\pm\gamma^5)/2$; that assignment is explicitly
**Hypothesized** and requires additional complex/spinor structure beyond the
real two-fluid sector (`foundations/unified-lagrangian.md`). Under that
Hypothesized extension, the Wu-Xing gap
$g = 1-\varphi^{-5} = 0.90983$ is the per-cycle conversion fraction. A Dirac
Yukawa couples both chiral components through the condensate; the unconverted
residue is $(1-g) = \varphi^{-5}$ per component, so the coupled fraction is

$$\boxed{y_t = 1 - (1-g)^2 = 2g - g^2 = 1 - \varphi^{-10} = 0.991869
  \quad\text{vs}\quad y_t(\text{pole}) = 0.991881}$$

—the two-component (chiral-pair) survival mechanism. The top is the only
fermion in the maximal-coupling regime; the other Yukawas attenuate down the
cascade (`computations/sm_radiative_corrections.py` §5.7). In the
top-anchored frame (pole top; MS-bar quark masses at $m_Z$), the ladder is

| $f$ | $\Delta n = \log_\varphi(y_t/y_f)$ | nearest half-rung | residual |
|---|---|---|---|
| b | 8.52 | 8.5 | +1.0% |
| τ | 9.51 | 9.5 | +0.5% |
| μ | 15.38 | 15.5 | −5.8% |
| e | 26.46 | 26.5 | −2.1% |

(c, s, d, u sit at 11.7, 16.7, 22.9, 24.4—none near a half-rung, though
their MS-bar masses carry 10–20% uncertainties.)

The b half-rung is new (the framework's lepton table did not include
quarks), and the electron half-step sharpens in the top-anchored frame; but
the family does not close—μ resists at −5.8%, and the result is
convention-sensitive: the MS-bar top anchor shifts b/τ to ≈ −4.5%, and the
pole bottom mass kills the b half-rung outright.

The half-rung positions are the wave-mechanical content of the pool-cell
quantization (`foundations/rung-offset-mechanism.md` §4.1,
`computations/pooled_zone_modes.py`): the pool is the constructive-overlap
cell of the rotating wake pair (`foundations/wake-geometry.md` §2), the
terminal cell $[n, n+1]$ closes with nodes at the voids, and the fundamental
mode $\sin(\pi(u-n))$ has its antinode at the midpoint—the sector-edge state
sits at the half-rung by boundary conditions, not by fit. What the
quantization does not supply: the absolute placement of each cell (the
empirical ladder) and the frame choice. The ladder remains a
mechanism-flavored hypothesis, not a prediction: the identification of the
catalog states with the fundamental modes is Hypothesized, and the electron's
$n_e = 26.5$ is still solved from the observed mass
(`foundations/deriving-remaining-gaps.md` §2.2).

The t/H 2/3-rung re-expresses in the same phase language: the wake phases of
the two cells are $\psi_t = -0.315$ and $\psi_H = +1.31$ rad (from
$\delta n(\psi) = A_0 - \psi/\omega_0$), so $\Delta\psi = 1.63$ rad $=
\omega_0/3$ and $n_H - n_t = 1 - \Delta\psi/\omega_0 = 1 - \tfrac13 =
\tfrac23$. The separation is one full cell minus exactly one third of a
phase-rung. The channel-split reading
(`foundations/rung-offset-mechanism.md` §4.4): the pool at the EW scale
splits into $K = 3$ coherence channels, and the adjacent cells advance one
channel of phase ($\omega_0/3$); the third channel is empty (frac 0.458, no
EW state). The coherent three-bubble construction fails the probe (T8-F: the
third bubble's composition shifts the t-cell crossing by +0.17 rungs, so the
catalog phases produce (+0.29, −0.16) rather than (+0.124, −0.209))—the pair
reads as independent cells, and the origin of the third is an
emission-phase structure, not a crossing-response structure. It is the open
structure of the Higgs chain.

The mechanism reduces the Higgs chain to one open structure:

$$\boxed{m_H = \frac{v}{\sqrt{2}}\,(2g-g^2)\,\varphi^{-2/3} = 125.30\ \text{GeV}
  \qquad (+0.04\%)}$$

---

## 7. Summary: What the Radiative Corrections Close, and What They Do Not

| Observable | Derivation | Value | Measured | Status |
|-----------|-----------|-------|----------|--------|
| $\bar\alpha^{-1}(m_Z)$ | $\alpha(0) + \Delta\alpha$ | 128.95 | 128.9 | match, 0.05% |
| $m_W$ | $\Delta r$ master relation (FOPS) | 80.363 | 80.360(11) | match, 0.004% |
| $\sin^2\theta_{\text{eff}}^{\text{lept}}$ | FOPS | 0.23149 | 0.23153(16) | match, 0.02% |
| $\alpha_s(m_Z)$ from φ-boundary | 1-/2-loop QCD + thresholds | 0.058 / 0.061 | 0.1180 | low by $2.0\times$ ($\Delta b = 1.70$) |
| $\alpha_2^{-1}(m_Z)$ from φ-boundary | 1-loop + thresholds | 36.9 | 29.6 | high by 25% |
| $\alpha_1^{-1}(m_Z)$ from φ-boundary | 1-loop + thresholds | 74.3 | 59.0 | high by 26% |
| $\alpha_{\text{em}}^{-1}(m_Z)$ from φ-boundary | §3.2 | 161 | 128.9 | high by 25% |
| $\sin^2\theta_W = \varphi^{-3}$ at $m_Z$ |—| 0.23607 | 0.23122 | high by 2.1% (at $\mu_* = 233$ GeV, the running value matches) |
| $m_W/m_Z = \sqrt{1-\varphi^{-3}}$, +$\rho$ | §5.3 | 0.8781 | 0.8813 | low by 0.36% |
| $m_H$ from $\lambda_\varphi = (\varphi^{-2}/2)(g^2/8)$ | §6.2 | 35 GeV | 125.25 | conditional comparison; $m_H$ is an input; anchors at −2.3% and +3.0–3.2% remain open |
| $\lambda(M_{\text{Pl}})$ | 1-loop running $y_t$ / pole $y_t$; external NNLO | −0.0116 / −0.0729; −0.011 |—| metastable and input-sensitive |

The radiative corrections close every relation that does not depend on the
φ-boundary and quantify each discrepancy that does. The status of the
φ-anchored predictions:

- **$\sin^2\theta_W$:** the running direction is upward; $\varphi^{-3}$ is
  realized at $\mu_* \approx 233$ GeV, and at $m_Z$ it sits 2.1% high.
- **$m_W/m_Z$:** the −0.82% tree gap becomes −0.36% after the $\rho$
  correction; FCC-ee tests the value 80.07 GeV.
- **$\alpha_s(m_Z)$:** $2.0\times$ low—the documented beyond-SM
  $\Delta b = 1.70$ hypothesis (vector-like quark doublet at the cascade
  Fibonacci precursor) carries the weight.
- **$\alpha_2$, $\alpha_1$, $\alpha_{\text{em}}$:** each ~25% high in
  $\alpha^{-1}$ from the φ-boundary—documented residuals.
- **Higgs:** the $\lambda_\varphi$ formula does not produce 125 GeV; the SM
  λ-running (metastability at $M_{\text{Pl}}$) is derived and standard. The
  conditional Wu-Xing quartic consistency test gives 122.4 GeV, below the
  measured mass, while the stability-line outputs (§6.2) give 129.0 GeV at
  one loop and 129.2 GeV in the NNLO reference, both above it. These are
  separate conditional constructions and cannot be combined into one
  stability result; three sub-0.1% candidates (top-Yukawa chain 0.001%,
  conditional Wu-Xing+$\varphi^{-3}/5$ consistency test 0.02%,
  $m_t\varphi^{-2/3}$ 0.04%) await mechanisms.

These residuals define the next stage of the framework: either the φ-boundary
itself shifts (the unification reading $\alpha_1=\alpha_2=\alpha_3$ is not
realized in the SM at any scale), or the beyond-SM content that rescues
$\alpha_s$ also carries the weak sector.

---

## 8. References

- A. Sirlin and A. Ferroglia, *Radiative Corrections in Precision Electroweak
  Physics: a Historical Perspective*, Rev. Mod. Phys. 85, 263 (2013)
  [arXiv:1210.5296]—on-shell master relation, Δα decomposition, Δr,
  scheme values, the 26σ evidence, the 1994 top-mass prediction
- A. Ferroglia, G. Ossola, M. Passera, A. Sirlin, *Simple Formulae for
  sin²θ_eff^lept, M_W, Γ_l*, Phys. Rev. D 65, 113002 (2002)
  [arXiv:hep-ph/0203224]—compact M_W and sin²θ_eff formulae (Tables 1–2)
- G. Degrassi et al., *Higgs mass and vacuum stability in the Standard Model
  at NNLO*, JHEP 08 (2012) 098 [arXiv:1205.6497]—λ(M_Pl) = −0.011,
  metastability
- `computations/sm_radiative_corrections.py`—all numbers in this document
- `computations/mu_star_crossing_audit.py`—μ* crossing provenance, scheme
  band, and rung-placement audit (§3.4)
- `standard-model/sm-from-phi.md`—φ-breaking chain, GUT-scale coupling
- `standard-model/su2-gauge-extension.md`—SU(2) extension, mixing angle
- `standard-model/gut-embedding.md`—SU(5)/SO(10) embedding
- `parameter-inventory.md` §4.4—canonical α_s(M_Z) = 0.058, Δb = 1.70
- `audit.md` §1—prediction-vs-experiment status

# Quantum Free-Fall Correspondence Verification Report

## Status: Derived conditional—September 2026

## 1. Scope

The governing protocol is
`computations/quantum_free_fall_correspondence_prereg.md`.
The empirical target is
[arXiv:2502.14535](https://arxiv.org/abs/2502.14535), published at
[doi:10.1126/sciadv.aec8045](https://doi.org/10.1126/sciadv.aec8045).

The calculation covers the accelerated-frame gauge phase, unequal-mass
ballistic action, local-acceleration identifiability, differential held-arm
response, constant common-lapse reparameterization, attractor-line
normalization, and dimensional closure. The atomic Cassi state map, source
equation, scalar screening, finite-pulse apparatus model, and numerical
interpretation of $q$ lie outside the adopted result.

## 2. Gate results

| Gate | Result | Verified identity |
|---|---|---|
| QF1 | **PASS** | $f=-m_ggtz-m_g^2g^2t^3/(6m_i)$ cancels both accelerated-frame residuals |
| QF2 | **PASS** | $v_0=(m_g/m_i)gT$ closes the path; $S_K=m_g^2g^2T^3/(3m_i)$ and $S_V=-2S_K$ |
| QF3 | **PASS** | $\Delta\phi=-m_g^2g^2T^3/(3\hbar m_i)$, reducing to $-mg^2T^3/(3\hbar)$ |
| QF4 | **PASS** | $g_b=(m_g/m_i)g$ gives $\Delta\phi=-m_ig_b^2T^3/(3\hbar)$ |
| QF5 | **PASS** | $\mathcal R_{br}=|r_b/r_r|$ for a common source and nonzero held-arm calibration |
| QF6 | **PASS** | the coordinate-time factor $N^3$ cancels after $\mathcal T=NT$ |
| QF7 | **PASS** | $\varepsilon=0$ gives $s=\varphi^{-3}$; $q(\varphi)=\varphi^2/3$ and $\mathcal G_C=5\sqrt5/3$ |
| QF8 | **PASS** | every phase and constitutive ratio is dimensionless |

## 3. Verifier output

The repository verifier prints:

```text
QF1 first-derivative residual: 0
QF1 scalar residual: 0
QF1 gauge action: -g**2*m_g**2*t**3/(6*m_i) - g*m_g*t*z
QF2 initial endpoint: 0
QF2 final endpoint: 0
QF2 kinetic action: 0
QF2 potential action: 0
QF3 unequal-mass phase: 0
QF3 equal-mass phase: 0
QF3 unequal-mass phase: -T**3*g**2*m_g**2/(3*hbar*m_i)
QF3 equal-mass phase: -T**3*g**2*m/(3*hbar)
QF4 local-acceleration degeneracy: 0
QF5 squared differential response: 0
QF5 positive differential response: 0
QF6 coordinate-time lapse phase: 0
QF6 physical-time lapse cancellation: 0
QF7 attractor condition: 0
QF7 attractor signed fraction: 0
QF7 dilute q limit: 0
QF7 reference q: 0
QF7 reference q exact: sqrt(5)/6 + 1/2
QF7 reference q numeric: 0.872677996250
QF7 reference G_C exact: 5*sqrt(5)/3
QF7 reference G_C numeric: 3.72677996250
QF8 phase dimensionless: True
QF8 q dimensionless: True
QF8 signed fraction dimensionless: True
QF8 G_C dimensionless: True
VERDICT: PASS
ALL CHECKS PASSED
```

## 4. Independent recomputation

The preserved clean-room receipt at
`computations/quantum_free_fall_correspondence_cleanroom_receipt.md` derives
the gates without reading or executing the verifier:

1. substitution of
   $\psi_N=e^{if/\hbar}\psi_E(z+\tfrac12(m_g/m_i)gt^2,t)$ fixes
   $f_z=-m_ggt$ and the QF1 scalar phase;
2. direct integration over $0\le t\le2T$ gives the QF2 and QF3 action terms;
3. replacing the supplied field by the measured ballistic acceleration gives
   the QF4 degeneracy;
4. division by the held preparation's acceleration gives the QF5 response
   ratio;
5. transforming the launch and closing data with $d\tau=Ndt$ gives QF6;
6. the canonical definitions of $\rho$, $\pi$, and $\varepsilon$ give QF7;
7. mass-length-time accounting gives QF8.

The independent expressions agree exactly with the repository calculation.

## 5. Verdict

```text
QF1-QF8: PASS
VERDICT: ADOPT
```

The adopted result is the **Derived conditional external-potential,
ideal-QGI correspondence theorem** in
`foundations/quantum-free-fall-correspondence.md`. Its uniform gravitational
potential and ideal apparatus limit are explicit inputs.

The Cassi atomic state map, variable-coupling gravity completion,
source/screening solution, direct-charge matching, finite-pulse experimental
model, path-dependent common lapse, and Cassi-specific empirical discriminator
remain Hypothesized or open. The published QGI measurement supplies a standard
low-energy boundary and no direct evidence for $\varphi$ scaling, Cassi $q$,
the $\sigma$ regulator, or a composite graviton.

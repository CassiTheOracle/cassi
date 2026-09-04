# Quantum Free-Fall Correspondence Pre-Registration

## Status: Pre-registered—September 4, 2026

## 1. Question

Can the conditional Cassi centre-of-mass quantum sector reproduce the ideal
Quantum Galileo Interferometer (QGI) phase after a uniform external gravity
potential is supplied, while keeping the Qi-gravity constitutive ansatz and the
candidate common lapse outside the derived result?

The target experiment is the $^{87}\mathrm{Rb}$ spin-state interferometer in
[arXiv:2502.14535](https://arxiv.org/abs/2502.14535), published as
[doi:10.1126/sciadv.aec8045](https://doi.org/10.1126/sciadv.aec8045).
The ideal target uses a ballistic interval $0\le t\le2T$, the closing velocity
$v_0=(m_g/m_i)gT$, and a magnetically held reference arm. The measured
apparatus also contains finite pulses, magnetic curvature, Zeeman shifts,
wave-packet shape corrections, and interactions. Those measured corrections
remain inputs to the published apparatus model and are outside the algebraic
correspondence calculation below.

## 2. Frozen starting objects

The verifier must use only these declared objects:

1. the one-dimensional external-potential Hamiltonian
   $$
   H_N=-\frac{\hbar^2}{2m_i}\partial_z^2+m_g g z,
   $$
   with positive inertial mass $m_i$, gravitational response coefficient
   $m_g$, and uniform source field $g$;
2. the free-fall coordinate
   $$
   \zeta=z+\frac12\frac{m_g}{m_i}gt^2;
   $$
3. the ballistic classical path
   $$
   z_b(t)=v_0t-\frac12\frac{m_g}{m_i}gt^2,
   \qquad 0\le t\le2T;
   $$
4. a reference path held at $z_r=0$ by a separately calibrated linear
   magnetic potential;
5. Cassi's canonical field and constitutive quantities
   $$
   E_Y,E_I\ge0,\qquad
   \rho=E_Y+E_I,\qquad
   \pi=E_Y-E_I,\qquad
   \varepsilon=E_Y-\varphi E_I,
   $$
   $$
   s=\frac{\pi}{\rho},\qquad
   q=\frac{\rho^2}{\rho^2+\varphi^{-2}\rho_\star^2+\varepsilon^2},\qquad
   \mathcal G_C=s\left[1+(\varphi^6-1)q\right];
   $$
6. a constant common-lapse reparameterization $d\tau=N\,dt$, used only to
   test clock-coordinate invariance;
7. no atom-to-$(E_Y,E_I)$ state map and no identification of
   $\mathcal G_C$ with $m_g/m_i$.

The calculation introduces no fit parameter and does not use the measured
phase residual to infer $q$.

## 3. Frozen proof obligations

### QF1—Accelerated-frame cancellation

For

$$
\psi_N(z,t)=e^{if(z,t)/\hbar}\psi_E(\zeta,t),
$$

the verifier must derive

$$
f(z,t)=-m_g gtz-\frac{m_g^2}{6m_i}g^2t^3
$$

and show that substitution into $H_N$ leaves the free Schrödinger equation for
$\psi_E$. Both the first-derivative coefficient and scalar residual must vanish.

### QF2—Closed ballistic path

The closing condition must give $z_b(0)=z_b(2T)=0$. The kinetic and potential
actions must reduce separately to

$$
S_K=\frac{m_g^2}{3m_i}g^2T^3,
\qquad
S_V=-\frac{2m_g^2}{3m_i}g^2T^3.
$$

### QF3—General ideal QGI phase

The total action and phase must be

$$
S_b-S_r=-\frac{m_g^2}{3m_i}g^2T^3,
\qquad
\Delta\phi=-\frac{m_g^2}{3\hbar m_i}g^2T^3.
$$

Setting $m_g=m_i=m$ must give

$$
\Delta\phi=-\frac{mg^2T^3}{3\hbar}.
$$

### QF4—Locally calibrated acceleration degeneracy

With the ballistic acceleration magnitude

$$
g_b=\frac{m_g}{m_i}g,
$$

the phase must reduce to

$$
\Delta\phi=-\frac{m_i g_b^2T^3}{3\hbar}.
$$

This identity establishes that the ideal phase expressed in the same arm's
locally calibrated acceleration cannot by itself separate $m_g/m_i$ from the
source field.

### QF5—Differential held-arm observable

If the ballistic and held preparations have response ratios $r_b$ and $r_r$
relative to the same source field, while the holding acceleration is
$a_h=r_rg$, the ideal dimensionless observable

$$
\mathcal R_{br}
:=\sqrt{\frac{-3\hbar\Delta\phi_b}{m_iT^3a_h^2}}
$$

must reduce to

$$
\mathcal R_{br}=\left|\frac{r_b}{r_r}\right|.
$$

This is a conditional effective-response ratio. A Cassi interpretation requires
an independently derived map from each preparation to the response ratio.

### QF6—Common-lapse coordinate invariance

For constant $N>0$, the coordinate-time action

$$
S_N=\int dt\left[
\frac{m_i}{2N}\dot z^2-Nm_ggz
\right]
$$

must produce

$$
\Delta\phi_N=-\frac{N^3m_g^2}{3\hbar m_i}g^2T^3.
$$

Writing the physical half-duration as $\mathcal T=NT$ must remove $N$:

$$
\Delta\phi_N=-\frac{m_g^2}{3\hbar m_i}g^2\mathcal T^3.
$$

A common constant lapse is therefore a clock-coordinate choice in this
experiment. A path-dependent $N_q$ requires the complete variational action and
an independent clock comparison.

### QF7—Attractor-line normalization

Starting from the canonical definitions in §2, the verifier must impose
$\varepsilon=0$ and derive

$$
E_Y=\varphi E_I,\qquad
s=\frac{\varphi-1}{\varphi+1}=\varphi^{-3}.
$$

With $\rho_\star=1$, it must then show

$$
q_{\mathrm{eq}}(\rho)=\frac{\rho^2}{\rho^2+\varphi^{-2}},
$$

so $q_{\mathrm{eq}}\to0$ only in the dilute limit. At the registered reference
point $\rho=\varphi$ it must show

$$
q_{\mathrm{eq}}=\frac{\varphi^2}{3}\approx0.872678,
\qquad
\mathcal G_C=\frac{5\sqrt5}{3}\approx3.72678.
$$

This gate distinguishes the composition attractor line from a selected density
point on that line.

### QF8—Dimensional closure

Using base dimensions $[m_i]=[m_g]=M$, $[g]=LT^{-2}$,
$[T]=T$, and $[\hbar]=ML^2T^{-1}$, the verifier must show that every displayed
QGI phase is dimensionless and that $\mathcal G_C$, $q$, and $s$ are
dimensionless.

## 4. Decision tree

- **PASS:** QF1–QF8 all vanish or evaluate exactly as declared.
- **FAIL:** any algebraic identity, endpoint, or dimensional gate fails.
- **ADOPT:** PASS plus an independent clean-room recomputation supports a
  Derived conditional QGI correspondence theorem. The theorem remains
  conditional on the supplied external potential and ideal pulse limit.
- **REJECT:** FAIL, or disagreement with the independent recomputation, rejects
  the claimed correspondence until the discrepancy is resolved.

The physical identification of $m_g/m_i$ with a Cassi field functional, the
source equation, scalar screening, finite-pulse apparatus model, and universal
common lapse remain separate hypotheses under either verdict.

## 5. Frozen output contract

The verifier must print:

1. one line for every QF gate;
2. the exact unequal-mass and equal-mass phases;
3. the reference $q$ and $\mathcal G_C$ values;
4. `VERDICT: PASS` only after every gate succeeds;
5. `ALL CHECKS PASSED` as its final line.

The report must preserve the verifier stdout, state the decision-tree outcome,
and record the independent recomputation separately.

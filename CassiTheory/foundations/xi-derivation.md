# Derivation of $\xi = \varphi^6$

## Status: Derived conditional on the quadratic-coupling input (imbalance inverse-square: $\xi = (\pi/\rho)^{-2} = \varphi^6$, $\pi/\rho = \varphi^{-3}$ from the attractor) / Calibrated empirical pin (Milky Way anchor—ledger row 498)—August 2026

## Abstract

The Qi-gravity force law in the Cassi framework is $\mathbf{F} = \pi\,(1 + (\varphi^{6}-1)q)\,\nabla\Phi$, with $q$ the dimensionless scalar Qi coherence diagnostic, $\Phi$ the gravitational potential, and $\xi$ the Qi-gravity coupling; equivalently $G_{\text{eff}} = G\,(\pi/\rho)(1 + (\varphi^{6}-1)q)$ (`foundations/unified-lagrangian.md` §3.2). This document derives the coupling conditionally as the inverse-square of the fixed-point imbalance under the stated quadratic-coupling input: $\xi = \varphi^6 = (\pi/\rho)^{-2}$, where $\pi/\rho = (\varphi-1)/(\varphi+1) = \varphi^{-3}$ is the fractional energy imbalance $(E_Y - E_I)/(E_Y + E_I)$ at the $\varphi$-attractor fixed point. The exponent $6 = 3 \times 2$ splits into the attractor-derived imbalance exponent $3$ (from $\pi/\rho = \varphi^{-3}$) and the explicitly assumed quadratic response power $2$. The numerical agreement with the rotation-curve fit is a calibration check, not an independent derivation of the coupling law.

## 1. The Problem

The Qi-gravity force law in the Cassi framework is

$$
\mathbf{F} = \pi\,(1 + (\varphi^{6}-1)q)\,\nabla\Phi
$$

where $q$ is the dimensionless scalar Qi coherence diagnostic, $\Phi$ is the gravitational potential, and $\xi$ is the Qi-gravity coupling constant. In the unified action the same coupling enters the effective Newton constant (`foundations/unified-lagrangian.md` §3.2):

$$
G_{\text{eff}} = G \cdot \frac{\pi}{\rho} \cdot (1 + (\varphi^{6}-1)q)
$$

Empirical calibration to the Milky Way rotation curve gives $\xi \approx 18$. The conditional derivation below obtains the exponent 6 from the two-fluid attractor plus one coupling assumption; it neither imports the spatial dimension nor asserts a per-degree-of-freedom factor.

## 2. The Derivation

### 2.1 The fixed-point imbalance

The canonical two-fluid state uses two real density fields, $E_Y$ and $E_I$. Define

$$
\rho = E_Y + E_I, \qquad \pi = E_Y - E_I
$$

where $\rho$ is total energy density and $\pi$ is the Yang excess. For notation that exposes an amplitude-like representative, the exact positive-root lift is $\Psi^{(+)} = (\sqrt{E_Y},\sqrt{E_I})$, so $(\Psi_0^{(+)})^2 = E_Y$ and $(\Psi_1^{(+)})^2 = E_I$. This lift introduces no phase variable; an $SO(2)$ rotation or compact phase assigned to it is an optional **Hypothesized** extension. The $\varphi$-attractor potential is

$$
V = \frac{\lambda}{2}(E_Y - \varphi E_I)^2 = \frac{\lambda}{2}\big((\Psi_0^{(+)})^2 - \varphi(\Psi_1^{(+)})^2\big)^2
$$

and drives the system to the fixed point $E_Y = \varphi E_I$ (`foundations/cassi-theory-reference.md` §2.3). At the fixed point:

$$
\boxed{\frac{\pi}{\rho} = \frac{\varphi - 1}{\varphi + 1} = \varphi^{-3} = 0.236067978}
$$

The quantity $\pi/\rho = (E_Y - E_I)/(E_Y + E_I)$ is the fractional energy imbalance—not the Yang fraction, which is $\varphi^{-1}$ at the fixed point (the "Yang fraction" label is Mapped—ledger row 500). The identity is pure attractor algebra: $\varphi^{-1} = \varphi - 1$ and $\varphi + 1 = \varphi^2$ from $\varphi^2 = \varphi + 1$, so $(\varphi-1)/(\varphi+1) = \varphi^{-1}/\varphi^2 = \varphi^{-3}$. The exponent 3 is a consequence of the two-fluid dynamics, not an input.

### 2.2 The inverse-square law

The quadratic-coupling input is stated on the exact positive-root lift: the source is bilinear in its real components ($T_{\mu\nu} \propto \partial\Psi^{(+)}\,\partial\Psi^{(+)}$), the coherent factor is $q \propto \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$, and the mixing term $\mathcal{L}_{qG} = (\xi q/16\pi G)R\sqrt{-g}$ multiplies those bilinears (`foundations/unified-lagrangian.md` §3.1–3.2, §5.1). The amplification of a quadratic (degree-2) coupling under a fractional imbalance $\alpha = \pi/\rho$ scales as the inverse square of the imbalance—each of the two real lift factors in a bilinear vertex carries one inverse power of the participating fraction. With $\alpha = \varphi^{-3}$:

$$
\boxed{\xi = \varphi^6 = \left(\frac{\pi}{\rho}\right)^{-2} = (\varphi^{-3})^{-2}}
$$

Numerically $\xi = \varphi^6 = 17.94427191$ and $\alpha_0^{-2} = (0.236067978)^{-2} = 17.94427191$—the identity is exact to machine precision (`computations/xi_imbalance_verification.py`). The Fibonacci decomposition $\varphi^6 = \varphi^5 + \varphi^4$ remains an arithmetic identity of the same number; it carries no independent structural content in this derivation.

**Inputs.** The derivation rests on two postulates:

1. **Attractor dynamics (framework postulate).** The $\varphi$-attractor potential $V = \frac{\lambda}{2}(E_Y - \varphi E_I)^2$ drives $E_Y/E_I \to \varphi$, fixing $\pi/\rho = \varphi^{-3}$. In the exact positive-root lift this is $(\Psi_0^{(+)})^2/(\Psi_1^{(+)})^2 \to \varphi$; $\pi/\rho = \varphi^{-3}$ is derived from the attractor.
2. **Quadratic coupling (input of this derivation).** Gravity couples through bilinear (degree-2) forms of the exact positive-root lift, and the full-coherence amplification of a bilinear coupling under a fractional imbalance $\alpha$ scales as $\alpha^{-2}$. The exponent $-2$ is the degree of the quadratic form. An $SO(2)$ or compact-phase representation is not required by this input and remains an optional **Hypothesized** extension.

The tier is Derived conditional on input 2: the imbalance exponent 3 follows from the attractor; the inverse-square law is the stated postulate.

### 2.3 Fixed-composition branch endpoints

With $\xi = (\pi/\rho)^{-2}$, the $\varphi$-attractor composition line has
$\pi/\rho=\varphi^{-3}$. Its dense endpoint is

$$
G_{\text{eff}}(\varepsilon=0,\rho\to\infty)
= G \cdot \varphi^{-3} \cdot \varphi^6
= G \cdot \varphi^3
= 4.236067978\,G
$$

On this fixed-composition line, the coupling runs from the reciprocal pair
$\varphi^{-3}G$ (gate open, $q\to0$ as $\rho\to0$) to
$\varphi^3G$ (gate closed, $q\to1$ as $\rho\to\infty$), and their ratio is
$\varphi^6=\xi$. These are branch limits, not global state-space extrema:
$q=q(\rho,s)$ and the composition prefactor $s=\pi/\rho$ both vary. The
$\alpha$-free bracket factor is separately bounded by $\varphi^6$ for
$0\le q\le1$. For the unrestricted-composition high-density expression
$q_\infty(s)=\left[1+\left((\varphi^2s-\varphi^{-1})/2\right)^2\right]^{-1}$,
$G_{\text{eff}}/G\to s[1+(\varphi^6-1)q_\infty(s)]$ has an interior peak
$\approx9.601$ at $s\approx0.8569$ on $0\le s\le1$; if $s>1$ is formally
admitted, it is unbounded, so $\varphi^3$ is not a universal $G_{\text{eff}}$
or velocity ceiling. The $q$-coefficient remains the saturation-anchored
chord $(\varphi^6-1)$: the boost is exactly $1$ at $q=0$ on the dilute
$\varphi$-line and exactly $\varphi^6$ at $q\to1$, not a Taylor linearization
of the exact ladder $1/(1-(1-\varphi^{-6})q)$.

## 3. Consistency Checks

Every computable claim below was verified from the repo root with `python computations/xi_imbalance_verification.py`; all identities hold to machine precision.

| Check | Expression | Value | Status |
|-------|-----------|-------|--------|
| Fixed-point imbalance | $(\varphi-1)/(\varphi+1) = \varphi^{-3}$ | $0.236067978$ | identity (attractor algebra) |
| Coupling | $(\pi/\rho)^{-2} = \varphi^6$ | $17.94427191$ | identity |
| Fixed-composition dense-branch benchmark | $G_{\text{eff}}/G = \varphi^{-3}\cdot\varphi^6 = \varphi^3$ | $4.236067978$ | compares with the dwarf-spheroidal M/L benchmark $\varphi^3=4.2361$ (`audit.md` §3) |
| Empirical pin | $\xi$ vs $18$ | residual $0.31\%$ | Calibrated anchor (ledger row 498); a consistency check of the calibration |
| Weinberg angle | $\sin^2\theta_W = 1/(1+2\varphi) = \varphi^{-3}$ | $0.236067978$ | identity: $1+2\varphi = \varphi^3$; the angle is the same fixed-point imbalance (`foundations/cassi-theory-reference.md` §4.4; exact at $\mu_* = 233$ GeV—Calibrated, ledger row 490) |
| GUT coupling | $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi)$ | $1/53.23$ | the imbalance over $4\pi$ |
| Emotions gate ladder | $b_i = \varphi^{-(2+i)} = \varphi^{-2}\cdot\varphi^{-i}$ | base $\varphi^{-2} = 0.381966011$ | human-gate openness hierarchy on the same $\varphi^{-2}$ base (`consciousness/emotions-as-gate-configurations.md` §2.2) |
| MW halo boost | $1 + (\varphi^6-1)\cdot 0.67$ | $12.3527$ | rotation-curve boost at $r = 7$ kpc, $q \approx 0.67$ |

The Weinberg-angle identity: $\varphi^3 = \varphi\cdot\varphi^2 = \varphi(\varphi+1) = \varphi^2 + \varphi = 2\varphi + 1$, so $1/(1+2\varphi) = 1/\varphi^3 = \varphi^{-3}$. The same imbalance $\varphi^{-3}$ therefore appears at three sites—the fixed-composition gravity open-gate branch, the weak mixing angle, and the GUT coupling—while its inverse square $\varphi^6$ is the separate $\alpha$-free bracket bound; no universal $G_{\text{eff}}$ ceiling follows from $\varphi^3$.

## 4. Origin Stories Reconciled

Four readings of the exponent 6 circulate in the repo. The conditional derivation of §2 supplies the single dynamical origin under its stated quadratic-coupling input; the others are secondary or descriptive:

- **2 × 3 degrees of freedom** (2 density components × 3 spatial dimensions)—the reading in `foundations/unified-lagrangian.md` §3.3 and `foundations/cassi-theory-reference.md` §4.3/§10.2. Retained in §6 as a clearly labeled secondary geometric reading. It does not derive the exponent: $d = 3$ rests on the Frenet-Serret hypothesis (`foundations/why-three-dimensions.md`; Hypothesized—registry G5) and the φ-per-DOF factor is asserted rather than shown by the dynamics or geometry.
- **Dimensional reduction** of the 4D two-fluid action to a 3D effective potential (`foundations/phi-rg-formalism.md` §7)—a restatement of the coupling's two fixed-point values, not an origin of the exponent.
- **Cascade activation at step 6** (`cosmology/sigma8-computational-plan.md` §2.1, `foundations/wa-pentagon-gate.md` §5)—a shorthand label of the exponent's rung position ($\xi = \varphi^6$ sits at ladder step 6), used by consumer documents, not a derivation.
- **Six-dimensional phase space** (`foundations/phi_attractor_synthesis.md` §2.2)—the 2 × 3 reading restated in phase-space language; same status.

The exponent is $6 = 3 \times 2$: the attractor-derived imbalance exponent 3 (this document, §2.1) times the quadratic degree 2 (the input of §2.2), so the result is derived conditionally on that input.

## 5. Prediction

$\xi = \varphi^6 = (\pi/\rho)^{-2}$ is derived conditionally from the attractor and the quadratic-coupling input. The empirical pin ($\xi \approx 18$ from the Milky Way rotation curve) is Calibrated—it anchors the value to the data it was calibrated on (Fit-Status Ledger row 498); any "confirmation" of $\xi$ on the rotation curve is a consistency check of that calibration, not an independent test.

The following are conditional phenomenological targets for realizations beyond the
local coupling derivation:

- **Milky Way rotation curves:** a full field/halo realization may target the observed flat curve. The pure $G$-rescaling Path 8 test is negative: its best curve is U-shaped, with $\chi^2=4522$ versus $4047$ for Newtonian gravity, and it overboosts the outer curve ($v(30\,\mathrm{kpc})=296\,\mathrm{km\,s^{-1}}$ versus observed $\sim190$–$200\,\mathrm{km\,s^{-1}}$).
- **Dwarf-galaxy mass discrepancies:** a coherence-condensate realization may target the observed boosts. The pure $G$-rescaling ceiling is exceeded by Segue 1 ($16.6\times$), Segue 2 ($16.8\times$), and Draco ($6.2\times$), above $\varphi^3=4.2361$.
- **Solar-system bounds:** compatibility with planetary ephemerides remains a conditional target requiring a dedicated realization and bound.
- **Terminal attractor convergence:** structure-formation convergence remains a conditional target requiring an independently validated dynamical realization.

These tests provide no physical success claim for the pure $G$-rescaling
phenomenology. The coherence-condensate sector is a separate conditional
realization and requires its own calibration and tests.

## 6. Secondary Geometric Reading: 2 × 3 Degrees of Freedom

The 2 × 3 reading of the exponent—$\varphi^6 = \varphi^{2 \times 3}$ with two density components × three Frenet-Serret spatial directions ($\mathbf{T}$, $\mathbf{N}$, $\mathbf{B}$; `foundations/cassi-theory-reference.md` §10.2)—remains a geometric restatement of the same number. It is not the derivation: the spatial dimension rests on the Frenet-Serret hypothesis (`foundations/why-three-dimensions.md`; Hypothesized—registry G5), and the per-DOF factor of $\varphi$ is asserted. The imbalance inverse-square derivation of §2 is the origin of the exponent; the 2 × 3 form is retained because it organizes the coupling's alternative expressions (§8).

## 7. Dimensionless Parameter Status

With $\xi = \varphi^6$ derived conditionally on the quadratic field-coupling
input, the surrounding catalog carries individual epistemic labels:

| Constant | Value | Status |
|----------|-------|--------|
| $\varphi$ | $(1+\sqrt{5})/2 \approx 1.618$ | Mathematical constant (golden ratio) |
| $\alpha_0 = \pi/\rho$ | $\varphi^{-3} \approx 0.236$ | Derived (fixed-point imbalance, attractor) |
| $\xi = \varphi^6 = \alpha_0^{-2}$ | $\approx 17.944$ | **Derived conditional** (imbalance inverse-square; input: quadratic field coupling); empirical pin Calibrated (ledger row 498) |
| Wu Xing coefficients | $\varphi^{-1}, \varphi^{-2}, \ldots$ | Derived from $\varphi$ |
| $\sin^2\theta_W$ | $\varphi^{-3} \approx 0.236$ | Asserted coupling boundary; exact at $\mu_* = 233$ GeV (Calibrated anchor—ledger row 490) |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi) \approx 1/53$ | Asserted boundary assignment; running requires $\Delta b = 1.70$ (Mapped—ledger) |

The PDE conversion rate is fixed at $\lambda = 0.1$ by solver normalization/timescale convention. The relation $\lambda = 1/(2w)$ with $w=5$ is a Hypothesized Wu Xing linkage requiring an independently defined cycle time and dynamical closure. The three dimensionful constants ($c$, $\hbar$, $G$) remain external. See `foundations/dimensionful-constants-status.md` for the complete accounting.

## 8. Alternative Expressions

$\varphi^6$ admits several equivalent forms, each illuminating a different aspect:

| Form | Expression | Content |
|------|-----------|---------|
| Imbalance inverse-square | $(\pi/\rho)^{-2} = (\varphi^{-3})^{-2}$ | the derivation (§2) |
| Radical | $9 + 4\sqrt{5}$ | rational + irrational parts, both integers times powers of $\sqrt{5}$ |
| Linear in $\varphi$ | $8\varphi + 5$ | basis $\{1, \varphi\}$, the ring $\mathbb{Z}[\varphi]$ |
| Square | $(\varphi^3)^2 = (2\varphi + 1)^2$ | the imbalance's reciprocal, squared |
| Fibonacci | $\varphi^5 + \varphi^4$ | arithmetic identity of the defining recurrence |

---

## 9. Summary

$\xi = \varphi^6$ is the inverse-square of the fixed-point imbalance, derived conditionally on the quadratic-coupling input. The attractor fixes $\pi/\rho = (\varphi-1)/(\varphi+1) = \varphi^{-3}$; the quadratic-coupling input gives $\xi = (\pi/\rho)^{-2} = \varphi^6$. The dense fixed-composition branch endpoint $G_{\text{eff}}=\varphi^3G=4.236068\,G$ is a branch benchmark compared with the dwarf-spheroidal M/L benchmark, not a global state-space ceiling. The exponent 6 is no longer the product of an imported dimension and an asserted per-DOF factor: its factor 3 is derived from the two-fluid attractor dynamics, and its factor 2 is the stated quadratic-coupling input. The empirical pin on the Milky Way rotation curve is the Calibrated anchor (Fit-Status Ledger row 498); its 0.3% agreement with $\varphi^6$ is a consistency check of that calibration.

---

## References

- `foundations/cassi-first-principles.md`—two-fluid postulate, Qi-enhanced gravity
- `foundations/unified-lagrangian.md`—the complete action with $G_{\text{eff}} = G(\pi/\rho)(1+(\varphi^{6}-1)q)$
- `foundations/cassi-theory-reference.md`—attractor fixed point §2.3, constant table §12
- `foundations/phi-rg-formalism.md`—φ-RG restatement of the coupling (dimensional-reduction reading)
- `foundations/phi_attractor_synthesis.md`—attractor dynamics (phase-space reading)
- `foundations/wa-pentagon-gate.md`—$w_a$ from $\xi = \varphi^6$ (cascade-step-6 label)
- `cosmology/sigma8-computational-plan.md`—σ8 pipeline parameter table (cascade-step-6 label)
- `foundations/why-three-dimensions.md`—three dimensions from the spiral's Frenet-Serret frame (secondary reading)
- `foundations/dimensionful-constants-status.md`—external dimensionful constants, parameter accounting
- `cosmology/observational_constraints.md` §2.6—rotation-curve tests of $\xi = \varphi^6$
- `audit.md`—dwarf-spheroidal M/L benchmark $\varphi^3 = 4.2361$
- `consciousness/emotions-as-gate-configurations.md`—gate openness ladder $b_i = \varphi^{-(2+i)}$
- `gravity/quantum-gravity.md`—σ-regularized gravity, UV-finite propagator
- `computations/xi_imbalance_verification.py`—numerical verification of every identity in §2–§3

# Cassi First Principles

## Status: Canonical defined/selected PDE and Qi diagnostic; algebraic consequences Derived conditional on the stated attractor/gated equations; Asserted single-channel g(q) input—August 2026

## Abstract

There exists a universal constant of scale separation, $\varphi=(1+\sqrt{5})/2\approx1.618033989$, which governs the equilibrium ratio between two nonnegative density components conventionally labeled Yang and Yin. A **Hypothesized** phenomenological mapping may call Yang expansive/active and Yin contractive/receptive; the canonical PDE treats the components as neutral. This document states the postulate, records the canonical two-fluid PDE, defines its Qi coherence diagnostic on reference-normalized solver fields, and maps quantum mechanics, cosmology, general relativity, and the Standard Model onto the four pillars of the framework. The PDE, gate form, and normalization are model conventions; fixed-point and gate arithmetic are Derived conditional on the stated equations. Dimensionless entries are expressed as $\varphi$-powers with individual status labels; $c$, $\hbar$, and $G$ remain external.

---

## 0. The Postulate

There exists a universal constant of scale separation:

$$
\boxed{\varphi = \frac{1 + \sqrt{5}}{2} \approx 1.618033989}
$$

The framework expresses dimensionless coupling constants and mass ratios as $\varphi$-powers. The closed subset carries zero free inputs after its named structural conditions are supplied; asserted boundaries, calibrated anchors, and mapped exponents retain their ledger status. The dimensionful constants $c$, $\hbar$, and $G$ remain external.

---

## 1. The Two Fields and Their Local Structure

The canonical substrate consists of nonnegative reference-normalized density components at every spacetime point:

$$
E_Y\ge 0,\qquad E_I\ge 0,\qquad \rho=E_Y+E_I.
$$

In canonical solver units, $E_Y$, $E_I$, $\rho$, $\pi$, and $\varepsilon$ are dimensionless model quantities. An external reference density $\rho_*$ is required to map them to physical energy densities, for example $\rho_{\mathrm{phys}}=\rho_*\rho$ and $\varepsilon_{\mathrm{phys}}=\rho_*\varepsilon$; no $\rho_*$ scale is derived here.

They are conventionally labeled **Yang** and **Yin**. A **Hypothesized**
phenomenological mapping may call them expansive/symmetry-breaking and
contractive/symmetry-restoring; the canonical equations treat them as neutral
densities.

When component amplitudes are useful, introduce the exact positive-root
coordinate lift

$$
\Psi^{(+)}
= \begin{pmatrix}\Psi_0^{(+)}\\ \Psi_1^{(+)}\end{pmatrix}
= \begin{pmatrix}\sqrt{E_Y}\\ \sqrt{E_I}\end{pmatrix}
\in \mathbb{R}_{\ge 0}^{2}.
$$

The lift is an exact coordinate representation of the density state. Compact
phase dynamics and branch-sign interpretations require optional signed or
complex extensions and remain **Hypothesized**. For $\rho>0$, define the lift's
amplitude-plane phase diagnostic

$$
\theta_\Psi
= \operatorname{atan2}(\Psi_1^{(+)},\Psi_0^{(+)})
= \operatorname{atan2}(\sqrt{E_I},\sqrt{E_Y}).
$$

The density-plane angle is a distinct coordinate,

$$
\theta_d = \operatorname{atan2}(E_I,E_Y),
$$

and the Stokes double angle is

$$
\Theta_S=\operatorname{atan2}
(2\Psi_0^{(+)}\Psi_1^{(+)},E_Y-E_I)
=2\theta_\Psi\pmod{2\pi}.
$$

The positive-root lift's optional spatial phase-current diagnostic is

$$
\mathbf{J}_\Psi
=\Psi_0^{(+)}\nabla\Psi_1^{(+)}
-\Psi_1^{(+)}\nabla\Psi_0^{(+)}
=\rho\,\nabla\theta_\Psi.
$$

The density-lattice diagnostic is

$$
\mathbf{J}_d=E_Y\nabla E_I-E_I\nabla E_Y
= (E_Y^2+E_I^2)\nabla\theta_d
=2\sqrt{E_YE_I}\,\mathbf{J}_\Psi.
$$

Under this lift, $\mathbf{J}_\Psi$ has model-density/length units while
$\mathbf{J}_d$ has model-density$^2$/length units; a physical-unit mapping
inherits the external $\rho_*$ normalization. They are distinct diagnostics. A
named projection of $\mathbf{J}_\Psi^{(+)}$ records a spatial component along a
specified direction. Physical-current and inter-rung transport interpretations
require a separate constitutive map and remain **Hypothesized**. Local coherence
and phase-current structure are summarized as **Qi**, the third fundamental in
a conceptual coherence-bookkeeping sense; Qi is not an independent field,
substance, or dynamical degree of freedom. The field equation is the two-fluid
PDE:

### 1.1 Energy densities

$$
E_Y\ge 0,\qquad E_I\ge 0,\qquad
\rho = E_Y + E_I,\qquad \pi = E_Y - E_I
$$

- $\rho$: total model-unit density (always $\ge0$); its physical energy-density
  mapping requires the external reference $\rho_*$.
- $\pi$: signed component imbalance (ranges $-\rho$ to $+\rho$); “Yang excess” is a phenomenological label for its positive side.

For $\rho>0$, the ratio $\pi/\rho$ is a dimensionless composition/imbalance
coordinate. The full local state remains the pair $(\rho,\pi)$, equivalently
$(E_Y,E_I)$.

### 1.2 The $\varphi$-attractor

The formal attractor penalty is:

$$
V_{\text{attr}} = \frac{\lambda}{2}(E_Y - \varphi E_I)^2
$$

Its minimizer is $E_Y=\varphi E_I$. In the positive-root lift, this is
$\Psi_0^{(+)}:\Psi_1^{(+)}=\sqrt{\varphi}:1$. When this expression is used
with solver-normalized fields, $\lambda$ inherits the selected solver-family
parameter: the `TwoFluid3DGPU` default is $\lambda=0.02$, while $\lambda=0.1$
is a named experiment convention only where explicitly passed. An
action-level coefficient and field normalization would be an additional
optional choice and is not fixed here.

If one selects unconstrained Euclidean gradient flow of this penalty, its
conversion part would be

$$
\dot E_Y=-\lambda(E_Y-\varphi E_I),\qquad
\dot E_I=+\lambda\varphi(E_Y-\varphi E_I),
$$

which changes $\rho$. The canonical PDE below instead selects an
equal-and-opposite, gated fixed-$\rho$ rank-one relaxation sharing the same
minimizer. A fixed-$\rho$ Euclidean projection with mobility $\mu$ would match
the canonical conversion only after the additional convention
$\mu\lambda(1+\varphi)/2=\lambda_{\mathrm{PDE}}$; no such mobility or
identification of an action coefficient with $\lambda_{\mathrm{PDE}}$ is derived
here.

The fixed-point imbalance is

$$
\alpha_0 \equiv \frac{\pi}{\rho}
= \frac{\varphi-1}{\varphi+1}
= \varphi^{-3}\approx 0.236.
$$

The fixed-point imbalance $\alpha_0 = \pi/\rho = \varphi^{-3}$ follows
conditionally from the stated attractor; it appears in cosmology (dark
energy), particle physics (the asserted weak-angle boundary), and gravity
(effective coupling). The equilibrium Yang fraction is $\varphi^{-1}$.

### 1.3 Two-fluid PDE

The selected canonical/theory equations use reference-normalized variables on
an expanding 3D spatial domain, an assumed domain choice; the local conversion
term does not determine the spatial dimension. The canonical state variables
are the nonnegative densities $E_Y$ and $E_I$; the positive-root lift is used
for coordinate diagnostics and formal action expressions. The displayed
q-gated rank-one form is a selected theory form and an optional implemented
mode, not a claim about every solver default:

$$\partial_t E_Y = -(\mathbf{u}\cdot\nabla)E_Y + D\nabla^2 E_Y - \lambda(1-q)(E_Y - \varphi E_I)$$

$$\partial_t E_I = -(\mathbf{u}\cdot\nabla)E_I + D\nabla^2 E_I + \lambda(1-q)(E_Y - \varphi E_I)$$

The conversion term in this selected form is gated, linearized, equal and
opposite in the two channels, and conserves total density exactly. The solver
family exposes $\lambda$ as its conversion-rate parameter, $D$ as scalar
density diffusion, and $\nu$ as velocity viscosity. In
`two-fluid/cassi_two_fluid_3d_gpu.py`, the base `TwoFluid3DGPU.rhs` uses the
ungated $-\lambda\varepsilon$ term. `ExpandingTwoFluid3DGPU` defaults to
`qi_gate=False` and applies $(1-q)$ only when `qi_gate=True`; `gate_model` and
`qi_memory` also affect the q-gated receipt. Its constructor defaults are
$\lambda=0.02$, $D=0$, and $\nu=0.001$; $\lambda=0.1$ is a named experiment
convention only where explicitly passed. The relation $\lambda=1/(2w)$ at
$w=5$ is a **Hypothesized** Wu Xing cycle linkage, not a
$\varphi$-derived rate or a determination of its units; the openness $(1-q)$
is the Qi gate (§2.4). The fixed point $E_Y=\varphi E_I$ is the attractor of
§1.2, while the full PDE remains conditional on this stated rank-one/gated
solver choice.

Here $\mathbf{u}$ is the shared velocity field. The $\nu$ viscosity term acts
in the velocity equation, while $D\nabla^2 E_{Y/I}$ is the scalar density
diffusion shown above. An optional **Hypothesized**
gravity/information-potential closure couples $\Phi$ to the velocity equation;
that velocity then advects both density channels through the displayed shared
term.

Writing $\kappa=\lambda(1-q)$, the conversion-only matrix is

$$
\partial_t
\begin{pmatrix}E_Y\\E_I\end{pmatrix}_{\!\mathrm{conv}}
=\kappa
\begin{pmatrix}-1&\varphi\\1&-\varphi\end{pmatrix}
\begin{pmatrix}E_Y\\E_I\end{pmatrix}.
$$

This matrix has rank one and eigenvalues $0$ and $-\kappa(1+\varphi)=-\lambda(1-q)(1+\varphi)$. The zero mode is the fixed-point line and the nonzero mode relaxes the imbalance $\varepsilon$; $\rho=E_Y+E_I$ is conserved while $E_Y^2+E_I^2$ is generally not. The canonical conversion is therefore a density-plane relaxation, not a norm-preserving $SO(2)$ generator.
---

## 2. Qi: Defined Scalar Coherence Bookkeeping and Optional Spatial Phase-Current Lift

Qi is the canonical defined/constitutive scalar coherence diagnostic
$q(E_Y,E_I)$, with $\rho$ and $\varepsilon$ supplying density bookkeeping. Its
algebraic bounds and equilibrium values are Derived conditional on this
definition and the reference normalization. The optional positive-root lift
defines $\mathbf{Q}_{\mathrm{lift}}=(\rho,\mathbf{J}_\Psi^{(+)})$ as a diagnostic
pair; it is not a canonical/foundational state variable, independent field,
substance, or dynamical degree of freedom.
A named projection of $\mathbf{J}_\Psi^{(+)}$ records a spatial component along a
specified direction. Physical-current and inter-rung transport interpretations
require a separate constitutive map and remain **Hypothesized**.

### 2.1 Canonical scalar Qi coherence

The canonical solver defines the scalar Qi coherence at each spacetime point
from the local reference-normalized field state:

$$\varepsilon = E_Y - \varphi E_I,\qquad \rho = E_Y + E_I$$

$$q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \varepsilon^2}$$
For $\rho>0$, let $s\equiv\pi/\rho=(E_Y-E_I)/(E_Y+E_I)\in[-1,1]$.
Then

$$
\frac{\varepsilon}{\rho}
=\frac{\varphi^2s-\varphi^{-1}}{2},
\qquad
q(\rho,s)
=\left[
1+\left(\frac{\varphi^2s-\varphi^{-1}}{2}\right)^2
+\frac{\varphi^{-2}}{\rho^2}
\right]^{-1}.
$$

Thus $q$ depends on both composition and total density; $q$ and $\pi/\rho$
are not independent inputs, but $q$ is not a function of composition alone.
At the fixed composition $s=\varphi^{-3}$, the deviation term vanishes and
$q=\rho^2/(\rho^2+\varphi^{-2})$: it approaches $0$ as $\rho\to0$ and $1$
only as $\rho\to\infty$. The formal $\varphi^6$ coupling range therefore
requires this fixed-composition, density-asymptotic interpretation; varying
$q$ at fixed finite density is not an independent operation.

The bare $\varphi^{-2}$ term is in the solver's reference units. For physical
density variables, with $\rho_{\mathrm{phys}}=\rho_*\rho$ and
$\varepsilon_{\mathrm{phys}}=\rho_*\varepsilon$, the same diagnostic is

$$
q=\frac{\rho_{\mathrm{phys}}^2}
{\rho_{\mathrm{phys}}^2+\varphi^{-2}\rho_*^2+\varepsilon_{\mathrm{phys}}^2},
\qquad \rho_* \text{ external}.
$$

No reference-density scale is derived here. Qi ranges from $q \to 0$ (far
from $\varphi$-equilibrium, large deviation $|\varepsilon|$) toward the
finite-density equilibrium value $q_{\mathrm{eq}}(\rho)=\rho^2/(\rho^2+\varphi^{-2})<1$
when $\varepsilon\to0$. The limit $q\to1$ additionally requires $\rho\gg\varphi^{-1}$;
at the $\varphi$-equilibrium ($\varepsilon=0$; the solver's reference state
$E_Y=1$, $E_I=\varphi^{-1}$ gives $\rho=\varphi$), the coherence and the gate
openness are:



$$q_{\text{eq}} = \frac{\varphi^{2}}{\varphi^2 + \varphi^{-2}} \approx 0.873, \qquad 1 - q_{\text{eq}} = \frac{\varphi^{-2}}{\varphi^2 + \varphi^{-2}} = \frac{\varphi^{-2}}{3} \approx 0.127$$

### 2.2 Optional positive-root lift diagnostic pair

The optional positive-root lift bookkeeping pair is

$$
\mathbf{Q}_{\mathrm{lift}}=(\rho,\;\mathbf{J}_\Psi^{(+)})
$$

- **Density component** $\rho$: the local total density. The dimensionless coherence diagnostic $q$ does not set the density.
- **Optional current component** $\mathbf{J}_\Psi^{(+)}=\Psi_0^{(+)}\nabla\Psi_1^{(+)}-\Psi_1^{(+)}\nabla\Psi_0^{(+)}=\rho\nabla\theta_\Psi$: the positive-root lift phase-current diagnostic. For a specified unit direction $\hat{\mathbf t}$, $J_{\Psi,\parallel}=\hat{\mathbf t}\cdot\mathbf{J}_\Psi^{(+)}$ records the chosen spatial projection. The density-lattice diagnostic $\mathbf{J}_d$ has the conversion and distinct units stated in §1, so the two diagnostics are not interchangeable; physical-current and inter-rung transport interpretations require a separate constitutive map and remain **Hypothesized**.

### 2.3 Qi-enhanced gravity

The candidate gravitational coupling is modulated by the scalar Qi coherence:

$$
G_{\text{eff}} = \frac{\pi}{\rho}\,(1 + (\varphi^{6}-1)q)\,G
$$

This is a coupling-magnitude parametrization. Since the canonical state permits
$\pi=0$ and $\pi<0$, it is undefined as an inverse Einstein–Hilbert
coefficient at $\pi=0$ and changes sign on the Yin-dominant branch. Any use in
a covariant action therefore requires a restricted positive-imbalance branch or
a new regularized/sign constitutive map.

where $\xi = \varphi^6 \approx 17.944$ is the Qi-gravity coupling constant. At the $\varphi$-fixed point the Qi boost is active at its equilibrium value: $\varepsilon = 0$ gives $q = q_{\text{eq}}(\rho) = \rho^2/(\rho^2 + \varphi^{-2})$ (density-dependent), and with $\pi/\rho = \alpha_0 = \varphi^{-3}$ the fixed-point coupling is the closed form

$$
G_{\text{eff}}(\varepsilon=0) = \varphi^{-3}\left(1 + (\varphi^{6}-1)\,q_{\text{eq}}(\rho)\right)G
  = \varphi^{-3}\,\frac{\varphi^{8}\rho^2+1}{\varphi^{2}\rho^2+1}\,G
$$

At the reference state ($E_Y = 1$, $E_I = \varphi^{-1}$, $\rho = \varphi$) this specializes to $q_{\text{eq}} = \varphi^2/(\varphi^2+\varphi^{-2}) \approx 0.873$ and

$$
G_{\text{eff}} = \varphi^{-3}\,\frac{\varphi^{10}+1}{\varphi^4+1}\,G \approx 3.73\,G
$$

(the equilibrium boost reduces to $1+(\varphi^6-1)q_{\text{eq}} = (\varphi^{10}+1)/(\varphi^4+1) \approx 15.79$; on this fixed-composition line, the dilute limit $\rho\to0$ gives $G_{\text{eff}}\to\alpha_0G\approx0.236\,G$ and the dense limit $\rho\to\infty$ gives $G_{\text{eff}}\to\varphi^3G\approx4.236\,G$; these are branch limits, not global state-space bounds because $q=q(\rho,s)$ varies with total density and composition).

The $\alpha$-free bracket factor $1+(\varphi^6-1)q$ is bounded by $\varphi^6\approx17.94$ for $0\le q\le1$, separately from the composition prefactor $s=\pi/\rho$. For the unrestricted-composition high-density expression $q_\infty(s)=\left[1+\left((\varphi^2s-\varphi^{-1})/2\right)^2\right]^{-1}$, the product $s[1+(\varphi^6-1)q_\infty(s)]$ has an interior peak $\approx9.601$ at $s\approx0.8569$ on the physical positive-imbalance interval $0\le s\le1$; if $s>1$ is formally admitted, it is unbounded, so this value is not a global ceiling. The halo-regime value is $\alpha_{\text{halo}}(1+(\varphi^{6}-1)q)\approx9.0$ ($\alpha_{\text{halo}}\approx0.7$, $q\approx0.7$), giving velocity boosts $2.8$–$3.0\times$ via $\sqrt{\alpha_{\text{halo}}(1+(\varphi^{6}-1)q)}$; no universal $G_{\text{eff}}$ or velocity ceiling $\varphi^3$ follows.

### 2.4 Temporal Coherence: The IIR Memory

An optional temporal-memory closure can supplement the instantaneous Qi
diagnostic with a per-cell exponential moving average (EMA) of the
$\varphi$-deviation. The canonical solver's `qi_memory` path is default-off;
enabling it changes the diagnostic used by the gate. The EMA is a causal
smoother using past samples.

$$\varepsilon^2(t) = \left(E_Y(t) - \varphi E_I(t)\right)^2$$

$$\bar{\varepsilon}^2(t) = (1-\tau)\,\bar{\varepsilon}^2(t-\Delta t) + \tau\,\varepsilon^2(t)$$

With the closure enabled, the EMA coefficient is conventionally set to
$\tau=\varphi^{-1}\approx0.618$; this is a solver timescale choice, not a
derived physical cycle. The Qi coherence then uses the temporally filtered
deviation in the same reference-normalized model units:

$$q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \bar{\varepsilon}^2}$$

**Mechanism—past-sample smoothing:** When the neutral component pattern
repeats quasi-periodically (standing-wave or bound-state solutions), the
optional IIR memory retains a weighted history of the $\varepsilon^2$ signal.
As the EMA converges to the pattern's recent mean, $\bar{\varepsilon}^2$
filters transient spikes. In the tested closure this produces a
**stabilized** $q$; the reported variance drops by $\sim37\%$ compared to
instantaneous $\varepsilon^2$.

**Jensen check for the tested comparison:** $q(\varepsilon^2)$ is a convex,
decreasing function of $\varepsilon^2$. Jensen's bound applies when the
comparison preserves the same mean and the required convex-order relation;
the observed mean/variance shifts depend on the sampled dynamics and
filter initialization. The reported $\sim -0.3\%$ mean change and $\sim-37\%$
variance change are receipts from the tested closure, not general properties.
Temporal coherence is a **stabilizer** in that receipt.

**Conversion gating:** The term $(1-q)$ gates the $\varphi$-attractor conversion.
When the filtered $q$ is high, conversion is suppressed; when it is low,
conversion reactivates and drives the system toward $\varphi$-equilibrium.


**Timescale matching (when enabled):** Choosing $\tau=\varphi^{-1}$ is a solver convention motivated by the attractor timescale. The IIR's effectiveness depends on the ratio $\tau/\omega$, where $\omega$ is the characteristic frequency of $\varepsilon^2$ fluctuations. In slowly evolving cosmological regimes ($H\ll1$), a smaller $\tau$ can give the memory comparable inertia. The $\varphi^{-1}$ value is near-optimal for dynamics at the conversion timescale $\sim1/\lambda$ in the tested closure; neither the coefficient nor the closure is forced on the canonical instantaneous diagnostic.

**Kernel identity (Derived conditional on the asserted $\tau$ and the EMA
form).** The EMA weights are exactly the odd $\varphi$-powers:

$$\tau = \varphi^{-1} \iff w_k = \tau(1-\tau)^k = \varphi^{-1}\varphi^{-2k} =
\varphi^{-(2k+1)}, \qquad k \ge 0,$$

with an e-folding of $1/\ln(\varphi^2)\approx1.04$ EMA steps. The normalized
weights sum to one,

$$
\sum_{k\ge0}w_k=\tau\sum_{k\ge0}(1-\tau)^k
=\varphi^{-1}\sum_{k\ge0}\varphi^{-2k}
=\varphi^{-1}\varphi=1,
$$

while the unnormalized geometric factor alone is

$$
\sum_{k\ge0}(1-\tau)^k=\sum_{k\ge0}\varphi^{-2k}=\varphi.
$$
Comparing this kernel to a hypothetical per-rung transfer amplitude $\varphi^{-1}$
would instead select $\tau=\varphi^{-2}$ (a factor $\varphi$ off); this comparison
is a solver-kernel convention, not a physical rung-crossing time, transport
law, or fixed phase/pitch assignment. The asserted EMA value remains
$\tau=\varphi^{-1}$.

### 2.5 Gate Transmission Function: Status and Selection Test

The first-principles conversion equation supplies the openness factor $(1-q)$.
Some application documents multiply that driving term by a separate
transmission function,

$$
\boxed{g(q) = \frac{q}{\varphi^2 + q^2}}.
$$

This single-channel form is an **Asserted input**. The action and the Qi
definition in §§1–2 supply the field potential, $q$, the $(1-q)$ closure, and
the IIR memory; they contain no equation selecting the rational function above.
Consumer documents cite this section for the status audit and input boundary,
not as a derivation of the rational function.

The available selection constraints are insufficient. Attractor consistency
requires a finite non-negative multiplier on $0\le q\le1$ and
$g(q)(1-q)\to0$ at $q\to1$; the family $g_A(q)=q/(A+q^2)$ satisfies these
conditions for every $A\ge1$. The current form has

$$
\frac{d}{dq}\bigl[g(q)(1-q)\bigr]
 = \frac{\varphi^2 - 2\varphi^2q - q^2}{(\varphi^2+q^2)^2},
\qquad
q_{\mathrm{power}}=\sqrt{\varphi^4+\varphi^2}-\varphi^2\approx0.4597,
$$

but the peak location is a consequence of the asserted denominator, not a
selection rule for it. The five-channel pentagon document derives the channel
weights $b_i=\varphi^{-(2+i)}$ and their efficiencies; it gives no equation
that reduces those channels to this single-channel denominator.

A conditional geometric construction exists. If one adds the reciprocal
coherence duality $q\mapsto\varphi^2/q$, a minimal rational family is

$$
g_m(q)=C_m\frac{q^m}{\varphi^{2m}+q^{2m}},
$$

which is self-dual for every positive integer $m$. A linear small-$q$ response
selects $m=1$; a further slope condition $g'(0)=\varphi^{-2}$ selects
$C_1=1$. Both conditions are additional inputs absent from the action. The
selection audit is reproducible in `computations/gate_origin_audit.py`.

**Epistemic boundary:** qualitative gate properties and the power peak are
Derived conditional on the asserted form; the denominator $\varphi^2+q^2$ and
its normalization remain Asserted.

**Exact values (all Derived $\varphi$-algebra on the asserted $g$; the
selection status of $g$ stays Asserted).** The gate's values at the
dynamically-distinguished coherences are closed $\varphi$-algebraic forms:

$$\boxed{\;q = \frac{\varphi^2}{4}\ \text{(the pinch } r = \varphi^{-1}\text{)}:
\quad g = \frac{4}{17+\varphi} \approx 0.2148;
\qquad
q = q_{\text{eq}} = \frac{\varphi^2}{3}:
\quad g = \frac{3}{10+\varphi} \approx 0.2582\;}$$

$g$ is monotone on $[0,1]$ with maximum $\max g(q) = g(1) =
1/(\varphi+2) \approx 0.276 < \tfrac12$: the transmission never reaches
half-open, so the openness $(1-q)$ is what actually gates conversion. The
self-duality fixed point is $g(\varphi) = \varphi^{-1}/2$—the identity
$g(\varphi^2/q) = g(q)$ holds formally, with the dual lying outside the
physical range $[0,1]$. The five-channel bank cannot reduce the single-channel
form: the solver's five gate aggregates OPENNESS (the constants
$0.438 \to 0.348$ of `foundations/wa-pentagon-gate.md` §2.3–2.5), never the
$q$-dependent shape; the pole argument (five distinct pole pairs vs one)
excludes proportionality; and
$\sum_{i=0}^{4} \varphi^{-(2+i)} = 1 - \varphi^{-5}$—exactly the Wu Xing gap.
For a ratio check, write $E_I=A$ and $E_Y=rA$. Since $q=\tfrac12$ requires $\rho^2-\varepsilon^2=\varphi^{-2}$, the condition is
$$A^2\bigl[(1+r)^2-(r-\varphi)^2\bigr]=\varphi^{-2}.$$
At $r=\varphi^{-2}$ the bracket equals $\varphi^{-2}$, so $q=\tfrac12$ only at $A=1$—that is, $E_I=1$ and $E_Y=\varphi^{-2}$ in the reference solver normalization. The ratio alone does not fix $q$; this algebraic comparison is not a physical rung assignment.

---


### 2.6 Density-Plane Relaxation Rate

The canonical conversion is a rank-one relaxation in the density variables, not an $SO(2)$ generator. With $\kappa=\lambda(1-q)$, its conversion-only matrix has eigenvalues $0$ and $-\kappa(1+\varphi)=-\lambda(1-q)(1+\varphi)$. It conserves $\rho=E_Y+E_I$ while generally changing $E_Y^2+E_I^2$.

For the density-plane angle

$$
\theta_d=\operatorname{atan2}(E_I,E_Y),
$$

the exact state-function rate is

$$\boxed{\frac{d\theta_d}{dt}=\lambda(1-q)\,\frac{\rho\,\varepsilon}{E_Y^2+E_I^2}}$$

The rate vanishes exactly at the $\varphi$-line ($\varepsilon=0$) and grows with $|\varepsilon|$, gated by the openness $(1-q)$. Positive $\varepsilon$ gives positive $\theta_d$ drift; calling that direction toward the Yin-named axis uses the density-plane coordinate convention and does not assert a universal spatial transport direction, while negative $\varepsilon$ gives the reverse. Measured in the committed solver: four homogeneous arms at $\lambda=0.05$, $t=4$ match the formula to per-checkpoint relative error $\le2.2\times10^{-3}$ with 100% sign agreement (`two-fluid/run_winding_rate_probe.py`).
This receipt uses `ExpandingTwoFluid3DGPU(lam=0.05, qi_gate=True,
gate_model='single', qi_memory=False)`; it is a named q-gated probe, not the
`TwoFluid3DGPU` or expanding-constructor default.

**Density-plane relaxation (exact).** Since $d\varepsilon/dt=-\lambda(1+\varphi)(1-q)\varepsilon$, the conversion rate and the gate cancel in $d\theta_d/d\varepsilon$, and with $\rho$ conserved the density-plane angle is a function of $\varepsilon$ alone, $\theta_d=\operatorname{atan}((\rho-\varepsilon)/(\rho\varphi+\varepsilon))$. The total density-plane drift accumulated while a state relaxes from $\varepsilon_0$ to equilibrium is therefore

$$\boxed{\Delta\theta_d=\operatorname{atan}\!\left(\frac{1}{\varphi}\right)-\operatorname{atan}\!\left(\frac{\rho-\varepsilon_0}{\rho\varphi+\varepsilon_0}\right)}$$

independent of $\lambda$ and of the gate shape. Its extremes are the Yang limit $\varepsilon_0\to\rho$ ($\Delta\theta_d\to+\operatorname{atan}(\varphi^{-1})\approx0.554$ rad) and the Yin limit $\varepsilon_0\to-\rho\varphi$ ($\Delta\theta_d\to-\operatorname{atan}(\varphi)\approx-1.017$ rad)—if one assigns a rung coordinate by the map $\delta n_{\mathrm{map}}\equiv\Delta\theta_d/(2\pi)$, the bound $|\delta n_{\mathrm{map}}|\le\operatorname{atan}(\varphi)/(2\pi)\approx0.162$ is **Hypothesized**, not a PDE-derived rung offset or physical rung flux. For small deviations the integral reduces to $\Delta\theta_d\approx\rho\varepsilon_0/[(1+\varphi)(E_Y^2+E_I^2)]$. Under that same Hypothesized map, a half-rung offset ($\delta n_{\mathrm{map}}=0.5$, e.g. the BAO half-step at 284.5, `foundations/dimensionful-cascade.md` §6) would correspond to a $\pi$ density-angle change and lies about $3.09\times$ beyond the mapped relaxation bound; the half-step class is assigned instead to the separate parity structure of `foundations/rung-offset-mechanism.md` §7.

The fixed-pitch clocks ($\varphi^{-2}$ turns per rung, the $69.1^\circ$ pitch tangent of `foundations/spiral-dynamics.md` §2.2) belong to the **Hypothesized** conversion→expansion term. The canonical density-plane drift is the $\varepsilon$-proportional state function above and stops at the $\varphi$-line. Its fluctuation statistics cannot produce the fixed-pitch clock: $\langle d\theta_d/dt\rangle=0$ identically for symmetric fluctuations (the committed solver has no noise source), the exact even part is negative at the vacuum scale, and the phase diffusion is $0.2$–$0.6\%$ of $\Omega_S$—so no rectification path exists and the two clocks stay separate (the canonical drift governs the $\varepsilon\neq0$ sector; the Hypothesized fixed-pitch clock governs the background-vacuum sector).

## 3. Four Pillars: Conditional Extensions and Receipts

### 3.1 Quantum Particles (Pillar 1; optional reduction)

The canonical two-fluid PDE supplies the density-pair evolution, conserved
total density under conversion, and Qi diagnostic. A Schrödinger/Bohm reduction
requires the optional positive-root amplitude/action and quantum-potential
sector. Within that construction, the following component-wise
quantum-potential/operator term is **Derived conditional** on the added ansatz.
Because it carries the free component index $\alpha$, it is not a scalar
Lagrangian density and does not by itself define an action:

$$
\mathcal{Q}_{\mathrm{QP},\alpha}^{(+)}
= -\frac{\hbar^2}{2m^2}
   \frac{\nabla^2 M^\beta}{M^\beta}\Psi_\alpha^{(+)},
\quad \beta = \frac{\varphi^{-1}}{2},\;
M = \rho = E_Y + E_I
  = (\Psi_0^{(+)})^2 + (\Psi_1^{(+)})^2
$$

The optional sector assigns atomic orbital energies as standing waves of the
two-field system. A numerical DFT receipt for $Z=1$–$10$ reports He at 0.9%
error and relativistic Dirac–Kohn–Sham at 3.2%; these are computed results for
the optional construction, not a reduction supplied by the canonical density
PDE. A Dirac equation via the Foldy–Wouthuysen transformation is a
**Hypothesized** conditional relativistic extension.

### 3.2 Cosmology (Pillar 2; optional Hubble closure)

An FLRW background plus a separately supplied Hubble closure gives the standard
Friedmann form:

$$
H^2 = \frac{8\pi G}{3}\rho_{\text{tot}} + \frac{\Lambda_{\text{eff}}}{3}
$$

This equation is **Derived conditional** on the FLRW embedding and its Hubble
closure. The canonical conversion conserves total density and supplies no
determination of $H$ or $\Lambda_{\text{eff}}$; a conversion-to-expansion source
identification is **Hypothesized**. Within that optional cosmological extension,
$\Lambda_{\text{eff}}$ is a model source term associated with Yang–Yin
conversion dynamics.

- **DESI DR2 baryon acoustic oscillations (Calibrated comparison):**
  $w_0 \approx -0.75 \pm 0.06$ is the anchor; the Cassi ODE gives
  $w_0=-0.87$, $2\sigma$ from the anchor.
- **Planck 2018 CMB (Mapped closed-form comparison):** the spectral-index
  expression $n_s=1-2\varphi^{-1}/N_e=0.9691$ uses $N_e=40$ and lies
  $1.0\sigma$ from Planck $0.9649\pm0.0042$ as a closed form. The gate
  slow-roll trajectory does not reproduce this value; $N_e$ is a start-threshold
  choice, **Mapped** in the ledger, 2026-08-06
  (`computations/slow_roll_trajectory.py`).
- **Hubble tension (Unresolved receipt):** the full $H(z)$ fit performed
  2026-08-06 (`computations/hz_full_fit.py`) leaves registry C3/T4 unresolved.
  The pipeline CMB-inferred value is $H_0\approx65.8$ km/s/Mpc versus the local
  $73.0$ km/s/Mpc; no resolved value is claimed.

Within the optional source closure, the dimensionless conversion residual
$(1-q)(E_Y-\varphi E_I)$ may enter a separately dimensionful dark-energy
source map. The constructor default is $\lambda=0.02$; $\lambda=0.1$ is a
named experiment convention only where explicitly passed. The candidate
cosmological rate is the separate $\kappa_{\text{DE}}=3\varphi^2H_0$.
This conversion-to-expansion identification is **Hypothesized**.

### 3.3 General Relativity (Pillar 3; optional Qi-gravity extension)

The canonical density PDE supplies no metric or force law. An optional
Qi-gravity constitutive/action extension associates the Yang–Yin ratio with an
effective coupling magnitude and an optional metric/force closure. The
displayed force branch uses $\Phi=-GM/r$ and a $+\pi[1+(\varphi^6-1)q]\nabla
\Phi$ term; since $\nabla\Phi=+GM\,\hat{\mathbf r}/r^2$, it is outward for
positive fixed-point $\pi$. Thus the values below are coupling magnitudes.
Attractive Newtonian/GR limits, rotation curves, Mercury, or PPN behavior
require a separate **Hypothesized** sign-changing force convention/closure;
the canonical PDE and the displayed term do not supply one.

- **Mercury precession (computed receipt):** a separate optional metric/force
  closure returns GR's $42.98''$/century exactly in the recorded calculation;
  this receipt does not establish attraction for the displayed-sign branch.
- **Strong-field PPN (Derived conditional):** an optional extension uses
  $\beta = 1 + \mathcal{O}(\xi q^2)$ and $\gamma = 1 + \mathcal{O}(\xi q^2)$,
  conditional on its additional sign and metric closure.
- **Gravitational waves (Hypothesized):** the extension assigns modified
  propagation speed near high-Qi regions.
- **Rotation curves (Mapped comparison):**
  $v_C/v_B = \sqrt{\alpha_{\text{halo}}(1+(\varphi^{6}-1)q)}
  \approx 3.00\times$ with $\alpha_{\text{halo}}\approx0.7$ and $q\approx0.7$
  (range 2.8–3.0), using the proposed coupling-magnitude boost; an attractive
  interpretation requires the separate sign/force closure above.
- **Dwarf spheroidals (partial receipt):** 3/8 pass, MOND is preferred for
  4/8, and the fixed-composition benchmark $\sqrt{\varphi^6}=\varphi^3=4.2361$
  is exceeded in 3/8; this benchmark is not a universal velocity ceiling.

A formal Einstein–Hilbert substitution may be written on a restricted branch
where $\pi/\rho>0$:

$$
G_{\text{eff}} = \frac{\pi}{\rho}
\left(1 + (\varphi^{6}-1)q\right)G
$$

The corresponding covariant coefficient $1/G_{\text{eff}}$ is undefined at
$\pi=0$ and changes sign on the Yin-dominant branch $\pi<0$. It therefore
requires a restricted positive-imbalance branch or a new regularized/sign
constitutive map; no complete covariant action is derived here.

If $F\equiv1/G_{\text{eff}}$ is allowed to vary in spacetime, varying
$\int\sqrt{-g}\,F R$ also produces
$(g_{\mu\nu}\Box-\nabla_\mu\nabla_\nu)F$ and any implicit metric-dependence
terms. A displayed Einstein equation with only $G_{\text{eff}}T_{\mu\nu}$,
and the associated Bianchi conservation, is therefore valid here only as a
formal frozen-background or locally constant-$G_{\text{eff}}$ ansatz; a
scalar-tensor completion or explicit exchange terms would be required for a
variable coupling.

On the $\varphi$-fixed-point branch, the conditional coupling magnitude is

$$
G_{\text{eff}} = \varphi^{-3}\left(1+(\varphi^{6}-1)q_{\text{eq}}\right)G
\approx 3.73\,G
$$

where $q_{\text{eq}}=\varphi^2/(\varphi^2+\varphi^{-2})\approx0.873$ at the
reference density (§2.3). The dilute $\varphi$-line magnitude
$G_{\text{eff}}\to\varphi^{-3}G$ and the vanishing PPN corrections are
**Derived conditional** on an additional sign/metric extension, with
$\varepsilon=0$ and $\rho\to0$. The proposed high-coherence deviation from GR
is a **Hypothesized** modified-gravity mechanism.

### 3.4 Standard Model (Pillar 4; optional gauge/Higgs extension)

The canonical density PDE supplies no gauge or isospinor identification. Within
an optional gauge/Higgs extension, the weak-angle relation is used as an
**Asserted** boundary condition:

$$
\sin^2\theta_W = \varphi^{-3} \approx 0.236
$$

Experiment gives $\sin^2\theta_W=0.23122(4)$ at the $Z$ pole (MS-bar). The
$\varphi$-point value overshoots by $2.1\%$; the running MS-bar angle equals
$\varphi^{-3}$ at $\mu_*\approx233$ GeV and runs upward with energy
(`standard-model/sm-radiative-corrections.md` §3.3). This is a running-angle
comparison within the optional sector, not a canonical PDE derivation.

The proposed GUT coupling boundary is

$$
\alpha_{\text{GUT}} = \frac{\varphi^{-3}}{4\pi} \approx 0.0188
$$

The value is a **Hypothesized** gauge-sector mapping with an asserted
boundary condition; its comparison to running gauge couplings at
$M_{\text{GUT}}\sim10^{16}$ GeV remains a candidate rather than a
normalization-level match.

A conditional cascade-seesaw construction assigns neutrino masses at step 20
using selected/fitted Fibonacci offsets in the cascade RGE
(`computations/cascade_rge_pmns.py`); its PMNS angle relations remain
conditional coefficient-free candidates within the selected conversion-Jacobian
ansatz, not direct angle derivations from the canonical PDE:
$$
m_1 = 0.00356,\quad m_2 = 0.00931,\quad m_3 = 0.05019\ \text{eV},
\qquad \Sigma m_\nu = 0.0631\ \text{eV}
$$

The construction assumes normal ordering and no sterile state. Its
squared-mass ratio is $ \Delta m^2_{31}/\Delta m^2_{21}=33.82$ versus the
observed $33.89$ (0.2%), with rung offsets $\Delta_1=1.00$ and
$\Delta_2=1.75$. These are **Mapped/Calibrated** conditional receipts from
the optional seesaw construction.
## 4. Structural Constants and Status

| Symbol | Value | Identity or construction | Tier / source |
|--------|-------|--------------------------|---------------|
| $\varphi$ | $1.618033989$ | Golden ratio | **Fundamental axiom**—Postulate |
| $\varphi^{-1}$ | $0.618033989$ | $= \varphi - 1$ | **Derived** algebraic identity |
| $\varphi^{-2}$ | $0.381966011$ | $= 1 - \varphi^{-1}$ | **Derived** algebraic identity |
| $\alpha_0 = \varphi^{-3}$ | $0.236067978$ | $= (\varphi-1)/(\varphi+1)$ | **Derived conditional** fixed-point imbalance $\pi/\rho$; Yang fraction $\varphi^{-1}$ is **Mapped** (ledger row 500) |
| $\xi = \varphi^6$ | $17.94427191$ | $= \varphi^5 + \varphi^4$ | **Derived** algebraic identity; Qi-gravity coupling **Calibrated/conditional** |
| $\sin^2\theta_W$ | $\varphi^{-3}$ | VEV ratio in optional gauge/Higgs sector | **Asserted** boundary; physical mapping **Hypothesized** |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi)$ | Fixed-point imbalance / $4\pi$ | **Asserted** boundary; physical gauge mapping **Hypothesized** |
| $w_0$ | $-0.87$ | Two-fluid ODE ($\xi$ coupling) | **Calibrated** model output; `two-fluid/calibrate_initial_ratio_xi_v2.py` |
| $\delta_{\text{CP}}$ | $\pi \cdot \varphi^{-2} \approx 1.199$ | CKM hierarchy via Yukawa diagonalisation | **Mapped conditional** CKM-phase candidate |
| $\lambda$ | $0.02$ (`TwoFluid3DGPU` default); $0.1$ when explicitly passed | PDE conversion-rate parameter; $\lambda=1/(2w)$ at $w=5$ is a **Hypothesized** Wu Xing cycle linkage, not a $\varphi$-derived rate; the cosmological dark-energy rate is the separate dimensionful constant $\kappa_{\text{DE}}=3\varphi^2H_0$ | **Asserted default; named experiment convention; Hypothesized linkage** |

---

## 5. Conditional Classical Limits

The table records limits of the corresponding optional constitutive or action
extensions. Each effective theory requires the added sector named in the
condition; the canonical density PDE supplies the exact density evolution,
conversion conservation, rank-one relaxation, and the scalar Qi coherence diagnostic $q$.

| Limit | Condition and required extension | Effective theory | Status |
|-------|----------------------------------|------------------|--------|
| $q \to 0$ on the $\varphi$-line (the dilute attractor limit: $\varepsilon = 0$, $\rho \to 0$; $q \to 0$ alone means $\rho \to 0$ or large $|\varepsilon|$, while the reference fixed point has $q=q_{\text{eq}}\approx0.873$) | $\pi/\rho=\varphi^{-3}$ and optional Qi-gravity boost $\to1$ | GR-like limit with $G_{\text{eff}}=\varphi^{-3}G\approx0.236\,G$ | **Derived conditional** |
| $q \to 0$ on the $\varphi$-line, $\hbar \to 0$ | Optional Qi-gravity extension plus classical limit | Newtonian gravity | **Derived conditional** |
| $\hbar \not\to 0$, $q \to 0$ on the $\varphi$-line | Optional amplitude/quantum-potential sector plus dilute limit | Schrödinger equation | **Hypothesized reduction; Derived conditional within the ansatz** |
| $\lambda \to 0$ | Optional pressure, force, and source closure with conversion removed | Euler–Poisson system | **Derived conditional** |
| $\xi \to 0$ | Optional Qi-gravity sector switched off | Standard GR | **Derived conditional** |
| $\chi \to 0$ | Optional chemotaxis sector with its scalar closure | Passive scalar advection | **Derived conditional** |

These entries are sector-specific conditional limits and mappings. The
canonical two-fluid PDE does not, by itself, supply the listed metric,
quantum-potential, gauge, chemotaxis, or expansion closures.

---

## 6. Falsifiability

The framework records quantitative tests with the epistemic tier and sector
whose assumptions define each observable:

1. **Dark energy (Hypothesized optional conversion-to-expansion mapping):** the
   candidate test is $w(z)$ deviating from $-1$ by $\Delta w > 0.15$ at $z<1$.
   The current calibrated baseline is $w_0=-0.87$, $w_a=+0.012$ and does not
   constitute a DESI DR2 confirmation. A result here constrains the named
   conversion-to-expansion mapping.
2. **Gravitational waves (Hypothesized optional Qi-gravity extension):**
   $h_{\text{Cassi}}/h_{\text{GR}} \leq 1 + (\varphi^{6}-1)q$ in high-Qi
   regions (LIGO falsifiable).
3. **Atomic energies (Derived conditional within the optional quantum-potential
   extension; computed receipt):** He ground state within $1\%$ of $-2.903$
   E_h (chemical accuracy).
4. **Weak mixing angle (Asserted optional gauge boundary; Calibrated running
   comparison):** $\sin^2\theta_W = 0.236 \pm 0.001$ at tree level; the
   $\varphi^{-3}=0.236$ value is a boundary assignment, with its running
   realization at the calibrated $\mu_*\approx233$ GeV comparison.
5. **Neutrino mass spectrum (Mapped/Calibrated optional seesaw construction):**
   $m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019$ eV, normal ordering
   ($\Delta m^2$ ratio $33.82$ versus observed $33.89$).

The falsification scope is sector-local: each result bears on the named
optional extension or mapping, while the canonical core is tested only by
observables derived from the density PDE itself.

---

## 7. Relation to Companion Documents

| Document | Content |
|----------|---------|
| `foundations/unified-lagrangian.md` | Full Lagrangian density with all terms |
| `foundations/xi-derivation.md` | Derivation of $\xi = \varphi^6$ |
| `foundations/phi_attractor_synthesis.md` | $\varphi$-attractor dynamics |
| `standard-model/sm-from-phi.md` | Standard Model couplings |
| `cosmology/cosmology-from-phi.md` | DESI calibration and cosmology |
| `gravity/quantum-gravity.md` | UV-finite quantum gravity |
| `gravity/three-body-analytical.md` | Three-body problem in Cassi framework |
| `predictions/falsifiable-predictions.md` | Full prediction catalog |

---

## References

- `foundations/unified-lagrangian.md`—the complete action assembled from this document's pillars
- `foundations/xi-derivation.md`—$\xi = \varphi^6$ as a **Derived conditional** quadratic-coupling relation; the physical coupling pin is **Calibrated**
- `foundations/dimensionful-constants-status.md`—external dimensionful constants, parameter accounting
- `foundations/phi_attractor_synthesis.md`—$\varphi$-attractor dynamics
- `standard-model/sm-from-phi.md`—Standard Model couplings
- `cosmology/cosmology-from-phi.md`—DESI calibration and cosmology
- `gravity/quantum-gravity.md`—UV-finite quantum gravity
- `gravity/three-body-analytical.md`—three-body problem in the Cassi framework
- `predictions/falsifiable-predictions.md`—full prediction catalog
- `computations/gate_origin_audit.py`—selection-constraint audit for the asserted single-channel $g(q)$

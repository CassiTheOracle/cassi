# The Three-Body Problem in Cassi Two-Fluid Gravity

## Status: Derived conditional on the selected $d = 3$ computational/physical domain and displayed PDE force sign—September 2026

## Abstract

The Cassi two-fluid PDE with Qi-enhanced gravity reduces, for well-separated
blobs in the selected $d=3$ computational/physical domain, to point-particle
ODEs with the displayed PDE force convention and the state-dependent
coupling-magnitude coefficient
$G_{\text{eff},j}=\alpha_j[1+(\varphi^6-1)q_j]G$.
With $\Phi=-G\sum_iM_i/|\mathbf{x}-\mathbf{X}_i|$, the canonical
$+\pi[1+(\varphi^6-1)q]\nabla\Phi$ branch is outward for positive $\alpha_j$;
it does not reduce to attractive Newtonian gravity. At the $\varphi$-fixed
point $\alpha_j = \varphi^{-3}$ each blob carries its equilibrium coherence
$q_j = q_{\text{eq}}(\rho_j) = \rho_j^2/(\rho_j^2+\varphi^{-2})$
(density-dependent), giving
$G_{\text{eff},j} = \varphi^{-3}(1+(\varphi^{6}-1)q_{\text{eq}}(\rho_j))G$—
at the reference density $\rho_j = \varphi$ this is $\approx 3.73\,G$. The
dilute fixed point has the coupling magnitude
$G_{\text{eff}} = \varphi^{-3}G$ ($\rho_j \to 0$, $q_j \to 0$), while the
canonical velocity-force sign remains outward. Classical non-integrability and
attractive-orbit comparisons therefore apply only conditionally; an attractive
point-particle branch requires a separate Hypothesized sign-changing force
extension. Away from the fixed point, the internal coefficient and retained
blob masses vary with the field state. Interpreting that coefficient as a
body-dependent gravitational-to-inertial response requires a separate
matter-state map and gravity closure.
In conversion-dominated blob reductions, the conversion term tends to drive
each internal ratio toward the fixed point on the timescale
$\tau_\lambda \sim 1/[\lambda(1-q)(1+\varphi)]$.
The framework triad uses Yang and Yin as the two real density components; Qi
enters this reduction through the scalar coherence $q$ and its gate and
gravity factors. For a given spatial field snapshot, the positive-root
amplitude lift
$\Psi=(\sqrt{E_Y},\sqrt{E_I})$ supplies a local spatial diagnostic
$J_\Psi=\rho\nabla\theta_\Psi$, with
$\theta_\Psi=\operatorname{atan2}(\sqrt{E_I},\sqrt{E_Y})$. The density-angle
diagnostic $\theta_d=\operatorname{atan2}(E_I,E_Y)$ gives
$J_d=(E_Y^2+E_I^2)\nabla\theta_d
=2\sqrt{E_YE_I}\,J_\Psi$ for this positive-root lift. These diagnostics have
different units and describe local spatial gradients. Inter-rung transport
between cascade scales, a compact $SO(2)$ phase, and directional
Yang-out/Yin-in channels require an explicit constitutive extension and remain
Hypothesized optional structures.

> **Division of labor with `foundations/phi_attractor_synthesis.md`:** this document
derives the *reduction theory*—PDE → point-particle ODEs, the $\varphi$-fixed point,
and the comparison/integrability assessment under the displayed force sign. The
companion `foundations/phi_attractor_synthesis.md` applies the machinery
computationally (Paths 1–9: $R_\infty(d)$, precession, Lagrange points,
stability, rotation curves) only as a conditional comparison; an attractive
orbital branch requires the separate Hypothesized sign extension.
>
> The conversion terms carry the canonical Qi gate factor $(1-q)$
> (PDE-verified in `consciousness/trauma-as-frozen-gate.md` §10.4). In the
> dimensionless solver normalization $\rho_\star=1$,
> $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$; physical-density variables
> restore the denominator term $\varphi^{-2}\rho_\star^2$. At the
> $\varphi$-fixed point $E_Y=\varphi E_I$, the conversion term vanishes for
> every gate openness.

---

### 1. The Full PDE System

The Cassi two-fluid PDE with Qi-enhanced gravity governs three fields on the selected $d = 3$ computational/physical domain: the velocity field $\mathbf{u}$, the Yang energy density $E_Y$, and the Yin energy density $E_I$. The local field algebra and point-particle reduction are Derived conditional on this domain selection and have a d-dimensional form; numerical PDE claims below use $d = 3$. In the field-pair form of `foundations/cassi-theory-reference.md` §2.2 the system is:

#### Continuity

$$
\begin{aligned}
\partial_t E_Y &= -\nabla \cdot (\mathbf{u} E_Y) + D\nabla^2 E_Y
                - \lambda(1-q)(E_Y - \varphi E_I)
                - \chi_Y \nabla\cdot(E_Y \nabla\Phi) \\
\partial_t E_I &= -\nabla \cdot (\mathbf{u} E_I) + D\nabla^2 E_I
                + \lambda(1-q)(E_Y - \varphi E_I)
                + \chi \nabla\cdot(E_I \nabla\Phi)
\end{aligned}
$$

The conversion terms carry the canonical Qi gate factor $(1-q)$: the gate is
**open** (conversion runs hard) when $q \to 0$ and **closed** (system rests at
$\varphi$-balance) when $q \to 1$ (`foundations/cassi-theory-reference.md`
§2.5). At the $\varphi$-fixed point $E_Y = \varphi E_I$ the conversion term
vanishes for *any* gate openness—the fixed-point reduction below does not
depend on the gate state.

#### Momentum

$$
\partial_t \mathbf{u} = -(\mathbf{u}\cdot\nabla)\mathbf{u}
                        + \pi\,(1 + (\varphi^{6}-1)q)\,\nabla\Phi
                        - \nu\nabla^2\mathbf{u}
$$

#### Fields

$$
\rho = E_Y + E_I,\qquad
\pi = E_Y - E_I
$$

$$
\nabla^2\Phi = +4\pi G\,\rho \quad\text{(Poisson)}
$$

$$
q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \varepsilon^2},
\qquad \varepsilon^2 = (E_Y - \varphi E_I)^2
$$

(the canonical coherence of `foundations/cassi-theory-reference.md` §2.4).
$q\to1$ at high density near $\varphi$-equilibrium. In the nonnegative
canonical density domain, $q\to0$ requires $\rho/\rho_\star\to0$;
composition changes at fixed nonzero density have a strictly positive
lower bound (`foundations/quantum-free-fall-correspondence.md` §9.1).
At the $\varphi$-fixed point ($\varepsilon=0$) the
coherence is the equilibrium value $q_{\text{eq}}(\rho) = \rho^2/(\rho^2+\varphi^{-2})$
(density-dependent; $\approx 0.873$ at the reference density $\rho = \varphi$,
theory-reference §2.4), giving
$G_{\text{eff}} = \varphi^{-3}(1+(\varphi^{6}-1)q_{\text{eq}}(\rho))G \approx 3.73\,G$
at the reference density;
the dilute fixed-point coupling magnitude is $G_{\text{eff}} = \varphi^{-3}G$
($\rho \to 0$, $q \to 0$); the canonical force sign remains outward.

#### Parameters (dimensionless couplings; $c$, $\hbar$, $G$ external)

$$
\varphi = \frac{1+\sqrt5}{2} \approx 1.618,\quad
\xi = \varphi^6 \approx 17.944,\quad
\chi_Y = \chi/\varphi
$$

---

### 2. Point-Particle Reduction

Consider $N$ well-separated Gaussian blobs indexed by $j$. For each blob:

| Quantity | Definition |
|----------|-----------|
| $M_j = \int \rho_j\,dV$ | Total mass |
| $\Pi_j = \int \pi_j\,dV$ | Total Yang excess |
| $\mathbf{X}_j = \frac{1}{M_j}\int\mathbf{x}\,\rho_j\,dV$ | Center of mass |
| $\mathbf{V}_j = \frac{1}{M_j}\int\mathbf{u}\,\rho_j\,dV$ | Bulk velocity |
| $\alpha_j = \Pi_j/M_j$ | Signed density-imbalance fraction (dimensionless) |

#### 2.1 The key approximation

The force density on the velocity field is the field-level force $\mathbf{F} = \pi\,(1+(\varphi^{6}-1)q)\,\nabla\Phi$.
Its local sign relative to $\nabla\Phi$ follows $\pi$ (or the blob-integrated
$\Pi$). This local force relation supplies the point-particle reduction below;
it does not define a string-axis or inter-rung transport channel.
For a compact blob of size $\sigma$ separated by $r \gg \sigma$ from all other blobs,
the potential varies slowly across the blob, so the field-level force on the $j$-th blob is:

$$
\begin{aligned}
\mathbf{F}_j &\equiv \int \mathbf{F}_j\,dV \\
&= \int \pi_j\,(1+(\varphi^{6}-1)q_j)\,\nabla\Phi\,dV \\
&\approx \alpha_j\,(1+(\varphi^{6}-1)q_j)\,M_j \cdot \nabla\Phi(\mathbf{X}_j) \quad\text{when blob is relaxed}
\end{aligned}
$$

The factor $\alpha_j = \Pi_j/M_j$ is the **local density-imbalance fraction** of
blob $j$, equal to the average of $\pi/\rho$ over the blob.

#### 2.2 Far-field gravitational potential

From the $N$ point-like sources:

$$
\Phi(\mathbf{x}) = -G\sum_{i=1}^N \frac{M_i}{|\mathbf{x} - \mathbf{X}_i|}
$$

The gradient of $1/|\mathbf{x} - \mathbf{X}_i|$ is $-(\mathbf{x} - \mathbf{X}_i)/|\mathbf{x} - \mathbf{X}_i|^3$, so the potential's own leading minus flips the direction: at $\mathbf{X}_j$ the gradient points **outward** from each source,

$$
\nabla\Phi(\mathbf{X}_j) = +G\sum_{i\neq j} M_i\frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}
$$

The outward gradient fixes the point-particle force direction through the PDE
convention; no additional sign is introduced in the ODE below.

#### 2.3 Point-particle equations of motion (PDE → ODE)

The point-particle sector uses the PDE convention $+\nabla\Phi$ for the force:

$$
\ddot{\mathbf{X}}_j = +\alpha_j\,(1+(\varphi^{6}-1)q_j)\,\nabla\Phi(\mathbf{X}_j)
$$

With the outward gradient of §2.2, $\nabla\Phi(\mathbf{X}_j) = +G\sum_{i\neq j}M_i(\mathbf{X}_j-\mathbf{X}_i)/|\mathbf{X}_j-\mathbf{X}_i|^3$,
the **three-blob ODE system** is:

$$
\boxed{
\ddot{\mathbf{X}}_j = +G\,\alpha_j\,(1+(\varphi^{6}-1)q_j)\,
\sum_{i\neq j} M_i\frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}
}
$$

with each blob's internal dynamics:

$$
\boxed{
\dot{M}_j = \chi\int\nabla\cdot(E_I\nabla\Phi)\,dV
           - \chi_Y\int\nabla\cdot(E_Y\nabla\Phi)\,dV
}
$$

$$
\boxed{
\dot{\Pi}_j = -\lambda(1-q_j)\bigl[(1+\varphi)\Pi_j - \varphi^{-1}M_j\bigr]
              + \ldots \quad\text{(advection + chemotaxis)}
}
$$
The conversion terms cancel in $\dot M_j=\int(\partial_tE_Y+\partial_tE_I)\,dV$
and therefore exchange the two density components without changing their sum.
The displayed mass equation retains only the chemotaxis boundary-flux terms.
They vanish for a full domain with periodic or zero-normal-flux boundaries, or
for a blob boundary on which $E_I\nabla\Phi\cdot\mathbf n$ and
$E_Y\nabla\Phi\cdot\mathbf n$ both vanish; otherwise they represent mass
exchange across the chosen blob boundary.

with $q_j$ the canonical coherence $q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$ evaluated in blob $j$ (theory-reference §2.4). At the $\varphi$-fixed point ($E_Y = \varphi E_I$) the conversion bracket vanishes for any $q_j$—the gate does not change the equilibrium.

**The mass and Yang-excess fraction are DYNAMICAL variables**—mass changes
through chemotaxis boundary fluxes, while the Yang-excess fraction evolves via
conversion and chemotaxis, unlike Newtonian gravity where masses are constant.

---

### 3. The $\varphi$-Fixed Point

The critical equilibrium: $\alpha_j = \varphi^{-3}$ for all $j$—equivalently
$\varepsilon_j = 0$ (the $\varphi$-line), where each blob's coherence takes its
equilibrium value $q_j = q_{\text{eq}}(\rho_j) = \rho_j^2/(\rho_j^2+\varphi^{-2})$
(density-dependent).

#### 3.1 What happens

- The conversion term vanishes: $\lambda(1-q)(E_Y - \varphi E_I) = 0$ (because $E_Y = \varphi E_I$, independent of gate openness)
- The Qi enhancement factor is its equilibrium value: $1+(\varphi^{6}-1)q_{\text{eq}}(\rho_j)$, which is $\approx 15.8$ at the reference density ($q_{\text{eq}} \approx 0.873$)—not 1
- The equation of motion keeps the PDE-sign point-particle form with a
  density-dependent coupling; its plus sign is outward for positive $\alpha_j$:

$$
\ddot{\mathbf{X}}_j = +G\,\varphi^{-3}\left(1+(\varphi^{6}-1)q_{\text{eq}}(\rho_j)\right)
                      \sum_{i\neq j} M_i
                      \frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}
$$

**This is the outward-sign point-particle form with a rescaled, body-dependent
coupling** —
$G_{\text{eff},j} = \varphi^{-3}(1+(\varphi^{6}-1)q_{\text{eq}}(\rho_j))G
\approx 3.73\,G$ at the reference density. The coupling magnitude in the dilute
fixed-point limit is

$$
G_{\text{eff}} = \varphi^{-3} G \approx 0.236\,G,
$$

but the canonical branch is not attractive Newtonian gravity. An attractive
Newtonian reduction requires a separate sign-changing force extension and is
Hypothesized.

#### 3.2 The three-body problem at the $\varphi$-fixed point

The attractive Newtonian three-body problem is **not integrable** in general.
Its known special solutions are comparison cases:

| Solution | Condition | Canonical Cassi status |
|----------|-----------|------------------------|
| Lagrange L4/L5 | Any masses | No attractive analogue under the outward PDE sign |
| Euler collinear | Any masses | No attractive analogue under the outward PDE sign |
| Figure-8 | Equal masses | No attractive analogue under the outward PDE sign |
| Elliptic L4 | Any masses | No attractive analogue under the outward PDE sign |

These are individual periodic orbits of the attractive comparison problem, not
a general solution. The canonical Cassi branch does not derive these orbits or
an attractive Newtonian reduction; an attractive orbital branch is Hypothesized
and requires a separate sign-changing force extension.

#### 3.3 Proof of reduction

At $\alpha_j = \varphi^{-3}$ ($\varepsilon_j = 0$; equilibrium coherence
$q_j = q_{\text{eq}}(\rho_j)$):

1. **Mass evolution**: the conversion contribution to $\dot{M}_j$ cancels
   identically between $E_Y$ and $E_I$. Under the compact-blob boundary
   conditions below, the retained chemotaxis fluxes integrate to zero, so
   $\dot{M}_j = 0$ at the fixed point (and, in fact, whenever those boundary
   fluxes vanish).

   > **Proof**: For a compact blob, $\nabla\Phi \approx \mathbf{r}/|\mathbf{r}|^3$
   > and $E_I \approx \text{const} \times \exp(-r^2/2\sigma^2)$. The integral
   > $\int \nabla\cdot(E_I\nabla\Phi)\,dV = \oint E_I\nabla\Phi\cdot d\mathbf{S}$
   > over a surface containing the blob. At the blob boundary,
   > $E_I \approx 0$ (Gaussian tail), so the integral vanishes.

2. **Yang-excess fraction**: $\dot{\Pi}_j = 0$ by the same reasoning.

3. **Momentum**: $G_{\text{eff},j} = \varphi^{-3}(1+(\varphi^{6}-1)q_{\text{eq}}(\rho_j))G$
   is constant per blob (each blob's density is fixed at the fixed point);
   it reduces to the universal $\varphi^{-3}G$ in the dilute limit $\rho_j \to 0$.

**Therefore, under the displayed well-separated-blob reduction and the
vanishing boundary-flux assumptions, the $\varphi$-fixed internal state is
stationary for the retained mass and imbalance variables.** At this point the
velocity dynamics have the outward PDE sign with per-blob constant coupling
magnitudes; in the dilute limit ($\rho_j \to 0$) the magnitude is
$G_{\text{eff}} = \varphi^{-3}G$. This is not the attractive classical
Newtonian problem; that comparison requires the Hypothesized sign-changing
force extension.

---

### 4. Does Away-from-Equilibrium Help?

When $\alpha_j \neq \varphi^{-3}$, the conversion term acts as a linear restoring
force:

$$
\dot{\alpha}_j = \frac{\dot{\Pi}_j}{M_j} - \alpha_j\frac{\dot{M}_j}{M_j}
                \approx -\lambda(1-q_j)(1+\varphi)(\alpha_j - \varphi^{-3})
$$

plus higher-order corrections from advection and chemotaxis. The system relaxes
to $\alpha_j = \varphi^{-3}$ on the conversion timescale
$\tau_\lambda \sim 1/[\lambda(1-q_j)(1+\varphi)]$. At low-density or
large-mismatch states $q_j$ may be small and the gate is open; high density can
keep $q_j$ appreciable even away from the fixed-point line. Near equilibrium
$q_j$ may be large, which lengthens $\tau_\lambda$, while the conversion
bracket vanishes exactly on the fixed-point line.

**For the canonical velocity-force branch, these are internal-relaxation
comparisons rather than established orbital regimes:**

- If an orbit is supplied by the Hypothesized sign-changing force extension and
  $T_{\text{orbit}} \gg \tau_\lambda$, the internal state is near the
  $\varphi$-fixed point; the canonical branch itself remains outward-sign.
- If $T_{\text{orbit}} \ll \tau_\lambda$ in that conditional comparison, each
  blob has approximately constant $\alpha_j\neq\varphi^{-3}$, giving the
  state-dependent internal coupling-magnitude coefficient
  $G_{{\rm eff},j}=\alpha_j[1+(\varphi^6-1)q_j]G$. A physical
  body-dependent response requires the separate matter and gravity maps.
- If $T_{\text{orbit}} \sim \tau_\lambda$, the conditional system retains at least the 24 position, velocity, mass, and Yang-excess degrees of freedom counted in Appendix B, plus any unresolved profile-closure variables. Integrability is therefore not established. No attractive orbit is derived from the canonical PDE sign.

---

### 5. The Cassi Three-Body: Scope of the Reduction

Although the general problem is not integrable, the Cassi framework provides
a **geometric principle** that constrains the internal-state solutions:

#### 5.1 The $\varphi$ attractor

The local conversion term $\lambda(1-q)(E_Y - \varphi E_I)$ drives the
internal state of each blob toward $\alpha_j = \varphi^{-3}$ when the
conversion dynamics dominate. This is a **universal conversion-sector
equilibrium** independent of mass, position, or velocity. Within the displayed
blob reduction, it defines an attracting internal-state manifold:

$$
\mathcal{M}_\varphi = \{(\mathbf{X}_j, \mathbf{V}_j, M_j, \alpha_j)\;|\;
                    \alpha_j = \varphi^{-3} \;\forall j\}
$$

On this manifold each blob sits at $\varepsilon_j = 0$ with its equilibrium
coherence $q_j = q_{\text{eq}}(\rho_j)$; the coupling magnitudes are
$G_{\text{eff},j} = \varphi^{-3}(1+(\varphi^{6}-1)q_{\text{eq}}(\rho_j))G$
($\approx 3.73\,G$ at the reference density). The canonical velocity dynamics
retain the outward PDE sign, and the internal state relaxes toward
$\mathcal{M}_\varphi$ off the manifold when the local conversion assumptions
hold.

**Consequence**: For long times $t \gg 1/\lambda$ (more precisely
$t \gg \tau_\lambda \sim 1/[\lambda(1-q)(1+\varphi)]$, §4), and while the
well-separated-blob reduction remains valid, each internal state approaches this
outward-sign fixed-point sector under conversion-dominated dynamics. The full
positions, velocities, and masses need not converge. An attractive Newtonian
three-body comparison requires the Hypothesized sign-changing force extension;
its orbital claims are not derived here.

#### 5.2 Component exchange under conversion

The conversion term exchanges the two density components locally while preserving
their sum:

$$
\left.\dot{M}_j\right|_{\mathrm{conv}} = 0,\qquad
\left.\dot{\Pi}_j\right|_{\mathrm{conv}}
= -\lambda(1-q_j)\bigl[(1+\varphi)\Pi_j-\varphi^{-1}M_j\bigr].
$$

The gate factor $(1-q_j)$ approaches one in the dilute limit.
At fixed nonzero density, composition mismatch changes its value only within
the canonical bounds in `foundations/quantum-free-fall-correspondence.md`
§9.1. On the fixed-point line it remains density-dependent;
at the reference density $\rho_j=\varphi$,
$(1-q_{\text{eq}})=\varphi^{-2}/(\varphi^2+\varphi^{-2})
=\varphi^{-2}/3\approx0.127$, while it approaches 1 in the dilute limit.
The conversion bracket $(1+\varphi)\alpha_j-\varphi^{-1}$ restores the
Yang-excess fraction toward $\alpha_j=\varphi^{-3}$; it does not create or
remove total mass. Spatial mass redistribution between blobs is supplied by
advection, diffusion, and the
chemotaxis boundary fluxes, subject to the boundary conditions stated in §2.3.

#### 5.3 Energy extraction via Qi coherence

When $q_j > 0$, the factor $(1+(\varphi^{6}-1)q_j)$ amplifies the magnitude
of the outward-sign force by up to $\varphi^6 \approx 17.94\times$. This can
change trajectories relative to the outward-sign dilute branch. A hierarchical
close-binary or receding-outer-body interpretation requires the Hypothesized
attractive sign-changing extension and is not a canonical result.

#### 5.4 Effective-coupling homogenization in strong Qi

For $\alpha_j > \varphi^{-3}$ and $\xi \gg 1$, the effective coupling
$G_{{\rm eff},j} \propto \xi$ can saturate, making the blob experience a
larger outward force magnitude. In the limit $q_j \to 1$,
$G_{{\rm eff},j} = (1+(\varphi^{6}-1))\,\alpha_j\,G = \varphi^6\,\alpha_j\,G$.
The ratio between two blobs' effective G is:

$$
\frac{G_{{\rm eff},j}}{G_{{\rm eff},i}} \approx
\frac{\alpha_j(1+(\varphi^{6}-1)q_j)}{\alpha_i(1+(\varphi^{6}-1)q_i)}
$$

When both $q_j,q_i\to1$, the ratio is approximately $\alpha_j/\alpha_i$.
Conversion-dominated evolution drives the internal fractions toward
$\varphi^{-3}$, so the coupling ratio approaches one. This is an
internal-state homogenization, not a dynamical $2+1$-body reduction.

---

### 6. Verdict

The canonical Cassi two-fluid velocity-force branch has no closed-form general
solution and retains its outward force sign. At the $\varphi$-fixed point it
has outward-sign, per-blob constant coupling magnitudes
$G_{\text{eff},j}\approx3.73\,G$ (reference density); the dilute magnitude is
$G_{\text{eff}}=\varphi^{-3}G$. Non-integrability and special-orbit statements
belong to the attractive comparison problem, not to the canonical branch.

**Current consequences:**

1. **Mass-dependent effective gravity**: $G_{\text{eff}} = \alpha_j(1+(\varphi^{6}-1)q_j)G$
   is body-dependent off the fixed point. This is a non-Newtonian modification
   that changes the dynamics qualitatively, even if it does not provide integrability.
2. **Dynamic component and boundary-flux evolution**: The Yang-excess fraction
   relaxes through conversion, while blob masses can change through chemotaxis
   boundary fluxes. This adds a dissipative layer not present in Newtonian
   gravity; any stabilization or destabilization of bound orbits is conditional
   on the Hypothesized attractive sign-changing extension.
3. **A conditional $\varphi$ attractor**: In conversion-dominated, well-separated
   blob configurations with the stated boundary assumptions, the internal
   states tend toward $\alpha_j = \varphi^{-3}$ (all blobs at Yang/Yin
   equilibrium), while the canonical velocity force retains its outward sign.
   The coupling magnitudes on that internal-state branch are
   $G_{\text{eff},j} = \varphi^{-3}(1+(\varphi^{6}-1)q_{\text{eq}}(\rho_j))G$
   ($\approx 3.73\,G$ at the reference density), with dilute magnitude
   $G_{\text{eff}} = \varphi^{-3}G$.
4. **Timescale comparison**: The $\varphi$ attractor can motivate searches for
   resonant internal-state trajectories. Comparisons involving
   $\tau_\lambda \sim 1/[\lambda(1-q)(1+\varphi)]$ may be used in a
   Hypothesized attractive orbital extension, but no canonical periodic orbit
   or bound-orbit selection is derived here.

**Bottom line**: The canonical Cassi three-body PDE has no closed-form
general solution or attractive Newtonian orbit branch. It yields a
physically motivated outward-sign point-particle approximation at the
$\varphi$-fixed point and a class of non-Newtonian, mass-evolving dynamics.
Attractive orbital claims remain Hypothesized pending an explicit
sign-changing force law.

---

### 7. Open Questions

1. **Do $\varphi$-resonant periodic internal-state trajectories exist?**
   Configurations with $\alpha_j(t)$ oscillating around $\varphi^{-3}$ at
   commensurate frequencies might form periodic solutions in an explicitly
   defined dynamical extension; the canonical outward-sign branch has no
   derived bound-orbit family.

2. **Can the conversion term be absorbed into a time-dependent mass?** If
   $\dot{M}_j \propto M_j$, the mass evolution is exponential and the
   conditional attractive-orbit problem may reduce to Newtonian form with
   conformally transformed time.

3. **What is the stability boundary of a Lagrange-triangle comparison under
   Qi?** The classical Routh criterion for the attractive L4/L5 problem is
   $$\frac{m_1m_2+m_2m_3+m_3m_1}{(m_1+m_2+m_3)^2}<\frac{1}{27},$$
   with the corresponding restricted-problem form $\mu(1-\mu)<1/27$.
   Qi-dependent corrections and an attractive sign-changing extension would
   require a new stability analysis.

4. **Does the chemotaxis term produce a three-body analog of the Tully-Fisher
   relation?** The extra $\chi$ term is density-gradient dependent and might
   produce a characteristic scaling $v^4 \propto GM$ for bound triples in the
   Hypothesized attractive extension.

5. **Is the $\varphi$-attractor's basin of attraction the whole physically
   accessible phase space?** Or do there exist configurations that avoid
   the attractor indefinitely (e.g., perpetually oscillating $\alpha_j$)?

---

### Appendix A: Derivation of ODE coefficients

For a Gaussian blob of width $\sigma$ centered at $\mathbf{X}$, write
$f_Y$ for the Yang component fraction:

$$E_Y(\mathbf{x}) = \frac{f_Y M}{(2\pi\sigma^2)^{3/2}}
                   \exp\!\Bigl(-\frac{|\mathbf{x}-\mathbf{X}|^2}{2\sigma^2}\Bigr)$$

$$E_I(\mathbf{x}) = \frac{(1-f_Y)M}{(2\pi\sigma^2)^{3/2}}
                   \exp\!\Bigl(-\frac{|\mathbf{x}-\mathbf{X}|^2}{2\sigma^2}\Bigr)$$

Then:

$$\Pi = \int (E_Y - E_I)\,dV = (2f_Y - 1)M$$

$$\rho(\mathbf{X}) = E_Y(\mathbf{X}) + E_I(\mathbf{X})
                    = \frac{M}{(2\pi\sigma^2)^{3/2}}
$$

$$\pi(\mathbf{X}) / \rho(\mathbf{X}) = 2f_Y - 1$$

Thus $\pi/\rho = 2f_Y - 1$ for a Gaussian blob. At the $\varphi$-fixed point
$\pi/\rho = \varphi^{-3} \approx 0.236$, this gives:

$$f_Y = \frac{1+\varphi^{-3}}{2} \approx 0.618,\qquad
  \Pi_j = (2f_Y-1)M_j = \varphi^{-3}M_j \approx 0.236\,M_j$$

**Verification**: $E_Y = \varphi E_I$ implies $\pi = \varphi^{-1}E_I$ and
$\rho = \varphi^2 E_I$, giving $\pi/\rho = \varphi^{-3}$.

#### Conversion component exchange

The conversion terms enter the two component equations with opposite signs, so
their contribution to the total blob mass cancels:

$$
\left.\dot{M}_j\right|_{\mathrm{conv}}
= \int\bigl[-\lambda(1-q_j)(E_Y-\varphi E_I)
+\lambda(1-q_j)(E_Y-\varphi E_I)\bigr]_j\,dV = 0.
$$

For the Yang excess, the same exchange gives

$$
\begin{aligned}
\left.\dot{\Pi}_j\right|_{\mathrm{conv}}
&= -2\lambda(1-q_j)\int(E_Y-\varphi E_I)_j\,dV \\
&= -\lambda(1-q_j)\bigl[(1+\varphi)\Pi_j-\varphi^{-1}M_j\bigr].
\end{aligned}
$$

At the $\varphi$-fixed point ($\Pi_j = \varphi^{-3}M_j$), the bracket is

$$
(1+\varphi)\varphi^{-3} - \varphi^{-1}
= \varphi^{-3} + \varphi^{-2} - \varphi^{-1}
= \varphi^{-1} - \varphi^{-1} = 0,
$$

so the conversion contribution to $\dot{\Pi}_j$ vanishes for any gate
openness. Any remaining $\dot M_j$ is supplied by the chemotaxis boundary
fluxes in §2.3.

---

### Appendix B: Phase space dimension count

| Variable | Symbol | DOF per blob | Total (3 blobs) |
|----------|--------|-------------|-----------------|
| Position | $\mathbf{X}_j$ | 3 | 9 |
| Velocity | $\mathbf{V}_j$ | 3 | 9 |
| Mass | $M_j$ | 1 | 3 |
| Yang excess | $\Pi_j$ | 1 | 3 |
| Local density inputs | $\rho_j,\varepsilon_j$ | profile-closure data | slaved under fixed Gaussian |
| Qi coherence | $q_j$ | 0 independent under closure | slaved from $\rho_j,\varepsilon_j$ |
| **Total** | | **8 under fixed-profile closure** | **24** |

The canonical coherence
$q_j=\rho_j^2/(\rho_j^2+\varphi^{-2}+\varepsilon_j^2)$ requires the local
$\rho_j$ and $\varepsilon_j$ inputs; it is not determined by $\Pi_j/M_j$ alone.
The 24-D count therefore uses the fixed-width Gaussian/profile closure in which
those local inputs are slaved to the retained blob variables. In the general
boundary-flux problem, $M_j$ remains dynamical.

Imposing $\Pi_j=\varphi^{-3}M_j$ alone removes three excess-fraction degrees of
freedom, leaving 21 dimensions. With explicit zero-flux or fixed-mass boundary
conditions that also freeze all $M_j$, the position/velocity sector has 18
dimensions, matching the classical Newtonian three-body phase-space dimension
as a geometric count only. The canonical velocity-force branch retains its
outward sign and is not thereby an attractive Newtonian system.

---

## References

- `foundations/phi_attractor_synthesis.md`—the computational companion: its
  Paths 1–9 (precession formula, Lagrange structure, L4/L5 stability, rotation
  curves) are conditional attractive-orbit comparisons requiring the
  Hypothesized sign-changing force extension; scripts are in
  `experiments/phi_attractor_paths/`
- `foundations/cassi-theory-reference.md` §2, §7.3—canonical two-fluid PDE, Qi gate sign, and the point-particle three-body result
- `foundations/dimensionful-cascade.md`—the cascade ladder setting the softening scale $\sigma$ context
- `consciousness/trauma-as-frozen-gate.md` §10.4—PDE gate verification behind the $(1-q)$ factor used throughout
- `open-questions-cassi-answers.md`—epistemic registry (Q7 measurement, G-series gravity questions)

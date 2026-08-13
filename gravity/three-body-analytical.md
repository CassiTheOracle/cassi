# The Three-Body Problem in Cassi Two-Fluid Gravity

## Status: Derived—July 2026

## Abstract

The Cassi two-fluid PDE with Qi-enhanced gravity reduces, for well-separated
blobs, to point-particle ODEs with body-dependent coupling
$G_{\text{eff},j} = \alpha_j(1+(\varphi^{6}-1)q_j)G$ and dynamically evolving masses. At
the $\varphi$-fixed point $\alpha_j = \varphi^{-3}$ the equations reduce
exactly to Newtonian gravity with $G_{\text{eff}} = \varphi^{-3}G$, so the
three-body problem inherits classical non-integrability; away from the fixed
point the coupling is body-dependent and the masses evolve, a non-Newtonian
dynamics that is even less integrable. The conversion term drives every
configuration toward the fixed point on the timescale
$\tau_\lambda \sim 2/[\lambda(1-q)(1+\varphi)^2]$. In the framework triad,
Yang and Yin are the doublet components and Qi is the flow of coherence between
them and along the string axis between cascade scales—the phase current
$J = \rho\nabla\theta$ (`foundations/qi-flow-double-helix.md`).

> **Division of labor with `foundations/phi_attractor_synthesis.md`:** this document
derives the *reduction theory*—PDE → point-particle ODEs, the φ-fixed point,
integrability assessment, and the effective 2+1 reduction. The companion
`foundations/phi_attractor_synthesis.md` applies the machinery computationally
(Paths 1–9: $R_\infty(d)$, precession, Lagrange points, stability, rotation
curves) with scripts in `experiments/phi_attractor_paths/`. Read this document
first for the formal reduction, then the synthesis doc for the numerical tests.
>
> The conversion terms carry the canonical Qi gate factor $(1-q)$ (PDE-verified
in `consciousness/trauma-as-frozen-gate.md` §10.4), and $q$ is the canonical
coherence $q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$. At the
$\varphi$-fixed point $E_Y = \varphi E_I$ the conversion term vanishes for any
gate openness.

---

### 1. The Full PDE System

The Cassi two-fluid PDE with Qi-enhanced gravity governs three fields on a 3D
domain: the velocity field $\mathbf{u}$, the Yang energy density $E_Y$, and the
Yin energy density $E_I$. In the field-pair form of `foundations/cassi-theory-reference.md` §2.2 the system is:

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
\nabla^2\Phi = -4\pi G\,\rho \quad\text{(Poisson)}
$$

$$
q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \varepsilon^2},
\qquad \varepsilon^2 = (\Psi_0 - \varphi\Psi_1)^2
$$

(the canonical coherence of `foundations/cassi-theory-reference.md` §2.4).
$q \to 1$ at high density near $\varphi$-equilibrium; $q \to 0$ far from it.
At the $\varphi$-fixed point the classical limit $q \to 0$ applies
(theory-reference §2.6), giving $G_{\text{eff}} = \varphi^{-3}G$.

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
| $\alpha_j = \Pi_j/M_j$ | Yang fraction (dimensionless) |

#### 2.1 The key approximation

The force density on the velocity field is the field-level force $\mathbf{F} = \pi\,(1+(\varphi^{6}-1)q)\,\nabla\Phi$,
which is $\Pi$-sign-following: a Yang excess ($\Pi > 0$) is pushed along $+\nabla\Phi$, a Yin excess against it
(measured in the two-strand record—the Yang-excess pair escapes, the Yin-excess pair coalesces;
`hypotheses/two-strand-five-channel-matter-organization.md` §3.3, §3.5).
For a compact blob of size $\sigma$ separated by $r \gg \sigma$ from all other blobs,
the potential varies slowly across the blob, so the field-level force on the $j$-th blob is:

$$
\begin{aligned}
\mathbf{F}_j &\equiv \int \mathbf{F}_j\,dV \\
&= \int \pi_j\,(1+(\varphi^{6}-1)q_j)\,\nabla\Phi\,dV \\
&\approx \alpha_j\,(1+(\varphi^{6}-1)q_j)\,M_j \cdot \nabla\Phi(\mathbf{X}_j) \quad\text{when blob is relaxed}
\end{aligned}
$$

The factor $\alpha_j = \Pi_j/M_j$ extracts—this is the **local Yang fraction** of blob $j$,
which is the average of $\pi/\rho$ over the blob.

#### 2.2 Far-field gravitational potential

From the $N$ point-like sources:

$$
\Phi(\mathbf{x}) = -G\sum_{i=1}^N \frac{M_i}{|\mathbf{x} - \mathbf{X}_i|}
$$

The gradient of $1/|\mathbf{x} - \mathbf{X}_i|$ is $-(\mathbf{x} - \mathbf{X}_i)/|\mathbf{x} - \mathbf{X}_i|^3$, so the potential's own leading minus flips the direction: at $\mathbf{X}_j$ the gradient points **outward** from each source,

$$
\nabla\Phi(\mathbf{X}_j) = +G\sum_{i\neq j} M_i\frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}
$$

The attraction in the equation of motion below comes from the sector's own leading minus (§2.3), not from the gradient.

#### 2.3 Point-particle equations of motion (PDE → ODE)

The point-particle sector adopts the **attractive convention**—the Newtonian $-\nabla\Phi$
form of the force:

$$
\ddot{\mathbf{X}}_j = -\alpha_j\,(1+(\varphi^{6}-1)q_j)\,\nabla\Phi(\mathbf{X}_j)
$$

With the outward gradient of §2.2, $\nabla\Phi(\mathbf{X}_j) = +G\sum_{i\neq j}M_i(\mathbf{X}_j-\mathbf{X}_i)/|\mathbf{X}_j-\mathbf{X}_i|^3$,
the sector's own leading minus inverts it, and the **three-blob ODE system** is:

$$
\boxed{
\ddot{\mathbf{X}}_j = -G\,\alpha_j\,(1+(\varphi^{6}-1)q_j)\,
\sum_{i\neq j} M_i\frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}
}
$$

with each blob's internal dynamics:

$$
\boxed{
\dot{M}_j = \frac{\lambda(1-q_j)}{2}\bigl[(1+\varphi)\Pi_j - \varphi^{-1}M_j\bigr]
           + \chi\int\nabla\cdot(E_I\nabla\Phi)\,dV
           - \chi_Y\int\nabla\cdot(E_Y\nabla\Phi)\,dV
}
$$

$$
\boxed{
\dot{\Pi}_j = -\frac{\lambda(1-q_j)}{2}\bigl[(1+\varphi)\Pi_j - \varphi^{-1}M_j\bigr]
              + \ldots \quad\text{(advection + chemotaxis)}
}
$$

with $q_j$ the canonical coherence $q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$ evaluated in blob $j$ (theory-reference §2.4). At the $\varphi$-fixed point ($E_Y = \varphi E_I$) the conversion bracket vanishes for any $q_j$—the gate does not change the equilibrium.

**The mass and Yang fraction are DYNAMICAL variables**—they evolve via
conversion and chemotaxis, unlike Newtonian gravity where masses are constant.

---

### 3. The $\varphi$-Fixed Point

The critical equilibrium: $\alpha_j = \varphi^{-3}$ for all $j$, with the
classical-limit coherence $q_j \to 0$ (theory-reference §2.6).

#### 3.1 What happens

- The conversion term vanishes: $\lambda(1-q)(E_Y - \varphi E_I) = 0$ (because $E_Y = \varphi E_I$, independent of gate openness)
- The Qi enhancement factor is exactly 1: $1+(\varphi^{6}-1)q = 1$ (classical limit)
- The equation of motion reduces to:

$$
\ddot{\mathbf{X}}_j = -G\,\varphi^{-3}\sum_{i\neq j} M_i
                      \frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}
$$

**This is EXACTLY Newtonian gravity** with a rescaled gravitational constant:

$$
G_{\text{eff}} = \varphi^{-3} G \approx 0.236\,G
$$

#### 3.2 The three-body problem at the $\varphi$-fixed point

The classical Newtonian three-body problem is **not integrable** in general.
The known exceptions are:

| Solution | Condition | Cassi analogue |
|----------|-----------|----------------|
| Lagrange L4/L5 | Any masses | Equil. triangle, stable for $M_1M_2+M_2M_3+M_3M_1 > 0$ |
| Euler collinear | Any masses | Mass-weighted ratio on line segment |
| Figure-8 | Equal masses | Chenciner-Montgomery 2000 |
| Elliptic L4 | Any masses | Triangle with varying side length |

These are individual periodic orbits, not a general solution. The Cassi
framework does **not** add new integration constants at the $\varphi$-fixed point.

#### 3.3 Proof of reduction

At $\alpha_j = \varphi^{-3}$ (classical-limit $q_j \to 0$):

1. **Mass evolution**: $\dot{M}_j = 0$ because $(1+\varphi)\varphi^{-3} - \varphi^{-1} = 0$.
   The gate factor $(1-q_j)$ is finite but the bracket vanishes; the conversion
   term is zero regardless of gate openness. The chemotaxis terms also vanish
   because $\chi\nabla\cdot(E_I\nabla\Phi)$ and
   $\chi_Y\nabla\cdot(E_Y\nabla\Phi)$ integrate to zero when the blob is compact
   and the external potential is harmonic across the blob (which holds at the
   fixed point—the positive and negative flux cancel in the integral).

   > **Proof**: For a compact blob, $\nabla\Phi \approx \mathbf{r}/|\mathbf{r}|^3$
   > and $E_I \approx \text{const} \times \exp(-r^2/2\sigma^2)$. The integral
   > $\int \nabla\cdot(E_I\nabla\Phi)\,dV = \oint E_I\nabla\Phi\cdot d\mathbf{S}$
   > over a surface containing the blob. At the blob boundary,
   > $E_I \approx 0$ (Gaussian tail), so the integral vanishes.

2. **Yang fraction**: $\dot{\Pi}_j = 0$ by the same reasoning.

3. **Momentum**: $G_{\text{eff}} = \varphi^{-3}G$ is constant and universal.

**Therefore the $\varphi$-fixed point is a true fixed point of the Cassi
two-fluid system.** At this point the three-body problem is exactly the
classical Newtonian one.

---

### 4. Does Away-from-Equilibrium Help?

When $\alpha_j \neq \varphi^{-3}$, the conversion term acts as a linear restoring
force:

$$
\dot{\alpha}_j = \frac{\dot{\Pi}_j}{M_j} - \alpha_j\frac{\dot{M}_j}{M_j}
                \approx -\frac{\lambda(1-q_j)}{2}\frac{(1+\varphi)^2}{M_j}(\alpha_j - \varphi^{-3})
$$

plus higher-order corrections from advection and chemotaxis. The system relaxes
to $\alpha_j = \varphi^{-3}$ on the conversion timescale
$\tau_\lambda \sim 2/[\lambda(1-q_j)(1+\varphi)^2]$. Away from equilibrium
$q_j \to 0$ so the gate is open and relaxation is fastest; near equilibrium the
conversion bracket itself vanishes, so the fixed point is reached in either
limit.

**For the three-body problem, this means:**

- If the orbital timescale $T_{\text{orbit}} \gg \tau_\lambda$, the system
  is effectively at the $\varphi$-fixed point → Newtonian (not integrable).
- If $T_{\text{orbit}} \ll \tau_\lambda$, the internal dynamics are frozen
  and each blob has a constant $\alpha_j \neq \varphi^{-3}$, giving a **body-dependent
  effective gravitational constant** $G_{{\rm eff},j} = \alpha_j(1+(\varphi^{6}-1)q_j)\,G$.
  This is now a **non-Newtonian** three-body problem with mass-dependent
  coupling—even less likely to be integrable.
- If $T_{\text{orbit}} \sim \tau_\lambda$, the system has 27+ degrees of
  freedom (positions, velocities, internal states), putting integrability
  further out of reach.

---

### 5. The Cassi Three-Body: What IS Special

Although the general problem is not integrable, the Cassi framework provides
a **geometric principle** that constrain solutions:

#### 5.1 The $\varphi$ attractor

The conversion term $\lambda(1-q)(E_Y - \varphi E_I)$ drives EVERY blob toward
$\alpha_j = \varphi^{-3}$. This is a **universal equilibrium** that does not
depend on mass, position, or velocity. The three-body system in the
Cassi framework has a global attractor manifold:

$$
\mathcal{M}_\varphi = \{(\mathbf{X}_j, \mathbf{V}_j, M_j, \alpha_j)\;|\;
                    \alpha_j = \varphi^{-3} \;\forall j\}
$$

(with classical-limit $q_j \to 0$ on the manifold). On $\mathcal{M}_\varphi$,
exactly Newton. Off $\mathcal{M}_\varphi$, the system relaxes to it.

**Consequence**: For long times $t \gg 1/\lambda$ (more precisely
$t \gg \tau_\lambda \sim 2/[\lambda(1-q)(1+\varphi)^2]$, §4), any three-body
configuration in the Cassi framework approaches the classical Newtonian
three-body problem. The Cassi dynamics are a perturbation that vanishes
exponentially in $t$.

#### 5.2 Mass redistribution via conversion

The conversion term can move mass between blobs:

$$
\dot{M}_j = \frac{\lambda(1-q_j)}{2}\bigl[(1+\varphi)\Pi_j - \varphi^{-1}M_j\bigr]
$$

When $\alpha_j > \varphi^{-3}$ (Yang-rich), $\dot{M}_j > 0$—the blob gains
mass from the ambient field. When $\alpha_j < \varphi^{-3}$ (Yin-rich),
$\dot{M}_j < 0$—it loses mass. Since $E_Y + E_I$ is conserved globally
(conversion just exchanges between them), one blob's gain is another's loss.
The gate factor $(1-q_j)$ stays near 1 (gate open, $q \to 0$ in the classical
limit) throughout the approach to the fixed point; the mass transfer self-damps
because the conversion *bracket* $(1+\varphi)\alpha_j - \varphi^{-1}$ vanishes
at $\alpha_j = \varphi^{-3}$—the same bracket cancellation proved in §3.3.

This mass transfer provides a **dissipative mechanism** that can stabilize
certain configurations (like the Lagrange triangle) against perturbations.

#### 5.3 Energy extraction via Qi coherence

When $q_j > 0$, the factor $(1+(\varphi^{6}-1)q_j)$ amplifies gravity by up to
$\varphi^6 \approx 17.94\times$. This is a significant effect that can drive
behavior not seen in Newtonian gravity—such as the hierarchical M=3,2,1
configuration maintaining a close binary while the outer body slowly recedes.

#### 5.4 Effective 2+1 body reduction for strong Qi

For $\alpha_j > \varphi^{-3}$ and $\xi \gg 1$, the effective coupling
$G_{{\rm eff},j} \propto \xi$ can saturate, making the blob act as if it
has a much stronger gravitational pull. In the limit $q_j \to 1$,
$G_{{\rm eff},j} = (1+(\varphi^{6}-1))\,\alpha_j\,G = \varphi^6\,\alpha_j\,G$.
The ratio between two blobs' effective G is:

$$
\frac{G_{{\rm eff},j}}{G_{{\rm eff},i}} \approx
\frac{\alpha_j(1+(\varphi^{6}-1)q_j)}{\alpha_i(1+(\varphi^{6}-1)q_i)}
$$

When both $q_j, q_i \to 1$, the ratio is approximately $\alpha_j/\alpha_i$.
Since the conversion drives both toward $\varphi^{-3}$, the ratio approaches 1
and the system homogenizes.

---

### 6. Verdict

**The Cassi two-fluid theory does NOT make the three-body problem analytically
integrable.** The system at the $\varphi$-fixed point reduces exactly to the
classical Newtonian three-body problem, which is non-integrable except for
known special solutions.

**What IS new:**

1. **Mass-dependent effective gravity**: $G_{\text{eff}} = \alpha_j(1+(\varphi^{6}-1)q_j)G$
   is body-dependent off the fixed point. This is a non-Newtonian modification
   that changes the dynamics qualitatively, even if it doesn't provide integrability.

2. **Dynamic mass evolution**: Blobs gain and lose mass via conversion and
   chemotaxis. This adds a dissipative layer not present in Newtonian gravity,
   which can stabilize or destabilize orbits.

3. **A global $\varphi$ attractor**: Any three-body configuration in the Cassi
   framework exponentially approaches $\alpha_j = \varphi^{-3}$ (all blobs at
   Yang/Yin equilibrium), at which point the dynamics are exactly Newtonian
   with $G_{\text{eff}} = \varphi^{-3}G$.

4. **A selection principle**: The $\varphi$ attractor PREFERS certain resonant
   configurations over others. Orbits whose timescales are commensurate with
   the conversion timescale $\tau_\lambda \sim 2/[\lambda(1-q)(1+\varphi)^2]$
   have different effective couplings for each blob, potentially creating
   unique periodic orbits not present in Newtonian gravity.

**Bottom line**: The Cassi three-body PDE does NOT yield a closed-form general
solution. It yields a physically motivated approximation (the $\varphi$-fixed
point) and a new class of non-Newtonian, mass-evolving three-body dynamics
that are richer than the classical problem but not simpler.

---

### 7. Open Questions

1. **Do $\varphi$-resonant periodic orbits exist?** Orbits where all three blobs
   have $\alpha_j(t)$ oscillating around $\varphi^{-3}$ at commensurate
   frequencies might form a new family of periodic solutions.

2. **Can the conversion term be absorbed into a time-dependent mass?** If
   $\dot{M}_j \propto M_j$, the mass evolution is exponential and the problem
   may reduce to Newtonian with conformally transformed time.

3. **What is the stability boundary of the Lagrange triangle under Qi?**
   The classical Routh criterion gives stability for $m_1 m_2 + m_2 m_3 +
   m_3 m_1 > 0$ (always). With $\xi q$ corrections, there may be a
   Yang-fraction threshold for instability.

4. **Does the chemotaxis term produce a three-body analog of the Tully-Fisher
   relation?** The extra $\chi$ term is density-gradient dependent and might
   produce a characteristic scaling $v^4 \propto GM$ for bound triples.

5. **Is the $\varphi$-attractor's basin of attraction the whole physically
   accessible phase space?** Or do there exist configurations that avoid
   the attractor indefinitely (e.g., perpetually oscillating $\alpha_j$)?

---

### Appendix A: Derivation of ODE coefficients

For a Gaussian blob of width $\sigma$ centered at $\mathbf{X}$ with
total mass $M$ and Yang fraction $\alpha$:

$$E_Y(\mathbf{x}) = \frac{\alpha M}{(4\pi\sigma^2)^{3/2}}
                   \exp\!\Bigl(-\frac{|\mathbf{x}-\mathbf{X}|^2}{2\sigma^2}\Bigr)$$

$$E_I(\mathbf{x}) = \frac{(1-\alpha)M}{(4\pi\sigma^2)^{3/2}}
                   \exp\!\Bigl(-\frac{|\mathbf{x}-\mathbf{X}|^2}{2\sigma^2}\Bigr)$$

Then:

$$\Pi = \int (E_Y - E_I)\,dV = (2\alpha - 1)M$$

$$\rho(\mathbf{X}) = E_Y(\mathbf{X}) + E_I(\mathbf{X})
                    = \frac{M}{(4\pi\sigma^2)^{3/2}}$$

$$\pi(\mathbf{X}) / \rho(\mathbf{X}) = 2\alpha - 1$$

Thus $\pi/\rho = 2\alpha - 1$ for a Gaussian blob. At the $\varphi$-fixed point
$\pi/\rho = \varphi^{-3} \approx 0.236$, this gives:

$$\alpha = \frac{1+\varphi^{-3}}{2} \approx 0.618,\qquad
  \Pi_j = \alpha M_j \approx 0.618\,M_j$$

**Verification**: $E_Y = \varphi E_I$ ⇒ $\pi = \varphi^{-1}E_I$ and
$\rho = \varphi^2 E_I$, giving $\pi/\rho = \varphi^{-3}$. ✓

#### Conversion mass flow

The conversion term $-\lambda(1-q)(E_Y - \varphi E_I)$ in the PDE gives a net
mass flow into blob $j$:

$$
\begin{aligned}
\dot{M}_j &= \lambda(1-q_j)\int (E_Y - \varphi E_I)_j\,dV \\
&= \frac{\lambda(1-q_j)}{2}\int\bigl[(1+\varphi)\pi - \varphi^{-1}\rho\bigr]_j\,dV \\
&= \frac{\lambda(1-q_j)}{2}\bigl[(1+\varphi)\Pi_j - \varphi^{-1}M_j\bigr]
\end{aligned}
$$

At the $\varphi$-fixed point ($\Pi_j = \varphi^{-3}M_j$):

$$
(1+\varphi)\varphi^{-3} - \varphi^{-1} = \varphi^{-3} + \varphi^{-2} - \varphi^{-1}
                              = \varphi^{-1} - \varphi^{-1} = 0
$$

so $\dot{M}_j = 0$—mass is conserved at the fixed point for any gate
openness, exactly as expected.

---

### Appendix B: Phase space dimension count

| Variable | Symbol | DOF per blob | Total (3 blobs) |
|----------|--------|-------------|-----------------|
| Position | $\mathbf{X}_j$ | 3 | 9 |
| Velocity | $\mathbf{V}_j$ | 3 | 9 |
| Mass | $M_j$ | 1 | 3 |
| Yang excess | $\Pi_j$ | 1 | 3 |
| Qi coherence | $q_j$ | 1 (derived from $\Pi_j/M_j$) | (0, slaved) |
| **Total** | | **8** | **24** |

The 24-D phase space is too large for standard integrability. On the
$\varphi$-fixed-point submanifold ($\Pi_j = \varphi^{-3}M_j$), the dimension
reduces to 18—the classical Newtonian three-body phase space.

---

## References

- `foundations/phi_attractor_synthesis.md`—the computational companion: Paths 1–9 apply this reduction theory numerically (precession formula, Lagrange structure, L4/L5 stability, rotation curves) with scripts in `experiments/phi_attractor_paths/`
- `foundations/cassi-theory-reference.md` §2, §7.3—canonical two-fluid PDE, Qi gate sign, and the point-particle three-body result
- `foundations/dimensionful-cascade.md`—the cascade ladder setting the softening scale $\sigma$ context
- `consciousness/trauma-as-frozen-gate.md` §10.4—PDE gate verification behind the $(1-q)$ factor used throughout
- `open-questions-cassi-answers.md`—epistemic registry (Q7 measurement, G-series gravity questions)

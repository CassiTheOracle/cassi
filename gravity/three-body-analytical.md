# The Three-Body Problem in Cassi Two-Fluid Gravity

## An Analytical Assessment of Integrability

---

### 1. The Full PDE System

The Cassi two-fluid PDE with Qi-enhanced gravity governs three fields on a 3D
domain: the velocity field $\mathbf{u}$, the Yang energy density $E_Y$, and the
Yin energy density $E_I$. From `cassi_qi_gravity.py` the system is:

#### Continuity

$$
\begin{aligned}
\partial_t E_Y &= -\nabla \cdot (\mathbf{u} E_Y) + D\nabla^2 E_Y
                - \lambda(E_Y - \phi E_I)
                - \chi_Y \nabla\cdot(E_Y \nabla\Phi) \\
\partial_t E_I &= -\nabla \cdot (\mathbf{u} E_I) + D\nabla^2 E_I
                + \lambda(E_Y - \phi E_I)
                + \chi \nabla\cdot(E_I \nabla\Phi)
\end{aligned}
$$

#### Momentum

$$
\partial_t \mathbf{u} = -(\mathbf{u}\cdot\nabla)\mathbf{u}
                        + \pi\,(1 + \xi\,q)\,\nabla\Phi
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
q = 1 - \exp\bigl[-\beta\max(\pi/\rho - \phi^{-3},\,0)\bigr]
$$

#### Parameters (all from $\phi$, zero free)

$$
\phi = \frac{1+\sqrt5}{2} \approx 1.618,\quad
\xi = \phi^6 \approx 17.944,\quad
\chi_Y = \chi/\phi
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

The force density on the velocity field is $\mathbf{F} = \pi\,(1+\xi q)\,\nabla\Phi$.
For a compact blob of size $\sigma$ separated by $r \gg \sigma$ from all other blobs,
the potential varies slowly across the blob, so the total force on the $j$-th blob is:

$$
\begin{aligned}
M_j\ddot{\mathbf{X}}_j &\equiv \int \mathbf{F}_j\,dV \\
&= \int \pi_j\,(1+\xi q_j)\,\nabla\Phi\,dV \\
&\approx \alpha_j\,(1+\xi q_j)\,M_j \cdot \nabla\Phi(\mathbf{X}_j) \quad\text{when blob is relaxed}
\end{aligned}
$$

The factor $\alpha_j = \Pi_j/M_j$ extracts — this is the **local Yang fraction** of blob $j$,
which is the average of $\pi/\rho$ over the blob.

#### 2.2 Far-field gravitational potential

From the $N$ point-like sources:

$$
\Phi(\mathbf{x}) = -G\sum_{i=1}^N \frac{M_i}{|\mathbf{x} - \mathbf{X}_i|}
$$

Hence at $\mathbf{X}_j$:

$$
\nabla\Phi(\mathbf{X}_j) = -G\sum_{i\neq j} M_i\frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}
$$

#### 2.3 Point-particle equations of motion (PDE → ODE)

Putting it together, the **three-blob ODE system** is:

$$
\boxed{
\ddot{\mathbf{X}}_j = -G\,\alpha_j\,(1+\xi q_j)\,
\sum_{i\neq j} M_i\frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}
}
$$

with each blob's internal dynamics:

$$
\boxed{
\dot{M}_j = \frac{\lambda}{2}\bigl[(1+\phi)\Pi_j - \phi^{-1}M_j\bigr]
           + \chi\int\nabla\cdot(E_I\nabla\Phi)\,dV
           - \chi_Y\int\nabla\cdot(E_Y\nabla\Phi)\,dV
}
$$

$$
\boxed{
\dot{\Pi}_j = -\frac{\lambda}{2}\bigl[(1+\phi)\Pi_j - \phi^{-1}M_j\bigr]
              + \ldots \quad\text{(advection + chemotaxis)}
}
$$

where $q_j = 1 - \exp[-\beta\max(\alpha_j - \phi^{-3},\,0)]$.

**The mass and Yang fraction are DYNAMICAL variables** — they evolve via
conversion and chemotaxis, unlike Newtonian gravity where masses are constant.

---

### 3. The $\phi$-Fixed Point

The critical equilibrium: $\alpha_j = \phi^{-3}$ for all $j$, so $q_j = 0$.

#### 3.1 What happens

- The conversion term vanishes: $\lambda(E_Y - \phi E_I) = 0$
- The Qi enhancement factor is exactly 1: $1+\xi q = 1$
- The equation of motion reduces to:

$$
\ddot{\mathbf{X}}_j = -G\,\phi^{-3}\sum_{i\neq j} M_i
                      \frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}
$$

**This is EXACTLY Newtonian gravity** with a rescaled gravitational constant:

$$
G_{\text{eff}} = \phi^{-3} G \approx 0.236\,G
$$

#### 3.2 The three-body problem at the $\phi$-fixed point

The classical Newtonian three-body problem is **not integrable** in general.
The known exceptions are:

| Solution | Condition | Cassi analogue |
|----------|-----------|----------------|
| Lagrange L4/L5 | Any masses | Equil. triangle, stable for $M_1M_2+M_2M_3+M_3M_1 > 0$ |
| Euler collinear | Any masses | Mass-weighted ratio on line segment |
| Figure-8 | Equal masses | Chenciner-Montgomery 2000 |
| Elliptic L4 | Any masses | Triangle with varying side length |

These are individual periodic orbits, not a general solution. The Cassi
framework does **not** add new integration constants at the $\phi$-fixed point.

#### 3.3 Proof of reduction

At $\alpha_j = \phi^{-3}$, $q_j = 0$ for all $j$:

1. **Mass evolution**: $\dot{M}_j = 0$ because $(1+\phi)\phi^{-3} - \phi^{-1} = 0$.
   The chemotaxis terms also vanish because $\chi\nabla\cdot(E_I\nabla\Phi)$ and
   $\chi_Y\nabla\cdot(E_Y\nabla\Phi)$ integrate to zero when the blob is compact
   and the external potential is harmonic across the blob (which holds at the
   fixed point — the positive and negative flux cancel in the integral).

   > **Proof**: For a compact blob, $\nabla\Phi \approx \mathbf{r}/|\mathbf{r}|^3$
   > and $E_I \approx \text{const} \times \exp(-r^2/2\sigma^2)$. The integral
   > $\int \nabla\cdot(E_I\nabla\Phi)\,dV = \oint E_I\nabla\Phi\cdot d\mathbf{S}$
   > over a surface containing the blob. At the blob boundary,
   > $E_I \approx 0$ (Gaussian tail), so the integral vanishes.

2. **Yang fraction**: $\dot{\Pi}_j = 0$ by the same reasoning.

3. **Momentum**: $G_{\text{eff}} = \phi^{-3}G$ is constant and universal.

**Therefore the $\phi$-fixed point is a true fixed point of the Cassi
two-fluid system.** At this point the three-body problem is exactly the
classical Newtonian one.

---

### 4. Does Away-from-Equilibrium Help?

When $\alpha_j \neq \phi^{-3}$, the conversion term acts as a linear restoring
force:

$$
\dot{\alpha}_j = \frac{\dot{\Pi}_j}{M_j} - \alpha_j\frac{\dot{M}_j}{M_j}
                \approx -\frac{\lambda}{2}\frac{(1+\phi)^2}{M_j}(\alpha_j - \phi^{-3})
$$

plus higher-order corrections from advection and chemotaxis. The system relaxes
to $\alpha_j = \phi^{-3}$ on the conversion timescale $\tau_\lambda \sim 2/[\lambda(1+\phi)^2]$.

**For the three-body problem, this means:**

- If the orbital timescale $T_{\text{orbit}} \gg \tau_\lambda$, the system
  is effectively at the $\phi$-fixed point → Newtonian (not integrable).
- If $T_{\text{orbit}} \ll \tau_\lambda$, the internal dynamics are frozen
  and each blob has a constant $\alpha_j \neq \phi^{-3}$, giving a **body-dependent
  effective gravitational constant** $G_{{\rm eff},j} = \alpha_j(1+\xi q_j)\,G$.
  This is now a **non-Newtonian** three-body problem with mass-dependent
  coupling — even less likely to be integrable.
- If $T_{\text{orbit}} \sim \tau_\lambda$, the system has 27+ degrees of
  freedom (positions, velocities, internal states), putting integrability
  further out of reach.

---

### 5. The Cassi Three-Body: What IS Special

Although the general problem is not integrable, the Cassi framework provides
a **geometric principle** that constrain solutions:

#### 5.1 The $\phi$ attractor

The conversion term $\lambda(E_Y - \phi E_I)$ drives EVERY blob toward
$\alpha_j = \phi^{-3}$. This is a **universal equilibrium** that does not
depend on mass, position, or velocity. The three-body system in the
Cassi framework has a global attractor manifold:

$$
\mathcal{M}_\phi = \{(\mathbf{X}_j, \mathbf{V}_j, M_j, \alpha_j)\;|\;
                    \alpha_j = \phi^{-3},\; q_j = 0 \;\forall j\}
$$

On $\mathcal{M}_\phi$, exactly Newton. Off $\mathcal{M}_\phi$, the system
relaxes to it.

**Consequence**: For long times $t \gg 1/\lambda$, any three-body configuration
in the Cassi framework approaches the classical Newtonian three-body problem.
The Cassi dynamics are a perturbation that vanishes exponentially in $t$.

#### 5.2 Mass redistribution via conversion

The conversion term can move mass between blobs:

$$
\dot{M}_j = \frac{\lambda}{2}\bigl[(1+\phi)\Pi_j - \phi^{-1}M_j\bigr]
$$

When $\alpha_j > \phi^{-3}$ (Yang-rich), $\dot{M}_j > 0$ — the blob gains
mass from the ambient field. When $\alpha_j < \phi^{-3}$ (Yin-rich),
$\dot{M}_j < 0$ — it loses mass. Since $E_Y + E_I$ is conserved globally
(conversion just exchanges between them), one blob's gain is another's loss.

This mass transfer provides a **dissipative mechanism** that can stabilize
certain configurations (like the Lagrange triangle) against perturbations.

#### 5.3 Energy extraction via Qi coherence

When $q_j > 0$, the factor $(1+\xi q_j)$ amplifies gravity by up to
$1 + \xi \approx 18.9\times$. This is a significant effect that can drive
behavior not seen in Newtonian gravity — such as the hierarchical M=3,2,1
configuration maintaining a close binary while the outer body slowly recedes.

#### 5.4 Effective 2+1 body reduction for strong Qi

For $\alpha_j > \phi^{-3}$ and $\xi \gg 1$, the effective coupling
$G_{{\rm eff},j} \propto \xi$ can saturate, making the blob act as if it
has a much stronger gravitational pull. In the limit $q_j \to 1$,
$G_{{\rm eff},j} = (1+\xi)\,\alpha_j\,G \approx \xi\cdot\alpha_j\cdot G$.
The ratio between two blobs' effective G is:

$$
\frac{G_{{\rm eff},j}}{G_{{\rm eff},i}} \approx
\frac{\alpha_j(1+\xi q_j)}{\alpha_i(1+\xi q_i)}
$$

When both $q_j, q_i \to 1$, the ratio is approximately $\alpha_j/\alpha_i$.
Since the conversion drives both toward $\phi^{-3}$, the ratio approaches 1
and the system homogenizes.

---

### 6. Verdict

**The Cassi two-fluid theory does NOT make the three-body problem analytically
integrable.** The system at the $\phi$-fixed point reduces exactly to the
classical Newtonian three-body problem, which is non-integrable except for
known special solutions.

**What IS new:**

1. **Mass-dependent effective gravity**: $G_{\text{eff}} = \alpha_j(1+\xi q_j)G$
   is body-dependent off the fixed point. This is a non-Newtonian modification
   that changes the dynamics qualitatively, even if it doesn't provide integrability.

2. **Dynamic mass evolution**: Blobs gain and lose mass via conversion and
   chemotaxis. This adds a dissipative layer not present in Newtonian gravity,
   which can stabilize or destabilize orbits.

3. **A global $\phi$ attractor**: Any three-body configuration in the Cassi
   framework exponentially approaches $\alpha_j = \phi^{-3}$ (all blobs at
   Yang/Yin equilibrium), at which point the dynamics are exactly Newtonian
   with $G_{\text{eff}} = \phi^{-3}G$.

4. **A selection principle**: The $\phi$ attractor PREFERS certain resonant
   configurations over others. Orbits whose timescales are commensurate with
   the conversion timescale $1/\lambda$ have different effective couplings for
   each blob, potentially creating unique periodic orbits not present in
   Newtonian gravity.

**Bottom line**: The Cassi three-body PDE does NOT yield a closed-form general
solution. It yields a physically motivated approximation (the $\phi$-fixed
point) and a new class of non-Newtonian, mass-evolving three-body dynamics
that are richer than the classical problem but not simpler.

---

### 7. Open Questions

1. **Do $\phi$-resonant periodic orbits exist?** Orbits where all three blobs
   have $\alpha_j(t)$ oscillating around $\phi^{-3}$ at commensurate
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

5. **Is the $\phi$-attractor's basin of attraction the whole physically
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

Thus $\pi/\rho = 2\alpha - 1$ for a Gaussian blob. At the $\phi$-fixed point
$\pi/\rho = \phi^{-3} \approx 0.236$, we have:

$$\alpha = \frac{1+\phi^{-3}}{2} \approx 0.618,\qquad
  \Pi_j = \alpha M_j \approx 0.618\,M_j$$

**Verification**: $E_Y = \phi E_I$ ⇒ $\pi = \phi^{-1}E_I$ and
$\rho = \phi^2 E_I$, giving $\pi/\rho = \phi^{-3}$. ✓

#### Conversion mass flow

The conversion term $-\lambda(E_Y - \phi E_I)$ in the PDE gives a net mass
flow into blob $j$:

$$
\begin{aligned}
\dot{M}_j &= \lambda\int (E_Y - \phi E_I)_j\,dV \\
&= \frac{\lambda}{2}\int\bigl[(1+\phi)\pi - \phi^{-1}\rho\bigr]_j\,dV \\
&= \frac{\lambda}{2}\bigl[(1+\phi)\Pi_j - \phi^{-1}M_j\bigr]
\end{aligned}
$$

At the $\phi$-fixed point ($\Pi_j = \phi^{-3}M_j$):

$$
(1+\phi)\phi^{-3} - \phi^{-1} = \phi^{-3} + \phi^{-2} - \phi^{-1}
                              = \phi^{-1} - \phi^{-1} = 0
$$

so $\dot{M}_j = 0$ — mass is conserved at the fixed point, as expected.

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
$\phi$-fixed-point submanifold ($\Pi_j = \phi^{-3}M_j$), the dimension
reduces to 18 — the classical Newtonian three-body phase space.

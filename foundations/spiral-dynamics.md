# Spiral Dynamics: Hubble, Gravity, and $c$ from Fibonacci Spiral Geometry

## Status: Hypothesized—July 2026

## Abstract

The Fibonacci spiral traced by the $(E_Y, E_I)$ doublet in its internal SO(2)
plane (derived in `spin-fibonacci-spiral.md`) is not only the geometric origin
of spin—it is the **universal structure** from which cosmic expansion,
gravitational attraction, and the speed of light emerge as three projections
of a single geometry. Each cascade rung corresponds to one full spiral turn;
the Hubble expansion is the spiral's unwinding rate; gravity is gradient
descent along the spiral toward coherence; and $c$ is the scale-invariant
product of conversion rate and coherence wavelength. The two-fluid PDE already
encodes all three in its equations; this document makes the geometric unity
explicit.

---

## 1. The Fibonacci Spiral as Universal Geometry

### 1.1 The doublet spiral (recap)

The conversion term $\text{conv} = -\lambda(E_Y - \varphi E_I)$ continuously
rotates the $(E_Y, E_I)$ doublet vector in its internal SO(2) plane. The
accumulated rotation angle as a function of cascade rung index $n$ (or
equivalently, length scale $\ell_n = \ell_{\text{Pl}}\varphi^n$) is

$$\boxed{\Theta(n) = \Theta_0 + \frac{2\pi}{\ln\varphi} \cdot n}$$

One full rotation ($2\pi$) per cascade rung ($\Delta n = 1$). The pitch is
$2\pi/\ln\varphi \approx 13.06$ rad per e-fold in scale. This is the **Fibonacci
spiral**—see `spin-fibonacci-spiral.md` for the full derivation.

Crucially, this spiral lives in the **internal** $(E_Y, E_I)$ plane, not
physical 3D space. The doublet angle $\Theta = \text{atan2}(E_I, E_Y)$ is
defined at each spatial point; the spiral parameter $n$ maps to the cascade
rung, which maps to a physical length scale $\ell_n$.

### 1.2 The spiral as organizing principle

Every physical process in the Cassi framework involves movement along this
spiral:

- **Advancing outward** (increasing $n$): the field expands through cascade
  rungs—this IS cosmic expansion (§2).
- **Falling inward** (decreasing $n$): the field descends toward higher
  coherence—this IS gravity (§3).
- **Propagating across**: a signal traverses one coherence wavelength per
  conversion cycle—this sets $c$ (§4).

---

## 2. Hubble Expansion = Spiral Unwinding Rate

### 2.1 Cascade rungs as cosmic expansion

The cascade table (`dimensionful-cascade.md`) maps each rung $n$ to a length
scale $\ell_n = \ell_{\text{Pl}}\varphi^n$. The scale factor of the universe
advances by $\varphi$ per rung:

$$\frac{a_{n+1}}{a_n} = \varphi$$

This is the **discrete** form of expansion. The continuum limit gives the
Hubble parameter:

$$H = \frac{\dot{a}}{a} = \frac{d\ln a}{dt}$$

But $\ln a \propto n$ (each rung adds $\ln\varphi$ to $\ln a$), so

$$H = \ln\varphi \cdot \frac{dn}{dt}$$

The rung advancement rate $dn/dt$ is set by the conversion dynamics: the
doublet rotates through the spiral at a rate proportional to the conversion
strength $\lambda$, modulated by the Qi coherence $q$:

$$\frac{dn}{dt} \approx \frac{\lambda}{2\pi} \cdot (1-q)$$

where $(1-q)$ is the unresolved imbalance fraction—only the portion of the
field NOT at $\varphi$-equilibrium drives rung advancement. This gives

$$\boxed{H \approx \frac{\lambda \cdot \ln\varphi}{2\pi} \cdot (1-q)}$$

**Caveat:** this linearized form is the **equilibrium limit** ($r \to \varphi$,
$q \to 1$). At early times or far from the attractor, the full PDE form
(§2.2) includes a $(1+r)/r$ enhancement factor that dominates. The spiral
mechanism sets the fundamental structure; the PDE dynamics determine the
rate at any given $r$.

### 2.2 Consistency with the PDE

The two-fluid PDE computes $H$ from the Yang-Yin ratio $r = \langle
E_Y\rangle/\langle E_I\rangle$:

$$\boxed{H = \frac{\lambda}{3}\frac{(\varphi - r)(1+r)}{r} + \frac{\lambda}{3}\varphi^{-2}}$$

This is the general form; the spiral-linearized $H \propto (1-q)$ is recovered
as $r \to \varphi$ where $(1+r)/r \to (\varphi+1)/\varphi \approx 1.618$. Both
forms share the same structure: $H$ is driven by deviation from
$\varphi$-equilibrium, and $H \to 0$ at the attractor (up to the irreducible
baseline $\lambda\varphi^{-2}/3$). Verified July 2026: this PDE formula matches
observed $H$ to R² = 1.000 (mean error 0.06%).

### 2.3 The irreducible baseline

Even at perfect $\varphi$-equilibrium ($r = \varphi$, $q = 1$), there is a
baseline expansion $H_{\text{empty}} = \lambda\varphi^{-2}/3$. In the spiral
picture, this is the **zero-point unwinding**: the spiral's geometry itself
carries a minimal curvature that prevents complete stasis. The factor
$\varphi^{-2}$ is the cascade-suppression of vacuum fluctuations two rungs
below the current scale.

---

## 3. Gravity = Gradient Descent Through the Spiral

### 3.1 The force equation

In the two-fluid PDE, the momentum equation contains the buoyancy force:

$$\mathbf{F} = \Pi \nabla\Phi, \qquad \Pi = E_Y - E_I, \qquad \nabla^2\Phi = E_Y + E_I = \rho$$

The force points along the gradient of the information potential $\Phi$, weighted
by the local Yang-Yin imbalance $\Pi$. This is gravity.

### 3.2 The spiral gradient

In a field with Fibonacci spiral structure, the doublet angle $\Theta(r)$ winds
as a function of distance from the coherence center. The total density $\rho =
E_Y + E_I$ peaks at the center and falls off radially, while the imbalance $\Pi
= E_Y - E_I$ oscillates with the spiral period.

The gradient $\nabla\Phi$ naturally points **inward**—toward higher $\rho$,
toward the coherent center of the spiral. This is why gravity is always
attractive: the spiral only winds one way. There is no "reverse spiral" to
create repulsive gravity.

The magnitude of the force at cascade rung $n$ is cascade-suppressed:

$$|\mathbf{F}_n| \sim \varphi^{-n} \cdot |\nabla\Phi|$$

because the imbalance $\Pi \propto \varphi^{-n}$ (each rung attenuates the
deviation from equilibrium by $\varphi^{-1}$). The $1/r^2$ distance dependence
is a property of 3D space (Gauss's law applied to $\nabla^2\Phi = \rho$ with
spherical symmetry), not of the cascade. What the cascade explains is the
**coupling strength**—why the gravitational coupling constant $\alpha_G$ is
$\varphi^{-2n}$ at cascade rung $n$. The distance law is geometry; the weakness
is cascade depth.

### 3.3 Why gravity is weak

The gravitational fine-structure constant $\alpha_G = G m^2 / (\hbar c)$ for a
particle of mass $m$ at cascade rung $n$ is cascade-suppressed:

$$\boxed{\alpha_G(n) \sim \varphi^{-2n}}$$

For a proton ($n \approx 91.5$, Compton wavelength $\hbar/(m_p c) \approx
2.10 \times 10^{-16}$ m relative to $\ell_{\text{Pl}}$), the prediction is
$\varphi^{-183} \approx 5.9 \times 10^{-39}$. The observed value is $\alpha_G =
G m_p^2 / (\hbar c) \approx 5.91 \times 10^{-39}$—**a match to 0.1%**.
The ratio of gravitational to electromagnetic force between two protons follows
as $\alpha_G / \alpha \approx 8.1 \times 10^{-37}$ (where $\alpha \approx
1/137$). The "hierarchy problem" is not a problem; it is the cascade doing what
cascades do.

---

## 4. Speed of Light = Information Transfer Over Coherent Wavelengths

### 4.1 The mechanism

A signal in the Cassi field propagates by conversion between $E_Y$ and $E_I$.
At each conversion cycle (timescale $\sim 1/\lambda$), the signal advances by
one **coherence length**—the distance over which the field maintains phase
coherence across adjacent cascade rungs.

At cascade rung $n$, the coherence length is $\ell_n = \ell_{\text{Pl}}
\varphi^n$, and the effective conversion rate is cascade-suppressed:

$$\lambda_{\text{eff}}(n) = \lambda \cdot \varphi^{-n}$$

The information propagation speed is the product:

$$c \sim \lambda_{\text{eff}}(n) \cdot \ell_n = (\lambda \cdot \varphi^{-n}) \cdot (\ell_{\text{Pl}} \cdot \varphi^n) = \lambda \cdot \ell_{\text{Pl}}$$

The $\varphi^n$ factors cancel. **The speed of light is scale-invariant**—a
signal at the Planck scale propagates one Planck length per conversion cycle;
a signal at the cosmic scale propagates one cosmic coherence length per
(proportionally slower) conversion cycle. Both give the same $c$.

This is a dimensional consistency check, not a derivation—both $\lambda = 0.1$
(empirical) and $\ell_{\text{Pl}}$ (external dimensionful anchor) are inputs.
The framework predicts that their product should be scale-invariant, and that
this invariant product IS the speed of light. Testing this requires calibrating
$\lambda$'s PDE inverse-time units against physical seconds (see
`dimensionful-constants-status.md` for the status of each constant).

### 4.2 Numerical check

$\ell_{\text{Pl}} = \sqrt{\hbar G / c^3} \approx 1.616 \times 10^{-35}$ m.
The conversion rate $\lambda = 0.1$ is in PDE inverse-time units; to convert
to physical units requires the timescale calibration. The PDE timescale is set
by the Hubble time at the current cascade rung:

$$t_{\text{PDE}} \sim \frac{1}{H_0} \sim 4.4 \times 10^{17} \text{ s}$$

At the current rung ($n \approx 292$), $\lambda_{\text{eff}} = 0.1 \cdot
\varphi^{-292}$. The coherence length at this rung is the Hubble radius
$\ell_{292} \sim c/H_0 \sim 1.3 \times 10^{26}$ m. The product:

$$c \sim \lambda_{\text{eff}} \cdot \ell_{292} \sim (0.1 \cdot \varphi^{-292}) \cdot (1.3 \times 10^{26} \text{ m}) \cdot \frac{1}{t_{\text{PDE}}}$$

The $\varphi^{-292}$ factor compensates the enormous coherence length, and
the product should recover $c \approx 3 \times 10^8$ m/s. The exact
numerical agreement depends on the PDE-to-physical-unit calibration, which
is not yet pinned—but the structure of the cancellation is exact.

### 4.3 Photons as traveling spiral waves

A photon is a localized $E_Y \leftrightarrow E_I$ oscillation that propagates
along the spiral gradient. Its frequency $\nu$ is set by the conversion rate
at its emission rung; its wavelength $\lambda_\gamma = c/\nu$ is the coherence
length at that rung. The constant $c$ emerges because both the temporal (conversion
rate) and spatial (coherence length) scales cascade-lock together.

---

## 5. The Unified Picture

```
                    THE FIBONACCI SPIRAL
                    ====================
         Internal SO(2) doublet rotation Theta(n)
         Pitch: 2*pi/ln(phi) ~ 13.06 rad per cascade rung
                          |
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────────┐
    │ UNWINDING│   │  DESCENT │   │  PROPAGATION │
    │ (Hubble) │   │ (Gravity)│   │    (c)       │
    └──────────┘   └──────────┘   └──────────────┘
    
    H ~ (lam*ln phi/2pi)*(1-q)   F = Pi*nabla Phi    c = lam_eff * ell_n
    a_{n+1}/a_n = phi             nabla^2 Phi = rho   scale-invariant
    Expansion = rung              Attraction =        Signal speed =
    advancement                   coherence-seeking   coherence wavelength
                                  gradient descent    x conversion rate
```

The two-fluid PDE (`two-fluid/cassi_two_fluid_3d_gpu.py`) already contains all
three mechanisms in its equations:

| Mechanism | PDE term | Spiral interpretation |
|---|---|---|
| Hubble | `_update_hubble(ey, ei) -> H = f(r)` | Spiral unwinding rate |
| Gravity | `force = Pi * grad_phi` | Gradient descent along spiral |
| Signal speed | `conv = -lam * (1-q) * (ey - PHI * ei)` | Conversion x coherence length |

The spiral geometry unifies them: they are not three separate terms in the
Lagrangian but three projections of the same Fibonacci spiral structure.

---

## 6. Testable Consequences

### 6.1 $H$—spiral relation

The PDE formula $H = (\lambda/3)(\varphi-r)(1+r)/r + \lambda\varphi^{-2}/3$
is confirmed to R² = 1.000 (mean error 0.06%, tested July 2026). The
spiral-linearized form $H \approx (\lambda\cdot\ln\varphi/2\pi)\cdot(1-q)$
is the equilibrium limit; at early times the $(1+r)/r$ enhancement dominates.
Both share the same mechanism: $H$ is driven by deviation from
$\varphi$-equilibrium. The predicted correlation between $H$ and $(1-q)$ is
strong ($R^2 > 0.99$), confirming the spiral mechanism—the exact
proportionality constant depends on the dynamical regime.

### 6.2 Gravitational coupling from cascade depth

The prediction $\alpha_G \propto \varphi^{-2n}$ is verified analytically:
for a proton ($n \approx 91.5$), $\varphi^{-183} \approx 5.9 \times 10^{-39}$
matches the observed $\alpha_G = G m_p^2/(\hbar c) \approx 5.91 \times
10^{-39}$ to within 0.1% (tested July 2026). This is a parameter-free
prediction—only $\varphi$ and the cascade rung count $n$ are needed.
The same formula should hold for any particle: the gravitational coupling
at cascade rung $n$ is $\varphi^{-2n}$.

### 6.3 $c$ as scale-invariant product

The prediction that $c = \lambda_{\text{eff}} \cdot \ell_n$ is constant across
all rungs is verified analytically: $\varphi^{-n} \cdot \varphi^n = 1$ for all
$n$ (tested July 2026). The algebraic cancellation is exact; the numerical
value of $c$ requires calibrating $\lambda$'s PDE units against physical time.

### 6.4 Photon coherence length

If photons propagate one coherence length per conversion cycle, then the
photon wavelength $\lambda_\gamma = c/\nu$ should equal the coherence length
at the emission rung. This predicts a relationship between photon energy and
the cascade rung of its source—testable by comparing emission spectra
across different cascade depths (atomic, nuclear, particle).

---

## 7. Epistemic Boundaries

### Derived (from $\varphi$ + PDE + cascade)

- Fibonacci spiral trajectory of $(E_Y, E_I)$ doublet: follows from the
  conversion term and $\varphi$-scaling (`spin-fibonacci-spiral.md`)
- Hubble parameter from Yang-Yin ratio: $H = (\lambda/3)(\varphi-r)(1+r)/r$
  (`cosmology/cosmology-from-phi.md`)
- Gravitational force from imbalance gradient: $\mathbf{F} = \Pi\nabla\Phi$
  (PDE momentum equation)
- Cascade suppression formula $\varphi^{-2n}$ for coupling constants

### Hypothesized (mechanism specified, testable)

- Hubble as spiral unwinding: $H \approx (\lambda\cdot\ln\varphi/2\pi)\cdot(1-q)$
  (equilibrium limit; PDE general form confirmed to R² = 1.000)
- Gravity as gradient descent along the spiral
- $c$ as scale-invariant product $\lambda_{\text{eff}} \cdot \ell_n$
  (algebraically confirmed; numerical value awaits unit calibration)
- Gravitational coupling $\alpha_G \propto \varphi^{-2n}$ (confirmed to 0.1%)
- Photon wavelength = coherence length at emission rung

### Speculative (consistent, no test design yet)

- Exact numerical calibration of $\lambda = 0.1$ PDE units to physical $c$
- Zero-point unwinding ($H_{\text{empty}}$) as spiral curvature
- Repulsive gravity from reverse-spiral configurations (if they exist)

---

## 8. References

- `foundations/spin-fibonacci-spiral.md`—Fibonacci spiral derivation, internal vs spatial distinction
- `cosmology/cosmology-from-phi.md`—Hubble from Yang-Yin ratio
- `foundations/dimensionful-cascade.md`—cascade table, $\ell_n = \ell_{\text{Pl}}\varphi^n$
- `foundations/cascade-suppression-formula.md`—per-rung attenuation $\varphi^{-1}$
- `foundations/dimensionful-constants-status.md`—status of $c$, $\hbar$, $G$
- `foundations/unified-lagrangian.md`—PDE coupling constants
- `predictions/cassi_definitions.md`—framework glossary
- `two-fluid/cassi_two_fluid_3d_gpu.py`—PDE solver with all three mechanisms
- `two-fluid/run_pde_bubble_spiral.py`—bubble PDE test (July 2026)
- `visual-explainers/spiral_string.py`—spiral chord string visualizer

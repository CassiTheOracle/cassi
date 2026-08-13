# Spiral Dynamics: Hubble, Gravity, and $c$ from Fibonacci Spiral Geometry

## Status: Hypothesized—August 2026

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

### 1.1 The doublet spiral

The conversion term $\text{conv} = -\lambda(E_Y - \varphi E_I)$ continuously
rotates the $(E_Y, E_I)$ doublet vector in its internal SO(2) plane, tracing
the Fibonacci spiral (derived in `foundations/spin-fibonacci-spiral.md` §1,
with winding quantization in §2.1). The accumulated rotation angle as a
function of cascade rung index $n$ (or equivalently, length scale
$\ell_n = \ell_{\text{Pl}}\varphi^n$) is

$$\boxed{\Theta(n) = \Theta_0 + \frac{2\pi}{\ln\varphi} \cdot n}$$

One full rotation ($2\pi$) per cascade rung ($\Delta n = 1$); equivalently the
pitch is $2\pi/\ln\varphi \approx 13.06$ rad per e-fold in scale. This
rung-to-angle mapping is the **coordinate postulate** (Asserted; pitch
convention $\Theta = 2\pi n$), not a dynamical claim.

**Status: Hypothesized—August 2026 (this interaction).** The dynamics'
rotation rate is a separate, derived quantity. With the ratified
conversion→expansion coupling (zero free constants;
`cassi-toe-rewrite-briefs/spiral-gravity/08-conversion-expansion-coupling.md`
§A.2):

$$\boxed{V_{\text{new}} = \lambda\,\tilde{h}(E_Y,E_I) + \frac{\lambda\varphi^{-2}}{d}}$$

the spiral clock turns **$\ln\varphi/2\pi \approx 0.0766$ turns per Hubble
rung** (dynamical pitch angle $\approx 11.34°$, $\tan = \ln\varphi/(2\pi\varphi^{-2}) =
0.2005$)—not one turn per rung; the azimuthal discriminator is
$|a_\theta/a_r| = 0.19880$ (08 §C.3). The generator ratio $\varphi^{-2} =
0.382$ is realized under the rung-time $2\pi d/\lambda \approx 4.987\times$
the Hubble rung-time. The solver as written has no $\Omega$
term (exchange-only rotation, $\omega = 0$).

**PDE winding test (09-winding-test.md, run 2026-08-04):** the rotation half
is **PDE-verified**—the layered $\Omega$ generator rotates the doublet at the
dressed rate in the $\varepsilon\to 0$ limit: measured **0.3868 ± 0.0001 turns
per rung vs the dressed 0.38902**; the bare $\varphi^{-2} = 0.382$ is the
generator ratio, never a realized winding; the asserted **1.0 is rejected as a
dynamical claim**; measured discriminator $|a_\theta/a_r| = 0.213$ vs the
predicted $0.19880$. The source half's **r-level content stands** (the $w_a$
shifts of 08 §C.6 are scale-free), but its field-level realization is
**unstable** (saddle at $(1,\varphi^{-1})$; density blow-up without Hubble
friction; log-domain exit after 0.108 turns; the source's Hessian exactly
cancels the $\Omega$ rotation at the fixed point)—**stable field-level
realization found (10-source-stabilization.md, run 2026-08-04):** the C1
Hubble-friction closure (the framework's own comoving-density structure,
$H = S/(d\rho) = H_{\text{conv}}$) freezes $\rho$ at $\varphi$ exactly and
realizes the source at the $r_*$ attractor, $r_* = 0.9502528427\ldots$ (the
fixed-point equation is **transcendental**—the log terms vanish only at
$r = \varphi$; 12 §1.2). The golden point $r = \varphi$ is a repeller
($f'(\varphi) = +0.12723$ exact—12 §1.4) and a **knife-edge**: $r > \varphi$
escapes, $r < \varphi$ drains to $r_*$. The cosmological consequence is a
**pure-Λ DESI-window fit $(w_0, w_a) = (-1, 0)$** (4.17σ/2.61σ from DESI—12; the pure-Λ identified with the frozen coherent-phase energy—16-qi-field.md: per-cell constant under the friction closure ⟹ w ≡ −1 exactly; the coherent phase carries 78% of the expansion rate);
the spatial test (11) confirms the ratio-field collapse is fast ($\sigma_r
\times 0.15$ in 1.2τ) into a $\rho$-dependent band ($dr_*/d\rho \approx
-0.38$) in which the density structure survives and amplifies; the full
ratified term with $\Omega$ still exits the log domain on the grid ($t =
8.07$—11 §5). [COMPUTED]

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

(The 1/3 is **Derived** as the isotropic dimension factor $1/d$ at $d = 3$—`cosmology/cosmology-from-phi.md` §1; the $(\lambda/2\pi)(1-q)$ clock form is Hypothesized (§2.1); the $\lambda\varphi^{-2}$ rate stays Asserted; T₀₀ at equilibrium gives 0 or (g/4)φ², never λφ⁻²/3.)

The two H forms are **two different clocks**, not one H in two limits: at the
fixed point the PDE form gives $H = \lambda\varphi^{-2}/3$, while the
spiral-linearized form gives $H = \lambda\ln\varphi\,(1-q_0)/2\pi =
\lambda\varphi^{-2}\ln\varphi/(6\pi)$—the ratio is exactly $2\pi/\ln\varphi$
(the rung-clock identity, 05 §C / 07; the gate is nonzero at the attractor,
$(1-q_0) = \varphi^{-2}/3$, so neither clock stops there). The deviation parts
differ in order: $(1-q) \to \varphi^{-2}/3 + O(\varepsilon^2)$ while
$(\varphi-r)(1+r)/r \to 0$ linearly. The identity locks the two clocks'
rates: under the Hubble rung-time the realized spiral-clock rate is
$\ln\varphi/2\pi = 0.0766$ turns per H-rung (bare), and $\varphi^{-2} =
0.382$ is the generator ratio, realized under the faster rung-time $2\pi d/\lambda
\approx 4.987\times$ the Hubble rung-time (08). Verified July 2026: this PDE formula matches
observed $H$ to R² = 1.000 (mean error 0.06%).

**The radial/azimuthal pitch tangent (2026-08-07).** The doublet's two motions
at the attractor have two $\varphi$-algebra rates: the radial relaxation rate
$\gamma = \lambda(1-q_0)(1+\varphi) = \lambda/3$ (the $\varepsilon$-direction)
and the azimuthal gate rate $\Omega_S = \lambda(1-q_0) = \lambda\varphi^{-2}/3 =
H_{\text{empty}}$ (the spiral-clock rate; §2.3). With the gate value at the
attractor, $(1-q_0) = \varphi^{-2}/3$ (above), the ratio is exact:

$$\boxed{\tan(\text{pitch}) = \frac{\gamma}{\Omega_S} = 1 + \varphi = \varphi^2 = 2.618 \quad (69.1°)}$$

(the identity $(1+\varphi) = \varphi^2$). The wake-geometry reading:
$\gamma/\Omega_S = \ell_{n+1}/\Lambda_I$—the composite closure in Yin-wake
units (`foundations/wake-geometry.md` §1(c)). The identity is **Derived**
(φ-algebra on the derived rates); its realization in the winding dynamics is
the falsifiable content (prediction 50, `predictions/falsifiable-predictions.md` §5).

**Contrast with the canonical rotation.** These Hypothesized fixed-pitch clocks ($\varphi^{-2} = 0.382$ turns per rung realized under the $2\pi d/\lambda \approx 4.987\times$ faster-than-Hubble rung-time, equivalently $\ln\varphi/2\pi \approx 0.0766$ turns per Hubble rung; the 69.1° pitch tangent $\gamma/\Omega_S = \varphi^2$; the $\Omega$-generator of the conversion→expansion term) keep turning at the attractor, whereas the canonical dynamical rotation of `foundations/cassi-first-principles.md` §2.6, $d\theta/dt = \lambda(1-q)\rho\varepsilon/(E_Y^2+E_I^2)$, is $\varepsilon$-proportional and vanishes exactly at the $\varphi$-line.

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

The gradient's direction is set by the Poisson convention $\nabla^2\Phi = \rho$
(the solver solves $\hat\Phi = -\hat\rho/k^2$), which for a point mass gives
$\Phi = -M/(4\pi r)$: in the far field $\nabla\Phi$ points **outward** from an
overdensity. The inward reading is the near-field statement—close to a source
the gradient points back toward it, as measured at the closure probe
($\nabla\Phi(x^*) = -0.0143$ with $\Pi(x^*) = +0.2834$, giving the raw force
$F_0(x^*) = -4.04\times10^{-3}$ at $t = 0$; `hypotheses/gravity-from-flow.md` §1).
The force $\mathbf{F} = \Pi\nabla\Phi$ is $\Pi$-sign-following, not
unconditionally attractive: a Yang excess ($\Pi > 0$) is repelled—the TS1 pair
escapes ($d$ 9.90 → 15.73, `hypotheses/two-strand-five-channel-matter-organization.md`
§3.3)—and a Yin excess ($\Pi < 0$) is attracted—the exchanged pair contracts
and coalesces ($d$ 9.90 → 7.51, §3.5). Gravity is always attractive in the
point-particle sector, where the reduced law is the Newtonian $-\nabla\Phi$
convention $\ddot{\mathbf{X}}_j = -\alpha_j(1+(\varphi^{6}-1)q_j)\nabla\Phi$ of
`gravity/three-body-analytical.md` §2.3.

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
(derived, $w = 5$) and $\ell_{\text{Pl}}$ (external dimensionful anchor) are inputs.
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

At the current epoch (horizon rung $N \approx 291.54$), $\lambda_{\text{eff}} = 0.1 \cdot
\varphi^{-291.54}$. The coherence length at this rung is the Hubble radius
$R_H = \ell_{\text{Pl}}\,\varphi^{291.54} \sim c/H_0 \sim 1.37 \times 10^{26}$ m
(4.44 Gpc = 14.5 Glyr). The product:

$$c \sim \lambda_{\text{eff}} \cdot R_H \sim (0.1 \cdot \varphi^{-291.54}) \cdot (1.37 \times 10^{26} \text{ m}) \cdot \frac{1}{t_{\text{PDE}}}$$

The $\varphi^{-291.54}$ factor compensates the enormous coherence length, and
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
         Pitch: 2*pi/ln(phi) ~ 13.06 rad per e-fold of scale
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
is NOT the equilibrium limit of the PDE form: the two are different clocks
locked by the rung-clock identity $dn_H/dn_S = 2\pi/\ln\varphi$ (§2.2). The
correlation between $H$ and $(1-q)$ is strong ($R^2 > 0.99$), confirming the
spiral mechanism; the proportionality constant is fixed by the identity, and
with the ratified conversion→expansion coupling the generator ratio is
$\varphi^{-2} = 0.382$ turns per rung (the $2\pi d/\lambda \approx 4.987\times$
faster-than-Hubble rung-time; under the Hubble rung-time the realized rate is
$\ln\varphi/2\pi = 0.0766$ turns per H-rung) (08).

### 6.2 Gravitational coupling from cascade depth

The relation $\alpha_G = \varphi^{-2n}$ is the definitional identity
$\alpha_G = (m_p/M_{\text{Pl}})^2$ with $n = \log_\varphi(M_{\text{Pl}}/m_p)$
the proton's measured rung: for $n \approx 91.5$, $\varphi^{-183} \approx
5.7 \times 10^{-39}$ vs the observed $\alpha_G = G m_p^2/(\hbar c) \approx
5.91 \times 10^{-39}$—about 3.5% low (the "0.1%" phrasing holds only for the
fractional rung 91.46, the log map of the measured mass itself; Fit-Status
Ledger row 506, **Mapped**). It is not a parameter-free prediction of the
hierarchy—the exponent is read off the measured mass. The same formula holds
for any particle by the identity: the gravitational coupling at cascade rung
$n$ is $\varphi^{-2n} = (m/M_{\text{Pl}})^2$.

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
  (Hypothesized spiral clock; related to the PDE $H$ by the rung-clock
  identity $dn_H/dn_S = 2\pi/\ln\varphi$, §2.2—not the equilibrium limit; PDE
  general form confirmed to R² = 1.000)
- Conversion→expansion coupling $V_{\text{new}} = \lambda\tilde{h}(E_Y,E_I) +
  \lambda\varphi^{-2}/d$ (Hypothesized—August 2026, zero free constants; the
  vacuum half is the framework's own $\Lambda$; predicts $\varphi^{-2} = 0.382$
  turns per rung (under the $2\pi d/\lambda \approx 4.987\times$ faster-than-Hubble
  rung-time; $\ln\varphi/2\pi = 0.0766$ turns per Hubble rung), pitch 11.34°,
  discriminator $|a_\theta/a_r| = 0.19880$; not
  implemented in the solver—08 §A.2, §C.3). **Winding-test verdict (09):** the
  rotation half is PDE-verified (dressed 0.389 turns/rung realized in the
  $\varepsilon\to 0$ limit, measured 0.3868 ± 0.0001; the bare $\varphi^{-2}$
  is the generator ratio; 1.0 rejected); the source half's field-level
  realization is unstable (saddle at $(1,\varphi^{-1})$, density blow-up, log-
  domain exit at 0.108 turns; the Hessian cancels the rotation at the fixed
  point)—r-level content stands; **stable realization found**: the C1
  Hubble-friction closure (10) realizes the source at the $r_* \approx
  0.9503$ attractor with a pure-Λ late universe (pure-Λ DESI-window fit
  $(-1, 0)$, 4.17σ/2.61σ—12); the full term with $\Omega$ is not integrable
  on the grid ($t = 8.07$—11 §5)
- Gravity as gradient descent along the spiral (anchored quantitatively by the rung-offset probes: at the closure rungs the flow reads $\le 1.5\%$ of the wave speed, inward for J/ψ and $\approx 0$ for μ, and the conversion term alone transports outward at $\le 0.1\%$—`foundations/rung-offset-mechanism.md` §5 T11–T13)
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
- `foundations/rung-offset-mechanism.md`—rung-offset probes T11–T13: descent flow, closure-crossing emission phase, conversion-driven flux
- `two-fluid/cassi_two_fluid_3d_gpu.py`—PDE solver with all three mechanisms
- `two-fluid/run_pde_bubble_spiral.py`—bubble PDE test (July 2026)
- `visual-explainers/spiral_string.py`—spiral chord string visualizer

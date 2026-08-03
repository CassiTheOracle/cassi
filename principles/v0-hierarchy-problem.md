# v₀/M_Pl: The Hierarchy Problem in φ-Clothing

## Status: Derived (step count N = log_φ(M_Pl/v₀) ≈ 79.7, per registry Q1); 5.3% residual open—August 2026

## The Physical Interactions at Play

---

## 1. The Question

The Cassi framework derives the electroweak scale through the cascade step
count $N = \log_\varphi(M_{\rm Pl}/v_0) \approx 79.7$ (registry Q1):
$v_0/M_{\rm Pl} \approx \varphi^{-80}$, within $5.3\%$ of the nearest integer
$\varphi$-power. **What is open?** The framework does not yet compute the
$5.3\%$ correction itself—the residual between $v_0/M_{\rm Pl}$ and the
nearest integer power.

What physics is at play, and what is needed to compute the correction from first principles?

---

## 2. What Determines $v_0$

The Standard Model Higgs potential:

$$V = \frac{\mu^2}{2}|\Psi|^2 + \frac{g}{4}|\Psi|^4$$

At the minimum, $v_0^2 = -\mu^2/g$. The Cassi two-field extension adds a
$\varphi$-attractor term:

$$V_{\text{Cassi}} = \frac{\mu^2}{2}|\Psi|^2 + \frac{g}{4}|\Psi|^4
                    + \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2$$

At the equilibrium point $\Psi_0^2 = \varphi\Psi_1^2$:

$$\frac{\partial V}{\partial u} = \frac{\mu^2}{2} + \frac{g}{2}(u+v) = 0
\;\Rightarrow\; v_0^2 = -\mu^2/g$$

**The equilibrium $v_0$ is independent of $\lambda$.** The $\varphi$-attractor
term contributes to fluctuations around equilibrium, not to the VEV itself.

This means: $v_0$ is set by $\mu^2$ and $g$, both of which are SM parameters
not determined by $\varphi$. The Cassi framework derives the ratio
$v_0/M_{\rm Pl}$ as the cascade step count $N = \log_\varphi(M_{\rm Pl}/v_0)
\approx 79.7$ (registry Q1)—the electroweak scale sits at rung 80—but it
does not derive the exact VEV: the $5.3\%$ residual between $v_0/M_{\rm Pl}$
and the nearest integer $\varphi$-power is open.

---

## 3. What Determines the 5.3% Correction

The correction $\delta \equiv v_0/v_0^{(\varphi^{-80})} - 1 = 5.6\%$ has
**four potential physical sources**, none of which is computed in the Cassi
framework:

### 3.1 RGE running of $v_0$

The Standard Model RGE for $v_0$:

$$16\pi^2 \frac{d v_0^2}{d \ln\mu} = v_0^2 \left[
    -6 y_t^2 + \frac{9}{2} g^2 + \frac{3}{2} g'^2 + 6 \lambda
    \right]$$

The dominant terms are $-6 y_t^2 + \frac{9}{2} g^2$. At $m_t$:
$y_t \approx 1$, $g \approx 0.65$, so the bracket is $\approx -6 + 1.9 = -4.1$.
The sign is **negative**: $v_0^2$ *decreases* with energy.

But this means $v_0$ at low energy is *larger* than $v_0$ at high energy by
the running. The SM Higgs RGE *increases* $v_0$ from the GUT scale
to the EW scale. This is the *opposite* sign from the observed $5.3\%$
correction (which says $v_0$ is larger than the $\varphi^{-80}$ baseline).

The "$\varphi^{-80}$ baseline" is $v_0/M_{\rm Pl} = 1.91 \times 10^{-17}$.
The observed is $v_0/M_{\rm Pl} = 2.02 \times 10^{-17}$. So $v_0$ is *larger* than
the baseline by $5.6\%$.

The SM RGE would give $v_0(M_{\rm GUT}) > v_0(m_t)$ (since $v_0$ increases as
energy decreases). So if $\varphi^{-80}$ is supposed to be the *GUT-scale*
value, then the SM RGE would shift it *down* going to low energy, making
the low-energy value *smaller* than $\varphi^{-80}$. This is the wrong sign
for the $5.6\%$ correction.

Either the $\varphi^{-80}$ baseline is the *low-energy* value, or the RGE shift
has the wrong sign for the Cassi framework.

### 3.2 Threshold corrections at the matching scale

If the SM is matched to the Cassi SU(2) gauge structure at $M_{\rm match}$,
the heavy particles at that scale contribute finite shifts to the matching
conditions:

$$v_0(m_t) = v_0(M_{\rm match}) \cdot \left(1 + \sum_i c_i \frac{M_i^2}{M_{\rm match}^2}\right)$$

For $M_i \sim M_{\rm match}$ (typical GUT-scale particles), the corrections
are $\mathcal{O}(1)$ and shift $v_0$ by a few percent. **This is the
plausible source of the $5.3\%$ correction**—but it has not been computed
in the Cassi framework.

### 3.3 The $\varphi^{-80}$ value is approximate

The actual exponent giving $v_0/M_{\rm Pl}$ exactly is $79.89$—not an
integer. The "$\varphi^{-80}$" is the *nearest integer power*. If the
$\varphi$-attractor is exact (no $\lambda$ correction), the framework would
predict $v_0/M_{\rm Pl} = \varphi^{-80}$ to within $0.13\%$. The $5.3\%$
is the *deviation* from this nearest power, set by the underlying dynamics.

The "underlying dynamics" might include:
- A $\varphi$-power from a different counting (e.g., $\varphi^{-79} \cdot 1.07$)
- A product of $\varphi$-powers and SM coupling ratios
- Some other effect not yet identified

### 3.4 The Bohm quantum potential contributes

The Cassi Lagrangian has a Bohm quantum potential:
$\mathcal{L}_{\rm QP} = -(\hbar^2/2m^2)(\nabla^2 M^\beta / M^\beta)\Psi$.

This term shifts the equilibrium VEV. The shift is of order
$\hbar^2 \Lambda^2 / (m^2 v_0^2)$ where $\Lambda$ is the UV cutoff. With
$\Lambda = M_{\rm Pl}$ and $m = M_{\rm Pl}$: shift $\sim 1$. With
$\Lambda = M_{\rm Pl}$ and $m = v_0$: shift $\sim (v_0/M_{\rm Pl})^2 = 10^{-34}$.
Negligible. So the Bohm potential doesn't give a $5\%$ correction.

---

## 4. Computing the Correction: What Is Required

Computing the $5.3\%$ correction from first principles requires:

1. **The exact $\varphi$-attractor value, not the integer approximation.**
   The step count $N = \log_\varphi(M_{\rm Pl}/v_0) \approx 79.7$ is derived
   (registry Q1), fixing $v_0/M_{\rm Pl}$ to rung 80. The framework's
   $\varphi$-attractor additionally gives a specific value on that rung in
   the absence of corrections; it should be computed rather than approximated
   by the nearest $\varphi$-power, and the $5.3\%$ residual is the gap to
   close.

2. **The RGE for $v_0$ in the Cassi SU(2) framework.** The SM RGE is
   known, but the Cassi framework has additional fields and couplings.
   The full RGE for $v_0$ requires knowing the complete particle content
   and the Yukawa/higgs/quartic structure.

3. **Threshold corrections at the matching scale.** The matching between
   the Cassi $\varphi$-attractor and the SM at $M_{\rm match}$ generates
   finite shifts. These depend on the heavy particle content at the
   matching scale, which is not specified.

None of these is computed in the Cassi framework.

---

## 5. Assessment

The $5.3\%$ correction in $v_0/M_{\rm Pl}$ is **the framework hierarchy problem
in disguise.** The cascade step count $N = \log_\varphi(M_{\rm Pl}/v_0)
\approx 79.7$ is derived (registry Q1), but the $5.3\%$ residual that the
nearest integer power $\varphi^{-80}$ leaves open is not yet computed.

The de-resonance principle (§3 in `principles/de-resonance-principle.md`)
labels the correction as **Hypothesized**: the $g/\lambda$-mixing candidate is
excluded ($v_0$ is $\lambda$-independent at equilibrium), and the mechanism
remains unidentified.

The framework's claim is:
- $\varphi$-powers set the *leading-order baseline* for all couplings and scales.
- Subleading corrections come from dynamics, not from $\varphi$.
- For $v_0/M_{\rm Pl}$, the correction is small ($5.3\%$), but the dynamics
  responsible for it have not been identified.

This is a **weaker** claim than "every quantity is exactly a $\varphi$-power,"
and a **stronger** claim than "we have a thousand free parameters."

---

## 6. What Could Change This

The $5.3\%$ correction would become *computed* by:

1. Deriving the exact $\varphi$-attractor value of $v_0/M_{\rm Pl}$ (approximated
   by the nearest integer $\varphi$-power).
2. Computing the RGE for $v_0$ in the Cassi SU(2) framework.
3. Calculating the threshold corrections at the matching scale.

Any one of these would close the $5.3\%$ residual. Until then, it remains
the framework's open gap.

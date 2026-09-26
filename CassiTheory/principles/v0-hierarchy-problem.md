# v₀/M_Pl: The Hierarchy Problem in φ-Clothing

## Status: Mapped (raw measured ratio $N_{\rm raw}=\log_\varphi(M_{\rm Pl}/v_0)\approx79.89$; gap-adjusted cascade placement $N_g=\log_\varphi(gM_{\rm Pl}/v_0)\approx79.7$ with $g=1-\varphi^{-5}$; the nearest-integer residual remains open)—August 2026

## Abstract

The measured Planck-to-electroweak ratio places $v_0$ near cascade rung 80, but the residual to an integer $\varphi$-power remains unresolved. The raw ratio gives $N_{\rm raw}\approx79.89$, while the gap-adjusted cascade convention gives $N_g\approx79.7$. The electroweak VEV is set by the Standard Model parameters $\mu^2$ and $g$; the $\varphi$-attractor term affects fluctuations around that equilibrium. A Cassi correction requires the full SU(2) renormalization-group flow and threshold matching at the relevant scale.

---

## 1. The Question

The raw measured ratio is
$N_{\rm raw}=\log_\varphi(M_{\rm Pl}/v_0)\approx79.89$ using
$M_{\rm Pl}=1.22\times10^{19}\,\mathrm{GeV}$ and $v_0=246\,\mathrm{GeV}$.
The gap-adjusted cascade convention in
`foundations/dimensionful-cascade.md` §2.1 is a separate placement,
$N_g=\log_\varphi(gM_{\rm Pl}/v_0)\approx79.7$, with
$g=1-\varphi^{-5}$. Both values locate the electroweak scale near rung 80;
the framework does not compute the residual to the nearest integer
$\varphi$-power.

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
not determined by $\varphi$. The raw ratio is
$N_{\rm raw}=\log_\varphi(M_{\rm Pl}/v_0)\approx79.89$. The gap-adjusted
cascade convention instead uses
$N_g=\log_\varphi(gM_{\rm Pl}/v_0)\approx79.7$ (registry Q1 and
`foundations/dimensionful-cascade.md` §2.1), with
$g=1-\varphi^{-5}$. The two conventions should not be conflated; the
electroweak scale remains near rung 80, and the nearest-integer residual is
open.

---

## 3. The Raw Nearest-Integer Residual

Using the displayed raw anchors, the correction
$\delta_{\rm raw}\equiv v_0/v_0^{(\varphi^{-80})}-1$ is approximately
$5.6\%$. The catalog's rounded $5.3\%$ entry uses its declared rounded
ratio. Both describe the open nearest-integer comparison; neither is a
computed Cassi correction. Four potential physical sources remain
uncomputed:

### 3.1 RGE running of $v_0$

The Standard Model RGE for $v_0$:

$$16\pi^2 \frac{d v_0^2}{d \ln\mu} = v_0^2 \left[
    -6 y_t^2 + \frac{9}{2} g^2 + \frac{3}{2} g'^2 + 6 \lambda
    \right]$$

The dominant terms are $-6 y_t^2 + \frac{9}{2} g^2$. At $m_t$:
$y_t \approx 1$, $g \approx 0.65$, so the bracket is $\approx -6 + 1.9 = -4.1$.
The sign is **negative**: $v_0^2$ decreases with energy. The corresponding
low- versus high-energy interpretation must be specified before assigning
the raw $5.6\%$ residual to SM running; the Cassi framework has not supplied
that matching calculation.

The displayed raw baseline is $v_0/M_{\rm Pl}=1.91\times10^{-17}$ and the
rounded observed ratio is $2.02\times10^{-17}$, giving the raw comparison
$\delta_{\rm raw}\approx5.6\%$. The SM RGE gives
$v_0(M_{\rm GUT})>v_0(m_t)$ under the sign convention used here. If
$\varphi^{-80}$ is assigned to the GUT-scale value, the low-energy shift
requires an explicit matching calculation; its sign relative to the raw
residual remains unresolved.

### 3.2 Threshold corrections at the matching scale

If the SM is matched to the Cassi SU(2) gauge structure at $M_{\rm match}$,
the heavy particles at that scale contribute finite shifts to the matching
conditions:

$$v_0(m_t) = v_0(M_{\rm match}) \cdot \left(1 + \sum_i c_i \frac{M_i^2}{M_{\rm match}^2}\right)$$

For $M_i\sim M_{\rm match}$ (typical GUT-scale particles), the corrections
can shift $v_0$ by a few percent. This is a candidate source of the raw
$5.6\%$ residual, but it has not been computed in the Cassi framework.

### 3.3 The $\varphi^{-80}$ value is approximate

The actual raw exponent giving $v_0/M_{\rm Pl}$ exactly is
$N_{\rm raw}\approx79.89$, not an integer. The $\varphi^{-80}$ value is the
nearest integer power. The gap-adjusted convention has
$N_g\approx79.7$; it is a separate model placement rather than a second
measurement of the ratio. The residual to either convention remains an open
matching problem.

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
Negligible at this estimate, so the Bohm potential does not supply the raw
$5.6\%$ residual.

---

## 4. Computing the Correction: What Is Required

Resolving the nearest-integer residual requires:

1. **The exact $\varphi$-attractor value, not the integer approximation.**
   The raw step count is $N_{\rm raw}=\log_\varphi(M_{\rm Pl}/v_0)
   \approx79.89$; the gap-adjusted cascade placement is
   $N_g=\log_\varphi(gM_{\rm Pl}/v_0)\approx79.7$ (registry Q1).
   The framework must specify which placement enters the attractor and
   compute its value rather than treating either approximation as a derived
   correction.

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

The hierarchy comparison is Mapped: the measured electroweak and Planck
anchors locate the scale near rung 80, while the residual to a selected
$\varphi$-power remains uncomputed. The raw nearest-integer comparison is
approximately $5.6\%$; the catalog's rounded entry is $5.3\%$. The
gap-adjusted placement $N_g\approx79.7$ is a separate cascade convention.

The de-resonance principle (§3 in `principles/de-resonance-principle.md`)
labels the correction mechanism as **Hypothesized**. The $g/\lambda$-mixing
candidate is excluded by the equilibrium relation, which leaves $v_0$
$\lambda$-independent; the remaining mechanism is unidentified.

The current framework states that $\varphi$-powers provide leading-order
baselines for selected couplings and scales, with subleading corrections
supplied by dynamics. For $v_0/M_{\rm Pl}$, the responsible dynamics have not
been computed.

## 6. What Could Change This

The residual would become **Derived** after:

1. specifying and deriving the exact $\varphi$-attractor value of
   $v_0/M_{\rm Pl}$;
2. computing the RGE for $v_0$ in the Cassi SU(2) framework; and
3. calculating threshold corrections at the matching scale.

Until those calculations are available, the mechanism remains an open
framework question.

## References

- `foundations/dimensionful-cascade.md` §2.1—dimensionful cascade placement and the gap-adjusted electroweak rung.
- `principles/de-resonance-principle.md` §3—the $\varphi$-power baseline and correction-mechanism scope.
- `open-questions-cassi-answers.md`—Q1 (the electroweak hierarchy and nearest-integer residual).
- `standard-model/sm-radiative-corrections.md` §§2–3—running-coupling and matching context.

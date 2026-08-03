# Metabolic Scaling and Allometry

## Status: Speculative (derivation not closed)—July 2026

## Abstract

Metabolic rate scales with body mass as $B = B_0 \cdot M^{3/4}$ (Kleiber's law)
across 21 orders of magnitude. West, Brown, and Enquist derived the $3/4$
exponent from space-filling, area-preserving, impedance-minimizing resource
networks—a derivation that does not involve $\varphi$. This document examines
whether the Cassi framework can supply the missing first-principles origin,
making the optimal branching ratio and the network's fractal dimension
$\varphi$-determined. The connection $\varphi^2 \approx 2.618 \to 3/4$ is not
mathematically rigorous: it is a prompt for future work, not a claim at the
framework's usual epistemic standard. The $\varphi$-derivation of Kleiber's
exponent is an open problem, not a solved one; metabolic scaling remains a
Speculative application.

---

## 1. Kleiber's Law

Metabolic rate $B$ scales with body mass $M$ across an enormous range of
organisms—from bacteria to blue whales—as:
$$B = B_0 \cdot M^{3/4}$$

This $3/4$ exponent (Kleiber's law) has been a puzzle for nearly a century.
West, Brown, and Enquist (1997) derived it from fractal resource distribution
networks: if the network is space-filling, area-preserving, and minimizes energy
dissipation, the scaling exponent is $3/4 = 1 - 1/(D+1)$ where $D = 3$ is the
embedding dimension. More generally, $B \propto M^{(D+1)/(D+2)}$, which gives
$4/5$ in 2D and $3/4$ in 3D.

The key assumption is that the terminal branches of the resource network
(capillaries in animals, leaf petioles in plants) are size-invariant—they have
the same radius and length regardless of organism size. This sets the network's
fractal structure but does not explain *why* the specific fractal dimension
emerges.

## 2. The $\varphi$ Connection (Tentative)

The resource distribution network in organisms is a branching tree. The optimal
branching ratio—the factor by which a parent vessel's cross-sectional area
exceeds the sum of its daughters' areas—is determined by the impedance
minimization problem. For laminar flow (Poiseuille's law), the impedance of a
vessel scales as $r^{-4}$ (radius to the fourth power). Minimizing total
impedance subject to a fixed total volume of conduit material yields the optimal
branching ratio.

In the Cassi framework, optimization problems in hierarchical systems naturally
approach $\varphi$-power solutions because $\varphi$ is the de-resonance
attractor—configurations at $\varphi$-ratios are maximally stable against
perturbation. The fractal dimension of the resource network would then be:
$$D_f = \frac{\ln N_{\text{branches}}}{\ln \varphi}$$

where $N_{\text{branches}}$ is the number of daughter branches per parent
branch. For $N_{\text{branches}} = 2$ (binary branching): $D_f = \ln 2 /
\ln\varphi \approx 1.44$. For $N_{\text{branches}} = 3$: $D_f = \ln 3 /
\ln\varphi \approx 2.29$.

The metabolic scaling exponent in $D=3$ embedding space is:
$$\alpha = \frac{D}{D_f + 1}$$

For $D_f = 1.44$: $\alpha = 3 / 2.44 \approx 1.23$—wrong (too large). For
$D_f = 2.29$: $\alpha = 3 / 3.29 \approx 0.91$—wrong (too large, should be
0.75).

**This does not close.** The WBE derivation gives $\alpha = 3/4$ from
$D_f = 3$ (the network fills 3D space), which comes from the area-preserving
branching assumption, not from $\varphi$. There is no clean path from $\varphi$
to the $3/4$ exponent—the numbers are nearby ($\varphi^2 \approx 2.618$ and
$3/4 = 0.75$; $1/\varphi^2 \approx 0.382$ and $3/4 - 1 = -0.25$) but the
derivation does not close mathematically.

## 3. What Cassi *Could* Contribute (If the Derivation Closed)

If the $\varphi$-derivation of the metabolic exponent were to close, Cassi would
predict:

1. **Universality of $3/4$:** The exponent is exactly $3/4$, not an empirical
   fit, because it follows from $\varphi$-determined fractal geometry. Any
   systematic deviation (e.g., $2/3$ scaling in some taxa) would falsify.

2. **$\varphi$-periodic allometric residuals:** After subtracting the $3/4$
   scaling, the residuals in $\ln B$ vs. $\ln M$ should show log-periodic
   modulation at period $\ln\varphi$—distinguishable from random taxonomic
   scatter.

3. **Branching ratio prediction:** The optimal number of daughter branches in
   biological resource networks should be a Fibonacci number (2, 3, 5, 8, ...)
   because only Fibonacci branching ratios preserve $\varphi$-resonance through
   multiple levels. Observed: arterial branching is predominantly binary (2) or
   trifurcating (3); bronchial branching is predominantly binary (2). These are
   Fibonacci numbers—but also the most common branching ratios expected from
   any space-filling optimization.

4. **Heart rate / respiratory rate scaling:** The ratio of heart rate to
   respiratory rate should be approximately $\varphi^3 \approx 4.24$ (mammals
   average ~4:1). The ratio of metabolic rate to heart rate should scale
   as $\varphi$-powers across species.

## 4. Why This Remains Speculative

Metabolic scaling does not currently admit a $\varphi$-derivation at the
framework's quality bar:

- The $3/4$ exponent is already derived from geometric constraints (space-filling,
  area-preserving, impedance-minimizing networks) without $\varphi$. The Cassi
  contribution would need to derive one of these constraints *from* $\varphi$,
  rather than merely noting that $\varphi$ appears nearby in the arithmetic.

- The connection $\varphi^2 \approx 2.618 \to 3/4 = 0.75$ via
  $1/(\varphi^2 + 1) \approx 0.276$ (not 0.75) or $\varphi^2/(\varphi^2+1)
  \approx 0.724$ (close to but not equal to 3/4 = 0.750) is suggestive but not
  exact. A $\sim$4% gap in the exponent would produce systematic errors in
  predicted metabolic rates across the 21 orders of magnitude in body mass.

- The fractal dimension of biological networks is set by the embedding space
  dimension and the optimization criterion, not by $\varphi$. Unless Cassi can
  derive *why* the network must be space-filling (and why it must fill exactly 3
  spatial dimensions, which it already does from the dimension derivation in
  `foundations/why-three-dimensions.md`), the connection is correlational rather
  than causal.

## 5. Path to Closing

To upgrade this from Speculative to Hypothesized, the following would need to be
derived:

1. **The cascade determines the optimal branching ratio.** Show that impedance
   minimization on a $\varphi$-structured cascade ladder yields area-preserving
   branching ($r_{\text{parent}}^2 = \sum r_{\text{daughter}}^2$) as the
   de-resonance attractor—not as an empirical assumption.

2. **The embedding dimension $D=3$ follows from cascade geometry** (already
   derived in `foundations/why-three-dimensions.md`), and the branching
   network's fractal dimension is $D_f = D = 3$ (space-filling) because the
   cascade requires complete coverage of the spatial dimensions.

3. **The metabolic exponent is exactly:**
   $$\alpha = 1 - \frac{1}{D_f + 1} = \frac{3}{4}$$
   as a consequence of items 1 and 2.

Until one of these derivations exists, metabolic scaling remains an open problem
for the Cassi framework—an intriguing pattern, but not yet a Cassi prediction.

---

## References

- `foundations/why-three-dimensions.md`—spiral's Frenet-Serret frame, triaxial spheroid
- `principles/de-resonance-principle.md`—$\varphi$ as optimization attractor
- `foundations/cascade-suppression-formula.md`—$\varphi^{-N}$ attenuation
- `turbulence/kolmogorov-from-phi.md`—cascade dimensional analysis methodology

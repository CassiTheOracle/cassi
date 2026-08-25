# Metabolic Scaling and Allometry

## Status: Speculative (derivation not closed)—August 2026

## Abstract

Metabolic rate scales empirically with body mass as $B = B_0 \cdot M^{3/4}$
(Kleiber's law) across 21 orders of magnitude. West, Brown, and Enquist
(WBE) derive this value from a space-filling, area-preserving,
impedance-minimizing resource network in three-dimensional organisms—a
derivation that does not involve $\varphi$. In the WBE dimensional
generalization, $\alpha_{\mathrm{WBE}}(D)=D/(D+1)$, so $D=3$ gives $3/4$
while $D=2$ gives $2/3$. A distinct candidate,
$\alpha_{\mathrm{alt}}(D)=(D+1)/(D+2)$, gives $3/4$ for $D=2$ and $4/5$ for
$D=3$; no derivation in this document or in WBE selects that closure. This
document examines whether the Cassi framework can supply the missing
first-principles origin, making the optimal branching ratio and the network's
fractal dimension $\varphi$-determined. The connection
$\varphi^2 \approx 2.618 \to 3/4$ is not mathematically rigorous: it is a
prompt for future work, not a claim at the framework's usual epistemic
standard. The $\varphi$-derivation of Kleiber's exponent is an open problem,
not a solved one; metabolic scaling remains a Speculative application.

## Origin Status

**Verdict: catalog correspondence; mechanism open — stated openly in this
document.** Recomputation (`computations/verify_hypotheses_origin_audit.py`,
2026-08-11) confirms every number: $D_f = \ln 2/\ln\varphi = 1.440$,
$D_f = \ln 3/\ln\varphi = 2.283$ (§2),
$\alpha_{\mathrm{trial}} = 3/2.440 = 1.229$ and $3/3.283 = 0.914$ — both
wrong for Kleiber's 3/4; $\varphi^2/(\varphi^2+1) = 0.724$ vs 3/4 (a 4%
gap that compounds over 21 decades of body mass); heart/resp ratio
$\varphi^3 = 4.24$. The WBE network derivation gives
$\alpha_{\mathrm{WBE}}(D)=D/(D+1)$, hence $3/4$ in $D=3$ and $2/3$ in $D=2$,
without $\varphi$ anywhere. The distinct
$\alpha_{\mathrm{alt}}(D)=(D+1)/(D+2)$ gives $3/4$ in $D=2$ and $4/5$ in
$D=3$, but remains a Hypothesized alternative because its required geometry
or network-volume scaling has not been derived. No step from the two-fluid
PDE closes either $\varphi$ gap. The doc's own §4 verdict stands: the
connection is correlational, not causal; the contingent predictions of §3
would become testable only if the derivation closed.

---

## 1. Kleiber's Law

Metabolic rate $B$ scales with body mass $M$ across an enormous range of
organisms—from bacteria to blue whales—as:
$$B = B_0 \cdot M^{3/4}$$

This $3/4$ exponent (Kleiber's law) has been a puzzle for nearly a century.
West, Brown, and Enquist (1997) derive it from a space-filling fractal
resource-distribution network. For an $n$-ary self-similar network, their
geometric assumptions give a length ratio $g=n^{-1/D}$ from space filling and
a radius ratio $b=n^{-1/2}$ from area preservation in an embedding/service
dimension $D$. With size-invariant terminal units, the leading network-volume
scaling is $M\propto r_0^2l_0\propto n^{N(1+1/D)}$, while the terminal-unit
count is $n^N$ and $B\propto n^N$. Therefore the stated network derivation
gives
$$\alpha_{\mathrm{WBE}}(D)=\frac{1}{1+1/D}
=1-\frac{1}{D+1}=\frac{D}{D+1}.$$
Thus $D=3$ gives $3/4$, whereas $D=2$ gives $2/3$. The $D$ here is the
embedding/service-space dimension; WBE's result requires the network to fill
that space, so it does not justify substituting an independently chosen
fractal dimension $D_f$.

The expression $\alpha_{\mathrm{alt}}(D)=(D+1)/(D+2)$ is not algebraically
equivalent to the WBE result: it gives $3/4$ at $D=2$ and $4/5$ at $D=3$.
Under the same network algebra, selecting it would require an additional
assumption that the effective service dimension is $D+1$ (or an equivalent
extra network-volume/terminal-unit scaling). No such geometry is stated or
derived here. It is therefore retained only as a Hypothesized alternative,
not as the WBE dimensional law and not as a way to preserve the observed
three-dimensional exponent by relabeling $D$.

The key WBE assumption is that the terminal branches of the resource network
(capillaries in animals, leaf petioles in plants) are size-invariant—they have
the same radius and length regardless of organism size. This sets the network's
scaling structure but does not explain *why* the specific fractal dimension
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

where $N_{\text{branches}}$ is the illustrative number of daughter branches per parent branch in this candidate parameterization. The values $N_{\text{branches}}=2$ (binary) and $N_{\text{branches}}=3$ (trifurcating) give $D_f=\ln2/\ln\varphi\approx1.44$ and $D_f=\ln3/\ln\varphi\approx2.28$, respectively; they are branch-count examples, not a measured universal choice or a fitted Cassi parameter.

The WBE exponent is $\alpha_{\mathrm{WBE}}(D)=D/(D+1)$ only when the network
fills the $D$-dimensional service space. The draft's diagnostic
non-space-filling extension was:
$$\alpha_{\mathrm{trial}}=\frac{3}{D_f+1}.$$
This extension is not derived by WBE; it is retained only to expose the
consequence of inserting a $\varphi$-based $D_f$ while holding the embedding
dimension at $D=3$. For $D_f=1.440$: $\alpha_{\mathrm{trial}} =
3/2.440 \approx 1.229$—wrong (too large). For $D_f=2.283$:
$\alpha_{\mathrm{trial}}=3/3.283\approx 0.914$—wrong (too large, should be
0.75).

**This does not close.** Setting $D_f=D=3$ recovers the WBE identity
$$\alpha=1-\frac{1}{D_f+1}=\frac{D_f}{D_f+1}=\frac34,$$
but that equality follows from the space-filling network assumption, not from
$\varphi$. There is no clean path from $\varphi$ to the $3/4$ exponent—the
numbers are nearby ($\varphi^2 \approx 2.618$ and $3/4 = 0.75$;
$1/\varphi^2 \approx 0.382$ and $3/4 - 1 = -0.25$), but the derivation does
not close mathematically.


## 3. What Cassi *Could* Contribute (If the Derivation Closed)

If the $\varphi$-derivation of the metabolic exponent were to close, Cassi would
predict:

1. **Universality of $3/4$ under the WBE-compatible closure:** If Cassi
   derives the space-filling, area-preserving geometry from $\varphi$, the
   exponent is exactly $3/4$, not an empirical fit. Any systematic deviation
   (e.g., $2/3$ scaling in some taxa) would falsify that closure.

2. **$\varphi$-periodic allometric residuals:** After subtracting the $3/4$
   scaling, the residuals in $\ln B$ vs. $\ln M$ should show log-periodic
   modulation at period $\ln\varphi$—distinguishable from random taxonomic
   scatter.

3. **Branching ratio candidate:** If a future $\varphi$-derivation closes, the optimal number of daughter branches in biological resource networks could be a Fibonacci number ($2,3,5,8,\ldots$). No mechanism, independent branch-count receipt, or evidence that only Fibonacci counts preserve the attractor is supplied here. Binary or trifurcating observations are compatible with ordinary space-filling optimization and do not establish a Cassi prediction.

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
  spatial dimensions, which is supplied here as a Hypothesized geometric
  construction and conditional input in `foundations/why-three-dimensions.md`),
  the connection is correlational rather than causal.

## 5. Path to Closing

To upgrade this from Speculative to Hypothesized, the following would need to be
derived:

1. **The cascade determines the optimal branching ratio.** Show that impedance
   minimization on a $\varphi$-structured cascade ladder yields area-preserving
   branching ($r_{\text{parent}}^2 = \sum r_{\text{daughter}}^2$) as the
   de-resonance attractor—not as an empirical assumption.

2. **The embedding dimension $D=3$ is supplied as a Hypothesized geometric
   construction** (a conditional input in
   `foundations/why-three-dimensions.md`), and the branching network's fractal
   dimension is $D_f = D = 3$ (space-filling) because the cascade requires
   complete coverage of the spatial dimensions.

3. **The metabolic exponent is exactly:**
   $$\alpha = 1 - \frac{1}{D_f + 1} = \frac{D_f}{D_f+1}
   = \frac{3}{4}$$
   as a consequence of items 1 and 2. This is a conditional Hypothesized
   target, not a current Cassi derivation.

Until one of these derivations exists, metabolic scaling remains an open problem
for the Cassi framework—an intriguing pattern, but not yet a Cassi prediction.

---

## References

- `foundations/why-three-dimensions.md`—spiral's Frenet-Serret frame, triaxial spheroid
- West, G. B., Brown, J. H., and Enquist, B. J. (1997), “A general model for the origin of allometric scaling laws in biology,” *Science* 276(5309), 122–126, doi:10.1126/science.276.5309.122—primary WBE network derivation
- `principles/de-resonance-principle.md`—$\varphi$ as optimization attractor
- `foundations/cascade-suppression-formula.md`—$\varphi^{-N}$ attenuation
- `turbulence/kolmogorov-from-phi.md`—cascade dimensional analysis methodology

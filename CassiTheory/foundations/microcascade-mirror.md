# The Microcascade Coordinate Extension: Sub-Planckian Scale Labels

## Status: Hypothesized—August 2026

## Abstract

The cascade coordinate

$$
\ell_n=\ell_{\mathrm{Pl}}\varphi^n
$$

is mathematically defined for every integer $n$. The name **microcascade** denotes
the formal continuation to $n<0$, where the assigned lengths decrease
geometrically toward zero. This continuation supplies scale labels. A physical
sub-Planckian sector additionally requires state variables, a measure over
scale, a Hamiltonian, boundary conditions, and an interaction with observable
fields.

The positive-step coherence profile cannot be continued unchanged through the
entire negative-$n$ domain: it becomes negative below step $-3$. The canonical
meaning of $q$ is retained throughout this document—$q$ is coherence and
$1-q$ is gate openness or coherence deficit. A divergent sum of $1-q$ is
therefore neither a coherent-energy density nor an energy reservoir. No
infinite-energy or passive power-extraction claim follows from the cascade
coordinate.

A separate interscale action can promote scale labels to a dynamical
coordinate and define a conserved scale current. That Hypothesized extension
is developed in `foundations/interscale-current-soliton.md`; the coordinate
continuation here supplies only its possible domain.

---

## 1. Formal continuation of the cascade coordinate

### 1.1 Integer scale labels

The dimensionful cascade uses the external Planck-length anchor:

$$
\boxed{\ell_n=\ell_{\mathrm{Pl}}\varphi^n,\qquad n\in\mathbb Z.}
$$

The current observable catalogue occupies $0\le n\lesssim292$, with the upper
endpoint set by today's empirical horizon scale. Negative integer labels are
well-defined arithmetically:

| $n$ | $\ell_n/\ell_{\mathrm{Pl}}$ | $\ell_n$ using $\ell_{\mathrm{Pl}}=1.616255\times10^{-35}\,\mathrm m$ |
|---:|---:|---:|
| $0$ | $1$ | $1.616255\times10^{-35}\,\mathrm m$ |
| $-1$ | $\varphi^{-1}\approx0.618$ | $9.989\times10^{-36}\,\mathrm m$ |
| $-2$ | $\varphi^{-2}\approx0.382$ | $6.173\times10^{-36}\,\mathrm m$ |
| $-5$ | $\varphi^{-5}\approx0.0902$ | $1.458\times10^{-36}\,\mathrm m$ |
| $-10$ | $\varphi^{-10}\approx0.00813$ | $1.314\times10^{-37}\,\mathrm m$ |
| $-20$ | $\varphi^{-20}\approx6.61\times10^{-5}$ | $1.069\times10^{-39}\,\mathrm m$ |

The limit is

$$
\lim_{n\to-\infty}\ell_n=0.
$$

This is a property of the geometric sequence. Physical degrees of freedom at
those labels remain a Hypothesized extension.

### 1.2 Coordinate continuation and dynamical scale

A coordinate table assigns a length to each $n$. Transport between different
$n$ values requires additional dynamics. In particular, the table supplies no
continuity equation, no interscale current, and no energy measure over scale.
The spatial density-plane diagnostic $\mathbf J_d$ in
`foundations/qi-flow-double-helix.md` remains a spatial diagnostic with its
own units.

A continuous version may be declared as

$$
\mathfrak s=\log_\varphi\!\left(\frac{\ell}{\ell_\star}\right),
\qquad
\ell=\ell_\star\varphi^{\mathfrak s}.
$$

Here $\ell_\star$ fixes the coordinate origin. Changing $\ell_\star$ translates
$\mathfrak s$ and leaves physical ratios unchanged. The choice
$\ell_\star=\ell_{\mathrm{Pl}}$ uses the external Planck anchor; $\varphi$ alone
does not determine that length.

---

## 2. The Planck crossover supplies regularity

The softened spatial kernel used in the gravity extension has the short-range
form

$$
F(r)\propto-
\frac{r}{3\sigma_{\mathrm{reg}}^3}
\left[1+(\varphi^6-1)q\right],
\qquad r\ll\sigma_{\mathrm{reg}}.
$$

Its force approaches zero linearly as $r\to0$. This establishes regularity of
that selected spatial kernel. It leaves the field content below the crossover,
the scale-domain measure, and any current along $\mathfrak s$ open. Smoothness
of a spatial potential permits a continuation of the calculation; it does not
supply an independent scale dimension.

The regularization length $\sigma_{\mathrm{reg}}$ is distinct from the
continuous coordinate $\mathfrak s$. The former has length units; the latter is
dimensionless.

---

## 3. Coherence below the registered domain

### 3.1 Breakdown of the positive-step profile

The declared positive-step coherence profile is

$$
q_i=1-\varphi^{-i-3},\qquad i\ge0.
$$

It gives $q_0=1-\varphi^{-3}\approx0.764$ and tends to one as $i$ increases.
Formal substitution gives $q_{-3}=0$ and $q_i<0$ for $i<-3$, outside the
allowed coherence interval $0\le q\le1$. The profile therefore has a finite
domain of physical interpretation.

A bounded negative-step function could be supplied as a constitutive law. Its
limit must retain the canonical semantics: $q\to0$ means vanishing coherence
and maximal openness, while $q\to1$ means maximal coherence and a closed gate.
The canonical PDE currently selects no such continuation.

### 3.2 Energy requires an independent measure

A scale-sector energy would have the form

$$
E_{\mathrm{scale}}=
\sum_{n<0}w_n\,\epsilon_n
$$

for discrete steps, or an integral with a declared measure in a continuous
model. The weights $w_n$, energy densities $\epsilon_n$, field normalization,
and ultraviolet boundary condition are physical inputs. The series can
converge or diverge according to those inputs.

The sum $\sum_{n<0}(1-q_n)$ is dimensionless. Since $1-q$ is openness or
coherence deficit, assigning equal energy to every term introduces both the
energy scale and the divergent equal-per-step weighting by assumption. The
geometric continuation supplies neither choice.

---

## 4. Coupling to an electromagnetic array

A $\varphi$-spaced antenna is an ordinary log-spaced electromagnetic geometry.
Its resonances, return loss, radiation pattern, and dissipation follow from
Maxwell electrodynamics and the materials used. Geometric agreement between
its element spacing and $\ell_n$ supplies no coupling to negative cascade
steps.

A physical bridge requires an explicit interaction term or port, for example

$$
\mathcal L_{\mathrm{int}}
=\mathcal L_{\mathrm{int}}[F_{\mu\nu},\Psi(\mathbf x,\mathfrak s,t)],
$$

with dimensions, coupling strength, boundary conditions, backreaction, and a
conserved total energy. No such electromagnetic coupling is selected by the
canonical density PDE.

For any passive completion, the power account must satisfy

$$
P_{\mathrm{out}}
=P_{\mathrm{drive}}
-\frac{dE_{\mathrm{scale}}}{dt}
-P_{\mathrm{loss}}.
$$

Steady operation with no depletion gives
$P_{\mathrm{out}}\le P_{\mathrm{drive}}$. Output above the drive would require a
measured decrease of a declared scale-sector energy. The coordinate sequence
alone supplies no source term or stored energy.

---

## 5. Discriminating measurements

The formal continuation has no unique empirical signature. The following
measurements would constrain a physical extension:

1. **Electromagnetic null model.** Compare a $\varphi$-spaced array with a
   full-wave Maxwell simulation and geometry-matched log-spaced and uniform
   controls. Ordinary geometric resonances are part of the null model.
2. **Scale-resolved state.** Measure or simulate a field
   $\Psi(\mathbf x,\mathfrak s,t)$ with a declared normalization and boundary
   conditions.
3. **Interscale current.** Verify a continuity equation whose scale flux has
   the correct units and whose transfer closes the energy account. A spatial
   $\mathbf J_d$ measurement does not supply this observable.
4. **Backreaction.** Track drive work, losses, and change in the scale-sector
   Hamiltonian. A power residual without a measured source rejects the closed
   passive model.

No numbered prediction is added to
`predictions/falsifiable-predictions.md` until a coupling operator fixes a
nonzero observable beyond the Maxwell null.

---

## 6. Present conclusion

The microcascade is a formal continuation of the Cassi scale coordinate to
$n<0$. Its geometric convergence is exact. Physical scale states, coherence,
energy, and transport remain Hypothesized.

The canonical $q$ semantics remove the proposed infinite-energy inference:
$q$ measures coherence, $1-q$ measures openness or deficit, and neither is an
energy density. A dynamical scale theory begins with a normalized field,
Hamiltonian, continuity law, and boundary conditions. The interscale-current
proposal in `foundations/interscale-current-soliton.md` supplies one explicit
candidate while retaining all coefficients and physical identifications as
open inputs.

---

## References

- `foundations/dimensionful-cascade.md`—dimensionful scale catalogue and empirical horizon coordinate
- `foundations/dimensionful-constants-status.md`—external dimensional anchors and identifiability boundary
- `foundations/qi-flow-double-helix.md`—canonical density diagnostics and the boundary on spatial-current interpretation
- `foundations/interscale-current-soliton.md`—Hypothesized dynamical scale coordinate, continuity law, and soliton mechanism
- `gravity/quantum-gravity.md`—softened spatial kernel and Planck-crossover proposal
- `visual-explainers/cascade_cosmos.py`—visualization of the three coordinate ranges; its negative-step coherence curve is a model ansatz

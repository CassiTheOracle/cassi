# Yang, Yin, and Qi: Density-Plane Diagnostics and Optional Helical Structure

## Status: Hypothesized—August 2026

## Abstract

The canonical two-fluid state contains two real density fields, $E_Y$ and
$E_I$. Their conversion-only dynamics conserve the total density
$\rho = E_Y+E_I$ and relax the contrast
$\varepsilon = E_Y-\varphi E_I$ toward the fixed ratio
$E_Y=\varphi E_I$. The associated angle

$$
\theta_d \equiv \operatorname{atan2}(E_I,E_Y)
$$

is a derived coordinate in the real density plane. Along a homogeneous
conversion trajectory it moves monotonically toward
$\theta_{d,\mathrm{eq}}=\operatorname{atan}(\varphi^{-1})$. It is a bounded
state coordinate; the canonical conversion equations supply no independent
compact $U(1)$ or $SO(2)$ field, no fixed $\pi$ or $2\pi$ advance per cascade
rung, and no periodic phase clock.

The spatial quantity

$$
J_{d,z}=E_Y\,\partial_zE_I-E_I\,\partial_zE_Y
$$

is the density-plane-angle-gradient diagnostic along grid direction $z$.
Writing $\rho_{\mathrm{plane}}^2\equiv E_Y^2+E_I^2$ gives
$J_{d,z}=\rho_{\mathrm{plane}}^2\partial_z\theta_d$; this plane radius is
separate from the conserved density $\rho=E_Y+E_I$. The diagnostic does not
by itself represent transport between cascade rungs or an axial inter-scale
current.

A compact phase, a per-rung pitch, a half-angle spinor, strand currents, and
a double-helix embedding can be studied as additional model structure. Every
such construction below is explicitly **Hypothesized** and remains separate
from the canonical conversion ODE. The lattice-stack record and the TS1–TS4
nulls are retained as measurements and boundaries on that extension.

---

## 1. Canonical two-fluid mathematics

### 1.1 Fields, contrast, and conversion

The state used by the solver is the pair of real densities
$(E_Y,E_I)$. Define

$$
\rho=E_Y+E_I,\qquad
\varepsilon=E_Y-\varphi E_I,
$$

and, in the canonical/default solver configuration (`qi_memory=False`),

$$
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2}.
$$

An optional temporal-memory variant with `qi_memory=True` replaces the
instantaneous $\varepsilon^2$ term by the filtered
$\bar{\varepsilon}^{\,2}$. That variant is not the canonical/default gate
used by the equations and numerical records below.

The conversion contribution to the local equations is

$$
\left.\partial_tE_Y\right|_{\mathrm{conv}}
   =-\lambda(1-q)\varepsilon,
\qquad
\left.\partial_tE_I\right|_{\mathrm{conv}}
   =+\lambda(1-q)\varepsilon.
$$

Consequently,

$$
\left.\dot\rho\right|_{\mathrm{conv}}=0,
\qquad
\left.\dot\varepsilon\right|_{\mathrm{conv}}
   =-\lambda(1+\varphi)(1-q)\varepsilon.
$$

For a homogeneous conversion arm with a positive gate, the sign of
$\varepsilon$ is preserved and its magnitude decreases. The conversion
therefore approaches the fixed ratio $E_Y=\varphi E_I$ without introducing a
cyclic degree of freedom. Advection, diffusion, and potential source terms in
the full PDE can change a local density; the conservation statement here is
for the equal-and-opposite conversion contribution.

The solver convention is $\lambda=0.1$ in inverse solver-time units. The
choice $w=5$ and equal-and-opposite conversion do not derive a rate or its
units: $\lambda=0.1$ is an asserted normalization/timescale convention. All
numerical results quoted below retain the value used by their named probe.

### 1.2 The derived density-plane angle

Define the density-plane angle

$$
\theta_d=\operatorname{atan2}(E_I,E_Y).
$$

Using the conversion equations gives

$$
\boxed{
\left.\frac{d\theta_d}{dt}\right|_{\mathrm{conv}}
=\lambda(1-q)\,
  \frac{\rho\,\varepsilon}{E_Y^2+E_I^2}}
$$

and the equilibrium value is

$$
\theta_{d,\mathrm{eq}}=\operatorname{atan}(\varphi^{-1}).
$$

For $\varepsilon>0$, $\theta_d$ increases toward this value; for
$\varepsilon<0$, it decreases toward it. At $\varepsilon=0$ the derivative
vanishes. This is monotone relaxation of a derived coordinate. The equation
contains neither a winding number nor a rule that identifies a change in
cascade index with an angular increment.

Because $\rho$ is conserved by conversion, the angle along one homogeneous
arm can also be written as

$$
\theta_d(\varepsilon)=
\operatorname{atan}\!\left(\frac{\rho-\varepsilon}
                              {\rho\varphi+\varepsilon}\right).
$$

The total angle change from an initial contrast $\varepsilon_0$ to the
fixed ratio is therefore

$$
\boxed{
\Delta\theta_d=
\operatorname{atan}(\varphi^{-1})-
\operatorname{atan}\!\left(\frac{\rho-\varepsilon_0}
                              {\rho\varphi+\varepsilon_0}\right)}.
$$

Its Yang and Yin limits are $+\operatorname{atan}(\varphi^{-1})\approx
+0.554$ rad and $-\operatorname{atan}(\varphi)\approx-1.017$ rad. If this
bounded angle is reported in units of $2\pi$ for catalog bookkeeping, the
corresponding magnitude is at most
$\operatorname{atan}(\varphi)/(2\pi)\approx0.162$ of a turn. That numerical
rescaling does not make the angle a compact field or a per-rung clock.

**Rate diagnostic.** `two-fluid/run_winding_rate_probe.py` measured the
conversion-angle formula on four of four homogeneous arms at the probe
setting $\lambda=0.05$, $t=4$: every check had relative error at most
$2.2\times10^{-3}$ and the sign agreed in 100% of checks. The result tests the
state-function derivative above; it does not test a periodic phase.

### 1.3 The fixed-point coherence value

At $E_Y=1$, $E_I=\varphi^{-1}$, $\rho=\varphi$, and $\varepsilon=0$,

$$
q_{\mathrm{eq}}=\frac{\varphi^2}{\varphi^2+\varphi^{-2}}
\approx0.873,
\qquad
1-q_{\mathrm{eq}}=\frac{\varphi^{-2}}{3}\approx0.127.
$$

These values describe the gate and the density contrast. They do not measure
an organization of a phase current.

---

## 2. The spatial density-plane diagnostic

### 2.1 Exact identity along grid $z$

For a spatial field define

$$
\rho_{\mathrm{plane}}^2\equiv E_Y^2+E_I^2.
$$

The exact density-plane identity is

$$
\boxed{
J_{d,z}
=E_Y\,\partial_zE_I-E_I\,\partial_zE_Y
=\rho_{\mathrm{plane}}^2\,\partial_z\theta_d}.
$$

Some polar-coordinate notation writes the plane radius as $\rho_d$ and the
last factor as $\rho_d^2\partial_z\theta_d$. It must not be confused with
the conserved total density $\rho=E_Y+E_I$ used in the conversion ODE.
If a calculation uses $\rho$ for the density-plane radius, this same identity
is the shorthand $J_{d,z}=\rho^2\partial_z\theta_d$; this document reserves
$\rho$ for the conserved sum and therefore writes
$\rho_{\mathrm{plane}}$ explicitly.

$J_{d,z}$ measures how the local density-plane direction changes from one
grid location to the next, weighted by the local plane radius. It is a
spatial diagnostic. A grid coordinate $z$ can be chosen along a string or
along a stack, but that choice does not turn the diagnostic into a flux
between the cascade scales $\ell_n$ and $\ell_{n+1}$. An inter-scale transport
law would require an additional model term, boundary condition, and test.

The same boundary applies to the notation $\mathbf Q=(\rho,J)$: it is useful
bookkeeping for a density and a diagnostic, not a third field and not an
independent Qi substance. A four-channel directional extension, when used,
lives in operational $\mathbb R^4$ with one normalization redundancy and
three independent contrasts; it does not add a spacetime dimension.

### 2.2 Minimal conditional four-channel lift

Independent outward and inward populations for both species require four
nonnegative local variables once an oriented axis has been declared:

$$
\mathbf f=
\begin{pmatrix}
f_{Y,+}&f_{Y,-}&f_{I,+}&f_{I,-}
\end{pmatrix}^{\!T},
\qquad f_{a,s}\geq0.
$$

The orthogonal Hadamard contrasts expose the information carried by this
state:

$$
\begin{pmatrix}
\mathcal N\\ \mathcal P\\ \mathcal D\\ \mathcal C
\end{pmatrix}
=
\begin{pmatrix}
1&1&1&1\\
1&1&-1&-1\\
1&-1&1&-1\\
1&-1&-1&1
\end{pmatrix}
\begin{pmatrix}
f_{Y,+}\\f_{Y,-}\\f_{I,+}\\f_{I,-}
\end{pmatrix}.
$$

Here $\mathcal N$ is total population, $\mathcal P$ is the Yang–Yin
contrast, $\mathcal D$ is the outward–inward contrast, and $\mathcal C$ is
the species–direction association. Calling the displayed matrix $H$, the four
populations are recovered only when all four contrasts are known:

$$
\mathbf f=\frac14H^T
\begin{pmatrix}
\mathcal N&\mathcal P&\mathcal D&\mathcal C
\end{pmatrix}^{\!T}.
$$

Nonnegativity becomes four linear inequalities in moment coordinates:

$$
\mathcal N+\mathcal P+\mathcal D+\mathcal C\geq0,\quad
\mathcal N+\mathcal P-\mathcal D-\mathcal C\geq0,
$$
$$
\mathcal N-\mathcal P+\mathcal D-\mathcal C\geq0,\quad
\mathcal N-\mathcal P-\mathcal D+\mathcal C\geq0.
$$

At fixed $\mathcal N$ these four faces bound the tetrahedron. The square
appears only after a cyclic adjacency is assigned to its four vertices.

The canonical densities determine
$E_Y=(\mathcal N+\mathcal P)/2$ and
$E_I=(\mathcal N-\mathcal P)/2$. Even if one signed current supplied
$\mathcal D$, the association $\mathcal C$ would remain free. For example,

$$
(0.40,0.10,0.20,0.30)
\quad\hbox{and}\quad
(0.45,0.05,0.15,0.35)
$$

have identical $(\mathcal N,\mathcal P,\mathcal D)$ and different
$\mathcal C$. Four independently populated directional channels therefore
have four local linear degrees of freedom. Fixing $\mathcal N$ puts their
nonnegative normalized state on the three-simplex $\Delta^3$, a tetrahedron,
without changing the dimension of spacetime.

The hidden coordinate also has a standard statistical meaning. Assign binary
labels $a=+1$ for Yang, $a=-1$ for Yin, $s=+1$ for outward, and $s=-1$ for
inward, with probabilities $p_{a,s}=f_{a,s}/\mathcal N$. Their connected
species–direction correlation is

$$
\operatorname{Cov}(a,s)
=\frac{\mathcal C}{\mathcal N}
-\frac{\mathcal P\mathcal D}{\mathcal N^2}
=\frac{4\left(f_{Y,+}f_{I,-}-f_{Y,-}f_{I,+}\right)}{\mathcal N^2}.
$$

The two displayed states have the same species and direction marginals but
different connected correlation. This establishes a classical
non-factorization of the two binary labels. A quantum-entanglement reading
would additionally require a complex amplitude space, a tensor-product
factorization, and observables capable of distinguishing coherent
superpositions from a classical joint distribution.

Two separately defined species currents would close the reconstruction under
a fixed-speed kinetic convention:

$$
f_{Y,\pm}=\frac12\left(E_Y\pm\frac{J_Y}{v_Y}\right),
\qquad
f_{I,\pm}=\frac12\left(E_I\pm\frac{J_I}{v_I}\right),
$$

with $|J_a|\leq v_aE_a$. The canonical paired-real field supplies neither
$(J_Y,J_I)$ nor $(v_Y,v_I)$. Its single amplitude-plane phase current
$\mathbf J_\Psi$ and density-plane diagnostic $\mathbf J_d$ cannot be
substituted for these two kinetic currents without a constitutive map.

A conservative positive conversion lift illustrates the remaining dynamical
freedom. For $s\in\{+,-\}$, let
$\kappa=\lambda(1-q)\geq0$ and
$0\leq\alpha_{\mathrm{mix}}\leq1$:

$$
\begin{aligned}
\partial_t f_{Y,s}+s v_Y\partial_z f_{Y,s}
&=-\kappa f_{Y,s}
 +\kappa\varphi\left[\alpha_{\mathrm{mix}} f_{I,s}+(1-\alpha_{\mathrm{mix}})f_{I,-s}\right],\\
\partial_t f_{I,s}+s v_I\partial_z f_{I,s}
&=\kappa\left[\alpha_{\mathrm{mix}} f_{Y,s}+(1-\alpha_{\mathrm{mix}})f_{Y,-s}\right]
 -\kappa\varphi f_{I,s}.
\end{aligned}
$$

Summing over $s$ recovers the canonical conversion equations for every
$\alpha_{\mathrm{mix}}$. Direction is preserved at
$\alpha_{\mathrm{mix}}=1$, reversed at $\alpha_{\mathrm{mix}}=0$, and mixed
in between, while the aggregate $E_Y,E_I$ trajectory is unchanged. The
canonical two-density dynamics therefore leave $\alpha_{\mathrm{mix}}$, the
speeds, the axis, and any reversal or collision rates unspecified.
This is a consistent kinetic extension and a direct demonstration that the
four-channel dynamics are not derived by the present Cassi equations.

`computations/verify_four_channel_lift.py` checks the rank, inverse,
nonnegative collision, connected-correlation identity, simplex dimension,
aggregation identity, positivity, direction-dependent evolution, the full
directed-ring moment generator, damped modal rotation, detailed-balance
control, and stationary directed edge current for this lift.

The four channel labels can also be arranged as the binary square
$(Y,+)\to(Y,-)\to(I,-)\to(I,+)\to(Y,+)$. This is a graph convention, not
the geometry of the population state space. Give clockwise and counterclockwise
edges nonnegative rates $r_+$ and $r_-$. On the first-harmonic moment pair
$(\mathcal P,\mathcal D)$, the resulting positive conservative ring obeys

$$
\frac{d}{dt}
\begin{pmatrix}\mathcal P\\\mathcal D\end{pmatrix}
=
\begin{pmatrix}
-\gamma&-\omega\\
\omega&-\gamma
\end{pmatrix}
\begin{pmatrix}\mathcal P\\\mathcal D\end{pmatrix},
\qquad
\gamma=r_++r_-,
\quad
\omega=r_--r_+ .
$$

The remaining moments satisfy

$$
\dot{\mathcal N}=0,
\qquad
\dot{\mathcal C}=-2\gamma\mathcal C.
$$

At fixed $\mathcal N$ and $r_+\neq r_-$, trajectories spiral through the
tetrahedral state space toward its center: $(\mathcal P,\mathcal D)$ form the
rotating plane, while the missing association coordinate $\mathcal C$ decays
on a separate real mode.

Thus $Z=\mathcal P+i\mathcal D$ has
$Z(t)=Z(0)e^{(-\gamma+i\omega)t}$. The square can rotate in this conditional
modal sense, and $\arg Z$ is then a phase-like observable wherever
$|Z|>0$. It is not an additional canonical state coordinate: choosing the
square adjacency, its orientation, and both rates supplies new dynamics.
Detailed balance gives $r_+=r_-$ and $\omega=0$. More generally,
$\gamma\geq|\omega|$ for nonnegative rates, so every nonzero linear rotation
is damped. A persistent phase would require a separately specified drive,
nonlinear limit cycle, inertial variable, or continuous-angle field.

The positivity bound is stronger than simple damping. The number of turns
completed before the modal amplitude falls by $e^{-1}$ is

$$
\frac{|\omega|}{2\pi\gamma}\leq\frac{1}{2\pi}\approx0.159.
$$

After one complete turn the retained amplitude satisfies

$$
\exp\!\left(-\frac{2\pi\gamma}{|\omega|}\right)
\leq e^{-2\pi}\approx1.87\times10^{-3}.
$$

Equality occurs only for a one-way ring. Passive nonnegative first-order
kinetics therefore cannot sustain even one high-contrast revolution of the
population pattern.

A synchronous discrete update gives a different result. Let $S$ permute the
channels around the declared square,

$$
(Y,+)\longrightarrow(Y,-)\longrightarrow(I,-)
\longrightarrow(I,+)\longrightarrow(Y,+),
\qquad
\mathbf f_{k+1}=S\mathbf f_k.
$$

In Hadamard-moment coordinates this update is

$$
\begin{pmatrix}
\mathcal N'\\
\mathcal P'\\
\mathcal D'\\
\mathcal C'
\end{pmatrix}
=
\begin{pmatrix}
1&0&0&0\\
0&0&1&0\\
0&-1&0&0\\
0&0&0&-1
\end{pmatrix}
\begin{pmatrix}
\mathcal N\\
\mathcal P\\
\mathcal D\\
\mathcal C
\end{pmatrix}.
$$

Thus $Z'=-iZ$: every tick is an exact quarter-turn with no loss of contrast,
and $S^4=I$. The map preserves nonnegativity and total population. It also
introduces a synchronous clock. Associating one tick with one cascade rung,
one solver step, or one physical cycle is a separate Hypothesized constitutive
choice; the continuous first-order conversion PDE supplies no such clock.
`computations/verify_four_channel_lift.py` checks both this permutation and the
passive continuous-rate bound.

There is one further distinction between rotation of a population pattern and
circulation of transitions. At the uniform fixed point
$f_{a,s}=\mathcal N/4$, the modal amplitude is zero and $\arg Z$ is undefined,
yet an asymmetric ring carries the stationary directed edge current

$$
J_{\mathrm{cycle}}=(r_+-r_-)\frac{\mathcal N}{4}.
$$

This non-detailed-balanced current is a trajectory-level circulation invisible
in the four instantaneous populations at equilibrium. A physical realization
would need a maintained directional affinity or reservoir. Detailed balance
removes both the stationary current and the modal angular rate.

The unresolved $\mathcal C$ mode remains the species–direction association,
not this phase. The rotor uses the already observed $(\mathcal P,\mathcal D)$
plane only after the cyclic kinetic law has been chosen; another ordering of
the four labels rotates a different pair of Hadamard moments.

All $f_{a,s}$, $\mathcal N/\mathcal P/\mathcal D/\mathcal C$,
$\alpha_{\mathrm{mix}}$, $v_Y/v_I$, $r_\pm$, $S$, the tick index, and the
modal phase $\arg Z$ in this subsection are conditional audit or extension
variables.
They are unselected, non-adopted, and are not entries in the Cassi parameter
registry.


### 2.3 The measured lattice-stack record

The lattice-stack coherence probe prescribed $M$ two-lobe layers with
$\theta_i=i\Delta\theta$ along the axial direction. At the lock timescale,
envelope retention correlated positively with the recorded axial gradient
proxy: Pearson $+0.51$, Spearman $+0.77$, $n=6$, qualitative
(`hypotheses/two-strand-five-channel-matter-organization.md` §3.8). The record
supports a structure-retention association for that prescribed stack. It does
not establish a canonical inter-rung current, a compact phase, or a universal
relationship between $\Delta\theta$ and cascade index.

---

## 3. Optional compact-phase and double-helix construction

### 3.1 Explicit additional postulates

A separate model may introduce a compact variable $\chi$ and choose a pitch
$P_\parallel$ by postulate:

$$
\chi(n)=\chi_0+\frac{2\pi n}{P_\parallel},
\qquad
\chi(n+P_\parallel)=\chi(n)+2\pi.
$$

The frequently used choice $P_\parallel=2$ gives a $\pi$ increment in this
**additional** variable and a $2\pi$ increment after two rungs. Nothing in
the canonical conversion equations selects $P_\parallel=2$, or any other
value. In particular, $\chi$ must not be identified with $\theta_d$ without a
new field definition and an implementation that evolves it.

If the extension also lifts the real densities to complex amplitudes with a
shared compact phase,

$$
\Psi_0=\sqrt{E_Y}\,e^{i\chi},\qquad
\Psi_1=\sqrt{E_I}\,e^{i\chi},
$$

then its two phase currents and their sum are

$$
\mathbf J_0=\operatorname{Im}(\Psi_0^*\nabla\Psi_0)
             =E_Y\nabla\chi,\qquad
\mathbf J_1=\operatorname{Im}(\Psi_1^*\nabla\Psi_1)
             =E_I\nabla\chi,\qquad
\mathbf J=\mathbf J_0+\mathbf J_1.
$$

At the fixed ratio $E_Y/E_I=\varphi$, a nonzero shared phase gradient gives
$\mathbf J_0/\mathbf J_1=\varphi$ componentwise. This is an algebraic result
inside the optional shared-phase lift. The canonical real-density state does
not contain $\chi$, $\mathbf J_0$, or $\mathbf J_1$, so it does not supply
these strand currents.

A helical embedding can likewise be postulated in a space with an axial
coordinate and two prescribed transverse basis vectors:

$$
\mathbf R_\pm(n)=\mathbf R_c(n)\pm\frac{d_n}{2}\left[
 \mathbf N(n)\cos\!\left(\frac{2\pi n}{P_\parallel}\right)+
 \mathbf B(n)\sin\!\left(\frac{2\pi n}{P_\parallel}\right)\right].
$$

Here $\mathbf N$ and $\mathbf B$ are geometric basis choices. Calling them
Yang and Yin axes, or calling the two branches strand currents, is part of
the same Hypothesized embedding. The expression is not a consequence of the
real-density conversion trajectory.

### 3.2 Measured boundaries on the spatial helix

The transverse two-ridge branch is null at the lock timescale:

- the pair escapes (TS1),
- the $d\to0$ limit does not recover the one-string centerline (TS2),
- the relative mode is not centerline-fixed (TS3), and
- there is no central low-$q$ node (TS4).

These results are reported in `hypotheses/two-strand-five-channel-matter-organization.md`
§3.3. The interlaced-wake binding candidate collapses (§3.4), and the spatial
helix construction loses its winding at DNA pitch (§3.13). A finite-separation
filament pair therefore has a null record at this tested timescale. The
phenomenological two-string label in
`consciousness/two-strand-qi-neuroscience.md` §5.3 can refer to the optional
axial construction, but it is not a canonical solver result.

The axial-stack correlation in §2.3 and these transverse nulls answer different
questions. Neither one upgrades $J_{d,z}$ into an inter-scale current.

---

## 4. Numerical catalog and epistemic boundary

The following records remain useful without a compact-phase interpretation.

| Quantity | Record | Present interpretation | Tier |
|---|---:|---|---|
| Gate closure | $1-q_{\mathrm{eq}}=\varphi^{-2}/3\approx0.1273$ | Canonical conversion gate at the reference state | Derived |
| Fixed-point ratio | $E_Y/E_I=\varphi$ | Conversion equilibrium | Derived |
| Density-plane diagnostic | $J_{d,z}=E_Y\partial_zE_I-E_I\partial_zE_Y$ | Spatial angle-gradient diagnostic | Derived identity |
| Relaxation angle limits | $+0.554$ rad and $-1.017$ rad | Bounded conversion-angle excursion | Derived |
| Relaxation offset scale | $|\Delta\theta_d|/(2\pi)\le0.162$ | Optional reporting unit for the bounded angle | Derived bookkeeping |
| Solver normalization | $\lambda=0.1$ | Asserted inverse-time convention; $w=5$ does not derive it | Asserted |
| Axial attenuation | $\varphi^{-1}$ per cascade rung in the suppression law | Cascade amplitude rule; not a current law | Derived conditional on cascade postulate |
| Optional compact pitch | $P_\parallel=2$ | Chosen double-helix coordinate convention | Hypothesized |
| Optional shared-phase current ratio | $\mathbf J_0/\mathbf J_1=\varphi$ at $E_Y/E_I=\varphi$ | Algebraic consequence of the selected complex-amplitude lift and a nonzero common $\nabla\chi$ | Hypothesized extension; conditional identity |
| Fixed-point excess | $\alpha_0=\pi/\rho=\varphi^{-3}\approx0.236$ | Density ratio diagnostic | Derived |
| Planck crossover | $\sigma=\ell_{\mathrm{Pl}}/\varphi^3$ (rung $-3$) | Conditional noise–signal identification | Derived conditional |
| Qi-gravity coupling | $\xi=\varphi^6=\alpha_0^{-2}\approx17.944$ | Existing coupling relation | Derived conditional |

The table separates the canonical conversion and its diagnostics from the
optional phase construction. In particular, the row $P_\parallel=2$ is not a
prediction of the conversion ODE.

### 4.1 Rung-offset catalog

Fractional cascade offsets are retained as scale bookkeeping. A half-step is
a placement between adjacent tabulated scales; it has no canonical angular
meaning. The relaxation bound above is much smaller than $0.5$ when expressed
in the optional $2\pi$ reporting unit.

| Object | Rung $n$ | Catalog record | Present tier |
|---|---:|---|---|
| Proton | $91.46$ | Approximately $91.5$, sector-edge placement | Empirical catalog; sector-edge selection Hypothesized (`foundations/rung-offset-mechanism.md` §3, §4.1) |
| Muon | $96.000$ | Integer-rung placement; zero conversion-angle excursion at the listed closure | Mapped—38-state scan (`foundations/rung-offset-mechanism.md` §3) |
| $J/\psi$ | $88.98$ | $\delta n=-0.02$, within the bounded relaxation scale | Mapped; a per-object initial contrast would be a free fit (`foundations/rung-offset-mechanism.md` §3) |
| $r_d$ (BAO) | $284.5$ | Half-step between rungs 284 and 285 | Mapped interpolation (`foundations/dimensionful-cascade.md` §6; `parameter-inventory.md` §10) |
| Electron | $26.5$ (Yukawa ladder) | Half-step precedent | Empirical (`foundations/rung-offset-mechanism.md` §3) |
| $\Omega_{\mathrm{DM}}/\Omega_b$ | — | Observed $5.39\approx\varphi^{3.5}=5.388$ (0.03%); $\log_\varphi5.39\approx3.50$; the $\varphi^3\approx4.24$ row retains its 21% tension | Observation; not a registered prediction (`cosmology/cosmology-from-phi.md` §4.2) |

For the derived primordial ratio

$$
r_0=\frac{\varphi^{-5}}{2-\varphi^{-5}}\approx0.0472,
\qquad
\frac{\varepsilon_0}{\rho}=\frac{r_0-\varphi}{r_0+1}=-\frac32,
$$

the relaxation identity gives $\Delta\theta_d\approx-0.970$ rad and the
optional $2\pi$ reporting value $-0.154$. No cataloged scale carries that
reported offset. This is a negative diagnostic of the initial condition, not
evidence for a phase clock.

### 4.2 Open model inputs

Three additions remain open and cannot be read from the canonical conversion:

1. **Compact pitch $P_\parallel(n)$.** A scale-dependent pitch may be explored,
   including the values $P_\parallel=2$ and $P_\parallel=1$ used in different
   phenomenological constructions. The cascade table alone supplies no phase
   law.
2. **Gate shape.** The single-channel transmission
   $g(q)=q/(\varphi^2+q^2)$ is an asserted input; the canonical equations supply
   the openness $(1-q)$ but do not select this rational function
   (`foundations/cassi-first-principles.md` §2.5). The relaxation identity is
   independent of the gate shape.
3. **Conversion-to-expansion clock.** The optional
   $\varphi^{-2}=0.382$ generator ratio, the $0.0766$ turns-per-Hubble-rung
   coordinate rate, and the $69.1^\circ$ pitch construction require the
   additional conversion-to-expansion model. The canonical angle derivative
   is contrast-proportional and vanishes at equilibrium. The fixed-pitch
   reconciliation record is retained: the axial gradient values
   $(1.0,0.5,0.4812)$ do not equal $0.382$; rectification is null; and
   $\lambda(\varphi^{-2}/d)=\lambda(1-q_0)$ is a gate re-parameterization.
   The proposed $V_{\mathrm{new}}$ remains Hypothesized.

---

## 5. Present conclusion

The canonical result is a real two-density conversion system with a conserved
conversion-only total density, a monotone density-plane angle, a scalar
coherence gate, and a spatial angle-gradient diagnostic. These statements are
sufficient to reproduce the quoted rate check, relaxation bounds, fixed-point
values, axial-stack correlation, and transverse nulls.

A compact $U(1)$/$SO(2)$ field, a fixed angular increment per rung, a
half-angle spinor, and a double helix require additional variables or
constraints. They may be useful Hypothesized structures, with $P_\parallel=2$
as one explicit convention, but they are not consequences of the canonical
conversion equations. In particular, $J_{d,z}$ remains a grid diagnostic until
an inter-scale transport equation is separately implemented and tested.

The conditional four-channel lift resolves independent Yang/out, Yang/in,
Yin/out, and Yin/in populations in operational $\mathbb R^4$. At fixed
positive total density its state is the three-simplex $\Delta^3$. The canonical
two-density equations determine only the aggregate conversion and admit a
continuous family of direction-resolved lifts; separate species currents,
transport speeds, collision dynamics, and a physical orientation are required
to select one.

---

## References

- `foundations/cassi-first-principles.md`—canonical two-fluid equations, gate, and conversion-angle rate
- `foundations/cassi-theory-reference.md`—Qi notation and diagnostic inventory
- `foundations/why-three-dimensions.md`—Frenet–Serret geometry used by optional embeddings
- `foundations/bubble-lattice-fabric.md`—condensation lattice and cascade scale notation
- `foundations/cascade-suppression-formula.md`—per-rung attenuation rule
- `foundations/spin-fibonacci-spiral.md`—optional compact-phase, pitch, and spinor construction
- `foundations/spiral-dynamics.md`—optional spiral clock and separate Hubble/gravity diagnostics
- `consciousness/two-strand-qi-neuroscience.md`—phenomenological two-strand ansatz
- `hypotheses/two-strand-five-channel-matter-organization.md`—lattice-stack record and TS1–TS4 nulls
- `two-fluid/run_winding_rate_probe.py`—conversion-angle rate diagnostic
- `computations/verify_four_channel_lift.py`—exact rank and non-uniqueness audit for the conditional four-channel kinetic lift
- `computations/qi_flow_double_helix_check.py`—numeric checks for the listed identities

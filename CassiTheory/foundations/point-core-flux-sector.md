# Quantized Point-Core Flux and the Persistent-Defect Boundary

## Status: Derived conditional exterior support / Derived current-action completion no-go—September 2026

## Abstract

A point excision gives the compact relative connection a spatial two-cycle and
therefore permits a nonzero first Chern number. The least spatial gauge energy
outside an excised sphere can be derived without choosing a trial profile. For
flux

$$
\Phi_G=\frac{4\pi N_G}{g_Q},
$$

the fixed-flux contribution is

$$
E_G(R)\geq\frac{\mathcal B_G}{R},
\qquad
\boxed{
\mathcal B_G
=\frac{\Phi_G^2}{8\pi}
\int_{I_{\mathfrak s}}
\frac{d\mathfrak s}{\mu_x}
=2\pi N_G^2
\int_{I_{\mathfrak s}}
\frac{d\mathfrak s}{e_x^2}.}
$$

Here $e_x^2=g_Q^2\mu_x$, and the scale integral uses the source action's
base-interval measure. Equality is attained by the radial exterior
field. The supported Derrick condition becomes

$$
\boxed{\mathcal B_G>\mathcal D.}
$$

This coefficient establishes a positive $1/R$ term for an imposed point-core
sector. It does not complete a smooth particle in the current Abelian action.
The Abelian Bianchi identity forbids smooth nonzero magnetic charge on the
unexcised base. In addition, the nonzero Yang and Yin condensates at spatial
infinity are charged sections of nontrivial line bundles when $N_G\ne0$.
Their angular covariant-gradient energy has a positive lower bound on every
large sphere, so an isolated point-flux configuration has infinite matter
energy. A scalar radial matter mode is absent for the same reason.

The current theory therefore determines the exterior flux coefficient, its
support inequality, and the positive reduced breathing curvature. A smooth
core, a finite-energy stationary field, and a dynamical fluctuation spectrum
require an additional magnetic or ultraviolet completion.

---

## 1. Scope and result ledger

### 1.1 Inputs

The calculation uses four registered structures:

1. the compact relative $U(1)_Q$ connection and spatial gauge energy from
   `foundations/interscale-current-soliton.md`;
2. the two-edge scale graph from
   `foundations/geometric-manifold-completion.md`;
3. the point-excised Chern sector from
   `foundations/endpoint-link-and-localization-boundary.md`;
4. the reduced Derrick profile
   $E(R)=\mathcal A R+(\mathcal B-\mathcal D)/R+\mathcal C R^3$.

The relative connection, scale metric, and particle interpretation remain
Hypothesized. The results below are deductions inside that declared sector.

### 1.2 Results

| ID | Result | Status |
|---|---|---|
| PF-1 | A point excision admits $N_G\in\mathbb Z$ and the two-patch Dirac connection with $\Phi_G=4\pi N_G/g_Q$ | Derived bundle geometry under compact $U(1)_Q$ |
| PF-2 | Fixed flux gives the sharp exterior bound $E_G(R)\geq\mathcal B_G/R$ with the displayed $\mathcal B_G$ | Derived conditional on the registered gauge energy and scale measure |
| PF-3 | Point-flux support requires $\mathcal B_G>\mathcal D$; the reduced radius and static breathing curvature then follow exactly | Derived reduced-profile algebra |
| PF-4 | The current smooth Abelian fields cannot resolve a nonzero magnetic point charge | Derived from the Bianchi identity |
| PF-5 | A nonzero asymptotic Yang/Yin condensate and isolated $N_G\ne0$ give divergent angular matter energy | Derived finite-energy obstruction |
| PF-6 | The current data do not define a radial stationary matter problem or a dynamical fluctuation spectrum | Derived well-posedness boundary |

No result identifies a Standard Model particle or selects a mass, electric
charge, color representation, spin, statistics, or lifetime.

---

## 2. Compact point-core sector

### 2.1 Excised base and Chern number

Let

$$
\Omega_R:=\mathbb R^3\setminus B_R,
\qquad R>0,
\tag{PF1}
$$

and take one compact pass around the completed scale graph. Every sphere
$S_r^2\subset\Omega_R$ links the excised core. With minimum relative charge
$q_{\min}=g_Q/2$, the first Chern number is

$$
\boxed{
N_G
:=\frac{g_Q}{4\pi}\int_{S_r^2}G
\in\mathbb Z.}
\tag{PF2}
$$

The Abelian Bianchi identity $dG=0$ makes this integer independent of $r$.
It is also independent of $\mathfrak s$. Integrating the mixed component of
$dG=0$ over the closed sphere gives

$$
\partial_{\mathfrak s}\int_{S_r^2}G=0.
\tag{PF3}
$$

Thus a smooth connection on the excised product carries one integer sector
through the entire scale support.

This topology removes the spatial core for every scale position: the removed
set is the worldtube $\{0\}\times S^1_{\mathfrak s}$. A point removed only
from the full four-dimensional base has an $S^3$ link and does not supply this
spatial Chern class.

### 2.2 Two-patch representative

A representative connection uses north and south patches on each linking
sphere:

$$
B^{(N)}
=\frac{N_G}{g_Q}(1-\cos\theta)\,d\phi,
\qquad
B^{(S)}
=-\frac{N_G}{g_Q}(1+\cos\theta)\,d\phi.
\tag{PF4}
$$

Both give

$$
G=dB
=\frac{N_G}{g_Q}\sin\theta\,d\theta\wedge d\phi,
\qquad
\int_{S_r^2}G=\frac{4\pi N_G}{g_Q}.
\tag{PF5}
$$

On the overlap,

$$
B^{(N)}-B^{(S)}=d\alpha,
\qquad
\alpha=\frac{2N_G}{g_Q}\phi.
\tag{PF6}
$$

The minimum-charge transition function is

$$
\exp\!\left(i\frac{g_Q}{2}\alpha\right)
=e^{iN_G\phi},
\tag{PF7}
$$

which is single-valued exactly when $N_G$ is an integer. The Yang and Yin
sections carry opposite transition windings $+N_G$ and $-N_G$. The charged
endpoint section carries winding $-2N_G$.

---

## 3. Sharp fixed-flux energy

### 3.1 Spherewise lower bound

Define the spatial relative magnetic field by

$$
\mathfrak b_i:=\frac12\epsilon_{ijk}G_{jk}.
\tag{PF8}
$$

Then $G_{ij}G_{ij}=2|\boldsymbol{\mathfrak b}|^2$ and

$$
\int_{S_r^2}\boldsymbol{\mathfrak b}\cdot d\mathbf S
=\Phi_G,
\qquad
\Phi_G:=\frac{4\pi N_G}{g_Q}.
\tag{PF9}
$$

Cauchy–Schwarz on every sphere gives

$$
\begin{aligned}
\int_{S_r^2}|\boldsymbol{\mathfrak b}|^2\,dA
&\geq
\int_{S_r^2}\mathfrak b_r^2\,dA\\
&\geq
\frac{1}{4\pi r^2}
\left(\int_{S_r^2}\mathfrak b_r\,dA\right)^2
=\frac{\Phi_G^2}{4\pi r^2}.
\end{aligned}
\tag{PF10}
$$

Tangential field components can only increase the energy. The spatial gauge
term therefore obeys

$$
\begin{aligned}
E_G(R)
&:=\int_{I_{\mathfrak s}}d\mathfrak s
\int_R^\infty dr
\int_{S_r^2}dA\,
\frac{G_{ij}G_{ij}}{4\mu_x}\\
&\geq
\frac{\Phi_G^2}{8\pi R}
\int_{I_{\mathfrak s}}
\frac{d\mathfrak s}{\mu_x}.
\end{aligned}
\tag{PF11}
$$

Equality holds for the scale-independent radial field

$$
\boxed{
\boldsymbol{\mathfrak b}_*(r)
=\frac{\Phi_G}{4\pi r^2}\,\widehat{\mathbf r}.}
\tag{PF12}
$$

Equation (PF11) is a variational lower bound at fixed flux and does not assume
a radial trial profile.

### 3.2 Core coefficient and scale measure

Define

$$
\boxed{
\mathcal B_G
:=\frac{\Phi_G^2}{8\pi}
\int_{I_{\mathfrak s}}
\frac{d\mathfrak s}{\mu_x}
=2\pi N_G^2
\int_{I_{\mathfrak s}}
\frac{d\mathfrak s}{e_x^2},
\qquad e_x^2:=g_Q^2\mu_x.}
\tag{PF13}
$$

For constant coefficients, define

$$
L_G:=\int_{I_{\mathfrak s}}d\mathfrak s=L_{\mathfrak s}.
\tag{PF14}
$$

this becomes

$$
\boxed{
\mathcal B_G
=\frac{2\pi L_GN_G^2}{e_x^2}.}
\tag{PF15}
$$

The registered source action integrates the common connection energy once over
the base interval, so its coefficient uses $L_G=L_{\mathfrak s}$. A separate
lift that assigns an independent gauge-energy term to both rail edges would
give $L_G=2L_{\mathfrak s}$ and double (PF15). That lift is an additional
normalization branch. Every term in a reduced energy must use the same measure.

For a nonflat declared scale density $\omega(\mathfrak s)$, every occurrence
of $d\mathfrak s/\mu_x$ is replaced by
$\omega(\mathfrak s)d\mathfrak s/\mu_x(\mathfrak s)$.

Under

$$
B_A' = aB_A,
\qquad
g_Q'=\frac{g_Q}{a},
\qquad
\mu_x'=a^2\mu_x,
\tag{PF16}
$$

one has $\Phi_G'=a\Phi_G$, $N_G'=N_G$, and
$\mathcal B_G'=\mathcal B_G$. The coefficient depends only on the registered
invariant $e_x^2$ and the chosen scale measure.

The dimensional check is

$$
[\mathcal B_G]
=\frac{\hbar L}{T}
=\text{energy}\times\text{length},
\qquad
\left[\frac{\mathcal B_G}{R}\right]
=\text{energy}.
\tag{PF17}
$$

---

## 4. Reduced support condition

### 4.1 Quantized support coefficient

Insert the exterior contribution into the registered reduced energy:

$$
E_N(R)
:=\mathcal A R
+\frac{\mathcal B_G(N_G)-\mathcal D}{R}
+\mathcal C R^3.
\tag{PF18}
$$

Let

$$
\mathcal Q_N:=\mathcal B_G(N_G)-\mathcal D.
\tag{PF19}
$$

For $\mathcal A>0$ and $\mathcal C\geq0$, a positive small-radius barrier and
an interior stationary point require

$$
\boxed{
\mathcal Q_N>0
\quad\Longleftrightarrow\quad
2\pi N_G^2
\int_{I_{\mathfrak s}}
\frac{d\mathfrak s}{e_x^2}
>\mathcal D.}
\tag{PF20}
$$

With constant $e_x$ this is

$$
\boxed{
\frac{2\pi L_GN_G^2}{e_x^2}>\mathcal D.}
\tag{PF21}
$$

The smallest allowed charge magnitude in that convention is

$$
\boxed{
|N_G|_{\min}
=
\left\lfloor
\sqrt{\frac{e_x^2\mathcal D}{2\pi L_G}}
\right\rfloor+1.}
\tag{PF22}
$$

The strict inequality is essential. Equality removes the $1/R$ barrier.
The quantities $e_x$, $L_G$, and $\mathcal D$ remain unselected, so the current
theory does not determine whether $|N_G|=1$ is sufficient.

### 4.2 Radius and scaling curvature

For $\mathcal C>0$ and $\mathcal Q_N>0$,

$$
\boxed{
R_*^2
=\frac{-\mathcal A
+\sqrt{\mathcal A^2+12\mathcal C\mathcal Q_N}}
{6\mathcal C}.}
\tag{PF23}
$$

The stationary relation is

$$
\mathcal Q_N
=\mathcal A R_*^2+3\mathcal C R_*^4,
\tag{PF24}
$$

and the reduced breathing curvature is

$$
\boxed{
E_N''(R_*)
=\frac{2\mathcal A}{R_*}
+12\mathcal C R_*>0.}
\tag{PF25}
$$

For $\mathcal C=0$,

$$
R_*=\sqrt{\frac{\mathcal Q_N}{\mathcal A}},
\qquad
E_N''(R_*)=\frac{2\mathcal A}{R_*}>0.
\tag{PF26}
$$

These equations establish static stability along the one-parameter scaling
family. Shape, matter, endpoint, scale, and gauge modes require the full field
solution.

---

## 5. Finite-energy completion boundary

### 5.1 Smooth Abelian core

On an unexcised spatial ball, a smooth Abelian curvature obeys

$$
\int_{S_r^2}G
=\int_{B_r}dG
=0.
\tag{PF27}
$$

Neither the charged Yang/Yin doublet nor the charged endpoint sections modify
the identity $dG=0$. They source the Euler–Lagrange equation for $B_A$ and do
not supply magnetic current. Consequently the present Abelian fields cannot
continue $N_G\ne0$ smoothly through the point core.

The divergence

$$
E_G(R)\sim\frac{\mathcal B_G}{R}
\longrightarrow\infty
\qquad(R\to0)
\tag{PF28}
$$

is the energy expression of the same obstruction. A dynamic smooth core needs
additional structure such as an emergent Abelian sector of a non-Abelian
bundle, an explicit magnetic source, or a boundary that retains the excision.
None is part of the registered action.

### 5.2 Nonzero condensate at infinity

Finite potential energy in the registered broken-density vacuum requires

$$
\rho\longrightarrow\rho_0>0,
\qquad
E_Y-\varphi E_I\longrightarrow0.
\tag{PF29}
$$

Thus

$$
E_Y\longrightarrow\frac{\rho_0}{\varphi},
\qquad
E_I\longrightarrow\frac{\rho_0}{\varphi^2},
\tag{PF30}
$$

so both charged components remain nonzero asymptotically. At fixed
$N_G\ne0$, they are sections of line bundles with Chern numbers $+N_G$ and
$-N_G$. A nowhere-vanishing section would trivialize its line bundle, which is
incompatible with a nonzero Chern number.

The energy obstruction can also be stated spectrally. For a minimum-charge
scalar on a linking sphere, the covariant angular Laplacian has monopole
harmonics satisfying

$$
-D_{S^2}^2Y^{(N_G)}_{jm}
=
\left[j(j+1)-\frac{N_G^2}{4}\right]
Y^{(N_G)}_{jm},
\qquad
j\geq\frac{|N_G|}{2}.
\tag{PF31}
$$

Its lowest eigenvalue is

$$
\lambda_{\min}=\frac{|N_G|}{2}>0.
\tag{PF32}
$$

Summing both charged components gives the angular lower bound

$$
E_{\rm ang}
\geq
\frac{K_x|N_G|}{4}
\int_{I_{\mathfrak s}}d\mathfrak s
\int_R^{R_{\max}}dr
\int_{S^2}d\Omega\,\rho(r,\Omega,\mathfrak s).
$$

The $r^{-2}$ from the physical angular derivative cancels the $r^2$ area
factor. With a flat interval of length $L_{\mathfrak s}$ and
$\rho\to\rho_0$, the cost per unit radius tends to
$\pi K_x|N_G|\rho_0L_{\mathfrak s}$, so $E_{\rm ang}$ diverges linearly as
$R_{\max}\to\infty$. Both charged components contribute positively.

An isolated point flux therefore has no finite-energy completion in the
current nonzero-condensate Abelian sector. Finite-energy alternatives require a
changed physical problem: a finite outer boundary, a defect–antidefect system
with zero net flux at infinity, flux confined to a finite string or loop, a
normal exterior with $\rho_0=0$, or a smooth magnetic ultraviolet completion.
These alternatives have different boundary data and field content.

### 5.3 Radial matter obstruction

Equation (PF31) also shows that $j=0$ is unavailable when $N_G\ne0$. A globally
defined ansatz

$$
\psi_a=\psi_a(r,\mathfrak s)
\tag{PF33}
$$

cannot represent the charged matter sector. Patched monopole harmonics are
required, and the nonlinear density and composition potentials generally mix
the selected angular modes. The exterior gauge field has a radial solution;
the coupled matter problem is at least angular–radial and must carry the core
and outer boundary data described above.

---

## 6. Stationary equations and solver verdict

### 6.1 Bulk equations

Let

$$
\varepsilon:=E_Y-\varphi E_I.
\tag{PF34}
$$

Away from scale vertices and the excised core, unconstrained static variation
of the registered energy gives

$$
\begin{aligned}
0={}&
\frac{K_x}{2}D_i^\dagger D_i\psi_Y
+\frac{K_{\mathfrak s}}{2}
D_{\mathfrak s}^\dagger D_{\mathfrak s}\psi_Y\\
&+\frac{\lambda_\rho}{2}(\rho-\rho_0)\psi_Y
+\lambda_\varphi\varepsilon\psi_Y,
\end{aligned}
\tag{PF35}
$$

$$
\begin{aligned}
0={}&
\frac{K_x}{2}D_i^\dagger D_i\psi_I
+\frac{K_{\mathfrak s}}{2}
D_{\mathfrak s}^\dagger D_{\mathfrak s}\psi_I\\
&+\frac{\lambda_\rho}{2}(\rho-\rho_0)\psi_I
-\varphi\lambda_\varphi\varepsilon\psi_I.
\end{aligned}
\tag{PF36}
$$

The registered static connection equations are

$$
\frac{1}{\mu_x}\partial_jG_{ji}
-\frac{1}{\mu_m}\partial_{\mathfrak s}G_{i\mathfrak s}
+\hbar\mathcal I_i=0,
\tag{PF37}
$$

$$
\frac{1}{\mu_m}\partial_iG_{i\mathfrak s}
+\hbar\mathcal I_{\mathfrak s}=0,
\tag{PF38}
$$

supplemented by $dG=0$. The coherent endpoint fields or open endpoint channel
supply separate scale-vertex equations and boundary conditions. A point-core
action must supply the inner spatial boundary conditions.

### 6.2 Exterior solution

When matter and mixed-curvature sources are omitted from the exterior gauge
subproblem, (PF12) solves (PF37) and saturates (PF11). This is a complete
solution of the fixed-flux Maxwell exterior problem on $\Omega_R$. It is not a
solution of (PF35)–(PF38) with the asymptotic condensate (PF30).

### 6.3 Well-posedness decision

A stationary numerical solve requires all of the following:

1. a core action or fixed inner boundary data at $r=R$;
2. one scale-measure convention for every energy term;
3. an angular or patched ansatz compatible with $N_G$;
4. outer data that permit finite total energy;
5. selected values for the free stiffnesses, potentials, endpoint sector, and
   mixed-curvature response.

The current action supplies none of the core data and its nonzero-condensate
outer condition conflicts with isolated point flux. A radial or axisymmetric
particle solve would therefore choose the missing physics through its boundary
conditions. No numerical boundary-value experiment is well posed in the
current sector, so no preregistered stationary run is performed.

---

## 7. Static and dynamical stability

### 7.1 Exterior gauge sector

For fixed core, fixed $N_G$, and fixed boundary flux, (PF10) proves that the
radial exterior field minimizes the spatial gauge energy. The quadratic gauge
energy for flux-preserving perturbations is

$$
Q_G[\delta B]
=
\int d^3x\,d\mathfrak s
\left[
\frac{\delta G_{ij}\delta G_{ij}}{4\mu_x}
+\frac{\delta G_{i\mathfrak s}
\delta G_{i\mathfrak s}}{2\mu_m}
\right]
\geq0,
\tag{PF39}
$$

with pure-gauge directions removed by gauge fixing. This establishes static
stability of the exterior gauge field inside its imposed flux sector.

### 7.2 Scaling mode

The reduced radius is statically stable when (PF20) holds, with curvature
(PF25). A physical breathing frequency would require a collective inertia
$M_R$:

$$
\omega_R^2=\frac{E_N''(R_*)}{M_R}.
\tag{PF40}
$$

The current action does not derive $M_R$ for an excised boundary.

### 7.3 Full fluctuation operator

A full spectrum requires a stationary background
$(\Psi_*,B_{A,*},\Upsilon_{v,*})$, gauge fixing, core and endpoint boundary
conditions, and the second variation in every coupled channel. The registered
action has first-order matter kinetics and no temporal gauge curvatures
$G_{ti}$ or $G_{t\mathfrak s}$. It therefore supplies no gauge-field inertia or
complete Gauss dynamics. Static positivity of (PF39) cannot be converted into
gauge-mode frequencies.

The exact result currently available is the positive one-dimensional scaling
curvature. The full fluctuation spectrum remains undefined until a finite-energy
background and temporal gauge completion are supplied.

---

## 8. Evidence and physical boundary

| Question | Result |
|---|---|
| Does point excision create an integer sector? | Yes, conditionally: $N_G\in\mathbb Z$ on the linking $S^2$ |
| Does fixed flux supply positive $1/R$ energy? | Yes: the sharp coefficient is (PF13) |
| Can the coefficient exceed the pinch attraction? | Only if (PF20) holds; current coefficients do not decide it |
| Does the current Abelian action smooth the point core? | No; $dG=0$ forces zero flux through a smooth ball |
| Does the registered condensate admit an isolated finite-energy monopole? | No; the nonzero charged asymptotic sections give divergent angular kinetic energy |
| Is a scalar radial matter solve available? | No; $j\geq|N_G|/2$ and the core/outer data are incomplete |
| Is the full fluctuation spectrum defined? | No; the stationary background, core data, and temporal gauge dynamics are absent |

The algebraic and spectral identities are checked by
`computations/point_core_flux_check.py`. They create no numbered physical
prediction. An observable requires a selected completion, a finite-energy
solution, and a map to measured particle data.

---

## 9. Present conclusion

A nonzero first Chern sector supplies the positive support term requested by
the reduced Derrick analysis. Its coefficient is fixed by the integer flux,
the invariant spatial gauge coupling, and the declared scale measure. The
condition for a supported reduced radius is now explicit:

$$
2\pi N_G^2
\int_{I_{\mathfrak s}}
\frac{d\mathfrak s}{e_x^2}
>\mathcal D.
$$

The same calculation identifies the next physical boundary. The point
excision remains part of the model, and the current broken-density Abelian
sector has no isolated finite-energy continuation. Its stationary radial
matter problem and full fluctuation spectrum are consequently undefined. A
persistent localized particle requires a magnetic core completion or a
finite, net-zero flux geometry before numerical stationary and stability work
can begin.

---

## References

- `foundations/interscale-current-soliton.md`—relative connection, gauge energy,
  coefficient units, mixed-curvature pinch, and Derrick profile
- `foundations/geometric-manifold-completion.md`—two-edge scale graph, scale
  measure, and physical completion requirements
- `foundations/endpoint-link-and-localization-boundary.md`—Chern candidate,
  point excision, and smooth-sector localization boundary
- `foundations/proton-coherence-budget.md`—particle-facing scale circuit and
  localization requirements
- `computations/point_core_flux_check.py`—flux, energy, support, and spectral
  algebra checker

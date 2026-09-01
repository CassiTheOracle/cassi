# Gauge-Covariant Endpoint Closure and the Localization Boundary

## Status: Derived conditional endpoint closure / Derived minimal-sector localization no-go—September 2026

## Abstract

The Cassi scale circuit has two vertices where Yang and Yin rail currents must
turn into one another. This document supplies two explicit endpoint
completions. A charged complex vertex field gives a coherent, gauge-covariant
link and reduces to the endpoint cosine interaction when its amplitude is
frozen. A one-way Lindblad channel gives a gauge-covariant open-system
alternative. The coherent link has a finite current capacity. At uniform
$\varphi$ composition, stationary Planck-to-proton circulation requires

$$
\kappa_v|\Upsilon_v|
\geq
\frac{K_{\mathfrak s}|\Delta_m|}
{2\varphi^{3/2}\mathfrak s_p}.
$$

The one-way open closure instead fixes the conditional endpoint-rate ratio
$\gamma_-/\gamma_+=\varphi$ while damping transverse coherence.

The normalized positive coherence fibre is $B^3$, so no homotopy invariant
constructed from the full state $\Gamma$ protects a localized sector. The
first Chern number of the independent compact relative connection is the
strongest surviving candidate. For a smooth object on
$\mathbb R^3\times S^1_{\mathfrak s}$, however, $H^2=0$. A nonzero Chern sector
therefore requires an excised core, line defect, boundary flux, or different
spatial topology.

These results produce a localization boundary. In the smooth, unexcised,
zero-Chern sector, the endpoint completion supplies no positive $1/R$ support
under spatial Derrick scaling, and the reduced energy has no finite-radius
stationary point. An imposed point-core Chern sector has the sharp exterior
coefficient derived in `foundations/point-core-flux-sector.md` and supports the
reduced radius only when $\mathcal B_G>\mathcal D$. An auxiliary adjoint
$SU(2)_Q$ branch smooths the local core and matches its exterior flux, but the
registered nonzero fundamental condensate removes the isolated magnetic sector
and confines flux. The residual-$U(1)_Q$ endpoint field has no selected
$SU(2)_Q$ vertex lift. The endpoint sector therefore closes the scale current
without deriving a persistent particle, particle quantum numbers, or a decay
rate.

---

## 1. Scope and dependency boundary

### 1.1 Inputs retained

The analysis uses the following registered structures:

1. The complex Yang/Yin doublet and relative $U(1)_Q$ connection from
   `foundations/interscale-current-soliton.md`.
2. The cross-glued two-rail metric graph and its compact scale circuit from
   `foundations/geometric-manifold-completion.md`.
3. The positive coherence matrix
   $\Gamma\in\operatorname{Herm}_2^+$ and normalized Bloch ball $B^3$ from the
   same completion.
4. The canonical open-system boundary from
   `foundations/physical-becoming-hierarchy.md`.
5. The conditional Derrick profile
   $E(R)=\mathcal A R+(\mathcal B-\mathcal D)/R+\mathcal C R^3$ from
   `foundations/interscale-current-soliton.md`.

The complex interscale action, compact relative connection, physical scale
metric, and particle interpretation retain their Hypothesized status. The
results below are deductions within those declared structures.

### 1.2 Result ledger

| ID | Result | Status |
|---|---|---|
| EL-1 | A charge-$-g_Q$ endpoint section makes the Yang/Yin mixing term gauge invariant | Derived representation and source algebra |
| EL-2 | A stationary coherent vertex has a finite critical current and the displayed $\varphi$-sector capacity bound | Derived conditional on the coherent endpoint action and uniform circuit state |
| EL-3 | One-way endpoint jumps close the population circuit with $\gamma_-/\gamma_+=\varphi$ | Derived conditional on the Markov endpoint channel and uniform $\varphi$ composition |
| EL-4 | The full positive coherence fibre carries no nontrivial state-only homotopy invariant | Derived topology |
| EL-5 | The smooth unexcised object base has no first-Chern sector; point or line excision creates one candidate integer sector | Derived topology for the declared base choices |
| EL-6 | The smooth zero-Chern endpoint completion has no finite Derrick radius; point-core flux gives a conditional exterior coefficient but no current-action particle completion | Derived minimal-sector no-go / Derived conditional point-core boundary |

No row identifies a Standard Model particle. Mass, electric charge, color,
spin, statistics, scale length, endpoint normalization, and lifetime remain
open.

---

## 2. Relative gauge convention

### 2.1 Bulk fields

Use the source action's temporal-gauge convention and time-independent relative
frame changes:

$$
\psi_Y\longmapsto e^{+ig_Q\alpha/2}\psi_Y,
\qquad
\psi_I\longmapsto e^{-ig_Q\alpha/2}\psi_I,
\qquad
B_A\longmapsto B_A+\partial_A\alpha,
\tag{EL1}
$$

where $A\in\{1,2,3,\mathfrak s\}$. With

$$
\psi_Y=\sqrt{E_Y}\,e^{i(\Theta-\vartheta/2)},
\qquad
\psi_I=\sqrt{E_I}\,e^{i(\Theta+\vartheta/2)},
\tag{EL2}
$$

the relative phase obeys

$$
\vartheta\longmapsto\vartheta-g_Q\alpha.
\tag{EL3}
$$

A completion covariant under time-dependent $\alpha$ additionally requires
$B_t$, its temporal covariant derivatives, and Gauss dynamics. Those fields are
absent from the interscale source action and remain outside the present
sector.

The separate source-free completion in
`foundations/particle-stationary-action-closure.md` supplies those temporal
fields and Gauss's law for the coupled fixed-$Q_C$ particle branch. The endpoint
sector here remains the authority for the spatial-and-scale vertex algebra.

### 2.2 Vertex orientation

Let

$$
V_{\mathfrak s}:=\{v_-,v_+\}
=\{\mathfrak s_-,\mathfrak s_+\},
\qquad
\sigma_-:=+1,
\qquad
\sigma_+:=-1.
\tag{EL4}
$$

For positive oriented circulation $\mathcal J_Q>0$, the desired Yang source at
a vertex is

$$
\Gamma_v=\sigma_v\mathcal J_Q.
\tag{EL5}
$$

Thus the lower vertex converts Yin into Yang and the upper vertex converts Yang
into Yin.

---

## 3. Coherent charged endpoint link

### 3.1 Endpoint transition section

Introduce one complex endpoint section $\Upsilon_v(\mathbf x,t)$ at each
vertex with relative charge $-g_Q$:

$$
\boxed{
\Upsilon_v\longmapsto
 e^{-ig_Q\alpha(v)}\Upsilon_v.}
\tag{EL6}
$$

The bulk bilinear transforms as

$$
\psi_Y^*\psi_I
\longmapsto
 e^{-ig_Q\alpha(v)}\psi_Y^*\psi_I.
\tag{EL7}
$$

Consequently the local coherent interaction

$$
\boxed{
\mathcal H_{\mathrm{link},v}
:=-\kappa_v\left(
\Upsilon_v^*\psi_Y^*\psi_I
+\Upsilon_v\psi_I^*\psi_Y
\right)_{\mathfrak s=v}}
\tag{EL8}
$$

is gauge invariant. The endpoint coupling is taken positive; its units include
the chosen vertex-field and boundary-trace normalization.

A minimal endpoint action in the convention of §2 is

$$
\begin{aligned}
S_{\mathrm{end}}
=\sum_{v\in V_{\mathfrak s}}\int dt\,d^3x\,\Bigg[
&\frac{i\hbar}{2}
\left(
\Upsilon_v^*\partial_t\Upsilon_v
-(\partial_t\Upsilon_v^*)\Upsilon_v
\right)
-\frac{K_v}{2}|D_i^{(-g_Q)}\Upsilon_v|^2\\
&-U_v(|\Upsilon_v|^2)
+\kappa_v\left(
\Upsilon_v^*\psi_Y^*\psi_I
+\Upsilon_v\psi_I^*\psi_Y
\right)_{\mathfrak s=v}
\Bigg],
\end{aligned}
\tag{EL9}
$$

with

$$
D_i^{(-g_Q)}\Upsilon_v
:=(\partial_i+ig_QB_i(v))\Upsilon_v.
\tag{EL10}
$$

The potentials $U_v$, stiffnesses $K_v$, and normalization of $\Upsilon_v$ are
new physical inputs. Equation (EL9) establishes a minimal covariant field
realization; it does not select those inputs.

### 3.2 Reduction to the endpoint cosine

Write

$$
\Upsilon_v=u_v e^{i\alpha_v},
\qquad u_v:=|\Upsilon_v|\geq0.
\tag{EL11}
$$

Its phase transforms as

$$
\alpha_v\longmapsto\alpha_v-g_Q\alpha(v),
\tag{EL12}
$$

so $\vartheta-\alpha_v$ is invariant. The interaction becomes

$$
\boxed{
\mathcal H_{\mathrm{link},v}
=-2\kappa_vu_v\sqrt{E_YE_I}
\cos(\vartheta-\alpha_v).}
\tag{EL13}
$$

The endpoint cosine in
`foundations/interscale-current-soliton.md` is the frozen-amplitude limit with
effective mixing strength

$$
\kappa_v^{\mathrm{eff}}:=\kappa_vu_v.
\tag{EL14}
$$

The endpoint phase is the charged field phase and carries the transformation
law (EL12).

### 3.3 Species source and conservation

Hamilton's equations from (EL8) give

$$
\boxed{
\left.\partial_tE_Y\right|_v
=-\frac{2\kappa_vu_v}{\hbar}
\sqrt{E_YE_I}\,
\sin(\vartheta-\alpha_v),}
\tag{EL15}
$$

and

$$
\boxed{
\left.\partial_tE_I\right|_v
=-\left.\partial_tE_Y\right|_v.}
\tag{EL16}
$$

The link therefore conserves Yang-plus-Yin number at every vertex:

$$
\left.\partial_t(E_Y+E_I)\right|_v=0.
\tag{EL17}
$$

Gauge charge is exchanged with the charged endpoint section. The corresponding
Noether current includes the $\Upsilon_v$ contribution.

### 3.4 Critical current and stable phase branch

Define the vertex critical current

$$
\boxed{
\mathcal J_{c,v}
:=\frac{2\kappa_vu_v}{\hbar}\sqrt{E_YE_I}.}
\tag{EL18}
$$

The stationary turning condition (EL5) requires

$$
\sin(\vartheta-\alpha_v)
=-\sigma_v\frac{\mathcal J_Q}{\mathcal J_{c,v}}.
\tag{EL19}
$$

A stationary phase lag exists only if

$$
\boxed{|\mathcal J_Q|\leq\mathcal J_{c,v}}
\tag{EL20}
$$

at both vertices. The local curvature of the link energy with respect to the
phase lag is

$$
K_{\delta,v}
:=2\kappa_vu_v\sqrt{E_YE_I}
\cos(\vartheta-\alpha_v).
\tag{EL21}
$$

The locally stable current branch has $K_{\delta,v}>0$, equivalently
$\cos(\vartheta-\alpha_v)>0$. Its phase stiffness vanishes at critical current.
An overcritical current has no stationary coherent phase lag in this endpoint
model.

### 3.5 Uniform $\varphi$-composition capacity

For the uniform circuit state,

$$
E_Y=\frac{\rho}{\varphi},
\qquad
E_I=\frac{\rho}{\varphi^2},
\qquad
\sqrt{E_YE_I}=\frac{\rho}{\varphi^{3/2}},
\tag{EL22}
$$

and

$$
|\mathcal J_{Q,m}|
=\frac{K_{\mathfrak s}\rho|\Delta_m|}
{\hbar\varphi^3\mathfrak s_p}.
\tag{EL23}
$$

Substitution into (EL20) gives the endpoint capacity bound

$$
\boxed{
\kappa_vu_v
\geq
\frac{K_{\mathfrak s}|\Delta_m|}
{2\varphi^{3/2}\mathfrak s_p}.}
\tag{EL24}
$$

For the unbiased $m=1$ sector,
$\Delta_1=2\pi$ and $\mathfrak s_p=91.461618346$, so

$$
\boxed{
\frac{\kappa_vu_v}{K_{\mathfrak s}}
\geq 0.0166889699.}
\tag{EL25}
$$

This number is a required coupling ratio within the declared endpoint
normalization. It is not a measured endpoint coupling or a prediction of the
canonical two-density PDE.

---

## 4. Gauge-covariant open endpoint channel

### 4.1 One-way vertex jumps

A trace-preserving Markov closure uses the one-way jumps

$$
L_-:=\sqrt{\gamma_-}\,|Y\rangle\langle I|,
\qquad
L_+:=\sqrt{\gamma_+}\,|I\rangle\langle Y|,
\tag{EL26}
$$

at the lower and upper vertices respectively. With

$$
\mathcal D[L](\Gamma)
:=L\Gamma L^\dagger
-\frac12\{L^\dagger L,\Gamma\},
\tag{EL27}
$$

the endpoint generator is

$$
\mathcal L_{\mathrm{end}}[\Gamma]
=\delta(\mathfrak s-\mathfrak s_-)
\mathcal D[L_-](\Gamma)
+\delta(\mathfrak s-\mathfrak s_+)
\mathcal D[L_+](\Gamma).
\tag{EL28}
$$

Under a relative frame change,

$$
L_-\longmapsto e^{+ig_Q\alpha(v_-)}L_-,
\qquad
L_+\longmapsto e^{-ig_Q\alpha(v_+)}L_+.
\tag{EL29}
$$

A Lindblad dissipator is unchanged when its jump acquires a local scalar phase.
Equation (EL28) is therefore gauge covariant.

### 4.2 Stationary population closure

The lower jump produces

$$
\left.\partial_tE_Y\right|_-=+\gamma_-E_I,
\qquad
\left.\partial_tE_I\right|_-=-\gamma_-E_I,
\tag{EL30}
$$

while the upper jump produces

$$
\left.\partial_tE_Y\right|_+=-\gamma_+E_Y,
\qquad
\left.\partial_tE_I\right|_+=+\gamma_+E_Y.
\tag{EL31}
$$

For positive oriented stationary circulation,

$$
\gamma_-E_I=\mathcal J_Q,
\qquad
\gamma_+E_Y=\mathcal J_Q.
\tag{EL32}
$$

The uniform $\varphi$ state and (EL23) then give

$$
\boxed{
\gamma_-
=\frac{K_{\mathfrak s}|\Delta_m|}
{\hbar\varphi\mathfrak s_p},
\qquad
\gamma_+
=\frac{K_{\mathfrak s}|\Delta_m|}
{\hbar\varphi^2\mathfrak s_p},}
\tag{EL33}
$$

and the rate ratio

$$
\boxed{\frac{\gamma_-}{\gamma_+}=\varphi.}
\tag{EL34}
$$

The ratio follows from the endpoint donor densities. The absolute rates retain
$K_{\mathfrak s}$, $\Delta_m$, and the Mapped scale length.

### 4.3 Coherence boundary

Each one-way jump damps the off-diagonal coherence of an undriven endpoint
state:

$$
\left.\partial_tc\right|_v
=-\frac{\gamma_v}{2}c.
\tag{EL35}
$$

The population circuit can therefore be stationary while its unconditional
transverse coherence decays. The jump channel supplies no endpoint phase
holonomy by itself. A coherent drive, monitored trajectory, protected sector,
or reservoir phase reference is required to retain endpoint phase information.

A closed conservative variational action cannot generate irreversible
one-way relaxation by itself. Equation (EL9) is the conservative coherent
choice. Equation (EL28) is an open-system choice. Effective non-Hermitian,
Schwinger–Keldysh, or MSRJD variational descriptions may encode reduced open
dynamics after a reservoir and contour structure are declared; they are not a
closed-system replacement for that reservoir.

---

## 5. Full-fibre invariant classification

### 5.1 State-only topology

For $\rho=\operatorname{tr}\Gamma>0$, every positive coherence state has the
unique form

$$
\Gamma
=\frac{\rho}{2}
\left(\mathbf 1+\mathbf n\cdot\boldsymbol\sigma\right),
\qquad
\|\mathbf n\|\leq1.
\tag{EL36}
$$

Hence

$$
\boxed{
\mathcal C_2^+\setminus\{0\}
\simeq\mathbb R_{>0}\times B^3.}
\tag{EL37}
$$

Both factors are contractible, so

$$
\boxed{
\pi_k(\mathcal C_2^+\setminus\{0\})=0
\qquad(k\geq1).}
\tag{EL38}
$$

A map into the full positive fibre carries no nontrivial homotopy class. This
includes maps that pass through $c=0$ or through full-rank states.

### 5.2 Candidate ledger

| Candidate | Domain of definition | Full-fibre protection |
|---|---|---|
| Projective degree or skyrmion number | Rank-one shell $\mathbb{CP}^1\simeq S^2$ | Lost when the path enters $\|\mathbf n\|<1$ |
| Relative coherence-phase winding | Region with $c\neq0$ | Lost when $c=0$; the phase is then undefined |
| Scale-graph winding $m$ | Nonvanishing coherent amplitude on the closed rail graph | Changed by an amplitude zero, phase slip, or incoherent endpoint event |
| Wilson holonomy around $S^1_{\mathfrak s}$ | Compact relative connection | Gauge invariant modulo the compact convention and generally continuous, with no integer quantization |
| First Chern number $N_G$ | Compact connection over a closed two-cycle | Integer and independent of mixedness in $\Gamma$ |

The canonical conversion lift damps $c$ and admits the full-rank interior, so
the first two candidates cannot protect the complete state space. The scale
winding remains a conditional circuit label as long as coherent nonzero
boundary amplitudes exist.

### 5.3 First Chern candidate

The matter doublet has minimum relative charge magnitude

$$
q_{\min}=\frac{g_Q}{2}.
\tag{EL39}
$$

For a compact relative connection with curvature $G=dB$, a closed oriented
two-cycle $\Sigma$ admits

$$
\boxed{
N_G
:=\frac{q_{\min}}{2\pi}\int_\Sigma G
=\frac{g_Q}{4\pi}\int_\Sigma G
\in\mathbb Z.}
\tag{EL40}
$$

This normalization agrees with the finite-energy flux relation
$\Phi_B=4\pi n_Y/g_Q$, for which $N_G=n_Y$. It also gives
$N_G=-m/2$ in the phase-only branch where both half-charged condensates remain
nonzero and individually current-free. The even-$m$ restriction belongs to
that branch.

The integer in (EL40) belongs to the connection bundle. It remains defined when
$\Gamma$ becomes mixed, provided the closed two-cycle and compact bundle remain
well defined.

### 5.4 Smooth-base obstruction

For the localized object sector with ordinary space $M_3=\mathbb R^3$ and the
internal scale circuit $S^1_{\mathfrak s}$,

$$
\mathbb R^3\times S^1_{\mathfrak s}
\simeq S^1,
\qquad
\boxed{H^2(\mathbb R^3\times S^1_{\mathfrak s};\mathbb Z)=0.}
\tag{EL41}
$$

Compactifying the spatial factor for scale-independent finite-energy boundary
data gives the same two-cycle result:

$$
\boxed{H^2(S^3\times S^1_{\mathfrak s};\mathbb Z)=0.}
\tag{EL42}
$$

Thus the smooth unexcised base has no nonzero first Chern class. A local field
strength may exist, while its bundle carries no protected integer flux sector.

Two minimal topology changes create a candidate two-cycle:

1. A point core gives

   $$
   (\mathbb R^3\setminus\{0\})\times S^1_{\mathfrak s}
   \simeq S^2\times S^1,
   \qquad
   H^2\simeq\mathbb Z.
   \tag{EL43}
   $$

   The integer is spatial flux through the linking $S^2$.

2. A line core gives

   $$
   (\mathbb R^3\setminus\mathbb R)\times S^1_{\mathfrak s}
   \simeq S^1_x\times S^1_{\mathfrak s},
   \qquad
   H^2\simeq\mathbb Z.
   \tag{EL44}
   $$

   The integer is flux through the mixed spatial-scale torus.

Both cases introduce a defect, excision, or boundary condition beyond the
smooth completion. The line case also invokes a toroidal support class. The
existing toroidal experiments constrain particular dynamical realizations of
such support; they do not alter the cohomology calculation.

A nonzero $N_G$ can change only when flux crosses a boundary, the defining
cycle disappears, a defect crosses it, or the connection becomes singular.
The endpoint link alone supplies none of these events.

---

## 6. Minimal-sector localization no-go

### 6.1 Declared sector

The no-go result applies under five conditions:

1. fields are smooth on the unexcised
   $\mathbb R^3\times S^1_{\mathfrak s}$ object base;
2. finite-energy boundary data approach one vacuum at spatial infinity;
3. the full coherence ball is dynamically accessible;
4. endpoint interactions are spatially local and contain at most two spatial
   derivatives, as in (EL9);
5. no fixed flux, excised defect, four-derivative core, or nonlocal repulsion is
   imposed.

These conditions define the minimal smooth zero-Chern sector. A broader action
may evade the result by violating a named condition.

### 6.2 Derrick scaling without an independent core

For a fixed profile rescaled as
$\mathbf x=R\mathbf y$, positive two-derivative energy scales as $R$ and local
potential energy scales as $R^3$. The endpoint field gradients and local link
potential have the same spatial scalings. With
$\mathcal A\geq0$ and $\mathcal C\geq0$, the minimal reduced energy is

$$
E_{\min}(R)=\mathcal A R+\mathcal C R^3.
\tag{EL45}
$$

For a nontrivial profile with positive energy,

$$
\frac{dE_{\min}}{dR}
=\mathcal A+3\mathcal C R^2>0
\qquad(R>0).
\tag{EL46}
$$

There is no finite positive stationary radius. Shrinking lowers the energy.

If elimination of a mixed-curvature response supplies the conditional
attractive term $-\mathcal D/R$ with $\mathcal D\geq0$, while no core term is
present, then

$$
E_{\mathrm{pinch}}(R)
=\mathcal A R-\frac{\mathcal D}{R}+\mathcal C R^3,
\tag{EL47}
$$

and

$$
\frac{dE_{\mathrm{pinch}}}{dR}
=\mathcal A+\frac{\mathcal D}{R^2}+3\mathcal C R^2>0.
\tag{EL48}
$$

The attractive contribution strengthens the small-radius collapse. It does not
create a stationary point.

### 6.3 Conditional supported radius

An independent fixed-flux, four-derivative, defect-core, or equivalent support
term contributes $+\mathcal B/R$. The registered reduced energy is

$$
E(R)
=\mathcal A R
+\frac{\mathcal B-\mathcal D}{R}
+\mathcal C R^3.
\tag{EL49}
$$

Set

$$
\mathcal Q:=\mathcal B-\mathcal D.
\tag{EL50}
$$

For $\mathcal A>0$, $\mathcal C>0$, and $\mathcal Q>0$, the unique positive
stationary radius is

$$
\boxed{
R_*^2
=\frac{-\mathcal A
+\sqrt{\mathcal A^2+12\mathcal C\mathcal Q}}
{6\mathcal C}.}
\tag{EL51}
$$

At the root,

$$
\mathcal Q=\mathcal A R_*^2+3\mathcal C R_*^4,
\tag{EL52}
$$

so

$$
\boxed{
E''(R_*)
=\frac{2\mathcal A}{R_*}+12\mathcal C R_*>0.}
\tag{EL53}
$$

If $\mathcal C=0$, the conditional root is

$$
R_*=\sqrt{\frac{\mathcal Q}{\mathcal A}}.
\tag{EL54}
$$

When $\mathcal A>0$, $\mathcal Q\leq0$, and $\mathcal C\geq0$,

$$
E'(R)
=\mathcal A-\frac{\mathcal Q}{R^2}+3\mathcal C R^2>0,
\tag{EL55}
$$

and no finite positive root exists. Therefore

$$
\boxed{\mathcal B>\mathcal D}
\tag{EL56}
$$

remains necessary for the reduced finite-radius solution.

The endpoint link fixes neither $\mathcal B$ nor a defect that could protect
it. Equations (EL45)–(EL56) establish the minimal-sector localization no-go and
the exact condition an added support sector must satisfy. They do not establish
a solution of a broader higher-derivative, defect, or nonlocal theory.

For the point-excised compact connection, the registered spatial gauge term
gives

$$
\mathcal B_G
=2\pi N_G^2
\int_{I_{\mathfrak s}}\frac{d\mathfrak s}{e_x^2},
\qquad e_x^2=g_Q^2\mu_x.
$$

This sharp coefficient replaces $\mathcal B$ in that branch. The associated
support condition is $\mathcal B_G>\mathcal D$. The auxiliary adjoint
$SU(2)_Q$ branch gives a smooth local core in its decoupled sector. Coupling the
registered condensate confines the flux, and the tested finite net-zero pair
has no registered finite-separation minimum. The neutral carrier branch in
`foundations/core-trapped-charge-support.md` supplies a conditional $A_C/L$
term and a unique reduced root when $A_C>C_Q$, carrier retention, and
thin-tube matching hold.

---

## 7. Stability and decay channels

### 7.1 Sector ledger

| Structure | Stability condition | Sector-changing event | Rate status |
|---|---|---|---|
| Coherent endpoint phase | $|\mathcal J_Q|<\mathcal J_{c,v}$, $u_v>0$, and $\cos(\vartheta-\alpha_v)>0$ at both vertices | Overcritical current, $u_v=0$, endpoint phase slip, or coupling to an incoherent channel | Requires $U_v$, endpoint damping, and fluctuation data |
| Scale-graph winding $m$ | Nonzero coherent amplitude around the compact graph | Rail-amplitude zero, endpoint phase slip, boundary event, or open jump | Unselected |
| Rank-one projective charge | Evolution remains on $\|\mathbf n\|=1$ with fixed boundary data | Entry into the full-rank interior or $\rho=0$ | Minimal conversion supplies an inward path but no universal transition rate |
| First Chern number $N_G$ | Closed two-cycle and compact connection in a defect or nontrivial-base sector | Boundary flux, defect crossing, singular connection event, or removal of the cycle | Exterior coefficient Derived conditionally; core dynamics unselected |
| Reduced spatial radius | $\mathcal A>0$, $\mathcal C\geq0$, and $\mathcal B_G>\mathcal D$ in the point-core branch | Collapse when support does not exceed $\mathcal D$; large-radius instability when $\mathcal C<0$ | Reduced curvature Derived; full stationary functional defined, background unselected |
| Auxiliary magnetic core | Adjoint-only $SU(2)_Q$ sector has the exact BPS core; the registered nonzero fundamental condensate confines flux | Condensate coupling removes the isolated magnetic sector; a finite pair can shrink and annihilate | Static adjoint Hessian nonnegative conditionally; temporal action defined, coupled spectrum absent |
| Core-trapped carrier pair | $A_C>C_Q$, $\hbar\omega_C<\varepsilon_{C,\rm out}$, and separation beyond core overlap | Carrier leakage, profile delocalization, core merger, or transition to another fixed-$Q_C$ configuration | Reduced length and line-density curvature Derived conditionally; fixed-charge action defined, background and spectrum absent |
| Fixed-$Q_C$ stationary particle | Selected static dimensionless groups, charge, domain, boundary data, gauge condition, and converged coupled solution | Basin change, charge leakage, boundary failure, or instability in the second variation | Action and Gauss constraint Derived conditionally; coefficient point, background, and spectrum unselected |
| Open endpoint population circuit | Positive rates satisfying (EL32) | Rate imbalance, donor depletion, or bath change | Absolute rates given conditionally by (EL33) |
| Open endpoint coherence | External coherent support | Undriven decay $\dot c=-\gamma_vc/2$ | Half the local donor-jump rate |

### 7.2 Phase-slip boundary

On the stable coherent branch, the phase curvature (EL21) controls the local
endpoint restoring force. As $|\mathcal J_Q|\to\mathcal J_{c,v}$,

$$
\cos(\vartheta-\alpha_v)\to0,
\qquad
K_{\delta,v}\to0.
\tag{EL57}
$$

A fluctuation can then cross the phase barrier. Computing its rate requires the
endpoint inertia or first-order kinetics, damping kernel, noise covariance, and
barrier profile. None is selected by the capacity bound.

### 7.3 Localization decay boundary

The radius relation is an existence and local-curvature result for one reduced
profile family. A physical lifetime additionally requires:

1. the full stationary field solution;
2. the spectrum of gauge, endpoint, amplitude, composition, and shape modes;
3. a declared bath or quantum fluctuation measure;
4. the topology-changing path when $m$ or $N_G$ changes;
5. a map from the solution to physical energy and observed particle channels.

The present endpoint completion supplies no proton decay rate. The Mapped value
$\mathfrak s_p$ and the conditional current coefficient cannot determine that
rate.

---

## 8. Reduction and evidence boundary

### 8.1 Dormant limit

When

$$
\Upsilon_v=0,
\qquad
\gamma_v=0,
\qquad
\mathcal J_{\mathfrak s}=0,
\qquad
B_A=0,
\tag{EL58}
$$

the endpoint sectors contribute zero to the canonical local bulk equation.
This is the neutral reduction already required by
`foundations/geometric-manifold-completion.md`.

A neutral-input receipt establishes only the dormant limit. It supplies no
evidence for the active endpoint field, active bath, current capacity,
localized solution, or defect sector.

### 8.2 Present evidential status

The gauge transformations, source cancellation, capacity inequality, Markov
rate ratio, coherence half-rate, cohomology groups, reduced-radius algebra, and
point-core exterior coefficient are executable analytic checks. No numerical
PDE run currently realizes the charged endpoint field, open endpoint channel,
or a finite-energy point defect. The toroidal experiments test different
conservative spatial constructions and do not instantiate (EL9) or (EL28).

No numbered prediction is added to
`predictions/falsifiable-predictions.md`. A physical discriminator requires a
selected endpoint normalization, support sector, solution, and observable map.

---

## 9. Present conclusion

A charge-$-g_Q$ endpoint section supplies the minimal coherent dressing of the
Yang/Yin conversion bilinear. Its frozen-amplitude limit gives the registered
endpoint cosine, its source conserves total Yang-plus-Yin density, and its
critical current yields an explicit coupling threshold. A one-way Lindblad
alternative closes the same population circuit and fixes a conditional
$\varphi$ rate ratio while damping endpoint coherence.

The complete positive coherence fibre has no state-only homotopy protection.
A first Chern number of the compact relative connection survives mixed states,
yet the smooth unexcised object base has no two-cycle that can carry it. A
protected flux sector requires a defect, excision, boundary flux, or different
spatial topology.

The endpoint closure supplies no positive $1/R$ support in the minimal smooth
sector. Point excision and fixed Chern flux give
$\mathcal B_G=2\pi N_G^2\int d\mathfrak s/e_x^2$ and a conditional reduced
radius when $\mathcal B_G>\mathcal D$. The auxiliary adjoint $SU(2)_Q$ branch
supplies a regular local core and matches that exterior coefficient. Its exact
monopole belongs to the decoupled adjoint sector; the registered nonzero
fundamental condensate removes the isolated magnetic sector and confines the
flux. The endpoint current retains mathematical closure at the declared
conditional level and has no selected non-Abelian vertex lift. The separate
source-free particle action defines the coupled fixed-$Q_C$ stationary problem
and Gauss constraint. A selected coefficient point, supported net-zero
particle, its quantum numbers, fluctuation spectrum, and decay rate remain
open physical sectors.

---

## References

- `foundations/geometric-manifold-completion.md`—metric-graph bundle,
  coherence fibre, canonical reduction, and endpoint-gluing boundary
- `foundations/interscale-current-soliton.md`—relative connection, scale
  current, endpoint cosine, mixed curvature, and Derrick profile
- `foundations/point-core-flux-sector.md`—quantized exterior support,
  finite-energy obstruction, and stationary-solver boundary
- `foundations/nonabelian-magnetic-core-boundary.md`—auxiliary smooth core,
  condensate confinement, and persistent-composite boundary
- `computations/magnetic_core_completion_check.py`—BPS profile, matching,
  London, and pair-slope checker
- `foundations/core-trapped-charge-support.md`—conditional conserved-charge
  support, retention boundary, and finite-separation theorem
- `computations/core_trapped_charge_check.py`—support-root, curvature,
  localization, and source-unit checker
- `foundations/particle-stationary-action-closure.md`—source-free temporal
  action, Gauss constraint, stationary equations, and variational boundary
- `computations/particle_action_closure_check.py`—action-algebra and
  nondimensionalization checker
- `foundations/physical-becoming-hierarchy.md`—closed conservative and
  mesoscopic open-system boundary
- `foundations/loop-to-bubble-projection-theorem.md`—positive Yang/Yin Gram
  matrix and coherence ball
- `foundations/string-bubble-projective-map.md`—rank-one projective shell
- `foundations/proton-coherence-budget.md`—proton-facing conditional circuit
  ledger
- `field-experience/toroidal-coherence-survival-report.md`—spatial torus
  survival verdict
- `field-experience/toroidal-connected-hierarchy-report.md`—connected
  hierarchy result
- `computations/endpoint_link_localization_check.py`—endpoint, topology, and
  localization algebra checker
- `computations/point_core_flux_check.py`—point-core flux and support checker

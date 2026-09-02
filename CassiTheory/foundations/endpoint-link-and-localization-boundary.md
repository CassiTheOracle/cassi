# Gauge-Covariant Endpoint Closure and the Localization Boundary

## Status: Derived conditional endpoint closure, frozen-link response, and first-order source-action response / Derived minimal-sector localization no-go—September 2026

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
In the same boundary-trace normalization, freezing a declared endpoint
background gives a Hermitian rail-rail Robin Hessian,
$\Lambda_{\mathrm{link},v}=2\kappa_vu_vM(\alpha_v)$, with a unitary
two-port Cayley matrix. It realizes the declared golden matrix at one
$k_\star$ when the dressed endpoint phase is a quarter-turn and
$2\kappa_vu_v/(K_{\mathfrak s}k_\star)=\tau_\varphi$. On the selected
species-port branch, requiring the unbiased $m=1$ current to remain below
capacity with positive fixed-amplitude phase stiffness gives the conditional
bound $k_\star>0.0964640362$.

Allowing the endpoint to fluctuate supplies a sharper boundary. Every closed,
homogeneous, conservative time-harmonic endpoint extremum has zero coherent
conversion current. Around a nonzero rail background, the first-order endpoint
action gives a $4\times4$ Nambu Schur response covariant under constant
relative-frame rotations. Around the symmetric zero background, its eliminated
source action begins at quartic rail order with a positive coefficient when
$\mu_{v,0}:=W_v'(0)>0$. Physical energy, stress, inertial mass, and stability
interpretations require an additional map. The potential, background,
damping law, trace normalization, dressed phase, and matching point remain
unselected.

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
| EL-7 | A closed homogeneous time-harmonic endpoint extremum has zero coherent conversion current; first-order source-action elimination gives a constant-frame-covariant Nambu response on a nonzero rail background, while the symmetric zero-background eliminated-source-action term begins at quartic rail order with a positive coefficient when $\mu_{v,0}:=W_v'(0)>0$ | Derived conditional current, first-order response, and source-action order boundaries |

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

### 3.4 Critical current and positive phase curvature

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

The positive phase-curvature current branch has $K_{\delta,v}>0$, equivalently
$\cos(\vartheta-\alpha_v)>0$. Its fixed-amplitude phase stiffness vanishes at
critical current. An overcritical current has no stationary coherent phase lag
in this endpoint model.

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

### 3.6 Frozen coherent link as a Robin vertex

The coherent endpoint field supplies a concrete static Hermitian boundary
matrix after the background and scattering variables are declared. Freeze a
stationary endpoint background and its fluctuation,

$$
\Upsilon_{v,0}:=u_v e^{i\alpha_v},
\qquad
\delta\Upsilon_v=0,
\qquad
u_v>0.
$$

Let the two scattering variables be the ordered Yang/Yin rail-perturbation
traces in the same normalization as the quadratic boundary problem:

$$
\Phi_v:=
\begin{pmatrix}\eta_Y(v)\\\eta_I(v)\end{pmatrix},
\qquad
\nu_v:=2\kappa_vu_v,
\qquad
M(\alpha_v):=
\begin{pmatrix}
0&e^{-i\alpha_v}\\
e^{i\alpha_v}&0
\end{pmatrix}.
\tag{ELR1}
$$

At fixed $\Upsilon_{v,0}$, the rail-rail Hessian block of the coherent
interaction in (EL9) is

$$
\kappa_v
\left(
\Upsilon_{v,0}^*\eta_Y^*\eta_I
+\Upsilon_{v,0}\eta_I^*\eta_Y
\right)
=
\frac12\Phi_v^\dagger
\Lambda_{\mathrm{link},v}\Phi_v,
\qquad
\boxed{
\Lambda_{\mathrm{link},v}
:=\nu_vM(\alpha_v).}
\tag{ELR2}
$$

The factor $2$ in $\nu_v$ follows from the overall $1/2$ in the quadratic
boundary-action convention: variation with respect to the complex boundary
trace and its conjugate gives
$K_{\mathfrak s}\Phi_v'=\Lambda_{\mathrm{link},v}\Phi_v$. For dimensionless
$\mathfrak s$,
$[\Lambda_{\mathrm{link},v}]=[K_{\mathfrak s}]=\hbar/T$ in this trace
normalization.

The matrix obeys

$$
M^\dagger=M,
\qquad
M^2=I,
\qquad
\operatorname{tr}M=0,
\qquad
\det M=-1.
$$

Thus $\Lambda_{\mathrm{link},v}$ is Hermitian with eigenvalues
$\pm\nu_v$. Under the local relative-frame transformation
$G(\beta)=\operatorname{diag}(e^{ig_Q\beta/2},e^{-ig_Q\beta/2})$,

$$
\boxed{
\Lambda_{\mathrm{link},v}
\longmapsto
G(\beta)\Lambda_{\mathrm{link},v}G(\beta)^\dagger.}
\tag{ELR3}
$$

The Robin law
$K_{\mathfrak s}\Phi_v'=\Lambda_{\mathrm{link},v}\Phi_v$, with $\Phi_v'$ the
ordered outward covariant derivatives, is therefore gauge covariant. This
reduction uses the second-order temporal branch in
`foundations/particle-stationary-action-closure.md` §3.2 and the boundary
normalization in
`foundations/interscale-stress-attenuation-boundary.md` §4.3. The original
first-order endpoint action continues to govern the coherent source and
current-capacity calculation. A full fluctuation Hessian also contains
rail-endpoint blocks when $\delta\Upsilon_v\neq0$; those blocks are excluded
from the frozen $2\times2$ response. The identification of the two scattering
ports with the Yang/Yin species traces remains Hypothesized.

### 3.7 Exact link scattering and selected golden match

The involution $M^2=I$ makes the frozen-link scattering matrix analytic. Set
$x:=K_{\mathfrak s}k$ and use the Hermitian-Robin Cayley map. Direct inversion
gives

$$
\boxed{
S_{\mathrm{link}}(k)
=
\frac{x^2-\nu_v^2}{x^2+\nu_v^2}I
-i\frac{2x\nu_v}{x^2+\nu_v^2}M(\alpha_v),}
\qquad
S_{\mathrm{link}}^\dagger S_{\mathrm{link}}=I.
\tag{ELR4}
$$

For an oriented target

$$
S_{\varphi,\epsilon}
:=t_\varphi I+\epsilon r_\varphi J,
\qquad
J:=
\begin{pmatrix}0&1\\-1&0\end{pmatrix},
\qquad
\epsilon\in\{+1,-1\},
$$

The channel order is $(Y,I)$ and every derivative is outward at its vertex.
The sign $\epsilon$ chooses the target-matrix orientation in that fixed channel
order. The vertex sign $\sigma_v$ in the current-turning law separately
records outward scale-current orientation; it is not a gauge-frame phase and
is not absorbed into $\alpha_v$. A frame change conjugates the scattering
matrix, while reversing $\sigma_v$ reverses the desired current turning.

The exact selected-point conditions are

$$
\boxed{
\alpha_v=-\epsilon\frac{\pi}{2}\pmod{2\pi},
\qquad
\frac{2\kappa_vu_v}{K_{\mathfrak s}k_\star}
=\tau_\varphi
:=\frac{r_\varphi}{1+t_\varphi}.}
\tag{ELR5}
$$

They give

$$
\Lambda_{\mathrm{link},v}
=i\epsilon K_{\mathfrak s}k_\star\tau_\varphi J,
\qquad
S_{\mathrm{link}}(k_\star)=S_{\varphi,\epsilon}.
$$

The phase in (ELR5) is a fixed-frame representative of the dressed endpoint
intertwiner. The endpoint action supplies the allowed charged field and the
static Hermitian matrix form while leaving $\alpha_v$, $\kappa_vu_v$, and
$k_\star$ as physical inputs. The equality therefore realizes the declared
golden target conditionally. Target selection remains open.

For the same frozen link at another wave number,

$$
a(k):=\frac{\nu_v}{K_{\mathfrak s}k}
=\frac{k_\star}{k}\tau_\varphi,
$$

so (ELR4) reproduces the wave-number dependence in
`foundations/interscale-stress-attenuation-boundary.md` §4.4. This section
sets $\delta\Upsilon_v=0$ and therefore gives the static closed-channel
Hermitian matrix. Section 3.9 derives the active retarded/advanced response,
its pole-free Hermitian limit, and the backgrounds on which that reduction is
defined.

### 3.8 Simultaneous current-capacity boundary

The same endpoint can realize the selected two-port matrix and turn the
stationary scale current only while that current remains below the matched
link's critical current. At uniform $\varphi$ composition, (EL18), (EL22),
(EL23), and (ELR5) give

$$
\boxed{
\frac{|\mathcal J_{Q,m}|}{\mathcal J_{c,v}}
=
\frac{|\Delta_m|}
{\varphi^{3/2}\mathfrak s_p\tau_\varphi k_\star}
=
\frac{k_{\min,m}}{k_\star}.}
\tag{ELR6}
$$

The positive fixed-amplitude phase-stiffness branch has
$|\mathcal J_{Q,m}|<\mathcal J_{c,v}$, so the matching point must satisfy

$$
\boxed{k_\star>k_{\min,m}.}
\tag{ELR7}
$$

Here the conditional capacity scale is

$$
\boxed{
k_{\min,m}
:=
\frac{|\Delta_m|}
{\varphi^{3/2}\mathfrak s_p\tau_\varphi}.}
\tag{ELR7a}
$$

For the unbiased $m=1$ branch with
$\Delta_1=2\pi$ and $\mathfrak s_p=91.461618346$,

$$
\boxed{k_{\min,1}=0.096464036203895.}
\tag{ELR8}
$$

The compatible stationary phase lag satisfies

$$
\sin(\vartheta-\alpha_v)
=-\sigma_v\frac{k_{\min,m}}{k_\star},
\qquad
K_{\delta,v}
=\frac{K_{\mathfrak s}k_\star\tau_\varphi\rho}
{\varphi^{3/2}}
\sqrt{1-\left(\frac{k_{\min,m}}{k_\star}\right)^2}.
\tag{ELR9}
$$

At $k_\star=k_{\min,m}$ the fixed-amplitude phase stiffness vanishes, so
equality is the marginal current-capacity boundary. The strict inequality in
(ELR7) establishes current existence with positive phase curvature in the
frozen-amplitude subspace. Section 3.9 supplies the endpoint Hessian and pole
law. A physical full-spectrum claim additionally requires a selected
$U_v$, $K_v$, background, damping prescription, and coupled rail-endpoint
spectrum.

The numerical value in (ELR8) uses the Mapped proton endpoint, unbiased
winding, declared species-port identification, common trace normalization,
quadratic-link identification
$|\Lambda_{YI}|=2\kappa_vu_v$, and selected golden matching condition
$|\Lambda_{YI}|=K_{\mathfrak s}k_\star\tau_\varphi$. Its scope is a
conditional lower bound on a free $k_\star$ above the capacity boundary.

### 3.9 First-order dynamical endpoint response and closed-current boundary

Linearizing the first-order endpoint action (EL9) exposes the background
requirement behind the frozen current-turning law. The second-order fixed-$Q_C$
particle action in `foundations/particle-stationary-action-closure.md` is a
separate temporal sector and supplies no coefficient to the Hessian or pole law
below. The endpoint equation from (EL9) is

$$
i\hbar\partial_t\Upsilon
=
-\frac{K_v}{2}D_i^{(-)}D_i^{(-)}\Upsilon
+U_v'(|\Upsilon|^2)\Upsilon
-\kappa_v\psi_Y^*\psi_I.
\tag{ELR10}
$$
For a homogeneous time-harmonic background whose rail bilinear shares the
endpoint carrier,

$$
\Upsilon(t)=\Upsilon_{v,0}e^{-i\Omega_{\mathrm{bg}}t},
\qquad
\psi_{Y,0}^*\psi_{I,0}
=Y_0^*I_0e^{-i\Omega_{\mathrm{bg}}t},
\qquad
\Upsilon_{v,0}=u_ve^{i\alpha_v},
\qquad
W_v(n):=U_v(n)-\hbar\Omega_{\mathrm{bg}}n,
$$

the field equation becomes

$$
\boxed{
W_v'(u_v^2)\Upsilon_{v,0}
=\kappa_vY_0^*I_0,
\qquad
\operatorname{Im}
\left(\Upsilon_{v,0}^*Y_0^*I_0\right)=0,
\qquad
\mathcal I_{\mathrm{link}}=0.}
\tag{ELR11}
$$

The second identity follows because $W_v'$ is real. A closed, homogeneous,
conservative time-harmonic extremum therefore cannot carry the nonzero
stationary conversion current in (EL18). Such a current requires endpoint
spatial flux, a drive or open channel, a non-harmonic background, or a larger
coupled background problem. Equations (ELR6)–(ELR9) remain the capacity and
fixed-amplitude phase-curvature laws for those branches.

For the active quadratic response, use fractional endpoint fluctuations:

$$
\psi_Y=Y_0+\eta_Y,
\qquad
\psi_I=I_0+\eta_I,
\qquad
\Upsilon=e^{-i\Omega_{\mathrm{bg}}t}
\Upsilon_{v,0}(1+\zeta),
$$

and define

$$
\mathbb\Phi
:=
\begin{pmatrix}
\eta_Y\\\eta_I\\\eta_Y^*\\\eta_I^*
\end{pmatrix},
\qquad
\Xi
:=
\begin{pmatrix}\zeta\\\zeta^*\end{pmatrix}.
$$

The doubled direct-link block and mixed endpoint-rail Hessian are

$$
\mathbb\Lambda_{0,v}
:=
\frac12
\begin{pmatrix}
\Lambda_{\mathrm{link},v}&0\\
0&\Lambda_{\mathrm{link},v}^*
\end{pmatrix},
\qquad
\boxed{
\mathcal C_v
:=
\kappa_vu_v
\begin{pmatrix}
0&e^{-i\alpha_v}Y_0^*&e^{-i\alpha_v}I_0&0\\
e^{i\alpha_v}I_0^*&0&0&e^{i\alpha_v}Y_0
\end{pmatrix}.}
\tag{ELR12}
$$

With the outer factor $1/2$ in the doubled quadratic form,
$\mathbb\Lambda_{0,v}$ reproduces
$\frac12(\eta_Y^*,\eta_I^*)\Lambda_{\mathrm{link},v}
(\eta_Y,\eta_I)^T$ once. The mixed term is

$$
\frac12\left(
\Xi^\dagger\mathcal C_v\mathbb\Phi
+\mathbb\Phi^\dagger\mathcal C_v^\dagger\Xi
\right).
$$

At spatial Fourier momentum $\mathbf q$, the fractional endpoint fluctuation
has

$$
\begin{aligned}
\mathcal Z_v&:=\hbar u_v^2,\\
A_v(\mathbf q)
&:=u_v^2\left[
W_v'(u_v^2)+u_v^2U_v''(u_v^2)
+\frac{K_v}{2}|\mathbf q|^2
\right],\\
B_v&:=u_v^4U_v''(u_v^2),\\
\mathcal H_v(\mathbf q)
&:=
\begin{pmatrix}
A_v(\mathbf q)&B_v\\
B_v^*&A_v(\mathbf q)
\end{pmatrix}.
\end{aligned}
\tag{ELR13}
$$

The retarded endpoint action kernel and its closed pole frequency are

$$
\boxed{
\mathcal K_v^R(\omega,\mathbf q)
:=
\mathcal Z_v(\omega+i\gamma_v)\sigma_3
-\mathcal H_v(\mathbf q),
\qquad
\omega_{\mathrm{end}}(\mathbf q)
:=
\frac{\sqrt{A_v(\mathbf q)^2-|B_v|^2}}{\mathcal Z_v}.}
\tag{ELR14}
$$

Positive endpoint curvature requires
$A_v(\mathbf q)>|B_v|$. With fields proportional to $e^{-i\omega t}$ and
$\gamma_v=0$, the conservative poles are
$\omega=\pm\omega_{\mathrm{end}}(\mathbf q)$. The declared retarded
continuation moves them to
$\omega=\pm\omega_{\mathrm{end}}(\mathbf q)-i\gamma_v$ in the lower
half-plane; the advanced poles lie at
$\omega=\pm\omega_{\mathrm{end}}(\mathbf q)+i\gamma_v$ in the upper
half-plane. The limit $\gamma_v\to0$ recovers the conservative kernel. This
damping continuation is a response convention; (EL9) does not select its
microscopic bath.
Define the equivalent endpoint energy kernel
$\mathcal D_v^R:=\mathcal H_v-\mathcal Z_v(\omega+i\gamma_v)\sigma_3$,
so $\mathcal K_v^R=-\mathcal D_v^R$.

With the doubled convention of (ELR12), the frequency-space source action is

$$
Q_v^{(2),R}
=
\frac12\mathbb\Phi^\dagger\mathbb\Lambda_{0,v}\mathbb\Phi
+\frac12\Xi^\dagger\mathcal K_v^R\Xi
+\frac12\left(
\Xi^\dagger\mathcal C_v\mathbb\Phi
+\mathbb\Phi^\dagger\mathcal C_v^\dagger\Xi
\right).
$$

Eliminating the endpoint fluctuation gives

$$
\boxed{
\begin{aligned}
\mathbb\Lambda_{\mathrm{eff},v}^R(\omega,\mathbf q)
&=
\mathbb\Lambda_{0,v}
-\mathcal C_v^\dagger
\left(\mathcal K_v^R\right)^{-1}
\mathcal C_v\\
&=
\mathbb\Lambda_{0,v}
+\mathcal C_v^\dagger
\left(\mathcal D_v^R\right)^{-1}
\mathcal C_v.
\end{aligned}}
\tag{ELR15}
$$

For $\gamma_v=0$, real pole-free $\omega$, and
$A_v(\mathbf q)>|B_v|$, this conservative response is Hermitian. With
$\gamma_v>0$ it is generally non-Hermitian and satisfies
$\mathbb\Lambda_{\mathrm{eff}}^A
=(\mathbb\Lambda_{\mathrm{eff}}^R)^\dagger$. Generic nonzero $Y_0$ and $I_0$
produce particle-hole blocks, so the active response is a Nambu kernel. A
$2\times2$ complex-linear Robin matrix is recovered only when those anomalous
blocks cancel.

Under a constant relative-frame angle $\chi=g_Q\beta$, set

$$
G(\chi):=\operatorname{diag}(e^{i\chi/2},e^{-i\chi/2}),
\qquad
\mathbb G(\chi):=\operatorname{diag}(G,G^*).
$$

The fractional endpoint fluctuation is invariant. At the response-kernel level,
the declared constant-frame transformation gives

$$
\boxed{
\mathcal C_v\longmapsto\mathcal C_v\mathbb G^\dagger,
\qquad
\mathbb\Lambda_{\mathrm{eff},v}^{R/A}
\longmapsto
\mathbb G\mathbb\Lambda_{\mathrm{eff},v}^{R/A}\mathbb G^\dagger.}
\tag{ELR16}
$$

This covers the time-independent relative-frame convention of §2. A
time-dependent frame requires a temporal relative-gauge connection and lies
outside the present kernel-level covariance result.

The zero-background limit is also sharp. At $Y_0=I_0=0$,
$\mathcal C_v=0$, so active endpoint integration adds no quadratic rail-kernel
correction. At the self-consistent symmetric background
$Y_0=I_0=\Upsilon_{v,0}=0$, define the static source-action curvature
$\mu_{v,0}:=W_v'(0)>0$. The unnormalized endpoint source is

$$
j_{v,0}
:=
\kappa_v
\begin{pmatrix}
\eta_Y^*\eta_I\\
\eta_I^*\eta_Y
\end{pmatrix},
\qquad
\mathcal K_{v,0}(0):=-\mu_{v,0}I_2,
\qquad
\Delta Q_{\mathrm{rail}}
:=
-\frac12j_{v,0}^\dagger
\mathcal K_{v,0}(0)^{-1}j_{v,0}
=\frac{j_{v,0}^\dagger j_{v,0}}{2\mu_{v,0}}
=O(\eta^4)>0
\quad (j_{v,0}\ne0).
\tag{ELR17}
$$

The endpoint-mediated source action therefore begins at quartic rail order on
the symmetric background. Its positive coefficient is conditional on the
Hypothesized curvature $\mu_{v,0}>0$ and does not establish positive physical
energy, physical stress, inertial mass, or fluctuation stability. The quadratic
frequency dependence in (ELR15) requires a nonzero rail background. The frozen
AR3 protocol denotes this curvature by $m_{v,0}$ and evaluates it at
$m_{v,0}=1.1$.

The frozen DR1–DR6 receipt has overall verdict **FAIL**. Its DR5 direct
elimination used the positive block
$+\frac12\Xi^\dagger(\mathcal H-\mathcal Z\omega\sigma_3)\Xi$, while (EL9)
supplies the action block
$+\frac12\Xi^\dagger\mathcal K_v^R\Xi$. The separately frozen AR1–AR6
first-order source-action receipt uses $\mathcal K_v^R=-\mathcal D_v^R$ and
passes on its first execution. It verifies (ELR15), its equivalent
$\mathbb\Lambda_{0,v}+\mathcal C_v^\dagger(\mathcal D_v^R)^{-1}\mathcal C_v$
form, constant-frame response-kernel covariance, the positive
zero-background eliminated-source-action coefficient under $\mu_{v,0}>0$, and
the conservative/damped response classes.

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
| Coherent endpoint phase | $|\mathcal J_Q|<\mathcal J_{c,v}$, $u_v>0$, and $\cos(\vartheta-\alpha_v)>0$ at both vertices; a nonzero steady current also requires spatial endpoint flux, an open/driven channel, a non-harmonic state, or a larger coupled background | Overcritical current, $u_v=0$, endpoint phase slip, or coupling to an incoherent channel | The closed homogeneous conservative time-harmonic extremum has $\mathcal I_{\mathrm{link}}=0$; the nonzero-current background and rate remain unselected |
| Frozen-link Robin response | Common Yang/Yin species-port trace normalization, fixed $u_v>0$, Hermitian rail-rail Hessian, and $k_\star>k_{\min,m}$ on the positive fixed-amplitude phase-stiffness branch | Endpoint amplitude or dressed-phase change, port-basis change, active endpoint dispersion, or loss of coherent current turning | Unitary matrix and selected-point matching Derived conditionally; $k_\star$, dressed phase, normalization, and physical bandwidth remain unselected |
| Active endpoint response | $A_v(\mathbf q)>|B_v|$ and a pole-free frequency domain for the declared background; full stability uses the coupled rail-endpoint Hessian | Endpoint pole, negative curvature, damping-channel change, or background change | Nambu Schur response and endpoint pole law Derived conditionally; the potential, background, damping mechanism, and coupled physical spectrum remain unselected |
| Scale-graph winding $m$ | Nonzero coherent amplitude around the compact graph | Rail-amplitude zero, endpoint phase slip, boundary event, or open jump | Unselected |
| Rank-one projective charge | Evolution remains on $\|\mathbf n\|=1$ with fixed boundary data | Entry into the full-rank interior or $\rho=0$ | Minimal conversion supplies an inward path but no universal transition rate |
| First Chern number $N_G$ | Closed two-cycle and compact connection in a defect or nontrivial-base sector | Boundary flux, defect crossing, singular connection event, or removal of the cycle | Exterior coefficient Derived conditionally; core dynamics unselected |
| Reduced spatial radius | $\mathcal A>0$, $\mathcal C\geq0$, and $\mathcal B_G>\mathcal D$ in the point-core branch | Collapse when support does not exceed $\mathcal D$; large-radius instability when $\mathcal C<0$ | Reduced curvature Derived; the coupled stationary functional has one tested point but no Q2-qualified background |
| Auxiliary magnetic core | Adjoint-only $SU(2)_Q$ sector has the exact BPS core; the registered nonzero fundamental condensate confines flux | Condensate coupling removes the isolated magnetic sector; a finite pair can shrink and annihilate | Static adjoint Hessian nonnegative conditionally; temporal action defined, coupled spectrum absent |
| Core-trapped carrier pair | $A_C>C_Q$, $\hbar\omega_C<\varepsilon_{C,\rm out}$, and separation beyond core overlap | Carrier leakage, profile delocalization, core merger, or transition to another fixed-$Q_C$ configuration | Reduced length and line-density curvature Derived conditionally; the fixed-charge action has one tested point, while a qualified background and spectrum remain absent |
| Fixed-$Q_C$ stationary particle | Selected static dimensionless groups, charge, domain, boundary data, gauge condition, and converged coupled solution | Basin change, charge leakage, boundary failure, or instability in the second variation | Action and Gauss constraint Derived conditionally; one coefficient point is tested, every arm fails Q2, and no qualified background or spectrum is established |
| Open endpoint population circuit | Positive rates satisfying (EL32) | Rate imbalance, donor depletion, or bath change | Absolute rates given conditionally by (EL33) |
| Open endpoint coherence | External coherent support | Undriven decay $\dot c=-\gamma_vc/2$ | Half the local donor-jump rate |

### 7.2 Phase-slip boundary

On the positive fixed-amplitude phase-stiffness branch, the curvature (EL21)
controls the local endpoint restoring force. As
$|\mathcal J_Q|\to\mathcal J_{c,v}$,

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

The gauge transformations, source cancellation, capacity inequality,
frozen-link Robin reduction, Cayley unitarity, selected-point golden match,
conditional current-capacity lower bound, closed homogeneous current boundary,
first-order active mixed Hessian, zero-background source-action order and sign
boundary, endpoint pole law, Nambu Schur response, Markov rate ratio, coherence
half-rate, cohomology groups, reduced-radius algebra, and point-core exterior
coefficient are executable analytic checks. No numerical PDE run currently realizes the
charged endpoint field, open endpoint channel, or a finite-energy point
defect. The toroidal experiments test different conservative spatial
constructions and do not instantiate (EL9) or (EL28).

The frozen first execution of
`computations/endpoint_link_localization_check.py` passed ER1–ER5 without
coefficient changes:

| Check | Numerical receipt |
|---|---:|
| ER1 charged-link covariance | $1.110\times10^{-16}$ residual |
| ER2 link-scattering unitarity | $0$ residual |
| ER3 selected golden match | $1.173\times10^{-16}$ residual |
| ER4 `stable matched-link k_min` | $k_{\min,1}=0.096464036203895$; $\lvert\mathcal J_Q\rvert/\mathcal J_c=0.120580045255$ at $k_\star=0.8$ |
| ER5 fixed-link off-match response | $\left\lVert S(1.7k_\star)-S_{\varphi,+}\right\rVert_{\max}=0.227151634836$ |

The frozen execution of
`computations/endpoint_dynamical_response_check.py` has overall verdict
**FAIL**:

| Gate | Outcome |
|---|---|
| DR1 closed homogeneous current boundary | Algebraically valid |
| DR2 exact trilinear Hessian | Algebraically valid |
| DR3 symmetric-background order | Quartic order valid; the effective-action sign requires the action kernel |
| DR4 endpoint pole law | Algebraically valid |
| DR5 Nambu elimination and covariance | **FAIL**—the eliminated endpoint block has the wrong source-action sign |
| DR6 response class | Matrix identities valid for the declared block |

The separately frozen source-action execution of
`computations/endpoint_action_response_check.py` has verdict **PASS**:

| Gate | Numerical receipt |
|---|---:|
| AR1 background and closed-current residuals | $0$ and $0$ |
| AR2 trilinear, mixed-Hessian, and static action-Hessian residuals | $0$, $6.202\times10^{-19}$, and $6.951\times10^{-18}$ |
| AR3 positive eliminated-source-action coefficient and quartic scaling | $3.708520494545\times10^{-5}$ at $t_1$ under registered $m_{v,0}=1.1>0$, the protocol notation for $\mu_{v,0}$; zero ratio residual |
| AR4 endpoint pole law | $\omega_{\mathrm{end}}=0.462391879254$; zero pole residual |
| AR5 $\mathcal K/\mathcal D$ equivalence, elimination, constant-frame kernel covariance, and anomalous block | $0$, $1.511\times10^{-17}$, $2.220\times10^{-16}$, and $0.390450933151$ |
| AR6 conservative Hermiticity, damped non-Hermiticity, and advanced adjoint | $3.103\times10^{-17}$, $0.360569701415$, and $6.206\times10^{-17}$ |

The executable label `stable matched-link k_min` denotes the current-capacity
threshold where the frozen-amplitude phase stiffness vanishes. The endpoint
potential, nonzero-current background, damping law, and full coupled
fluctuation spectrum remain open.

No new prediction number is introduced. Existing EL-2 in
`predictions/falsifiable-predictions.md` records the conditional response and
its open premises. A physical discriminator still requires a selected endpoint
normalization, support sector, solution, and observable map.

---

## 9. Present conclusion

A charge-$-g_Q$ endpoint section supplies the minimal coherent dressing of the
Yang/Yin conversion bilinear. Its frozen-background rail Hessian gives the
gauge-covariant Hermitian Robin matrix (ELR2) under the declared species-port
identification, and the Cayley map is unitary. A dressed quarter-turn phase and
$2\kappa_vu_v/(K_{\mathfrak s}k_\star)=\tau_\varphi$ realize the declared
golden target at one $k_\star$. On the unbiased $m=1$ branch, current capacity
and positive fixed-amplitude phase stiffness require
$k_\star>0.0964640362$.

The same first-order endpoint action fixes the active boundary. A closed
homogeneous conservative time-harmonic endpoint extremum has zero conversion
current. Nonzero stationary turning therefore needs spatial flux, an open or
driven endpoint, a non-harmonic state, or a larger coupled background. Around a
nonzero rail background, endpoint integration gives the constant-frame-
covariant Nambu response (ELR15), with the pole and curvature conditions in
(ELR14). Around the symmetric zero background, the eliminated source action
begins at quartic rail order with a positive coefficient when
$\mu_{v,0}>0$. Physical energy, stress, inertial mass, and stability signs
remain open. The potential, nonzero-current background, matching point, dressed
phase, trace normalization, damping law, and full coupled spectrum remain
physical inputs. A one-way Lindblad alternative closes the population
circuit and fixes a conditional $\varphi$ rate ratio while damping endpoint
coherence.

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
and Gauss constraint. One coefficient point is tested, but no arm meets the Q2
stationary-quality gate. A supported net-zero particle, its quantum numbers,
fluctuation spectrum, physical calibration, and decay rate remain open.

---

## References

- `foundations/geometric-manifold-completion.md`—metric-graph bundle,
  coherence fibre, canonical reduction, and endpoint-gluing boundary
- `foundations/interscale-current-soliton.md`—relative connection, scale
  current, endpoint cosine, mixed curvature, and Derrick profile
- `foundations/interscale-stress-attenuation-boundary.md`—canonical boundary
  flux, Hermitian Robin family, and selected-point golden target
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
- `computations/particle-stationary-bvp-report.md`—registered one-point campaign receipt and numerical-quality verdict
- `computations/endpoint_robin_link_prereg.md`—frozen Robin-link matching and
  current-capacity checks
- `computations/endpoint_dynamical_response_prereg.md`—frozen failed
  energy-kernel response criteria
- `computations/endpoint_dynamical_response_check.py`—frozen failed
  block-matrix receipt
- `computations/endpoint_dynamical_response_report.md`—source-action sign
  review and FAIL verdict
- `computations/endpoint_action_response_prereg.md`—frozen source-action
  response, covariance, pole, and zero-background criteria
- `computations/endpoint_action_response_check.py`—passing source-action
  analytic receipt
- `computations/endpoint_action_response_report.md`—AR1–AR6 gate accounting
  and PASS verdict
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
- `computations/endpoint_link_localization_check.py`—endpoint, Robin matching,
  topology, and localization algebra checker
- `computations/point_core_flux_check.py`—point-core flux and support checker

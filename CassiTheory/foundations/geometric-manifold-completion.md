# Cassi Geometric Manifold Completion Ansatz

## Status: Hypothesized completion ansatz / Derived canonical reduction and conditional fibre geometry / Tested one-point stationary campaign—September 2026

## Abstract

This document supplies one minimal geometric completion ansatz that places the
canonical Cassi densities, the loop-coherence projection, the projective bubble
geometry, and the conditional interscale current in one compatible bundle. The
result is a stratified metric-graph bundle with distinct smooth strata and
dynamical blocks.

The physical base remains selected time and three-space. Scale is represented
by the logarithmic coordinate

$$
\mathfrak s=\log_\varphi\!\left(\frac{\ell}{\ell_\star}\right).
$$

A compact object sector uses two oriented scale rails over a finite interval.
Their endpoints are glued crosswise, producing a metric circle whose Yang rail
runs outward through scale and whose Yin rail returns. The open position-scale
stratum carries a rank-two Yang/Yin bundle; endpoint gluing selects matched
vertex fibres. Its positive Hermitian coherence
cone contains the canonical real-density pair as the diagonal subcone, the
loop-derived Bloch ball as its normalized section, and the conditional
$\mathbb{CP}^1$ shell as its rank-one boundary. The affine bubble map is an
observation map from this common fibre.

The conservative interscale action remains a Hypothesized sector. Canonical
$q$-gated conversion remains mesoscopic open-system dynamics. A minimal
completely positive conversion lift reproduces the canonical population
operator exactly on the diagonal and fixes one additional conditional result:
in the undriven lift, transverse Yang/Yin coherence decays at half the
composition-relaxation rate. Maintaining a projective shell therefore requires
an identified coherent drive, protected carrier sector, or reservoir structure.

The ansatz adds a normalized scale-graph metric, endpoint gluing maps, a
positive coherence fibre, and a declared open-system lift. A charged coherent
endpoint section and a one-way Markov vertex channel supply two conditional
realizations of the gluing in
`foundations/endpoint-link-and-localization-boundary.md`. Their physical
normalization, the scale metric, endpoint microphysics, observation map, and
decay rate remain unselected. The smooth zero-Chern endpoint sector has no
finite Derrick radius. Point-core Chern flux supplies a conditional exterior
$1/R$ coefficient. An auxiliary adjoint $SU(2)_Q$ branch smooths that core and
matches its flux. The registered nonzero fundamental condensate removes the
isolated magnetic sector and confines flux; its finite pair has no
finite-separation minimum in the registered branch. A neutral core carrier
supplies one conditional reduced support branch under explicit charge,
retention, and matching inequalities
(`foundations/core-trapped-charge-support.md`). The separate source-free
temporal action combines the charged and carrier sectors, derives Gauss's law,
and defines the fixed-$Q_C$ stationary variational problem
(`foundations/particle-stationary-action-closure.md`). One registered
coefficient point is tested; all twelve primary/domain arms fail Q2, so no
qualified stationary solution is established.

---

## 1. Result and dependency boundary

### 1.1 Existing inputs

The completion uses five source structures with their current statuses:

1. **Canonical real-density dynamics.** The primary state is
   $(E_Y,E_I)\in\mathbb R_{\ge0}^2$ with
   $\rho=E_Y+E_I$, $\varepsilon=E_Y-\varphi E_I$, canonical $q$, and
   rank-one conversion (`foundations/cassi-first-principles.md`).
2. **Mesoscopic open-system form.** Canonical conversion is a
   positive-semidefinite gradient flow with an optional Markovian bath and
   MSRJD response functional (`foundations/physical-becoming-hierarchy.md`
   §4).
3. **Loop-coherence projection.** A shared-support carrier state defines a
   positive $2\times2$ species Gram matrix whose normalized Bloch vector fills
   the affine bubble volume
   (`foundations/loop-to-bubble-projection-theorem.md`).
4. **Projective shell geometry.** A normalized complex Yang/Yin pair gives
   $\mathbb{CP}^1\simeq S^2$, and an affine map sends that sphere to the
   declared quadratic bubble shell
   (`foundations/string-bubble-projective-map.md`).
5. **Conditional interscale dynamics.** A complex Yang/Yin doublet on a
   continuous scale coordinate carries conservative spatial and scale currents
   and admits a conditional mixed-curvature force
   (`foundations/interscale-current-soliton.md`).

The completion preserves the status of every input. It supplies explicit maps
between them and introduces the assumptions listed next.

### 1.2 Added assumptions

| Added structure | Minimal choice in this ansatz | Status |
|---|---|---|
| Scale topology | A two-rail metric graph over a finite scale interval | Hypothesized object-sector geometry |
| Scale metric | Flat dimensionless edge metric $d\mathfrak s^2$ | Coordinate normalization; physical scale length remains open |
| Yang/Yin fibre | Positive Hermitian cone $\operatorname{Herm}_2^+$ | Derived compatibility geometry |
| Bulk relative connection | Existing $U(1)_Q$ connection generated by $\sigma_3/2$ | Hypothesized physical field |
| Endpoint closure | Gauge-covariant cross-rail intertwiners represented by flux-unitary boundary phases $\delta_-$ and $\delta_+$; charged coherent sections or trace-preserving vertex channels provide conditional realizations | Hypothesized physical endpoint / Derived conditional covariance and source algebra |
| Conversion off the diagonal subcone | Minimal completely positive two-jump lift | Hypothesized lift / exact canonical diagonal reduction |
| Reservoir | Reduced Markovian conversion environment | Required physical completion; microscopic identity open |
| Bubble observation | Existing affine map $\mathbf X=D\mathbf n$ | Derived map between declared geometries; physical identification open |

No additional numerical constant is fixed. Endpoint phases, scale stiffness,
scale tension, gauge normalization, bath normalization, and physical scale
measure retain their existing open status.

### 1.3 Completion object

The complete ansatz is the tuple

$$
\boxed{
\mathfrak G_{\rm C}
:=
\left(
X_4,
I_{\mathfrak s},
\widetilde I_{\mathfrak s},
V,
\mathcal C_2^+,
B_A,
S_-,S_+,
S_{\rm cons},
\mathcal L_{\rm conv},
\mathcal P_D
\right).
}
\tag{GM1}
$$

Here:

- $X_4=\mathbb R_t\times M_3$ is the selected evolution-time and physical
  three-space base;
- $I_{\mathfrak s}$ is a finite interval in logarithmic scale;
- $\widetilde I_{\mathfrak s}$ is its two-rail metric-graph cover;
- $V$ is the Yang/Yin complex bundle, rank two on the open scale stratum with
  matched endpoint fibres;
- $\mathcal C_2^+=\operatorname{Herm}_2^+$ is the positive coherence cone;
- $B_A$ is the relative connection in the conditional interscale sector;
- $S_\pm$ are endpoint gluing maps;
- $S_{\rm cons}$ is the conservative transport/action sector;
- $\mathcal L_{\rm conv}$ is the mesoscopic open-system conversion sector;
- $\mathcal P_D$ is the affine bubble observation map.

A physical theory must supply dynamics and normalization for every open entry.
Equation (GM1) fixes the geometric bookkeeping and exact reduction contracts.

---

## 2. Physical base and scale graph

### 2.1 Selected physical base

The canonical field lives on

$$
X_4:=\mathbb R_t\times M_3,
\tag{GM2}
$$

where $M_3$ carries the selected spatial metric $h_{ij}$. The canonical PDE is
mesoscopic and nonrelativistic. The optional covariant gravity extension
supplies a Lorentzian metric $g_{\mu\nu}$; the reduction in §7 uses only
evolution time and $h_{ij}$.

### 2.2 Universal scale chart

The dimensionless logarithmic coordinate is

$$
\mathfrak s
:=
\log_\varphi\!\left(\frac{\ell}{\ell_\star}\right),
\qquad
\ell(\mathfrak s)=\ell_\star\varphi^{\mathfrak s}.
\tag{GM3}
$$

The coordinate identity supplies an ordering of dimensionful scales. The
completion chooses the normalized edge metric

$$
ds_{\rm edge}^2=d\mathfrak s^2
\tag{GM4}
$$

for the metric graph. This fixes graph arclength in scale-coordinate units.
The coefficient $K_{\mathfrak s}$ in the conservative action carries the
physical normalization. Equation (GM4) does not identify one unit of
$\mathfrak s$ with a physical spatial distance or proper time.

### 2.3 Finite object interval

For a candidate object with endpoints $\mathfrak s_-$ and $\mathfrak s_+$,
define

$$
I_{\mathfrak s}
:=[\mathfrak s_-,\mathfrak s_+],
\qquad
L_{\mathfrak s}:=\mathfrak s_+-\mathfrak s_->0.
\tag{GM5}
$$

The endpoints are boundary data. A particle calculation must derive or select
them from a stationary solution. For the mapped Planck-to-proton application,

$$
\mathfrak s_-=0,
\qquad
\mathfrak s_+=\mathfrak s_p=91.461618346\ldots.
\tag{GM6}
$$

This value uses the measured proton mass and does not constitute a proton-mass
prediction.

### 2.4 Two-rail spectral cover

Introduce two copies of the interval, labeled $Y$ and $I$, and identify their
corresponding endpoints:

$$
\boxed{
\widetilde I_{\mathfrak s}
:=
\bigl(I_{\mathfrak s}\times\{Y,I\}\bigr)
\Big/
\left[
(\mathfrak s_-,Y)\sim(\mathfrak s_-,I),
\ (\mathfrak s_+,Y)\sim(\mathfrak s_+,I)
\right].
}
\tag{GM7}
$$

The interior projects two-to-one onto physical scale:

$$
\pi_{\mathfrak s}:
\widetilde I_{\mathfrak s}\longrightarrow I_{\mathfrak s},
\qquad
\pi_{\mathfrak s}(\mathfrak s,a)=\mathfrak s.
\tag{GM8}
$$

The rail-exchange involution is

$$
\tau(\mathfrak s,Y)=(\mathfrak s,I),
\qquad
\tau(\mathfrak s,I)=(\mathfrak s,Y).
\tag{GM9}
$$

The graph has two vertices and two edges. Its first Betti number is

$$
\boxed{
b_1=E-V+1=2-2+1=1,
\qquad
\pi_1(\widetilde I_{\mathfrak s})\simeq\mathbb Z.
}
\tag{GM10}
$$

Its total normalized circumference is $2L_{\mathfrak s}$. Orient the Yang edge
from $\mathfrak s_-$ to $\mathfrak s_+$ and the Yin edge in the return
direction. A single trip around the graph is therefore Yang-outward followed by
Yin-return.

This circle is an internal scale circuit. It is distinct from a spatial ring
and from the carrier-loop coordinate $\chi$ in
`foundations/loop-to-bubble-projection-theorem.md`.

### 2.5 Endpoint gluing

Let $\psi_Y$ and $\psi_I$ denote the rail amplitudes in a fixed species frame.
For nonzero stationary rail current, define the flux-normalized boundary traces

$$
a_{a,v}
:=\sqrt{\frac{K_{\mathfrak s}}{\hbar}
\left|\nu_{a,\mathfrak s}(v)\right|}\,\psi_a(v),
\qquad
|a_{a,v}|^2=|J_{a,\mathfrak s}(v)|.
$$

The minimal coherent vertex conditions are

$$
a_{Y,\mathfrak s_-}
:=e^{i\delta_-}a_{I,\mathfrak s_-},
\qquad
a_{I,\mathfrak s_+}
:=e^{i\delta_+}a_{Y,\mathfrak s_+},
\tag{GM11}
$$

with oriented Kirchhoff current conservation

$$
J_{Y,\mathfrak s}(v)
+J_{I,\mathfrak s}(v)=0,
\qquad
v\in\{\mathfrak s_-,\mathfrak s_+\}.
\tag{GM12}
$$

The phase conditions are unitary in the boundary flux norm. They match
incoming and outgoing current magnitudes while allowing the rail densities to
differ. In the uniform $\varphi$ sector,
$E_Y/E_I=\varphi$ and
$|\nu_{I,\mathfrak s}/\nu_{Y,\mathfrak s}|=\varphi$, so the two flux norms
agree. At zero current the boundary phase is inert.

Each occupied endpoint trace reaches exactly one outgoing rail with unit
modulus. This is a phase-only perfect-transfer vertex. Partial
reflection/transmission requires an additional endpoint interaction; the
self-adjoint two-lead family and the coupling required by the declared golden
target are derived in
`foundations/interscale-stress-attenuation-boundary.md` §4.3–§4.4.
Under the conditional species-port trace identification, freezing the charged
endpoint background gives the gauge-covariant rail-rail Hessian
$\Lambda_{\mathrm{link},v}=2\kappa_vu_vM(\alpha_v)$. A dressed quarter-turn
phase and $2\kappa_vu_v/(K_{\mathfrak s}k_\star)=\tau_\varphi$ realize the
declared golden matrix at one selected $k_\star$. Requiring the simultaneous
unbiased proton current to remain below capacity with positive fixed-amplitude
phase stiffness gives the conditional bound $k_\star>0.0964640362$.
The active first-order endpoint Hessian is explicit. Source-action elimination
of the first-order Schrödinger/Berry endpoint action (EL9) gives its Nambu
Schur response around a declared nonzero rail background, with response-kernel
covariance under constant relative-frame rotations. The source-free
second-order particle action remains a separate temporal sector. The endpoint
potential, nonzero-current background, microscopic damping channel, temporal
relative-gauge connection, doubled port-flux law, and full coupled fluctuation
spectrum remain open. The one registered coupled coefficient point therefore
provides a numerical boundary for the declared model, while a physically
qualified particle solution remains open.

The scalar phases in (GM11) are fixed-frame representatives of endpoint
intertwiners. Under a relative $U(1)_Q$ frame change, each $S_v$ must transform
as
$S_v\mapsto g_{\rm out}(v)S_vg_{\rm in}(v)^{-1}$.
Charged endpoint fields can supply the same covariance dynamically. Holding a
raw scalar phase fixed under this transformation explicitly breaks
$U(1)_Q$. The endpoint contribution to the circuit holonomy is the dressed
gauge-invariant composition of these intertwiners; its microscopic dressing
remains open.

Equations (GM11)–(GM12) replace imposed endpoint source terms by a
flux-preserving graph gluing. They are an added boundary assumption. A
physical endpoint may instead require an explicitly resolved mixing field or
a trace-preserving open-system vertex channel.

The charged transition section in
`foundations/endpoint-link-and-localization-boundary.md` realizes the endpoint
intertwiner, frozen-link Robin family, and source-action Nambu response
conditionally. A closed homogeneous conservative time-harmonic endpoint
extremum has zero coherent conversion current. A stationary spatial endpoint
obeys $\nabla\cdot\mathbf J_{\Upsilon,v}=\Gamma_v$. When $K_v>0$ and
$u_v>0$, it carries the positive inverse-Laplacian gradient cost derived in
§3.10 of that paper. Periodic,
no-flux, and sufficiently localized domains require zero integrated
$\Gamma_v$ at each scale vertex, so spatial flux supports compensating local
source-and-sink structure while a nonzero source mean requires boundary flux
or additional endpoint transport. Open or driven channels, non-harmonic
states, and larger coupled backgrounds supply distinct branches. A one-way
Lindblad vertex channel gives a separate gauge-covariant population closure,
with $\gamma_-/\gamma_+=\varphi$ in the uniform circuit state while undriven
endpoint coherence decays.

---

## 3. Rank-two Yang/Yin bundle and coherence cone

### 3.1 Complex species bundle

Over the open scale stratum

$$
\mathcal B^\circ
:=X_4\times(\mathfrak s_-,\mathfrak s_+)
\tag{GM13}
$$

define the rank-two bundle

$$
V^\circ=L_Y\oplus L_I.
\tag{GM14}
$$

Let
$p=\operatorname{id}_{X_4}\times\pi_{\mathfrak s}$ and let $\mathscr L$ be
the complex amplitude line over
$X_4\times\widetilde I_{\mathfrak s}$. On the open edges,
$V^\circ\simeq p_*\mathscr L$: the two preimages of each scale point give the
Yang and Yin components. At each vertex, $S_\pm$ selects the
one-dimensional matching subspace in the two flux-normalized boundary values.
The resulting object is a stratified bundle, rank two on the open edge stratum
and rank one in each matched vertex fibre.
The tuple (GM1) denotes this stratified extension by $V$.

With local frame $\{|Y\rangle,|I\rangle\}$, the complex doublet is a section

$$
\Psi
=
\psi_Y|Y\rangle+\psi_I|I\rangle.
\tag{GM15}
$$

The declared relative $U(1)_Q$ action is

$$
U_Q(\alpha)
=
\exp\!\left(-\frac{i\alpha}{2}\sigma_3\right),
\qquad
\Psi\mapsto U_Q(\alpha)\Psi.
\tag{GM16}
$$

It preserves the fixed Yang/Yin axis selected by the canonical conversion
operator. The completion does not promote arbitrary $U(2)$ species rotations
to gauge redundancy.

### 3.2 Positive Hermitian fibre

The common reduced state is

$$
\boxed{
\Gamma
:=
\begin{pmatrix}
E_Y&c^*\\
c&E_I
\end{pmatrix}
\in\mathcal C_2^+
:=\operatorname{Herm}_2^+.
}
\tag{GM17}
$$

Positivity is equivalent to

$$
E_Y\ge0,
\qquad
E_I\ge0,
\qquad
|c|^2\le E_YE_I.
\tag{GM18}
$$

For $\rho:=\operatorname{tr}\Gamma>0$, write

$$
\widehat\Gamma
:=\frac{\Gamma}{\rho}
=
\frac12\left(\mathbf1+\mathbf n\cdot\boldsymbol\sigma\right),
\tag{GM19}
$$

where

$$
\boxed{
\mathbf n
=
\frac1\rho
\begin{pmatrix}
2\operatorname{Re}c\\
2\operatorname{Im}c\\
E_Y-E_I
\end{pmatrix}.
}
\tag{GM20}
$$

A direct determinant identity gives

$$
\boxed{
\det\Gamma
=
E_YE_I-|c|^2
=
\frac{\rho^2}{4}\left(1-\|\mathbf n\|^2\right).
}
\tag{GM21}
$$

Consequently,

$$
\mathcal C_2^+\setminus\{0\}
\simeq
\mathbb R_{>0}\times B^3,
\tag{GM22}
$$

with the ball collapsed to one cone tip at $\rho=0$. The fibre is stratified:

- $\rho>0$, $\|\mathbf n\|<1$: positive-definite rank-two interior;
- $\rho>0$, $\|\mathbf n\|=1$: rank-one projective boundary;
- $\rho=0$: vacuum cone tip.

### 3.3 Canonical density subcone

The canonical embedding is

$$
\boxed{
\iota_{\rm can}(E_Y,E_I)
:=
\begin{pmatrix}E_Y&0\\0&E_I\end{pmatrix}.
}
\tag{GM23}
$$

It is the diameter

$$
n_x=n_y=0,
\qquad
-1\le n_z\le1
\tag{GM24}
$$

inside each normalized Bloch ball. Define $z:=n_z$. Then

$$
E_Y=\frac\rho2(1+z),
\qquad
E_I=\frac\rho2(1-z).
\tag{GM25}
$$

Using $1+\varphi=\varphi^2$ gives

$$
\boxed{
\varepsilon
=E_Y-\varphi E_I
=\frac{\rho\varphi^2}{2}
\left(z-\varphi^{-3}\right).
}
\tag{GM26}
$$

The canonical equilibrium ray is therefore the fibre coordinate

$$
\boxed{z_\varphi=\varphi^{-3}.}
\tag{GM27}
$$

The canonical diagnostic becomes

$$
q(\rho,z)
=
\frac{\rho^2}
{\rho^2+\varphi^{-2}
+\frac{\rho^2\varphi^4}{4}(z-\varphi^{-3})^2}.
\tag{GM28}
$$

Thus $q$ is a scalar on the canonical diagonal subcone. It does not determine
$n_x$, $n_y$, or the rank of $\Gamma$.

### 3.4 Projective boundary and latitude circle

Rank-one states satisfy

$$
\det\Gamma=0,
\qquad
\|\mathbf n\|=1.
\tag{GM29}
$$

At fixed $\rho$, this boundary is

$$
\partial B^3=S^2\simeq\mathbb{CP}^1.
\tag{GM30}
$$

For canonical populations at $z=z_\varphi$, every rank-one phase-bearing lift
lies on the latitude

$$
\mathcal C_\varphi
=
\left\{
\mathbf n\in S^2:
 n_z=\varphi^{-3}
\right\}.
\tag{GM31}
$$

The canonical equilibrium state itself is the interior point

$$
\widehat\Gamma_{\varphi,\rm can}
=
\begin{pmatrix}
\varphi^{-1}&0\\
0&\varphi^{-2}
\end{pmatrix},
\qquad
\|\mathbf n\|=\varphi^{-3}.
\tag{GM32}
$$

The latitude circle and the canonical equilibrium point have the same diagonal
populations and different transverse coherence. This separates composition
relaxation from phase coherence within one fibre.

### 3.5 Relative action on the fibre

The relative transformation acts by conjugation,

$$
\Gamma\mapsto U_Q(\alpha)\Gamma U_Q(\alpha)^\dagger.
\tag{GM33}
$$

It rotates $(n_x,n_y)$ about the $n_z$ axis and fixes the canonical diagonal
subcone. The relative connection is

$$
\mathcal B_A
:=
\frac{g_Q}{2}B_A\sigma_3,
\qquad
\nabla_A^B\Gamma
:=
\partial_A\Gamma-i[\mathcal B_A,\Gamma].
\tag{GM34}
$$

The projective Berry connection and the dynamical field $B_A$ retain separate
statuses. Equation (GM34) supplies their common $U(1)_Q$ transformation law
without identifying their curvatures.

### 3.6 Loop-carrier moment map

The existing carrier Hilbert space is

$$
\mathcal K
=
L^2(S^1_\chi,d\chi/2\pi)
\otimes\mathbb C^2_{\rm dir}.
\tag{GM35}
$$

For $\psi_Y,\psi_I\in\mathcal K$, define

$$
\mu(\psi_Y,\psi_I)_{ab}
:=
\langle\psi_a,\psi_b\rangle_{\mathcal K}.
\tag{GM36}
$$

Then

$$
\boxed{
\mu:
\mathcal K\oplus\mathcal K
\longrightarrow
\mathcal C_2^+
}
\tag{GM37}
$$

is the Gram moment map used by the loop-to-bubble theorem. Every positive
$2\times2$ Hermitian matrix is the Gram matrix of two vectors in a Hilbert
space of dimension at least two, so (GM37) is surjective. Its inverse image is
many-to-one.

The loop coordinate $\chi$, the relative phase longitude, and the scale-rail
circle remain distinct. Equation (GM37) joins them through a many-to-one
reduced-state map while preserving their separate coordinate meanings.

### 3.7 Affine bubble map and metric compatibility

For the declared positive axis matrix

$$
D=\operatorname{diag}(a_x,a_y,a_z),
\tag{GM38}
$$

define

$$
\boxed{
\mathcal P_D(\Gamma)
:=D\mathbf n(\Gamma).
}
\tag{GM39}
$$

It maps the normalized cone section to

$$
\mathbf X^TD^{-2}\mathbf X\le1.
\tag{GM40}
$$

The rank-one boundary maps to the quadratic shell and the full-rank
interior maps inside it.

The normalized Hilbert–Schmidt metric is

$$
\boxed{
ds_{\rm coh}^2
:=2\operatorname{tr}(d\widehat\Gamma^2)
=d\mathbf n\cdot d\mathbf n.
}
\tag{GM41}
$$

Because $d\mathbf X=D\,d\mathbf n$,

$$
\boxed{
ds_{\rm coh}^2
=d\mathbf X^TD^{-2}d\mathbf X.
}
\tag{GM42}
$$

Thus the coherence-ball metric and the affine bubble pullback metric are the
same normalized metric. On the rank-one shell,

$$
ds_{\rm FS}^2=\frac14d\mathbf n^2
=\frac14ds_{\rm coh}^2,
\tag{GM43}
$$

so the projective Fubini–Study metric, Gram-coherence metric, and affine-shell
metric differ only by the displayed normalization.

This is a metric compatibility among declared geometries. The identification
of $\mathbf X$ with physical position remains Hypothesized.

A spatial bubble lattice, a physical-space shell, and numerical axis choices
for $D$ remain optional geometric ansätze. They are absent from the canonical
PDE and require separate constitutive and observation maps.

---

## 4. Conservative transport and open-system conversion

### 4.1 Conservative sector

On each smooth graph edge, the conditional interscale action has the schematic
form

$$
\begin{aligned}
S_{\rm cons}
:=\int dt\,d^3x\,d\mathfrak s\,\sqrt h\,
\Bigg[
&\frac{i\hbar}{2}
\left(
\Psi^\dagger D_t\Psi
-(D_t\Psi)^\dagger\Psi
\right)
-\frac{K_x}{2}|D_i\Psi|^2\\
&-\frac{K_{\mathfrak s}}{2}|D_{\mathfrak s}\Psi|^2
-V(\Psi)
-\frac{1}{4\mu_Q}G_{AB}G^{AB}
\Bigg].
\end{aligned}
\tag{GM44}
$$

This is the existing Hypothesized conservative extension written on the graph
edges. Its $U(1)_Q$ sector supplies the relative current and mixed curvature.
It separately conserves Yang and Yin in the bulk and therefore does not
reproduce canonical ratio relaxation.

### 4.2 Matrix continuity equation

The completion combines conservative transport and reduced conversion through

$$
\boxed{
\nabla_t^B\Gamma
+\nabla_i^B\mathcal J^i
+\nabla_{\mathfrak s}^B\mathcal J^{\mathfrak s}
=
\mathcal L_{\rm conv}[\Gamma]
+\mathcal L_{\rm end}[\Gamma]
+\Xi.
}
\tag{GM45}
$$

Here:

- $\mathcal J^i$ contains the declared spatial transport;
- $\mathcal J^{\mathfrak s}$ contains the conditional interscale transport;
- $\mathcal L_{\rm conv}$ is the mesoscopic composition bath;
- $\mathcal L_{\rm end}$ is zero on smooth edges and represents a resolved
  endpoint channel when graph gluing alone is insufficient;
- $\Xi$ is a trace-free fluctuation/source term after a bath and normalization
  are selected.

Taking the trace gives

$$
\partial_t\rho
+\nabla_iJ^i
+\partial_{\mathfrak s}J^{\mathfrak s}
=
\operatorname{tr}\mathcal L_{\rm end}
+\operatorname{tr}\Xi,
\tag{GM46}
$$

because the relative commutator and the conversion generator are traceless.
Norm-preserving endpoint gluing and a trace-free bath recover total continuity.

Equation (GM45) is an open-system ansatz outside the variational scope of
$S_{\rm cons}$.

### 4.3 Canonical dissipative block

Let

$$
\gamma_{\rm conv}
:=\lambda(1-q)\ge0.
\tag{GM47}
$$

On the canonical diagonal subcone, the established conversion law is

$$
\frac{D}{Dt}
\begin{pmatrix}E_Y\\E_I\end{pmatrix}_{\!\rm conv}
=
\gamma_{\rm conv}
\begin{pmatrix}
-1&\varphi\\
1&-\varphi
\end{pmatrix}
\begin{pmatrix}E_Y\\E_I\end{pmatrix}.
\tag{GM48}
$$

Equivalently,

$$
\frac{D\rho}{Dt}=0,
\qquad
\frac{D\varepsilon}{Dt}
=-\varphi^2\gamma_{\rm conv}\varepsilon.
\tag{GM49}
$$

This is the positive-semidefinite gradient-flow block derived in
`foundations/physical-becoming-hierarchy.md` §4.2.

### 4.4 Minimal completely positive fibre lift

The canonical PDE does not define the evolution of $c$. One minimal
positivity-preserving extension uses the two directed conversion jumps already
implicit in (GM48):

$$
L_{Y\to I}
:=
\sqrt{\gamma_{\rm conv}}\,|I\rangle\langle Y|,
\qquad
L_{I\to Y}
:=
\sqrt{\varphi\gamma_{\rm conv}}\,|Y\rangle\langle I|.
\tag{GM50}
$$

Define

$$
\boxed{
\mathcal L_{\rm conv}[\Gamma]
:=
\sum_{a\in\{Y\to I,I\to Y\}}
\left(
L_a\Gamma L_a^\dagger
-\frac12\{L_a^\dagger L_a,\Gamma\}
\right).
}
\tag{GM51}
$$

For frozen $q$, this is the minimal time-local completely positive,
trace-preserving generator built only from the two canonical directed
conversion channels. The state dependence of $q$ makes the complete equation
nonlinear while preserving the nonnegative jump rates pointwise.

Writing (GM51) in components gives

$$
\boxed{
\begin{aligned}
\dot E_Y\big|_{\rm conv}
&=-\gamma_{\rm conv}(E_Y-\varphi E_I),\\
\dot E_I\big|_{\rm conv}
&=+\gamma_{\rm conv}(E_Y-\varphi E_I),\\
\dot c\big|_{\rm conv}
&=-\frac{\varphi^2}{2}\gamma_{\rm conv}\,c.
\end{aligned}
}
\tag{GM52}
$$

The first two lines reproduce the canonical conversion exactly. The third is
an added conditional result of this minimal lift. Hamiltonian phase drives,
pure-dephasing channels, correlated jumps, and coherent reservoirs can change
the transverse equation while leaving the diagonal reduction unchanged.

For frozen $q$ with $\gamma_{\rm conv}>0$ and unit trace, the unique
stationary state of the minimal lift is

$$
\boxed{
\widehat\Gamma_{\varphi,\rm can}
=
\begin{pmatrix}
\varphi^{-1}&0\\
0&\varphi^{-2}
\end{pmatrix}.
}
\tag{GM53}
$$

At $\gamma_{\rm conv}=0$, the generator vanishes and every fibre state is
stationary. In the positive-rate undriven sector, the conversion environment
selects the canonical interior point; coherent projective latitude requires
additional support.

### 4.5 Coherence and composition rates

The composition relaxation rate is

$$
\gamma_\varepsilon
=\varphi^2\gamma_{\rm conv},
\tag{GM54}
$$

while the transverse coherence rate in the minimal lift is

$$
\boxed{
\gamma_c
=\frac{\varphi^2}{2}\gamma_{\rm conv}
=\frac12\gamma_\varepsilon.
}
\tag{GM55}
$$

At the canonical reference state with gated conversion,

$$
\gamma_\varepsilon=\frac\lambda3,
\qquad
\boxed{\gamma_c=\frac\lambda6.}
\tag{GM56}
$$

A physical phase-bearing carrier that remains on or near the rank-one shell
must therefore include a coherent source or protection mechanism that offsets
(GM55). The required mechanism is absent from the canonical PDE.

### 4.6 Reservoir and fluctuation boundary

Equation (GM51) is a reduced semigroup generator. A microscopic theory must
identify the traced-out reservoir or auxiliary fields. At the mesoscopic
trajectory level, the compatible density noise, stochastic-calculus convention,
positivity boundary rule, and finite-volume normalization remain those recorded
in `foundations/physical-becoming-hierarchy.md` §4.4.

The diagonal zero-noise limit is the canonical deterministic conversion. A
trajectory-level completion may use the existing equal-and-opposite bath noise

$$
\mathbb B_{\rm TF}
=
\sqrt{\frac{2\gamma_{\rm conv}}{1+\varphi}}
\begin{pmatrix}-1\\1\end{pmatrix},
\tag{GM57}
$$

with reflecting positivity boundaries under that declared normalization. Noise
in the transverse coherence coordinates requires an additional positive
covariance kernel. The manifold does not select it.

### 4.7 Time-lapse branch

Let $N=d\tau/dt$ be a candidate lapse and $K$ an intrinsic kinetic factor. The
canonical conversion trace fixes only

$$
K(q)N(q)=1-q.
\tag{GM58}
$$

The manifold completion retains $N$ as an unselected constitutive field. Two
admissible readings remain:

$$
N=1,
\quad K=1-q,
\tag{GM59a}
$$

and

$$
N=1-q,
\quad K=1.
\tag{GM59b}
$$

The second is the candidate $q$-lapse. Geometry alone does not choose between
them.

---

## 5. Closed scale circuit and holonomy

### 5.1 Current orientation

On the compact rail graph, take

$$
J_{Y,\mathfrak s}=+\mathcal J_Q,
\qquad
J_{I,\mathfrak s}=-\mathcal J_Q.
\tag{GM60}
$$

Then

$$
J_{\mathfrak s}
=J_{Y,\mathfrak s}+J_{I,\mathfrak s}=0,
\qquad
J_Q
=\frac{J_{Y,\mathfrak s}-J_{I,\mathfrak s}}2
=\mathcal J_Q.
\tag{GM61}
$$

The graph interpretation makes this a circulating current on one compact
internal cycle. No net scale-number current crosses either endpoint when the
Kirchhoff conditions hold.

### 5.2 Circuit holonomy

Let $\nu_Y$ and $\nu_I$ be the gauge-invariant rail velocities in the shared
increasing-$\mathfrak s$ coordinate. The symbols $\delta_\pm$ denote the
dressed endpoint contributions represented in the selected frame. The
oriented circuit phase is

$$
\boxed{
\Delta_m
:=
\int_{\mathfrak s_-}^{\mathfrak s_+}
(\nu_Y-\nu_I)\,d\mathfrak s
+\delta_-+\delta_+
=2\pi m,
\qquad m\in\mathbb Z.
}
\tag{GM62}
$$

Equivalently,

$$
\int_{\mathfrak s_-}^{\mathfrak s_+}
(\nu_Y-\nu_I)\,d\mathfrak s
=2\pi m-\delta_{\rm end},
\qquad
\delta_{\rm end}:=\delta_-+\delta_+.
\tag{GM63}
$$

This recovers the compact-circuit condition in
`foundations/interscale-current-soliton.md` §4.5.

### 5.3 Uniform $\varphi$ composition

For $E_Y/E_I=\varphi$, zero total current gives

$$
\nu_I=-\varphi\nu_Y.
\tag{GM64}
$$

On a uniform interval of length $L_{\mathfrak s}$,

$$
\nu_Y
=\frac{\Delta_m}{\varphi^2L_{\mathfrak s}},
\qquad
\nu_I
=-\frac{\Delta_m}{\varphi L_{\mathfrak s}}.
\tag{GM65}
$$

The relative current and circulation energy are

$$
\mathcal J_{Q,m}
=
\frac{K_{\mathfrak s}\rho}
{\hbar\varphi^3L_{\mathfrak s}}
\Delta_m,
\tag{GM66}
$$

$$
\mathscr E_{\rm circ,m}
=
\frac{K_{\mathfrak s}\rho}
{2\varphi^3L_{\mathfrak s}}
\Delta_m^2.
\tag{GM67}
$$

The endpoint, uniformity, and compact-phase assumptions remain conditional.

### 5.4 Length modulus

The graph circumference is a modulus until a scale-tension sector is supplied.
A reduced energy

$$
\mathscr E(L_{\mathfrak s})
=
\mathcal T_{\mathfrak s}L_{\mathfrak s}
+
\frac{K_{\mathfrak s}\rho\Delta_m^2}
{2\varphi^3L_{\mathfrak s}}
+
\mathscr E_{\rm end}
\tag{GM68}
$$

has an interior stationary point only after
$\mathcal T_{\mathfrak s}$ and the endpoint sector are selected. The mapped
proton interval therefore labels one member of the ansatz family, while the
manifold topology leaves its length unselected.

---

## 6. Topology, localization, and the spatial boundary

### 6.1 Scale winding

The compact rail graph has

$$
\pi_1(\widetilde I_{\mathfrak s})\simeq\mathbb Z,
\tag{GM69}
$$

so the circuit phase admits the integer $m$ in (GM62). A change in $m$ requires
a phase-slip event, endpoint-channel event, or vanishing circuit amplitude.
The corresponding transition action and rate remain open.

### 6.2 Projective topology and the coherence interior

The rank-one shell has

$$
\partial B^3\simeq S^2,
\qquad
\pi_2(S^2)\simeq\mathbb Z.
\tag{GM70}
$$

The complete normalized coherence fibre is the ball $B^3$, which is
contractible:

$$
\pi_k(B^3)=0
\qquad(k\ge1).
\tag{GM71}
$$

Therefore a winding defined only on the pure projective shell loses topological
protection when the state enters the full-rank interior. The minimal
conversion lift in (GM52) damps $c$ and moves an undriven pure state inward.
Projective winding can then unwind without forcing $\rho$ to zero.

A topological particle sector must protect purity, carry an independent gauge
flux, impose a boundary condition, or supply another invariant defined beyond
the state fibre. The pure-$CP^1$ obstruction remains valid inside its declared
rank-one sector. The first Chern number of the compact relative connection is
the strongest full-fibre candidate, but the smooth object base
$\mathbb R^3\times S^1_{\mathfrak s}$ has $H^2=0$. A nonzero Chern sector
requires a defect, excision, boundary flux, or different spatial topology
(`foundations/endpoint-link-and-localization-boundary.md` §5).

### 6.3 Mixed-curvature localization

The relative gauge current can source the mixed curvature

$$
G_{i\mathfrak s}
=
\partial_iB_{\mathfrak s}
-\partial_{\mathfrak s}B_i.
\tag{GM72}
$$

Under the restricted static response in
`foundations/interscale-current-soliton.md`, the force density is

$$
f_i
:=\hbar\mathcal I_{\mathfrak s}G_{i\mathfrak s},
\qquad
\mathcal I_{\mathfrak s}=g_QJ_Q.
\tag{GM73}
$$

An inward sign is conditional on the source, response, and boundary data. A
finite spatial radius additionally requires independent flux/core support. In
the smooth unexcised zero-Chern sector, the endpoint completion supplies no
positive $1/R$ term and the Derrick profile has no finite stationary radius.
Point-core Chern flux gives
$\mathcal B_G=2\pi N_G^2\int d\mathfrak s/e_x^2$ and requires
$\mathcal B_G>\mathcal D$, but the present Abelian action cannot smooth the
core or satisfy isolated finite-energy condensate asymptotics
(`foundations/point-core-flux-sector.md`).

### 6.4 Spatial loop boundary

The scale circuit in (GM7) is an internal metric circle. A spatial centerline
$\mathcal C_x\simeq S^1$ would add a second compact cycle and a candidate
product support $\mathcal C_x\times\widetilde I_{\mathfrak s}\simeq T^2$.
This spatial factor is not part of the minimal completion.

The supplied toroidal double-helix experiment has the verified verdict
`DOES NOT EMERGE` for finite-time survival under its tested conservative
Schrödinger–Poisson dynamics. The connected-hierarchy extension has
`INCONCLUSIVE—MIXED LOOP RESPONSE`. Those results constrain spatial-torus
claims and do not test the new metric-graph conversion or mixed-curvature
sectors.

---

## 7. Canonical reduction theorem

### 7.1 Reduction conditions

Take the following neutral limit:

1. restrict to the canonical diagonal section $c=0$;
2. suppress scale dependence and scale current,
   $\partial_{\mathfrak s}\Gamma=0$ and
   $\mathcal J^{\mathfrak s}=0$;
3. set the relative connection to zero, $B_A=0$;
4. exclude endpoint channels from the local bulk equation;
5. choose diagonal spatial currents equal to the canonical advection and
   diffusion fluxes;
6. retain $\mathcal L_{\rm conv}$ with
   $\gamma_{\rm conv}=\lambda(1-q)$;
7. take the zero-noise mesoscopic limit, $\Xi=0$.

Then

$$
\Gamma
=
\begin{pmatrix}E_Y&0\\0&E_I\end{pmatrix}
\tag{GM74}
$$

remains diagonal under (GM51).

### 7.2 Zero-extension identity

Separate the canonical block from every added geometric contribution by
defining

$$
\begin{aligned}
\mathcal R_{\rm ext}
:={}&
(\nabla_t^B-\partial_t)\Gamma
+(\nabla_i^B-\partial_i)\mathcal J^i
+\nabla_{\mathfrak s}^B\mathcal J^{\mathfrak s}\\
&-\mathcal L_{\rm end}[\Gamma]-\Xi.
\end{aligned}
$$

Under conditions 1–5 and 7 in §7.1, every term in
$\mathcal R_{\rm ext}$ vanishes separately. The graph fields, relative
connection, endpoint channel, bath source, transverse coherence, and scale
transport therefore contribute the exact zero operator:

$$
\boxed{
\mathcal R_{\rm ext}=0,
\qquad
\partial_t\Gamma+\partial_i\mathcal J^i
=\mathcal L_{\rm conv}[\Gamma].
}
\tag{GM74a}
$$

The affine bubble map is a readout and contributes no evolution term. Equation
(GM74a) is the zero-extension bookkeeping receipt: switching off every added
sector leaves the pre-existing canonical conversion block unchanged. The
checker evaluates the connection commutators at $B_A=0$, the scale divergence
from zero rail velocities, a zero-rate endpoint channel, and a zero-amplitude
trace-free bath source, then asserts each component separately before
assembling $\mathcal R_{\rm ext}$. The nonzero endpoint and bath operators
remain unspecified, so this receipt verifies their declared neutral inputs and
the canonical reduction, while their active dynamics remain open.

### 7.3 Exact population reduction

The diagonal of (GM45) becomes

$$
\partial_tE_Y+\nabla_iJ_Y^i
=-\lambda(1-q)(E_Y-\varphi E_I),
\tag{GM75}
$$

$$
\partial_tE_I+\nabla_iJ_I^i
=+\lambda(1-q)(E_Y-\varphi E_I).
\tag{GM76}
$$

With the canonical flux choices, these are the canonical two-fluid equations.
Adding them gives total-density continuity; taking the combination
$E_Y-\varphi E_I$ gives

$$
\partial_t\varepsilon+\text{canonical transport}
=-\varphi^2\lambda(1-q)\varepsilon.
\tag{GM77}
$$

The $q$ in (GM28) reduces exactly to the canonical rational form.

### 7.4 Reduction statement

Under the seven conditions in §7.1,

$$
\boxed{
\mathfrak G_{\rm C}
\longrightarrow
\text{canonical real-density Cassi PDE}
}
\tag{GM78}
$$

without changing $\lambda$, $q$, the conversion direction, or the conserved
total density.

The graph, phase, coherence, endpoint, and gauge sectors become dormant in this
limit. Their physical presence remains an additional hypothesis, and the
canonical variables retain the definitions in the canonical PDE.

---

## 8. Conditional discriminators

The completion supplies five unnumbered conditional checks:

| ID | Quantity | Completion result | Boundary |
|---|---|---|---|
| GM-1 | Positive coherence fibre | $\det\Gamma=\rho^2(1-\|\mathbf n\|^2)/4$ | Algebraic identity |
| GM-2 | Canonical and zero-extension reduction | (GM74a) gives zero added-sector residual, and (GM75)–(GM77) reproduce canonical conversion exactly | Requires the neutral conditions in §7.1 |
| GM-3 | Undriven transverse coherence | $\gamma_c=\gamma_\varepsilon/2$; at the gated reference state, $\gamma_c=\lambda/6$ | Specific to the minimal two-jump lift |
| GM-4 | Compact scale topology | Two vertices and two edges give $b_1=1$ and the holonomy (GM62) | Requires gauge-covariant flux-unitary endpoint gluing; the physical endpoint sector remains open |
| GM-5 | Projective protection | Rank-one winding can unwind through the contractible full-rank interior | Requires access to $\|\mathbf n\|<1$ |

GM-3 is physically discriminating only after a carrier-to-$c$ observable and an
identified undriven conversion regime are supplied. A measured persistent
rank-one phase state under those conditions would reject the minimal lift and
require a coherent drive or different reservoir.

No numbered prediction is added to
`predictions/falsifiable-predictions.md`.

---

## 9. Epistemic ledger

| Result | Status |
|---|---|
| Metric-graph construction, $b_1=1$, and rail involution | Derived geometry under the declared endpoint quotient |
| Positive Hermitian cone and Bloch-ball decomposition | Derived linear algebra |
| Canonical subcone and $z_\varphi=\varphi^{-3}$ | Derived algebra |
| Gram moment map onto $\mathcal C_2^+$ | Derived conditional on the carrier Hilbert space |
| Coherence metric equals affine-bubble pullback metric | Derived conditional geometry |
| Relative $U(1)_Q$ associated-bundle action | Derived representation geometry; physical connection Hypothesized |
| Conservative interscale action on graph edges | Hypothesized physical extension |
| Endpoint phase gluing and Kirchhoff current conditions | Hypothesized physical boundary; charged coherent and one-way open realizations have Derived conditional covariance and source algebra |
| Minimal completely positive conversion lift | Hypothesized off-diagonal lift / exact canonical reduction |
| Coherence half-rate $\gamma_c=\gamma_\varepsilon/2$ | Derived within the minimal lift |
| Existing Markov bath and MSRJD sector | Derived conditional mesoscopic completion; microscopic reservoir open |
| Candidate $q$-lapse | Hypothesized; conversion data fix only $KN=1-q$ |
| Scale tension and endpoint selection | Capacity bound and one-way rate ratio Derived conditionally; physical couplings, rates, and scale selection open |
| Mixed-curvature inward force | Conditional restricted-sector result |
| Physical bubble identification | Hypothesized observation map |
| Stable spatially localized solution | Absent in the minimal smooth zero-Chern and registered confined-pair sectors; point-core flux supplies a conditional exterior coefficient, an auxiliary adjoint $SU(2)_Q$ branch supplies a smooth local core, and a neutral fixed-$Q_C$ carrier supplies one statically stable reduced separation under support, retention, and matching inequalities. A separate source-free temporal action defines the coupled stationary variational problem. One coefficient point is tested, but every arm fails Q2 and no qualified stationary solution is established |
| Particle mass, charge, color, spin, statistics, and decay rate | Open |
| Covariant gravity and physical scale metric | Open |

---

## 10. Required physical solution

The ansatz reaches physical completion only when one declared model supplies:

1. a microscopic or controlled mesoscopic origin for the complex doublet and
   the coherence matrix;
2. a reservoir or auxiliary-field derivation of the canonical dissipative
   conversion and its fluctuation kernel;
3. a physical choice between the charged coherent endpoint field and a
   trace-preserving open vertex channel, including its potentials, rates, and
   boundary normalization;
4. a physical scale measure, $K_{\mathfrak s}$, and scale tension;
5. a relative-connection action and boundary state that produce the required
   mixed curvature;
6. the point-flux support condition
   $2\pi N_G^2\int d\mathfrak s/e_x^2>\mathcal D$ and a compatible core; the
   auxiliary adjoint $SU(2)_Q$ branch supplies the local core but not a
   persistent condensate-coupled object;
7. a bound core-carrier mode, selected $Q_C$ and carrier coefficients, and
   finite-energy boundary data satisfying the reduced support, retention, and
   matching inequalities;
8. a stationary solution localized in $M_3$ and compact through scale in that
   completed support sector;
9. a stability spectrum with no growing physical modes;
10. an observation map from $\Gamma$ to measured density, phase coherence, and
    particle observables;
11. independently identifiable mass, charge, color, spin, statistics, and any
    winding-changing rate.

The target equations form a coupled conservative and open-system problem:

$$
\frac{\delta S_{\rm cons}}{\delta\Psi}=0,
\qquad
\frac{\delta S_{\rm cons}}{\delta B_A}=0,
\tag{GM79}
$$

alongside the reduced continuity equation

$$
\nabla_t^B\Gamma
+\nabla_i^B\mathcal J^i
+\nabla_{\mathfrak s}^B\mathcal J^{\mathfrak s}
=
\mathcal L_{\rm conv}[\Gamma]
+\mathcal L_{\rm end}[\Gamma]
+\Xi.
\tag{GM80}
$$

Equation (GM79) governs only the optional conservative sector. Equation (GM80)
contains the canonical dissipative reduction. A microscopic conservative
completion would need explicit reservoir fields whose elimination yields
(GM80); the current theory does not possess that larger action.

---

## 11. Present conclusion

The minimal common geometry is a stratified bundle over physical position and a
finite logarithmic scale interval. Its species spectral cover is a compact
metric graph. Its internal positive Hermitian cone contains:

- the canonical density pair as a diagonal subcone;
- the loop-derived coherence ball as its normalized section;
- the projective Yang/Yin sphere as its rank-one boundary;
- the affine bubble as a metric-compatible observation image.

The conservative interscale current and the canonical dissipative conversion
coexist through separate dynamical blocks. The minimal completely positive
lift proves exact canonical reduction and exposes a specific boundary: the
canonical conversion environment damps undriven transverse coherence. A
persistent projective shell therefore requires physical support beyond the
canonical conversion law.

The rail graph geometrizes the Planck-to-proton Yang-outward/Yin-return circuit
without identifying it with a spatial torus. A charged endpoint section gives
a coherent realization with finite current capacity; a one-way open channel
gives a population realization with a conditional $\varphi$ rate ratio. Their
physical couplings and the scale length remain boundary data. Mixed curvature
supplies a conditional localization route, while the smooth zero-Chern sector
has no finite Derrick radius. Point-core flux fixes the conditional exterior
$1/R$ coefficient. An auxiliary adjoint $SU(2)_Q$ branch supplies a regular
local core and matches that coefficient. The registered nonzero fundamental
condensate removes the isolated magnetic sector and confines the flux; its
finite monopole-antimonopole branch has no registered finite-separation
minimum. A neutral core carrier supplies a unique reduced separation when
$A_C>C_Q$ and the retention and matching conditions hold. The full backreacted
stationary solution and all particle quantum numbers remain open.

The completion ansatz closes the mathematical map among the declared geometric
layers. Physical completion requires the solution specified in §10.

---

## References

- `foundations/cassi-first-principles.md`—canonical real-density PDE and $q$
- `foundations/physical-becoming-hierarchy.md`—gradient flow, Markov bath, and response functional
- `foundations/loop-to-bubble-projection-theorem.md`—carrier projection and species Gram matrix
- `foundations/string-bubble-projective-map.md`—projective shell and affine bubble geometry
- `foundations/interscale-current-soliton.md`—conditional scale current, mixed
  curvature, and compact circuit
- `foundations/endpoint-link-and-localization-boundary.md`—charged endpoint
  realization, open vertex alternative, invariant classification, and
  minimal-sector localization no-go
- `foundations/point-core-flux-sector.md`—quantized exterior flux support and
  current-action point-defect boundary
- `foundations/nonabelian-magnetic-core-boundary.md`—auxiliary smooth core,
  condensate confinement, and persistent-composite boundary
- `computations/magnetic_core_completion_check.py`—BPS profile, matching,
  London, and pair-slope checker
- `foundations/core-trapped-charge-support.md`—conditional conserved-charge
  support, carrier retention, and reduced finite-separation theorem
- `computations/core_trapped_charge_check.py`—support-root, curvature,
  localization, and source-unit checker
- `foundations/particle-stationary-action-closure.md`—source-free temporal
  action, Gauss constraint, stationary equations, and variational boundary
- `computations/particle_action_closure_check.py`—action-algebra and
  nondimensionalization checker
- `computations/particle-stationary-bvp-report.md`—registered one-point stationary campaign and numerical-quality verdict
- `foundations/unified-lagrangian.md`—optional conservative sector bookkeeping
- `field-experience/toroidal-coherence-survival-report.md`—spatial torus survival verdict
- `field-experience/toroidal-connected-hierarchy-report.md`—connected hierarchy result
- `computations/geometric_manifold_completion_check.py`—algebraic verification

# Non-Abelian Magnetic Core and the Confined-Defect Boundary

## Status: Hypothesized auxiliary completion / Derived conditional smooth-core and confinement boundaries—September 2026

## Abstract

The point-core calculation fixes a nonzero relative flux and its exterior
energy, but the registered Abelian action cannot continue that flux through a
smooth spatial core. This document tests the smallest standard local repair: an
auxiliary internal gauge group $SU(2)_Q$ broken to the registered relative
$U(1)_Q$ by one adjoint field. This group is distinct from the electroweak
$SU(2)_L$ extension in `standard-model/su2-gauge-extension.md`.

The adjoint-only branch resolves the Abelian Bianchi obstruction. Its
gauge-invariant residual tensor carries
$\Phi_G=4\pi N_G/g_Q$, exactly matching the point-core convention.
At the Prasad-Sommerfield limit it has the regular analytic monopole

$$
K(X)=\frac{X}{\sinh X},
\qquad
H(X)=\coth X-\frac1X,
\qquad
X=g_Qv_Qr,
$$

and, for one scale-independent core over the registered base interval,

$$
M_{\rm BPS}
=\frac{4\pi L_{\mathfrak s}v_Q|N_G|}{\mu_xg_Q}.
$$

This is a conditional smooth-core completion, not a completion of the Cassi
particle sector. The registered vacuum has nonzero Yang and Yin condensates.
Promoting that doublet to the fundamental representation completely breaks the
residual gauge group. The chosen-vacuum gauge orbit becomes
$SU(2)_Q\simeq S^3$ with $\pi_2=0$, while the complete minimum set, including
the ungauged common phase, has the finite central identification
$(SU(2)_Q\times U(1)_N)/\mathbb Z_2\simeq U(2)$ and also has trivial
$\pi_2$. The registered London mass then confines a unit monopole flux into a
tube. A finite monopole-antimonopole string is possible conditionally, but its
positive tension and attractive screened tail drive it toward annihilation;
the present action supplies no finite-separation minimum.

The resulting boundary is sharp. A smooth magnetic core is available only in
the adjoint-only or vanishing-condensate branch. An isolated finite-energy
point defect, a persistent net-zero composite, a full stationary particle
solve, and a dynamical fluctuation spectrum remain absent from the registered
Cassi sector. The next particle-level ingredient must first supply a conserved
or repulsive support mechanism for a finite composite. Temporal gauge
curvatures and a Gauss law are additionally required before mode frequencies
can be defined.

---

## 1. Scope and result ledger

### 1.1 Inputs

The calculation uses five declared structures:

1. the relative connection and flat $d\mathfrak s$ source measure from
   `foundations/interscale-current-soliton.md`;
2. the minimum relative charges $\pm g_Q/2$ of the Yang/Yin doublet;
3. the point-core normalization
   $\Phi_G=4\pi N_G/g_Q$ and exterior coefficient
   $\mathcal B_G=2\pi N_G^2\int d\mathfrak s/e_x^2$ from
   `foundations/point-core-flux-sector.md`;
4. the nonzero asymptotic composition
   $E_Y=\rho_0/\varphi$ and $E_I=\rho_0/\varphi^2$;
5. one Hypothesized auxiliary $SU(2)_Q$ connection and one adjoint field.

No value of $v_Q$, $\lambda_H$, a string tension, a temporal gauge coefficient,
or a particle observable is derived from $\varphi$.

### 1.2 Results

| ID | Result | Status |
|---|---|---|
| MC-1 | An adjoint $SU(2)_Q\to U(1)_Q$ branch is the smallest tested local smooth-core lift compatible with the registered half-charged doublet | Hypothesized completion choice / Derived representation matching |
| MC-2 | The gauge-invariant residual tensor has flux $4\pi N_G/g_Q$ and reproduces the registered exterior coefficient | Derived within the auxiliary action |
| MC-3 | The adjoint-only Prasad-Sommerfield branch has an exact regular profile and mass $4\pi L_{\mathfrak s}v_Q|N_G|/(\mu_xg_Q)$ | Derived conditional analytic solution |
| MC-4 | A polynomial adjoint-doublet composition scalar reduces exactly to $E_Y-\varphi E_I$ in unitary gauge | Derived algebraic matching |
| MC-5 | The nonzero fundamental condensate leaves trivial gauge stabilizer; the magnetic $\pi_2$ sector disappears in the fully coupled vacuum | Derived topology within the auxiliary field content |
| MC-6 | The registered London mass confines unit flux into one residual-$U(1)_Q$ tube with relative spatial phase winding two | Derived asymptotic consequence; full string profile conditional |
| MC-7 | Positive tube tension plus the attractive screened tail gives no finite-separation monopole-antimonopole minimum | Derived for the registered long-distance branch; core interaction unselected |
| MC-8 | The exact BPS core needs no numerical solve; the full Cassi particle boundary-value problem and dynamical spectrum remain undefined | Derived well-posedness boundary |

No row identifies a Standard Model particle or predicts a mass, electric
charge, color representation, spin, statistics, lifetime, or cross section.

---

## 2. Minimal branch classification

The point-core obstruction can be changed in several inequivalent ways. They
must not be combined as though they were one model.

| Branch | Smooth local core? | Isolated finite energy with $\rho\to\rho_0>0$? | Persistent finite object? | Boundary |
|---|---:|---:|---:|---|
| Retained excision or finite inner boundary | No | Conditional on the imposed boundary | Boundary-supported only | Core remains external data |
| Explicit Abelian magnetic source | Only after a source profile is independently supplied | The charged-condensate far-field obstruction remains | Not supplied | Source dynamics and ultraviolet origin absent |
| Adjoint $SU(2)_Q$, $\Psi\to0$ at infinity | Yes | Yes | Yes in a fixed adjoint magnetic sector | Does not reproduce the registered nonzero Cassi vacuum |
| Adjoint $SU(2)_Q$ plus the registered $\Psi_\infty\ne0$ | Yes locally | No for isolated net flux | No isolated object | Flux is screened and confined |
| Monopole-antimonopole joined by a finite tube | Yes locally | Yes because net far-field flux vanishes | No minimum in the registered asymptotic energy | Pair shrinks unless another support term is selected |
| Current-carrying or otherwise supported net-zero composite | Possible | Possible | Undetermined | Conserved support, coefficients, and equations are not registered |

A neutral scalar, a Stueckelberg scalar, or another purely electric Abelian
Higgs field leaves $dG=0$ on a smooth ball and therefore does not repair the
magnetic source. A dual-potential description changes the electric locality
and charge formulation. The adjoint $SU(2)_Q$ branch is selected here only as
the smallest tested local model that smooths the magnetic core while retaining
the half-charged doublet representation.

It passes the core criterion and fails the complete-particle criterion. This
separation controls every result below.

---

## 3. Auxiliary $SU(2)_Q$ source action

### 3.1 Group and representation

Let

$$
T^a:=\frac{\sigma^a}{2},
\qquad
[T^a,T^b]=i\epsilon^{abc}T^c,
\tag{MC1}
$$

and introduce a spatial-and-scale connection
$\mathcal A_A=\mathcal A_A^aT^a$ for
$A\in\{1,2,3,\mathfrak s\}$. The fundamental doublet is

$$
\Psi=
\begin{pmatrix}
\psi_Y\\
\psi_I
\end{pmatrix},
\qquad
D_A\Psi
:=\left(\partial_A-ig_Q\mathcal A_A^aT^a\right)\Psi.
\tag{MC2}
$$

The curvature and adjoint derivative are

$$
\mathcal F_{AB}^a
:=\partial_A\mathcal A_B^a-\partial_B\mathcal A_A^a
+g_Q\epsilon^{abc}\mathcal A_A^b\mathcal A_B^c,
\tag{MC3}
$$

$$
(D_A\Phi)^a
:=\partial_A\Phi^a
+g_Q\epsilon^{abc}\mathcal A_A^b\Phi^c.
\tag{MC4}
$$

The fundamental representation requires the group $SU(2)_Q$ rather than
$SO(3)_Q$. The subscript $Q$ denotes the auxiliary relative Yang/Yin sector.
It is not the weak-isospin group $SU(2)_L$, its connection is not identified
with the Standard Model $W$ bosons, and $v_Q$ is not assigned the electroweak
vacuum value.

### 3.2 Minimal static Hamiltonian

A source-unit adjoint completion of the spatial and mixed gauge terms is

$$
\begin{aligned}
\mathcal H_Q={}&
\frac{1}{4\mu_x}\mathcal F_{ij}^a\mathcal F_{ij}^a
+\frac{1}{2\mu_m}\mathcal F_{i\mathfrak s}^a
 \mathcal F_{i\mathfrak s}^a\\
&+\frac{1}{2\mu_x}(D_i\Phi)^a(D_i\Phi)^a
+\frac{1}{2\mu_m}(D_{\mathfrak s}\Phi)^a
 (D_{\mathfrak s}\Phi)^a\\
&+\frac{\lambda_H}{4}
 \left(\Phi^a\Phi^a-v_Q^2\right)^2.
\end{aligned}
\tag{MC5}
$$

This normalization ties the adjoint spatial and scale stiffnesses to the two
registered gauge stiffnesses. A general model may replace them by independent
positive coefficients, but no result here requires that extra freedom. Under
the flat-density convention,

$$
[\Phi]=[v_Q]=L^{-1},
\qquad
[\lambda_H]=\frac{\hbar L}{T}.
\tag{MC6}
$$

The registered gauge-normalization change extends as

$$
\mathcal A_A' =a\mathcal A_A,
\quad
\Phi'=a\Phi,
\quad
g_Q'=\frac{g_Q}{a},
\quad
\mu_{x,m}'=a^2\mu_{x,m},
\quad
v_Q'=av_Q,
\quad
\lambda_H'=\frac{\lambda_H}{a^4}.
\tag{MC7}
$$

Every displayed mass, flux energy, and BPS energy below is invariant under
(MC7).

### 3.3 Residual Abelian matching

Choose unitary gauge outside the core,

$$
\Phi^a=v_Q\delta^{a3},
\qquad
\mathcal A_A^{1,2}=0,
\qquad
\mathcal A_A^3=B_A.
\tag{MC8}
$$

The orientation in (MC8) assigns the $+1$ eigencomponent of $\sigma^3$ to
Yang. Reversing $\Phi$ exchanges the two residual weights and therefore
exchanges the Yang/Yin composition assignment. This orientation is part of the
matching convention, not a second physical vacuum prediction.

Then (MC2) becomes

$$
D_A\psi_Y
=\left(\partial_A-\frac{i g_Q}{2}B_A\right)\psi_Y,
\qquad
D_A\psi_I
=\left(\partial_A+\frac{i g_Q}{2}B_A\right)\psi_I,
\tag{MC9}
$$

and (MC5) reduces to the registered Abelian gauge energy. The off-diagonal
connection components carry residual charges $\pm g_Q$ and are additional
massive fields of the auxiliary completion.

Define

$$
\rho:=\Psi^\dagger\Psi,
\qquad
S^a:=\Psi^\dagger\sigma^a\Psi,
\tag{MC10}
$$

and the gauge-invariant composition scalar

$$
\boxed{
\Delta_\varphi
:=\frac12\left[
(1-\varphi)\rho
+\frac{1+\varphi}{v_Q}\Phi^aS^a
\right].}
\tag{MC11}
$$

The completion replaces the registered composition potential by
$\lambda_\varphi\Delta_\varphi^2/2$. Equation (MC11) is regular at
$\Phi=0$ because it contains $\Phi^a$, not $\widehat\Phi^a$. In the unitary
exterior,

$$
\Delta_\varphi
=\frac12\left[(1-\varphi)(E_Y+E_I)
 +(1+\varphi)(E_Y-E_I)\right]
=E_Y-\varphi E_I.
\tag{MC12}
$$

The density potential $\lambda_\rho(\rho-\rho_0)^2/4$ therefore retains the
registered asymptotic composition.

This matching covers the bulk static energy. The charged endpoint field
$\Upsilon_v$ in `foundations/endpoint-link-and-localization-boundary.md` is
currently a residual-$U(1)_Q$ section. It could be placed in a larger
$SU(2)_Q$ vertex multiplet, but that choice adds boundary components and
couplings. No such endpoint lift is selected here.

---

## 4. Smooth adjoint core

### 4.1 Topological stage

With $\Psi$ absent or asymptotically vanishing, the adjoint vacuum stabilizer
is

$$
H_{\rm adj}=U(1)_Q,
\tag{MC13}
$$

so the gauge orbit of vacua is

$$
\mathcal V_{\rm adj}
=\frac{SU(2)_Q}{U(1)_Q}
\simeq S^2,
\qquad
\pi_2(\mathcal V_{\rm adj})\simeq\mathbb Z.
\tag{MC14}
$$

The physical gauge quotient of a uniform vacuum is a point; the magnetic
defect classification uses the orbit $G/H$ in (MC14). The integer is the
degree of $\widehat\Phi:S^2_\infty\to S^2$.

For $\Phi\ne0$, define the residual gauge-invariant tensor

$$
\boxed{
\mathscr G_{AB}
:=\widehat\Phi^a\mathcal F_{AB}^a
-\frac1{g_Q}\epsilon^{abc}\widehat\Phi^a
 (D_A\widehat\Phi)^b(D_B\widehat\Phi)^c,}
\qquad
\widehat\Phi^a:=\frac{\Phi^a}{|\Phi|}.
\tag{MC15}
$$

In the unitary exterior, $D_A\widehat\Phi=0$ and
$\mathscr G_{AB}=\mathcal F_{AB}^3=G_{AB}$. Its spatial flux is

$$
\boxed{
\int_{S^2_\infty}\mathscr G
=\frac{4\pi N_G}{g_Q}.}
\tag{MC16}
$$

The underlying $\mathcal A_A^a$ and $\Phi^a$ remain smooth at the monopole
center. The derived tensor (MC15) is undefined where $\Phi=0$, which is how the
residual Abelian Bianchi identity ceases to extend through the core without a
singular non-Abelian field.

### 4.2 Bogomolny reduction

Take a scale-independent core with
$\mathcal A_{\mathfrak s}=0$, $D_{\mathfrak s}\Phi=0$, and
$\lambda_H=0$. Write

$$
\mathcal B_i^a:=\frac12\epsilon_{ijk}\mathcal F_{jk}^a.
\tag{MC17}
$$

For each $\mathfrak s$, the core energy is

$$
\begin{aligned}
E_{\rm adj}
={}&\frac1{2\mu_x}\int d^3x
\left[\mathcal B_i^a\mathcal B_i^a
 +(D_i\Phi)^a(D_i\Phi)^a\right]\\
={}&\frac1{2\mu_x}\int d^3x
\left|\mathcal B_i^a\mp(D_i\Phi)^a\right|^2
\pm\frac1{\mu_x}\int_{S^2_\infty}
\Phi^a\mathcal B_i^a\,dS_i.
\end{aligned}
\tag{MC18}
$$

Thus

$$
E_{\rm adj}
\geq\frac{4\pi v_Q|N_G|}{\mu_xg_Q},
\tag{MC19}
$$

with equality when

$$
\boxed{\mathcal B_i^a=\pm(D_i\Phi)^a.}
\tag{MC20}
$$

### 4.3 Exact unit profile

For $N_G=1$, choose correlated orientation signs and set

$$
\Phi^a=v_QH(X)\widehat r^a,
\qquad
\mathcal A_i^a
=\frac{1-K(X)}{g_Qr}\epsilon_{aij}\widehat r_j,
\qquad
X:=g_Qv_Qr.
\tag{MC21}
$$

Equation (MC20) becomes

$$
\frac{dK}{dX}=-KH,
\qquad
X^2\frac{dH}{dX}=1-K^2,
\tag{MC22}
$$

with

$$
K(0)=1,
\quad H(0)=0,
\qquad
K(\infty)=0,
\quad H(\infty)=1.
\tag{MC23}
$$

The regular solution is

$$
\boxed{
K(X)=\frac{X}{\sinh X},
\qquad
H(X)=\coth X-\frac1X.}
\tag{MC24}
$$

Its limiting forms are

$$
K(X)=1-\frac{X^2}{6}+O(X^4),
\qquad
H(X)=\frac X3+O(X^3)
\quad (X\to0),
\tag{MC25}
$$

and

$$
K(X)=2Xe^{-X}+O(Xe^{-3X}),
\qquad
H(X)=1-\frac1X+O(e^{-2X})
\quad (X\to\infty).
\tag{MC26}
$$

The vector-core inverse length is

$$
\boxed{m_W=g_Qv_Q.}
\tag{MC27}
$$

The dimensionless radial energy density integrates to one:

$$
\begin{aligned}
1
={}&\int_0^\infty dX\left[
(K')^2+\frac{(1-K^2)^2}{2X^2}
+\frac{X^2(H')^2}{2}+K^2H^2
\right]\\
={}&\left[H(1-K^2)\right]_{0}^{\infty}.
\end{aligned}
\tag{MC28}
$$

For one scale-independent core copied over the source interval
$I_{\mathfrak s}$ of length $L_{\mathfrak s}$,

$$
\boxed{
M_{\rm BPS}
=\frac{4\pi L_{\mathfrak s}v_Q|N_G|}{\mu_xg_Q}.}
\tag{MC29}
$$

The registered action has one common $d\mathfrak s$ integral. Drawing the same
core on two scale-graph edges without changing that source measure would not
double (MC29); an independent two-edge gauge action would be a different
normalization branch.

### 4.4 Exterior matching

At $r\gg m_W^{-1}$, (MC15) has radial field

$$
\mathfrak b_r
=\frac{N_G}{g_Qr^2}+O(e^{-m_Wr}).
\tag{MC30}
$$

Its energy outside radius $R$ is

$$
E_{\rm ext}(R)
=\frac{2\pi L_{\mathfrak s}N_G^2}{g_Q^2\mu_xR}
+O(e^{-m_WR})
=\frac{\mathcal B_G}{R}+O(e^{-m_WR}),
\tag{MC31}
$$

where $e_x^2=g_Q^2\mu_x$. The smooth core therefore matches the point-core
coefficient without changing its factor or scale measure.

For $\lambda_H>0$, the adjoint radial mode has

$$
m_H^2=2\mu_x\lambda_Hv_Q^2,
\qquad
\beta_Q^2:=\frac{m_H^2}{m_W^2}
=\frac{2\mu_x\lambda_H}{g_Q^2}.
\tag{MC32}
$$

A finite smooth adjoint monopole continues away from the BPS limit, but its
profile and mass factor require a numerical boundary-value solve after
$\beta_Q$ is selected. The present framework selects no value.

---

## 5. Coupling the registered Cassi condensate

### 5.1 Full minimum set and gauge quotient

The BPS solution in §4 is exact only when the fundamental doublet is absent,
decoupled, or vanishes at spatial infinity. With the registered density and
composition potentials, the asymptotic minima obey

$$
|\Phi|=v_Q,
\qquad
\Psi^\dagger\Psi=\rho_0,
\qquad
\widehat\Phi^a\frac{S^a}{\rho_0}=\varphi^{-3}.
\tag{MC33}
$$

The last identity follows from

$$
\frac{E_Y-E_I}{E_Y+E_I}
=\frac{\varphi-1}{\varphi+1}
=\varphi^{-3}.
\tag{MC34}
$$

Fix a reference vacuum in unitary gauge,

$$
\Phi_0^a=v_Q\delta^{a3},
\qquad
\Psi_0=
\begin{pmatrix}
\sqrt{\rho_0/\varphi}\\
e^{i\delta}\sqrt{\rho_0/\varphi^2}
\end{pmatrix}.
\tag{MC35}
$$

An element that leaves $\Phi_0$ fixed has the form
$U(\theta)=\exp(i\theta T^3)$. Requiring it also to leave $\Psi_0$ fixed gives

$$
e^{i\theta/2}\psi_Y=\psi_Y,
\qquad
e^{-i\theta/2}\psi_I=\psi_I.
\tag{MC36}
$$

Both components are nonzero, so $\theta=4\pi n$ and

$$
\boxed{H_{\rm full}=\{1\}.}
\tag{MC37}
$$

There are three related spaces, and they must be kept distinct:

1. Holding the ungauged common-number phase fixed, the gauge orbit is
   $SU(2)_Q/H_{\rm full}\simeq SU(2)_Q\simeq S^3$.
2. Allowing the common phase $U(1)_N$, the unquotiented minimum set is

   $$
   \mathcal V_{\rm min}
   \simeq\frac{SU(2)_Q\times U(1)_N}{\mathbb Z_2}
   \simeq U(2),
   \tag{MC38}
   $$

   where $(-\mathbf 1,-1)$ acts trivially on the reference pair.
3. Quotienting the complete minimum set by the gauge group leaves
   $\mathcal V_{\rm min}/SU(2)_Q\simeq U(1)_N$; fixing or superselecting that
   common phase reduces the quotient to a point.

All three statements give the same magnetic conclusion:

$$
\pi_2(S^3)=0,
\qquad
\pi_2(U(2))=0,
\qquad
\pi_2(U(1)_N)=0.
\tag{MC39}
$$

The global $U(1)_N$ can carry global-string data through $\pi_1$, but it does
not restore local monopole charge. The adjoint magnetic integer of (MC14) can
unwind once the nonzero fundamental is included.

### 5.2 Loss of the exact BPS branch

The fundamental kinetic energy, the density potential, and the composition
potential add positive terms and source both $\Phi$ and $\mathcal A_i$.
Consequently (MC20)-(MC24) do not solve the fully coupled field equations even
when $\lambda_H=0$. Calling (MC24) the core of the full nonzero-condensate
object would omit those equations.

The exact statement is narrower:

- the adjoint-only branch has a smooth BPS monopole;
- it matches the registered Abelian exterior flux;
- the registered nonzero condensate changes the asymptotic topology and the
  field equations;
- the coupled branch has no isolated finite-energy continuation of that flux.

### 5.3 London confinement and spatial winding

The registered common-phase minimization gives

$$
M_i^2
=g_Q^2K_x\frac{E_YE_I}{\rho}.
\tag{MC40}
$$

At (MC35),

$$
\boxed{
M_i^2=\frac{g_Q^2K_x\rho_0}{\varphi^3},
\qquad
\kappa_L^2=\mu_xM_i^2
=\frac{e_x^2K_x\rho_0}{\varphi^3}>0.}
\tag{MC41}
$$

Thus the residual Abelian magnetic field is screened. Around a candidate flux
tube, finite covariant phase energy requires

$$
2\pi n_Y-\frac{g_Q}{2}\Phi_{\rm tube}=0,
\qquad
2\pi n_I+\frac{g_Q}{2}\Phi_{\rm tube}=0.
\tag{MC42}
$$

For one monopole flux quantum,

$$
\Phi_{\rm tube}=\frac{4\pi}{g_Q},
\qquad
n_Y=1,
\qquad
n_I=-1,
\qquad
n_Y-n_I=2.
\tag{MC43}
$$

The minimum-charge vortex therefore carries exactly one unit of the monopole
flux. This winding is spatial and must not be identified with the separate
scale-circuit integer $m$.

In the low-energy residual-$U(1)_Q$ truncation, a tube with a resolved core has
positive tension

$$
\sigma_Q
:=\int_{I_{\mathfrak s}}d\mathfrak s
\int d^2x_\perp
\left(\mathcal H-\mathcal H_{\rm vac}\right)>0.
\tag{MC44}
$$

Neither $\sigma_Q$, the tube-core width, nor a critical-coupling profile is
fixed by the registered coefficients. Because the complete gauge orbit is
$S^3$, the embedded residual-$U(1)_Q$ string is not protected by a full-theory
$\pi_1$ charge; its existence and metastability require the coupled equations.

### 5.4 Finite pair and collapse direction

A monopole-antimonopole pair joined by a finite tube has zero net magnetic flux
at infinity and can therefore have finite total energy. At separations large
compared with the core widths, the registered asymptotic terms have the form

$$
E_{M\bar M}(L)
=2M_{\rm core}+\sigma_QL+V_{\rm tail}(L)+\cdots,
\tag{MC45}
$$

with the attractive massive-Abelian tail

$$
V_{\rm tail}(L)
\simeq
-\frac{4\pi L_{\mathfrak s}}{e_x^2}
\frac{e^{-\kappa_LL}}{L}.
\tag{MC46}
$$

Writing $C_Q:=4\pi L_{\mathfrak s}/e_x^2>0$, the long-distance slope is

$$
\boxed{
E_{M\bar M}'(L)
\simeq\sigma_Q
+C_Qe^{-\kappa_LL}
\left(\frac{\kappa_L}{L}+\frac1{L^2}\right)>0.}
\tag{MC47}
$$

Energy therefore decreases as the pair moves to smaller separation. The
asymptotic formula does not control core overlap, but the full vacuum topology
permits annihilation and the registered action supplies no repulsive core
barrier, conserved charge, angular momentum, or current that would reverse the
slope. A persistent finite pair is not derived.

---

## 6. Stationary and fluctuation boundary

### 6.1 Solver decision

| Problem | Well posed now? | Reason |
|---|---:|---|
| Adjoint-only BPS unit core | Yes, analytically solved | Equations (MC22)-(MC24) give the exact solution and boundary limits |
| Adjoint-only non-BPS core | Not numerically selected | $\beta_Q$ and any scale dependence are free |
| Isolated core with $\rho\to\rho_0>0$ | No | Finite-energy isolated magnetic boundary data do not exist |
| Fixed-separation monopole-antimonopole string | Conditional constrained problem only | Tube profile, core data, outer boundary, endpoint lift, and coefficients are unselected |
| Persistent finite-separation composite | No | The registered energy has a collapse direction and no support mechanism |

A numerical integration of the already exact BPS profile would add no physical
information. A full stationary particle solve would choose absent physics
through its boundary conditions and coefficients. No preregistered PDE run is
therefore performed.

### 6.2 Static BPS Hessian

Within the adjoint-only fixed-$N_G$ sector, (MC18) factorizes the quadratic
energy around a BPS solution:

$$
\Delta E^{(2)}
=\frac1{2\mu_x}
\int d^3x\,
\left|\delta\left(\mathcal B_i^a-D_i\Phi^a\right)\right|^2
\geq0,
\tag{MC48}
$$

subject to gauge fixing and boundary-preserving perturbations. Translation,
global gauge orientation, and BPS moduli supply zero modes. The massless
adjoint radial field at $\lambda_H=0$ also prevents a positive spectral gap.
Equation (MC48) establishes static nonnegativity, not dynamical frequencies.

### 6.3 Full dynamical spectrum

The registered source action contains first-order matter kinetics but no
$\mathcal F_{ti}^a$ or $\mathcal F_{t\mathfrak s}^a$ kinetic terms and no
complete Gauss law. The coupled branch also lacks a finite-energy stationary
background. A physical fluctuation spectrum therefore requires, in order:

1. a selected support mechanism and finite-energy composite background;
2. an $SU(2)_Q$ lift or replacement of the endpoint sector;
3. temporal gauge curvatures with positive coefficients;
4. the corresponding Gauss constraint and gauge fixing;
5. the second variation in adjoint, doublet, gauge, endpoint, and scale
   channels.

Temporal completion alone would make frequencies definable only after the
stationary-background problem is solved. It does not remove the
nonzero-condensate monopole obstruction.

---

## 7. Decision ledger

| Criterion | Verdict | Evidence |
|---|---|---|
| Smooth magnetic core | **PASS conditionally** | Adjoint-only $SU(2)_Q$ BPS solution (MC20)-(MC29) |
| Exact point-core flux and exterior coefficient matching | **PASS** | (MC16) and (MC31) |
| Exact BPS solution after coupling $\Psi_\infty\ne0$ | **FAIL** | Fundamental kinetic and composition terms source the BPS equations |
| Isolated finite-energy monopole with $\rho_0>0$ | **FAIL** | Trivial full stabilizer, $\pi_2=0$, and positive London mass |
| Finite net-zero monopole-antimonopole configuration | **CONDITIONAL** | Requires a resolved flux tube and selected coefficients |
| Persistent finite-separation composite | **FAIL in the registered asymptotic branch** | Strictly positive slope (MC47); no selected support term |
| Full stationary particle solver | **FAIL / not well posed** | No finite-energy isolated boundary data or persistent pair background |
| Static adjoint BPS stability | **PASS conditionally** | Nonnegative factorized quadratic energy (MC48) |
| Full dynamical fluctuation spectrum | **FAIL / undefined** | No stationary full background, temporal gauge kinetics, or Gauss law |

The first additional ingredient for a particle candidate is a declared
conserved or repulsive support sector that yields a finite composite and
passes $E'(L_*)=0$, $E''(L_*)>0$. If that succeeds, the first additional
ingredient for a spectrum is a positive temporal gauge completion with its
Gauss law. Neither is selected in this document.

---

## 8. Evidence boundary

`computations/magnetic_core_completion_check.py` independently checks:

1. the gauge-invariant composition reduction;
2. the exact profile ODE residuals and boundary limits;
3. the unit dimensionless BPS energy integral;
4. the source-unit mass and gauge-normalization invariants;
5. the point-core exterior coefficient;
6. the $\varphi$-vacuum London mass and unit-flux spatial winding;
7. the positive monopole-antimonopole separation slope.

These are analytic checks of a Hypothesized auxiliary completion. They create
no numbered physical prediction. No numerical field solution is evidence for
a Cassi particle until the fully coupled finite-energy background and all of
its boundary data are selected.

---

## 9. Present conclusion

The auxiliary adjoint $SU(2)_Q$ branch closes one precise gap: it replaces the
singular Abelian point core by a regular local field configuration and recovers
the already derived flux normalization and exterior energy. In the decoupled
Prasad-Sommerfield limit, its profile and source-interval mass are exact.

The registered Cassi condensate changes the result. Its nonzero fundamental
doublet removes the magnetic $\pi_2$ sector, produces the registered London
mass, and confines residual flux. Neutralizing the far field with a finite
monopole-antimonopole string removes the infinite-volume energy divergence but
leaves a collapse direction. The tested minimal completion therefore supplies
a smooth core without supplying a persistent particle.

Stationary particle numerics remain premature. The next physical decision is
a support mechanism for a finite net-zero composite, followed by a temporal
gauge action only after such a background exists.

---

## References

- `foundations/interscale-current-soliton.md`—relative connection, source
  measure, condensate action, and London coefficients
- `foundations/endpoint-link-and-localization-boundary.md`—residual charged
  endpoint field and localization requirements
- `foundations/point-core-flux-sector.md`—flux normalization, exterior energy,
  Abelian core obstruction, and finite-energy boundary
- `foundations/geometric-manifold-completion.md`—scale graph and completion
  requirements
- `computations/magnetic_core_completion_check.py`—profile, energy, matching,
  screening, and pair-slope checker
- G. 't Hooft, “Magnetic Monopoles in Unified Gauge Theories,” *Nuclear Physics
  B* **79** (1974), 276–284
- A. M. Polyakov, “Particle Spectrum in Quantum Field Theory,” *JETP Letters*
  **20** (1974), 194–195
- M. K. Prasad and C. M. Sommerfield, “Exact Classical Solution for the 't
  Hooft Monopole and the Julia-Zee Dyon,” *Physical Review Letters* **35**
  (1975), 760–762
- E. B. Bogomolny, “Stability of Classical Solutions,” *Soviet Journal of
  Nuclear Physics* **24** (1976), 449–454

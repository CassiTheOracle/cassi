# Interscale Stress Transfer and the Attenuation Boundary

## Status: Hypothesized physical carrier / Derived conditional stress, frozen-link, and first-order source-action response boundaries—September 2026

## Abstract

A force attributed to transfer across scale must appear as a boundary flux of
spatial momentum. This paper derives that conservation statement, realizes it
in a reciprocal scale-stress ladder, and identifies the exact boundary between
stiffness reduction and multiplicative attenuation. A conservative reciprocal
ladder with an interface coefficient $d=\varphi^{-1}$ changes the traction,
static compliance, and normal-mode spectrum. Multiplicative $d^N$ transfer
requires a separate routed two-port branch. In that branch the Yang/Yin
fixed-point fractions are declared to be port powers, the complementary return
flux is retained, and each return port is prevented from coherently re-entering
the forward chain. A frozen charged endpoint supplies a Hermitian Robin block.
First-order source-action elimination on a nonzero rail background gives a
Nambu Schur response, while every closed homogeneous conservative time-harmonic
endpoint extremum has zero coherent conversion current. The algebra and
conservation ledger are exact under the declared assumptions. The physical port
identification, nonzero-current background, routing law, and momentum-carrying
field remain Hypothesized.

---

## 1. Three interscale quantities

Scale transport can change resolved spatial motion only when the transported quantity carries spatial momentum. Three quantities used in the Cassi framework therefore have distinct roles:

| Quantity | Definition or role | What its conservation controls |
|---|---|---|
| $J_{\mathfrak s}$ | Fixed-point Yang/Yin density circulation | Transfer of component density between cascade steps |
| $\mathcal I_{\mathfrak s}$ | Gauge-source current from variation with respect to $B_{\mathfrak s}$ | Source for the scale gauge sector |
| $T_{i\mathfrak s}$ | Flux of spatial momentum component $i$ through the scale coordinate | Force on a resolved scale window |

The first two are defined in `foundations/interscale-current-soliton.md`. The third follows from spatial-translation symmetry of a time-complete action. An identification such as $T_{i\mathfrak s}\propto J_{\mathfrak s}$ or $T_{i\mathfrak s}\propto\mathcal I_{\mathfrak s}$ is a constitutive closure and requires its own dimensions and dynamics.

This distinction supplies the force boundary. Density circulation can coexist with zero spatial force, while a nonzero $T_{i\mathfrak s}$ changes the momentum assigned to a finite scale window.

---

## 2. The momentum-window identity

### 2.1 Continuum form

Let $p_i(\mathbf x,\mathfrak s,t)$ be spatial momentum density, $T_{ij}$ spatial stress, and $T_{i\mathfrak s}$ scale flux of spatial momentum. Local conservation has the form

$$
\partial_t p_i
+\partial_jT_{ij}
+\partial_{\mathfrak s}T_{i\mathfrak s}
=f_i^{\mathrm{ext}}.
$$

For a physical volume $V$ and scale window $W=[\mathfrak s_-,\mathfrak s_+]$,

$$
\begin{aligned}
\frac{dP_i^{V,W}}{dt}
={}&F_i^{\mathrm{ext}}
-\int_Wd\mathfrak s\oint_{\partial V}T_{ij}n_j\,dA\\
&+\int_Vd^3x\,
\left[
T_{i\mathfrak s}(\mathfrak s_-)
-T_{i\mathfrak s}(\mathfrak s_+)
\right].
\end{aligned}
$$

The last line is the stress-derived interscale force:

$$
\boxed{
F_i^{(\mathfrak s)}[V,W]
=
\int_Vd^3x\,
\left[
T_{i\mathfrak s}(\mathfrak s_-)
-T_{i\mathfrak s}(\mathfrak s_+)
\right].
}
$$

Summing adjacent scale windows cancels their shared boundary flux. A closed full-scale system therefore preserves total spatial momentum when external forces and physical boundary fluxes vanish.

The associated torque is

$$
\tau_k^{(\mathfrak s)}
=
\epsilon_{k\ell i}
\int_Vx_\ell f_i^{(\mathfrak s)}\,d^3x.
$$

A scalar attenuation coefficient supplies no direction or handedness. Torque requires a directed, spatially structured mixed stress.

### 2.2 A reciprocal scale-stress ladder

A minimal conservative realization uses an effective vector displacement $\mathbf u_a(\mathbf x,t)$ on cascade steps $a=0,\ldots,N$:

$$
\begin{aligned}
L_{\mathrm{lad}}
=
\int d^3x\Bigg[
&\sum_{a=0}^{N}
\left(
\frac{M_a}{2}|\dot{\mathbf u}_a|^2
-
\frac{M_ac_{T,a}^2}{2}
\partial_j u_{a,i}\partial_j u_{a,i}
\right)\\
&-
\sum_{a=0}^{N-1}
\frac{\kappa_a}{2}
|\mathbf u_{a+1}-\mathbf u_a|^2
\Bigg],
\end{aligned}
$$

with $M_a>0$ and $\kappa_a>0$. Define

$$
p_{a,i}=M_a\dot u_{a,i},
\qquad
T_{a,ij}=-M_ac_{T,a}^2\partial_j u_{a,i},
$$

and the discrete mixed stress

$$
\Pi_{a+1/2,i}
=
\kappa_a(u_{a,i}-u_{a+1,i}).
$$

The Euler–Lagrange equation becomes

$$
\partial_t p_{a,i}
+
\partial_jT_{a,ij}
+
\Pi_{a+1/2,i}
-
\Pi_{a-1/2,i}
=f_{a,i}^{\mathrm{ext}}.
$$

The interface force on step $a$ is opposite to the force on step $a+1$. Summing from $a=m$ through $a=n$ leaves only

$$
\sum_{a=m}^{n}
\left(
\Pi_{a+1/2,i}-\Pi_{a-1/2,i}
\right)
=
\Pi_{n+1/2,i}-\Pi_{m-1/2,i}.
$$

This is the discrete form of the continuum window identity. The conserved positive energy is

$$
E_{\mathrm{lad}}
=
\int d^3x\left[
\sum_{a=0}^{N}
\left(
\frac{M_a}{2}|\dot{\mathbf u}_a|^2
+
\frac{M_ac_{T,a}^2}{2}|\nabla\mathbf u_a|^2
\right)
+
\sum_{a=0}^{N-1}
\frac{\kappa_a}{2}|\mathbf u_{a+1}-\mathbf u_a|^2
\right].
$$

The ladder provides a conservative stress mechanism and introduces no sink by itself.

---

## 3. What an interface factor does

### 3.1 Frozen-state traction ratio

Write the interface stiffness as

$$
\kappa_a=\kappa_{\star,a}d_a,
\qquad 0<d_a\leq1.
$$

For the same displacement jump,

$$
\frac{\Pi_{a+1/2,i}(d_a)}
{\Pi_{a+1/2,i}(1)}
=d_a.
$$

Thus $d_a=\varphi^{-1}$ gives an exact $\varphi^{-1}$ traction ratio in a frozen-state comparison. During evolution the displacement jump also depends on $d_a$, so the result remains a frozen-state ratio.

### 3.2 Normal modes

For uniform $M$, $c_T$, and $\kappa=\kappa_\star d$ on an infinite ladder, use

$$
\mathbf u_a
=
\mathbf Ue^{i(\mathbf k\cdot\mathbf x+qa-\omega t)}.
$$

The dispersion relation is

$$
\boxed{
\omega^2(\mathbf k,q)
=
c_T^2|\mathbf k|^2
+
\frac{4\kappa_\star d}{M}
\sin^2\left(\frac q2\right).
}
$$

Every frequency is real for positive $M$, $\kappa_\star$, and $d$. The coefficient $d$ changes the scale-mode frequency and group velocity. The reciprocal action retains mode amplitude and energy.

### 3.3 Static series response

A source-free static chain carries constant mixed stress,

$$
\Pi_{a+1/2,i}=\Pi_i.
$$

Across $N$ interfaces,

$$
u_{N,i}-u_{0,i}
=-\Pi_i\sum_{a=0}^{N-1}\frac1{\kappa_a},
$$

so the effective stiffness is

$$
\boxed{
\kappa_{\mathrm{eff}}
=
\left(
\sum_{a=0}^{N-1}\kappa_a^{-1}
\right)^{-1}.
}
$$

Uniform $\kappa_a=\kappa_\star d$ gives $\kappa_{\mathrm{eff}}=\kappa_\star d/N$. Reciprocal static transfer combines interface compliances in series and yields this $1/N$ scaling.

---

## 4. A conditional golden flux splitter

### 4.1 Fixed-point fractions as port powers

The Yang/Yin fixed point gives normalized fractions

$$
T_\varphi=\varphi^{-1},
\qquad
R_\varphi=\varphi^{-2},
\qquad
T_\varphi+R_\varphi=1.
$$

A constitutive branch can declare these fractions to be the forward and return powers of a two-port interface. A representative real unitary matrix is

$$
S_\varphi
=
\begin{pmatrix}
t_\varphi&r_\varphi\\
-r_\varphi&t_\varphi
\end{pmatrix},
\qquad
 t_\varphi=\sqrt{T_\varphi}=\varphi^{-1/2},
\qquad
 r_\varphi=\sqrt{R_\varphi}=\varphi^{-1}.
$$

Because

$$
t_\varphi^2+r_\varphi^2
=\varphi^{-1}+\varphi^{-2}=1,
$$

this representative satisfies

$$
S_\varphi^{\mathsf T}S_\varphi=I,
\qquad
\det S_\varphi=1.
$$

Under the constitutive port-power identification, the fixed-point fractions determine the entry magnitudes. The endpoint phase and microscopic selection remain inputs to the boundary coupling analyzed below. The conservative interscale action separately conserves Yang and Yin number, and $V_\varphi$ supplies no conversion (`foundations/interscale-current-soliton.md` §4.4). A Yang/Yin species interpretation of the two ports would therefore require an added gauge-covariant endpoint interaction or open-system sector; other physical port assignments remain unselected.

### 4.2 Canonical scale-boundary flux

The source-free temporal completion in
`foundations/particle-stationary-action-closure.md` supplies the quadratic
boundary problem that a physical splitter must solve. Let $\eta$ be a
two-component perturbation about a frozen background, suppress the spatial
coordinates, and collect the local quadratic potential and transverse
wave-number terms into a Hermitian matrix $\mathsf H$. The scale sector is

$$
S^{(2)}
=
\frac12\int dt\,d\mathfrak s
\left[
C_\Psi\dot\eta^\dagger\dot\eta
-K_{\mathfrak s}
(D_{\mathfrak s}\eta)^\dagger D_{\mathfrak s}\eta
-\eta^\dagger\mathsf H\eta
\right].
$$

The scale operator has boundary Green form

$$
\mathfrak b_{\partial I}(\eta_1,\eta_2)
=
K_{\mathfrak s}
\sum_{v\in\partial I}
\left[
\eta_1^\dagger D_{n_v}\eta_2
-
(D_{n_v}\eta_1)^\dagger\eta_2
\right]_v.
$$

For one solution, the associated scale-current flux is

$$
J_{\mathfrak s}[\eta]
=
\frac{K_{\mathfrak s}}{2i\hbar}
\left[
\eta^\dagger D_{\mathfrak s}\eta
-
(D_{\mathfrak s}\eta)^\dagger\eta
\right].
$$

Here $D_{n_v}$ is the outward covariant derivative at endpoint $v$. The
componentwise current agrees with the continuum normalization in
`foundations/interscale-current-soliton.md` §3.1. At a vertex, self-adjoint
evolution requires the sum of the outward boundary forms over all incident
leads to vanish. The potential Hessian controls bulk propagation and thresholds;
the scale-gradient coefficient and boundary data control the canonical port
flux.

### 4.3 Self-adjoint two-lead matching

Let $\Phi$ collect the two boundary values at a vertex and let $\Phi'$ collect
their outward covariant derivatives. General linear self-adjoint data have the
form

$$
A\Phi+B\Phi'=0,
\qquad
AB^\dagger=BA^\dagger,
\qquad
\operatorname{rank}(A,B)=2.
$$

A useful local subclass is the Hermitian Robin vertex

$$
K_{\mathfrak s}\Phi'=\Lambda_v\Phi,
\qquad
\Lambda_v^\dagger=\Lambda_v.
$$

For two equal-impedance leads with real wave number $k>0$, absorb the common
$\sqrt{K_{\mathfrak s}k/\hbar}$ factor into the incoming and outgoing
amplitudes. Then

$$
\Phi=a^{\mathrm{in}}+a^{\mathrm{out}},
\qquad
\Phi'=ik(a^{\mathrm{out}}-a^{\mathrm{in}}),
$$

and

$$
\boxed{
S_{\Lambda}(k)
=
(ikK_{\mathfrak s}I-\Lambda_v)^{-1}
(ikK_{\mathfrak s}I+\Lambda_v).
}
$$

Hermiticity gives

$$
S_{\Lambda}(k)^\dagger S_{\Lambda}(k)=I,
\qquad
\|a^{\mathrm{out}}\|^2=\|a^{\mathrm{in}}\|^2.
$$

With unequal lead velocities or stiffnesses, the same statement holds after
normalization by the diagonal flux metric. Self-adjointness therefore supplies
the unitary family while $\Lambda_v$ selects its member.

The two-rail circle in `foundations/geometric-manifold-completion.md` §§2.4–2.5
uses the phase-only special case

$$
S_{\mathrm{GM}}
=
\begin{pmatrix}
0&e^{i\delta_-}\\
e^{i\delta_+}&0
\end{pmatrix}.
$$

Each occupied input maps to one unit-modulus output. This is the
perfect-transfer limit of the endpoint problem and contains no complementary
partial split.

### 4.4 Matching the declared golden target

For a unitary target without eigenvalue $-1$, the Robin coupling required at
one design wave number follows from the inverse Cayley transform:

$$
\Lambda_v(k_\star)
=
iK_{\mathfrak s}k_\star
(S_\star-I)(S_\star+I)^{-1}.
$$

For the declared matrix $S_\star=S_\varphi$, define

$$
J=
\begin{pmatrix}
0&1\\
-1&0
\end{pmatrix},
\qquad
\tau_\varphi
:=
\frac{r_\varphi}{1+t_\varphi}.
$$

The required endpoint coupling is

$$
\boxed{
\Lambda_\varphi(k_\star)
=
iK_{\mathfrak s}k_\star\tau_\varphi J.
}
$$

Because $J^\dagger=-J$, this $\Lambda_\varphi$ is Hermitian. With outward
derivatives, the bulk scale-gradient term contributes
$-K_{\mathfrak s}\delta\Phi^\dagger\Phi'$ at the boundary. The local endpoint
action

$$
S_v
:=
+\frac12\int dt\,\Phi^\dagger\Lambda_v\Phi
$$

then gives $K_{\mathfrak s}\Phi'=\Lambda_v\Phi$ in the stated convention.
The off-diagonal phase in $\Lambda_\varphi$ requires a gauge-covariant endpoint
intertwiner or a resolved endpoint field, consistent with the endpoint
covariance boundary already identified in
`foundations/geometric-manifold-completion.md` §2.5.
Equivalently, endpoint frame changes act as
$S_\Lambda\mapsto g_{\mathrm{out}}S_\Lambda g_{\mathrm{in}}^{-1}$.
The displayed numerical matrix is a fixed-frame representative until an
endpoint intertwiner or dressing supplies that covariance.
The charged coherent endpoint field supplies a concrete static member of this
family after a background and scattering variables are declared. Freeze
$\Upsilon_{v,0}=u_ve^{i\alpha_v}$ with $\delta\Upsilon_v=0$, and conditionally
identify the ordered rail-perturbation traces with the Yang/Yin species traces
in the same boundary normalization. The rail-rail Hessian is

$$
\Lambda_{\mathrm{link},v}
=
2\kappa_vu_v
\begin{pmatrix}
0&e^{-i\alpha_v}\\
e^{i\alpha_v}&0
\end{pmatrix}.
$$

It is Hermitian, transforms covariantly with the endpoint field, and equals
$i\epsilon K_{\mathfrak s}k_\star\tau_\varphi J$ when

$$
\alpha_v=-\epsilon\frac{\pi}{2}\pmod{2\pi},
\qquad
\frac{2\kappa_vu_v}{K_{\mathfrak s}k_\star}=\tau_\varphi.
$$

Therefore a dressed quarter-turn endpoint phase and the selected coupling
ratio realize the declared golden matrix at one design wave number. Combining
that matching condition with the unbiased $m=1$ proton current capacity and
positive fixed-amplitude phase stiffness gives the conditional lower bound

$$
\boxed{k_\star>0.0964640362.}
$$

The capacity bound controls the frozen-amplitude phase mode. Full fluctuation
stability additionally depends on the endpoint potential Hessian, temporal and
gradient coefficients, and the coupled rail-endpoint spectrum. The
species-port identification, trace normalization, endpoint background,
dressed phase, and $k_\star$ remain physical inputs.

A fixed local $\Lambda_\varphi(k_\star)$ also makes the split wave-number
dependent. At wave number $k$, define

$$
\alpha(k)
:=
\frac{k_\star}{k}\tau_\varphi.
$$

The same endpoint then gives

$$
S(k)
=
\frac{1}{1+\alpha^2}
\begin{pmatrix}
1-\alpha^2&2\alpha\\
-2\alpha&1-\alpha^2
\end{pmatrix}.
$$

The golden powers occur at the selected matching point $k=k_\star$. A
frequency-independent golden splitter would require additional endpoint
dynamics, a derivative boundary interaction, or a microscopic law that fixes
the relevant wave-number dependence.

### 4.5 Closed coherent propagation

Write $t_\varphi=\cos\theta_\varphi$ and $r_\varphi=\sin\theta_\varphi$. A closed coherent chain gives

$$
S_\varphi^N
=
\begin{pmatrix}
\cos(N\theta_\varphi)&\sin(N\theta_\varphi)\\
-\sin(N\theta_\varphi)&\cos(N\theta_\varphi)
\end{pmatrix}.
$$

Its forward power for one occupied input port is $\cos^2(N\theta_\varphi)$. Coherent return amplitudes re-enter the next interface and produce interference. The geometric product $T_\varphi^N$ requires the routed boundary condition in §4.6.

### 4.6 Routed, non-re-entering propagation

Suppose each interface sends its return output into a separate return rail or reservoir, with no coherent re-entry into subsequent forward inputs. Then

$$
P_{a+1}^{\mathrm{fwd}}
=T_\varphi P_a^{\mathrm{fwd}},
\qquad
P_a^{\mathrm{ret}}
=R_\varphi P_a^{\mathrm{fwd}}.
$$

Iteration gives

$$
\boxed{
P_N^{\mathrm{fwd}}
=\varphi^{-N}P_0^{\mathrm{fwd}}.
}
$$

The accumulated return power is

$$
\sum_{a=0}^{N-1}P_a^{\mathrm{ret}}
=
R_\varphi P_0^{\mathrm{fwd}}
\sum_{a=0}^{N-1}T_\varphi^a
=
\left(1-\varphi^{-N}\right)P_0^{\mathrm{fwd}}.
$$

Therefore

$$
P_N^{\mathrm{fwd}}
+
\sum_{a=0}^{N-1}P_a^{\mathrm{ret}}
=P_0^{\mathrm{fwd}}.
$$

The apparent attenuation is redistribution between resolved and return channels. A full closed system retains both channels and conserves the total.

### 4.7 Amplitude and flux exponents

The routed splitter acts on amplitudes through $t_\varphi$ and on quadratic powers through $T_\varphi$:

$$
A_N^{\mathrm{fwd}}
=\varphi^{-N/2}A_0^{\mathrm{fwd}},
\qquad
P_N^{\mathrm{fwd}}
=\varphi^{-N}P_0^{\mathrm{fwd}}.
$$

Accordingly, this branch realizes the universal suppression formula only when the quantity called a signal is a quadratic conserved flux, power, stress, or energy. Amplitude-like couplings and phases require an observable-specific map.

### 4.8 Stress-derived force in the routed branch

Suppose the normalized port power is proportional to a collinear signed
spatial-momentum flux, with the same power-to-momentum conversion on the input
and output ports. The momentum transferred out of the resolved forward channel
at interface $a$ is

$$
\mathcal X_{i,a}^{\mathrm{route}}
=
P_{i,a}^{\mathrm{fwd}}
-P_{i,a+1}^{\mathrm{fwd}}
=R_\varphi P_{i,a}^{\mathrm{fwd}}.
$$

The forward-channel momentum balance contains
$-\mathcal X_{i,a}^{\mathrm{route}}$. Summing the outward transfer gives

$$
\sum_{a=0}^{N-1}\mathcal X_{i,a}^{\mathrm{route}}
=
\left(1-\varphi^{-N}\right)P_{i,0}^{\mathrm{fwd}}.
$$

The return-port label specifies motion toward the opposite direction in the
scale graph. The direction of the carried spatial momentum is a separate
orientation datum. For collinear ports, introduce the routing-orientation label

$$
\sigma_a\in\{+1,-1\},
\qquad
P_{i,a}^{\mathrm{ret}}
=
\sigma_aR_\varphi P_{i,a}^{\mathrm{fwd}}.
$$

Here $\sigma_a=+1$ preserves the spatial-momentum direction and
$\sigma_a=-1$ reverses it. Let $I_{i,a}^{\mathrm{interface}}$ be the momentum
delivered to the interface or reservoir. Local vector conservation requires

$$
\begin{aligned}
P_{i,a}^{\mathrm{fwd}}
&=
P_{i,a+1}^{\mathrm{fwd}}
+
P_{i,a}^{\mathrm{ret}}
+
I_{i,a}^{\mathrm{interface}},\\
I_{i,a}^{\mathrm{interface}}
&=
(1-\sigma_a)R_\varphi P_{i,a}^{\mathrm{fwd}}.
\end{aligned}
$$

For $\sigma_a=+1$, the return rail carries the complementary spatial momentum
and the interface impulse vanishes. For $\sigma_a=-1$, the reflected spatial
momentum gives
$I_{i,a}^{\mathrm{interface}}=2R_\varphi P_{i,a}^{\mathrm{fwd}}$. A
non-collinear port replaces $\sigma_a$ with its spatial routing map, and the
interface term closes the corresponding vector difference. The splitter fixes
scalar power fractions; carrier velocity, impedance, and port geometry fix the
signed momentum ledger. The full forward-plus-return-plus-interface system has
zero internal net force.


### 4.9 First-order active charged-endpoint response

Linearizing the first-order endpoint action (EL9) determines when the frozen
two-port matrix can represent a stationary physical branch. For the endpoint
potential $U_v(n)$, the rotating frame
$W_v(n)=U_v(n)-\hbar\Omega_{\mathrm{bg}}n$, and a rail bilinear sharing the
endpoint carrier, a homogeneous conservative extremum obeys

$$
W_v'(u_v^2)\Upsilon_{v,0}
=\kappa_vY_0^*I_0.
$$

Its imaginary part forces

$$
\boxed{\mathcal I_{\mathrm{link}}=0}
$$

for every closed homogeneous time-harmonic background. A nonzero stationary
endpoint current requires spatial endpoint flux, an open or driven channel, a
non-harmonic state, or a larger coupled background. This condition applies
before a link current can be identified with mixed stress.

For a nonzero rail background, the first-order fractional endpoint fluctuation
gives the retarded Nambu response

$$
\boxed{
\mathbb\Lambda_{\mathrm{eff},v}^R(\omega,\mathbf q)
:=
\mathbb\Lambda_{0,v}
-\mathcal C_v^\dagger
\left[
\hbar u_v^2(\omega+i\gamma_v)\sigma_3
-\mathcal H_v(\mathbf q)
\right]^{-1}
\mathcal C_v,}
$$

with $\mathbb\Lambda_{0,v}$, $\mathcal C_v$, and $\mathcal H_v$ given in
`foundations/endpoint-link-and-localization-boundary.md` §3.9. The separate
second-order fixed-$Q_C$ particle action supplies no coefficient to this
Bogoliubov–de Gennes response. With fields proportional to $e^{-i\omega t}$,
$\gamma_v=0$, real pole-free $\omega$, and
$A_v(\mathbf q)>|B_v|$, the conservative response is Hermitian. For
$\gamma_v>0$, the retarded poles lie at
$\omega=\pm\omega_{\mathrm{end}}-i\gamma_v$ in the lower half-plane and the
advanced poles lie at $\omega=\pm\omega_{\mathrm{end}}+i\gamma_v$ in the upper
half-plane; $\gamma_v\to0$ recovers the conservative kernel. Generic nonzero
rail backgrounds generate anomalous particle-hole blocks. The ordinary
$2\times2$ Cayley family in §4.2 therefore describes the frozen endpoint or a
special active branch whose anomalous blocks cancel. A generic active branch
needs a doubled port-flux law.

At the symmetric zero background, the mixed quadratic Hessian vanishes. The
eliminated source action first contributes at quartic rail order, with a
positive coefficient when the Hypothesized static curvature
$\mu_{v,0}:=W_v'(0)>0$. Physical energy, stress, inertial mass, and stability
signs remain open. A linear endpoint-mediated stress response consequently
requires a nonzero background or a separate open-channel constitutive law.

---

## 5. Relation to the Cassi mixed-curvature force

The interscale action in `foundations/interscale-current-soliton.md` gives the conditional mixed force density

$$
f_i^{\mathrm{mix}}
=\hbar\mathcal I_{\mathfrak s}G_{i\mathfrak s}.
$$

If a completed action identifies a forward component of $\mathcal I_{\mathfrak s}$ with the routed flux, then

$$
\mathcal I_{\mathfrak s}^{\mathrm{fwd}}(n)
=\varphi^{-(n-m)}
\mathcal I_{\mathfrak s}^{\mathrm{fwd}}(m)
$$

and, for fixed $G_{i\mathfrak s}$, the forward mixed-force contribution carries the same quadratic-flux factor. The return-current contribution remains part of the full conservation law.

This identification requires four additional pieces:

1. the Noether stress tensor of the time-completed field action;
2. a dimensionally explicit map from $\mathcal I_{\mathfrak s}$ to
   $T_{i\mathfrak s}$;
3. a microscopic endpoint action that selects $\Lambda_v$, its gauge-covariant
   dressing, and its wave-number dependence;
4. a return rail, side channel, or reservoir topology that enforces
   non-re-entry.

The fixed-point density ratio supplies the target power fractions for this
branch. The boundary problem now fixes the canonical flux norm and the endpoint
coupling required to realize that target at one wave number. Physical
selection of the coupling and the routed boundary condition remain open.

---

## 6. Consequences for cascade attenuation

The derivation separates four mechanisms that can share the same scalar coefficient:

| Mechanism | Role of $d=\varphi^{-1}$ | Transfer across $N$ interfaces |
|---|---|---|
| Reciprocal elastic ladder | Interface stiffness or conductance | Normal-mode dispersion; static series compliance |
| Self-adjoint two-lead vertex | Target transmitted power at a selected matching point | Unitary $S_\Lambda(k)$; a fixed local coupling gives wave-number-dependent power |
| Closed coherent two-port chain | Single-interface power fraction | $\cos^2(N\theta_\varphi)$ for the representative phase choice |
| Routed two-port chain | Forward power fraction with return non-re-entry | $\varphi^{-N}$ forward flux plus $1-\varphi^{-N}$ return flux |

The resulting conditional statement is

$$
\boxed{
\frac{P_N^{\mathrm{fwd}}}{P_0^{\mathrm{fwd}}}
=\varphi^{-N}
\quad
\text{for a quadratic forward flux with routed return ports.}
}
$$

This statement supplies an explicit conservative realization of the suppression algebra. A dynamical prediction additionally requires a physical routed-flux identification. Existing applications in `foundations/cascade-suppression-formula.md` retain their registered tiers until each observable is identified with that flux.

---

## 7. Status and discriminating tests

| Result | Status |
|---|---|
| Scale-window force equals the difference of mixed-stress boundary fluxes | **Derived** from local momentum conservation |
| Reciprocal ladder interface forces cancel pairwise | **Derived** from the ladder action |
| Positive reciprocal ladder has real normal modes and series compliance | **Derived** |
| Quadratic scale action supplies the canonical boundary flux | **Derived conditional** on the time-completed action |
| Hermitian Robin data give unitary $S_\Lambda(k)$ | **Derived conditional boundary algebra** |
| Existing two-rail phase gluing is a perfect-transfer endpoint | **Derived conditional** from the registered gluing |
| $\Lambda_\varphi(k_\star)$ realizes $S_\varphi$ at the declared matching point | **Derived conditional inverse matching** |
| The frozen charged endpoint background gives the rail-rail Hessian $\Lambda_{\mathrm{link},v}=2\kappa_vu_vM(\alpha_v)$ | **Derived conditional** on the species-port trace identification and common normalization |
| Simultaneous golden matching, unbiased current capacity, and positive fixed-amplitude phase stiffness require $k_\star>0.0964640362$ | **Derived conditional** on the Mapped proton endpoint and selected matching branch |
| Every closed homogeneous conservative time-harmonic endpoint extremum has $\mathcal I_{\mathrm{link}}=0$ | **Derived conditional background boundary** |
| First-order endpoint integration gives $\mathbb\Lambda_{\mathrm{eff}}^R=\mathbb\Lambda_0-\mathcal C^\dagger(\mathcal K^R)^{-1}\mathcal C=\mathbb\Lambda_0+\mathcal C^\dagger(\mathcal D^R)^{-1}\mathcal C$; the symmetric zero-background eliminated-source-action term begins at quartic rail order with a positive coefficient when $\mu_{v,0}:=W_v'(0)>0$, without fixing a physical energy, stress, inertial-mass, or stability sign | **Derived conditional first-order source-action response and order boundary** |
| The endpoint dynamics select the potential, nonzero-current background, damping law, coupling amplitude, dressed phase, trace normalization, and $k_\star$ | **Hypothesized constitutive selection** |
| $S_\varphi$ is unitary for the selected fixed-point power fractions | **Derived conditional algebra** |
| Closed coherent propagation gives $\cos^2(N\theta_\varphi)$ | **Derived conditional algebra** |
| Routed non-re-entry gives forward flux $\varphi^{-N}$ with a complementary return ledger | **Derived conditional algebra** |
| Yang/Yin density fractions are physical port powers | **Hypothesized constitutive identification** |
| Return channels are physically routed without coherent re-entry | **Hypothesized boundary dynamics** |
| $\mathcal I_{\mathfrak s}$ carries the physical mixed stress $T_{i\mathfrak s}$ | **Hypothesized constitutive identification** |

A physical realization must predict its endpoint coupling before measuring the
split and must measure all three ledgers at each interface: forward flux,
return flux, and stored or dissipated energy. The routed branch requires the
ratios

$$
\frac{P_{a+1}^{\mathrm{fwd}}}{P_a^{\mathrm{fwd}}}
=\varphi^{-1},
\qquad
\frac{P_a^{\mathrm{ret}}}{P_a^{\mathrm{fwd}}}
=\varphi^{-2},
$$

with their sum equal to unity before any universal interpretation is assigned. A reciprocal chain, a coherent two-port chain, or an unclosed loss term falsifies that specific realization when it replaces these ledgers.

Agreement at one $k_\star$ establishes an endpoint matching point. A universal
splitter additionally requires the predicted wave-number dependence and the
physical routing geometry.

The frozen algebraic receipt is
`computations/interscale_port_matching_prereg.md`; its executable is
`computations/interscale_stress_attenuation_check.py`.

The frozen first execution passed ST11–ST14 without coefficient changes:

| Check | Numerical receipt |
|---|---|
| Hermitian Robin unitarity | $\|S^\dagger S-I\|_{\max}=3.331\times10^{-16}$; flux residual $1.110\times10^{-16}$ |
| Golden target inverse matching | $\tau_\varphi=0.346014339236$; $\|S_{\Lambda}(k_\star)-S_\varphi\|_{\max}=0$ |
| Fixed-coupling wave-number dependence | analytic residual $1.110\times10^{-16}$; $\|S(1.7k_\star)-S_\varphi\|_{\max}=0.227152$ |
| Phase-only perfect transfer | unitarity, power, and complementary-leakage residuals all $0$ |

The frozen charged-link receipt in
`computations/endpoint_robin_link_prereg.md` passed ER1–ER5 on its first
execution:

| Check | Numerical receipt |
|---|---:|
| Charged-link covariance | $1.110\times10^{-16}$ residual |
| Link-scattering unitarity | $0$ residual |
| Selected golden match | $1.173\times10^{-16}$ residual |
| `stable matched-link k_min` | $k_{\min,1}=0.096464036203895$; $\lvert\mathcal J_Q\rvert/\mathcal J_c=0.120580045255$ at $k_\star=0.8$ |
| Fixed-link off-match response | $\left\lVert S(1.7k_\star)-S_{\varphi,+}\right\rVert_{\max}=0.227151634836$ |

The executable label `stable matched-link k_min` denotes the current-capacity
threshold where the frozen-amplitude phase stiffness vanishes.

The frozen execution of
`computations/endpoint_dynamical_response_check.py` has overall verdict
**FAIL** because its DR5 endpoint block has the opposite sign from the
registered source action. The separately frozen
`computations/endpoint_action_response_check.py` receipt passes AR1–AR6 on its
first execution: the $\mathcal K/\mathcal D$ equivalence residual is zero, the
direct-elimination residual is $1.511\times10^{-17}$, the covariance residual
is $2.220\times10^{-16}$, the anomalous-block norm is $0.390450933151$, and the
damped non-Hermiticity norm is $0.360569701415$.

The endpoint potential, nonzero-current background, damping mechanism, doubled
port-flux law, and full coupled fluctuation spectrum remain unselected.

---

## References

- `foundations/cassi-first-principles.md` §1.2—Yang/Yin attractor and fixed-point density fractions
- `foundations/cascade-suppression-formula.md`—registered conditional suppression law and evidence boundary
- `foundations/interscale-current-soliton.md`—density current, gauge current, endpoint circuit, and mixed-curvature force
- `foundations/particle-stationary-action-closure.md` §3.2—time-completed quadratic scale action
- `foundations/geometric-manifold-completion.md` §§2.4–2.5—two-rail circuit and phase-only endpoint gluing
- `foundations/endpoint-link-and-localization-boundary.md` §§3.6–3.9—gauge-covariant frozen and active charged-endpoint response
- `computations/interscale_port_matching_prereg.md`—frozen boundary-matching checks
- `computations/endpoint_robin_link_prereg.md`—frozen charged-link matching and capacity receipt
- `computations/endpoint_dynamical_response_prereg.md`—frozen failed energy-kernel response criteria
- `computations/endpoint_dynamical_response_check.py`—frozen failed block-matrix receipt
- `computations/endpoint_dynamical_response_report.md`—source-action sign review and FAIL verdict
- `computations/endpoint_action_response_prereg.md`—frozen source-action response criteria
- `computations/endpoint_action_response_check.py`—passing source-action analytic receipt
- `computations/endpoint_action_response_report.md`—AR1–AR6 outcome and scope boundary
- `computations/interscale_stress_attenuation_check.py`—conservation, endpoint matching, coherent-chain, and routed-chain checks
- `computations/endpoint_link_localization_check.py`—charged-link covariance, matching, and current-capacity checks

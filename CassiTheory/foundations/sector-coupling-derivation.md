# Conditional Sector Scale and the Dirac Density Obstruction

## Status: Derived conditional sector, fermionic, formation-dynamics and non-identifiability identities / Tested finite-mode production, continuum, scalar-vacuum and conditional dynamical restrictions / Calibrated electroweak anchor / Hypothesized physical fermion coupling—September 2026

## Abstract

The arithmetic scale $\kappa_{s,\mathrm{scale}}=\varphi^{-6}/v_0^2$ follows from the stipulated offset $\delta=3$ and the external electroweak anchor $v_0$. Its inverse square root is $\varphi^3v_0\approx1.04\ \mathrm{TeV}$. A physical interaction requires further microscopic input. The proposed chiral-scalar identification compares fields of different mass dimension and uses complex-conjugate bilinears whose simultaneous real positive values must be equal. Its displayed squared enforcement expression is generically non-Hermitian. The separate component-quadratic observables in the Dirac helper are nonnegative chiral-current densities. Their closed evolution depends on relative coherence; stationary positive-energy states also fail the proposed canonical population conversion. Adding the existing minimal conversion lift to a nonzero Dirac mass changes the golden population fixed point and allows transitions out of the positive-energy one-particle subspace. These are conditional boundaries on the specified microscopic and reduced descriptions. A physical fermion coupling requires an admissible interaction, a state and reservoir prescription, and a controlled density reduction.

A separately declared real scalar mass interaction admits a fermionic vacuum and an explicit production-energy ledger. Its finite-mode covariance evolution preserves Pauli bounds and vector charge, while a classical scalar mean field can supply coherent pair excitation with reciprocal feedback. This construction assumes its spinor content, vacuum, scalar source and finite-volume subtraction. Physical normalization, canonical density reduction, continuum quantum dynamics and localized particle formation remain open.

Independent continuum quadratures verify the sudden-source ultraviolet divergence, a specified static one-loop subtraction and a logarithmic initial-state overlap mismatch. At the unchanged coupling, a sufficient bound excludes two-body binding in the leading nonrelativistic scalar-exchange reduction. The renormalized spatial quantum model and its physical identification remain open.

The specified local static one-loop scalar energy has positive reference curvature but no global lower bound. An exact negative bulk-energy witness and a finite-energy spatial trial family establish this conditional restriction. The full nonlocal quantum energy, metastability and physical matter identification remain open.

The same supplied scalar parent has an exact periodic mediator background,
resolved carrier and spatial-mediator Floquet instabilities, and a signed-charge
continuity law permitting local separation from prepared complex carrier data.
Exactly empty carrier data remain empty. A frozen nonlinear comparison is
`INCONCLUSIVE`; period-sampled reconstruction identifies phase aliasing without
altering its verdict. Complex-scalar and Dirac parents reduce to the same slow
carrier equation while carrying different spin and statistics. The registered
dynamics therefore leave the microscopic action, state, normalization,
localized forming solution and particle discriminator as independent inputs.
The conditional continuum theorem additionally concerns only the entire
fixed-$Q$ minimizer set at strictly bound charge in the specified energy
space; it does not classify the simulated radiating clouds
or cover complex mediator/gauge sectors
(`computations/matter-formation-continuum-report.md` §§25–29, 36;
`foundations/matter-completion-boundary.md` §18).

## 1. The projection and its mathematical boundary

The distinction between a chiral scalar and a chiral density determines whether the proposed field map can describe the canonical state. The canonical two-fluid variables satisfy $E_Y,E_I\ge0$. The optional spinor correspondence uses

$$
B_R=\bar\psi P_R\psi,\qquad B_L=\bar\psi P_L\psi,
\qquad P_{R,L}=\frac{1\pm\gamma^5}{2}.
$$

### 1.1 Dimensions and the sector symbol

In four-dimensional natural units, $[\psi]=[M]^{3/2}$, $[B_{R,L}]=[M]^3$, and the optional condensate squares $\Psi_0^2,\Psi_1^2$ have dimension $[M]^2$. The formal expression

$$
\mathcal L_{\rm proj}^{\rm formal}
=\frac{\kappa_s}{2}\left[(B_R-\Psi_0^2)^2+(B_L-\Psi_1^2)^2\right]
$$

therefore subtracts quantities of different dimensions. A common real bridge mass $M_b$ could make the brackets homogeneous by replacing $\Psi_\alpha^2$ with $M_b\Psi_\alpha^2$. That operation addresses dimensions; the algebraic obstructions below remain for every positive real $M_b$.

The symbol $\kappa_s$ denotes a proposed sector interaction coefficient. It is distinct from the geometric pentagram transmission $K_{fw}=\varphi^{-1}$ in `foundations/wu-xing-cycle-structure.md` §1.3 and the charge-density coefficient in `predictions/cassi_definitions.md`. The mass dimension $-2$ would apply to a homogeneous dimension-six interaction. The formal scale in §2 selects no such interaction or coefficient.

### 1.2 Conjugacy and positivity

The adjoint of one chiral-scalar bilinear is the other. Since $\gamma^0P_R=P_L\gamma^0$,

$$
\boxed{B_R^\dagger=B_L.}
$$

For ordinary complex spinors in the Weyl basis, $\psi=(L,R)$ gives

$$
B_R=L^\dagger R,\qquad B_L=R^\dagger L=B_R^*.
$$

These quantities need not be real or positive. Taking $L=(1,0)$ and $R=(i,0)$ gives $(B_R,B_L)=(i,-i)$; taking $R=-L$ gives $(-1,-1)$. A pure left-handed spinor has both scalar bilinears zero despite a nonzero spinor density. The operator adjoint identity also constrains quantum expectation values. These two chiral scalars supply no two independent Hermitian positive-density operators.

If a common real normalization identifies both bilinears with real nonnegative condensate squares, conjugacy forces those squares to be equal. For $z=B_R$, the required golden ratio would impose

$$
z=\varphi z^*.
$$

Its real and imaginary parts obey $(1-\varphi)\operatorname{Re}z=0$ and $(1+\varphi)\operatorname{Im}z=0$. Therefore

$$
\boxed{B_R=\varphi B_L,\quad B_L=B_R^*
\quad\Longrightarrow\quad B_R=B_L=0.}
$$

Independent unequal bridge coefficients would insert the desired density ratio into the dictionary as an additional selected input. They would still need a real positive observable assignment for general states.

The frame densities $n_R=R^\dagger R$ and $n_L=L^\dagger L$ are nonnegative for ordinary complex spinors and can have ratio $\varphi$. They are components of chiral currents referred to a timelike observer, rather than the Lorentz scalars used above. A physical use of those currents requires an observer or foliation, a quantum-state and particle/antiparticle prescription, and an evolution law connecting them to the canonical conversion dynamics. None is selected by the arithmetic sector scale.

The helper `two-fluid/cassi_dirac_bridge.py` implements a separate nonnegative component-quadratic pair. Its chiral-current identification, normalization convention and dynamical closure limits are developed in §§1.5–1.6. Its spin and current diagnostics supply no established physical fine-structure interpretation.

### 1.3 Reality of the displayed interaction

A mass scale also leaves the action's adjoint problem unchanged. After factoring out a common dimensional bridge, write $B_R=x+iy$, $B_L=x-iy$ and let $A,B$ be real condensate targets. Then

$$
\operatorname{Im}(AB_R+BB_L)=(A-B)y,
$$

$$
\boxed{
\operatorname{Im}\left\{\frac{\kappa_s}{2}
\left[(B_R-A)^2+(B_L-B)^2\right]\right\}
=\kappa_s(B-A)y.}
$$

Both terms are generically complex when the condensates differ. They cannot define a real classical interaction or a Hermitian quantum interaction for arbitrary fields. Replacing an ordinary square by an absolute square would define a different interaction and would not make the two incompatible scalar targets simultaneously attainable.

The registered matrix and independent two-component calculations both have valid numerical receipts with empty failures. At $A=\varphi,B=1$ and $(B_R,B_L)=(i,-i)$, the linear interaction has imaginary part $+0.6180339887498949$ and the squared expression with unit coefficient has imaginary part $-0.6180339887498949$. The exact verdicts are `CONTRADICTS—chiral-scalar nonnegative-density identification` and `CONTRADICTS—displayed chiral projection interaction as a physical real action`. The five fixed witnesses, independent constructions and immutable identities are recorded in `computations/matter-formation-continuum-report.md` §12. These are checks of the specified algebraic identification and interaction; physical fermion production remains unselected.

### 1.4 Elementary carrier identity

A local invertible normalization preserves a field's Lorentz representation. The scalar carrier restriction in `foundations/particle-stationary-action-closure.md` has scalar elementary quanta under its stated canonical quantization. A Dirac field has a spinorial representation and fermionic quantization supplied as additional microscopic content. Matching a scalar mass to the electron mass supplies neither property. Fermionic topological solitons require a separate configuration space and quantization; this statement concerns the topologically trivial scalar restriction.

### 1.5 Chiral currents and the closed-density obstruction

The positive component map has a precise current interpretation once a spinor representation and observer frame are fixed. Use natural units $\hbar=c=1$, with the Dirac Hamiltonian

$$
H_D=\boldsymbol\alpha\cdot\mathbf p+\mu\beta,\qquad
\alpha_i=\begin{pmatrix}0&\sigma_i\\\sigma_i&0\end{pmatrix},\quad
\beta=\begin{pmatrix}1_2&0\\0&-1_2\end{pmatrix},\quad
\gamma^5=\begin{pmatrix}0&1_2\\1_2&0\end{pmatrix}.
$$

Here $\mu$ is the selected Dirac mass frequency in these units. The chiral components are $L=(u-v)/\sqrt2$ and $R=(u+v)/\sqrt2$. Thus the helper's two quadratics are twice the respective chiral number densities. For the algebra below choose the bookkeeping normalization $E_Y=Y_{\rm bridge}/2=L^\dagger L$ and $E_I=I_{\rm bridge}/2=R^\dagger R$. This convention supplies no physical conversion from spinor number density to the canonical energy densities.

Writing $z=L^\dagger R$, the Dirac equation gives the exact local balance

$$
\boxed{
\partial_tE_Y+\nabla\cdot\mathbf j_Y=2\mu\operatorname{Im}z,\qquad
\partial_tE_I+\nabla\cdot\mathbf j_I=-2\mu\operatorname{Im}z,}
$$

$$
\mathbf j_Y=-L^\dagger\boldsymbol\sigma L,\qquad
\mathbf j_I=R^\dagger\boldsymbol\sigma R.
$$

Restoring units multiplies these currents by $c$ and replaces $\mu$ in the source by $mc^2/\hbar$. A common real potential term $V(x,t)1_4$ cancels from both population derivatives. A Lorentz-scalar mass interaction instead changes the off-diagonal mass term and its source. These are classical complex-amplitude identities; quantum states, normal ordering and gauge anomalies require their own specification.

Relative coherence is essential to the conversion source. The constant-amplitude plane waves $L=\sqrt p(1,0)$ and $R=\pm i\sqrt{1-p}(1,0)$ have equal populations and currents between the two signs, but opposite sources $\dot E_Y=\pm2\mu\sqrt{p(1-p)}$. At $p=\varphi^{-1}$ the canonical imbalance $\varepsilon=E_Y-\varphi E_I$ is zero, while both massive Dirac sources remain nonzero. A state described only by the two densities therefore loses information needed for its subsequent closed Dirac evolution.

The closure obstruction has a general finite-dimensional form. For a fixed orthogonal density projector $P$ and a fixed Hermitian Hamiltonian, the population derivative is $\operatorname{tr}(i[H,P]\varrho)$. The commutator has zero diagonal blocks in the $P\oplus(1-P)$ decomposition. If this derivative depends only on the two populations for every positive density matrix, it must vanish: block-diagonal states realize every population pair and have zero derivative, while any nonzero off-diagonal commutator distinguishes states with the same populations. A nonzero autonomous two-population conversion law needs additional reduced-state structure or an open-system construction.

The obstruction also appears within the positive-energy free-particle sector, without the unrestricted phases of the preceding witness. A positive-energy plane wave is stationary in all its quadratic densities. For momentum $(0,0,p_z)$, helicity $h=\pm1$ and energy $E=\sqrt{\mu^2+p_z^2}$,

$$
E_Y=\frac{1-hp_z/E}{2},\qquad
E_I=\frac{1+hp_z/E}{2}.
$$

At rest both are $1/2$. The canonical source $-\lambda(1-q)(E_Y-\varphi E_I)$ is then nonzero at finite density and $\lambda>0$. The free Dirac law supplies no relaxation toward a universal golden chiral population ratio. Its helicity and momentum dependence remains explicit. These plane-wave statements establish neither a localized particle nor microscopic production.

### 1.6 The Dirac mass changes the minimal lift

The existing positive-fibre conversion flow reproduces the canonical diagonal law when its declared Hamiltonian commutes with the population projectors (`foundations/geometric-manifold-completion.md` §4.4). A Dirac mass introduces an off-diagonal Hamiltonian in the chiral basis. Its effect can be calculated in one homogeneous spin sector:

$$
\Gamma=\begin{pmatrix}E_Y&z^*\\z&E_I\end{pmatrix},\qquad
H=\mu\sigma_x,\qquad \operatorname{tr}\Gamma=\rho.
$$

With the two jumps $\sqrt\kappa|I\rangle\langle Y|$ and $\sqrt{\varphi\kappa}|Y\rangle\langle I|$, the component equations are

$$
\dot E_Y=2\mu\operatorname{Im}z-\kappa\varepsilon,\qquad
\dot E_I=-\dot E_Y,\qquad
\dot z=-i\mu(E_Y-E_I)-\frac{1+\varphi}{2}\kappa z.
$$

For a frozen positive rate $\kappa$, define $\delta=E_Y-E_I$, $s=1+\varphi$ and $\delta_*=(\varphi-1)\rho/s$. Solving the stationary equations gives

$$
\boxed{
\delta_{\rm st}=\frac{\delta_*}{1+8\mu^2/(s^2\kappa^2)},\qquad
z_{\rm st}=-\frac{2i\mu\delta_{\rm st}}{s\kappa}.}
$$

Every finite-rate massive stationary state has $0<\delta_{\rm st}<\delta_*$ for $\rho>0$. Its population ratio lies between unity and $\varphi$. The massless control recovers the canonical ratio. With the canonical rate $\kappa(\delta)=\lambda[1-q(\delta)]$, the same stationary equation has a unique root in $(0,\delta_*)$: on that interval $\varepsilon=s(\delta-\delta_*)/2$, the rate decreases with $\delta$, and the right-hand side of the boxed fixed-point equation decreases while its left-hand side increases. This is a stationary result; stability of the combined nonlinear flow requires a separate calculation.

The positive-energy restriction introduces another constraint on this particular jump construction. Let $\varrho_+$ be the normalized positive-energy rest spinor and $P_-=(1-H_D/\mu)/2$. The instantaneous leakage under the dissipator is

$$
\boxed{
\operatorname{tr}\!\left(P_-\dot\varrho_+\right)_{\rm conv}
=\sum_a\|P_-J_a\psi_+\|^2
=\frac{1+\varphi}{4}\kappa>0.}
$$

This transition leaves the positive-energy one-particle subspace. Interpreting it physically requires a Fock-space state, occupation and Pauli constraints, energy and charge ledgers, and a reservoir interaction. The amplitude-space leakage alone supplies no pair-production rate.

These equations constrain the combination of the standard Dirac mass and the specified minimal chiral conversion jumps. They leave alternative interactions, restricted preparations and controlled coarse-graining as separate microscopic possibilities. The frozen witnesses are independently reconstructed with no mismatches in `computations/matter-formation-continuum-report.md` §13; `computations/matter-formation-spinor-closure-prereg.md` supplies their definitions and stopping rule.

### 1.7 A real scalar mass source and its quantum production ledger

A Hermitian mass interaction supplies a conditional production candidate once the quantum field and source are independently specified. Let a real scalar $f$ couple through

$$
\boxed{\mathcal L_\psi=
\bar\psi[i\gamma^\mu\partial_\mu-(m_0+yf)]\psi.}
$$

In four spacetime dimensions, $[f]=[m_0]=M$, $[\psi]=M^{3/2}$ and the real coefficient $y$ is dimensionless. The interaction preserves vector $U(1)$ charge. Its source field, coefficient, fermionic anticommutation relations and vacuum are additional inputs. The canonical $E_Y,E_I$ equations do not select them.

In a homogeneous source, each retained momentum block has
$H_j(f)=\boldsymbol\alpha\cdot\mathbf p_j+(m_0+yf)\beta$,
$E_j=\sqrt{\mathbf p_j^2+(m_0+yf)^2}$ and spectral projectors
$P_{j,\pm}=(1_4\pm H_j/E_j)/2$. The covariance
$(C_j)_{ab}=\langle\hat\psi_{j,b}^\dagger\hat\psi_{j,a}\rangle$
evolves by $\dot C_j=-i[H_j,C_j]$. The reference vacuum is
$C_{j,0}=P_{j,-}(f=0)$. It has zero particle and hole excitations
and a rank-two covariance. Setting an ordinary classical spinor amplitude
to zero specifies a different state object.

The projector occupations retain the pair and charge information. Per spin state,

$$
n_j^+=\tfrac12\operatorname{tr}(P_{j,+}C_j),\qquad
n_j^-=\tfrac12\operatorname{tr}[P_{j,-}(1_4-C_j)],
$$

and therefore

$$
\boxed{2(n_j^+-n_j^-)=\operatorname{tr}C_j-2=0.}
$$

Unitary covariance evolution preserves $C_j^2=C_j$ and $0\le C_j\le1_4$,
so each occupation remains in $[0,1]$. Exciting a particle and an
oppositely charged hole preserves the vector charge. An instantaneous
particle projector in a driven source is a specified diagnostic; constant
initial and final Hamiltonians give unambiguous endpoint comparisons.

A sudden positive-mass change has a direct overlap formula. For
$E_a=\sqrt{p^2+m_a^2}$, the occupation per spin after
$m_0\to m_1$ is

$$
n_{\rm quench}=\frac12\left(1-\frac{p^2+m_0m_1}{E_0E_1}\right).
$$

A cyclic square pulse, with excursion mass $m_1$ for duration $T$ and
return to $m_0$, gives

$$
\boxed{n_{\rm pulse}=
\frac{p^2(m_1-m_0)^2}{E_0^2E_1^2}\sin^2(E_1T),\qquad
W_{\rm pulse}=2E_0n_{\rm pulse}.}
$$

Here $W_{\rm pulse}$ is the source's two-quench work per spin.
The formula has exact zero-production controls at $p=0$ and $m_1=m_0$.
Its oscillatory dependence on duration retains coherent return and
Pauli bounds; it supplies no irreversible conversion law.

Reciprocal scalar feedback follows from a specified finite-volume
Hamiltonian. Let $\Pi=V\dot f$, take a selected oscillator frequency
$\Omega$, and subtract the fixed reference covariance:

$$
\mathcal H=\frac{\Pi^2}{2V}+\frac{V\Omega^2f^2}{2}
+\sum_j\operatorname{tr}\{H_j(f)[C_j-C_{j,0}]\}.
$$

The subtraction fixes a constant and a linear scalar term. It makes
$f=\Pi=0,\ C_j=C_{j,0}$ stationary in the selected finite model.
The reciprocal equations are

$$
\dot f=\Pi/V,\qquad
\dot\Pi=-V\Omega^2f-y\sum_j\operatorname{tr}\{\beta(C_j-C_{j,0})\}.
$$

Together with the covariance commutator, these equations give
$d\mathcal H/dt=0$: the scalar force cancels the source-dependent
fermion work, while $\operatorname{tr}(H_j[H_j,C_j])=0$.
The energy partition is

$$
\boxed{\mathcal H=\mathcal E_s+\Delta\mathcal E_{\rm vac}
+\mathcal E_{\rm exc},\qquad
\mathcal E_{\rm exc}=\sum_j4E_jn_j^+,}
$$

with $\mathcal E_s=\Pi^2/(2V)+V\Omega^2f^2/2$ and
$\Delta\mathcal E_{\rm vac}
=\sum_j[-2E_j-\operatorname{tr}(H_jC_{j,0})]$.
The vacuum-polarization contribution may be negative. Scalar energy
loss therefore includes both polarization and excitation energy.

This is a semiclassical finite-mode construction: the scalar is a
classical mean field and the fermion state remains Gaussian.
Its reference subtraction establishes no renormalized continuum limit.
Renormalized homogeneous fermion backreaction also requires ultraviolet
counterterms and a compatible initial quantum state; Baacke, Heitmann and
Pätzold give such a one-loop construction and treat its initial
singularities [arXiv:hep-ph/9806205](https://arxiv.org/abs/hep-ph/9806205).
The specified witness box, four retained momentum cells, coupling and
oscillator schedule are in
`computations/matter-formation-fermion-production-prereg.md`.
Independent full-covariance and Bloch-vector calculations reproduce all
32 exact quench/pulse rows and six trajectories. The finest closed
trajectory reaches per-spin occupation $0.5729566253$ with relative
energy error $5.6211\times10^{-5}$ and time-convergence ratio $4.00277$;
reciprocal feedback changes the normalized scalar trajectory by $0.03464$.
All 1,185 verification checks pass, including 1,494,186 raw scalar
comparisons. The exact scoped verdicts, source-bound receipts and
implementation provenance are in
`computations/matter-formation-continuum-report.md` §14.
Physical mode content and scales, a two-fluid identification, the
accuracy of the mean-field approximation, spatially localized production
and measured particle identities remain unselected.

### 1.8 Continuum vacuum and initial-state requirements

Adding arbitrarily high momenta exposes contributions that a finite set
of modes cannot resolve. For the explicitly declared isotropic measure
$\int_{\mathbf p}^{\Lambda}=(2\pi^2)^{-1}\int_0^\Lambda p^2dp$,
occupation $n$ remains per spin. The pair density is
$N_{\rm pair}=2\int_{\mathbf p}^{\Lambda}n$, the combined particle and
antiparticle density is $N_{\rm exc}=2N_{\rm pair}$, and their positive
excitation energy is $\rho_{\rm exc}=4\int_{\mathbf p}^{\Lambda}E_{\rm out}n$.

A sudden mass change has $n_q=\delta^2/(4p^2)+O(p^{-4})$, where
$\delta=m_1-m_0$. Its pair density therefore diverges linearly and its
excitation energy quadratically. A cyclic square pulse at any fixed
positive duration has twice the leading coefficients:

$$
\boxed{\begin{array}{c|cc}
&N_{\rm pair}/\Lambda&\rho_{\rm exc}/\Lambda^2\\\hline
\text{sudden change}&\delta^2/(4\pi^2)&\delta^2/(4\pi^2)\\
\text{square pulse}&\delta^2/(2\pi^2)&\delta^2/(2\pi^2)
\end{array}\quad(\Lambda\to\infty).}
$$

The pulse energy also has an oscillatory $O(\Lambda)$ cutoff term.
These positive out-particle energies depend on source preparation;
subtracting a static vacuum energy does not make the sudden histories
finite-energy continuum preparations.

The instantaneous negative-energy sea has a separate local divergence.
Including both spin states, its fixed-reference energy per momentum cell is

$$
v(p,m)=2\left[\frac{p^2+mm_0}{E_0}-E\right]
=-\frac{\delta^2}{p}
+\frac{\tfrac32m_0^2\delta^2+m_0\delta^3+\delta^4/4}{p^3}
+O(p^{-5}).
$$

Its integrated leading term is $-\delta^2\Lambda^2/(4\pi^2)$.
The scalar mass, cubic and quartic local contributions consequently
require counterterms after the constant and linear reference terms have
been fixed. A specified static subtraction can remove the Taylor
polynomial $T_4v$ through fourth order in $\delta$ and impose zero
reference derivatives through that order. Its finite remainder is

$$
\mathcal V_R(m)=
-\frac{m^4\log(m^2/m_0^2)-2m_0^3\delta-7m_0^2\delta^2
-\tfrac{26}{3}m_0\delta^3-\tfrac{25}{6}\delta^4}{16\pi^2}.
$$

This condition fixes a static one-loop subtraction scheme. Physical
finite parts and a globally viable scalar potential require matching.
Baacke, Heitmann and Pätzold use $m=g\phi$ with no additive bare fermion
mass; their model-specific absence of an infinite scalar-mass counterterm
does not apply to the present expansion $m=m_0+yf$.

Time dependence also introduces a kinetic divergence. The first
adiabatic correction to a negative-energy Bloch vector is
$r_y^{(1)}=-p\dot m/(2E^3)$, giving energy
$\dot m^2 I_\Lambda/4$ at the reference, where

$$
I_\Lambda=\frac{\operatorname{arsinh}(\Lambda/m_0)-u-u^3/3}{2\pi^2},
\qquad u=\frac{\Lambda}{\sqrt{\Lambda^2+m_0^2}}.
$$

A local scalar kinetic counterterm has
$\delta Z_\Lambda=-y^2I_\Lambda/2$ in this reference convention.
Its logarithmic normalization agrees with the homogeneous one-loop
counterterm of Baacke, Heitmann and Pätzold, Eq. (4.24).

Initial-state regularity is an additional requirement. At nonzero
$\nu=\dot m(0)$, the pure normalized first-adiabatic-direction state
has overlap occupation
$n_{\rm ov}=\tfrac12[1-(1+b^2)^{-1/2}]$ relative to the static vacuum,
where $b=p\nu/(2E_0^3)$. Thus
$n_{\rm ov}=\nu^2/(16p^4)+O(p^{-6})$, and the overlap excitation energy
has logarithmic coefficient $\nu^2/(8\pi^2)$. This comparison diagnoses
the ultraviolet mismatch between the two specified preparations; it
does not compute renormalized time-dependent production.
Even when $\dot m(0)=0$, higher initial derivatives can generate
initial singularities: the cited one-loop construction treats the
$\ddot m(0)$ term in its Eq. (5.1) by a Bogoliubov preparation.

The cutoff sequence, independent quadratures and exact-identity
requirements are fixed in
`computations/matter-formation-continuum-admissibility-prereg.md`.
A renormalized dynamical energy ledger still requires compatible
initial data, common counterterms in force and stress, and controlled
regulator removal.

### 1.9 Localized fermionic states and the two-body reduction

Pair excitation supplies particles that may propagate apart. Binding
requires a separate spatial mechanism and a total-energy comparison.
In the stated static leading nonrelativistic reduction, the scalar
equation and its Green function are

$$
(-\nabla^2+\Omega^2)f=-y\rho_s,\qquad
G_\Omega(r)=\frac{e^{-\Omega r}}{4\pi r}.
$$

Eliminating the scalar contributes
$-\tfrac12y^2\int d^3x\,d^3x'\rho_s(x)G_\Omega(x-x')\rho_s(x')$.
After absorbing the one-body self-energies in the reference mass, the
cross term gives $V_Y(r)=-\alpha_Ye^{-\Omega r}/r$ with
$\alpha_Y=y^2/(4\pi)$ and reduced mass $\mu_{\rm red}=m_0/2$.
For each partial wave, the positive zero-energy
Birman–Schwinger kernel has trace

$$
\boxed{\operatorname{tr}K_\ell
=\frac{2\mu_{\rm red}}{2\ell+1}\int_0^\infty r|V_Y|\,dr
=\frac{B}{2\ell+1},\qquad
B=\frac{\mu_{\rm red}y^2}{2\pi\Omega}.}
$$

If $B<1$, no eigenvalue reaches unity and no negative-energy two-body
level exists in any partial wave. The converse is not implied.
This sufficient Bargmann bound concerns the stated pairwise
nonrelativistic Hamiltonian. Relativistic effects, annihilation,
vacuum polarization and cooperative many-body states require their
own calculations.

A spatial scalar–Dirac candidate needs a normalized microscopic action,
a scalar tending to its vacuum at infinity, occupied Dirac gap levels,
consistent Pauli filling and signed fermion number, and a renormalized
sea contribution in the same energy functional. Its fixed-charge
energy must lie below the relevant free-particle and fragmentation
thresholds. Constrained spatial and dynamical stability then have to
be established, followed by a real-time formation channel with energy
and charge accounting. Farhi, Graham, Jaffe and Weigel illustrate why
the sea energy is indispensable in three spatial dimensions.
The prepared scalar carrier charge $Q_C$ supplies no identification
with this fermion number or spin representation.

At the frozen normalized inputs $m_0=1$, $y=0.25$ and $\Omega=3$,
independent quadratures give $B=0.00165786399054<1$.
The continuum and two-body calculation passes all 645 independent
payload comparisons, including 539 numerical values and ten symbolic
identities in each program. Its exact scoped verdicts, finite-cutoff
errors and source identities are recorded in
`computations/matter-formation-continuum-report.md` §15.

The pairwise no-binding result does not decide a collective bag. In the
declared static local-density restriction, with $m_0=1$, $y=1/4$,
$\Omega=3$, $|m(x)|\le1$ and the specified one-loop remainder, the favorable
fourfold particle/antiparticle occupation obeys
$$
\boxed{\mathcal E_{\mathrm{LDA}}-N_{\mathrm{exc}}
\ge\frac12\int|\nabla f|^2\,d^3x
+\frac{3236}{45}\int(1-|m|)^2\,d^3x\ge0.}
$$
The single-sign sector has coefficient $3238/45$. Thus this restricted
functional has no state below the separated-particle threshold, while exact
finite-fermion spectra, nonlocal sea effects, exchange, metastability,
mass-enhancing configurations and physical particle assignment remain open.
The bound is a conditional model restriction, not a general many-body
localization theorem (`computations/matter-formation-continuum-report.md`
§§15.6–15.7).

### 1.10 Global lower boundedness of the specified static energy

Positive reference curvature alone cannot establish a globally stable
vacuum. Combining the supplied harmonic scalar potential with the
static remainder in §1.8 gives, at $m_0=1$, $y=1/4$ and $\Omega=3$,

$$
\mathcal U(m)=72(m-1)^2+\mathcal V_R(m),\qquad
\mathcal U(1)=\mathcal U'(1)=0,\qquad
y^2\mathcal U''(1)=9.
$$

The large-field asymptote has a negative leading coefficient:

$$
\lim_{m\to\infty}
\frac{\mathcal U(m)}{m^4\log(m^2)}
=-\frac1{16\pi^2}.
$$

A fixed finite-field witness gives an exact sign proof. At $m=64$,
the inequalities $\log2>2/3$ and $\pi^2<10$ imply

$$
\boxed{\mathcal U(64)<-\frac{8265011}{64}<0.}
$$

The directly evaluated value is $-168382.922633654$ in the supplied
normalization. This amplitude is an algebraic witness, with no
identification as a physical mass or preferred field value.

For the explicitly local functional
$\mathcal E[f]=\int[\tfrac12|\nabla f|^2+\mathcal U(1+yf)]d^3x$,
take a plateau $f=252$ inside radius $R$, a linear transition to zero
over width $\sqrt R$, and zero exterior. Each trial field has finite
energy and the reference boundary at infinity. Its negative core
energy grows as $4\pi\mathcal U(64)R^3/3$. The gradient energy is
$O(R^{3/2})$ and the absolute shell-potential bound is $O(R^{5/2})$.
Consequently $\mathcal E\to-\infty$ along this family.
Sixteen symbolic and exact-rational checks verify the stated
identities and the positive zero-loop control
(`computations/matter-formation-continuum-report.md` §16).

The conclusion applies to this local static one-loop functional.
It omits the full nonlocal fermionic determinant and higher derivative
terms. A completion retaining the same bulk potential and a
subextensive interface energy inherits the volume argument.
Extension to fixed nonzero fermion charge needs a charge-preserving
finite-energy valence construction separated from the neutral bubble.
Local extrema, metastable configurations, formation times and their
physical identification remain separate questions.

### 1.11 Autonomous scalar-parent dynamics

The supplied scalar parent can generate its own time-dependent carrier
coefficient. After the phase change
$z=e^{-it/(2a)}\chi$ and the definition $B=e_C+1/(4a)$, its dimensionless
Lagrangian is

$$
\mathcal L=
\frac{c_\Psi}{2}\dot f^2-\frac12|\nabla f|^2
+a|\dot z|^2-\frac{k_{Cx}}2|\nabla z|^2
-\frac{u_\rho}{4}(f^2-1)^2
-[B-h_C+h_Cf^2]|z|^2-\frac{u_C}{2}|z|^4 .
$$

The Euler–Lagrange equations conserve the rotating-frame energy and the signed
charge

$$
\mathcal Q_a=-2a\int\operatorname{Im}(z^\ast\dot z)\,d^3x .
$$

At $a=1/16$, $c_\Psi=1/8$, $u_\rho=4$ and carrier-free initial data, the
mediator has the exact periodic solution

$$
\boxed{
f_0(t)=\sqrt{\frac32}\,
\operatorname{dn}\!\left(\sqrt{24}\,t,\frac23\right).
}
$$

A carrier Fourier mode reduces to the Lamé/Hill problem

$$
\frac{d^2y}{du^2}
+\left[\Lambda-h_Cm\,\operatorname{sn}^2(u,m)\right]y=0,
\qquad
m=\frac23,\quad
\Lambda=\frac1{6a}+\frac12+\frac{h_C}{3}+\frac{k^2}{3}.
$$

The complete fixed six-gap schedule contains one resolved accessible
instability. Its carrier wave number is $k=2.6753367051$ and its independently
matched physical-time Floquet exponents are
$0.0017215448659$ and $0.0017215449183$. Constant-mediator and
zero-coupling controls remain stable. The result is conditional linear
amplification of a supplied nonzero classical carrier seed.

The same background has a faster spatial mediator channel. A Fourier
perturbation obeys

$$
-\eta''+6m\,\operatorname{sn}^2(u,m)\eta=\Lambda_f\eta,
\qquad
\Lambda_f=\frac{14+p^2}{3}.
$$

The physical interval is

$$
\boxed{
0<p<\sqrt{2\sqrt7-4}.
}
$$

At the registered comparison mode, the independently matched exponent is
$0.362037120923$, about $210.3$ times the carrier exponent. This establishes a
conditional instability of the homogeneous mediator background on boxes that
admit the mode.

Complex carrier data also have an exact local transport law:

$$
\rho_a=-2a\,\operatorname{Im}(z^\ast\dot z),\qquad
\mathbf j_a=k_{Cx}\operatorname{Im}(z^\ast\nabla z),\qquad
\boxed{\partial_t\rho_a+\nabla\cdot\mathbf j_a=0.}
$$

For
$z(x,0)=\epsilon[\cos(px)+i\cos(2px)]$ and $\dot z(x,0)=0$,
the initial charge density vanishes while

$$
\partial_t\rho_a(x,0)
=3k_{Cx}\epsilon^2p^2\cos(px)\cos(2px),
$$

which has both signs and zero cell integral. This is transport from prepared
complex carrier data. Exactly empty carrier data remain empty.

The full plane-symmetric equations conserve energy and signed charge. The
evolutions include carrier backreaction and self-interaction. Their frozen
cross-method verdict is `INCONCLUSIVE`: a fixed phase-space coordinate crosses
its carrier threshold before mediator entry, while its period-sampled
reconstruction recovers the accepted Floquet rates and mediator-first secular
ordering. The reconstruction diagnoses phase aliasing and leaves the
frozen verdict unchanged. These plane-symmetric calculations supply no
finite-energy localized forming solution
(`computations/matter-formation-continuum-report.md` §§25–28).

A separate radial calculation shows initially diffuse clouds creating their
own depleted mediator core under the same selected positive-inertia scalar action:
$a=1/16$, $c_\Psi=1/8$ and inherited **Mapped**
$h_C=2.9598260763447164$. Diffuse Gaussian clouds carry supplied signed
$\mathcal Q_a=256$ at widths $w=4,8$, distinct from prepared population $Q_C=256$.
Starting with real mediator $f=1$, independent RK4 mean core fractions inside $r<8$
over $32\le t\le48$ are $0.7476513029152703$ and
$0.5637353289380143$, versus matched $h_C=0$ controls
$0.054518103963512976$ and $0.15375753009303855$. No trap or damping is
imposed. The result is `EMERGES-conditional finite-charge radial
condensation` for supplied initially charged data. A conditional continuum
theorem applies to the same positive-inertia real-mediator/full-complex-carrier
action: strict binding $I(Q)<\Omega_\infty Q$ yields attainment, compactness
of minimizing sequences modulo translations and carrier phase, and nonlinear
orbital stability of the entire fixed-$Q$ minimizer set. The proof establishes
the global conservative flow and excludes dispersion, splitting and escaping
neutral energy (`computations/matter-formation-continuum-report.md` §36.6).
Stability covers arbitrary small perturbations in the specified energy
space, including nonradial and nearby-charge perturbations. The fixed
trial's sufficient threshold and its $Q=256$ binding benchmark are given
there in §36.5. Here $Q$ is the dimensionless
supplied signed charge, distinct from prepared carrier population $Q_C$. The
theorem does not prove uniqueness, stability of a selected profile, asymptotic
convergence, or membership/capture/stability of the §35 radiating clouds; their
nonradial and long-time behavior, complex-mediator-phase behavior and
all-sector survival remain open. It covers no complex mediator or gauge
sector. Physical action selection, physical normalization and units, quantum
state and creation, spin/statistics and particle identity remain open
(`computations/matter-formation-continuum-report.md` §§35–36;
`foundations/matter-completion-boundary.md` §§17–18).


### 1.12 Slow-sector non-identifiability

The measured slow carrier equation cannot select its microscopic parent. For a
prescribed real background $U$, the complex-scalar action

$$
\mathcal L_B=
|\partial_t\Phi|^2-|\nabla\Phi|^2-(m^2+2mU)|\Phi|^2
$$

and the substitution $\Phi=e^{-imt}\psi_B/\sqrt{2m}$ give

$$
i\partial_t\psi_B=
\left(-\frac{\nabla^2}{2m}+U\right)\psi_B
+\frac{\partial_t^2\psi_B}{2m}.
$$

The slow-envelope limit removes the final term. A separately supplied Dirac
parent,

$$
i\partial_t\Psi_D=
\left(-i\boldsymbol\alpha\cdot\nabla+\beta m+U\right)\Psi_D,
$$

has a lower component
$\eta_D=-i\boldsymbol\sigma\cdot\nabla\psi_D/(2m)+O(m^{-2})$ and therefore

$$
i\partial_t\psi_D=
\left(-\frac{\nabla^2}{2m}+U\right)\psi_D+O(m^{-2}).
$$

The scalar envelope and each fixed Dirac spin component consequently share
the registered leading density evolution and current conservation. Their
canonical algebras remain distinct:

$$
|\alpha_B|^2-|\beta_B|^2=1,\qquad
|\alpha_F|^2+|\beta_F|^2=1.
$$

They therefore differ in spin, exchange, stimulated occupation and
saturation even when their prescribed low-occupation slow trajectories agree.
The state prescription remains independent because the positive-frequency
splitting defines the vacuum. Physical units remain independent because
length, time and field rescalings can preserve the same normalized equations.

Let $\mathfrak M$ contain a microscopic field representation, canonical
algebra, state rule and unit map, and let $\mathfrak D$ contain the registered
dimensionless carrier observables. The two explicit parents prove

$$
\boxed{\mathcal P:\mathfrak M\longrightarrow\mathfrak D
\quad\text{is many-to-one}.}
$$

A complete matter claim must fix one canonical action and state, calibrate its
physical units and couplings, support continuum-localized stable states, form
those states dynamically with conserved total energy and charges, and expose
a particle observable that distinguishes spin, statistics and charges. The
registered slow dynamics leave those selections open
(`computations/matter-formation-continuum-report.md` §29).

## 2. The conditional scale and electroweak anchor

The cascade arithmetic determines a scale once its dimensionful anchor and offset are declared. With $E_n=M_{\rm Pl}\varphi^{-n}$, the exact step-80 value is $E_{80}=233.2\ \mathrm{GeV}$ at the displayed precision. The calibrated $v_0=246\ \mathrm{GeV}$ instead has coordinate $n(v_0)\approx79.89$. These two inputs define two related scale evaluations.

Using the exact cascade value gives

$$
\kappa_{s,80}=\frac{\varphi^{-6}}{E_{80}^2}
=M_{\rm Pl}^{-2}\varphi^{154},\qquad
\kappa_{s,80}^{-1/2}=E_{77}\approx987.7\ \mathrm{GeV}.
$$

The exponent identity $154/2=77$ follows exactly from the declared offset $\delta=3$. Using the calibrated VEV gives the formal coefficient-free candidate

$$
\boxed{
\kappa_{s,\mathrm{scale}}=\frac{\varphi^{-6}}{v_0^2}
\approx9.21\times10^{-7}\ \mathrm{GeV}^{-2}
=0.921\ \mathrm{TeV}^{-2},\qquad
M_{s,\mathrm{scale}}=\varphi^3v_0\approx1042.07\ \mathrm{GeV}.}
$$

Its coordinate is $n(v_0)-3\approx76.89$, and its mass lies $5.50\%$ above $E_{77}$. The inherited electroweak offset is explicit. The equality to an integer cascade coordinate applies to the $E_{80}$-anchored expression.

More generally, a stipulated offset $\delta$ gives $\varphi^{-2\delta}/v_0^2$ and $\varphi^\delta v_0$. The choice $\delta=3$ is shared with the conditional phase-resolution construction in `gravity/quantum-gravity.md` §2.1. It selects no microscopic operator, matrix element or interaction rate. The reciprocity between $\varphi^{-6}$ and the Qi-gravity factor $\xi=\varphi^6$ is arithmetic. The numerical evaluations are recorded by `computations/kappa_s_rung_identity.py`.

## 3. Optional coefficient choices

An interaction coefficient requires an interaction to multiply. The formal readings $C\kappa_{s,\mathrm{scale}}$ below are scale conventions without a selected physical operator:

| $C$ | Formal coefficient | Formal inverse-square-root scale |
|---|---:|---:|
| $1$ | $0.921\ \mathrm{TeV}^{-2}$ | $1.042\ \mathrm{TeV}$ |
| $\varphi^{-1}$ | $0.569\ \mathrm{TeV}^{-2}$ | $1.326\ \mathrm{TeV}$ |
| $\varphi^{-2}$ | $0.352\ \mathrm{TeV}^{-2}$ | $1.686\ \mathrm{TeV}$ |

The order-of-magnitude phrase $1/\mathrm{TeV}^2$ does not discriminate among them. The solver convention $\lambda=0.1$, its Hypothesized Wu Xing interpretation and the de-resonance principle supply no operator selection or physical value of $C$. A viable Dirac/two-fluid coupling needs a dimensionally homogeneous Hermitian interaction built from suitable observables, followed by matching to the canonical density dynamics.

## 4. The transport-mobility bridge

A dimensional inconsistency also prevents the displayed sector scale from predicting the dimensionless solver mobility. The expression

$$
\chi=\frac{\kappa_s\varphi^{-1}}{m_e(1+\varphi)}
$$

would have dimension $[M]^{-3}$ if $[\kappa_s]=[M]^{-2}$. A normalization factor would need dimension $[M]^3$ before the result could be compared with a dimensionless $\chi$:

$$
\chi=\mathcal N_{\rm pde}
\frac{\kappa_s\varphi^{-1}}{m_e(1+\varphi)}.
$$

The expression specifies neither that factor's physical origin nor a matching calculation. The formal substitution $C=1$ yields $4.25\times10^{-4}$ in mixed units, which is not a dimensionless mobility. The back-solved numerical normalization $\mathcal N_{\rm pde}\approx2.35\times10^3$ is Mapped in `parameter-inventory.md` §10. Its apparent closure depends on solver conventions and does not define a microscopic coupling (`computations/n_pde_bridge_check.py`).

A physical bridge requires a specified Hermitian microscopic interaction, selected current or density observables, state preparation, and a coarse-graining calculation. Reading numerical grid constants cannot supply those missing ingredients. The solver's $\chi\in[0.5,1.0]$ remains a calibrated numerical target.

## 5. Conditional arithmetic and open predictions

| Label | Statement | Status |
|---|---|---|
| K1 | $M_{s,\mathrm{scale}}=\varphi^3v_0\approx1.04\ \mathrm{TeV}$ and $\kappa_{s,\mathrm{scale}}\approx0.921\ \mathrm{TeV}^{-2}$; the exact cascade-anchor counterpart is $E_{77}$ | Derived conditional arithmetic / Calibrated VEV input |
| K2 | A microscopic coupling and coarse-graining could predict a dimensionless solver mobility | Hypothesized; operator, normalization and state-dependent matching are unselected |
| K3 | A physical Dirac/two-fluid equilibration scale is associated with the proposed offset | Hypothesized; the scale arithmetic supplies no dynamics |

The K labels identify conditional scale statements and remain separate from the numbered prediction catalog. The excluded chiral-scalar positive-density identification and non-Hermitian enforcement expression provide no prediction for particle production, equilibration or transport.

## 6. Epistemic boundaries

The exact results are the conditional scale arithmetic, the field dimensions, the chiral-scalar adjoint and interaction-reality obstructions, the chiral-current identities, the closed-population obstruction, and the stationary and positive-energy boundaries of the specified massive conversion lift. The external $v_0$ anchor is Calibrated. Selected coefficient readings and the back-solved numerical bridge retain their ledgered status. The physical coupling, state preparation, microscopic production process and controlled reduction to canonical density dynamics remain Hypothesized or open.

The declared scalar–fermion model additionally supplies exact overlap,
charge and energy identities, continuum asymptotes, a specified static
subtraction, an initial-overlap logarithm and a sufficient two-body
no-binding condition. Its specified mass-depleting local-density extension,
including the local one-loop remainder and favorable fourfold occupation
relaxation, also excludes subthreshold collective binding for $|m|\le1$.
Independent computations verify finite-mode production and feedback as well as
these continuum restrictions
(`computations/matter-formation-continuum-report.md` §§14–15.7).
The static subtraction fixes a reference scheme. Dynamical
renormalization, physical finite parts, relativistic and many-body
localization, and a common formation/stability calculation remain open.

The scalar temporal parent additionally has an exact periodic orbit, a resolved
carrier Floquet instability, a faster spatial mediator instability, exact
energy and signed-charge ledgers, and local charge separation from prepared
complex carrier data. Its frozen plane-symmetric nonlinear comparison remains
`INCONCLUSIVE`. Exactly empty carrier data remain invariant. The explicit
scalar/Dirac reduction proves that the measured slow carrier dynamics have
multiple microscopic parents with different spin and statistics. A canonical
action, quantum state, physical normalization, continuum-localized formation
and observable particle discriminator remain open
(`computations/matter-formation-continuum-report.md` §§25–29).

A distinct finite-time radial calculation qualifies `EMERGES-conditional
finite-charge radial condensation` for the supplied positive-inertia
real-mediator/complex-carrier action ($a=1/16$, $c_\Psi=1/8$, inherited
**Mapped** $h_C=2.9598260763447164$). Diffuse clouds begin with supplied
signed $\mathcal Q_a=256$ at $w=4,8$, distinct from prepared population $Q_C=256$;
their independent-RK4 mean core fractions inside $r<8$ over
$32\le t\le48$ are $0.7476513029152703$ and $0.5637353289380143$,
versus matched $h_C=0$ controls $0.054518103963512976$ and
$0.15375753009303855$. No imposed trap or damping is used. The result is
finite-time, finite-charge radial scalar condensation. The conditional §36
theorem concerns the entire minimizer set at strictly bound charge in the
specified energy space; it does not establish
membership, capture, nonradial behavior or long-time stability of these
radiating clouds, and it covers no complex mediator or gauge sector.
Canonical microscopic action selection, physical units and normalization,
quantum state and creation, spin/statistics and particle identity remain open
(`computations/matter-formation-continuum-report.md` §§35–36;
`foundations/matter-completion-boundary.md` §§17–18).

Finite quantum occupation further restricts the density identification.
Ordinary two-mode Bose/Fermi transfers agree with the specified unsaturated
carrier process at one carrier but add stimulation or blocking at two;
the fully occupied fermionic state cannot follow the unrestricted canonical
drift. A scalar half-angle phase also fails the full spatial rotation
algebra. Independently qualified anomaly identities still allow multiple
color counts and a continuous charge family with a right-handed neutrino.
These conditional constraints leave the physical microscopic sector and
state map open (`computations/matter-formation-continuum-report.md` §38;
`foundations/matter-completion-boundary.md` §19).


The canonical scalar topology checks find contractible regular
positive-density domains with no rotation or exchange
Finkelstein–Rubinstein sign. Separated exchange, large-gauge and compact
target sectors need independently selected configuration spaces and quantum
lifts. The massless $SU(2)_{\rm top}$ comparison supports only finite-domain
radial stationarity and radial energetic qualification. A smooth pointwise
map of the two canonical densities cannot generate its degree density.
In the optional gauge sector, fixed
nonzero fundamental and adjoint norms leave a physical relative $S^2$;
joint gauge cancellation is distinct from a nonconstant relative texture.
The PA12 soft adjoint amplitude gives strict first-order descent for every
hard-norm nonzero-Hopf field and contracts the included hard-norm loops. A
relaxed soft-amplitude state or separately constrained hard-norm model remains
open (`computations/matter-formation-continuum-report.md` §§12.7–12.12,
18–20).

The specified local static one-loop energy has positive reference
curvature but no global lower bound (§1.10). A physical completion
needs a justified bulk and interface energy before it can support a
global particle-ground-state claim.

The canonical real-density state and its slow carrier reductions admit scalar
and spinor microscopic parents. A fermionic theory therefore requires the
independent selection of a Dirac field, its canonical algebra, state and
interaction. A physical mass fit, cascade coordinate and formal
coefficient-scale identity leave that selection open.

## References

- `foundations/unified-lagrangian.md` §§2, 5–7—optional fermion sector and action assembly.
- `foundations/particle-stationary-action-closure.md` §8.12—scalar physical-normalization and particle-identity boundary.
- `computations/matter-formation-normalization-prereg.md`—frozen unit-normalization, bilinear and action-reality checks.
- `computations/matter-formation-continuum-report.md` §§12–29, 35–36—normalization and identity boundaries, scalar and fermionic production witnesses, conditional formation dynamics, the microscopic non-identifiability and continuum minimizer-set theorem, and finite-charge radial condensation.
- `foundations/matter-completion-boundary.md` §§12, 17–18—conditional completion boundary, finite-charge radial formation scope and conditional minimizer-set stability boundary.
- `computations/matter-formation-spinor-closure-prereg.md`—frozen positive-observable, closed-conversion, massive fixed-point and positive-energy witnesses.
- `computations/matter-formation-spinor-closure-implementation-recovery.md`—execution provenance and accepted receipt location under the scientific preregistration's recovery rule.
- `computations/matter_formation_spinor_closure.py` and `computations/verify_matter_formation_spinor_closure.py`—independent four-component and reduced-component witnesses.
- `computations/matter-formation-fermion-production-prereg.md`—real scalar mass source, fermionic state, finite-volume energy ledger and frozen independent witnesses.
- Patrick B. Greene and Lev Kofman, *Preheating of Fermions* (1998), [arXiv:hep-ph/9807339](https://arxiv.org/abs/hep-ph/9807339)—standard coherent fermion excitation and Pauli-bounded occupation.
- Juergen Baacke, Katrin Heitmann and Carsten Pätzold, *Nonequilibrium dynamics of fermions in a spatially homogeneous scalar background field* (1998), [arXiv:hep-ph/9806205](https://arxiv.org/abs/hep-ph/9806205)—one-loop backreaction, renormalization and initial-state requirements.
- `computations/matter-formation-continuum-admissibility-prereg.md`—frozen continuum asymptotes, static subtraction, initial overlap and two-body localization criterion.
- `computations/matter-formation-scalar-vacuum-prereg.md`—frozen local static lower-boundedness criterion.
- `computations/verify_matter_formation_scalar_vacuum.py`—symbolic identities, exact-rational sign witness and spatial trial-energy scaling.
- V. Bargmann, *On the Number of Bound States in a Central Field of Force* (1952), [doi:10.1073/pnas.38.11.961](https://doi.org/10.1073/pnas.38.11.961)—sufficient partial-wave bound-state counting.
- E. Farhi, N. Graham, R. L. Jaffe and H. Weigel, *Searching for Quantum Solitons in a 3+1 Dimensional Chiral Yukawa Model* (2001), [arXiv:hep-th/0112217](https://arxiv.org/abs/hep-th/0112217)—localized fixed-fermion-number energies including the renormalized sea.
- `foundations/geometric-manifold-completion.md` §4.4—minimal positive-fibre conversion lift.
- `foundations/yin-yang-qi-dynamical-geometry.md` §§5–7—off-diagonal coherence and declared Hamiltonian scope.
- `two-fluid/cassi_dirac_bridge.py`—exploratory Dirac kinetics and nonnegative quadratic, spin and current diagnostics; physical density and fine-structure interpretations remain unestablished.
- `foundations/dimensionful-cascade.md` §§2–3—cascade scales and coordinates.
- `gravity/quantum-gravity.md` §2.1—conditional shared offset $\delta=3$.
- `computations/kappa_s_rung_identity.py`—formal sector-scale arithmetic.
- `computations/n_pde_bridge_check.py`—solver-convention dependence of the numerical mobility bridge.
- `foundations/deriving-remaining-gaps.md` §3.3—electroweak anchor offset.
- `foundations/dimensionful-constants-status.md` §2.1—solver normalization and external scales.
- `foundations/wu-xing-cycle-structure.md` §1.3—distinct pentagram transmission coefficient.
- `principles/de-resonance-principle.md`—physical selection assumptions.
- `parameter-inventory.md` §§3.3, 10—mobility status and Fit-Status Ledger.

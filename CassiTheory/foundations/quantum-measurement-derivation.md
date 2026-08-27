# CassiFI Quantum Dynamics and Measurement

## Status: Derived conditional (regulated quantum mechanics); Hypothesized (CassiFI physical identification)—August 2026

## Abstract

The CassiFI field law supplies a finite, metric-bearing Hamiltonian configuration and a topological apparatus state. Canonical quantization of that regulated configuration gives a linear Schrödinger wavefunctional, the standard free-particle dispersion, configuration-space entanglement, conserved probability current, and a controlled classical limit. A Cassi field-configuration ontology supplies one actual field configuration. Its guidance by the wavefunctional current gives one detector record in a topological sector. The Born density is the unique normalized density that is both local in $|\Psi|^2$ and equivariant under this guidance; empirical frequencies additionally require the declared quantum-equilibrium condition.

The construction contains no mass-triggered or observer-triggered collapse term. Closed evolution is unitary. Measurement correlates a system with disjoint, retained apparatus sectors; conditioning on the actual apparatus configuration produces effective collapse. Passive CassiFI reflection, transmission, and absorption become channels of a unitary total scattering map. The reduced open-system description may decohere or absorb amplitude while the enlarged state preserves norm.

The algebra below is Derived conditional on four explicit quantum-sector postulates. The identification of the CassiFI laboratory fields with nature's microscopic configuration remains Hypothesized. The positive-root density lift $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ is a separate coordinate diagnostic and is never identified with the quantum wavefunctional $\Psi[Q,t]$.

The frozen DQ1–DQ9 promotion audit in §8.1 yields `REJECT`: the canonical
real-density state does not supply the missing complex phase fibre, Fisher
ensemble term, unique guidance law, equilibrium preparation, physical-sector
maps, interacting continuum limit, or a Cassi-specific discriminator. The
reverse-Madelung and tensor-composition gates pass under their declared
quantum premises.

The frozen GQ1–GQ7 campaign in §8.3 `ADOPT`s a moment-map/Kähler projection
architecture as a Hypothesized research direction. Fibre causality passes and
finite Kähler compatibility passes conditionally; symmetry reduction,
microscopic projection, cotangent reconstruction, physical-sector geometry,
and Cassi-specific holonomy fail. The physical-identification promotion verdict remains
`REJECT`.

---

## 1. Inputs from the CassiFI field law

### 1.1 Complex Yang/Yin coordinates

The CassiFI complex-field extension uses the weighted coordinates

$$
D=\mathcal E_Y-\varphi\mathcal E_I,
\qquad
C=\frac{\varphi\mathcal E_Y+\mathcal E_I}{1+\varphi^2},
$$

with

$$
w_D=\frac{1}{1+\varphi^2},
\qquad
w_C=1+\varphi^2,
$$

and inverse

$$
\mathcal E_Y=w_DD+\varphi C,
\qquad
\mathcal E_I=C-\varphi w_DD.
$$

The exact pointwise metric identity is

$$
|\mathcal E_Y|^2+|\mathcal E_I|^2
=w_D|D|^2+w_C|C|^2.
$$

The physical-density identification

$$
E_Y=|\mathcal E_Y|^2,
\qquad
E_I=|\mathcal E_I|^2
$$

is the bridge from the complex CassiFI extension to the canonical nonnegative density pair. This identification is Hypothesized. The weighted coordinate identity itself is algebraic.

### 1.2 Finite regulated configuration and metric

On each registered spatial sheet $s$, let $W_s$ be the positive cell metric. Split every complex field into real and imaginary parts and collect the position coordinates as

$$
Q^A=
\left\{
\operatorname{Re}D_{s,j},\operatorname{Im}D_{s,j},
\operatorname{Re}C_{s,j},\operatorname{Im}C_{s,j}
\right\}_{s,j}.
$$

The finite-dimensional configuration metric is

$$
G_{\mathrm{FI}}
=
\bigoplus_s
\operatorname{diag}
\left(
 w_DW_s,w_DW_s,w_CW_s,w_CW_s
\right).
$$

For the conservative CassiFI core,

$$
L_{\mathrm{FI}}(Q,\dot Q)
:=\frac12G_{AB}\dot Q^A\dot Q^B-U_{\mathrm{FI}}(Q),
$$

$$
P_A=G_{AB}\dot Q^B,
\qquad
H_{\mathrm{FI}}(Q,P)
:=\frac12P_AG^{AB}P_B+U_{\mathrm{FI}}(Q).
$$

$U_{\mathrm{FI}}$ contains the registered gradient, base-frequency, nonlinear, composition, cross-scale, and topological retention potentials. The factor of two in the complex Wirtinger force convention is exactly the real-coordinate metric gradient of this $L_{\mathrm{FI}}$.

The CassiFI engineering state records both positions and velocities. In the quantum sector, $(C,D)$ are configuration coordinates and $(V_C,V_D)$ are the classical velocities recovered from the phase guidance law. The non-Hamiltonian EMA is a reduced constitutive variable and is not an independent coordinate in this quantization.

### 1.3 Closed and open terms

Fundamental unitary evolution uses a self-adjoint Hamiltonian for the total field, ports, detector, and environment. CassiFI damping, dissipative conversion, and absorbed boundary work are reduced open-system terms. They enter the quantum theory through additional bath or port coordinates:

$$
\mathcal C_{\mathrm{total}}
:=\mathcal C_{\mathrm{field}}\times
 \mathcal C_{\mathrm{ports}}\times
 \mathcal C_{\mathrm{apparatus}}\times
 \mathcal C_{\mathrm{environment}}.
$$

Tracing over unobserved coordinates may produce a completely positive trace-preserving map or a Lindblad equation. A fundamental state-dependent nonlinear term in $\Psi$ is excluded because it would generally violate mixture equivalence and operational no-signalling. Classical CassiFI nonlinearities remain admissible as the multiplication operator $U_{\mathrm{FI}}(Q)$; the Schrödinger equation remains linear in $\Psi$.

---

## 2. Four quantum-sector postulates

### QF1. Regulated configuration Hilbert space

At a fixed CassiFI regulator, the quantum state is a normalized ray in

$$
\mathcal H_Q=L^2(\mathcal C,d\mu_G),
\qquad
d\mu_G=\sqrt{|G|}\,d^KQ,
$$

where $K$ is the finite real configuration dimension. The continuum theory is defined only after a regulator-removal and renormalization limit exists. No continuum claim follows from the finite construction alone.

### QF2. Canonical quantization

The closed quantum Hamiltonian is the Laplace-Beltrami quantization of the CassiFI Hamiltonian,

$$
\boxed{
\hat H_Q
:=-\frac{\hbar^2}{2}\Delta_G+U_{\mathrm{FI}}(Q)
},
$$

$$
\Delta_G
=|G|^{-1/2}\partial_A
\left(|G|^{1/2}G^{AB}\partial_B\right),
$$

on a declared self-adjoint domain. Its action is

$$
\mathcal S_Q
=\int dt\,d\mu_G
\left[
\frac{i\hbar}{2}
\left(\Psi^*\partial_t\Psi-
\partial_t\Psi^*\Psi\right)
-\frac{\hbar^2}{2}G^{AB}
\partial_A\Psi^*\partial_B\Psi
-U_{\mathrm{FI}}|\Psi|^2
\right].
$$

Variation with respect to $\Psi^*$ gives

$$
\boxed{i\hbar\partial_t\Psi=\hat H_Q\Psi}.
$$

$\hbar$ remains an External physical constant. No $\varphi$ exponent is assigned to it.

### QF3. Actual Cassi field configuration

One configuration $Q(t)\in\mathcal C$ is physically realized. Writing

$$
\Psi(Q,t)=R(Q,t)e^{iS(Q,t)/\hbar},
$$

the actual configuration follows the conserved quantum current:

$$
J^A
=\hbar G^{AB}\operatorname{Im}
\left(\Psi^*\partial_B\Psi\right)
=R^2G^{AB}\partial_BS,
$$

$$
\boxed{
\dot Q^A=\frac{J^A}{|\Psi|^2}
=G^{AB}\partial_BS
}.
$$

Nodes $R=0$ have zero quantum-equilibrium measure. The guidance law is nonlocal on a composite configuration space, as required for Bell-correlated systems. Operational no-signalling is recovered under QF4.

### QF4. Quantum equilibrium

Prepared ensembles use the equivariant density

$$
\boxed{\rho_Q(Q,t)=|\Psi(Q,t)|^2}.
$$

This condition is the irreducible statistical postulate of the bridge. Equivariance preserves it at every later time. Typical repeated preparations then obey Born frequencies. A nonequilibrium ensemble $\rho_Q\ne|\Psi|^2$ would permit observable departures and, for entangled states, may permit operational signalling; no such Cassi branch is adopted.

---

## 3. Schrödinger dynamics, dispersion, and units

### 3.1 Norm conservation

Self-adjointness gives

$$
\frac{d}{dt}\langle\Psi|\Psi\rangle
=\frac{i}{\hbar}
\langle\Psi|(\hat H_Q^\dagger-\hat H_Q)|\Psi\rangle
=0.
$$

The local form is

$$
\partial_t|\Psi|^2+\nabla_AJ^A=0,
$$

where $\nabla_A$ is the metric-compatible configuration divergence.

The quantum ray phase $\Psi\mapsto e^{i\alpha}\Psi$ is distinct from the internal CassiFI symmetry $(C,D)\mapsto e^{i\theta}(C,D)$. The first leaves every quantum ray unchanged. The second acts on the physical field coordinates and has its own conserved generator when $U_{\mathrm{FI}}$ is invariant.

### 3.2 Single-particle and centre-of-mass reduction

Let $\mathbf r$ be a collective coordinate with classical kinetic term

$$
T_{\rm COM}=\frac12M\dot{\mathbf r}^{\,2}.
$$

The induced configuration metric is $G_{ij}=M\delta_{ij}$. If internal modes remain in one adiabatic band, the conditional wavefunction $\psi(\mathbf r,t)$ obeys

$$
\boxed{
i\hbar\partial_t\psi
=\left[-\frac{\hbar^2}{2M}\nabla^2+V(\mathbf r,t)\right]\psi.
}
$$

For a plane wave,

$$
\psi\propto e^{i(\mathbf k\cdot\mathbf r-\omega t)},
\qquad
E=\hbar\omega=\frac{\hbar^2k^2}{2M},
\qquad
\mathbf p=\hbar\mathbf k,
$$

$$
\lambda_{\rm dB}=\frac{h}{Mv},
\qquad
\mathbf j
=\frac{\hbar}{M}\operatorname{Im}(\psi^*\nabla\psi).
$$

In three dimensions, $[\psi]=L^{-3/2}$ under unit normalization. The field wavefunctional has units $[\Psi]=[d\mu_G]^{-1/2}$. Neither object has the units of the Cassi density coordinate $\Psi^{(+)}$.

The sodium-cluster identification uses $M$ as the measured inertial mass. A derivation of that mass from a Cassi field soliton remains open and is not required for the centre-of-mass interference calculation.

### 3.3 Quantum Hamilton-Jacobi form and classical limit

Separating real and imaginary parts gives

$$
\partial_tS
+\frac12G^{AB}\partial_AS\partial_BS
+U_{\mathrm{FI}}
+Q_G=0,
$$

$$
Q_G
=-\frac{\hbar^2}{2R}\Delta_GR.
$$

The quantum potential $Q_G$ is therefore derived from the linear wavefunctional equation and has no free exponent.

When $|Q_G|$ and its gradients are negligible relative to the resolved classical action, the guidance characteristics obey the Hamilton-Jacobi limit of $H_{\rm FI}$. The CassiFI velocity coordinates are then

$$
V^A=\dot Q^A=G^{AB}\partial_BS.
$$

---

## 4. Composite systems and entanglement

### 4.1 Product configuration and tensor factorization

For a regulated split $Q=(Q_A,Q_B)$,

$$
\mathcal C=\mathcal C_A\times\mathcal C_B,
\qquad
\mathcal H_Q
\cong\mathcal H_A\otimes\mathcal H_B.
$$

A product state has

$$
\Psi(Q_A,Q_B)=\psi_A(Q_A)\psi_B(Q_B).
$$

A generic entangled state is nonfactorizable:

$$
\Psi(Q_A,Q_B)
=\sum_r\sqrt{\lambda_r}\,
 u_r(Q_A)v_r(Q_B),
\qquad
\sum_r\lambda_r=1.
$$

The reduced density operator is

$$
\rho_A
=\operatorname{Tr}_B|\Psi\rangle\langle\Psi|.
$$

An ordinary field value at one point of three-space cannot encode an arbitrary function of $N$ spatial arguments. Generic entanglement therefore lives in the wavefunctional over the complete field configuration. The CassiFI multiscale stack provides physical configuration coordinates and coarse-graining maps; it does not replace the configuration-space dependence of $\Psi$.

### 4.2 Particle sectors

For $N$ effective particles,

$$
\mathcal H_N
=L^2(\mathbb R^{3N},d^{3N}x)
$$

before internal and identical-particle restrictions. Bosonic and fermionic sectors use the standard symmetric and antisymmetric subspaces. The Hamiltonian

$$
\hat H_N
=\sum_{j=1}^N
\left[-\frac{\hbar^2}{2m_j}\nabla_j^2
+V_j(\mathbf x_j)\right]
+\sum_{j<k}V_{jk}(\mathbf x_j-\mathbf x_k)
$$

is Hermitian on its declared domain and conserves total norm. A Cassi field theory may recover these sectors as collective excitations of the regulated field; that particle-field identification remains Hypothesized.

### 4.3 No-signalling

For any local trace-preserving completely positive map on $B$,

$$
\mathcal E_B(\rho)
=\sum_k(I_A\otimes K_k)\rho(I_A\otimes K_k^\dagger),
\qquad
\sum_kK_k^\dagger K_k=I_B,
$$

cyclicity of the partial trace gives

$$
\operatorname{Tr}_B[(I_A\otimes\mathcal E_B)(\rho_{AB})]
=\operatorname{Tr}_B\rho_{AB}.
$$

Local outcome-averaged operations cannot change statistics at $A$. The guidance law remains ontically nonlocal. QF4 prevents that nonlocality from becoming a controllable signal.

### 4.4 No-cloning

Suppose a universal unitary copier acted as

$$
U|\psi\rangle|0\rangle=|\psi\rangle|\psi\rangle,
\qquad
U|\phi\rangle|0\rangle=|\phi\rangle|\phi\rangle.
$$

Unitary preservation of inner products would require

$$
\langle\phi|\psi\rangle
=\langle\phi|\psi\rangle^2.
$$

This holds generally only for orthogonal or identical rays. An arbitrary
unknown CassiFI quantum state therefore cannot be copied. A measurement can
write a topologically retained classical record after the alternatives have become
distinguishable; that record is not a second copy of the original
wavefunctional.

### 4.5 Entanglement as joint Qi flow

The quantum continuity equation on a product configuration
$Q=(Q_A,Q_B)$ is

$$
\partial_t\rho_\Psi
+\operatorname{div}_{G_A}J_A
+\operatorname{div}_{G_B}J_B=0,
\qquad
\rho_\Psi:=|\Psi|^2,
$$

with

$$
J_A^a
:=\rho_\Psi G_A^{ab}\partial_bS,
\qquad
J_B^\alpha
:=\rho_\Psi G_B^{\alpha\beta}\partial_\beta S.
$$

The derived quantum Qi-flow object for this split is the conserved
density-current object

$$
\mathfrak F_\Psi
:=(\rho_\Psi,J_A,J_B).
$$

It includes both occupancy and transport. This matters because a stationary
entangled state may have $J_A=J_B=0$ while its joint density remains
nonfactorizable.

For a product state
$\Psi=\psi_A\psi_B=R_AR_Be^{i(S_A+S_B)/\hbar}$,

$$
\rho_\Psi=\rho_A\rho_B,
\qquad
J_A=\rho_BJ_A^{(A)},
\qquad
J_B=\rho_AJ_B^{(B)}.
$$

Equivalently, the normalized guidance velocities obey

$$
v_A(Q_A,Q_B)=v_A(Q_A),
\qquad
v_B(Q_A,Q_B)=v_B(Q_B).
$$

On a connected nonnodal product domain, these global density-current
factorization conditions are equivalent to wavefunctional factorization.
Entanglement there is therefore the failure of the conserved Qi-flow object
$\mathfrak F_\Psi$ to decompose across the declared subsystem split. Across
disconnected nodal domains, density and current can omit relative branch
phases; Schmidt rank or reduced-state purity supplies the exact global
criterion.

Two local cross-flow tensors expose the two ways factorization can fail:

$$
\Xi^{(R)}_{a\beta}
:=\nabla_a\nabla_\beta\ln R,
\qquad
\Xi^{(S)}_{a\beta}
:=\nabla_a\nabla_\beta S.
$$

A nonzero $\Xi^{(R)}$ diagnoses amplitude correlation. A nonzero
$\Xi^{(S)}$ means that one subsystem's guidance velocity changes with the
other subsystem's configuration:

$$
\Xi^{(S)}_{a\beta}
=\nabla_\beta\!\left[(G_A)_{ab}v_A^b\right].
$$

Either condition is sufficient for entanglement on that support. A real
correlated standing state can have $\Xi^{(R)}\neq0$ and zero current. A
phase-coupled state

$$
\Psi(Q_A,Q_B)
=\psi_A(Q_A)\psi_B(Q_B)e^{i\chi Q_AQ_B}
$$

can have a factorized density and
$\Xi^{(S)}=\hbar\chi\neq0$. The full density-current pair is required.

For the actual configuration $Q_B(t)$, subsystem $A$ follows

$$
\dot Q_A^a(t)
=\left.
G_A^{ab}\partial_bS(Q_A,Q_B,t)
\right|_{Q_A=Q_A(t),\,Q_B=Q_B(t)}.
$$

This is the precise Qi-flow form of ontic quantum nonlocality: entanglement
makes the local conditional flow depend on the actual remote configuration.
The reduced-state identity in §4.3 preserves operational no-signalling under
quantum equilibrium.

#### 4.5.1 How CassiFI couplings create entanglement

Write the regulated Hamiltonian as

$$
\hat H
=\hat H_A\otimes I
+I\otimes\hat H_B
+\hat H_{\mathrm{int}}.
$$

The reduced state evolves as

$$
\dot\rho_A
=-\frac{i}{\hbar}[\hat H_A,\rho_A]
-\frac{i}{\hbar}
\operatorname{Tr}_B[\hat H_{\mathrm{int}},\rho_{AB}].
$$

The local commutator changes the local basis while preserving the eigenvalues
of $\rho_A$. The interaction term changes those eigenvalues and therefore can
change the entanglement entropy

$$
\mathcal E_{A:B}
:=-\operatorname{Tr}(\rho_A\ln\rho_A).
$$

The CassiFI reciprocal link is an explicit interaction of this kind. For
$Z\in\{C,D\}$ across adjacent sheets $s$ and $s+1$,

$$
U_{\mathrm{link},Z,s}
:=\frac{w_Zg_{Z,s}}{2}
\left\|Z_{s+1}-P_sZ_s\right\|_{W_{s+1}}^2.
$$

After quantization, its cross term is

$$
\hat H_{\mathrm{cross},Z,s}
=-w_Zg_{Z,s}\,
\operatorname{Re}
\left\langle\hat Z_{s+1},P_s\hat Z_s\right\rangle_{W_{s+1}}.
$$

The link enters the Qi flow immediately. For an initially factorized
nonnodal state, its short-time contribution to the phase is

$$
\delta S_{\mathrm{int}}
=-\delta t\,U_{\mathrm{link},Z,s}
+O(\delta t^2).
$$

Use the declared cell metrics to define the whitened reciprocal map

$$
\widetilde P_s
:=W_{s+1}^{1/2}P_sW_s^{-1/2}.
$$

In the corresponding real coordinate blocks, the mixed Hessian and induced
phase cross-flow are

$$
H_{(s+1)s}^{\mathrm{link}}
:=\frac{\partial^2U_{\mathrm{link},Z,s}}
{\partial\widetilde Q_{s+1}\,\partial\widetilde Q_s}
=-w_Zg_{Z,s}\widetilde P_s,
$$

$$
\delta\Xi_{(s+1)s}^{(S)}
=-\delta t\,H_{(s+1)s}^{\mathrm{link}}
=\delta t\,w_Zg_{Z,s}\widetilde P_s
+O(\delta t^2).
$$

Thus a generic product state first acquires cross-dependent guidance flow.
The continuity equation can then convert that phase correlation into joint
density correlation. On connected nonnodal product support, entanglement
begins once the density or current sector of $\mathfrak F_\Psi$ ceases to
factorize.

If

$$
\widetilde P_s=U\Sigma V^\dagger,
\qquad
\Sigma=\operatorname{diag}(\sigma_1,\ldots,\sigma_r),
$$

then the cross interaction decomposes into
$r=\operatorname{rank}\widetilde P_s=\operatorname{rank}P_s$ directly coupled
mode pairs. Its nonzero metric-aware singular directions identify the direct
inter-sheet entangling channels. Null directions have no direct coupling
through that link.

For the scalar identity-metric audit $P_s=I$ with unit mass, write
$g_{\mathrm{link}}:=w_Zg_{Z,s}$.

$$
H
=\frac12(p_A^2+p_B^2)
+\frac12\omega^2(q_A^2+q_B^2)
+\frac{g_{\mathrm{link}}}{2}(q_B-q_A)^2.
$$

Its normal frequencies are

$$
\omega_+=\omega,
\qquad
\omega_-=\sqrt{\omega^2+2g_{\mathrm{link}}}.
$$

The ground state's reduced symplectic eigenvalue and purity are

$$
\nu_A
=\frac14
\sqrt{(\omega_++\omega_-)
\left(\omega_+^{-1}+\omega_-^{-1}\right)},
\qquad
\mu_A=\frac{1}{2\nu_A}.
$$

At $g_{\mathrm{link}}=0$, $\nu_A=1/2$ and $\mu_A=1$. For
$g_{\mathrm{link}}>0$,
$\nu_A>1/2$ and $\mu_A<1$: the quantized reciprocal Qi link produces
intersheet entanglement even in a stationary zero-current ground state.

#### 4.5.2 What the classical signed link current measures

The corresponding CassiFI phase-charge transfer is

$$
\mathcal K_{Z,s\to s+1}
:=-w_Zg_{Z,s}\,
\operatorname{Im}
\left\langle P_sZ_s,Z_{s+1}-P_sZ_s\right\rangle_{W_{s+1}}
=-w_Zg_{Z,s}\,
\operatorname{Im}
\left\langle P_sZ_s,Z_{s+1}\right\rangle_{W_{s+1}}.
$$

This is the semiclassical exchange quadrature of the same reciprocal link.
Its sign gives transfer direction and its magnitude gives instantaneous
phase-charge transport. Entanglement is measured by Schmidt coefficients,
reduced purity, or $\mathcal E_{A:B}$. Product coherent states can carry a
nonzero $\mathcal K$, while the entangled coupled ground state above has
$\langle\mathcal K\rangle=0$. Current and entanglement are complementary
diagnostics of the same interaction.

System-apparatus measurement applies the same structure at a larger
bipartition. The interaction creates nonfactorizable joint Qi flow between
the system alternatives and apparatus coordinates. Topological apparatus
sectors retain the resulting record branches, and the actual guided
configuration enters one of them.

The resulting identification is

$$
\boxed{
\begin{aligned}
\text{connected nonnodal product support:}\quad
\Psi\ \text{entangled}
&\Longleftrightarrow
\mathfrak F_\Psi\ \text{nonfactorizable},\\
\text{all pure bipartite states:}\quad
\Psi\ \text{entangled}
&\Longleftrightarrow
\operatorname{rank}_{\mathrm{Schmidt}}\Psi>1.
\end{aligned}
}
$$

The Qi-flow equivalence is **Derived conditional** on QF1-QF3, the declared
subsystem factorization, and the regulated Hamiltonian. The scalar classical
diagnostic $q$ measures local Yang/Yin coherence. The object
$\mathfrak F_\Psi$ captures connected-support density-current organization;
Schmidt coefficients and reduced-state invariants supply the exact global
criterion. The physical identification of the CassiFI link coordinates
remains **Hypothesized**.

---

## 5. Measurement and retained records

### 5.1 Premeasurement

Let $\{|s_k\rangle\}$ be the system alternatives resolved by the apparatus. A measurement interaction produces

$$
\left(\sum_kc_k|s_k\rangle\right)
|A_0\rangle|E_0\rangle
\longrightarrow
\sum_kc_k|s_k\rangle|A_k\rangle|E_k\rangle.
$$

The interaction Hamiltonian determines the basis. The scalar Qi diagnostic $q$ and the cascade rung count do not select it.

### 5.2 Topological apparatus sectors

For the apparatus configuration $Q_A$, CassiFI topological retention defines

$$
\mathcal T_{\mathrm{topo}}(Q_A)
:=\left(
\{n_{\mathrm{topo},x}\},\{n_{\mathrm{topo},y}\},\{p_{\mathrm{topo}}\}
\right).
$$

A record value $k$ corresponds to a guarded region

$$
\Omega_k
:=\{Q_A:\mathcal T_{\mathrm{topo}}(Q_A)=\tau_k\},
\qquad
\Omega_j\cap\Omega_k=\varnothing
\quad(j\ne k).
$$

The measurement packets satisfy

$$
\operatorname{supp}A_k\subset\Omega_k.
$$

The bounded topological retention potential and its phase-slip barrier provide metastability and retention. In the semiclassical detector limit, the interaction supplies the energy that moves the apparatus between sectors and the CassiFI work ledger closes. Quantum tunnelling between retained sectors is allowed in principle; a usable record requires

$$
\Gamma_{\rm tunnel}T_{\rm hold}\ll1.
$$

### 5.3 Decoherence and record distinguishability

After tracing the environment, an off-diagonal system element is multiplied by

$$
\gamma_{jk}
=\langle A_kE_k|A_jE_j\rangle.
$$

Define the derived record-distinguishability diagnostic

$$
\boxed{
\mathcal M_{jk}=1-|\gamma_{jk}|^2
},
\qquad
0\le\mathcal M_{jk}\le1.
$$

$\mathcal M_{jk}=0$ means that the apparatus and environment carry no distinguishing record. $\mathcal M_{jk}\simeq1$ means that the records are effectively orthogonal. Organization or randomness does not determine this value by itself. A coherent phase grating may be highly organized with $\mathcal M\simeq0$; random scattering may have $\mathcal M\simeq1$ when it exports which-path information.

### 5.4 One outcome and effective collapse

The total wavefunctional retains all dynamically separated packets. The actual apparatus configuration belongs to one guarded region $\Omega_K$. The conditional system wavefunction is

$$
\psi_{\rm cond}(Q_S,t)
\propto
\Psi(Q_S,Q_A(t),Q_E(t),t).
$$

When the packets have disjoint support, this conditional wavefunction contains only branch $K$ to observational accuracy. The effective update is

$$
\psi\longrightarrow
\frac{P_K\psi}{\|P_K\psi\|}.
$$

No observer term and no fundamental stochastic collapse term is added. The unique record is the topological sector occupied by the actual field configuration. The global wavefunctional remains unitary.

### 5.5 Passive scattering and absorption

For each CassiFI port,

$$
\eta_{\rm ref}+\eta_{\rm trans}+\eta_{\rm abs}=1
$$

within the declared numerical residual. Quantum amplitudes require an enlarged unitary scattering matrix $S_r$ whose channel norms reproduce these fractions:

$$
|r|^2=\eta_{\rm ref},
\qquad
|t|^2=\eta_{\rm trans},
\qquad
\sum_a|a_a|^2=\eta_{\rm abs},
\qquad
S_r^\dagger S_r=I.
$$

Absorption transfers amplitude into detector or environment channels. It does not delete total norm. A reduced no-click state may be non-unitarily conditioned after the absorbed channels are excluded.

---

## 6. Born probabilities and frequencies

### 6.1 Equivariance

The Schrödinger continuity equation and the guidance flow share the same current:

$$
\partial_t|\Psi|^2+\nabla_A(|\Psi|^2\dot Q^A)=0.
$$

Any ensemble initially distributed according to QF4 remains distributed according to QF4.

### 6.2 Uniqueness among local equivariant densities

Suppose a candidate equilibrium density is local in $u=|\Psi|^2$,

$$
\rho_Q=f(u),
$$

and is transported by the same velocity field for every admissible flow. Along a trajectory,

$$
D_tu=-u\,\nabla_A\dot Q^A,
\qquad
D_tf(u)=-f(u)\,\nabla_A\dot Q^A.
$$

The chain rule therefore requires

$$
uf'(u)=f(u).
$$

The nonnegative solutions are $f(u)=Cu$. Normalization gives $C=1$. Thus

$$
\boxed{\rho_Q=|\Psi|^2}
$$

is the unique normalized equilibrium density within the declared local-equivariance class. This theorem fixes the functional form; QF4 supplies the equilibrium condition for the realized ensemble.

### 6.3 Outcome probabilities

For disjoint detector sectors,

$$
\boxed{
P(k)
=\int_{\Omega_k}|\Psi(Q)|^2d\mu_G
=\langle\Psi|P_k|\Psi\rangle
}.
$$

For an ideal state $\sum_kc_k|s_k\rangle$ correlated with disjoint apparatus packets,

$$
P(k)=|c_k|^2.
$$

Repeated independently prepared trials converge to these frequencies by the law of large numbers. Correlated trials require their joint quantum state and do not inherit an independent-trial claim.

For a detector represented by disjoint outgoing absorbing surfaces $\Sigma_k$, the same probability may be written as an integrated outward flux when the detector boundary condition makes that flux nonnegative:

$$
P(k)
=\int_0^\infty dt
\int_{\Sigma_k}J^An_A\,d\Sigma.
$$

If all prepared systems are eventually detected, $\sum_kP(k)=1$.

### 6.4 Coherent-state counting as a special case

A Glauber coherent field with detector amplitude $A_k=g c_k$ has Poisson mean $|A_k|^2$. Normalizing its mean counts reproduces $|c_k|^2$. That calculation remains valid for coherent-state counting. The general Born result above applies to one-particle, Fock, mixed, and entangled states and does not assume Poisson source statistics.

---

## 7. Sodium-nanoparticle interferometer

### 7.1 Standard quantum-sector prediction

For a symmetric Talbot-Lau interferometer,

$$
S(x_3)=\sum_{\ell=-\infty}^{\infty}
S_\ell e^{2\pi i\ell x_3/d},
$$

$$
S_\ell
=B_{-\ell}^{(1)}(0)
 B_{2\ell}^{(2)}\!\left(\ell\frac{L}{L_T}\right)
 B_{\ell}^{(3)}(0),
$$

$$
L_T=\frac{d^2}{\lambda_{\rm dB}}
=\frac{d^2Mv}{h},
\qquad
V=\frac{2|S_1|}{S_0}.
$$

The Talbot coefficients include coherent dipole phase and ionization depletion. The CassiFI quantum bridge uses the same linear centre-of-mass Hamiltonian and therefore predicts

$$
\boxed{
S_\ell^{\rm Cassi}=S_\ell^{\rm QM},
\qquad
V_{\rm Cassi}=V_{\rm QM}
}
$$

for isolated propagation, apart from ordinary environment and apparatus channels already included in the Hamiltonian or reduced open-system model. The canonical bridge contains no additional visibility factor and no fitted quantum coefficient.

### 7.2 Experimental anchors

For the 2026 sodium-cluster result,

$$
d=133\ \mathrm{nm},
\qquad
L=0.983\ \mathrm{m},
\qquad
M\simeq172\ \mathrm{kDa},
\qquad
v\simeq160\ \mathrm{m\,s^{-1}}.
$$

These values give

$$
\lambda_{\rm dB}\simeq14.5\ \mathrm{fm},
\qquad
L_T\simeq1.22\ \mathrm{m},
\qquad
\frac{L}{L_T}\simeq0.806,
$$

and a G1-to-G3 flight time near $12.3$ ms. The measured diagnostic regime around 172 kDa gave $V=0.10\pm0.01$ and $0.08\pm0.01$ in two runs. The reported 0.4-1 MDa fringes do not distinguish the quantum and classical curves in that apparatus geometry.

The experiment's conventional environment factor $0.78$ is applied equally to its quantum and classical models. It is an apparatus nuisance factor, not a Cassi parameter.

### 7.3 Constraint on additional collapse

The published minimal-macrorealist modification multiplies each Fourier order by $R_\ell$, with $R_0=1$. The data give the 5% bound

$$
\tau_e\ge2.84\times10^{15}\ \mathrm{s}
$$

at $\hbar/\sigma_q=10$ nm, corresponding to

$$
\mu=\log_{10}(\tau_e/1\ \mathrm{s})=15.45.
$$

The CassiFI field-configuration bridge selects

$$
R_\ell^{\rm Cassi}=1
$$

for spontaneous collapse during isolated propagation. Any later stochastic or nonlinear Cassi extension must be registered separately and satisfy the published $R_\ell$ likelihood bound. The 133 nm and 8 nm lengths have no preregistered $\varphi$-rung relation and provide no cascade evidence.

### 7.4 Apparatus interpretation

G1 and G3 implement absorptive spatial filtering. G2 implements coherent, position-dependent phase transmission. Its transmitted alternatives retain overlapping path records, so $\mathcal M_{jk}\simeq0$. Final ionization and amplification correlate position with disjoint detector records, giving $\mathcal M_{jk}\simeq1$ and a retained apparatus outcome.

---

## 8. Epistemic accounting and falsifiers

### 8.1 Canonical-to-quantum configuration audit

The frozen protocol
`computations/quantum-configuration-bridge-pre-registration.md` asks whether
QF1–QF4 follow from the canonical real-density state and the declared
Cassi/CassiFI dynamics. The campaign separates three claims:

1. the canonical density state determines the finite complex CassiFI
   configuration;
2. the finite CassiFI field law determines the quantum ensemble,
   wavefunctional, guidance, and equilibrium structure;
3. the regulated construction determines physical sectors, a continuum
   theory, and a Cassi-specific observable.

The deterministic script
`computations/verify_quantum_configuration_bridge.py` evaluates the frozen
algebraic certificates. Source-existence requirements remain documentary
gates.

#### DQ1. Canonical lift

Write the complex amplitude extension locally as
$\mathcal E_Y,\mathcal E_I\in\mathbb C$ to distinguish it from the canonical
densities. Its density projection is

$$
\pi(\mathcal E_Y,\mathcal E_I)
=\left(|\mathcal E_Y|^2,|\mathcal E_I|^2\right).
$$

At $\mathcal E_Y=2+i$ and $\mathcal E_I=3+2i$,

$$
D\pi
=
\begin{pmatrix}
4&2&0&0\\
0&0&6&4
\end{pmatrix},
\qquad
\operatorname{rank}D\pi=2,
\qquad
\operatorname{nullity}D\pi=2.
$$

The generic fibre contains the two independent phase directions
$U(1)\times U(1)$. The complex-linear CassiFI coordinate change

$$
D=\mathcal E_Y-\varphi\mathcal E_I,
\qquad
C=\frac{\varphi\mathcal E_Y+\mathcal E_I}{1+\varphi^2}
$$

is invertible after the complex amplitudes are supplied. It leaves the phase
fibre of $\pi$ unresolved.

The exact positive-root section of the canonical state is

$$
s(E_Y,E_I)
=\left(\sqrt{E_Y},0,\sqrt{E_I},0\right).
$$

At $(E_Y,E_I)=(4,9)$,

$$
Ds=
\begin{pmatrix}
1/4&0\\
0&0\\
0&1/6\\
0&0
\end{pmatrix}.
$$

For the canonical complex-coordinate two-form

$$
\Omega=
\begin{pmatrix}
0&1&0&0\\
-1&0&0&0\\
0&0&0&1\\
0&0&-1&0
\end{pmatrix},
$$

the pullback is

$$
(Ds)^{\mathsf T}\Omega Ds=0.
$$

The section is rank two and isotropic. It supplies neither the two phase
directions nor conjugate momenta. The frozen source set contains no canonical
phase law, gauge quotient, or momentum closure that reconstructs them from
$(E_Y,E_I)$.

**DQ1 verdict: `FAIL`.** QF1 remains an independent regulated-configuration
postulate.

#### DQ2. Configuration-space Fisher bridge

The canonical Qi terms are local functionals of physical-space fields. The
Fisher functional required by an ensemble action is a functional of a
probability density on configuration space,

$$
\mathcal I_F[\varrho]
=
\int_{\mathcal C}d\mu_G\,
\varrho G^{AB}
\partial_A\ln\varrho\,
\partial_B\ln\varrho.
$$

The frozen independence controls give

$$
\begin{array}{c|cc}
\text{control}&E_\nabla&I_F\\
\hline
q=(1,-1),\ p=(1/2,1/2)&2&0\\
q^{(0)}=(0,0),\ q^{(1)}=(1,1),\ p=(0.8,0.2)&0&0.72
\end{array}.
$$

Physical-space gradients and configuration-space ensemble gradients can vary
independently. A bridge between them requires an additional measure,
coarse-graining map, or information principle. The frozen source set contains
no such bridge and no derivation of the coefficient $\hbar^2/8$.

**DQ2 verdict: `FAIL`.** The Fisher term remains an additional quantum-sector
premise.

#### DQ3. Reverse-Madelung linearization

Assume $\varrho=R^2>0$, a phase $S$, and the Fisher coefficient
$\hbar^2/8$. For $\Psi=Re^{iS/\hbar}$,

$$
\partial_t\Psi
=e^{iS/\hbar}
\left(\partial_tR+\frac{i}{\hbar}R\partial_tS\right),
$$

$$
\partial_x^2\Psi
=e^{iS/\hbar}
\left[
\partial_x^2R
+\frac{2i}{\hbar}\partial_xR\,\partial_xS
+\frac{i}{\hbar}R\partial_x^2S
-\frac{R}{\hbar^2}(\partial_xS)^2
\right].
$$

Grouping real and imaginary terms gives the exact identity

$$
i\hbar\partial_t\Psi
+\frac{\hbar^2}{2}\partial_x^2\Psi-U\Psi
=e^{iS/\hbar}
\left[-R\mathcal H+\frac{i\hbar}{2R}\mathcal C\right],
$$

where

$$
\mathcal C
=\partial_t(R^2)+\partial_x(R^2\partial_xS),
$$

$$
\mathcal H
=\partial_tS+\frac12(\partial_xS)^2+U
-\frac{\hbar^2}{2R}\partial_x^2R.
$$

The frozen Gaussian/quadratic certificate has maximum complex residual
$6.206\times10^{-17}$.

**DQ3 verdict: `PASS` conditional** on the ensemble density, phase, and Fisher
term. The identity establishes the linearization algebra under those premises.

#### DQ4. Guidance uniqueness

Equivariance fixes the divergence of the probability current. If
$\nabla\cdot K=0$, then

$$
J'=J+K,
\qquad
v'=\frac{J+K}{|\Psi|^2}
$$

obeys the same continuity equation as $J$ and
$v=J/|\Psi|^2$. On $\mathbb R^2$, choose

$$
\rho=f=e^{-(x^2+y^2)},
\qquad
K=(\partial_yf,-\partial_xf)=(-2yf,2xf).
$$

Then

$$
\nabla\cdot K=0,
\qquad
v_0=0,
\qquad
v_1=K/\rho=(-2y,2x).
$$

The two fields generate different trajectories while preserving the same
stationary density. The certificate gives zero divergence residual and a
minimum sampled velocity difference of $0.721110$. The source contains no
locality, covariance, boundary, or minimal-current theorem that excludes all
such $K$ on the regulated configuration space.

**DQ4 verdict: `FAIL`.** QF3 selects a guidance law by declaration.

#### DQ5. Quantum equilibrium

Let $p$ and $q=|\Psi|^2$ obey the same continuity equation with velocity $v$.
On their common positive support, the ratio $f=p/q$ satisfies

$$
(\partial_t+v\cdot\nabla)f=0.
$$

Equivariance transports every initial ratio. It preserves the special choice
$f=1$ and also preserves nonequilibrium choices. With suitable boundary
conditions, the fine-grained relative entropy

$$
D_{\mathrm{KL}}(p\|q)
=\int p\ln(p/q)
$$

is invariant under the common transport.

The frozen 128-point periodic control starts with
$D_{\mathrm{KL}}=2.276105622459\times10^{-2}$. After a common 37-cell
transport, both the KL change and the transported-ratio change are zero at
the reported precision. The local-equivariance theorem in §6.2 fixes the
functional form within its declared class once the shared flow is assumed.
It does not select the preparation density of the realized ensemble.

**DQ5 verdict: `FAIL`.** QF4 remains the irreducible statistical postulate
stated in §2.

#### DQ6. Composition, Bell correlations, and no-signalling

Assume QF1 on a product configuration space and

$$
L^2(\mathcal C_A\times\mathcal C_B)
\cong
L^2(\mathcal C_A)\otimes L^2(\mathcal C_B).
$$

For

$$
|\Phi^+\rangle
=\frac{|00\rangle+|11\rangle}{\sqrt2},
$$

and the frozen CHSH settings,

$$
A_0=\sigma_z,\quad A_1=\sigma_x,\quad
B_0=\frac{\sigma_z+\sigma_x}{\sqrt2},\quad
B_1=\frac{\sigma_z-\sigma_x}{\sqrt2},
$$

the certificate gives

$$
\langle\Phi^+|\mathcal B|\Phi^+\rangle
=2\sqrt2,
\qquad
\|\mathcal B\|=2\sqrt2.
$$

A local unitary on subsystem $B$ changes the reduced state at $A$ by
$1.110\times10^{-16}$ in maximum element norm.

**DQ6 verdict: `PASS` conditional** on QF1 and tensor-product composition.
The conditional quantum algebra supplies Bell correlations and local
no-signalling.

#### DQ7. Physical sectors and records

| Required artifact | Frozen-source result |
|---|---|
| Derived spin-$1/2$ sector | The Dirac sector in `foundations/unified-lagrangian.md` is an optional standard sector. |
| Derived fermionic composition | No antisymmetric composition rule follows from the canonical density pair or the complex CassiFI coordinates. |
| Dimensionally complete particle correspondence | The optional two-fluid/particle projection retains an unset dimensionful bridge. |
| Derived gauge quotient and observable map | Gauge sectors are appended standard sectors; the canonical state supplies no derived quotient. |
| Apparatus record map from the same microscopic variables | Record sectors are conditional on QF3, a declared subsystem split, and retained apparatus sectors. |

**DQ7 verdict: `FAIL`.** The regulated field coordinates do not yet supply
the required microscopic-sector correspondence.

#### DQ8. Regulator removal

For the periodic second-difference Laplacian and its $m=1$ mode,

$$
\lambda_N
=\frac{4}{a_N^2}\sin^2\left(\frac{a_N}{2}\right),
\qquad
a_N=\frac{2\pi}{N}.
$$

The frozen receipt is

| $N$ | $|\lambda_N-1|$ | successive order |
|---:|---:|---:|
| 16 | $1.278517\times10^{-2}$ | |
| 32 | $3.208636\times10^{-3}$ | $1.994439$ |
| 64 | $8.029325\times10^{-4}$ | $1.998610$ |
| 128 | $2.007815\times10^{-4}$ | $1.999652$ |

This certifies second-order convergence of the free spatial operator. QF1
explicitly conditions the continuum theory on a regulator-removal and
renormalization limit. The source supplies no interacting regulator sequence,
counterterm flow, self-adjoint-domain limit, or convergent physical
observable without retuning.

**DQ8 verdict: `FAIL`.** The free-operator certificate passes; the interacting
continuum gate fails.

#### DQ9. Cassi-specific discrimination

CT-1 sets $R_\ell^{\mathrm{CassiFI}}=1$ and reproduces linear quantum
mechanics under the same calibrated apparatus model. It is a compatibility
constraint. Schrödinger dispersion, Born frequencies, interference,
entanglement, and no-signalling are shared by the reference quantum theory.
The reciprocal strengths $g_{Z,s}$ and scale maps $P_s$ are declared
Hamiltonian inputs, so their ordinary coupled-oscillator consequences do not
select the Cassi physical ontology.

The frozen prediction registry contains no no-fit observable with a Cassi
value, an orthodox-quantum baseline, fixed parameter provenance, a null
model, and a preregistered decision threshold.

**DQ9 verdict: `FAIL`.**

#### Gate ledger and campaign verdict

| Gate | Result | Decisive receipt or boundary |
|---|---|---|
| DQ1 canonical lift | `FAIL` | $\operatorname{rank}Ds=2$, $(Ds)^{\mathsf T}\Omega Ds=0$, $\operatorname{nullity}D\pi=2$; no phase/momentum closure |
| DQ2 Fisher bridge | `FAIL` | $(E_\nabla,I_F)=(2,0)$ and $(0,0.72)$; no $\hbar^2/8$ derivation |
| DQ3 linearization | `PASS` conditional | Reverse-Madelung residual $6.206\times10^{-17}$ |
| DQ4 guidance uniqueness | `FAIL` | Nonzero divergence-free current addition changes trajectories |
| DQ5 equilibrium | `FAIL` | Nonequilibrium ratio and KL divergence survive common transport |
| DQ6 composition | `PASS` conditional | CHSH and operator norm $2\sqrt2$; remote reduced-state change $1.110\times10^{-16}$ |
| DQ7 physical sectors | `FAIL` | Required spin, fermion, gauge, particle, and record maps are undeclared or conditional |
| DQ8 continuum | `FAIL` | Free operator converges at order $>1.99$; interacting renormalized limit absent |
| DQ9 discrimination | `FAIL` | CT-1 is compatibility-only; no registered Cassi-specific no-fit observable |

The protocol requires every gate to pass for promotion. The campaign verdict
is **`REJECT` promotion of the CassiFI physical-field identification to
Derived**. The regulated quantum construction remains **Derived conditional**
on QF1–QF4 and the stated operator assumptions. Its physical identification
remains **Hypothesized**.

The gate can be reopened by source artifacts that supply: a symplectic
canonical lift; a derived ensemble/Fisher action; a guidance-selection
theorem; an equilibrium-preparation law; complete fermion, gauge, particle,
and apparatus maps; an interacting regulator-removal construction; and a
preregistered Cassi-specific discriminator.

### 8.2 Conditional result ledger

| Result | Status | Decisive failure |
|---|---|---|
| Weighted $C,D$ metric and finite Hamiltonian coordinates | **Derived** within the CassiFI field law | Metric, adjoint, or energy ledger fails |
| $\hat H_Q=-\hbar^2\Delta_G/2+U$ and norm conservation | **Derived conditional** on QF1-QF2 and self-adjointness | Non-unitary closed evolution |
| Schrödinger centre-of-mass dispersion | **Derived conditional** on an induced mass metric $M\delta_{ij}$ | Measured $E(p)$ differs after declared interactions are included |
| Connected-support entanglement as nonfactorizable Qi flow | **Derived conditional** on tensor composition, QF1-QF3, and the declared subsystem split | On connected nonnodal product support, Schmidt rank exceeds one while the global density-current object satisfies the product-flow law; or a $g_{\mathrm{link}}>0$ reciprocal oscillator link has unit reduced purity in its ground state |
| One retained outcome | **Derived conditional** on QF3 and disjoint topological apparatus sectors | One actual configuration yields simultaneous incompatible records |
| Born functional form | **Derived conditional** on local equivariance | Another normalized local equivariant density exists |
| Born frequencies | **Derived conditional** on QF4 and the preparation model | Repeated controlled trials reject $|\Psi|^2$ |
| CassiFI as nature's microscopic field configuration | **Hypothesized** | Bell/interference, spectroscopy, or field-configuration tests reject the identification |
| No spontaneous Cassi collapse | **Selected quantum branch** | Reproducible excess visibility loss cannot be assigned to registered environmental channels |
| Finite CassiFI Kähler configuration and $W$-isometric refinement | **Derived conditional** within the declared complex configuration | $W$, $J$, $g$, $\omega$, or complex-linear refinement compatibility fails |
| Moment-map/Kähler projection architecture | **Hypothesized; `ADOPT` research direction** | Phase fibre is causally inert, finite Kähler compatibility fails, or the canonical state is declared complete and invertible |
| Microscopic-to-mesoscopic projection theorem | **Open** | A source-defined phase ensemble or reservoir derives the canonical PDE with parameter provenance |

### 8.3 Quantum-geometric reconstruction campaign

The frozen protocol
`computations/quantum-geometric-bridge-pre-registration.md` tests the
microscopic-to-mesoscopic direction

$$
\text{complex CassiFI geometry}
\xrightarrow{\ \mu\ }
\text{canonical real densities}.
$$

This direction treats $(E_Y,E_I)$ as action-like or moment-map coordinates.
The inverse positive-root section remains an exact density coordinate and an
isotropic real slice. The physical bridge requires a projection theorem from
the richer geometry.

#### Local Bloch and moment-map geometry

For one candidate complex Yang/Yin pair, write

$$
\widehat z
=e^{i\gamma}
\begin{pmatrix}
\cos(\vartheta/2)\\
e^{i\delta}\sin(\vartheta/2)
\end{pmatrix}.
$$

The normalized modulus projection is

$$
p_Y=|z_Y|^2=\cos^2(\vartheta/2),
\qquad
p_I=|z_I|^2=\sin^2(\vartheta/2).
$$

After quotienting a constant common phase, the normalized complex pair is a
point of

$$
\mathbb{CP}^1\simeq S^2.
$$

Its Bloch coordinates are

$$
n_x=2\operatorname{Re}(z_Y^*z_I),
\qquad
n_y=2\operatorname{Im}(z_Y^*z_I),
\qquad
n_z=p_Y-p_I,
$$

with

$$
n_x=\sin\vartheta\cos\delta,
\qquad
n_y=\sin\vartheta\sin\delta,
\qquad
n_z=\cos\vartheta.
$$

The real density pair fixes the radius and $n_z$. The relative phase
$\delta$ labels a circle over every interior normalized density. Pointwise
phase rotations act on $\mathbb C^2$ with moment-map coordinates

$$
\mu(z_Y,z_I)
=\left(|z_Y|^2,|z_I|^2\right)
$$

up to conventional factors. In action-angle notation,

$$
z_a=\sqrt{E_a}\,e^{i\theta_a},
\qquad
\Omega\sim
\sum_{a\in\{Y,I\}}dE_a\wedge d\theta_a.
$$

The canonical state contains the action coordinates. The phase angles occupy
the fibre.

At the Cassi attractor,

$$
E_Y=\varphi E_I,
\qquad
p_Y=\varphi^{-1},
\qquad
p_I=\varphi^{-2},
$$

so

$$
n_z=p_Y-p_I=\varphi^{-3}=0.236067977500.
$$

The attractor selects the Bloch latitude

$$
\vartheta_\varphi
=\arccos(\varphi^{-3})
=76.345415254^\circ
$$

with transverse radius

$$
\sin\vartheta_\varphi=0.971736543513.
$$

The positive-root section selects $\gamma=\delta=0$, one meridian of this
geometry. The density-plane angle $\theta_d$ remains a bounded coordinate on
the positive density cone. It has a different type from the compact
longitude $\delta$.

The C1 certificate reproduces all identities with maximum residual
$2.776\times10^{-17}$.

#### Two phase-bearing levels

The geometric hierarchy contains two distinct many-to-one maps:

```text
projective quantum state [Psi] in P L2(C)
        | Born map
        v
probability density rho_Q on field-configuration space C

actual complex field configuration Q in C
        | modulus / moment / coarse map mu
        v
canonical real-density configuration (E_Y,E_I)
```

The lower phase belongs to the physical CassiFI field variables and controls
spatial currents, modal content, cross-scale exchange, and retained winding.
The upper phase is $\arg\Psi[Q,t]$ on the complete configuration space and
controls quantum probability current and entanglement. A lower complex lift
supplies a candidate $Q$; QF1–QF2 remain the separate upper quantum lift.

The upper fibre has the same phase-loss pattern. The frozen states

$$
\Psi_0=\frac1{\sqrt2}(1,1),
\qquad
\Psi_1=\frac1{\sqrt2}(1,i)
$$

share probabilities $(1/2,1/2)$ and have discrete edge currents $0$ and
$1/2$. The C3 probability residual is zero.

#### GQ1. Fibre causality

For fixed projected densities $A=0.7$ and $B=0.3$, let

$$
\mathcal E_Y=\sqrt A,
\qquad
\mathcal E_I=\sqrt B\,e^{i\delta}.
$$

The declared CassiFI coordinates obey

$$
|D|^2
=A+\varphi^2B
-2\varphi\sqrt{AB}\cos\delta,
$$

$$
|C|^2
=\frac{
\varphi^2A+B
+2\varphi\sqrt{AB}\cos\delta
}{(1+\varphi^2)^2}.
$$

Their weighted total remains fixed,

$$
w_D|D|^2+w_C|C|^2=A+B,
$$

while their individual modal contents vary. Across the frozen phase sweep,

$$
\Delta|D|^2=2.965905292183,
\qquad
\Delta|C|^2=0.226575002840.
$$

For the scalar reciprocal link,

$$
Z_s=1,
\qquad
Z_{s+1}=e^{i\delta},
$$

the source-defined phase-charge current is

$$
\mathcal K(\delta)=-\sin\delta.
$$

It takes the frozen values $(0,-1,0)$ at
$\delta=(0,\pi/2,\pi)$. Equal projected moduli therefore carry different
declared modal contents and link currents.

**GQ1 verdict: `PASS`.** The discarded lower phase fibre is causally active
in the declared CassiFI dynamics. The upper Born fibre is also current-bearing
under C3.

#### GQ2. Symmetry and reduction

A common global rotation

$$
(\mathcal E_Y,\mathcal E_I)
\mapsto
(e^{i\alpha}\mathcal E_Y,e^{i\alpha}\mathcal E_I)
$$

multiplies $D$ and $C$ by the same phase. Closed norm, polynomial, reciprocal
link, and retained phase-difference terms preserve this global $U(1)$ when
all coupled fields transform together. The C4 modal-norm residual at
$\alpha=0.37$ is $2.168\times10^{-18}$.

An independent Yang/Yin phase rotation changes $|D|^2$ and $|C|^2$. The
frozen relative-phase modal change is $1.482952646092$. A local phase
rotation also changes an ordinary gradient or edge energy:

$$
E_\nabla(e^{i\alpha},e^{i\alpha})=0,
\qquad
E_\nabla(1,i)=2.
$$

The declared field theory therefore supports a common global $U(1)$ in its
closed compatible terms. It supplies neither an independent pointwise
$U(1)\times U(1)$ gauge quotient nor a local connection that makes arbitrary
spatial phase rotations gauge-covariant. External ports and fixed references
can reduce the global symmetry further.

**GQ2 verdict: `FAIL`.** The full phase fibre discarded by
$\mu=(|\mathcal E_Y|^2,|\mathcal E_I|^2)$ is not a gauge orbit of the
declared dynamics.

#### GQ3. Microscopic-to-mesoscopic projection

For the scalar source-defined reciprocal force

$$
F_0=z_1-z_0,
\qquad
z_0=1,
\qquad
z_1=e^{i\delta},
$$

with zero initial velocity,

$$
\left.\frac{d^2}{dt^2}|z_0|^2\right|_{t=0}
=2(\cos\delta-1).
$$

The preparations $\delta=0$ and $\delta=\pi$ have identical initial moduli
and projected accelerations $0$ and $-4$. This is a direct closure
obstruction: the instantaneous projected state does not determine its own
projected evolution.

The source hierarchy classifies the canonical advection-diffusion-conversion
PDE as mesoscopic open-system dynamics. The current source set contains no
reservoir state, conditional phase measure, memory kernel, or trace operation
whose projection derives

$$
\partial_tE_Y+\nabla\cdot(E_Y\mathbf u)
=\nu\nabla^2E_Y-\lambda(1-q)\varepsilon,
$$

$$
\partial_tE_I+\nabla\cdot(E_I\mathbf u)
=\nu\nabla^2E_I+\lambda(1-q)\varepsilon
$$

from the complex CassiFI wave law with the same parameter provenance.

The required future object is a map

$$
\mu:\mathcal C_{\mathrm{micro}}\to\mathcal B_{\mathrm{density}}
$$

together with a defined reservoir or conditional ensemble for which

$$
\frac{d}{dt}\mathbb E[\mu(Q_t)]
$$

closes as the canonical PDE.

**GQ3 verdict: `FAIL`.** The mesoscopic classification supports the projection
architecture; the microscopic projection theorem is absent.

#### GQ4. Cotangent phase reconstruction

For a locally irrotational shared flow,

$$
m\mathbf u^\flat=dS_c,
$$

the canonical velocity can supply a common phase potential. The frozen
control

$$
S_c=x^2-\frac32y^2,
\qquad
\mathbf u_c=(2x,-3y)
$$

has zero curl.

For every constant $\delta$,

$$
S_Y=S_c+\delta/2,
\qquad
S_I=S_c-\delta/2
$$

produces the same two gradients while changing the relative phase by
$\delta$. The certificate gives zero gradient residual between
$\delta=0$ and $\delta=1.1$.

The rotational control

$$
\mathbf u_r=(-0.37y,0.37x)
$$

has curl $0.74$ and unit-circle circulation

$$
\oint\mathbf u_r\cdot d\boldsymbol\ell
=2.324778563656.
$$

At $m=\hbar=1$, its distance from the nearest integer multiple of $2\pi$ is
$2.324778563656$. The canonical source supplies neither a vortex-patch
connection nor a circulation-quantization law.

The four-channel construction in `foundations/qi-flow-double-helix.md`
confirms the same missing direction: total density, composition, and one
directional current leave the species-direction association coordinate free.
Its passive positive ring has at most
$0.159$ turns per amplitude e-fold under the positive-rate contract.

**GQ4 verdict: `FAIL`.** A restricted irrotational sector can reconstruct one
common phase potential. The relative phase, vortex data, and global period
quantization remain independent.

#### GQ5. Finite Kähler compatibility

At fixed resolution, let the CassiFI configuration space carry the Hermitian
form

$$
h_W(u,v)=u^\dagger Wv.
$$

Define

$$
g_W(u,v)=\operatorname{Re}h_W(u,v),
\qquad
\omega_W(u,v)=\operatorname{Im}h_W(u,v),
\qquad
Ju=iu.
$$

Then

$$
g_W(Ju,Jv)=g_W(u,v),
\qquad
\omega_W(u,v)=g_W(Ju,v).
$$

For every declared complex-linear refinement satisfying

$$
I^\dagger W'I=W,
$$

one also has

$$
h_{W'}(Iu,Iv)=h_W(u,v),
$$

$$
g_{W'}(Iu,Iv)=g_W(u,v),
\qquad
\omega_{W'}(Iu,Iv)=\omega_W(u,v),
\qquad
IJu=JIu.
$$

The C7 deterministic receipt gives zero metric and compatibility residuals,
refinement and Hermitian residuals $4.441\times10^{-16}$, and zero
complex-linearity residual.

This is the Kähler geometry of the finite complex configuration manifold.
The second-order CassiFI mechanical phase space remains its cotangent bundle,
with $V_D,V_C$ mapped to canonical momenta by the declared kinetic metric.
The regulated quantum wavefunctional is a further construction over this
configuration manifold.

The geometric Madelung map places the upper lift on

$$
T^*\operatorname{Dens}(\mathcal C)
\longrightarrow
\mathbb P L^2(\mathcal C).
$$

Its density metric contains the Fisher-Rao form

$$
g_{\mathrm{FR}}(\delta\varrho,\delta\varrho)
=\int_{\mathcal C}
\frac{(\delta\varrho)^2}{\varrho}\,d\mu_G
=4\int_{\mathcal C}
(\delta\sqrt{\varrho})^2\,d\mu_G.
$$

This supplies a geometric origin for the Fisher functional form under the
density-cotangent premise. The scale $\hbar$ and the physical identification
of this statistical manifold remain external or postulated.

**GQ5 verdict: `PASS` conditional** on the declared finite complex CassiFI
configuration and its metric-compatible refinement contract.

#### GQ6. Physical-sector geometry

The local normalized complex pair supplies $\mathbb{CP}^1$ qubit geometry.
A physical spin-$1/2$ sector additionally requires an $SU(2)$ action whose
quotient covers the observed $SO(3)$ action on spatial frames. The real
density projection retains only $n_z$ and cannot represent this orbit.

For composite rays, product states form the Segre submanifold

$$
\mathbb{CP}^{m-1}\times\mathbb{CP}^{n-1}
\hookrightarrow
\mathbb{CP}^{mn-1}.
$$

The C9 coefficient-matrix receipt gives

$$
\det M_{\mathrm{prod}}=0,
\qquad
|\det M_{\mathrm{Bell}}|=\frac12.
$$

This is the correct conditional geometry of product and entangled two-qubit
states. It assumes the tensor-product quantum composition rule.

Fermionic statistics require a line bundle over unordered multiparticle
configuration space with exchange holonomy $-1$. A local gauge sector
requires a principal-bundle connection and gauge-covariant observables.
The retained edge energy

$$
1-\operatorname{Re}(\widehat\psi_i^*\widehat\psi_j)
$$

has global $U(1)$ invariance and changes under independent local rotations
unless a link variable is supplied. The source also retains the dimensionful
particle/field bridge and the QF3 apparatus-record premise as open or
conditional.

**GQ6 verdict: `FAIL`.** Qubit and Segre geometry are conditionally available.
Physical spin, fermionic exchange, local gauge structure, particle
correspondence, and records do not follow from the same microscopic
geometry.

#### GQ7. Cassi-specific holonomy

The retained phase loop

$$
(0,\pi/2,\pi,-\pi/2,0)
$$

has wrapped phase sum $2\pi$ and winding $n=1$. A common phase shift of $0.37$
leaves both unchanged. The C8 residual is zero.

This is generic $U(1)$ topology. Its formula contains no $\varphi$, and its
winding is a property of the prepared field state. The frozen source set
contains no derived local connection, closed spatial-scale Wilson loop,
parameter-free curvature, orthodox comparison value, or observational
threshold.

**GQ7 verdict: `FAIL`.** Topological retention supplies a valid state-dependent
winding receipt after a complex field exists. It supplies no Cassi-specific
holonomy discriminator.

#### Gate ledger and decisions

| Gate | Verdict | Decisive receipt or boundary |
|---|---|---|
| GQ1 fibre causality | `PASS` | Equal modulus data give different $D/C$ modal contents, link currents, and upper discrete currents |
| GQ2 symmetry reduction | `FAIL` | Common global $U(1)$ survives; relative and local phase actions change declared energies |
| GQ3 microscopic projection | `FAIL` | Equal moduli give projected accelerations $0$ and $-4$; no bath or phase-ensemble closure |
| GQ4 cotangent phase | `FAIL` | Shared irrotational flow recovers one common potential; relative phase and circulation quantization remain free |
| GQ5 Kähler compatibility | `PASS` conditional | $W$, $J$, complex-linear refinement, $g$, and $\omega$ are compatible to $4.441\times10^{-16}$ |
| GQ6 physical sectors | `FAIL` | Conditional qubit/Segre geometry lacks derived spin, fermion, gauge, particle, and record maps |
| GQ7 holonomy | `FAIL` | Integer winding is generic and state-dependent; no fixed Cassi connection or observable |

The frozen architecture rule is satisfied:

1. GQ1 passes;
2. GQ5 passes conditionally;
3. the hierarchy declares the canonical PDE mesoscopic;
4. the canonical source does not declare an invertible microscopic phase
   space.

The campaign therefore **`ADOPT`s the moment-map/Kähler projection
architecture as a Hypothesized research direction**.

The physical-identification rule requires every gate to pass. Its verdict
remains **`REJECT` promotion to Derived**. The adopted direction changes the
required bridge artifact from an inverse density lift to a
microscopic-to-mesoscopic projection theorem.

The projection architecture can advance through source artifacts that supply:

1. an exact symmetry and reduction statement for the surviving phase
   variables;
2. a reservoir or conditional phase ensemble that derives the canonical PDE;
3. common and relative cotangent currents with vortex and period rules;
4. physical $SU(2)$, fermion-bundle, local gauge, particle, and record maps;
5. interacting continuum convergence for the Kähler/Hamiltonian sequence;
6. a preregistered, parameter-free spatial or scale holonomy observable.

---

## 9. Verification contract

`computations/cassifi-quantum-bridge-pre-registration.md`,
`computations/qi-flow-entanglement-pre-registration.md`,
`computations/quantum-configuration-bridge-pre-registration.md`, and
`computations/quantum-geometric-bridge-pre-registration.md` freeze the
deterministic gates. Their companion scripts check:

1. self-adjoint finite evolution and norm conservation;
2. free-particle dispersion and the sodium de Broglie/Talbot anchors;
3. entanglement plus local no-signalling under a trace-preserving map;
4. Born normalization, equivariance, and the unique local exponent;
5. the published macroscopicity arithmetic and $R_0=1$ contract;
6. product-state density-current factorization and its phase- and
   amplitude-correlation failure modes;
7. reciprocal-link ground-state entanglement and direct-channel rank;
8. unitary exchange flow producing a maximally entangled state;
9. canonical-section rank, symplectic pullback, and density-map nullity;
10. physical-gradient/Fisher independence, reverse-Madelung linearization,
    guidance ambiguity, and equilibrium transport;
11. conditional CHSH/no-signalling algebra and free-lattice convergence;
12. the $\varphi$ Bloch latitude and lower/upper phase-fibre causality;
13. global, relative, and local phase actions plus projected nonclosure;
14. cotangent reconstruction controls and finite Kähler refinement;
15. generic winding and conditional Segre geometry.

The scripts are `computations/verify_cassifi_quantum_bridge.py`,
`computations/verify_qi_flow_entanglement.py`,
`computations/verify_quantum_configuration_bridge.py`, and
`computations/verify_quantum_geometric_bridge.py`. The first two verify the
conditional quantum construction. The third records premises outside the
canonical real-density theory. The fourth verifies the geometric projection
receipts and counterexamples.

---

## References

- J. S. Bell, “On the Einstein Podolsky Rosen paradox,” *Physics Physique Fizika* **1**, 195-200 (1964), <https://doi.org/10.1103/PhysicsPhysiqueFizika.1.195>.
- D. Bohm, “A suggested interpretation of the quantum theory in terms of ‘hidden’ variables. I and II,” *Physical Review* **85**, 166-193 (1952), <https://doi.org/10.1103/PhysRev.85.166>, <https://doi.org/10.1103/PhysRev.85.180>.
- D. Dürr, S. Goldstein, and N. Zanghì, “Quantum equilibrium and the origin of absolute uncertainty,” *Journal of Statistical Physics* **67**, 843-907 (1992), <https://doi.org/10.1007/BF01049004>.
- S. Nimmrichter and K. Hornberger, “Macroscopicity of mechanical quantum superposition states,” *Physical Review Letters* **110**, 160403 (2013), <https://doi.org/10.1103/PhysRevLett.110.160403>.
- S. Pedalino et al., “Probing quantum mechanics with nanoparticle matter-wave interferometry,” *Nature* **649**, 866-870 (2026), <https://doi.org/10.1038/s41586-025-09917-9>.
- Published data and analysis code for the sodium-cluster experiment, <https://doi.org/10.5281/zenodo.17502163>.
- B. Khesin, G. Misiołek, and K. Modin, “Geometry of the Madelung transform,” <https://arxiv.org/abs/1807.07172>.
- A. Ashtekar and T. A. Schilling, “Geometrical formulation of quantum mechanics,” <https://arxiv.org/abs/gr-qc/9706069>.

## Internal references

- `foundations/cassi-first-principles.md` §3.1
- `foundations/cassi-theory-reference.md` §5
- `foundations/unified-lagrangian.md` §1.3
- `foundations/physical-becoming-hierarchy.md` §§1, 5–7
- `foundations/qi-flow-double-helix.md` §§1–6
- `open-questions-cassi-answers.md` Q7
- `parameter-inventory.md` §§2.2, 4, 9
- `predictions/falsifiable-predictions.md` §9

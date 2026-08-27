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


---

## 9. Verification contract

`computations/cassifi-quantum-bridge-pre-registration.md`,
`computations/qi-flow-entanglement-pre-registration.md`, and
`computations/quantum-configuration-bridge-pre-registration.md` freeze the
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
11. conditional CHSH/no-signalling algebra and free-lattice convergence.

The scripts are `computations/verify_cassifi_quantum_bridge.py`,
`computations/verify_qi_flow_entanglement.py`, and
`computations/verify_quantum_configuration_bridge.py`. The first two verify
the conditional quantum construction. The third records which additional
premises remain outside the canonical real-density theory.

---

## References

- J. S. Bell, “On the Einstein Podolsky Rosen paradox,” *Physics Physique Fizika* **1**, 195-200 (1964), <https://doi.org/10.1103/PhysicsPhysiqueFizika.1.195>.
- D. Bohm, “A suggested interpretation of the quantum theory in terms of ‘hidden’ variables. I and II,” *Physical Review* **85**, 166-193 (1952), <https://doi.org/10.1103/PhysRev.85.166>, <https://doi.org/10.1103/PhysRev.85.180>.
- D. Dürr, S. Goldstein, and N. Zanghì, “Quantum equilibrium and the origin of absolute uncertainty,” *Journal of Statistical Physics* **67**, 843-907 (1992), <https://doi.org/10.1007/BF01049004>.
- S. Nimmrichter and K. Hornberger, “Macroscopicity of mechanical quantum superposition states,” *Physical Review Letters* **110**, 160403 (2013), <https://doi.org/10.1103/PhysRevLett.110.160403>.
- S. Pedalino et al., “Probing quantum mechanics with nanoparticle matter-wave interferometry,” *Nature* **649**, 866-870 (2026), <https://doi.org/10.1038/s41586-025-09917-9>.
- Published data and analysis code for the sodium-cluster experiment, <https://doi.org/10.5281/zenodo.17502163>.

## Internal references

- `foundations/cassi-first-principles.md` §3.1
- `foundations/cassi-theory-reference.md` §5
- `foundations/unified-lagrangian.md` §1.3
- `open-questions-cassi-answers.md` Q7
- `parameter-inventory.md` §§2.2, 4, 9
- `predictions/falsifiable-predictions.md` §9

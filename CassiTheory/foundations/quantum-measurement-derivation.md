# CassiFI Quantum Dynamics and Measurement

## Status: Derived conditional (regulated quantum mechanics); Hypothesized (CassiFI physical identification)—August 2026

## Abstract

The CassiFI field law supplies a finite, metric-bearing Hamiltonian configuration and a topological apparatus state. Canonical quantization of that regulated configuration gives a linear Schrödinger wavefunctional, the standard free-particle dispersion, configuration-space entanglement, conserved probability current, and a controlled classical limit. A Cassi field-configuration ontology supplies one actual field configuration. Its guidance by the wavefunctional current gives one detector record in a topological sector. The Born density is the unique normalized density that is both local in $|\Psi|^2$ and equivariant under this guidance; empirical frequencies additionally require the declared quantum-equilibrium condition.

The construction contains no mass-triggered or observer-triggered collapse term. Closed evolution is unitary. Measurement correlates a system with disjoint, retained apparatus sectors; conditioning on the actual apparatus configuration produces effective collapse. Passive CassiFI reflection, transmission, and absorption become channels of a unitary total scattering map. The reduced open-system description may decohere or absorb amplitude while the enlarged state preserves norm.

The algebra below is Derived conditional on four explicit quantum-sector postulates. The identification of the CassiFI laboratory fields with nature's microscopic configuration remains Hypothesized. The positive-root density lift $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ is a separate coordinate diagnostic and is never identified with the quantum wavefunctional $\Psi[Q,t]$.

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

G1 and G3 implement absorptive spatial filtering. G2 implements coherent, position-dependent phase transmission. G2 does not establish orthogonal path records, so $\mathcal M\simeq0$ for the transmitted alternatives. Final ionization and amplification correlate position with disjoint detector records, giving $\mathcal M\simeq1$ and a retained apparatus outcome.

---

## 8. Epistemic accounting and falsifiers

| Result | Status | Decisive failure |
|---|---|---|
| Weighted $C,D$ metric and finite Hamiltonian coordinates | **Derived** within the CassiFI field law | Metric, adjoint, or energy ledger fails |
| $\hat H_Q=-\hbar^2\Delta_G/2+U$ and norm conservation | **Derived conditional** on QF1-QF2 and self-adjointness | Non-unitary closed evolution |
| Schrödinger centre-of-mass dispersion | **Derived conditional** on an induced mass metric $M\delta_{ij}$ | Measured $E(p)$ differs after declared interactions are included |
| Configuration-space entanglement and no-signalling | **Derived conditional** on tensor composition and trace-preserving local maps | Local outcome-averaged operation changes a remote reduced state |
| One retained outcome | **Derived conditional** on QF3 and disjoint topological apparatus sectors | One actual configuration yields simultaneous incompatible records |
| Born functional form | **Derived conditional** on local equivariance | Another normalized local equivariant density exists |
| Born frequencies | **Derived conditional** on QF4 and the preparation model | Repeated controlled trials reject $|\Psi|^2$ |
| CassiFI as nature's microscopic field configuration | **Hypothesized** | Bell/interference, spectroscopy, or field-configuration tests reject the identification |
| No spontaneous Cassi collapse | **Selected quantum branch** | Reproducible excess visibility loss cannot be assigned to registered environmental channels |

The real-density organized-versus-random contrast test remains a NULL result for that protocol. It does not test this quantum sector because its initial state had no complex unitary wavefunctional, no configuration-space entanglement, and no topological detector record.

---

## 9. Verification contract

`computations/cassifi-quantum-bridge-pre-registration.md` freezes the deterministic gates. `computations/verify_cassifi_quantum_bridge.py` checks:

1. self-adjoint finite evolution and norm conservation;
2. free-particle dispersion and the sodium de Broglie/Talbot anchors;
3. entanglement plus local no-signalling under a trace-preserving map;
4. Born normalization, equivariance, and the unique local exponent;
5. the published macroscopicity arithmetic and $R_0=1$ contract.

These checks verify the stated algebra and numerical anchors. They do not establish QF1-QF4 as laws of nature.

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
- `predictions/falsifiable-predictions.md` §5

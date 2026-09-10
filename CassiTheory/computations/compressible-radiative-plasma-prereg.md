# Compressible Radiative Plasma Closure: Fixed Conservation and Transport Controls

## Status: Preregistered—September 2026

## Abstract

This schedule verifies the conditional equations in `turbulence/compressible-radiative-plasma-closure.md`. The calculation covers a compressible ideal multilevel gas, normal shocks, population kinetics, LTE line detailed balance, photoionization energy partition, finite stellar energy reservoirs and a positive discrete-ordinates radiation state that retains crossing beams. The schedule uses fixed dimensionless controls and established constants only. It does not identify the canonical Cassi fields with baryonic density, temperature, chemical species, electromagnetic charge or nuclear fuel, and it does not calibrate an astrophysical object.

## 1. Frozen equations

### 1.1 Material conservation and EOS

Use baryonic mass continuity and inviscid material fluxes

$$
\partial_t\rho+\nabla\cdot(\rho u)=0,
$$

$$
\partial_t(\rho u)+\nabla\cdot(\rho u\otimes u+p\mathbf1)=0,
$$

$$
\partial_tE_m+\nabla\cdot[(E_m+p)u]=0,
\qquad
E_m=\frac12\rho|u|^2+u_m.
$$

For the fixed dilute monatomic multilevel gas,

$$
p=k_BT\left(n_e+\sum_i n_i\right),
$$

$$
u_m=\frac32k_BT\left(n_e+\sum_i n_i\right)
+\sum_i n_i\epsilon_i.
$$

The primitive-recovery oracle is

$$
T=\frac{2(u_m-\sum_i n_i\epsilon_i)}
{3k_B(n_e+\sum_i n_i)}.
$$

All numerical EOS controls use $k_B=1$. No physical temperature calibration is inferred.

### 1.2 Normal shocks

For ideal-gas ratio $\gamma=5/3$ and upstream Mach number $M_1>1$, fix

$$
r:=\frac{\rho_2}{\rho_1}
=\frac{(\gamma+1)M_1^2}{(\gamma-1)M_1^2+2},
$$

$$
\Pi:=\frac{p_2}{p_1}
=1+\frac{2\gamma}{\gamma+1}(M_1^2-1),
\qquad
\frac{T_2}{T_1}=\frac\Pi r.
$$

In the shock frame, require equal mass, momentum and energy fluxes,

$$
\rho_1w_1=\rho_2w_2,
$$

$$
\rho_1w_1^2+p_1=\rho_2w_2^2+p_2,
$$

$$
\rho_1w_1\left(h_1+\frac{w_1^2}{2}\right)
=\rho_2w_2\left(h_2+\frac{w_2^2}{2}\right),
$$

with $h=\gamma p/[(\gamma-1)\rho]$. Entropy is proportional to

$$
\Delta s/c_v=\log(\Pi/r^\gamma).
$$

### 1.3 Population and line identities

Use level populations governed by a finite gain-minus-loss generator $Q$,

$$
\dot n=Qn,
\qquad
Q_{ij}=R_{ji}\geq0\quad(i\ne j),
\qquad
Q_{jj}=-\sum_{i\ne j}Q_{ij}.
$$

The fixed equilibrium distribution for energies $E_i$, weights $g_i$ and temperature $T$ is

$$
\pi_i=\frac{g_ie^{-E_i/T}}{\sum_jg_je^{-E_j/T}}.
$$

Pairwise rates satisfy $\pi_iR_{ij}=\pi_jR_{ji}$.

For a two-level line,

$$
j_\nu=\frac{h\nu}{4\pi}n_uA_{ul}\phi_\nu,
$$

$$
\alpha_\nu=\frac{h\nu}{4\pi}
(n_lB_{lu}-n_uB_{ul})\phi_\nu,
$$

$$
g_lB_{lu}=g_uB_{ul},
\qquad
A_{ul}=\frac{2h\nu^3}{c_\gamma^2}B_{ul}.
$$

At LTE, $n_u/n_l=(g_u/g_l)e^{-h\nu/(k_BT)}$, so $j_\nu/\alpha_\nu=B_\nu(T)$.

For photoionization threshold $\chi=h\nu_0$,

$$
\Gamma^{\rm ph}=4\pi\int_{\nu_0}^\infty
\frac{\sigma_\nu J_\nu}{h\nu}\,d\nu,
$$

and the absorbed power must equal

$$
4\pi n\int\sigma_\nu J_\nu\,d\nu
=n\chi\Gamma^{\rm ph}
+4\pi n\int\frac{\sigma_\nu J_\nu}{h\nu}
(h\nu-\chi)\,d\nu.
$$

### 1.4 Stellar energy reservoirs

For an ideal monatomic hydrostatic star with
$\Omega=-\alpha_GGM^2/R$, freeze the virial identities

$$
2U+\Omega=0,
\qquad
E_*=U+\Omega=\Omega/2.
$$

Contraction from $R_i$ to $R_f<R_i$ releases

$$
E_{\rm KH}=\frac{\alpha_GGM^2}{2}
\left(\frac1{R_f}-\frac1{R_i}\right).
$$

Accretion releases $GM\dot M/R$ per unit time, partitioned by a declared efficiency $\eta_{\rm acc}\in[0,1]$. A nuclear reaction with state production rates $\omega_i^{\rm nuc}$ releases

$$
Q_{\rm nuc}=-c_\gamma^2\sum_i m_i\omega_i^{\rm nuc}
$$

while preserving baryon number and charge. Numerical controls use dimensionless masses and rates rather than fitting a physical reaction.

The radiative diffusion identity is

$$
F=-\frac{c_\gamma}{3\kappa_R\rho}\nabla(a_RT^4),
\qquad
L=4\pi r^2F_r,
$$

which implies

$$
\frac{dT}{dr}
=-\frac{3\kappa_R\rho L}
{16\pi a_Rc_\gamma r^2T^3}.
$$

### 1.5 Discrete ordinates

Use six directions

$$
\{+e_x,-e_x,+e_y,-e_y,+e_z,-e_z\}
$$

with $w_m=4\pi/6$. They must satisfy

$$
\sum_mw_m=4\pi,
\qquad
\sum_mw_mn_m=0,
\qquad
\sum_mw_mn_m\otimes n_m=\frac{4\pi}{3}\mathbf1.
$$

For nonnegative intensities,

$$
E=\frac1{c_\gamma}\sum_mw_mI_m,
\quad
F=\sum_mw_mn_mI_m,
\quad
P=\frac1{c_\gamma}\sum_mw_mn_m\otimes n_mI_m.
$$

Isotropic scattering uses $p_{mm'}=1/(4\pi)$ and the exact homogeneous update

$$
I_m(t+\Delta t)=\bar I+[I_m(t)-\bar I]e^{-c_\gamma\alpha_s\Delta t},
\qquad
\bar I=\frac1{4\pi}\sum_mw_mI_m.
$$

Vacuum axis streaming at unit cell Courant number shifts the $+e_x$ intensity one cell in $+x$ and the $+e_y$ intensity one cell in $+y$ per step.

## 2. Frozen analytical checks

All symbolic residuals must simplify to zero.

1. Subtracting the kinetic-energy balance from the total-energy balance leaves the internal pressure-work term $-p\nabla\cdot u$.
2. Substitution of the normal-shock ratios into the three flux jumps gives zero.
3. The line source function under Boltzmann populations and Einstein identities equals the Planck function.
4. The photoionization threshold-storage and photoelectron-heat terms sum to total absorbed photon power.
5. The virial identities give $E_*=\Omega/2$ and the displayed contraction release.
6. Combining the diffusion flux with $L=4\pi r^2F_r$ gives the displayed stellar temperature gradient.
7. The six-direction quadrature gives the zeroth, first and second angular moments above.
8. Two equal counterpropagating beams have $(E,F)=(E_0,0)$ and $P=E_0e_x\otimes e_x$, while an isotropic state with the same $(E,F)$ has $P=E_0\mathbf1/3$.

## 3. Frozen numerical controls

### 3.1 EOS recovery

Use the eight fixed population vectors generated by the Cartesian product

$$
n_e\in\{0.2,2.0\},
\quad
(n_0,n_1,n_2)\in\{(1,0.1,0.01),(0.3,0.8,0.4)\},
\quad
T\in\{0.4,3.0\},
$$

with level energies $(0,1.5,4)$ and $k_B=1$. Reconstruct $u_m$, pressure and total energy at velocity $(0.3,-0.2,0.1)$, then recover $T$. Require relative error at most $2\times10^{-14}$, positive pressure and positive thermal energy in every case. Feed one state with $u_m\leq\sum n_i\epsilon_i$ and require rejection.

### 3.2 Shock controls

Use $\rho_1=p_1=1$, $\gamma=5/3$ and

$$
M_1\in\{1.2,2,5,10\}.
$$

Require normalized mass, momentum and energy jump residuals below $2\times10^{-13}$, $1<\rho_2/\rho_1<4$, $p_2>p_1$, $T_2>T_1$ and positive entropy change. A control that omits enthalpy from the energy flux must have residual greater than $10^{-2}$ at $M_1=5$.

### 3.3 Population kinetics

Use energies $(0,1,2.5)$, weights $(2,4,6)$ and $T=1.3$. Fix downward rates

$$
R_{10}=3,
\qquad
R_{20}=1.7,
\qquad
R_{21}=0.8,
$$

and determine the reverse rates by detailed balance. Require generator column sums below $10^{-14}$, off-diagonal nonnegativity, $\|Q\pi\|_\infty<10^{-13}$ and conservation of total population below $10^{-13}$ after matrix-exponential steps at

$$
t\in\{10^{-6},0.1,1,20\}
$$

from initial population $(0.02,0.08,0.90)$. Every evolved population must remain nonnegative within $10^{-14}$. A generator with one missing diagonal loss must be rejected.

### 3.4 Line and photoionization controls

Use dimensionless $h=c_\gamma=k_B=1$, $g_l=2$, $g_u=6$, $B_{ul}=0.7$, $\phi_\nu=0.9$ and

$$
x:=\frac{h\nu}{k_BT}\in\{0.1,1,5,15\}.
$$

Set $\nu=2$, $T=\nu/x$, determine $A_{ul}$, $B_{lu}$ and LTE populations, and require $j/\alpha=B_\nu$ to relative error $2\times10^{-13}$. Require exact cancellation of material level-energy and radiation-energy increments for five fixed non-LTE radiation intensities.

For photoionization, use $h=1$, $\chi=2$, frequencies $(2,3,5,9)$, quadrature widths $(0.1,0.4,0.7,1.1)$, cross-sections $(0.4,0.3,0.1,0.02)$ and mean intensities $(0.2,1.0,0.8,0.3)$. Require the discrete form of the energy partition to relative error $2\times10^{-14}$ and nonnegative threshold storage and electron heat.

At fixed upper-level radiative sum $A=4$ and collisional de-excitation sum $C=0.25$, require $n_{e,{\rm crit}}=16$ and equality of radiative and collisional depopulation rates there.

### 3.5 Stellar ledgers

Use dimensionless $G=M=c_\gamma=1$, $\alpha_G=3/5$, $R_i=2$, $R_f=1$ and $L=0.03$. Require the virial, contraction-energy and Kelvin–Helmholtz identities to relative error $2\times10^{-14}$.

For accretion use $\dot M=0.04$, $R=0.8$ and efficiencies
$\eta_{\rm acc}\in\{0,0.2,0.7,1\}$. Partition the released power into radiation $\eta_{\rm acc}GM\dot M/R$ and retained power $(1-\eta_{\rm acc})GM\dot M/R$; require exact reconstruction within $2\times10^{-14}$.

For a fixed reaction $4X\to Y$ use baryon numbers $(1,4)$, charges $(1,4)$, masses $(1.01,4.0)$ and event rates $(0,10^{-6},0.2)$. Require baryon and charge residuals below $10^{-14}$ and nonnegative mass-defect power equal to $0.04\mathcal R$ in the selected units: zero at $\mathcal R=0$ and strictly positive at both positive rates.

For the diffusion gradient use $a_R=0.8$, $c_\gamma=3$, $\kappa_R=0.4$, $\rho=1.2$, $r=2.3$, $T=1.7$ and $L=0.6$. Independently compute the flux from the displayed temperature gradient and require $4\pi r^2F_r=L$ to relative error $2\times10^{-14}$.

Finally use gross power contributions $(0.3,0.2,0.4,0.1)$ from thermal release, gravitational release, nuclear mass defect and matter inflow. Emit $0.73$ as photons, retain $0.19$ as material heat and lose $0.08$ through neutrinos, with no mechanical outflow. The retained heat reduces the net stored-energy drawdown from $-0.50$ to $-0.31$. Require exact total-energy closure and exact reconstruction of the unit gross budget when retained heat is counted as a destination. Increasing emitted energy to $1.01$ with unchanged sources and net stored-energy rate must be rejected.

### 3.6 Angular moments, scattering and crossing beams

Require the six-direction quadrature identities to absolute error $2\times10^{-14}$ and the isotropic discrete phase matrix $p_{mm'}=1/(4\pi)$ to be finite, nonnegative and column-normalized under the quadrature weights. Evaluate 257 deterministic nonnegative intensity vectors

$$
I_m(k)=0.02+(1+0.1m)\left[1+\sin^2((k+1)(m+1))\right],
\quad k=0,\ldots,256.
$$

For each, require $E>0$, $|F|\leq c_\gamma E+2\times10^{-13}$, symmetric positive-semidefinite $P$ to eigenvalue tolerance $2\times10^{-13}$ and $|\operatorname{tr}P-E|<2\times10^{-13}$.

For equal $\pm e_x$ beams, require the discrete pressure to equal $Ee_x\otimes e_x$. Require the M1 zero-flux pressure $E\mathbf1/3$ to differ from it by Frobenius norm greater than $0.5E$; this is an expected obstruction check.

Apply the exact isotropic-scattering update to 32 fixed intensity vectors at optical times

$$
c_\gamma\alpha_s\Delta t\in\{0,10^{-6},0.1,1,20\}.
$$

Require nonnegative intensity, angularly integrated energy conservation below $2\times10^{-13}$ and flux damping by the same exponential below $2\times10^{-13}$.

On a $32\times32$ periodic grid, place one compact nonnegative pulse in the $+e_x$ ordinate and one different pulse in the $+e_y$ ordinate. Advance nine unit-Courant steps by exact axis shifts. Require each directional field to equal its independently rolled initial state, total angular energy to remain constant below $2\times10^{-13}$ and both beams to continue after occupying common cells. A moment-only M1 replacement is not run as an alternative solver; the analytical non-identifiability check is decisive.

Aggregate the angular rejection controls into one check. Alter one quadrature weight by $1\%$ without compensating the others; pass a negative weight, a nonunit direction or a nonfinite intensity directly to moment reconstruction; pass a nonfinite scattering weight to the isotropic update; and pass negative or nonnormalized entries to phase-matrix validation. Every case must raise `ValueError`.

## 4. Tolerances, decision and stopping rule

Use float64, NumPy, SciPy and SymPy. Relative error means
$|a-b|/\max(1,|b|)$ unless a check explicitly normalizes by another scale. Symbolic checks require exact simplification to zero. No tolerance may be relaxed after execution.

The verifier refuses an existing output, manifest, staging path or source-snapshot directory. It reads each source once and writes those exact bytes to a staged snapshot tree. The complete tree and manifest are published by separate atomic renames; a successful return exposes both, while any publication failure removes every staging path and any snapshot tree published by that attempt.

After the external numerical dependencies load, the kernel and fixed scientific schedule are imported directly from their manifest-recorded snapshot files under unique module names. The receipt records each module's snapshot path, executed `__file__`, byte count, pre-import SHA-256, post-import SHA-256 and binding result. A module path, size or hash mismatch prevents scientific execution and gives receipt status `FAIL` with scientific classification `INCONCLUSIVE`.

Every current source and snapshot is compared with the manifest immediately after publication, after dependency imports and before scientific controls, and after the controls. A pre-control mismatch prevents scientific execution. A source-integrity or fixed-count mismatch gives receipt status `FAIL` with scientific classification `INCONCLUSIVE`. The outer runner requires exactly 70 named checks and separately requires the frozen verifier's declaration to equal 70, so the scientific schedule cannot lower its own acceptance count. The result is `PASS` only when that count guard, every source-integrity comparison and both execution-module bindings succeed. Its scientific classification is `SUPPORTS-conditional compressible radiative-plasma closure`. A failed identity, conservation check, positivity check or rejection control gives `FAIL` and `CONTRADICTS`. A missing numerical dependency or source-read failure produces a source-bound `INCONCLUSIVE` receipt and stops interpretation.

A passing result supports the displayed conditional equations and reference kernels at the fixed controls. It does not establish a Cassi material map, physical element abundances, atomic or nuclear data accuracy, a production shock solver, general angular convergence, stellar evolution or a live CassiCosmos implementation.

Run once from the CassiTheory root:

```text
python computations/verify_compressible_radiative_plasma.py \
  --output runs/compressible_radiative_plasma_frozen_execution_final/verification.json
```

## References

- `turbulence/compressible-radiative-plasma-closure.md`—complete conditional derivation and epistemic boundary
- `turbulence/cassi-radiative-material-closure.md`—parent LTE, M1 and covariant exchange closure
- D. Mihalas and B. Weibel-Mihalas, *Foundations of Radiation Hydrodynamics*—radiation-hydrodynamic conservation laws
- G. B. Rybicki and A. P. Lightman, *Radiative Processes in Astrophysics*—line and continuum rates
- R. Kippenhahn, A. Weigert and A. Weiss, *Stellar Structure and Evolution*—stellar energy and transport equations
- B. G. Carlson, [Discrete-ordinates quadrature over the unit sphere](https://www.osti.gov/biblio/4083770)—angular quadrature conditions

# Matter Completion Boundary Preregistration

## Status: Preregistered—September 2026

## 1. Question

What is the strongest common mathematical boundary for the nine sectors needed
to connect the positive two-domain coherence interface to a finite-energy,
fixed-charge particle calculation?

The nine sectors are:

1. exterior-domain identity and dynamics;
2. microscopic interface action and transfer maps;
3. transport-branch selection;
4. carrier normalization between coherence and power;
5. reservoir dynamics that can maintain cross coherence;
6. complete field-plus-reservoir stress;
7. stress-sourced geometry backreaction;
8. the map into the local $SU(2)_Q$ fixed-charge particle branch;
9. the qualification boundary for a finite-energy stationary state and its
   physical fluctuation spectrum.

The receipt tests conditional algebra, conservation, covariance, normalization,
and reduced stability criteria. The physical exterior, microscopic
coefficients, multimode carrier, bath, gravity sector, Q2-qualified stationary
particle, and full constrained spectrum remain open wherever the source
documents leave them open.

## 2. Frozen source boundary

The authorities are:

- `foundations/yin-yang-qi-dynamical-geometry.md` DG13–DG16 and
  DG39–DG49—the relative connection, positive two-domain source, transfer
  families, mixed-stress boundary, and total-stress requirement;
- `foundations/geometric-manifold-completion.md` GM33–GM37 and GM44–GM51—the
  positive coherence fibre, Gram moment map, conditional conservative action,
  and open conversion flow;
- `foundations/interscale-stress-attenuation-boundary.md` §§4–5—the unitary
  golden splitter, closed coherent control, routed-return power ledger,
  amplitude exponent, and stress-map requirements;
- `foundations/physical-becoming-hierarchy.md` OS1–OS6—the conditional
  Markovian reservoir boundary, fluctuation-dissipation normalization, and
  relaxation poles;
- `foundations/unified-lagrangian.md` §3—the optional Einstein–Hilbert term,
  Hilbert stress, and unresolved variable-coupling boundary;
- `foundations/particle-stationary-action-closure.md` PA1–PA38—the local
  $SU(2)_Q$ action, independent global $U(1)_C$ carrier, fixed-charge
  stationary functional, boundary conditions, and variational class;
- `foundations/core-trapped-charge-support.md` CC29–CC48—the reduced
  finite-separation theorem, line-density curvature, and spectrum boundary;
- `computations/particle-stationary-bvp-report.md`—the frozen twelve-arm
  `INCONCLUSIVE—NUMERICAL QUALITY` verdict and absence of a Q2-qualified
  stationary background;
- `computations/cross_scale_coherence_interface_prereg.md` and its EC1–EC7
  receipt—the already verified positive-interface and exchange algebra.

This checker will not rerun EC1–EC7 or the stationary particle campaign. It
uses new deterministic witnesses only for the nine statements below.

## 3. Conditional derivation boundary

### 3.1 Exterior as the complementary dilation output

For the routed single-mode branch, freeze

$$
T:=T_\varphi=\varphi^{-1},
\qquad
R:=R_\varphi=\varphi^{-2}=1-T.
\tag{MB1}
$$

The reduced amplitude-damping channel has Kraus operators

$$
E_0=
\begin{pmatrix}
1&0\\
0&\sqrt T
\end{pmatrix},
\qquad
E_1=
\begin{pmatrix}
0&\sqrt R\\
0&0
\end{pmatrix}.
\tag{MB2}
$$

For $0<T<1$, its Kraus rank is two. A two-dimensional return mode supplies a
minimal Stinespring environment. Rotating $(E_0,E_1)$ by any $2\times2$
unitary changes the environment basis and leaves the reduced channel
unchanged. The complementary output space is therefore fixed only up to an
environment unitary. Its carrier, topology, preparation, and boundary dynamics
require physical input beyond the reduced channel.

### 3.2 Lowest-order reciprocal interface

Assume locality, bilinearity in interior and exterior carrier fields,
Hermiticity, conservation of their enlarged number, and independent-frame
covariance. The lowest-order interface Hamiltonian density then has the form

$$
\boxed{
\mathcal H_{\rm int}
=\Psi_{\rm in}^\dagger V\Psi_{\rm out}
+\Psi_{\rm out}^\dagger V^\dagger\Psi_{\rm in},
\qquad
V\mapsto U_{\rm in}VU_{\rm out}^\dagger.}
\tag{MB3}
$$

The complete propagator is

$$
U_{\rm io}(t_1,t_0)
=\mathcal T\exp\!\left[-\frac{i}{\hbar}
\int_{t_0}^{t_1}H_{\rm io}(t)\,dt\right].
\tag{MB4}
$$

A cross-domain block carries one index in each frame, so its reduced transfer
has the two-sided form $K_{a+1}=L_aK_aR_a^\dagger$. A discrete unitary does not
select a unique continuous generator: eigenphase logarithms differ by integer
multiples of $2\pi$. The form and covariance of the interface follow from the
assumptions; $V$, $L_a$, and $R_a$ remain microscopic inputs.

### 3.3 Closed fundamental transport and one-sided routed readout

The complete forward-plus-return splitter is unitary. For a selected single
forward carrier whose return output does not coherently re-enter later forward
inputs, the reduced cross-coherence map is

$$
\boxed{
K_{a+1}=t_\varphi U_aK_aR_a^\dagger,
\qquad
|t_\varphi|^2=T_\varphi,
\qquad
U_a^\dagger U_a=R_a^\dagger R_a=I.}
\tag{MB5}
$$

After $N$ interfaces,

$$
\frac{\|K_N\|_F}{\|K_0\|_F}=\varphi^{-N/2},
\qquad
\frac{P_N^{\rm fwd}}{P_0^{\rm fwd}}=\varphi^{-N}.
\tag{MB6}
$$

Attenuating both indices by $t_\varphi$ describes two independently routed
legs and gives $\|K_N\|_F/\|K_0\|_F=\varphi^{-N}$. The closed coherent control
gives $\cos^2(N\theta_\varphi)$ forward power, where
$t_\varphi=\cos\theta_\varphi$. The physical routing and the identification of
the golden density fractions with port powers remain constitutive selections.

### 3.4 Carrier normalization

Physical power through a hypersurface $\Sigma$ is

$$
\boxed{
P[\Sigma]
=\int_\Sigma T_{\mu\nu}u^\mu n^\nu\,d\Sigma.}
\tag{MB7}
$$

For one canonically flux-normalized mode of frequency $\omega$,

$$
P=\hbar\omega\dot N,
\qquad
\frac{P_{\rm out}}{P_{\rm in}}=|t|^2.
\tag{MB8}
$$

This gives the amplitude-to-power square in (MB6). The Frobenius norm of
$K$ alone has no universal power normalization. A multimode map additionally
requires a positive mode-energy or flux operator, group velocities,
impedances, and the embedding of $K$ in the physical carrier state.

### 3.5 Repeated-interaction reservoir

Tracing a fresh return mode after every splitter application gives the channel
(MB2). For step duration $\Delta t$,

$$
\boxed{
\gamma=-\frac{\ln T}{\Delta t},
\qquad
N(t)=N(0)e^{-\gamma t},
\qquad
C(t)=C(0)e^{-\gamma t/2}}
\tag{MB9}
$$

for the undriven resonant mode. A linear maintained cross block obeys

$$
\dot C=-\left(\frac\gamma2+i\Omega\right)C+F,
\qquad
\boxed{C_*=\frac{F}{\gamma/2+i\Omega}.}
\tag{MB10}
$$

The homogeneous eigenvalue has real part $-\gamma/2<0$. Nonzero stationary
coherence requires coherent or occupied input, boundary forcing, or another
source. The bath spectral density, temperature, correlation time, drive $F$,
and physical reservoir identity remain unselected.

### 3.6 Closed stress and reduced exchange

For a local closed dilation action,

$$
S_{\rm closed}
=S_P+S_{\rm out}+S_{\rm int}+S_{\rm env},
\qquad
\boxed{
T^{\rm closed}_{\mu\nu}
=-\frac{2}{\sqrt{-g}}
\frac{\delta S_{\rm closed}}{\delta g^{\mu\nu}}.}
\tag{MB11}
$$

Diffeomorphism invariance gives the on-shell Ward identity

$$
\boxed{\nabla^\mu T^{\rm closed}_{\mu\nu}=0.}
\tag{MB12}
$$

A reduced interior sector may obey

$$
\nabla^\mu T^{\rm in}_{\mu\nu}=-J^{\rm io}_\nu,
\qquad
\nabla^\mu
\left(T^{\rm out}_{\mu\nu}+T^{\rm int}_{\mu\nu}
+T^{\rm env}_{\mu\nu}\right)=+J^{\rm io}_\nu.
\tag{MB13}
$$

The Markovian reduced flow does not determine the local terms on the right of
(MB11). Mixed $T_{i\mathfrak s}$ carries scale-window force. A number current
requires a constitutive carrier map before it can be used as that stress.

### 3.7 Minimal covariant backreaction

Selecting a constant-$G$ Einstein–Hilbert sector gives

$$
\boxed{
G_{\mu\nu}+\Lambda g_{\mu\nu}
=8\pi G\,T^{\rm closed}_{\mu\nu}.}
\tag{MB14}
$$

The Bianchi identity is compatible with (MB14) because (MB12) uses the total
closed stress. An exchanging reduced interior stress cannot source (MB14) by
itself. Replacing $G$ by $G_{\rm eff}(q)$ introduces
$(\nabla^\mu G_{\rm eff})T_{\mu\nu}$ and requires additional covariant field
terms. No state-dependent gravity law is selected here.

### 3.8 Cartan map into the fixed-charge particle branch

For $\Psi=(\psi_Y,\psi_I)^T$, define

$$
\boxed{
\Gamma_\Psi=\Psi\Psi^\dagger
=\begin{pmatrix}
|\psi_Y|^2&\psi_Y\psi_I^*\\
\psi_I\psi_Y^*&|\psi_I|^2
\end{pmatrix}\succeq0.}
\tag{MB15}
$$

Thus $E_Y=|\psi_Y|^2$, $E_I=|\psi_I|^2$,
$c=\psi_I\psi_Y^*$, and $\det\Gamma_\Psi=0$. Gram sums or coarse-grained
ensembles produce full-rank fibres as in GM35–GM37.

The relative $U(1)_Q$ is the Cartan subgroup generated by
$T^3=\sigma_3/2$. With

$$
D_A=\partial_A-i g_Q\mathcal A_A,
\qquad
U=e^{-i\alpha T^3},
\tag{MB16}
$$

covariance requires

$$
\boxed{
\mathcal A_A^3\mapsto
\mathcal A_A^3-\frac1{g_Q}\partial_A\alpha.}
\tag{MB17}
$$

This is the Cartan restriction of PA7. It also makes DG15 covariant. The plus
sign currently displayed in DG13 is inconsistent with these conventions and
will be corrected if MCC8 passes. Generic $SU(2)_Q$ transformations rotate the
Yang/Yin composition axis. The particle carrier charge

$$
Q_C=\int|\chi_C|^2\,d^3x\,d\mathfrak s
\tag{MB18}
$$

belongs to an independent global $U(1)_C$ and remains distinct from the Cartan
charge.

### 3.9 Stationary and spectral qualification boundary

A fixed-charge stationary candidate is a critical point of

$$
\boxed{
\mathcal F_{\omega_C}
=\mathcal E_{\rm stat}-\hbar\omega_CQ_C}
\tag{MB19}
$$

with PA27–PA28 boundary data, the Gauss constraint, vanishing excluded fluxes,
and a converged outer-domain limit. On the fixed-charge tangent space and after
gauge fixing, the physical Hessian is

$$
\boxed{
\mathcal H_Q
=P_QP_{\rm gf}\,
\delta^2\mathcal F_{\omega_C}\,
P_{\rm gf}P_Q.}
\tag{MB20}
$$

Spectral stability requires no negative physical eigenvalue, only declared
symmetry or gauge zero modes, and a nonnegative essential-spectrum threshold.
The CC29 reduced branch proves one finite stationary separation and positive
length curvature when $A_C>C_Q$. CC47 gives nonnegative frozen-mode
line-density curvature for $\Lambda_C>0$. These results cover the declared
reduced coordinates. Transverse, gauge, topological, continuum, and dynamical
fluctuations remain unevaluated.

The registered particle campaign supplies no Q2-qualified stationary
background. Its physical verdict remains
`INCONCLUSIVE—NUMERICAL QUALITY`, and MCC9 cannot upgrade it.

## 4. Frozen numerical witnesses

The checker uses IEEE-754 double precision and NumPy only.

- $\varphi=(1+\sqrt5)/2$, $T=\varphi^{-1}$, $R=1-T=\varphi^{-2}$.
- Numerical tolerance: $10^{-11}$ unless a positive-separation condition is
  stated explicitly.
- Routed propagation depth: $N=5$.
- Repeated-interaction duration: $\Delta t=0.2$ and six applications.
- Generator-branch phase: $\theta=0.43$ with branches $\theta$ and
  $\theta+2\pi$.
- Linear reservoir frequency: $\Omega=0.37$ and drive
  $F=0.08-0.03i$.
- Reduced support coefficients:
  $\sigma_Q=1$, $C_Q=0.5$, $\kappa_L=0.7$, and $A_C=2$.
- Line-density witness: periodic eight-site grid with
  $\Lambda_C=0.8$, $K_C=0.3$, and the constant mode removed by fixed charge.
- Fourier geometry witness:
  $k^\mu=(0,1.3,0,0)$ and a symmetric trace-reversed perturbation with zero
  row and column along the spatial $k$ direction.

Every other matrix is a literal constant in the checker. No random numbers are
used.

## 5. Frozen gates

### MCC1—minimal exterior dilation

Pass when:

1. $E_0^\dagger E_0+E_1^\dagger E_1=I$;
2. the channel Choi matrix is positive and has rank two;
3. the one-excitation two-port dilation reproduces (MB2);
4. a nontrivial unitary rotation of the Kraus pair leaves the reduced channel
   unchanged.

### MCC2—interface action and generator boundary

Pass when:

1. the block Hamiltonian built from (MB3) is Hermitian;
2. independent interior and exterior frame changes transform it by block
   conjugation;
3. exact unitary evolution preserves total number and total energy;
4. the two frozen logarithm branches exponentiate to the same discrete
   unitary and differ as generators.

### MCC3—transport selection

Pass when:

1. the full golden splitter is unitary;
2. one-sided routed cross coherence scales as $\varphi^{-N/2}$;
3. forward power scales as $\varphi^{-N}$ and the accumulated return power
   closes the unit ledger;
4. symmetric two-leg transport scales as $\varphi^{-N}$ in cross-coherence
   norm;
5. the closed coherent control differs from routed multiplication at $N=5$.

### MCC4—carrier normalization

Pass when:

1. the single-mode output/input power ratio equals $|t_\varphi|^2=T$;
2. two equal-Frobenius-norm mode states receive different energy weights from
   a nondegenerate positive frequency operator;
3. the scope record leaves a universal $\|K\|_F$-to-power map false.

### MCC5—reservoir support

Pass when:

1. six channel applications scale excited population by $T^6$ and transverse
   coherence by $T^3$;
2. (MB9) reproduces both discrete factors;
3. the frozen $C_*$ solves (MB10);
4. the homogeneous pole has negative real part;
5. the scope record leaves the physical bath identity false.

### MCC6—closed stress ledger

Pass when:

1. exact evolution under the enlarged Hermitian interface preserves total
   energy and number;
2. frozen interior and complementary exchange four-vectors cancel exactly;
3. the scope record leaves local reservoir stress components false until a
   metric-dependent reservoir action is supplied.

### MCC7—geometry compatibility

Pass when:

1. the frozen trace-reversed perturbation satisfies harmonic transversality;
2. its linearized Einstein tensor is transverse;
3. the induced constant-$G$ source is conserved;
4. multiplying the source by a scalar with a nonzero gradient produces a
   nonzero extra divergence for the frozen counterexample;
5. the scope record leaves state-dependent gravity false.

### MCC8—particle-interface map

Pass when:

1. (MB17) makes the Cartan covariant derivative transform covariantly;
2. the plus-sign alternative has a residual above $10^{-6}$;
3. $\Gamma_\Psi$ is positive with zero determinant;
4. a two-state Gram mixture is positive and full rank;
5. $Q_C$ remains invariant under $SU(2)_Q$ while a generic $SU(2)_Q$ rotation
   changes the Cartan population split.

### MCC9—reduced stationary boundary

Pass when:

1. the reduced CC36 equation has exactly one bracketed positive root for the
   frozen coefficients;
2. the root lies between the CC38 bounds and has positive CC39 curvature;
3. every nonconstant fixed-charge line-density mode has positive frozen
   quadratic curvature;
4. the scope record leaves a Q2-qualified full background and full constrained
   spectrum false;
5. the retained physical verdict equals `INCONCLUSIVE—NUMERICAL QUALITY`.

MCC9 is restricted to the CC29 one-coordinate branch and the CC47 frozen-mode
line-density sector. It supplies no full particle existence or spectrum claim.

## 6. Decision tree and stopping rule

The checker executes MCC1 through MCC9 once and prints every measured residual.
There is no adaptive tolerance, parameter change, rerun, or numerical search
outside the bracketed one-dimensional CC36 root.

- Any failed gate gives receipt verdict `FAIL`.
- Nine passed gates give receipt verdict `PASS` for the conditional completion
  boundary.
- The physical particle verdict remains `INCONCLUSIVE—NUMERICAL QUALITY`
  regardless of the receipt result because this checker supplies no qualified
  PA32 stationary background.
- The physical exterior and microscopic action remain Hypothesized unless a
  later action derives their carriers and coefficients independently of this
  receipt.

The first execution is the sole registered execution. Its literal output will
be copied to `computations/matter_completion_boundary_report.md`.

## 7. Expected artifacts

- `computations/matter_completion_boundary_check.py`—deterministic MCC1–MCC9
  checker;
- `computations/matter_completion_boundary_report.md`—derivation summary,
  first-execution output, receipt verdict, and retained physical boundary;
- `foundations/matter-completion-boundary.md`—integrated nine-part source
  authority after the receipt is recorded.

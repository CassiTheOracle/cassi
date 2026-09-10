# Regular Quark–Meson Carrier Protocol

## Status: Preregistered—September 2026

## Abstract

This calculation tests the smallest empirically grounded matter carrier that remains regular when the chiral condensate vanishes. The two-flavour quark–meson action keeps explicit Dirac quarks coupled polynomially to the linear chiral field. Its exact vector baryon current, fermionic spin and canonical statistics are defined at every field value, including a chiral zero. Three occupied colour copies give one unit of baryon number. A fixed hedgehog family then tests whether that inherited baryon number can lower its energy by binding into a finite chiral profile.

The calculation also uses the cosmological initial condition that matters for interpretation. The QCD transition inherits a nonzero baryon asymmetry from an earlier process; QCD conserves that asymmetry while reorganizing quarks into hadrons. A neutral five-femtometre box is therefore the usual initial condition at the QCD epoch, even though the cosmological volume contains a large net baryon number. The result separates regular current transport and fixed-baryon binding from baryogenesis, confinement, a full thermal formation rate and a Cassi derivation of the Standard Model.

<!-- qcd-quark-meson-carrier-protocol:start -->

## 1. Question and model

### 1.1 Selected empirical action

Use the two-flavour linear quark–meson action

$$
\boxed{
\mathcal L_{\rm QM}
=\bar q\left[i\gamma^\mu\partial_\mu
-g\left(\sigma+i\gamma_5\boldsymbol\tau\!\cdot\!\boldsymbol\pi\right)\right]q
+\frac12\partial_\mu\sigma\,\partial^\mu\sigma
+\frac12\partial_\mu\boldsymbol\pi\!\cdot\!\partial^\mu\boldsymbol\pi
-V(\sigma,\boldsymbol\pi),}
$$

with

$$
V=\frac{\lambda}{4}
\left(\sigma^2+\boldsymbol\pi^2-v^2\right)^2-H\sigma-C_{\rm vac}.
$$

The constant makes the physical vacuum $(\sigma,\boldsymbol\pi)=(f_\pi,\mathbf0)$ have zero energy. The parameter relations are

$$
\lambda=\frac{m_\sigma^2-m_\pi^2}{2f_\pi^2},\qquad
v^2=f_\pi^2-\frac{m_\pi^2}{\lambda},\qquad
H=f_\pi m_\pi^2,\qquad
g=\frac{M_q}{f_\pi}.
$$

The frozen values are

| Quantity | Value | Provenance |
|---|---:|---|
| $N_c$ | $3$ | QCD colour multiplicity |
| $f_\pi$ | $93\ {\rm MeV}$ | physical pion-decay scale used by the source model |
| $m_\pi$ | $139.6\ {\rm MeV}$ | physical pion mass used by the source model |
| $m_\sigma$ | $1200\ {\rm MeV}$ | Birse–Banerjee comparison parameter |
| $M_q$ | $500\ {\rm MeV}$ | Birse–Banerjee constituent-quark comparison parameter |
| $\hbar c$ | $197.3269804\ {\rm MeV\,fm}$ | unit conversion |

This is a low-energy effective model of QCD. The action and its parameters are external empirical inputs. The canonical Cassi two-density equations supply no selection rule for them.

### 1.2 Exact current and quantum sector

The global quark phase $q\mapsto e^{i\alpha/3}q$ gives

$$
\boxed{j_B^\mu=\frac13\bar q\gamma^\mu q,\qquad
\partial_\mu j_B^\mu=0.}
$$

The Yukawa matrix remains finite at $(\sigma,\boldsymbol\pi)=0$, so this current has no chiral-zero singularity. Quantize $q$ with canonical anticommutation relations. For the fixed-baryon calculation, occupy the same lowest grand-spin-zero orbital with one quark of each colour. The colour Slater determinant is antisymmetric, the occupation carries

$$
B=3\times\frac13=1,
$$

and the unoccupied reference is the normal-ordered constituent-quark vacuum. Meson fields are classical mean fields. Vacuum polarization and the Dirac-sea determinant are excluded from the energy; QMC6 records that truncation as a physical-completion failure.

### 1.3 Fixed chiral family

Let

$$
F_R(r)=2\arctan\!\left(\frac{R^2}{r^2}\right),
\qquad F_R(0)=\pi,
$$

and define

$$
\frac{\sigma_{a,R}}{f_\pi}=s_{a,R}(r)=1-a+a\cos F_R(r),
\qquad
\frac{\boldsymbol\pi_{a,R}}{f_\pi}
=p_{a,R}(r)\hat{\mathbf r}
=-a\sin F_R(r)\hat{\mathbf r}.
$$

The amplitude $a=0$ is the vacuum and $a=1$ is the standard unit chiral hedgehog. At $a=1/2$, the origin has $(\sigma,\boldsymbol\pi)=0$. Every term in $\mathcal L_{\rm QM}$ remains polynomial and finite there. The profile shape is fixed before execution; no result-dependent profile fitting is permitted.

## 2. Radial Dirac problem and energy

### 2.1 Grand-spin-zero orbital

Write the colour-independent quark orbital as

$$
q(\mathbf r,t)=\frac{e^{-iEt}}{\sqrt{4\pi}}
\begin{pmatrix}
h(r)\\ i\,j(r)\,\boldsymbol\sigma\!\cdot\!\hat{\mathbf r}
\end{pmatrix}\chi_h,
\qquad
(\boldsymbol\sigma+\boldsymbol\tau)\chi_h=0.
$$

For

$$S(r)=M_qs_{a,R}(r),\qquad P(r)=M_qp_{a,R}(r),$$

the radial equations are

$$
\boxed{
\begin{aligned}
\hbar c\,h'&=P h+(E+S)j,\\
\hbar c\left(j'+\frac{2j}{r}\right)&=-Pj+(S-E)h.
\end{aligned}}
$$

Regularity gives $h'(0)=0$ and $j(0)=0$. A bound state has $|E|<M_q$ and decays at infinity. Normalize it by

$$
\int_0^\infty r^2\left(h^2+j^2\right)dr=1.
$$

The baryon density is

$$
\rho_B(r)=\frac{N_c}{3}\frac{h^2+j^2}{4\pi},
\qquad
4\pi\int_0^\infty r^2\rho_B(r)dr=1.
$$

### 2.2 Meson and total energies

The meson energy of the fixed family is

$$
E_\Phi(a,R)=4\pi\int_0^\infty dr\,r^2
\left\{
\frac{f_\pi^2}{2\hbar c}
\left[(s')^2+(p')^2+\frac{2p^2}{r^2}\right]
+\frac{V(f_\pi s,f_\pi p)-V(f_\pi,0)}{(\hbar c)^3}
\right\}.
$$

$$
\boxed{E_B(a,R)=3E_{\rm lev}(a,R)+E_\Phi(a,R).}
$$

Before a bound orbital appears, use the separated threshold
$E_B(a,R)=3M_q+E_\Phi(a,R)$. The no-quark control is $E_\Phi(a,R)$ alone.
Binding at $a=1$ requires an interior minimum with

$$E_B(1,R_*)<3M_q.$$

This inequality is a fixed-sector binding criterion. It does not establish
confinement because free constituent quarks remain states of the effective
action.

## 3. Primary numerical calculation

### 3.1 Self-adjoint radial discretization

Use cell-centred radii $r_i=(i+1/2)\Delta r$ on
$0<r<r_{\max}=12\ {\rm fm}$. Construct the lower-left radial block

$$A=\hbar c\,D_h-P$$

with an even left ghost for $h$ and a zero outer ghost. With the radial weight
$W={\rm diag}(r_i^2\Delta r)$, set the upper-right block to the exact weighted
adjoint

$$A^\dagger_W=W^{-1}A^T W.$$

Suppress finite-difference doublers with the vanishing Wilson regulator

$$
\mathcal W_{\Delta r}
=\frac{\hbar c\,\Delta r}{2}D_h^\dagger{}_W D_h.
$$

The discrete Hamiltonian is

$$
H_r=\begin{pmatrix}
S+\mathcal W_{\Delta r}&A^\dagger_W\\
A&-S-\mathcal W_{\Delta r}
\end{pmatrix},
$$

and its Euclidean similarity transform
$\widetilde H_r=W_2^{1/2}H_rW_2^{-1/2}$ must be symmetric to absolute residual
below $10^{-10}$, where $W_2=W\oplus W$. The Wilson term is a numerical
regulator and must vanish under the declared grid sequence. Use sparse
shift-invert diagonalization around zero. Run $N_r=600,1200,2400$ at the final
selected point and $N_r=1200$ for the frozen scans.

At each point retain all eigenvalues in $(-M_q,M_q)$ returned among the 12
eigenpairs nearest zero. Track a branch by maximum weighted eigenvector overlap
between adjacent scan points. A candidate valence branch must have positive
overlap above $0.70$ at every step and remain separated from the next
same-sign level by at least $1\ {\rm MeV}$ at the selected endpoint. If no
in-gap state exists, record the threshold $M_q$ without inventing a bound
eigenvalue.

### 3.2 Frozen scans

At $a=1$, scan

$$R=0.10,0.15,\ldots,2.50\ {\rm fm}.$$

Choose the lowest sampled $E_B$ and refine only its immediately adjacent $R$ interval with Brent minimization to absolute radius tolerance $10^{-6}\ {\rm fm}$. A boundary minimum is reported as unqualified.

At the selected $R_*$, scan

$$a=0,0.05,\ldots,1.00.$$

For the formation-path envelope, repeat the frozen $R$ scan at each amplitude and retain the minimum permitted by the same rule. Report the largest excess above $3M_q$ along this envelope as the reduced nucleation barrier. No continuous-time formation rate is inferred.

For the fixed endpoint, compute the $2\times2$ central finite-difference Hessian of $E_B(a,R)$ at $(1,R_*)$ with steps $\Delta a=0.01$ and $\Delta R=0.01\ {\rm fm}$. Since $a=1$ is the edge of the declared path, the amplitude direction is qualified by the backward second difference and the one-sided first derivative. The radial curvature is qualified by the centered second difference.

### 3.3 Cosmological initial-condition ledger

Use

$$T_c=156.5\ {\rm MeV},\qquad
\eta_B=\frac{n_B}{n_\gamma}=6.0\times10^{-10},$$

with

$$
n_\gamma=\frac{2\zeta(3)}{\pi^2}
\left(\frac{T_c}{\hbar c}\right)^3,
\qquad
n_B=\eta_Bn_\gamma,
\qquad
d_B=n_B^{-1/3}.
$$

Record the expected net baryon number in a $(5\ {\rm fm})^3$ volume, the number of such volumes per net baryon, and $d_B$. Also reconstruct the radiation-era Hubble interval over
$155\le T\le158\ {\rm MeV}$ and $17.25\le g_*\le61.75$ using

$$H=1.66\sqrt{g_*}\,T^2/M_{\rm Pl},$$

with $M_{\rm Pl}=1.220890\times10^{19}\ {\rm GeV}$ and
$1\ {\rm GeV}^{-1}=6.582119569\times10^{-25}\ {\rm s}$.

The initial-condition statement is fixed: the QCD-era action conserves $B$. The $B=1$ calculation represents one unit inherited from baryogenesis. An exactly neutral closed state remains net neutral.

### 3.4 Exact finite-graph current control

Construct a deterministic three-site periodic Wilson–Dirac chain with internal Dirac-isospin dimension eight, spacing $0.4\ {\rm fm}$, Wilson parameter one, and the middle site set to $(\sigma,\boldsymbol\pi)=0$. Use the complex spinor whose real and imaginary components are consecutive integers $1,\ldots,48$, then normalize it.

For Hermitian hopping blocks $H_{xy}$ define

$$
\dot n_x=2\,\operatorname{Im}\sum_y\psi_x^\dagger H_{xy}\psi_y,
\qquad
J_{x\to y}=-2\,\operatorname{Im}(\psi_x^\dagger H_{xy}\psi_y).
$$

Require bond antisymmetry and
$\dot n_x+\sum_yJ_{x\to y}=0$ at every site. Repeat with the middle-site chiral field set to the vacuum and verify that the density derivative is unchanged, because every local Yukawa block is Hermitian and carries no baryon source.

## 4. Independent calculation

The verifier may read the primary receipt and retained radial arrays. It must not import the primary module.

1. Reconstruct every constant and field profile from the protocol.
2. Solve the bound-state equation by outward `DOP853` shooting from $r=10^{-7}\ {\rm fm}$ to $20\ {\rm fm}$. Use the regular series
   $$h=1+O(r^2),\qquad
   j=\frac{S(0)-E}{3\hbar c}r+O(r^3),$$
   and impose the asymptotic condition
   $$
   \frac{j}{h}=-\frac{\hbar c}{E+M_q}
   \left(\frac{\sqrt{M_q^2-E^2}}{\hbar c}+\frac1r\right).
   $$
   Bracket every root on 4,001 fixed energies in
   $[-0.999M_q,0.999M_q]$ and refine with Brent’s method. Select the nodeless branch by direct node counting.
3. Recompute meson energies with 512-point Gauss–Legendre quadrature on each of the intervals $[0,R]$, $[R,4R]$, $[4R,20\ {\rm fm}]$, plus the analytic power-law tail bound from $20\ {\rm fm}$ to infinity.
4. Reconstruct baryon normalization, RMS radius, current identities, scan selections, endpoint curvatures and all verdicts.
5. Verify every source hash and every retained array hash. Missing, altered or nonfinite evidence fails closed.

Primary and independent valence energies must agree within
$\max(0.5\ {\rm MeV},0.002|E|)$ at every independently checked point. Meson energies must agree within $0.05\%$. The selected radius must agree within $0.02\ {\rm fm}$ and the endpoint total energy within $2\ {\rm MeV}$.

## 5. Frozen decisions

### QMC1—regular action and current

`PASS` requires the vacuum first derivatives to vanish below
$10^{-10}$ in dimensionless units; the vacuum Hessian to reproduce
$m_\pi$ and $m_\sigma$ within $10^{-8}$ relative error; finite meson density at the declared chiral zero; discrete Hamiltonian symmetry below $10^{-10}$; finite-graph current residual and bond antisymmetry below $10^{-12}$; and zero change in $\dot n_x$ when the onsite chiral field is replaced at the zero site. Otherwise QMC1 is `FAIL`.

### QMC2—resolved quark spectrum

`PASS` requires QMC1, a nodeless in-gap endpoint state, branch overlaps above $0.70$, endpoint same-sign gap above $1\ {\rm MeV}$, finite normalized wavefunctions, three-grid eigenvalue convergence with the finest two differing by at most $2\%$, and primary–independent agreement at every checked point. Otherwise QMC2 is `FAIL` when a numerical or agreement criterion fails and `INCONCLUSIVE` when no endpoint bound state exists.

### QMC3—fixed-baryon binding and reduced stability

`SUPPORTS` requires QMC2, an interior $R_*$, $E_B(1,R_*)<3M_q$ by at least $5\ {\rm MeV}$, positive radial curvature, a baryon RMS radius in $[0.2,1.5]\ {\rm fm}$, and endpoint total-energy convergence within $5\%$. `CONTRADICTS` applies when the qualified minimum lies at or above $3M_q$. Other outcomes are `INCONCLUSIVE`.

### QMC4—formation-path accessibility

`SUPPORTS` requires QMC3 and a reduced envelope barrier no larger than the lower frozen crossover temperature, $155\ {\rm MeV}$. `CONTRADICTS` applies when QMC3 is `CONTRADICTS`. Other outcomes are `INCONCLUSIVE`. This verdict concerns the two-parameter hedgehog family only and supplies no thermal nucleation rate.

### QMC5—cosmological initial-condition consistency

`PASS` requires exact net-baryon conservation in the selected action, a finite positive $d_B$, an expected net baryon count below $10^{-6}$ in a $(5\ {\rm fm})^3$ volume, more than $10^6$ such volumes per net baryon, and a minimum Hubble-to-$2\ {\rm fm}/c$ ratio above $10^{12}$. This gate establishes the scale separation and inherited-$B$ interpretation. It does not derive baryogenesis.

### QMC6—complete physical matter formation

`PASS` requires all of the following in one retained model and state:

1. a Cassi selection rule for the quark–meson action and its physical parameters;
2. a regulator-compatible interacting vacuum or thermal density operator including the renormalized Dirac sea;
3. exact baryon-current transport, fermionic spin and canonical statistics;
4. continuum nonradial persistence and a physically normalized real-time formation rate from the cosmological ensemble;
5. confinement and an observable map that distinguishes the nucleon and its measured quantum numbers; and
6. a baryogenesis mechanism that supplies the measured signed asymmetry without fitting its outcome.

Any absent item makes QMC6 `FAIL` and sets
`complete_physical_matter_formation=false`. Positive QMC1–QMC5 results remain conditional evidence at their declared scope.

## 6. Evidence and stopping rules

The primary output directory is
`runs/20260910_qcd_quark_meson_carrier/primary/`; the independent output is
`runs/20260910_qcd_quark_meson_carrier/verification/`. Each program writes one strict JSON receipt and compressed arrays. Outputs store protocol bytes and SHA-256, source identities, environment, constants, all scan rows, selected wavefunctions, quadrature components, cosmological rows, current-control matrices or their exact hashes, gate inputs and verdicts.

Run the frozen scan once. A code defect may be repaired only by a protocol amendment that identifies the defect, preserves the first output, changes the protocol hash and reruns every affected arm into a fresh directory. Numerical thresholds, physical parameters, scan points and decision branches remain fixed. The verifier reconstructs all scientific observables independently. A missing primary receipt exits nonzero and records QMC1–QMC5 as `INCONCLUSIVE`, QMC6 as `FAIL`, and
`complete_physical_matter_formation=false`.

### 6.1 Execution amendment 1—implementation defects

The first primary receipt is retained at
`runs/20260910_qcd_quark_meson_carrier/primary/`. It exposed two
implementation departures from the frozen equations:

1. QMC1 specifies the vacuum-gradient residual in dimensionless units, while
   the implementation compared its cancellation remainder in ${\rm MeV}^3$
   directly with the dimensionless tolerance. The amended implementation
   divides by $\max(H,1\ {\rm MeV}^3)$ before applying the unchanged
   $10^{-10}$ threshold and retains both dimensional and dimensionless values.
2. Section 3.1 requires the in-gap valence branch to pass continuously through
   $E=0$. The implementation admitted only $0<E<M_q$, replacing the occupied
   branch by the separated threshold after its zero crossing. The amended
   implementation admits the declared interval $-M_q<E<M_q$, selects the
   nodeless in-gap level of smallest $|E|$, and evaluates the same-sign gap
   relative to that level.

No action coefficient, profile, scan point, numerical threshold or verdict
branch changes. The amended primary output is
`runs/20260910_qcd_quark_meson_carrier/amendment-1/primary/`; its independent
output is
`runs/20260910_qcd_quark_meson_carrier/amendment-1/verification/`. Every
affected scan is rerun.

### 6.2 Execution amendment 2—stable shooting reconstruction

The first independent receipt is retained at
`runs/20260910_qcd_quark_meson_carrier/amendment-1/verification/`. Its
eigenvalue residual was evaluated correctly, while its normalized wavefunction
was built by integrating the regular solution outward to $20\ {\rm fm}$.
Roundoff admitted an exponentially growing component beyond the localized
core, producing an RMS radius near the outer boundary.

The independent solver now shoots from both boundaries and matches at the
fixed radius $r_m=4\ {\rm fm}$. The outward solution retains the regular origin
series. The inward solution begins at $20\ {\rm fm}$ with the frozen decaying
asymptotic ratio. The normalized Wronskian at $r_m$ is the root residual, and
the joined outward–inward solution supplies the norm, node count and RMS
radius. The energy grid, tolerances, action, profiles, decision thresholds and
verdict tree remain unchanged.

The amended primary output is
`runs/20260910_qcd_quark_meson_carrier/amendment-2/primary/`; the amended
independent output is
`runs/20260910_qcd_quark_meson_carrier/amendment-2/verification/`. The primary
calculation is rerun solely to bind its receipt to this protocol hash.

<!-- qcd-quark-meson-carrier-protocol:end -->

## 7. Scope of a positive result

A positive result can establish a regular explicit-fermion carrier, exact baryon conservation and a finite reduced-space binding channel for an inherited baryon number. It can also show why a neutral five-femtometre QCD box is consistent with the cosmological asymmetry. The calculation cannot make this effective action emerge from the canonical Cassi state, generate baryon asymmetry, reproduce confinement, supply the renormalized sea, prove full nonradial stability or determine a real-time hadronization rate.

## References

- `computations/matter-formation-continuum-report.md` §§29, 31, 77–78—microscopic non-identifiability, complete-mechanism requirements, size boundary and normalized-chiral zero obstruction.
- `foundations/matter-completion-boundary.md` §§12, 22–23—six-part completion boundary and regular-carrier requirement.
- D. Diakonov, [“Chiral Quark-Soliton Model”](https://arxiv.org/abs/hep-ph/9802298), especially Eqs. (3.21), (4.6), (4.14)–(4.16)—Dirac Hamiltonian, occupied valence level, hedgehog profile and radial equations.
- M. C. Birse and M. K. Banerjee, [“Chiral model for nucleon and delta”](https://doi.org/10.1103/PhysRevD.31.118)—self-consistent valence-quark chiral soliton and physical parameter comparison.
- G. Holzwarth and J. Klomfass, [“The Chiral Phase Transition in Dissipative Dynamics”](https://arxiv.org/abs/hep-ph/0206228)—linear chiral field, physical scales and QCD transition context.
- A. Bazavov et al., [“Chiral crossover in QCD at zero and non-zero chemical potentials”](https://arxiv.org/abs/1812.08235)—physical-mass crossover and $T_c=156.5\pm1.5\ {\rm MeV}$.
- N. Aghanim et al., [“Planck 2018 results. VI. Cosmological parameters”](https://arxiv.org/abs/1807.06209)—cosmological baryon-density input underlying $\eta_B\simeq6\times10^{-10}$.

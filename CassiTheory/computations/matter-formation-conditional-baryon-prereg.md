# Conditional Chiral Baryon Benchmark

## Status: Mapped—September 2026

## Abstract

The registered real-density carrier laws do not identify a microscopic field, quantum state, physical normalization, or particle map. This frozen protocol tests one explicitly added low-energy model without treating that choice as a derivation from the canonical Cassi fields. A normalized complex doublet is lifted to an $SU(2)$ chiral field, the leading two- and four-derivative action admits a degree-one hedgehog profile, and a supplied Finkelstein–Rubinstein character gives a conditional fermionic nucleon interpretation. Two coefficients are fixed by the nucleon and Delta masses. A smooth, nonstationary degree-one radial profile must transfer excess core energy into an outgoing shell while approaching the finite-domain stationary profile. Independent calculations must reproduce the profile, calibration, trajectory, and empirical residuals. This benchmark supplies neither the six inputs required for physical matter formation nor a precision nucleon model.

## 1. Added effective field and action

Introduce an additional normalized complex doublet

$$
z(x)=\frac{1}{\sqrt{|Z_Y|^2+|Z_I|^2}}
\begin{pmatrix}Z_Y\\Z_I\end{pmatrix},
\qquad
E_Y=|Z_Y|^2,
\qquad
E_I=|Z_I|^2,
$$

whose relative phase is physical information absent from the registered real-density pair. Define

$$
U[z]=
\begin{pmatrix}
z_1&-z_2^*\\
z_2&z_1^*
\end{pmatrix}\in SU(2),
\qquad
L_\mu=U^\dagger\partial_\mu U.
$$

The conditional leading-order effective action is

$$
\boxed{
S_B=\int d^4x\left[
-\frac{f_B^2}{4}\operatorname{Tr}(L_\mu L^\mu)
+\frac{1}{32e_B^2}\operatorname{Tr}([L_\mu,L_\nu][L^\mu,L^\nu])
\right].
}
$$

The metric is $(+,-,-,-)$, $L_\mu$ is anti-Hermitian, $f_B>0$ has energy dimension, and $e_B>0$ is dimensionless. With the near-vacuum convention $U=\exp(i\boldsymbol{\sigma}\cdot\boldsymbol{\pi}/f_B)$, the quadratic term gives $\tfrac12\partial_\mu\boldsymbol{\pi}\cdot\partial^\mu\boldsymbol{\pi}$; $f_B$ is the pion-field and axial-current normalization used below. The coefficients are independent of the scalar-carrier coefficients registered elsewhere. No $\varphi$ identity or canonical density-to-phase map is asserted.

Compactify a finite-energy spatial slice to $S^3$. The integer

$$
B=-\frac{1}{24\pi^2}\int d^3x\,\epsilon^{ijk}
\operatorname{Tr}(L_iL_jL_k)\in\mathbb Z
$$

is the conserved baryon number. The $B=1$ hedgehog is

$$
U_0(\mathbf x)=\cos F(x)+i\,\widehat{\mathbf x}\cdot\boldsymbol\sigma\sin F(x),
\qquad x=e_Bf_Br,
\qquad F(0)=\pi,
\quad F(\infty)=0.
$$

Its dimensionless static energy is

$$
\mathcal E=4\pi\int_0^\infty
\left[x^2F_x^2+2\sin^2F+2\sin^2F\,F_x^2+
\frac{\sin^4F}{x^2}\right]dx,
$$

and its physical classical mass is $M_{\rm cl}=2f_Bs/e_B$ with $s=\mathcal E/4$. The two derivative orders scale oppositely under $F(x)\mapsto F(x/a)$, so the stationary solution obeys $\mathcal E_2=\mathcal E_4$ and has a finite Derrick scale.

## 2. Supplied sector rule and particle interpretation

The radial initial data lie in the degree-one configuration space $\mathcal Q_1$. As an additional analytic model input, impose the Finkelstein–Rubinstein odd-sector condition: a wavefunction changes sign under the noncontractible loop corresponding to a $2\pi$ spatial rotation. Collective-coordinate quantization of

$$
U(\mathbf x,t)=A(t)U_0(\mathbf x)A^\dagger(t),
\qquad A(t)\in SU(2),
$$

then admits half-integer spin and isospin with fermionic exchange statistics. The lowest allowed multiplet has $J=I=1/2$ and is conditionally identified with the nucleon doublet; the next has $J=I=3/2$ and is conditionally identified with the Delta multiplet. Supply the two-flavour charge rule

$$
Q=I_3+\frac{B}{2}.
$$

For $B=1$, $I_3=+1/2$ gives a charge-$+1$ proton and $I_3=-1/2$ gives a neutral neutron. For $B=-1$, $I_3=-1/2$ gives an antiproton and $I_3=+1/2$ an antineutron. This colour-neutral interpretation does not derive the charge rule, quark or gluon observables, a quantum vacuum or density operator, a regulator, or renormalization.

The dimensionless moment integral is

$$
\Lambda=8\int_0^\infty x^2\sin^2F
\left(1+F_x^2+\frac{\sin^2F}{x^2}\right)dx,
\qquad
I_0=\frac{\pi}{3e_B^3f_B}.
$$

The quantized masses are

$$
M_N=M_{\rm cl}+\frac{3}{8I_0\Lambda},
\qquad
M_\Delta=M_{\rm cl}+\frac{15}{8I_0\Lambda}.
$$

## 3. Frozen two-mass calibration

Use only

$$
M_N=938.918754\ \mathrm{MeV},
\qquad
M_\Delta=1232.0\ \mathrm{MeV}
$$

as calibration targets. The nucleon target is the arithmetic mean of the proton and neutron masses; the Delta target is the conventional isospin-averaged resonance mass. Let $d=M_\Delta-M_N$ and $M_{\rm cl}=(5M_N-M_\Delta)/4$. Solve, without numerical fitting,

$$
A=\frac{M_{\rm cl}}{2s},
\qquad
e_B=\left(\frac{2\pi\Lambda d}{9A}\right)^{1/4},
\qquad
f_B=Ae_B.
$$

Use $\hbar c=197.3269804\ \mathrm{MeV\,fm}$ only for unit conversion. Record $s$, $\Lambda$, $M_{\rm cl}$, $e_B$, $f_B$, $I_0$, reconstructed masses, the length unit $\hbar c/(e_Bf_B)$, and whether all coefficients are positive. The calibration is **Mapped** because two measured masses fix two coefficients. It sets only this effective baryon mass and length scale; it supplies no canonical Cassi flux, $Q_C$, stress-exchange, or general interaction normalization.

## 4. Imported out-of-fit discriminators

Compute from the same profile

$$
R_0^2=-\frac{2}{\pi}\int_0^\infty x^2\sin^2F\,F_x\,dx,
\qquad
r_{I=0}=\frac{\hbar c}{e_Bf_B}\sqrt{R_0^2},
$$

$$
R_{M0}^2=
\frac{\int_0^\infty x^4\sin^2F\,F_x\,dx}
{\int_0^\infty x^2\sin^2F\,F_x\,dx},
\qquad
r_{M,I=0}=\frac{\hbar c}{e_Bf_B}\sqrt{R_{M0}^2},
$$

$$
\mu_{p,n}=\frac{R_0^2}{9(e_Bf_B)^2}M_Nd
\ \pm\ \frac{M_N}{2d},
$$

and

$$
G=4\int_0^\infty x^2\left[
F_x+\frac{\sin2F}{x}+\frac{\sin2F}{x}F_x^2
+\frac{2\sin^2F}{x^2}F_x
+\frac{\sin^2F\sin2F}{x^3}
\right]dx,
$$

$$
g_A=-\frac{\pi G}{3e_B^2},
\qquad
g_{\pi NN}=\frac{M_N}{f_B}g_A.
$$

The last relation uses the declared $U=\exp(i\boldsymbol{\sigma}\cdot\boldsymbol{\pi}/f_B)$ pion normalization and the corresponding leading axial current. It is an imported leading-order chiral-model discriminator, not a quantity derived from the canonical Cassi densities.

The frozen comparison values are $r_{I=0}=0.769\ \mathrm{fm}$, $\mu_p=2.7928473446$, $\mu_n=-1.91304273$, $g_A=1.2754$, and $g_{\pi NN}=13.0$. The radius target is $\sqrt{r_p^2+\langle r_n^2\rangle}$ using $r_p=0.84075\ \mathrm{fm}$ and $\langle r_n^2\rangle=-0.1155\ \mathrm{fm}^2$, rounded only after combination. None enters the coefficient calibration.

For each observable, `SUPPORTS` means that observable agrees within 10 percent and `CONTRADICTS` means it does not. Also record the magnetic-moment magnitude ratio $|\mu_p/\mu_n|$ against $1.459898$ with a 5 percent threshold. No individual agreement licenses a precision-model or matter-completion claim, and no threshold may be changed after execution.

## 5. Conservative radial relaxation calculation

The time-dependent hedgehog equation in the same dimensionless variables is

$$
M(F,x)F_{tt}=M(F,x)F_{xx}+2xF_x+
\sin(2F)\left(F_x^2-F_t^2-1-\frac{\sin^2F}{x^2}\right),
\qquad
M=x^2+2\sin^2F.
$$

Its energy is proportional to

$$
\mathcal E(t)=4\pi\int_0^L
\left[M(F,x)(F_t^2+F_x^2)+2\sin^2F+\frac{\sin^4F}{x^2}\right]dx.
$$

Use $L=64$, spacing $h=0.04$, timestep $\Delta t=0.008$, and classical fourth-order Runge–Kutta integration through $t=30$. Hold $F(0,t)=\pi$ and $F(L,t)=0$. A unit-speed signal emitted from the initial core cannot return from the outer boundary by the stopping time. The initial condition is

$$
F(x,0)=2\arctan\left[\left(\frac{1.60}{x}\right)^3\right],
\qquad F_t(x,0)=0,
$$

with the endpoint values imposed exactly. Its odd near-origin expansion makes the Cartesian hedgehog field smooth, its degree is one, and its half-angle radius is deliberately wider than the stationary profile. Save $F$ and $F_t$ at $t=(0,5,10,15,20,25,30)$ plus a scalar record every $0.1$ time unit. Spatial derivatives use centred second-order differences in the interior and one-sided second-order differences only for diagnostic integrals. Energy and mismatch integrals use composite Simpson quadrature. The degree uses the exact cellwise primitive of $\sin^2F\,dF$, while a derivative-plus-Simpson value is retained as a discretization diagnostic.

At each scalar sample record total energy, energy inside $x\le 8$, energy outside $x\ge 8$, exact-primitive degree, derivative-plus-Simpson degree, half-angle radius, maximum $|F_t|$ inside $x\le8$, and the energy-norm profile mismatch to the independently solved stationary profile on $x\le8$. The mismatch is

$$
\delta_F^2=
\frac{\int_0^8\left[x^2(F_x-F_{0,x})^2+2(F-F_0)^2\right]dx}
{\int_0^8\left[x^2F_{0,x}^2+2F_0^2\right]dx}.
$$

Use the mean of the last 51 scalar samples, $25\le t\le30$, for late-time metrics. The radial relaxation gate passes only if all of the following hold:

1. the CFL ratio is 0.2, every evolved number is finite, and $M(F,x)>0$ at every evolved interior point;
2. total-energy drift through $t=30$ is at most 0.5 percent relative;
3. the exact-primitive degree remains within $2\times10^{-12}$ of one, its endpoint identity agrees independently, and every stored profile has finite first differences;
4. the initial half-angle radius exceeds the stationary value by at least 50 percent and the initial mismatch exceeds 0.20;
5. the late mean half-angle radius is within 10 percent of the stationary value and the late mean mismatch is below 0.15;
6. the late mean inner excess energy above the stationary profile is at most 35 percent of its initial value, while the outer energy has increased by at least the complementary decrease within a 3 percent total-energy ledger tolerance.

The continuum radial action conserves energy. The numerical result qualifies that statement only through the bounded-drift and outward-transfer gates; it does not assert exact discrete conservation or relaxation outside the hedgehog sector.

## 6. Static solver, independent verifier, and evidence contract

The primary program is `computations/matter_formation_conditional_baryon.py`; the independent program is `computations/verify_matter_formation_conditional_baryon.py`. Neither imports the other. Both solve the stationary boundary-value problem on $[10^{-5},64]$ with

$$
F_{xx}=\frac{-2xF_x-\sin(2F)
[F_x^2-1-\sin^2F/x^2]}{x^2+2\sin^2F},
$$

the regular origin condition $F(\epsilon)-\epsilon F_x(\epsilon)=\pi$, and the finite-domain condition $F(L)=0$. Both static and dynamic calculations therefore use the same outer boundary. The primary uses SciPy `solve_bvp` tolerance $10^{-8}$ and adaptive quadrature on $[0,L]$ with an explicit regular origin segment. It evolves the declared $h=0.04$ grid. Because a dilation changes the finite outer boundary, the stationary virial identity is $\mathcal E_4-\mathcal E_2=4\pi L^3F_x(L)^2$ rather than the infinite-domain $\mathcal E_2=\mathcal E_4$ relation.

The independent verifier solves the static profile from its own mesh and evaluates all integrals by fixed Gauss–Legendre panels. It reruns the radial evolution at $h=0.03$, $\Delta t=0.006$, with an independently written right-hand side and diagnostics. It compares dimensionless static energy and $\Lambda$ to the primary within $3\times10^{-5}$ relative, calibrated coefficients and out-of-fit observables within $8\times10^{-5}$ relative, and late relaxation metrics within 5 percent relative or $5\times10^{-4}$ absolute, whichever is larger. Both resolutions must independently satisfy every radial relaxation gate.

The primary output directory is `runs/20260907_matter_formation_conditional_baryon/`; the verifier writes to `runs/20260907_matter_formation_conditional_baryon_verification/`. Each refuses to overwrite any existing file. Canonical-LF hashes identify text sources and are labelled `canonical_text_sha256`; ordinary raw-byte SHA-256 identifies every generated artifact. Primary files are `results.json`, `static_profile.npz`, `relaxation_arrays.npz`, `frozen_protocol.txt`, and `source_record.md`; verifier files are `verification.json`, `independent_static_profile.npz`, `independent_relaxation_arrays.npz`, and `frozen_protocol.txt`. JSON must contain no NaN or Infinity.

Run a missing-preregistration control for the primary and a missing-primary control for the verifier in fresh directories. Each must exit nonzero with a typed failure receipt and no scientific pass. The independent verifier must check exact source identities, artifact paths and key sets, raw hashes, byte sizes, array shapes and finiteness, scalar fields, gate booleans, verdict strings, and calibration labels. It must construct the FR parity, allowed multiplets, and charge rows from the supplied rules rather than copying the primary dictionary. Duplicate check names invalidate the evidence contract.

## 7. Verdict tree and stopping rule

If source identities, output contracts, finite values, independent comparisons, static degree, Derrick balance, or mass reconstruction fail, every aggregate verdict is `INCONCLUSIVE`. If those checks pass:

- `radial_stationary_profile` is `SUPPORTS—finite-domain degree-one stationary profile in the hedgehog sector` when the static degree differs from one by at most $2\times10^{-8}$ and $|\mathcal E_4-\mathcal E_2-4\pi L^3F_x(L)^2|/(\mathcal E_2+\mathcal E_4)\le10^{-6}$; otherwise it is `CONTRADICTS`.
- `conditional_particle_interpretation` is `SUPPORTS—supplied odd-degree FR and charge rules yield nucleon/Delta assignments` when independent algebra reproduces the parity, $J=I=(1/2,3/2)$ assignments, and particle/antiparticle charge rows; otherwise it is `CONTRADICTS`. This verdict checks consequences of supplied rules, not their microscopic origin.
- `radial_relaxation` is `SUPPORTS—bounded-drift outward energy transfer approaches the stationary radial profile` only when both resolutions pass every radial relaxation gate; otherwise it is `CONTRADICTS`.
- `precision_nucleon_observables` is `SUPPORTS—every absolute out-of-fit observable agrees within 10 percent` only when $r_{I=0}$, $\mu_p$, $\mu_n$, $g_A$, and $g_{\pi NN}$ each support; otherwise it is `CONTRADICTS—one or more absolute out-of-fit observables miss 10 percent`.
- `conditional_baryon_benchmark` is `ADOPT—Mapped conditional leading colour-neutral chiral baryon benchmark` only when the stationary profile, supplied particle interpretation, radial relaxation, and mass reconstruction all pass. It is `REJECT—conditional benchmark fails a frozen structural discriminator` if the evidence qualifies but any of those conditions fails.

An `ADOPT` benchmark verdict does not close physical matter formation. It establishes only the consequences of an added leading chiral action in a prescribed degree-one hedgehog sector. The calculation supplies no canonical real-density-to-phase bridge, quantum vacuum or renormalization, full Cassi coupling and stress normalization, infinite-domain or nonradial stability, creation from degree-zero data, microscopic derivation of the FR or charge rules, QCD, colour confinement, baryogenesis, nuclear binding, chemistry, or precision nucleon agreement. Any change to the field, action, state rule, initial profile, grid, stopping time, observable, threshold, or verdict tree requires a new protocol and output directory.

## References

- `computations/matter-formation-continuum-report.md` §§18, 29—the qualified radial profile and six-part non-identifiability boundary.
- `computations/matter_formation_compact_carrier.py`—independent radial stationary and constrained-Hessian implementation.
- `foundations/geometric-manifold-completion.md` §§2.4–3—the complex Yang/Yin doublet and compact target geometry.
- `foundations/matter-completion-boundary.md` §12—the present completion interface.
- `foundations/particle-stationary-action-closure.md` §8—the conditional compact-target comparison and its current scope.
- Skyrme, *A Non-Linear Field Theory*, Proc. Roy. Soc. A **260** (1961) 127–138—the two- and four-derivative chiral action.
- Adkins, Nappi and Witten, *Static Properties of Nucleons in the Skyrme Model*, Nucl. Phys. B **228** (1983) 552–566—collective-coordinate calibration and nucleon observables.
- Finkelstein and Rubinstein, *Connection between Spin, Statistics, and Kinks*, J. Math. Phys. **9** (1968) 1762–1779—topological fermion state rule.
- Jia and Wang, [arXiv:0912.5142](https://arxiv.org/abs/0912.5142)—profile conventions and low-energy observable formulas used for independent comparison.
- Particle Data Group, *Review of Particle Physics* (2024)—mass, charge-radius, magnetic-moment, and axial-coupling comparison values.

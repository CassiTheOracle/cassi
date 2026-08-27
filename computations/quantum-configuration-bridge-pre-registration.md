# Quantum Configuration Bridge Pre-Registration

## Status: Hypothesized—August 2026

## Purpose

This protocol tests whether the regulated Cassi quantum construction can be
recovered from the canonical real-density theory without using QF1–QF4 as
independent premises. It separates mathematical equivalence, ontological
selection, physical-sector correspondence, continuum control, and empirical
discrimination.

The target implication is

$$
\left\{
\text{canonical two-density state and declared Cassi dynamics}
\right\}
\Longrightarrow
\left\{
\mathcal C,\mathcal H_Q,\hat H_Q,Q(t),|\Psi|^2,
\text{records},\text{physical correspondence}
\right\}.
$$

A successful downstream calculation after inserting canonical quantization,
an actual configuration, or quantum equilibrium does not establish this
implication. Each inserted premise is recorded at the gate that consumes it.

The companion numerical certificate is
`computations/verify_quantum_configuration_bridge.py`. It uses Python's
standard library and NumPy, has no random inputs, performs no fit or parameter
search, and evaluates the frozen constructions below once for the recorded
receipt.

## Source boundary

The source set is frozen to:

- `foundations/cassi-first-principles.md` §§1–2;
- `foundations/unified-lagrangian.md` §§1.1–1.3, 2, and 4;
- `foundations/quantum-measurement-derivation.md` §§1–7;
- `open-questions-cassi-answers.md` Q7 and Q10;
- `parameter-inventory.md` §§4 and 9;
- `predictions/falsifiable-predictions.md`;
- `CassiQwen/CassiFI/01-field-physics.md` §§“Canonical derived coordinates,”
  “Declared spatial geometry,” “Intrinsic field transport,” “Yang/Yin
  conversion,” and “Scale links.”

The canonical theory state is the nonnegative density pair

$$
X_{\mathrm{TF}}=(E_Y,E_I)\in\mathbb R_{\ge0}^2.
$$

Its exact positive-root coordinate section is

$$
s(E_Y,E_I)
:=\left(\sqrt{E_Y},0,\sqrt{E_I},0\right)\in\mathbb R^4.
$$

The complex CassiFI extension instead uses
$\mathcal E_Y,\mathcal E_I\in\mathbb C$ and the invertible complex-linear
coordinates

$$
D=\mathcal E_Y-\varphi\mathcal E_I,
\qquad
C=\frac{\varphi\mathcal E_Y+\mathcal E_I}{1+\varphi^2}.
$$

The physical-density bridge is

$$
\pi:\mathbb C^2\to\mathbb R_{\ge0}^2,
\qquad
\pi(\mathcal E_Y,\mathcal E_I)
=\left(|\mathcal E_Y|^2,|\mathcal E_I|^2\right).
$$

The registered finite quantum construction uses

$$
Q^A=
\left\{
\operatorname{Re}D,\operatorname{Im}D,
\operatorname{Re}C,\operatorname{Im}C
\right\}_{s,j}
$$

and declares QF1–QF4 in
`foundations/quantum-measurement-derivation.md`.

## Verdict vocabulary

Each DQ gate receives `PASS`, `FAIL`, or `NULL`.

- `PASS` means every required statement follows from the frozen source set or
  from the gate's explicitly named conditional premise.
- `FAIL` means a required source artifact is absent, a counterexample exists,
  or a mandatory equality exceeds its tolerance.
- `NULL` means the frozen evidence is non-discriminating while the required
  source artifacts exist.

Conditional algebra gates DQ3 and DQ6 may pass under their named premises.
Their pass does not repair a failed upstream derivation.

The campaign verdict is:

- `ADOPT` the promotion only if DQ1–DQ9 all pass and no gate imports the result
  it is meant to derive;
- `REJECT` the promotion if any required gate fails;
- `NULL` only if no required gate fails and at least one required gate is
  non-discriminating.

Numerical tolerance is

$$
\epsilon_{\mathrm{num}}=10^{-12}.
$$

## DQ1—Canonical lift

### Required result

The canonical real-density state must determine the finite complex
configuration up to a declared gauge, including the phases or canonical
momenta needed by the symplectic structure. The lift must be invertible on the
physical quotient and must preserve a nondegenerate two-form.

### Frozen certificates

At $(E_Y,E_I)=(4,9)$, evaluate the Jacobian of the positive-root section
$s$. In the coordinate order
$(\operatorname{Re}\mathcal E_Y,\operatorname{Im}\mathcal E_Y,
\operatorname{Re}\mathcal E_I,\operatorname{Im}\mathcal E_I)$, use

$$
\Omega
=
\begin{pmatrix}0&1&0&0\\-1&0&0&0\\0&0&0&1\\0&0&-1&0\end{pmatrix}.
$$

The certificate records

$$
\operatorname{rank}Ds,
\qquad
(Ds)^{\mathsf T}\Omega Ds.
$$

It also evaluates the Jacobian of $\pi$ at
$\mathcal E_Y=2+i$ and $\mathcal E_I=3+2i$ and records its rank and nullity.

### Pass condition

DQ1 passes only if the source supplies the missing phase/canonical variables,
an invertible physical quotient, and a nondegenerate pulled-back symplectic
form. A rank-two section with zero pulled-back two-form, or an undeclared
phase fibre of $\pi$, fails the gate.

## DQ2—Configuration-space Fisher bridge

### Required result

The canonical Qi/coherence law must generate the configuration-space Fisher
functional

$$
\mathcal I_F[\varrho]
:=
\int_{\mathcal C}d\mu_G\,
\varrho G^{AB}
\partial_A\ln\varrho\,
\partial_B\ln\varrho
$$

with coefficient $\hbar^2/8$, without a fitted multiplier or an independent
ensemble-information postulate.

### Frozen independence controls

Use the two-cell physical gradient energy

$$
E_\nabla(q)=\frac12(q_1-q_0)^2
$$

and the two-point discrete Fisher diagnostic

$$
I_F(p_0,p_1)
:=\frac{(p_1-p_0)^2}{(p_0+p_1)/2}.
$$

Evaluate:

1. $q=(1,-1)$ with uniform ensemble weights $p=(1/2,1/2)$;
2. the two spatially uniform configurations $(0,0)$ and $(1,1)$ with ensemble
   weights $p=(0.8,0.2)$.

### Pass condition

DQ2 passes only if the source derives an identity or controlled reduction
between physical-space Qi terms and $\mathcal I_F$ and fixes its coefficient.
A control with $E_\nabla>0$, $I_F=0$, together with a control having
$E_\nabla=0$, $I_F>0$, establishes that the two functionals are independent
and fails an unmediated identification.

## DQ3—Reverse-Madelung linearization

### Conditional premise

Assume an ensemble density $\varrho=R^2>0$, phase $S$, metric $G$, and the
Fisher coefficient $\hbar^2/8$.

### Required identity

For one flat configuration coordinate and unit mass, define

$$
\Psi=Re^{iS/\hbar},
$$

$$
\mathcal C
:=\partial_t(R^2)+\partial_x(R^2\partial_xS),
$$

$$
\mathcal H
:=\partial_tS+\frac12(\partial_xS)^2+U
-\frac{\hbar^2}{2R}\partial_x^2R.
$$

Then

$$
i\hbar\partial_t\Psi
+\frac{\hbar^2}{2}\partial_x^2\Psi-U\Psi
=
e^{iS/\hbar}
\left[-R\mathcal H+\frac{i\hbar}{2R}\mathcal C\right].
$$

The deterministic certificate uses

$$
R=e^{-ax^2/2},
\qquad
S=\frac b2x^2+ct,
$$

with $(a,b,c,\hbar)=(0.7,0.4,-0.3,1.2)$ at
$x\in\{-1.1,-0.4,0.2,0.9\}$ and
$U(x)=0.15x^2$.

### Pass condition

DQ3 passes if the maximum complex residual of the displayed identity is at
most $\epsilon_{\mathrm{num}}$. Its verdict is conditional on the DQ2 premise
and does not derive that premise.

## DQ4—Guidance uniqueness

### Required result

Equivariance must uniquely select

$$
v^A=J^A/|\Psi|^2
$$

from the frozen Cassi structure.

### Frozen counterexample family

On $\mathbb R^2$, use

$$
\rho(x,y)=e^{-(x^2+y^2)},
\qquad
f(x,y)=e^{-(x^2+y^2)},
$$

$$
K=(\partial_yf,-\partial_xf)
=(-2yf,2xf).
$$

Then

$$
\nabla\cdot K=0,
\qquad
v_0=0,
\qquad
v_1=K/\rho=(-2y,2x).
$$

Both satisfy the same stationary continuity equation for $J=0$ while defining
different trajectories.

### Pass condition

DQ4 passes only if the source supplies and proves conditions that eliminate
all nonzero divergence-free $K$. A nonzero certified $K$ with
$\nabla\cdot K=0$ and no source-level exclusion theorem fails the gate.

## DQ5—Quantum equilibrium

### Required result

The physical preparation density must be derived as
$\rho_Q=|\Psi|^2$, rather than declared only as an equivariant initial
condition.

### Frozen transport control

On a periodic grid with $128$ points, define positive normalized densities

$$
q_j\propto1+0.2\cos(2\pi j/128),
$$

$$
p_j\propto q_j\left[1+0.3\sin(4\pi j/128)\right].
$$

Advect both by the same integer circular shift for $37$ steps. Record

$$
D_{\mathrm{KL}}(p\|q)
=\sum_jp_j\ln(p_j/q_j)
$$

before and after transport and the maximum change in the transported ratio
$p_j/q_j$ after undoing the common shift.

### Pass condition

DQ5 passes only if the source derives equilibrium preparation, typicality, or
a registered coarse-grained relaxation theorem. Conservation of the
fine-grained non-equilibrium ratio and KL divergence, together with an
explicit source statement that equilibrium is irreducible, fails the gate.

## DQ6—Composition, Bell correlations, and no-signalling

### Conditional premise

Assume QF1 on product configuration spaces and the standard tensor-product
composition

$$
L^2(\mathcal C_A\times\mathcal C_B)
\cong
L^2(\mathcal C_A)\otimes L^2(\mathcal C_B).
$$

### Frozen certificate

Use the Bell state

$$
|\Phi^+\rangle=(|00\rangle+|11\rangle)/\sqrt2
$$

and

$$
A_0=\sigma_z,
\quad A_1=\sigma_x,
\quad
B_0=(\sigma_z+\sigma_x)/\sqrt2,
\quad
B_1=(\sigma_z-\sigma_x)/\sqrt2.
$$

Evaluate

$$
\mathcal B
=A_0\otimes(B_0+B_1)+A_1\otimes(B_0-B_1),
$$

its expectation and operator norm, and the reduced-state change after a frozen
local unitary on subsystem $B$.

### Pass condition

DQ6 passes conditionally if

$$
\langle\mathcal B\rangle=2\sqrt2,
\qquad
\|\mathcal B\|=2\sqrt2,
$$

and the reduced-state change is at most $\epsilon_{\mathrm{num}}$. This gate
checks the conditional quantum composition algebra and does not derive QF1
from the canonical density PDE.

## DQ7—Physical sectors and records

### Required result

The canonical state must derive a dimensionally complete map to the observed
microscopic sectors, including spin, fermionic antisymmetry, gauge-invariant
observables, particle creation/annihilation where applicable, and stable
detector-record functionals.

### Documentary gate

DQ7 passes only if the frozen source set contains:

1. a derived Dirac or equivalent spin-$1/2$ sector;
2. a derived fermionic composition rule;
3. a dimensionally complete two-fluid/particle correspondence;
4. a derived gauge quotient and observable map;
5. an apparatus record map from the same microscopic variables.

An optional sector, a formal projection with an unset dimensionful bridge, or
a standard sector appended by declaration fails the gate.

## DQ8—Regulator removal

### Required result

The finite CassiFI construction must possess a regulator-removal and
renormalization limit with convergent observables and no retuning.

### Frozen free-operator receipt

For the periodic second-difference Laplacian on a domain $L=2\pi$, use mode
$m=1$ and

$$
\lambda_N
=\frac{4}{a_N^2}\sin^2\!\left(\frac{a_N}{2}\right),
\qquad
a_N=\frac{2\pi}{N},
$$

for $N\in\{16,32,64,128\}$. The expected continuum value is $1$.
Record the observed order from successive errors.

### Pass condition

The numerical receipt passes if the free-operator convergence order exceeds
$1.9$. DQ8 itself passes only if the source additionally supplies an
interacting CassiFI regulator sequence, counterterm/parameter flow,
self-adjoint-domain control, and convergence of at least one physical
observable without retuning. A free-operator receipt alone is insufficient.

## DQ9—Cassi-specific discrimination

### Required result

The quantum configuration must produce at least one preregistered observable
that distinguishes the Cassi physical identification from ordinary quantum
mechanics or from an empirically equivalent ontology.

The candidate must specify, before target comparison:

- the physical preparation and observable;
- the Cassi prediction and orthodox-quantum baseline;
- every parameter and its provenance;
- the raw data source and null model;
- a fixed decision threshold;
- a result that cannot be reproduced by choosing a generic Hamiltonian input.

### Pass condition

DQ9 passes only if such a frozen, no-fit candidate and its required evidence
artifact exist in the source set. Standard Schrödinger dispersion,
interference, Born statistics, entanglement, no-signalling, or a reciprocal
coupled-oscillator result shared by ordinary quantum mechanics does not
satisfy this gate.

## Protocol lock

The numerical certificate is evidentiary only after this file is written.
Changing a construction, point set, threshold, source boundary, or decision
rule requires a new frozen protocol before another evidentiary execution.
Documentary absences are checked against the frozen source set and receive no
numerical substitute.

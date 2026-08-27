# Scalar Time Reparameterization in Cassi Applications

## Status: Derived conditional theorem / Hypothesized common-lapse application—August 2026

## Abstract

A positive scalar multiplying an autonomous first-order generator changes the
rate at which a trajectory is traversed while preserving its state-space
orbit. This paper states and proves the exact result, records the hypotheses
that make the result valid, and identifies the structures that require more
than a scalar multiplication. The result applies directly to a global
first-order generator and to an uncoupled local reaction. Spatially varying
multipliers, second-order equations, stochastic terms, memory kernels,
time-dependent boundaries, and noncommuting operator splits each require the
corresponding transformed terms; multiplying only a displayed right-hand side
is generally insufficient.

The canonical conversion subflow supplies an exact conditional age
$d\tau_F=(1-q)\,dt$. Relative to a reference clock, the normalized candidate
lapse is $N_q=(1-q)/(1-q_{\mathrm{ref}})$. The conversion identity is
**Derived conditional**. Applying the same factor to wave, particle,
gravitational, boundary, or other independent sectors is **Hypothesized** and
is tested by the registered CT-2 cross-clock discriminator. The paper adds no
new parameter or prediction. The symbol $q$ below means only the CassiTheory
canonical bounded diagnostic; a similarly named quantity from another
repository is not substituted into these equations.

---

## 1. Scope and notation

The theorem concerns a change of evolution parameter, not an automatic
construction of a physical metric or a global simultaneity convention.

Let $X(t)$ be a state in a finite-dimensional space or in a function space with
a specified generator domain. Let $L$ be an autonomous first-order generator,
possibly nonlinear, and write

$$
\frac{dX}{dt}=N(t,X(t))\,L[X(t)].
\tag{1}
$$

The scalar $N$ multiplies the complete tangent vector $L[X]$. It is allowed to
depend on the coordinate time and on the state along the trajectory. For an
orientation-preserving time change, $N$ is positive along the trajectory. The
coordinate time $t$ is the simulator or laboratory parameter; a parameter
$\tau$ is introduced only by the integral of $N$.

A claim that $N$ is a common lapse has a stronger meaning than a claim that a
single equation can be rewritten. Every sector included in that claim must
have the same $N$, and all of its clock-bearing, boundary, noise, and memory
terms must be transformed consistently. A gate inserted into one selected
update equation is a sector-specific rate modification until those conditions
are established.

### 1.1 Regularity needed for an invertible clock

The clean equivalence uses an absolutely continuous, strictly increasing map
$t\mapsto\tau(t)$. It is enough on each finite interval to require that $N$
is measurable and locally integrable along the solution, positive almost
everywhere, and bounded above and away from zero on that interval. The latter
bounds give a locally absolutely continuous inverse. A weaker positive
integrable $N$ can still define a monotone clock, but an inverse may fail to be
regular where $N$ approaches zero.

The generator must admit a unique solution for the initial state over the
interval under consideration. For an unbounded linear operator this means a
well-posed semigroup or evolution problem with its domain kept explicit. The
same initial state is used in both parameters. These are analytic hypotheses,
not additional Cassi constants.

### 1.2 What the scalar claim includes

When (1) holds, the scalar changes elapsed coordinate time, rates per unit
coordinate time, and any observable whose definition explicitly uses $t$.
It preserves the ordered state-space trajectory, fixed points, and events
identified by a state-space condition. It does not preserve a coordinate-time
period, a coordinate-time delay, a noise quadratic variation, a boundary
injection schedule, or a second-order acceleration law unless each is
transformed. A local scalar $N(x,t)$ supplies a family of local clocks; it is a
single global reparameterization only when its value is spatially uniform on
the coupled state.

---

## 2. Scalar first-order reparameterization theorem

The theorem says exactly when a scalar multiplier is only a change of the
clock used to traverse an autonomous first-order flow.

### 2.1 Statement

**Theorem 1 (scalar first-order reparameterization, Derived conditional).**
Let $L$ generate a unique flow $\Phi_s$ on a state domain, and let $X$ solve
(1) on $[t_0,t_1]$. Assume $N(t,X(t))$ is finite, positive, and locally
integrable along this solution, with enough local bounds for the inverse below
to exist. Define

$$
\tau(t):=\tau_0+\int_{t_0}^{t}N(s,X(s))\,ds.
\tag{2}
$$

Then $\tau$ is strictly increasing and the reparameterized state

$$
Y(\tau):=X\bigl(t(\tau)\bigr)
\tag{3}
$$

satisfies

$$
\frac{dY}{d\tau}=L[Y].
\tag{4}
$$

Conversely, if $Y$ solves (4) and an absolutely continuous strictly
increasing $\tau(t)$ satisfies

$$
\frac{d\tau}{dt}=N\bigl(t,Y(\tau(t))\bigr),
\tag{5}
$$

then $X(t):=Y(\tau(t))$ solves (1). In either direction,

$$
\boxed{
X(t)=\Phi_{\tau(t)-\tau_0}(X_0)
}
\tag{6}
$$

for $X_0=X(t_0)=Y(\tau_0)$.

### 2.2 Proof and exact solution equivalence

The proof is the chain rule along an absolutely continuous orbit. From (2),
$d\tau/dt=N$. Therefore

$$
\frac{dY}{d\tau}
=\frac{dX/dt}{d\tau/dt}
=\frac{N(t,X(t))L[X(t)]}{N(t,X(t))}
=L[Y].
\tag{7}
$$

The converse follows in the same way:

$$
\frac{dX}{dt}
=\frac{dY}{d\tau}\frac{d\tau}{dt}
=L[X]N(t,X(t)).
\tag{8}
$$

Uniqueness of the $L$-flow gives (6). For a linear generator $A$, the same
statement reads

$$
X(t)=\exp\!\left(A\int_{t_0}^{t}N(s,X(s))\,ds\right)X_0,
\tag{9}
$$

with the usual semigroup interpretation when $A$ is unbounded. If $N$ is a
known function of $t$ alone, the integral can be formed before solving. If
$N$ depends on $X$, (2) and the orbit are determined together; the orbit
identity remains exact, while the clock is path-dependent.

A spatially uniform piecewise-constant lapse is covered without a special
case: each segment advances the same $L$-flow by the integrated $\Delta\tau$.
The endpoint state depends on the sum of those increments, while the
coordinate-time partition remains a separate record.

### 2.3 Necessary conditions for the orientation-preserving reading

For an equation to represent the same autonomous first-order flow under one
orientation-preserving scalar clock, the following conditions are required.

1. **One scalar tangent multiplier.** The complete vector $L[X]$ is multiplied
   by the same scalar. Component-specific factors, matrices, or operators do
   not satisfy (1).
2. **A monotone clock.** $N>0$ almost everywhere and its integral is finite on
   finite intervals. A zero interval pauses the flow and destroys a strict
   inverse; a sign change reverses or folds the parameter orientation.
3. **The same generator domain.** Spatial domains, constraints, and admissible
   states must remain those of $L$ after the change of parameter.
4. **No untransformed explicit time.** If the generator is $L_t$, the changed
   equation is $dY/d\tau=L_{t(\tau)}[Y]$. It equals the autonomous equation
   (4) only when the explicit time dependence is removed or consistently
   pulled back.
5. **No hidden coordinate-time memory.** A delayed or history term must be
   expressed in the new parameter or represented by state variables whose
   equations receive the same scalar.
6. **Complete event and boundary data.** Sources, resets, moving boundaries,
   and boundary clocks must use the transformed parameter whenever they are
   part of the claimed system.

These conditions are necessary for a literal global reparameterization. They
also give a practical sufficiency test when the generator problem is
well-posed. Relaxing positivity can describe a nondecreasing or orientation-
reversing parameter, but it is outside the positive-lapse interpretation.

---

## 3. Spatially varying PDE generators

A PDE turns a scalar time question into a question about multiplication and
spatial derivatives.

Let $U(\cdot,t)$ be the full field state and let $\mathcal L$ include advection,
diffusion, conversion, sources, and any coupled auxiliary fields. If
$N=N(t)$ is uniform over the spatial domain, then

$$
\partial_tU=N(t)\mathcal L[U]
\tag{10}
$$

is exactly Theorem 1 in the function space, subject to the domain and
boundary conditions. Every term in $\mathcal L$ advances by the same
$\Delta\tau$.

If $N=N(x,t)$, the equation instead has the multiplication operator
$M_N$:

$$
\partial_tU=M_N\mathcal L[U],
\qquad (M_NV)(x)=N(x,t)V(x).
\tag{11}
$$

Unless $N$ is spatially uniform, there is no single $\tau(t)$ with
$d\tau/dt=N(x,t)$ for all $x$. A pointwise reaction
$\mathcal L[U](x)=R(U(x))$ can use independent local clocks
$\tau_x(t)=\int N(x,s)\,ds$ when cells are uncoupled. Advection, diffusion,
Poisson coupling, and nonlocal sources connect those cells and require a
coupled transformation.

The obstruction is visible in the commutators. For a spatial derivative,
$[M_N,\nabla]U$ contains $(\nabla N)U$, and for diffusion
$[M_N,\nabla^2]U$ contains both first- and second-derivative terms of $N$.
Consequently, multiplying $-\mathbf u\!\cdot\nabla U+D\nabla^2U$ by $N(x,t)$
does not equal a global change of time. A divergence-form flux must also be
redesigned consistently: $N D\nabla^2U$ and
$\nabla\!\cdot(ND\nabla U)$ differ by terms containing $\nabla N$.

The canonical two-fluid equations therefore support two distinct statements.
A uniform lapse applied to the complete field generator is a conditional
first-order reparameterization. The local conversion receipt
$d\tau_F(x)=(1-q(x,t))dt$ is a family of local conversion ages when $q$ varies
in space. It becomes a global time change only in a spatially uniform or
explicitly decoupled setting. An elliptic Poisson solve or an algebraic
readout is a constraint/readout at a chosen slice; it acquires no time lapse by
multiplying the elliptic equation by $N$.

---

## 4. Second-order systems

Second-order equations carry a velocity definition, so their acceleration does
not transform by multiplying the force once.

Let $x(\tau)$ solve a second-order equation

$$
\frac{d^2x}{d\tau^2}=F\!\left(x,\frac{dx}{d\tau},\tau\right),
\qquad \frac{d\tau}{dt}=N(t)>0.
\tag{12}
$$

Writing $\dot{x}=dx/dt$ and $x_\tau=dx/d\tau$ gives

$$
\dot{x}=N x_\tau,
\qquad
\ddot{x}=N^2x_{\tau\tau}+\dot N x_\tau
=N^2F\!\left(x,\frac{\dot x}{N},\tau(t)\right)
+\frac{\dot N}{N}\dot x.
\tag{13}
$$

The $\dot N/N$ term is required even for a spatially uniform lapse that
changes with time. For example, a physical damping law
$x_{\tau\tau}+\gamma x_\tau=F(x)$ becomes

$$
\ddot x=\frac{\dot N}{N}\dot x-\gamma N\dot x+N^2F(x).
\tag{14}
$$

The common shortcut $\ddot x=N F(x)$ is a different dynamical system. It
agrees only under special normalization choices and does not establish a time
reparameterization.

A second-order model can still use Theorem 1 after state augmentation. Define
$X=(x,v)$ with $v=dx/d\tau$, and write

$$
\frac{d}{dt}\begin{pmatrix}x\\v\end{pmatrix}
=N(t)\begin{pmatrix}v\\F(x,v,\tau(t))\end{pmatrix}.
\tag{15}
$$

This is first-order in the $\tau$-velocity state. A simulator whose stored
velocity is $dx/dt$ must apply (13); changing only the force leaves the state
variables inconsistent. The same distinction applies to wave equations,
particle sectors, and any PDE with an independently evolved momentum or
velocity field.

---

## 5. Stochastic terms and quadratic variation

Random increments scale with the square root of elapsed time, not with the
elapsed time itself.

Suppose a physical-parameter SDE in Itô form is

$$
 dX=L[X]d\tau+B[X]dW_\tau,
\tag{16}
$$

where $W_\tau$ is a standard Wiener process and $N$ is positive and
predictable. Under $d\tau=N(t,X)dt$, the time-changed equation is

$$
\boxed{
 dX=N(t,X)L[X]dt+\sqrt{N(t,X)}\,B[X]dW_t
}
\tag{17}
$$

in the usual Itô time-change sense. The drift receives the factor $N$ and the
noise amplitude receives $\sqrt N$ because

$$
 d\langle W_{\tau(t)}\rangle=d\tau=Ndt.
\tag{18}
$$

Multiplying the noise amplitude by $N$ would give quadratic variation
$N^2dt$ and a different diffusion process. With several independent noise
channels, all channels receive the same $\sqrt N$ only when the claim is a
common lapse. State-dependent time changes require the standard adaptedness
and integrability conditions. Converting between Itô and Stratonovich forms
must be done after the time change; state-dependent noise can then carry the
usual convention-dependent drift correction.

A deterministic first-order receipt does not establish the stochastic
extension. A stochastic sector can share the candidate lapse only after its
noise covariance, filtration, and any boundary noise have been transformed
with (17).

---

## 6. Memory and delay kernels

A memory law stores elapsed history, so its kernel must be reparameterized
along with the state.

Consider a physical-parameter Volterra equation

$$
\frac{dY}{d\tau}
=R[Y(\tau)]
+\int_0^{\tau-\tau_0}K(\sigma)M[Y(\tau-\sigma)]\,d\sigma.
\tag{19}
$$

Let $X(t)=Y(\tau(t))$ with $d\tau/dt=N(t)>0$. For each accessible $\sigma$,
let $t_\sigma$ satisfy $\tau(t_\sigma)=\tau(t)-\sigma$. Then

$$
\frac{dX}{dt}
=N(t)R[X(t)]
+N(t)\int_0^{\tau(t)-\tau_0}
K(\sigma)M[X(t_\sigma)]\,d\sigma.
\tag{20}
$$

Changing the integral to the coordinate lag $s=t-t_\sigma$ gives

$$
\frac{dX}{dt}
=N(t)R[X(t)]
+N(t)\int_0^{t-t_0}
K\!\bigl(\tau(t)-\tau(t-s)\bigr)
M[X(t-s)]N(t-s)\,ds.
\tag{21}
$$

Thus a fixed physical kernel becomes a path-dependent coordinate-time kernel
and carries the Jacobian $N(t-s)$. A fixed coordinate delay $s_0$ generally
represents a changing physical delay
$\tau(t)-\tau(t-s_0)$; it is equivalent only when that distinction is
intended or $N$ is constant. A delayed equation with an internal Markovian
realization can use Theorem 1 by appending every memory state to $X$ and
multiplying every memory-state equation by the same $N$.

A memory-bearing $q$ makes the accumulated candidate time a worldline
functional. The exact conversion age remains the integral of the instantaneous
openness along the recorded path. Recovering a coordinate-time interval from
an endpoint imbalance requires the gate history when the gate has memory.
Neither fact promotes the candidate common lapse to an independent physical
law.

---

## 7. Boundaries, domains, and events

A boundary condition is part of a generator problem and has its own clock
when it carries time dependence.

For a fixed spatial domain $\Omega$, a static Dirichlet or homogeneous Neumann
condition is compatible with a uniform scalar reparameterization when its
operator domain is unchanged. A time-dependent boundary value

$$
B U(t)=g(t)
\tag{22}
$$

must be supplied as $g(t)=\widetilde g(\tau(t))$ to describe the same physical
boundary schedule. A boundary source prescribed per unit $t$ requires the
corresponding conversion to a source per unit $\tau$. Reset rules, threshold
events, and sampled observations have the same requirement when they are part
of the claimed dynamics.

A moving boundary $x_b(\tau)$ obeys

$$
\frac{dx_b}{dt}=N(t)\frac{dx_b}{d\tau}.
\tag{23}
$$

Keeping the interior lapse while leaving the boundary velocity in coordinate
time changes the domain problem. Dynamic boundary variables must be appended
to the state and evolved with the same scalar. Conservation-law fluxes must be
transformed together with volume terms; an interior multiplication that leaves
the boundary flux on its old clock need not conserve the same quantity.

For $N(x,t)$, even a static boundary can see a different local rate from the
interior. A global boundary-time claim then requires a specified spatial clock
field and transformed flux/trace conditions, rather than the single inverse
$\tau(t)$ used in Theorem 1.

---

## 8. Explicit time dependence and noncommuting operators

Operator ordering determines whether a split update is a reparameterization or
a new approximation.

### 8.1 Explicitly time-dependent generators

For

$$
\frac{dX}{dt}=N(t)L_t[X],
\tag{24}
$$

Theorem 1 yields

$$
\frac{dY}{d\tau}=L_{t(\tau)}[Y].
\tag{25}
$$

The result is an exact pullback of the time-dependent generator. It equals a
fixed autonomous $L$ only when the explicit dependence is absent or has a
separate declared transformation. For a linear family $A(t)$, commutation
$[A(t_1),A(t_2)]=0$ removes time-ordering in the propagator, yet it does not
usually make the result $\exp(A\Delta\tau)$; proportionality to one fixed
operator, or another explicit reduction, is still required.

### 8.2 Splitting and commutators

Let $L=A+B$. The exact global-lapse step of size $\Delta t$ advances by
$\Delta\tau=\int_t^{t+\Delta t}N(s)ds$:

$$
X_{\mathrm{exact}}=\exp\!\bigl(\Delta\tau(A+B)\bigr)X.
\tag{26}
$$

A Lie split and a Strang split are respectively

$$
\exp(\Delta\tau A)\exp(\Delta\tau B)X,
\qquad
\exp\!\left(\tfrac12\Delta\tau A\right)
\exp(\Delta\tau B)
\exp\!\left(\tfrac12\Delta\tau A\right)X.
\tag{27}
$$

They remain approximations when $[A,B]\ne0$, with the usual commutator
errors. They are consistent with a scalar clock only when every substep uses
the same integrated $\Delta\tau$ and the intended order. Applying $N$ to one
operator while leaving another on $dt$ gives a sector-selective update.

For a spatial lapse, $M_N$ generally fails to commute with derivative
operators. Commutators such as $[M_N,A]$ are then part of the transformed
operator. A split implementation that evaluates $N$ once and silently moves
it through a derivative is a different operator. These errors are structural
and do not disappear by naming the multiplier a lapse.

---

## 9. The conversion-flow clock and the candidate normalized lapse

The canonical conversion identity is exact on its isolated subflow; its
universal interpretation is a separate hypothesis.

### 9.1 Exact conversion age

Use the canonical CassiTheory fields and definitions

$$
\varepsilon=E_Y-\varphi E_I,
\qquad
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2},
\qquad
\rho=E_Y+E_I.
\tag{28}
$$

The additive floor in (28) is in the reference-normalized solver variables;
its physical-density form carries the external reference density described in
`foundations/cassi-first-principles.md` §2.1. On the isolated conversion
subflow,

$$
\frac{d\varepsilon}{dt}
=-(1+\varphi)\lambda(1-q)\varepsilon.
\tag{29}
$$

Remove transport and source increments before applying this local receipt.
Define

$$
\boxed{
 d\tau_F:=(1-q)dt,
 \qquad
 \frac{d\varepsilon}{d\tau_F}=-(1+\varphi)\lambda\varepsilon.
}
\tag{30}
$$

This is Theorem 1 with the intrinsic conversion generator
$L_{\mathrm{conv}}[\varepsilon]=-(1+\varphi)\lambda\varepsilon$ and the
local scalar $N=1-q$. For $\lambda>0$ and resolved nonzero endpoints on one
sign-preserving conversion branch,

$$
\boxed{
\Delta\tau_F
=-\frac{1}{(1+\varphi)\lambda}
\ln\left|\frac{\varepsilon_1}{\varepsilon_0}\right|
=\int_{t_0}^{t_1}(1-q)dt.
}
\tag{31}
$$

The conversion age and its monotone imbalance arrow are **Derived
conditional** on the canonical rank-one conversion law. Exact equilibrium
$\varepsilon=0$ has no readable conversion tick even though the constitutive
value of $1-q$ is continuous. Spatial transport, diffusion, and external
sources belong to separate receipts.

When $\lambda=0$, the direct constitutive age
$\Delta\tau_F=\int(1-q)\,dt$ remains defined from the frozen $q$ path, but the
endpoint expression (31) is unavailable because conversion leaves
$\varepsilon$ unchanged. Receipts therefore distinguish a computed
conversion age from an endpoint-observable conversion tick.

### 9.2 Relative rate and candidate common lapse

For two local conversion clocks using the same coordinate interval, (30) gives

$$
\boxed{
\frac{d\tau_F(x)}{d\tau_F(x_{\mathrm{ref}})}
=\frac{1-q(x)}{1-q_{\mathrm{ref}}}
=:N_q(x\mid x_{\mathrm{ref}}).
}
\tag{32}
$$

For $q_{\mathrm{ref}}<1$ and finite canonical fields, $N_q$ is positive. The
candidate physical time defines, relative to an independently specified
reference clock,

$$
\boxed{
 d\tau_{\mathrm{phys}}^{\mathrm{cand}}(x)
=N_q(x\mid x_{\mathrm{ref}})\,d\tau_{\mathrm{ref}}.
}
\tag{33}
$$

If the reference is itself the conversion clock,
$d\tau_{\mathrm{ref}}=d\tau_F(x_{\mathrm{ref}})$ and (33) reproduces the local
conversion age. The open-gate choice $q_{\mathrm{ref}}=0$ with
$d\tau_{\mathrm{ref}}=dt$ is a normalization limit; an active conversion
reference with a readable imbalance has $q_{\mathrm{ref}}>0$.

Equation (32) is **Derived conditional** as a relative conversion-clock
identity. Equation (33) is **Hypothesized** as a universal common lapse. The
conversion trace fixes only a product of an intrinsic kinetic factor and a
clock factor:

$$
\frac{d\varepsilon}{dt}
=-(1+\varphi)\lambda K(q)N(q)\varepsilon,
\qquad K(q)N(q)=1-q.
\tag{34}
$$

Gated kinetics uses $K=1-q$, $N=1$; the candidate physical-time reading uses
$K=1$, $N=1-q$. Both give the same conversion receipt. Independent sectors
must decide whether one common lapse exists.

### 9.3 Symbol boundary across repositories

This paper uses `$q$` only for the CassiTheory canonical bounded diagnostic in
(28). A `$q$` or `$Q$` in another repository can have a different denominator,
normalization, state, and unit convention. CassiFI/Qwen currently defines

$$
Q=
\frac{\bar\rho^2}
{\bar\rho^2+\varphi^{-2}+\bar m_{\varepsilon^2}},
$$

where $\bar m_{\varepsilon^2}$ is the normalized stored `epsilon2_ema`;
equation (28) contains the instantaneous canonical $\varepsilon^2$.
Cross-repository work may compare the declared clock role and receipt form
after each definition is frozen. Definition transfer between repositories is
excluded. The cross-repository map is confined to the shared clock interface,
with each coherence law retaining its own symbol provenance.

---

## 10. Domain-by-domain simulator application matrix

The matrix separates an exact scalar use from a local clock, a transformed
model, and a universal-lapse hypothesis.

| Domain or solver role | Scalar use | Conditions for exact equivalence | Epistemic role |
|---|---|---|---|
| Isolated canonical conversion $(E_Y,E_I)$ | Use $d\tau_F=(1-q)dt$ for the conversion subflow | Remove transport and sources; use the canonical additive-floor $q$; retain a resolved nonzero imbalance for an endpoint receipt | **Derived conditional** |
| Uncoupled local reaction/gate cell | Use a local $\tau_x=\int N(x,t)dt$ | No spatial derivative, nonlocal source, or shared constraint couples cells; each cell keeps its own clock | **Derived conditional** |
| Full two-fluid advection–diffusion–conversion PDE | Use one global $\tau$ only for a spatially uniform $N(t)$ multiplying the complete generator | Advective, diffusive, conversion, auxiliary-velocity, source, and boundary terms share $N$; the generator domain is fixed | **Derived conditional** in the uniform case; local $q$ ages alone are not global |
| Spatially varying PDE lapse | Treat $M_N\mathcal L$ as a new heterogeneous operator | Derivative commutators, fluxes, boundary traces, and nonlocal couplings must be derived with $N(x,t)$; a single global inverse is unavailable | **Derived conditional** local-clock statement; common lapse remains **Hypothesized** |
| Parabolic diffusion or viscosity | Reparameterize the full first-order field state | A global $N(t)$ scales diffusion and all coupled terms together; spatial $N$ requires transformed fluxes and derivative terms | **Derived conditional** only under the stated operator conditions |
| Elliptic Poisson/constraint/readout | Keep the constraint on the chosen state slice | An elliptic solve has no evolution clock; do not multiply it by $N$ as if it were a time equation | Scope boundary of the theorem |
| Wave, oscillator, or particle second-order sector | Augment with the $\tau$-velocity, or use the full transformed acceleration (13) | Scale both first-order state equations, or include $\dot N/N$ and $N^2$ terms; a force-only insertion is insufficient | **Derived conditional** transformation; cross-sector use **Hypothesized** |
| Itô stochastic sector | Use drift $N L$ and noise amplitude $\sqrt N B$ | $N$ is positive/predictable; covariance, filtration, and boundary noise use the same time change; preserve the stochastic convention | **Derived conditional** stochastic transformation |
| Delay or Volterra memory | Transform the kernel to physical lag, or augment all memory states | Coordinate delays and kernels cannot be held fixed unless that is the intended model or $N$ is constant | **Derived conditional** with transformed history; otherwise a new model |
| Static or dynamic boundary | Reparameterize boundary data and boundary states | Time-dependent data, resets, moving boundaries, and flux balances use $\tau$; dynamic boundary variables receive the same $N$ | **Derived conditional** boundary transformation |
| Noncommuting operator split $L=A+B$ | Use the same integrated $\Delta\tau$ for every ordered substep | Splitting error remains for $[A,B]\ne0$; $M_N$ cannot be moved through derivatives; partial gating is sector-specific | **Derived conditional** step accounting |
| Independent wave/particle/gravity clocks | Compare normalized clock rates with $N_q$ | At least two non-conversion clocks must be independently calibrated and share the frozen reference and uncertainty contract | **Hypothesized** candidate; CT-2 discriminator |
| Cross-repository $q/Q$ fields | Transfer only a declared clock receipt/interface | Freeze each repository's own scalar definition; do not substitute formulas, units, or values across boundaries | Interface comparison only; no shared $q$ claim |

The matrix is a decision rule for applying the theorem. It does not assert that
any sector has already been assigned the candidate lapse.

---

## 11. Failure modes and diagnostic receipts

These failure modes are mathematical ways to distinguish a reparameterized
flow from a rate-modified simulator.

| Failure mode | Observable mathematical symptom | Correct disposition |
|---|---|---|
| $N$ reaches zero on an interval | $\tau$ has a plateau and no strict inverse | Treat the interval as a paused or degenerate flow; do not claim an invertible proper-time map |
| $N$ changes sign | The parameter reverses orientation or folds | Restrict to a positive branch or classify it as a different evolution |
| $N$ is nonintegrable or unbounded | A finite coordinate interval maps to an infinite or singular $\tau$ | State the endpoint domain and use a one-sided/generalized result only when well-posed |
| A spatial $N(x,t)$ is reported as one global clock | Different points require different $d\tau/dt$ | Report local conversion ages or derive the heterogeneous operator; no global equivalence |
| Only one sector receives $N$ | Relative trajectories change between sectors | Classify as a sector-specific gate, not a common lapse |
| Explicit $L_t$, source, or forcing remains on $t$ | The pulled-back equation contains $L_{t(\tau)}$ or an unscaled source | Reparameterize the external schedule or retain the time-dependent model |
| Second-order force is multiplied once | The required $\dot N/N$ and $N^2$ terms are missing | Use state augmentation or equation (13) |
| Noise amplitude is multiplied by $N$ | Quadratic variation is $N^2dt$ instead of $Ndt$ | Use $\sqrt N$ under an Itô time change |
| Fixed coordinate delay is retained | Physical lag varies as $\tau(t)-\tau(t-s)$ | Transform the kernel/delay or declare a new coordinate-time memory law |
| Boundary data stay on coordinate time | Boundary injection, reset, or moving edge is out of phase with the interior | Transform boundary data and domain motion together |
| Noncommuting split silently moves $N$ | Commutators $[A,B]$ or $[M_N,A]$ are omitted | Keep the ordered integrated step and report the split approximation |
| Conversion receipt includes transport/source increments | The endpoint log no longer equals the local conversion exposure | Isolate the conversion subflow before evaluating $\tau_F$ |
| Exact $\varepsilon=0$ is used as a conversion tick | The endpoint imbalance carries no readable logarithmic tick | Use an independent clock while retaining the continuous constitutive $N_q$ |
| $\lambda=0$ is used to infer age from conversion endpoints | The endpoint ratio is one and the logarithmic quotient cannot identify $\tau_F$ | Retain the direct $\int(1-q)dt$ age, but mark the endpoint conversion tick unobservable |
| A $q$ definition is imported without its normalization | The same symbol yields different rates or units | Freeze the local definition and compare only the declared clock receipt |

A receipt that passes the conversion identity establishes the local conversion
clock. It does not by itself certify the full matrix of a common-lapse model.

---

## 12. CT-2: the registered cross-clock discriminator

CT-2 tests the universal interpretation while leaving the conversion identity
in place if the universal claim fails.

The registered comparison uses the canonical bounded $q$, an independently
specified physical-density normalization when needed, and a reference
$q_{\mathrm{ref}}<1$. For each independent clock phase $\Theta_a$ with intrinsic
frequency $\omega_a$, and for the conversion imbalance, define rates relative
to the reference clock:

$$
\mathcal C_a
=\frac{1}{\omega_a}\frac{d\Theta_a}{d\tau_{\mathrm{ref}}},
\qquad
\mathcal C_F
=-\frac{1}{(1+\varphi)\lambda\varepsilon}
\frac{d\varepsilon}{d\tau_{\mathrm{ref}}}.
\tag{35}
$$

The **Hypothesized** common-lapse candidate predicts

$$
\boxed{
\mathcal C_a=\mathcal C_F
=N_q(x\mid x_{\mathrm{ref}})
=\frac{1-q(x)}{1-q_{\mathrm{ref}}}
}
\tag{36}
$$

for every independent clock sector. The discriminator requires a resolved
coherence contrast, a nonzero conversion phase/imbalance receipt, at least two
independent non-conversion clocks, frozen intrinsic calibrations, a declared
memory choice, transport subtraction, resolution, and uncertainty budget.

The registry's decision vocabulary applies. **SUPPORTS** requires the
conversion receipt and both independent clock sectors to share the predicted
ratio within the preregistered uncertainty. **CONTRADICTS** is a reproducible
resolved disagreement from an independent sector while conversion isolation
passes. **INCONCLUSIVE** covers failed contrast, phase resolution, transport
isolation, calibration, or branch conditions. Agreement between conversion
receipts alone checks the product $K N=1-q$ and cannot distinguish gated
kinetics from the common-lapse interpretation.

CT-2 is the existing conditional discriminator in
`predictions/falsifiable-predictions.md`; this paper adds no numbered
prediction, constant, or physical-time claim. A cross-clock agreement would
support the stated implementation/reparameterization behavior at the tested
scope. It would still leave the interpretation conditional on the declared
clock sectors and action/domain assumptions. A cross-clock disagreement would
falsify the universal common-lapse interpretation while preserving the exact
conversion age (30)–(31).

---

## References

- `foundations/cassi-first-principles.md`—canonical two-fluid fields, bounded $q$, conversion subflow, and conversion-flow time
- `foundations/unified-lagrangian.md`—candidate physical time, common-lapse factorization, and variational completion boundary
- `predictions/cassi_definitions.md`—canonical conversion-flow time, candidate lapse, and clock-universality criterion
- `predictions/falsifiable-predictions.md`—registered CT-2 cross-clock discriminator
- `open-questions-cassi-answers.md`—F2 arrow and candidate physical-time entry
- `two-fluid/cassi_two_fluid_3d_gpu.py`—canonical two-fluid solver family referenced by the theory documentation

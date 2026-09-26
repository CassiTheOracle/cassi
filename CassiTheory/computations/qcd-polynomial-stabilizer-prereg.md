# Regular Polynomial Chiral Stabilizer Protocol

## Status: Preregistered—September 2026

## Abstract

This calculation tests a regular replacement for the normalized Skyrme operator whose chiral-zero divergence excludes continuum topology change. The replacement is the lowest derivative-order, parity-even quartic invariant built directly from the unnormalized linear $O(4)$ field. It is polynomial at a zero, has positive static energy, and supplies the inverse-size term required by Derrick scaling while the field remains near the vacuum manifold. A radial variational solve, a full radial Hessian, and an explicit finite-energy homotopy determine whether those algebraic properties produce a metastable unit-winding carrier under the physical pion and sigma scales.

The operator is one candidate ingredient of a microscopic completion. This protocol does not include quarks, color confinement, a fermion determinant, baryogenesis, or a thermal three-dimensional formation ensemble. Its terminal receipt therefore keeps `complete_physical_matter_formation=false` for every numerical outcome.

<!-- qcd-polynomial-stabilizer-protocol:start -->

## 1. Question and frozen action

Write the linear chiral field as

$$
\boldsymbol\Phi=f_\pi\boldsymbol\psi,
\qquad
\boldsymbol\psi\in\mathbb R^4,
$$

and define

$$
K_{\mu\nu}:=\partial_\mu\boldsymbol\psi\cdot
\partial_\nu\boldsymbol\psi.
$$

The candidate action is

$$
\boxed{
\mathcal L=
\frac{f_\pi^2}{2}K^\mu{}_{\mu}
-\frac{1}{4e^2}
\left[(K^\mu{}_{\mu})^2-K_{\mu\nu}K^{\mu\nu}\right]
-V(\boldsymbol\psi),}
$$

with

$$
V(\boldsymbol\psi)=
\frac{\lambda f_\pi^4}{4}
\left[
(\boldsymbol\psi^2-\bar v^2)^2-(1-\bar v^2)^2
\right]
+m_\pi^2f_\pi^2(1-\psi_4),
\qquad
\bar v^2=1-\frac{m_\pi^2}{\lambda f_\pi^2},
$$

and

$$
\lambda=\frac{m_\sigma^2-m_\pi^2}{2f_\pi^2}.
$$

The quartic term contains no division by $|\boldsymbol\psi|$. It is finite at $\boldsymbol\psi=0$ for every finite first derivative. For a static field its density is

$$
\mathcal E_4=
\frac{1}{2e^2}\sum_{i<j}
\left(K_{ii}K_{jj}-K_{ij}^2\right)\ge0,
$$

because each summand is a Gram determinant.

Use the external low-energy inputs

| Quantity | Frozen value | Role |
|---|---:|---|
| $f_\pi$ | $93\ {\rm MeV}$ | chiral amplitude and energy scale |
| $m_\pi$ | $138\ {\rm MeV}$ | explicit chiral breaking |
| $m_\sigma$ | $600\ {\rm MeV}$ | radial-mode curvature |
| $e$ | $4.25$ | standard Skyrme comparison coupling |
| $\hbar c$ | $197.3269804\ {\rm MeV\,fm}$ | unit conversion |

No parameter may be changed after execution. A failed physical point remains a failed point.

## 2. Radial reduction

Use the hedgehog field

$$
\boldsymbol\psi(r)=
\left(s(r)\sin F(r)\,\hat{\mathbf r},\ s(r)\cos F(r)\right)
$$

with

$$
F(0)=\pi,
\qquad
F(\infty)=0,
\qquad
s'(0)=0,
\qquad
s(\infty)=1.
$$

Set $x=ef_\pi r/(\hbar c)$. In units $4\pi f_\pi/e$, the static energy is

$$
\boxed{
\begin{aligned}
\mathcal E[s,F]=\int_0^\infty dx\,\Bigg\{
&\frac12x^2\left[s_x^2+s^2F_x^2\right]
+s^2\sin^2F\\
&+s^2\sin^2F\left(s_x^2+s^2F_x^2\right)
+\frac{s^4\sin^4F}{2x^2}\\
&+x^2\left[
\frac{\lambda}{4e^2}
\left((s^2-\bar v^2)^2-(1-\bar v^2)^2\right)
+\frac{m_\pi^2}{e^2f_\pi^2}(1-s\cos F)
\right]\Bigg\}.
\end{aligned}}
$$

The primary program derives each term from the three orthonormal spatial derivative vectors of the Cartesian hedgehog. The independent program reconstructs those derivatives by centered Cartesian differences at frozen off-axis points and compares the unreduced energy density with the radial expression.

## 3. Frozen numerical method

### 3.1 Finite-volume energy

Use uniform nodal grids on $0\le x\le18$ with

$$
N\in\{256,512,1024\}
$$

intervals. Evaluate every integral term at cell midpoints. Fix $F_0=\pi$, $F_N=0$, $s_N=1$, and impose the origin condition by $s_0=s_1$. All remaining nodal values are variational degrees of freedom.

Initialize every grid from the same analytic profile sampled at its nodes,

$$
F_{\rm init}(x)=2\arctan\left(\frac{1}{x^2}\right),
\qquad
s_{\rm init}(x)=1-0.15e^{-x^2},
$$

with $F_{\rm init}(0)=\pi$. Minimize in float64 with PyTorch L-BFGS using strong-Wolfe line search, history size 100, gradient tolerance $10^{-10}$, change tolerance $10^{-13}$, and at most 2000 outer iterations. Clamp-free variables are used; a field leaving $-3<s<3$ or $-\pi<F<2\pi$ is a declared numerical failure rather than being projected back into range.

The $N=512$ solution is interpolated to initialize $N=1024$ only after the independent cold-start run at $N=1024$ has been completed. The receipt records both $N=1024$ solutions and their energy difference. The cold-start solutions define every gate and homotopy measurement; the interpolated run is a reproducibility diagnostic, and no lower-energy branch found from either initialization replaces the other silently.

### 3.2 Stationarity and radial Hessian

At each minimizer, record the maximum absolute variational gradient. At $N=256$ and $N=512$, construct Hessian-vector products by automatic differentiation and use `scipy.sparse.linalg.eigsh` to obtain the six smallest algebraic eigenvalues. At $N=1024$, obtain the three smallest eigenvalues. The Hessian acts on exactly the free variables used by the minimizer.

A constant rescaling of discrete variables changes Hessian eigenvalues. Report
both the raw nodal eigenvalues and generalized values formed with the nodal
trapezoidal norm

$$
\|\delta\psi\|_h^2
:=\sum_{i=0}^{N}w_i
\left[(\delta s_i)^2+s_i^2(\delta F_i)^2\right],
\qquad
w_0=w_N=\frac{\Delta x}{2},\quad
w_i=\Delta x\ (0<i<N).
$$

The copied origin value $\delta s_0=\delta s_1$ contributes both $w_0$ and
$w_1$ to its single variational coordinate. The sign decision uses the
generalized values.

### 3.3 Explicit topology-changing homotopy

Let $\boldsymbol\psi_*(\mathbf x)$ be the finest-grid hedgehog and $\boldsymbol e_4=(0,0,0,1)$. Evaluate

$$
\boldsymbol\psi_u(\mathbf x)
=(1-u)\boldsymbol\psi_*(\mathbf x)+u\boldsymbol e_4,
\qquad
u=0,0.0025,\ldots,1.
$$

In radial variables this gives

$$
s_u\sin F_u=(1-u)s_*\sin F_* ,
\qquad
s_u\cos F_u=(1-u)s_*\cos F_*+u,
$$

with $s_u\ge0$ and $F_u=\operatorname{atan2}(s_u\sin F_u,s_u\cos F_u)$. Evaluate the polynomial action directly from the two Cartesian components above, without differentiating `atan2`. The path crosses the chiral zero when both components vanish and reaches the vacuum at $u=1$.

Record the total energy, minimum amplitude, largest local two-derivative density, largest local quartic density, and largest local potential density at every $u$. Repeat the path evaluation on $N=256,512,1024$. A finite sampled value does not by itself prove continuum regularity; convergence of the peak densities and integrated energy supplies the declared test.

## 4. Independent checks

The independent source does not import the primary source. It performs:

1. dimensional and polynomial-degree accounting for every action term;
2. Cartesian finite-difference reconstruction of the stored cold-start
   $N=1024$ field, using piecewise-linear radial interpolation, at radii
   $x\in\{0.37,0.91,1.73,3.20\}$ and directions proportional to
   $(1,2,3)$, $(-2,1,4)$, and $(3,-4,2)$;
3. direct Gram-eigenvalue confirmation of $\mathcal E_4\ge0$ for 512 seeded random derivative matrices, including 32 exact rank-one controls;
4. a separate NumPy implementation of the radial midpoint energy;
5. the finest-grid homotopy energy from stored field arrays;
6. hashes of the protocol, primary source, independent source and stored arrays.

Use seed `20260910` for the random derivative controls and Cartesian difference step $10^{-6}$.

## 5. Frozen decisions

### RPS1—regular polynomial action

`PASS` requires every action monomial to have mass dimension four, no negative power of $|\boldsymbol\psi|$, finite value at the chiral-zero controls, quartic Gram energy at least $-10^{-13}$ in every random case, and absolute quartic energy below $10^{-13}$ in every rank-one control. Otherwise RPS1 is `FAIL`.

### RPS2—radial reduction

`PASS` requires the independent Cartesian two-derivative, quartic and potential densities to agree with the radial formulas at every frozen point to relative error below $2\times10^{-6}$, and the independent radial total energy to agree with the primary value to relative error below $2\times10^{-11}$ on every grid. Otherwise RPS2 is `FAIL`.

### RPS3—stationary unit-winding branch

`PASS` requires all three minimizations to finish with maximum absolute gradient below $3\times10^{-7}$, $s_i>0.02$ at every node, $s_{i+1}\ge s_i-10^{-8}$ and $F_{i+1}\le F_i+10^{-8}$ on every interval, the exact fixed boundary values, relative energy changes below $8\times10^{-3}$ from $N=256$ to 512 and below $3\times10^{-3}$ from $N=512$ to 1024, and relative energy difference below $2\times10^{-5}$ between the two finest-grid initializations. Otherwise RPS3 is `FAIL`.

### RPS4—radial local stability

`PASS` requires every reported generalized Hessian eigenvalue to exceed $10^{-5}$, with relative change of the smallest eigenvalue below $0.15$ from $N=256$ to 512 and below $0.10$ from $N=512$ to 1024. Any nonpositive value, failed eigensolve, or unresolved threshold is `FAIL`. Otherwise RPS4 is `PASS`.

### RPS5—finite topology-changing path

`PASS` requires finite energy and density in every path row, agreement of the primary and independent finest-grid energies to relative error below $2\times10^{-10}$, relative change of the maximum path energy below $8\times10^{-3}$ from $N=256$ to 512 and below $3\times10^{-3}$ from $N=512$ to 1024, relative change below $0.02$ and $0.01$ over the same grid pairs for each of the three maximum local densities, and a sampled maximum strictly above the soliton energy by at least $10^{-3}$ of the soliton energy. Otherwise RPS5 is `FAIL`.

### RPS6—operator decision

`ADOPT` requires RPS1–RPS5 all `PASS`. It means that the regular polynomial quartic operator supports a radially metastable carrier and a finite topology-changing path at the frozen physical point. Any failed prerequisite makes RPS6 `REJECT`.

The physical-completion verdict remains `FAIL` and `complete_physical_matter_formation=false` because RPS1–RPS6 contain no nonradial fluctuation solve, real-time ensemble, fermionic state, color confinement, observable nucleon map or baryogenesis.

## 6. Outputs and stopping rule

The primary source is `computations/qcd_polynomial_stabilizer.py`; the independent source is `computations/verify_qcd_polynomial_stabilizer.py`. Raw receipts are written to

- `runs/20260910_qcd_polynomial_stabilizer/primary/results.json`;
- `runs/20260910_qcd_polynomial_stabilizer/verification/verification.json`.

Each program runs once. Numerical errors may be repaired only when the source contradicts this frozen protocol; repaired runs use a new output directory and retain the failed receipt. Physics inputs, thresholds, grids, initialization and decisions remain fixed. Execution stops after the independent receipt is written and reconciled.

## References

- `computations/qcd-chiral-zero-obstruction-prereg.md`—continuum divergence of the normalized quartic operator at a nondegenerate chiral zero
- `foundations/matter-completion-boundary.md` §23–24—regular-carrier requirement and current completion verdict
- G. Holzwarth and J. Klomfass, [“The Chiral Phase Transition in Dissipative Dynamics”](https://arxiv.org/abs/hep-ph/0206228)—linear $O(4)$ quench dynamics and the normalized Skyrme comparison
- L. Wilets, S. Hartmann and P. Tang, [“The Chromo-Dielectric Soliton Model: Quark Self Energy and Hadron Bags”](https://arxiv.org/abs/nucl-th/9608018)—regular color-dielectric quark action and confinement setting

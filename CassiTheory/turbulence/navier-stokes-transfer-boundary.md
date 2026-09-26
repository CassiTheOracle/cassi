# Navier–Stokes Transfer, Heat Corrections, and Coercivity

## Status: Derived identities and obstructions; conditional small-data estimates—September 2026

## Abstract

The original incompressible Navier–Stokes equation has an exact signed transfer budget for the positive critical norm $\|u\|_{\dot H^{1/2}}^2$. An auxiliary heat-semigroup functional converts its cubic production into a boundary term and a quartic remainder. Standard multiplier and Sobolev estimates bound both terms, with closure in the small-critical-data regime. An explicit family of smooth periodic initial fields has unbounded critical norm on a single level set of the corrected energy. The quartic remainder has both signs, and a natural positive completion retains a higher-order transfer term. These statements delimit a specific scalar energy method. A positive Gaussian covariance representation connects the same critical norm to the stress-geometry analysis in `turbulence/navier-stokes-stress-geometry.md`.

## 1. Equation, domains, and conventions

A regularity argument must control concentration in the original fluid equation. Work with unforced incompressible Navier–Stokes,

$$
\partial_t u=\nu\Delta u+B(u,u),\qquad
B(u,u)=-\mathbb P[(u\cdot\nabla)u],\qquad \nabla\cdot u=0,
$$

where $\nu>0$ and $\mathbb P$ is the Leray projection. Identities below hold while the solution is smooth, on the mean-zero $2\pi$-periodic torus or on $\mathbb R^3$ with sufficient decay and integrability. Periodic brackets denote the volume-normalized spatial integral; Euclidean brackets denote the ordinary integral. Fourier normalization matches Parseval in each case.

Set $\Lambda=(-\Delta)^{1/2}$ and

$$
\mathcal C=\langle u,\Lambda u\rangle=\|u\|_{\dot H^{1/2}}^2,
\qquad Y=\|u\|_{\dot H^{3/2}}^2,
\qquad F(u)=\langle\Lambda u,B(u,u)\rangle.
$$

Then

$$
\boxed{\mathcal C'+2\nu Y=2F.}
$$

On $\mathbb R^3$, $u_\lambda(x,t)=\lambda u(\lambda x,\lambda^2t)$ preserves the equation and $\mathcal C$, while kinetic energy scales as $\lambda^{-1}$. This distinction explains why an energy bound alone leaves the critical norm uncontrolled.

The Cassi scale coordinate and internal currents in `foundations/interscale-current-soliton.md` require a separate constitutive map to spatial momentum. The equations here use the original Navier–Stokes velocity. Spectral curl polarizations are components of that velocity; an identification with Cassi's Yang/Yin density fields is absent.

## 2. Exact signed all-scale transfer

Energy transfer becomes a concentration budget when finer scales receive their critical weight. On the torus, define

$$
E_{>K}=\frac12\sum_{|k|>K}|u_k|^2,
\qquad
\Pi(K)=\operatorname{Re}\sum_{|k|>K}\overline{u_k}\cdot B_k.
$$

For each nonzero Fourier mode, $\int_0^\infty\mathbf1_{K<|k|}\,dK=|k|$. Consequently,

$$
\boxed{\mathcal C=2\int_0^\infty E_{>K}\,dK,
\qquad F=\int_0^\infty\Pi(K)\,dK.}
$$

The corresponding Euclidean formulas use Fourier integrals. Interchanges involving signed transfer require convergence; they are valid under the smoothness and decay assumptions stated in §1.

There is also an exact polarization representation. Let

$$
\mathbb P_\pm(k)=\frac12\left(\mathbb P(k)\pm\frac{i\,k\times}{|k|}\right),
\qquad u_\pm=\mathbb P_\pm u,\qquad \omega_\pm=\nabla\times u_\pm.
$$

Thus $\omega_+=\Lambda u_+$ and $\omega_-=-\Lambda u_-$. Using $B=\mathbb P(u\times\omega)$ and orthogonality of the two curl eigenspaces gives

$$
\boxed{F=2I,\qquad I=\langle u\cdot(\omega_-\times\omega_+)\rangle,}
$$

and hence $\mathcal C'+2\nu Y=4I$. The ordinary signed helicity is the difference of the two positive contributions to $\mathcal C$. The original nonlinear dynamics can exchange energy between both polarizations.

## 3. A cubic heat correction

An auxiliary heat evolution defines a functional of the current velocity without changing its Navier–Stokes evolution. Define

$$
\Phi(u)=\int_0^\infty F(e^{\nu s\Delta}u)\,ds.
$$

A shift of the integration variable gives

$$
\Phi(e^{\nu h\Delta}u)=\int_h^\infty F(e^{\nu s\Delta}u)\,ds,
\qquad D\Phi(u)[\nu\Delta u]=-F(u).
$$

The functional is cubic. Along the full equation, with $R(u)=D\Phi(u)[B(u,u)]$,

$$
\frac{d\Phi}{dt}=-F+R,
\qquad
\boxed{(\mathcal C+2\Phi)'+2\nu Y=2R.}
$$

Equivalently,

$$
\int_0^t F(u(s))\,ds
=\Phi(u_0)-\Phi(u(t))+\int_0^t R(u(s))\,ds.
$$

### 3.1 The sum divisor

The cubic Fourier interaction with output $a=p+q$ contains the heat factor

$$
e^{-\nu s(|a|^2+|p|^2+|q|^2)}.
$$

Complex conjugation of one coefficient leaves its real heat decay unchanged. Integration produces the positive sum divisor $\nu(|a|^2+|p|^2+|q|^2)$. A quadratic interaction representation for the velocity instead produces the difference $\nu(|p|^2+|q|^2-|a|^2)=-2\nu p\cdot q$.

For $p=(1,0,0)$ and $q=(0,2,0)$ these are $10\nu$ and zero respectively. The cubic functional has no right-angle divisor singularity.

### 3.2 Estimates and their scope

The standard critical trilinear estimate gives

$$
|F(v)|\le K\|v\|_{\dot H^{1/2}}\|v\|_{\dot H^{3/2}}^2.
$$

Heat contractivity and the exact integrated heat dissipation then imply

$$
\boxed{|\Phi(u)|\le\frac{K_0}{\nu}\mathcal C^{3/2}.}
$$

The variational derivative of $\Phi$ is an order-zero bilinear multiplier. Its symbols contain factors of the form

$$
\frac{|a|q_j}{D},\qquad D=|a|^2+|p|^2+|q|^2,\qquad a=p+q.
$$

The angular nonsmoothness can be isolated:

$$
\frac{|a|q_j}{D}
=\sum_m\frac{a_m}{|a|}\frac{a_mq_j}{D}.
$$

The first factor is a Riesz transform on the relevant input or output. The second is a smooth degree-zero bilinear symbol away from the joint origin. The other differentiated slots have the same factorization after relabeling frequencies. Standard nonendpoint Coifman–Meyer and Riesz-transform estimates give

$$
\left\|\frac{\delta\Phi}{\delta u}\right\|_3
\le\frac{K}{\nu}\|u\|_6^2.
$$

The Leray projection is bounded on $L^{3/2}$, so Hölder and Sobolev inequalities yield

$$
|R|\le\frac{K}{\nu}\|u\|_6^3\|\nabla u\|_2
\le\frac{K_1}{\nu}\|\nabla u\|_2^4
\le\frac{K_1}{\nu}\mathcal C Y.
$$

The last inequality follows by Fourier Cauchy–Schwarz:
$\|\nabla u\|_2^2\le\mathcal C^{1/2}Y^{1/2}$.
The multiplier estimates apply on $\mathbb R^3$; their periodic counterparts give the mean-zero fixed-torus statement. Constants depend on the stated normalization and domain, with no Fourier-cutoff dependence.

If $\sqrt{\mathcal C}/\nu$ is sufficiently small, $\mathcal C+2\Phi$ is comparable to $\mathcal C$ and viscosity absorbs the quartic bound. A standard continuity argument closes the small-critical-data regime. These estimates leave both steps unavailable for general large data.

## 4. An unbounded corrected-energy level set

A corrected quantity can remain fixed while the positive concentration norm grows without bound. Consider the real periodic field with positive Fourier modes

$$
u_p=i(0,1,1),\quad p=(1,0,0),\qquad
u_q=i(1,0,0),\quad q=(0,2,0),
$$

$$
u_k=i(-2,1,0),\quad k=(1,2,0),\qquad
u_r=i(1,0,0),\quad r=(0,0,3),
$$

where the symbols $u_p,u_q,u_k,u_r$ denote velocity coefficients, and negative modes are their conjugates. The field is smooth, divergence-free, odd under $x\mapsto-x$, and depends on all three coordinates. Direct convolution gives

$$
\mathcal C_0=14+10\sqrt5,\qquad F_0=14-6\sqrt5>0,
\qquad \Phi_0=\frac{F_0}{10\nu}.
$$

Change only the $k$ coefficient by a unit complex multiplier $a+ib$, $a^2+b^2=1$, and change its conjugate accordingly. Modal energies and the full energy/helicity spectra stay fixed; the interaction gives

$$
\mathcal C=\mathcal C_0,\qquad F=aF_0,\qquad \Phi=a\Phi_0.
$$

For amplitude $A$, choose

$$
a=-\frac{5\nu\mathcal C_0}{AF_0},\qquad
b=\sqrt{1-a^2},\qquad A\ge(155+70\sqrt5)\nu.
$$

This produces

$$
\boxed{\mathcal C(Au)+2\Phi(Au)=0,
\qquad\mathcal C(Au)=A^2(14+10\sqrt5)\longrightarrow\infty.}
$$

Therefore no finite-valued function of $\mathcal C+2\Phi$ alone uniformly bounds $\mathcal C$ over these smooth admissible data. The family varies initial data and supplies no finite-time singular solution. Additional information, such as an independently controlled energy, geometry, or second functional, is outside this single-scalar obstruction.

## 5. Quartic signs and positive completion

The quartic term retains both production and depletion. The full convolution on the three-coordinate fixture in §4 gives positive $R$. The planar two-mode field with $u_p=i(0,1,0)$, $u_q=i(1,0,0)$ gives negative $R$. Initially absent modes contribute to $D\Phi[B]$ and must be retained even though their current velocity coefficients vanish. The verifier prints both exact remainders and separates the generated-mode contribution.

A positive completion can restore coercivity. Let

$$
\mathcal E_\alpha=\mathcal C+2\Phi+
\frac{\alpha}{\nu^2}\mathcal C^2.
$$

The bound in §3.2 ensures $\mathcal E_\alpha\ge\mathcal C/2$ when, for example, $\alpha\ge2K_0^2$. Its exact evolution is

$$
\boxed{\mathcal E_\alpha'
=-2\nu Y-\frac{4\alpha}{\nu}\mathcal C Y
+2R+\frac{4\alpha}{\nu^2}\mathcal C F.}
$$

The final term is quintic in velocity amplitude and has the sign of $F$. A positive functional therefore still requires an independently closed dynamic estimate. The unbounded-level-set result in §4 applies to scalar functions of $\mathcal C+2\Phi$ alone; it places no such exclusion on every higher-order or nonperturbative completion.

## 6. Phase organization and continuum limits

The equation preserves odd velocity symmetry, $u(-x,t)=-u(x,t)$, while a smooth solution exists, by parity invariance and uniqueness. In a fixed Cartesian Fourier frame this means purely imaginary coefficients. It permits changing polarization directions and helical scalar phases.

The three-coordinate fixture has positive instantaneous $F$ within this symmetry class. At amplitude $400$ and $\nu=1$, its full $\mathcal C'$ is positive even with viscosity included. Thus persistent Cartesian phase symmetry is compatible with instantaneous concentration transfer. This establishes no persistent positive growth or blow-up trajectory.

Common uniform advection also leaves a triad's relative phase unchanged, because $a\cdot V-p\cdot V-q\cdot V=0$ when $a=p+q$. Diffusive decay has real rates. A proposed universal dephasing mechanism needs an additional dynamic argument.

Under the Euclidean Navier–Stokes scaling, $\mathcal C$ and $\Phi$ are invariant, whereas $F$, $Y$, and $R$ scale as $\lambda^2$. This agreement makes the identities scale-consistent. It supplies no large-data estimate beyond §3.2.

## 7. Positive covariance representation

A Gaussian covariance provides a positive geometric representation of the critical norm. With $\widehat{\bar u_\ell}(k)=e^{-\ell^2|k|^2/2}\hat u(k)$, set

$$
\tau_\ell=\overline{u\otimes u}_\ell-
\bar u_\ell\otimes\bar u_\ell.
$$

Positivity of the kernel makes $\tau_\ell$ positive semidefinite. Parseval gives

$$
\langle\operatorname{tr}\tau_\ell\rangle
=\sum_k(1-e^{-\ell^2|k|^2})|u_k|^2.
$$

Integration by parts yields

$$
\int_0^\infty\frac{1-e^{-\ell^2r^2}}{\ell^2}\,d\ell
=\sqrt\pi\,r\qquad(r>0).
$$

Tonelli's theorem therefore gives

$$
\boxed{\mathcal C=\frac1{\sqrt\pi}\int_0^\infty
\ell^{-2}\langle\operatorname{tr}\tau_\ell\rangle\,d\ell.}
$$

The same result holds on $\mathbb R^3$ with the corresponding Fourier integral. Let $\Pi_\ell=-\bar S_\ell:\tau_\ell$ and
$D_\ell=\|\nabla u\|_2^2-\|\nabla\bar u_\ell\|_2^2$.
Subtracting the resolved energy balance from the full balance gives

$$
\frac{d}{dt}\langle\operatorname{tr}\tau_\ell\rangle
+2\nu D_\ell=2\langle\Pi_\ell\rangle.
$$

Consequently,

$$
F=\frac1{\sqrt\pi}\int_0^\infty\ell^{-2}
\langle\Pi_\ell\rangle\,d\ell,
\qquad
Y=\frac1{\sqrt\pi}\int_0^\infty\ell^{-2}D_\ell\,d\ell.
$$

This gives the stress-geometry route a positive concentration quantity and an exact signed production term. The missing result is a data-controlled dynamic estimate for that term, developed explicitly as a proof obligation in `turbulence/navier-stokes-stress-geometry.md`.

## 8. Reproducible verification and claim boundary

`computations/verify_navier_stokes_transfer.py` implements full finite Fourier convolution, helical projections, the heat divisor, all differentiated cubic slots, and the fixed initial-data controls. Run it from the CassiTheory directory:

```
python computations/verify_navier_stokes_transfer.py
```

The fixed fixtures, thresholds, decision tree and evidence paths are specified in `computations/navier_stokes_stress_geometry_prereg.md`. The raw receipt is `runs/navier_stokes_transfer/verification.json`, a generated ignored artifact containing script/protocol hashes and exact expressions.

All 48 exact checks pass. At $\nu=1$, the three-coordinate fixture has $R\approx3.45309672470702$, with $2.26582101680676$ contributed by directional modes absent from the initial field. The planar value is $6(-7+3\sqrt5)/25\approx-0.0700310562001514$. The full three-coordinate nonlinear convolution contains 20 nonzero modes, including 14 absent from the initial support. An independent numerical reconstruction extracts the linear coefficient of the cubic polynomial $\Phi(u+tB)$ and agrees with these values.

The accepted script SHA-256 is `a7ca230b989f5713cb511b18971007d41cbdad20d9c8cf8e2af7d34f107755e0`; the protocol SHA-256 is `0c56f063a75a13b1b9e497963f694b1138ea1a3641f1a854c167ce8c472eaf62`. The raw receipt stores the exact radical expressions and every verification check.

Symbolic computation verifies the algebra and explicit witnesses. The infinite-dimensional estimates in §3.2 rest on the multiplier and Sobolev arguments stated there. The standing mathematical conclusions are the exact transfer identities, a small-data closure, and the noncoercive level set. Arbitrary-data regularity for the original three-dimensional Navier–Stokes equation remains unresolved.

## References

- `turbulence/navier-stokes-stress-geometry.md`—exact stress evolution, helical covariance assumptions and geometric proof obligations.
- `computations/navier_stokes_stress_geometry_prereg.md`—fixed analytical controls and numerical-quality decisions.
- `computations/verify_navier_stokes_transfer.py`—reproducible full-convolution verification.
- `foundations/interscale-current-soliton.md`, §12—conditional surrounding-state response and causal memory.
- `foundations/interscale-stress-attenuation-boundary.md`, §1—density current, gauge current and spatial momentum-flux distinctions.
- Eyink and Aluie, [Localness of energy cascade in hydrodynamic turbulence. I. Smooth coarse-graining](https://arxiv.org/abs/0909.2386), *Physics of Fluids* 21, 115107 (2009)—filtered energy budgets and conditional scale locality.
- Biferale and Titi, [On the global regularity of a helical-decimated version of the 3D Navier–Stokes equations](https://arxiv.org/abs/1303.1215)—the positive-helicity critical norm in a projected model with one retained handedness.
- L. Grafakos, [Multilinear Calderón–Zygmund Singular Integrals](https://grafakos.missouri.edu/preprints/GrafakosCRM.pdf), Theorems 7 and 9—nonendpoint bilinear Coifman–Meyer estimates; *Classical Fourier Analysis*, third edition, Springer (2014)—Riesz-transform and Sobolev estimates.
- Fefferman, [Existence and smoothness of the Navier–Stokes equation](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf)—official domain, data and regularity problem.

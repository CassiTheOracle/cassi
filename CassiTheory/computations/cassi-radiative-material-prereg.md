# Cassi Radiative Material Closure: Fixed LTE and Transport Controls

## Status: Preregistered—September 2026

## Abstract

This schedule verifies a selected radiative extension of the constant-density Cassi capillary and thermal fluid. Established photon transport supplies the Planck spectrum, Kirchhoff emission, absorption, elastic scattering and radiation moments. The M1 pressure tensor is a constitutive angular closure. The calculation checks emissive power, transfer through a homogeneous slab, moment realizability, conservative matter–radiation relaxation, entropy production and the optically thick diffusion limit. It does not derive photons, opacity, a physical density, a temperature scale or an electromagnetic current from the canonical Yang/Yin densities. No CassiCosmos renderer or dynamics source is changed by this calculation.

## 1. Fixed equations and conventions

Use the physical light speed $c_\gamma$ to distinguish it from the material composition fraction $c$. The monochromatic specific intensity $I_\nu(t,x,n)$ obeys, in the local material rest frame,

$$
\frac{1}{c_\gamma}\partial_t I_\nu+n\cdot\nabla I_\nu
=\alpha_\nu^{\rm a}[B_\nu(T)-I_\nu]
+\alpha_\nu^{\rm s}\left[\int_{4\pi}p_\nu(n,n')I_\nu(n')\,d\Omega'-I_\nu(n)\right],
$$

where $\alpha_\nu^{\rm a},\alpha_\nu^{\rm s}\geq0$ have units of inverse length and $\int p_\nu(n,n')\,d\Omega=1$. The LTE Planck function and Kirchhoff emissivity are

$$
B_\nu(T)=\frac{2h\nu^3}{c_\gamma^2}\frac{1}{\exp[h\nu/(k_BT)]-1},
\qquad j_\nu^{\rm a}=\alpha_\nu^{\rm a}B_\nu(T).
$$

For a gray absorption coefficient, the angle- and frequency-integrated emitted power per volume is

$$
4\pi\alpha^{\rm a}\int_0^\infty B_\nu\,d\nu
=4\alpha^{\rm a}\sigma_{\rm SB}T^4
=c_\gamma\alpha^{\rm a}a_{\rm R}T^4,
\qquad a_{\rm R}=\frac{4\sigma_{\rm SB}}{c_\gamma}.
$$

For frequency group $g$ define

$$
E_g=\frac1{c_\gamma}\int_g\!\int I_\nu\,d\Omega d\nu,
\quad F_g=\int_g\!\int nI_\nu\,d\Omega d\nu,
\quad P_g=\frac1{c_\gamma}\int_g\!\int n\otimes n I_\nu\,d\Omega d\nu,
$$

and

$$
E_g^{\rm LTE}(T)=\frac{4\pi}{c_\gamma}\int_g B_\nu(T)\,d\nu.
$$

With groupwise coefficients, the rest-frame moments are

$$
\partial_tE_g+\nabla\cdot F_g
=c_\gamma\alpha_g^{\rm a}(E_g^{\rm LTE}-E_g),
$$

$$
\partial_tF_g+c_\gamma^2\nabla\cdot P_g
=-c_\gamma\alpha_g^{\rm tr}F_g,
\qquad
\alpha_g^{\rm tr}=\alpha_g^{\rm a}+\alpha_g^{\rm s}(1-\langle\cos\theta\rangle_g).
$$

The M1 closure is

$$
f_g=\frac{|F_g|}{c_\gamma E_g},\qquad
P_g=E_gD_g,
$$

$$
D_g=\frac{1-\chi_g}{2}\mathbf 1
+\frac{3\chi_g-1}{2}\hat F_g\otimes\hat F_g,
\qquad
\chi(f)=\frac{3+4f^2}{5+2\sqrt{4-3f^2}}.
$$

The admissible set is $E_g\geq0$ and $|F_g|\leq c_\gamma E_g$. At $F_g=0$, set $D_g=\mathbf1/3$. M1 is the selected angular closure; it does not resolve crossing beams.

For moving material, use metric signature $(-,+,+,+)$, four-velocity
$U^\mu U_\mu=-c_\gamma^2$ and projector
$h^\mu{}_\nu=\delta^\mu{}_\nu+U^\mu U_\nu/c_\gamma^2$. Decompose the
radiation stress tensor by

$$
\mathcal E_g=\frac{R_g^{\mu\nu}U_\mu U_\nu}{c_\gamma^2},
\qquad
\mathcal F_g^\mu=-h^\mu{}_\alpha R_g^{\alpha\beta}U_\beta.
$$

The selected covariant interaction source is

$$
\boxed{
\nabla_\mu R_g^{\mu\nu}=S_g^\nu,\qquad
S_g^\nu=
\alpha_g^{\rm a}(E_g^{\rm LTE}-\mathcal E_g)\frac{U^\nu}{c_\gamma}
-\alpha_g^{\rm tr}\frac{\mathcal F_g^\nu}{c_\gamma},\qquad
\nabla_\mu T_{\rm matter}^{\mu\nu}=-\sum_gS_g^\nu.}
$$

In the material rest frame this reduces to the two displayed moment sources.
Pairing the source with its exact negative conserves total four-momentum.
LTE isotropy, $\mathcal E_g=E_g^{\rm LTE}$ and
$\mathcal F_g^\mu=0$, makes the source vanish in every inertial frame.

For a stationary gray cell, couple radiation to thermal energy $C T$ by

$$
\dot E=c_\gamma\alpha^{\rm a}(a_{\rm R}T^4-E),
\qquad
C\dot T=c_\gamma\alpha^{\rm a}(E-a_{\rm R}T^4).
$$

This local source conserves $CT+E$. Write $E=a_{\rm R}T_r^4$. Its entropy production is

$$
\frac{d}{dt}\left[C\log(T/T_*)+\frac43a_{\rm R}T_r^3\right]
=c_\gamma\alpha^{\rm a}a_{\rm R}(T^4-T_r^4)
\left(\frac1{T_r}-\frac1T\right)\geq0.
$$

The monochromatic statement uses the photon occupation
$n_\nu=c_\gamma^2I_\nu/(2h\nu^3)$ and
$g(n)=\log[(1+n)/n]$. Absorption and emission give
$\dot n_\nu=c_\gamma\alpha_\nu^{\rm a}(n_{\nu,B}-n_\nu)$.
Combining photon entropy with the material heat change gives an integrand
proportional to

$$
(n_{\nu,B}-n_\nu)
\left[g(n_\nu)-g(n_{\nu,B})\right]\geq0,
\qquad
g'(n)=-\frac1{n(1+n)}<0.
$$

This is the spectral detailed-balance form underlying the gray identity.

The implementation source step uses backward Euler. With $\lambda=c_\gamma\alpha^{\rm a}\Delta t$,

$$
E^{n+1}=\frac{E^n+\lambda a_{\rm R}(T^{n+1})^4}{1+\lambda},
\qquad CT^{n+1}+E^{n+1}=CT^n+E^n.
$$

The scalar temperature residual is strictly increasing for $T\geq0$, so bisection on $[0,(CT^n+E^n)/C]$ selects its unique positive root. Elastic isotropic scattering leaves rest-frame $E$ unchanged and updates

$$
F^{n+1}=e^{-c_\gamma\alpha^{\rm tr}\Delta t}F^n,
\qquad
\Delta p_{\rm matter}=\frac{F^n-F^{n+1}}{c_\gamma^2}.
$$

For a homogeneous isothermal slab with optical depth $\tau=\alpha^{\rm a}\Delta s$,

$$
I_{\rm out}=I_{\rm in}e^{-\tau}+B_\nu(T)(1-e^{-\tau}).
$$

The optically thick isotropic limit has $P=E\mathbf1/3$ and

$$
F=-\frac{c_\gamma}{3\alpha^{\rm tr}}\nabla E.
$$

## 2. Fixed analytical controls

The verifier checks these identities before evolving any trajectory.

1. $\int_0^\infty x^3/(e^x-1)\,dx=\pi^4/15$, $a_{\rm R}=4\sigma_{\rm SB}/c_\gamma$, and the gray emissive-power identity above.
2. Kirchhoff equilibrium has zero net energy source at $E=a_{\rm R}T^4$.
3. The M1 formula gives $\chi(0)=1/3$, $\chi(1)=1$, $\operatorname{tr}D=1$, transverse eigenvalue $(1-\chi)/2\geq0$ and longitudinal eigenvalue $\chi\in[1/3,1]$.
4. The entropy factor equals
   $$
   (T-T_r)^2\frac{(T+T_r)(T^2+T_r^2)}{TT_r}\geq0.
   $$
5. The implicit temperature residual has derivative
   $$
   C+\frac{4\lambda a_{\rm R}T^3}{1+\lambda}>0.
   $$
6. Two consecutive homogeneous slabs compose to the single-slab solution at the summed optical depth. The zero-depth, source-free and opaque limits are checked separately.
7. The diffusion flux makes $c_\gamma^2\nabla\cdot P+c_\gamma\alpha^{\rm tr}F=0$ for a supplied constant gradient.
8. The photon occupation entropy integrand is nonnegative because $g(n)$ is strictly decreasing on $n>0$.
9. The covariant source is orthogonal-decomposed correctly, reduces to the stated energy and flux sources in the material rest frame, vanishes for a Lorentz-boosted isotropic LTE tensor and cancels exactly against the matter source.

Every symbolic equality must simplify to zero. Fixed floating-point identities use the tolerances in §4.

## 3. Fixed numerical controls

### 3.1 Physical Planck integral

Use CODATA constants exposed by `scipy.constants`. Integrate the dimensionless Planck kernel with adaptive quadrature over the fixed intervals

$$
[0,0.5],\ [0.5,1],\ [1,2],\ [2,4],\ [4,8],\ [8,16],\ [16,\infty).
$$

The intervals must sum to $\pi^4/15$. At $T\in\{100,3000,10^4\}\ {\rm K}$ and $\alpha^{\rm a}\in\{10^{-8},10^{-3},2\}\ {\rm m}^{-1}$, independently reconstruct the integrated emissive power and compare with $4\alpha^{\rm a}\sigma_{\rm SB}T^4$. These constants validate established radiation physics and are not Cassi parameter predictions.

### 3.2 M1 realizability

Evaluate 1001 equally spaced reduced fluxes on $[0,1]$ for each Cartesian direction and four fixed non-axis directions. Require finite symmetric pressure tensors, trace $E$, eigenvalues in $[0,E]$, $\chi\in[1/3,1]$, and endpoint agreement. Feed one inadmissible flux with $|F|>c_\gamma E$ and require rejection rather than clipping.

### 3.3 Slab transfer

Use every combination

$$
\tau\in\{0,10^{-10},10^{-4},0.1,1,10,80\},\quad
I_{\rm in}\in\{0,0.2,3\},\quad B\in\{0,0.7,4\}.
$$

Require finiteness, nonnegativity, containment between $I_{\rm in}$ and $B$, agreement with the direct exponential expression, and the semigroup identity for splits $0.37\tau$ and $0.63\tau$. The implementation must use a cancellation-safe evaluation of $1-e^{-\tau}$.

### 3.4 Matter–radiation exchange

Use dimensionless benchmark coefficients

$$
c_\gamma=3,\\qquad a_{\rm R}=1,
\qquad C=2,\qquad \alpha^{\rm a}=0.7,
\qquad \alpha^{\rm tr}=1.1.
$$

These are numerical controls without a physical Cassi calibration. Evolve the five initial states

$$
(T_0,E_0)\in\{(2,0.1),(0.5,8),(1.2,1.2^4\times1.001),(3,10^{-4}),(0.2,0.5)\}
$$

to time 2 with $\Delta t\in\{0.04,0.02,0.01\}$. Compare every endpoint with an independent DOP853 solution of the two-variable source ODE at relative and absolute tolerance $10^{-12}$. Require:

- finite $T,E>0$ at every stored step;
- total-energy drift at most $2\times10^{-12}$;
- entropy never decreases by more than $2\times10^{-12}$ between steps;
- the finest endpoint normalized error at most $5\times10^{-5}$;
- halving the step improves endpoint error by a factor of at least $1.7$ whenever the coarse error exceeds $10^{-8}$;
- the finest endpoint lies closer to the independently solved equilibrium than its initial state.

Add one stiff source step with $(T_0,E_0)=(3,10^{-8})$ and $c_\gamma\alpha^{\rm a}\Delta t=10^4$. It must remain positive, conserve energy to $2\times10^{-12}$ and increase entropy. Evolve the same state with the radiation source deleted from the material equation; the magnitude of its total-energy defect must exceed $10^{-3}$. This altered equation is a rejection control.

### 3.5 Scattering and diffusion

Use six fixed admissible flux vectors, including zero and a free-streaming boundary state. For $c_\gamma\alpha^{\rm tr}\Delta t\in\{0,10^{-6},0.1,1,100\}$, compare flux damping with the exponential solution, require continued realizability, and verify radiation-plus-material momentum conservation to $10^{-13}$. Check the diffusion residual for seven fixed gradients and $\alpha^{\rm tr}\in\{0.1,1,10\}$.

### 3.6 Covariant source

Use material velocities $v/c_\gamma\in\{0,0.01,0.1,0.3\}$ along four fixed
directions. Reconstruct $R^{\mu\nu}$ from admissible lab-frame M1 moments,
project $\mathcal E$ and $\mathcal F^\mu$, and require
$U_\mu\mathcal F^\mu=0$ to normalized tolerance $10^{-12}$. For each velocity,
construct the Lorentz-boosted isotropic LTE tensor

$$
R_{\rm LTE}^{\mu\nu}
=\frac{4E^{\rm LTE}}{3c_\gamma^2}U^\mu U^\nu
+\frac{E^{\rm LTE}}3g^{\mu\nu}
$$

and require its interaction source to vanish to normalized tolerance
$10^{-12}$. At rest, compare all source components with the energy and flux
moment equations. Pair every radiation source with its negative matter source
and require zero total four-force exactly.

## 4. Tolerances, decision and stopping rule

The Planck integral and group partition use relative or absolute tolerance $5\times10^{-11}$. Physical-constant identities use relative tolerance $5\times10^{-12}$. M1, slab, momentum and diffusion algebra use absolute or normalized tolerance $10^{-12}$ unless §3 states a tighter value. The trajectory rules are fixed in §3.4.

Every named check is unique. A nonfinite value, missing control, unexpected acceptance of an inadmissible state or failed tolerance makes the verification status `FAIL`. The scientific classification is **SUPPORTS** only for the displayed LTE emissivity, M1 realizability, covariant interaction source, static matter–radiation exchange, entropy and diffusion identities when all checks pass. A mismatch gives **CONTRADICTS**. Numerical ambiguity gives **INCONCLUSIVE**.

Physical Cassi matter, a Yang/Yin-to-temperature map, mass density, opacity tables, ionization, spectral lines, a moving-medium transport implementation and the electromagnetic current remain **UNESTABLISHED** regardless of the numerical result. No parameter may be tuned after execution. Run the frozen schedule once. An implementation defect may be repaired without changing equations, fixtures or tolerances, with the failed receipt retained at a separate path.

The verifier refuses an existing output, manifest or source-snapshot directory. It records strict JSON, source hashes and frozen source copies before scientific evaluation.

## 5. Evidence path

From the CassiTheory root, run:

```text
python computations/verify_cassi_radiative_material.py --output runs/cassi_radiative_material/verification.json
```

Generated evidence remains local and is indexed in `BROKEN_REFS.md`.

## References

- `turbulence/cassi-fluid-feasibility.md` §7—selected capillary and thermal material budget.
- `computations/cassi_fluid_thermodynamics.py`—existing constant-density material evolution.
- `computations/cassi_radiative_material.py`—selected radiation closure and local source implementation.
- `computations/verify_cassi_radiative_material.py`—fixed analytical and numerical controls.
- C. D. Levermore, [Relating Eddington factors to flux limiters](https://doi.org/10.1016/0022-4073(84)90112-2)—M1 Eddington closure.
- D. Mihalas and B. Weibel-Mihalas, *Foundations of Radiation Hydrodynamics*—transfer moments, material coupling and diffusion limits.
- S. Rosseland, [Note on the absorption of radiation within a star](https://academic.oup.com/mnras/article/84/7/525/975098)—optically thick diffusion mean.

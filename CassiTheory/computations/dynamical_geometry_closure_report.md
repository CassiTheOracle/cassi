# Yin–Yang–Qi Dynamical Geometry Closure Report

## Status: PASS—September 2026

## 1. Frozen Question

The preregistered DG1–DG7 closure asks whether the canonical Yin/Yang density conversion, positive Hermitian coherence fibre, conditional relative-$U(1)_Q$ frame, and endpoint/Wilson incidence can coexist as one explicit **open-system effective closure** while retaining their separate source status.

The closure combines exact analytic identities with a deterministic frozen witness. Universal claims below follow from the displayed factorization for arbitrary admissible states; the numerical receipt verifies the implementation at the preregistered states. Finite sampling is not used as a proof over the full state cone.

The protocol is `computations/dynamical_geometry_closure_prereg.md`. The executable is `computations/dynamical_geometry_closure_check.py`. The derivation is `foundations/yin-yang-qi-dynamical-geometry.md`.

## 2. First Execution

Run from the CassiTheory repository root:

```text
python computations/dynamical_geometry_closure_check.py
```

The first and only execution printed:

```text
YIN–YANG–QI DYNAMICAL GEOMETRY CLOSURE RECEIPT
phi=1.618033988749895 lambda=0.020000000000000
DG1: PASS — q_min=0.000000000000000e+00, q_max=8.726779962499650e-01, q_ref=8.726779962499650e-01, ref_error=0.000e+00
DG2: PASS — component_error=4.337e-19, hermiticity_error=0.000e+00, trace_error=4.337e-19, min_jump_rate=2.546440075000700e-03
DG3: PASS — covariance_error=5.439e-19
DG4: PASS — z_rate_error=0.000e+00, coherence_norm_rate_error=1.084e-19
DG5: PASS — max_finite_q=8.726779962499650e-01, frozen_d|c|2_dt=-5.718663214773172e-04, factor_controls=True
DG6: PASS — number_error=0.000e+00, local_charge_error=0.000e+00, edge_incidence_error=0.000e+00
DG7: PASS — lambda_zero_error=0.000e+00, diagonal_offdiag=0.000e+00, zero_t_current=0.000e+00, endpoint_residual=3.700e-01, particle_branch_imported=False
OVERALL: PASS
```

No gate, coefficient, state point, tolerance, or control changed after this execution. The checker is not rerun.

## 3. Analytic State-Cone Closure

### 3.1 Universal finite-state bound

For arbitrary finite $E_Y,E_I\ge0$,

$$
q
=
\frac{\rho^2}
{\rho^2+\varphi^{-2}+\varepsilon^2},
$$

so

$$
1-q
=
\frac{\varphi^{-2}+\varepsilon^2}
{\rho^2+\varphi^{-2}+\varepsilon^2}.
$$

The denominator is positive, the numerator of $q$ is nonnegative, and $\varphi^{-2}>0$. Therefore

$$
\boxed{0\le q<1}
$$

for every finite admissible density state. This proves the universal DG1 bound independently of the frozen witness.

### 3.2 Universal minimal-lift sign

For arbitrary admissible $c$, the declared lift gives

$$
\frac{d}{dt}|c|^2\bigg|_{\rm conv}
=
-\varphi^2\lambda(1-q)|c|^2.
$$

For arbitrary finite density, $\lambda>0$, and $c\ne0$, every factor on the right after the minus sign is strictly positive. Hence

$$
\boxed{
\frac{d}{dt}|c|^2\bigg|_{\rm conv}<0.}
$$

The product vanishes only when

$$
\lambda=0,
\qquad
c=0,
\qquad
\text{or}
\qquad
q=1.
$$

The canonical finite-state gate does not attain $q=1$. This proves the universal DG5 sign for the undriven homogeneous minimal lift. The frozen numerical point tests the implementation of the same factorization.

This result is scoped to the declared conversion lift. Coherent Hamiltonian torque, protected sectors, boundary or transport influx, a modified reservoir, and different off-diagonal lifts can change the transverse balance.

## 4. Gate Results

### DG1—Finite-State Qi Bound: PASS

The exact proof is §3.1. Every frozen witness also satisfies the bound. The vacuum gives $q=0$. At the reference $\varphi$ composition,

$$
q_{\rm ref}
=
\frac{\varphi^2}{3}
=0.8726779962499650,
$$

with zero floating-point residual against the frozen analytic value.

### DG2—Canonical Diagonal Reduction: PASS

Direct matrix evaluation of the nonlinear pointwise Lindblad-form vector field agrees with

$$
\dot E_Y=-\lambda(1-q)(E_Y-\varphi E_I),
$$

$$
\dot E_I=+\lambda(1-q)(E_Y-\varphi E_I),
$$

and

$$
\dot c=-\frac{\varphi^2}{2}\lambda(1-q)c.
$$

The maximum component residual is

$$
4.337\times10^{-19}.
$$

Hermiticity is exact at the reported precision, the maximum trace residual is $4.337\times10^{-19}$, and every frozen jump rate is nonnegative.

Because the rate depends on the state through $q$, the complete flow is nonlinear. At fixed $q$ the generator is linear GKSL. The state-dependent evolution follows the fixed-generator orbits under a nondecreasing conversion-time reparametrization and preserves the positive cone. The nonlinear map is not classified as a linear completely positive semigroup.

### DG3—Relative-Frame Covariance: PASS

The analytic jump phases cancel in each dissipator. The frozen covariance residual is

$$
5.439\times10^{-19}.
$$

The conversion vector field therefore obeys the declared constant relative-$U(1)_Q$ covariance identity.

### DG4—Bloch-Rate Reduction: PASS

The component algebra gives

$$
\dot z
=-\varphi^2\lambda(1-q)(z-\varphi^{-3})
$$

and

$$
\frac{d}{dt}|c|^2
=-\varphi^2\lambda(1-q)|c|^2.
$$

The frozen implementation errors are respectively zero and $1.084\times10^{-19}$.

### DG5—Finite-Density Coherence-Support Boundary: PASS

The exact sign proof is §3.2. The frozen nonzero-coherence witness gives

$$
\frac{d}{dt}|c|^2
=-5.718663214773172\times10^{-4}<0.
$$

The arbitrary-state factorization establishes the universal conclusion. The sampled value is an implementation witness.

### DG6—Integrated Endpoint and Charge Ledgers: PASS

The frozen endpoint-number incidence, local rail-endpoint relative-charge cancellation, and Wilson edge/vertex charge incidence each close with zero residual.

This gate integrates the registered orientations. The independent SF1–SF6 and IT1–IT6 receipts remain the detailed evidence for spatial endpoint flux and finite Wilson transport.

### DG7—Controls: PASS

The controls give:

- zero conversion vector field at $\lambda=0$;
- zero generated off-diagonal component on the canonical diagonal subcone;
- zero inter-vertex current at $t_\Upsilon=0$;
- nonzero endpoint residual $0.37$ when the rail source remains active and Wilson transport is disabled;
- no import from the separate local-$SU(2)_Q$ particle action.

## 5. Verdict

The frozen verdict is

$$
\boxed{\mathrm{PASS}.}
$$

The current Cassi sectors are compatible as an open-system effective closure:

1. the canonical scalar $q$ gates population conversion;
2. the nonlinear two-jump lift preserves the positive cone by conversion-time reparametrization and reproduces the canonical diagonal equations exactly;
3. constant relative-$U(1)_Q$ frame covariance holds;
4. the minimal lift damps undriven finite-density transverse coherence;
5. the declared rail, endpoint, and Wilson incidence closes number and relative-charge ledgers.

The result does not derive one microscopic action. It leaves open:

- the physical identity of transverse coherence;
- the reservoir producing the state-dependent rate and its noise;
- a coherence-support source;
- the total field-plus-reservoir Noether stress;
- geometry backreaction;
- physical scale normalization;
- a local scale-bulk endpoint mediator;
- an interface to the separate local-$SU(2)_Q$ fixed-charge particle branch;
- a qualified stationary matter solution and full stability spectrum.

## References

- `computations/dynamical_geometry_closure_prereg.md`—frozen DG1–DG7 criteria.
- `computations/dynamical_geometry_closure_check.py`—deterministic first-execution witness.
- `foundations/yin-yang-qi-dynamical-geometry.md`—integrated open-system derivation and arbitrary-state sign proof.
- `foundations/cassi-first-principles.md`—canonical density PDE and scalar Qi gate.
- `foundations/geometric-manifold-completion.md`—positive fibre and conditional graph geometry.
- `foundations/endpoint-link-and-localization-boundary.md`—endpoint and Wilson ledgers.

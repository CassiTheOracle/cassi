# String–Bubble Projective-Map Verification Pre-Registration

## Status: Pre-registration—August 2026

## Purpose

This computation checks the finite algebra used by
`foundations/string-bubble-projective-map.md`. It tests projective, affine,
fivefold, conversion-flow, and Berry-geometry identities. It supplies no
evidence that the complex phase, quadratic bubble shell, fivefold selector, or
surface flow is physically realized.

## Frozen inputs

- Golden ratio: $\varphi=(1+\sqrt5)/2$.
- Affine shell axes: $(a_x,a_y,a_z)=(3,2,5/4)$; any positive axes give the
  same normalized identities.
- Attractor latitude: $\vartheta_\varphi=\arccos(\varphi^{-3})$.
- Common-phase check: $\gamma=0.37$ radians.
- Conversion check: $\rho=1.7$, $\lambda=0.02$, with polar angles on both
  sides of $\vartheta_\varphi$.
- Double-precision absolute tolerance: $10^{-12}$.
- Standard-library Python only.

## Frozen gates

### SB1—Projective shell map

For a deterministic angle grid, the Bloch vector must have unit norm, the map
$\mathbf X=D\mathbf n$ must satisfy
$\mathbf X^T D^{-2}\mathbf X=1$, and multiplication of the complex pair by the
common phase $e^{i\gamma}$ must leave $\mathbf X$ unchanged. Every maximum
absolute residual must be at most $10^{-12}$.

### SB2—String orbit

The positive-root meridian transformed by
$G(\delta)=DR_z(\delta)D^{-1}$ must equal the direct shell parameterization
$D\mathbf n(\vartheta,\delta)$ on the deterministic angle grid. The maximum
component residual must be at most $10^{-12}$.

### SB3—Fivefold orbit

At $\vartheta_\varphi$, the normalized step-two/step-one chord ratio of the
$C_5$ orbit must equal $\varphi$. The two internal intersections on one
pentagram diagonal must divide it into fractions
$(\varphi^{-2},\varphi^{-3},\varphi^{-2})$. The same fractions must survive the
chosen affine shell map. Every maximum absolute residual must be at most
$10^{-12}$.

### SB4—Canonical meridional drift

For q-gated conversion-only dynamics, differentiating
$s=\cos\vartheta=(E_Y-E_I)/\rho$ directly must agree with

$$
\dot\vartheta
=\lambda(1-q)
\frac{\varphi^2\cos\vartheta-\varphi^{-1}}{\sin\vartheta}.
$$

The rate must point toward $\vartheta_\varphi$ on both sides and vanish there
to tolerance. The maximum formula residual must be at most $10^{-12}$.

### SB5—Projective connection

The normalized-spinor connection around the attractor latitude must satisfy

$$
\oint\mathcal A
=\pi(1-\varphi^{-3}),
\qquad
\Delta\Gamma_5=\frac{1}{5}\oint\mathcal A.
$$

A five-step sum must recover the loop value to $10^{-12}$. This is a generic
$\mathbb{CP}^1$ geometric identity evaluated on the selected latitude; it is
not a Cassi-specific holonomy discriminator.

## Decision and stopping rule

- **PASS:** SB1–SB5 all pass on the first completed execution.
- **FAIL:** any gate exceeds tolerance or violates its direction/sign
  condition.
- Execution stops after the first completed gate ledger. A source-code defect
  that prevents the frozen computation from running may be corrected without
  changing inputs, tolerances, equations, or decision rules; the correction
  must be reported with the result.

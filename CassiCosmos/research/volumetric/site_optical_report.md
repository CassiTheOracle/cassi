# Site-native optical integration — report

Date: 2026-08-17
Verdict: **SUPPORTS controlled analytic integration.**

`compute/cassi_voronoi_optical.glsl` consumes verified site sequences/boundary parameters, reconstructs EY/EI at each segment midpoint from the site values plus AREPO gradients, and integrates front-to-back emission and Beer–Lambert transmittance. Site positions use the same tile→world transform as traversal.

For a constant two-segment field with `rho=1`, total length 2, `sigma_abs=0.5`, and `sigma_fog=0.1`, the exact opacity is

```
alpha = 1 - exp[-(0.5*1 + 0.1)*2] = 0.69880579
```

GPU result:

```
PASS analytic transmittance got=0.69880581 expected=0.69880579
PASS finite nonnegative RGB [0.6502240,0.2118539,0.2118539]
RESULT: PASS (5 checks, 0 failures including load/pipeline)
```

This validates constant-field radiative transfer independently of topology. Linear-gradient exactness/convergence, live field ranges, palette parity, and temporal accumulation remain downstream gates.

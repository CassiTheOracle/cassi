# Second-Order Field Energy: Symbolic Substitution Recovery

## Status: Pre-registered—September 2026

## 1. Trigger

The first execution of `computations/verify_navier_stokes_second_order_field_energy.py` completed **77/78** checks. Check C04 retained a factor $1-\sigma^2$ after substituting $q=\sigma\omega$. The checker supplied $\sigma^2=1$ in the same SymPy substitution map as the component replacements, so the newly created powers of $\sigma$ were not reduced. The displayed failure is

$$
(1-\sigma^2)\,\omega\cdot S\omega.
$$

The same run passed the general tensor factorization in C03 and its independent pointwise NumPy reconstruction in E10. No coefficient, tolerance, mathematical target, or interpretation changes.

The retained failed receipt is
`runs/navier_stokes_second_order_field_energy/verification.initial-failed.json`, SHA-256
`fad2190b9d2cf1c522aef8da5a75b3080789c8964900366bf814a7e5f01c2d6e`.
The first-run verifier SHA-256 is
`7140ea8c07fe918f8550c6accc2e94f6c943c78a406cda700ce75d4039acae5c`.

## 2. Fixed implementation correction

Only C04 changes. The verifier must:

1. substitute $q_i=\sigma\omega_i$;
2. expand the resulting scalar expression;
3. substitute $\sigma^2=1$;
4. simplify and require exact zero.

The recovery adds this protocol to the source-hash inventory. Every other check, the fixed Fourier datum, the $2\times10^{-10}$ tolerances, the receipt schema, and the output path remain unchanged.

## 3. Decision rule

Run the corrected verifier once. All **78** original checks and the recovery source-presence check must pass. Success ends with `ALL CHECKS PASSED` and qualifies the classifications fixed in the parent protocol. Any remaining failure produces `FAIL—SECOND-ORDER FIELD ENERGY` and blocks integration.

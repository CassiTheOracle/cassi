# Dynamical Charged-Endpoint Response Outcome

## Status: FAIL—September 2026

## 1. Verdict

The frozen DR1–DR6 execution is an internally consistent check of its declared block matrix, but DR5 does not reproduce the quadratic Hessian of the registered endpoint action. The receipt therefore has verdict **FAIL** and none of its active-response claims are adopted.

The background-current identity, exact trilinear expansion, zero-background order, endpoint-curvature eigenvalues, and pole locations remain algebraically valid. The response sign and direct-elimination gate require a source-action calculation under a new preregistration.

## 2. Source-Action Failure

The rotating-frame endpoint action in
`foundations/endpoint-link-and-localization-boundary.md` contains the canonical temporal term, minus the endpoint energy, and plus the coherent link. With the frozen definition

$$
\mathcal D_v^R
=\mathcal H_v-\mathcal Z_v(\omega+i\gamma_v)\sigma_3,
$$

the quadratic action has the endpoint block

$$
-\frac12\Xi^\dagger\mathcal D_v^R\Xi,
$$

rather than the positive block used by the frozen DR5 elimination. Including the symmetrized mixed term gives

$$
Q_v^{(2),R}
=
\frac12\mathbb\Phi^\dagger\mathbb\Lambda_{0,v}\mathbb\Phi
-\frac12\Xi^\dagger\mathcal D_v^R\Xi
+\frac12\left(
\Xi^\dagger\mathcal C_v\mathbb\Phi
+\mathbb\Phi^\dagger\mathcal C_v^\dagger\Xi
\right).
$$

The endpoint equation is

$$
\Xi=(\mathcal D_v^R)^{-1}\mathcal C_v\mathbb\Phi,
$$

so source-action elimination gives

$$
\boxed{
\mathbb\Lambda_{\mathrm{action},v}^R
=
\mathbb\Lambda_{0,v}
+\mathcal C_v^\dagger
(\mathcal D_v^R)^{-1}
\mathcal C_v.}
$$

Equivalently, define the action kernel

$$
\mathcal K_v^R
:=
\mathcal Z_v(\omega+i\gamma_v)\sigma_3-
\mathcal H_v
=-\mathcal D_v^R.
$$

Then the same result takes the standard Schur form

$$
\boxed{
\mathbb\Lambda_{\mathrm{action},v}^R
=
\mathbb\Lambda_{0,v}
-\mathcal C_v^\dagger
(\mathcal K_v^R)^{-1}
\mathcal C_v.}
$$

The frozen checker instead combines the positive quadratic block
$+\frac12\Xi^\dagger\mathcal D_v^R\Xi$ with the latter minus-sign Schur complement. That block is not the Hessian of the registered action.

## 3. Gate Accounting

| Gate | Outcome |
|---|---|
| DR1 closed homogeneous current boundary | Algebraically valid |
| DR2 exact trilinear Hessian | Algebraically valid |
| DR3 zero-background quadratic boundary | Quartic order valid; the effective action sign requires the action kernel |
| DR4 endpoint stability and poles | Algebraically valid |
| DR5 Schur complement, covariance, and Nambu boundary | **FAIL**—the eliminated endpoint block has the wrong source-action sign |
| DR6 closed and open response classes | Matrix identities valid for the declared block; source-action response must use $\mathcal K_v^{R/A}$ |

The overall frozen verdict is **FAIL** because every gate is required to pass.

## 4. Required Follow-Up

A separate preregistration must freeze the source-action kernel
$\mathcal K_v^{R/A}$, direct elimination, zero-background action sign, pole
law, covariance law, and retarded/advanced relation before another execution.
The frozen preregistration and checker remain unchanged as the receipt for this
verdict.

## References

- `foundations/endpoint-link-and-localization-boundary.md`—registered charged-endpoint action
- `computations/endpoint_dynamical_response_prereg.md`—frozen DR1–DR6 protocol
- `computations/endpoint_dynamical_response_check.py`—frozen internal block-matrix receipt

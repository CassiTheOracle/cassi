# Phi Counterflow Selection Verification Report

## Status: Tested conditional—August 2026

## Scope

This report records the protocol-complete execution of the frozen PC1–PC7 gates
in `computations/phi-counterflow-selection-pre-registration.md`. The computation
checks the conditional chain

$$
E_Y/E_I\longrightarrow\varphi,
\qquad
J_Y+J_I=0,\ \mu_Y=\mu_I
\quad\Longrightarrow\quad
\theta_I'/\theta_Y'\longrightarrow\varphi,
$$

together with its exact transient, stability, controls, and compact Fibonacci
near-closures. The physical occurrence of the compact phases and current
closure lies outside the computation.

## Execution

From the CassiTheory repository root:

```text
python computations/verify_phi_counterflow_selection.py
```

The process exited with code 0.

The PC6 denominator and frozen-input list both set $E_{I,*}=1$, matching the
verifier normalization. The ledger below is the protocol-complete execution of
that fully specified construction.

## Gate ledger

| Gate | Result | Recorded diagnostic |
|------|--------|---------------------|
| PC1 | PASS | Maximum density-balance residual $0$ |
| PC2 | PASS | Maximum current and phase-ratio residual $0$ |
| PC3 | PASS | Exact-transient residual $4.441\times10^{-16}$; terminal $\varphi$ residual $6.843\times10^{-10}$; positivity and monotonicity satisfied |
| PC4 | PASS | Projective-flow residual $1.110\times10^{-16}$; stable eigenvalue $-0.183262$ |
| PC5 | PASS | $K=0$ residual $4.441\times10^{-16}$; finite-exposure residual $0.3326$; $K=50$ residual $2.220\times10^{-16}$ |
| PC6 | PASS | Mobility and through-current controls shift the fixed ratio as derived; maximum residual $1.665\times10^{-16}$ |
| PC7 | PASS | Fibonacci identity residual $1.017\times10^{-14}$; record denominators $1,2,3,5,8,13,21,34,55,89,144$ |

Verbatim terminal ledger:

```text
PC1: PASS — max residual=0.000e+00
PC2: PASS — max residual=0.000e+00
PC3: PASS — exact residual=4.441e-16; phi residual=6.843e-10; monotone=True; positive=True
PC4: PASS — max residual=1.110e-16; eigenvalue=-0.183262
PC5: PASS — K=0 residual=4.441e-16; K=0.4 residual=3.326e-01; K=50 residual=2.220e-16
PC6: PASS — mobility=(0.8090169943749475, 1.618033988749895, 2.750657780874821); through-current=(1.868033988749895, 1.618033988749895, 1.368033988749895); max residual=1.665e-16
PC7: PASS — identity residual=1.017e-14; record denominators=[1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]
VERDICT: PASS (7/7 gates)
```

## Verdict

**PASS.** The canonical homogeneous conversion law exponentially selects the
density ratio $E_Y/E_I\to\varphi$ when accumulated positive gate exposure
diverges. Equal-mobility, zero-net-current counterflow maps that density ratio
to the local continuum phase-gradient magnitude ratio. Finite compact windings
recover the Fibonacci record sequence of rational near-closures.

The controls establish the theorem's boundary. A mobility ratio
$m=\mu_Y/\mu_I$ moves the fixed phase ratio to $m\varphi$. A through-current
adds $-J_0/(\mu_IE_Ik_Y)$. Finite accumulated exposure retains a finite
initial-condition residual. Fixed winding sectors require phase slips or
another transition law to track the continuum target. These effects remain
part of any physical test.

## Epistemic boundary

The receipt verifies algebra and numerical implementation for the frozen
conditional model. The coefficient $\varphi$ remains the input to the
canonical conversion law; this computation transfers that target into the
phase sector. Physical adoption requires separate evidence for compact
Yang/Yin phases on a common ordinary loop, counteroriented currents, equal
effective mobility, vanishing net current in the selected sector, adiabatic
current adjustment, winding-sector dynamics, and the predicted phase-locking
or spectral-transfer response.

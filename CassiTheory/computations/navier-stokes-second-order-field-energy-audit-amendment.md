# Second-Order Field Energy: Independent Audit Amendment

## Status: Pre-registered—September 2026

## 1. Trigger and retained evidence

The independent audit of
`computations/navier-stokes-second-order-field-energy-prereg.md`,
`computations/verify_navier_stokes_second_order_field_energy.py`, and the
79/79 v1 receipt finds that the central mass-metric identity,
Navier–Stokes balance, residual factorization, interpolation estimate and
conditional continuation theorem are correct under their stated smooth
source-free assumptions. It also finds two qualifications and several
verification weaknesses that must be resolved before documentary integration.

The retained v1 receipt is
`runs/navier_stokes_second_order_field_energy/verification.json`, SHA-256
`5a1baee3e42995b778e1a6b4b118337284be9cd903ee1048e313b7c8bc011d7a`.
It records 79/79 checks with the source hashes current at that execution. The
receipt records hashes; the v1 verifier does not compare them with a frozen
expected manifest.

This amendment freezes the corrections below before the verifier is changed
or rerun. The v1 receipt and the retained 77/78 failure receipt remain
unchanged.

## 2. Dimensional gauge-map correction

The canonical source dimensions in
`foundations/particle-stationary-action-closure.md` are

$$
[A_i]=L^{-1},
\qquad
[A_0]=T^{-1},
\tag{SOA1}
$$

while a physical fluid velocity has $[u]=LT^{-1}$. Introduce a fixed positive
conversion coefficient

$$
A_i^a=\delta^{a3}\kappa_Au_i,
\qquad
[\kappa_A]=TL^{-2}.
\tag{SOA2}
$$

In temporal gauge,

$$
F_{ti}^3=\kappa_Au_{t,i},
\qquad
F_{ij}^3=\kappa_A(\partial_i u_j-\partial_j u_i).
\tag{SOA3}
$$

The normalized energy identity is therefore

$$
\boxed{
\frac{\mu_x}{\kappa_A^2}\mathcal H_A
=\frac12\left(
\|\omega\|_2^2+c_g^{-2}\|u_t\|_2^2
\right),
\qquad
c_g^{-2}=\epsilon_x\mu_x.}
\tag{SOA4}
$$

The source-free Gauss reduction additionally imposes

$$
q_\Psi^a=q_\Phi^a=0,
\qquad
(D_{\mathfrak s}F_{t\mathfrak s})^a=0.
\tag{SOA5}
$$

On the Abelian one-color slice, the surviving spatial term is
$\epsilon_x\kappa_A\nabla\cdot u_t$ and vanishes by differentiated
incompressibility. The gauge interpretation is conditional on (SOA2) and
(SOA5). The Navier–Stokes identity for $H_c$ is unchanged.

## 3. Scaling-domain qualification

The transformation

$$
u_\lambda(x,t)=\lambda u(\lambda x,\lambda^2t),
\qquad
c_\lambda=\lambda c
\tag{SOA6}
$$

produces

$$
g_{c_\lambda,\lambda}(x,t)
=\lambda^2g_c(\lambda x,\lambda^2t).
\tag{SOA7}
$$

With Lebesgue spatial norms on $\mathbb R^3$, or with an unnormalized norm and
simultaneously rescaled spatial domain,

$$
\|g_{c_\lambda,\lambda}\|_r
=\lambda^{2-3/r}\|g_c\|_r.
\tag{SOA8}
$$

The work is invariant exactly on

$$
\frac2p+\frac3r=2.
\tag{SOA9}
$$

The fixed volume-normalized $2\pi$ torus used by the theorem has no continuous
Navier–Stokes dilation symmetry. For integer $\lambda$, periodic repetition
on that fixed torus gives

$$
\|g_{c_\lambda,\lambda}\|_r
=\lambda^2\|g_c\|_r,
\tag{SOA10}
$$

and noninteger $\lambda$ need not preserve periodicity. Thus “critical” in the
torus theorem denotes the local $\mathbb R^3$/rescaled-domain dimensional
line (SOA9), not an exact symmetry of the fixed normalized torus.

## 4. Fixed verifier hardening

The corrected verifier keeps every mathematical target and every deterministic
Fourier input from the parent protocol. It writes a new receipt at
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.json`
with schema
`cassi.navier-stokes.second-order-field-energy.verification.v2`. It must not
overwrite either retained v1 receipt.

### 4.1 Source preflight and frozen manifest

The verifier performs source-existence checks before reading source text.
Missing sources produce named failed checks and a receipt instead of an
uncaught file-read exception.

The following expected SHA-256 values are frozen:

| Source | SHA-256 |
|---|---|
| Parent protocol | `de08fca92c0d4b84fb0cdfe8cc0008b22446255a7a89308baec4571097dc1b27` |
| Recovery protocol | `8b4e1ddbebe507c672aa02ec0a0463ce7e73f4b511508b41f648b2142a97bf1c` |
| Retained v1 receipt | `5a1baee3e42995b778e1a6b4b118337284be9cd903ee1048e313b7c8bc011d7a` |
| Yang/Yin scalar shader | `a6811a4967e1a7641905990ae28c0777e39bbe578d5559e37007f6f4ce7d632a` |
| Field-particle shader | `f0a12d0e1952215bbb1a71bdb95da35beed4548671085ca83d623a194c09a679` |
| Gauge-action source | `b15d6340cb8f15369f091d7ea5d5e70daad788f7953eb7917cd550554e56fe1a` |

The amendment itself is added to the frozen manifest after this file is
written and before verifier implementation. The verifier's own hash is
recorded in the v2 receipt and cannot be self-compared without a recursive
hash definition.

### 4.2 Live-source checks

Checks A18–A21 become declaration and executable-block checks:

1. A18 and A19 inspect the `pass_a` function body for the exact live
   acceleration assignments.
2. A20 parses `STATE_STRIDE = 18`, `AX0 = 9`, and executable connection
   accesses at `AX0`, `AX0 + 3`, and `AX0 + 6`.
3. A21 parses `VELOCITY_STRIDE = 16`, both velocity buffer declarations,
   the state/velocity component mapping, and executable loops over the full
   velocity stride.

Checks B06–B08 inspect the tagged PA11 and PA14 equation regions instead of
accepting a match anywhere in the document. New checks establish the PA13
connection dimensions, the $\kappa_A$ dimension conversion and the complete
source-free/scale-free Gauss reduction.

### 4.3 Mathematical checks

B03 is replaced by a nontrivial symbolic calculation: represent a smooth
velocity as the curl of a time-dependent vector potential, differentiate it
in time, and verify $\nabla\cdot u_t=0$ by commutation of mixed derivatives.
B04 checks (SOA4) with symbolic $\kappa_A$.

C14–C17 are relabeled as $\mathbb R^3$/rescaled-domain dimensional checks.
Two new checks verify the fixed normalized torus amplitude law (SOA10) and the
resulting nonzero $r=3$ work exponent.

## 5. Fixed check inventory and decision rule

The v2 verifier executes exactly **93 checks**:

- A01–A21: 21 scalar and live-runtime checks;
- B01–B11: 11 gauge-map, dimension and Gauss checks;
- C01–C19: 19 cancellation, interpolation and scaling checks;
- D01–D16: 16 exact heat-flow controls;
- E01–E11: 11 deterministic Fourier checks;
- F01–F08: 8 source-existence preflight checks;
- F09–F15: 7 frozen-source-hash checks.

Every check must pass. Success records `PASS—DERIVED CONDITIONAL`, prints
`ALL CHECKS PASSED`, and qualifies the result for documentary integration
with the unit and scaling-domain statements in §§2–3. Any failure records
`FAIL—SECOND-ORDER FIELD ENERGY AUDIT`, preserves the failure receipt, and
blocks integration.

## 6. Interpretation preserved by the amendment

The following results remain the mathematical output under the corrected
scope:

1. the source-free constant-coefficient Yang/Yin pair has a positive weighted
   Hamiltonian;
2. the dimensionally converted Abelian gauge energy is proportional to
   $H_{c_g}$ under the source-free and scale-free restrictions;
3. the original unforced Navier–Stokes evolution satisfies the time–curl
   cancellation identity;
4. finite critical residual work implies smooth continuation;
5. an arbitrary-data bound for that work remains unproved.

The amendment supplies no force, gauge equation, cutoff, constitutive term or
regularity assumption to Navier–Stokes.

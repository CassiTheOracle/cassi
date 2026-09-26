# Particle Stationary Precision Continuation Report

## Status: Tested—September 2026

## Abstract

This report records the deterministic higher-precision continuation frozen in
`computations/particle-stationary-precision-v5-prereg.md`. The sole input is the
selected `P:separated_core` finite-grid field. One strong-Wolfe L-BFGS block
reduces its independently recomputed physical first-variation RMS from
$1.936974511462459\times10^{-4}$ to
$5.471248126403572\times10^{-5}$ while preserving PA32 gates Q1–Q4. The cutoff
virial falls from $1.891010219094089\times10^{-3}$ to
$1.348199143828711\times10^{-4}$.

The primary and independent verifier return

$$
\boxed{\mathrm{PASS\text{—}HIGHER\text{-}PRECISION\ BACKGROUND}}.
$$

The selected endpoint supplies the registered background for the successor
PA42 physical-Hessian campaign. It establishes a more precise stationary point
inside one finite $C_4$-projected variational class. Localization, carrier
retention, domain and resolution convergence, unrestricted basin ordering, and
a continuum particle remain open.

## 1. Frozen question and input

The campaign asks whether the fixed input field reaches

$$
\|\delta\widehat E\|_{\mathrm{source,RMS}}
\le 1.20\times10^{-4}
$$

with Q1–Q4 all passing. The source is:

- artifact:
  `runs/20260902_particle_stationary_q2_recovery_v2/fields_P_separated_core.npz`;
- SHA-256:
  `99766cddb04107bb0c103c8f96254df651094054578867d37662ee7bff7e2550`;
- family: `P:separated_core`;
- grid: $(R,N,\Delta x,\Delta V)=(4,17,0.5,0.125)$;
- fixed charge: $q_C=4$;
- physical energy: $3.854200126928118$;
- physical-gradient RMS: $1.936974511462459\times10^{-4}$;
- cutoff virial: $1.891010219094089\times10^{-3}$;
- carrier multiplier: $\widehat\omega_C=0.9619135625713445$.

The coefficient point, charge, field class, grid, shell values, $C_4$
projection, finite-difference operator, quadrature, and optimizer family remain
fixed throughout the continuation.

### 1.1 Arithmetic audit of the acquisition diagnostic

The exact dimension factor quoted symbolically in HP2 is

$$
\sqrt{\frac{15^3\times17}{13622}}
=\sqrt{\frac{57375}{13622}}
=2.052300312622504.
$$

The printed decimal `2.052300119747167` in HP2 is a preregistration
transcription error. The corresponding product at the acquisition target is
$2.462760375147005\times10^{-4}$; HP3 prints
$2.462760143696600\times10^{-4}$. These decimals are explanatory diagnostics.
Neither driver reads them, and the campaign selects directly on the frozen
source-gradient threshold. The PA42 campaign independently compares its
measured augmented gradient with the direct $3\times10^{-4}$ H3 limit. The
hash-bound preregistration remains unchanged.

## 2. Frozen continuation

The primary driver allows at most eight fresh L-BFGS blocks and selects the
first endpoint that passes the precision target and Q1–Q4. Each block uses:

| Setting | Frozen value |
|---|---:|
| maximum iterations | 880 |
| maximum function evaluations | 1100 |
| history size | 20 |
| gradient tolerance | $10^{-10}$ |
| change tolerance | $10^{-12}$ |
| line search | strong Wolfe |
| arithmetic | `float64` |
| deterministic algorithms | enabled |

The selected endpoint occurs in block 1. The block consumes 880 iterations and
900 closure calls/function evaluations. Its optimizer wall time is 13.85 s and
its complete block wall time is 13.90 s. The optimizer-coordinate gradient
receipts are

$$
\|g_{\rm raw}\|_{\rm RMS}=3.764853761381442\times10^{-7},
\qquad
\|g_{\rm raw}\|_{\max}=6.591885559993365\times10^{-6}.
$$

These two values document the optimization coordinates. Endpoint selection is
controlled by the independently recomputed physical first variation.

## 3. Selected endpoint

The selected artifact is
`runs/20260902_particle_stationary_precision_v5/fields_block01.npz`, with
SHA-256
`ac4c54fa0e5ed61f73cb86b5e83d0061806fc2e5d1725894bad9e8e89457a61e`.
The independent verifier gives:

| Quantity | Source | Selected endpoint | Change |
|---|---:|---:|---:|
| physical energy | $3.854200126928118$ | $3.854183410304055$ | $-1.6716624063\times10^{-5}$ |
| physical-gradient RMS | $1.936974511462459\times10^{-4}$ | $5.471248126403572\times10^{-5}$ | $3.540279\times$ smaller |
| cutoff virial | $1.891010219094089\times10^{-3}$ | $1.348199143828711\times10^{-4}$ | $14.026194\times$ smaller |
| $\widehat\omega_C$ | $0.9619135625713445$ | $0.9619139451720478$ | finite continuation shift |
| charge $q_C$ | $4.000000000000002$ | $4.0$ | exact target retained |

The selected physical-gradient RMS is 54.4% of the acquisition limit. The
fixed shell is reproduced exactly in every field component, with maximum shell
residual zero under the registered $10^{-12}$ tolerance. The independently
reconstructed NPZ fields round-trip with maximum relative infinity residual
$2.220444141341195\times10^{-16}$.

Additional selected diagnostics are:

| Diagnostic | Value |
|---|---:|
| fixed-boundary residual | $0$ |
| gauge-divergence RMS | $1.937744624111872\times10^{-6}$ |
| gauge-fixing fraction | $8.974468548023008\times10^{-10}$ |
| outer flux RMS | $1.697589457029775\times10^{-7}$ |
| outer magnetic number | $0$ |
| carrier radius | $2.568225140128511$ |
| outer carrier fraction | $0.0154852054500713$ |
| maximum density depletion | $0.181756560727574$ |

## 4. Independent gates

The final verifier loads the selected artifact with `allow_pickle=False`, ports
the physical field map and PA32 diagnostics independently, recomputes Q1–Q4,
checks the optimizer schedule and artifact hashes, and verifies that block 1 is
the first qualifying endpoint.

| Gate | Measured condition | Result |
|---|---|:---:|
| HP-A | manifest, source schema, source scalars, shell, and reconstruction pass | **PASS** |
| HP-B | the executed block and its hashed artifact are finite and complete | **PASS** |
| HP-C | block 1 is the first endpoint below $1.20\times10^{-4}$ with Q1–Q4 passing | **PASS** |
| HP-D | independent diagnostics, optimizer receipts, gates, artifact, and selection agree | **PASS** |

The independent receipt contains no mismatches. Its scientific verdict is

$$
\boxed{\mathrm{PASS\text{—}HIGHER\text{-}PRECISION\ BACKGROUND}}.
$$

## 5. Frozen implementation and receipts

The implementation freeze is commit
`9a41262a886bf8533962127772062538fdb6aaaf`. Its source manifest is
`computations/particle_stationary_precision_v5_manifest.json`, with canonical
SHA-256
`1307cc689272eb0100655299232719079ca34697e6e6f74451efb50270d6fc33`.
Text hashes canonicalize CRLF to LF; the NPZ hash is byte-exact.

| Evidence | Canonical SHA-256 |
|---|---|
| preregistration | `b95d9f1bbf361161fcc2b1647e1ee707c1ded004be683a791748c1508b6dc0e1` |
| primary program | `ca0f824261612e007689d1be1028a33faa9edb4e55c3b6a6372731cc904749dc` |
| independent verifier | `e970991cd4947bf6bc4259dec8cb5b5f1ae38546c949d68616639f733b18e87f` |
| `results.json` | `9decc9a751d7c833f92754eb3e5187da9056bc5ddda0c9bd125e188f4e90cfa5` |
| `verification.json` | `7667c9617c3e4bd237e77e84226c78805d224002a18a192f25cce24cd2ce4b32` |
| selected NPZ | `ac4c54fa0e5ed61f73cb86b5e83d0061806fc2e5d1725894bad9e8e89457a61e` |

The evidence directory is
`runs/20260902_particle_stationary_precision_v5/`. The executed commands use
the registered ROCm environment:

```text
python computations/particle_stationary_precision_v5.py
python computations/verify_particle_stationary_precision_v5.py
```

## 6. Scientific boundary

This campaign supplies a lower-residual finite-grid stationary background at
one uncalibrated coefficient point. Q1–Q4 remain satisfied, and the endpoint is
precise enough to enter a separately frozen PA42 preflight.

The result leaves these questions open:

- carrier localization and the raw retention inequality;
- outer-domain and finer-grid stationary convergence;
- perturbations outside the $C_4$ field class;
- an unrestricted minimum across unrepresented basins;
- infinite-domain existence and a continuum limit;
- calibrated particle mass, radius, electric charge, spin, and statistics;
- temporal coefficients and the PA43 mixed dynamical spectrum.

The PA42 outcome is reported separately in
`computations/particle-physical-hessian-precision-v2-report.md`.

## References

- `computations/particle-stationary-precision-v5-prereg.md`—frozen continuation, gates, and stopping rule.
- `computations/particle_stationary_precision_v5.py`—frozen primary continuation driver.
- `computations/verify_particle_stationary_precision_v5.py`—independent endpoint verifier.
- `computations/particle-stationary-q2-recovery-report.md`—source Q2-qualified finite-grid background.
- `computations/particle-physical-hessian-precision-v2-report.md`—successor finite-grid PA42 spectrum.
- `foundations/particle-stationary-action-closure.md` §8—stationary action and PA42 fluctuation boundary.

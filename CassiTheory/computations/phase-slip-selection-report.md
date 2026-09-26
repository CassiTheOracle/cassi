# Passive Compact Phase-Current Selection Report

## Status: Tested—August 2026

## Purpose

This report records the protocol-complete execution of the passive
complex-amplitude candidate $M_0$ frozen in
`computations/phase-slip-selection-pre-registration.md`. The candidate uses
only lattice stiffness, local amplitude restoration, and symmetric Yang/Yin
alignment. Its evolution law contains no $\varphi$-dependent term.

## Frozen execution

```text
python computations/verify_phase_slip_selection.py
```

The verifier completed both frozen arms and exited $0$. It reserves a
nonzero exit only for an implementation or sampled-descent failure.

| Arm | $N$ | $\Delta t$ | Steps | $T$ |
|-----|-----|--------------|-------|-----|
| primary | 64 | 0.02 | 30,000 | 600 |
| resolution | 96 | 0.01 | 60,000 | 600 |

## Receipt

| Arm | Seed $(p,q)$ | $H_0$ | $H_T$ | Final $(w_Y,w_I)$ | Orientation | $|w_I/w_Y|$ | Minimum amplitude | Maximum sampled rise |
|-----|--------------|--------|--------|-------------------|-------------|--------------|-------------------|----------------------|
| primary | $(1,1)$ | 12.201120 | 4.703569 | $(1,-1)$ | counter | 1.000000 | $5.000\times10^{-2}$ | $1.510\times10^{-14}$ |
| primary | $(1,2)$ | 13.989531 | 7.336430 | $(1,-2)$ | counter | 2.000000 | $5.000\times10^{-2}$ | 0 |
| primary | $(2,3)$ | 18.739485 | 12.593116 | $(2,-3)$ | counter | 1.500000 | $5.000\times10^{-2}$ | 0 |
| primary | $(3,5)$ | 31.018396 | 15.565880 | $(3,-3)$ | counter | 1.000000 | $9.372\times10^{-3}$ | 0 |
| primary | $(5,8)$ | 62.047723 | 18.005094 | $(4,4)$ | co-oriented | — | $1.012\times10^{-3}$ | 0 |
| primary | $(8,13)$ | 135.528987 | 1.226791 | $(1,1)$ | co-oriented | — | $2.122\times10^{-4}$ | 0 |
| resolution | $(1,1)$ | 15.010908 | 4.702919 | $(1,-1)$ | counter | 1.000000 | $5.000\times10^{-2}$ | $1.776\times10^{-14}$ |
| resolution | $(1,2)$ | 16.218034 | 7.236069 | $(1,-2)$ | counter | 2.000000 | $5.000\times10^{-2}$ | 0 |
| resolution | $(2,3)$ | 19.431294 | 12.013148 | $(2,-3)$ | counter | 1.500000 | $5.000\times10^{-2}$ | 0 |
| resolution | $(3,5)$ | 27.808966 | 20.612887 | $(3,-5)$ | counter | 1.666667 | $5.000\times10^{-2}$ | 0 |
| resolution | $(5,8)$ | 49.406775 | 18.454045 | $(5,-2)$ | counter | 0.400000 | $5.000\times10^{-2}$ | 0 |
| resolution | $(8,13)$ | 103.530143 | 35.576121 | $(7,7)$ | co-oriented | — | $2.172\times10^{-4}$ | 0 |

Every sampled energy decrease passes PS1. The largest sampled rise is
$1.776\times10^{-14}$, below the frozen $10^{-10}$ tolerance.

| Arm | $\varphi$ hits | $3/2$ hits | $\sqrt2$ hits |
|-----|-----------------|------------|---------------|
| primary | 0 | 1 | 0 |
| resolution | 0 | 1 | 0 |

PS2 requires at least two counteroriented $\varphi$-band sectors in each arm
and a count exceeding each control. Both arms return zero $\varphi$ hits.

## Verdict

\[
\boxed{\mathrm{REJECT}\ M_0}
\]

The passive candidate satisfies sampled gradient descent and produces no
$\varphi$-band selection in either frozen arm. The result rejects $M_0$ as a
phase-ratio candidate. The conditional counterflow theorem, compact winding
boundary, and supplied-ring algebra retain their stated scopes. A physical
compact-current and phase-slip law remains Hypothesized.

## References

- `computations/phase-slip-selection-pre-registration.md`
- `computations/verify_phase_slip_selection.py`
- `principles/de-resonance-principle.md` §1.4–§1.5
- `foundations/qi-loop-mass-cascade.md` §6

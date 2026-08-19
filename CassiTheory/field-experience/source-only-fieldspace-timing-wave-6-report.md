# Source-Only Field-Space Timing (Wave 6) Report

## Status: Hypothesized—August 2026

## Abstract

Wave 6 keeps the compact target-only pulse and passive diagonal/axial receiver cores from Wave 5, while replacing the projected-current and direct-calibration statistic with a projection-free amplitude-pair response. The execution passes every frozen quality gate. A detectable diagonal field-space response emerges, but the diagonal and axial timing profiles are equal and the phase-label shuffle leaves that result unchanged. The frozen terminal decision is **CONTRADICTS** for the delayed-diagonal timing hypothesis.

## 1. Execution receipt

**Protocol:** `field-experience/source-only-fieldspace-timing-pre-registration.md`  
**Script:** `field-experience/source_only_fieldspace_timing_probe.py`  
**Receipt:** `runs/20260818_184621_source_only_fieldspace_timing/results.json`  
**Device:** ROCm through `torch.cuda`  
**Horizon:** $48^3$, $dt=0.001$, one target-only pulse at $t_p=0.100$, $t_{\rm end}=0.260$.

| gate | result |
|---|---|
| synthetic field-space reference | PASS: equal pairs give $q=0$; unit antisymmetric pairs give $q=1$ |
| actual read-only pair wrapper | PASS: 101 wrapper snapshots and pair snapshots are bit-identical to 100 direct canonical RK2 steps; maximum state difference $0.0$ |
| compact support | PASS: 895 cells in each $T,D,A$ core; $T$ has zero overlap with $D$ and $A$ |
| target phase match | PASS: $M=0.9999999966$ in every source arm |
| pulse-snapshot field-space gate | PASS: standard $q_D(0)=2.09\times10^{-16}$, $q_A(0)=2.77\times10^{-16}$; shuffled values are $1.90\times10^{-16}$ and $2.52\times10^{-16}$ |
| numerical field integrity | PASS: finite throughout with no $10^{-3}$ floor contact |
| source pulse schedule | PASS: four active source arms, one pulse per arm |
| compact $SO(2)$ kick | PASS: $\beta_{\max}=0.0278202<0.05$, maximum norm error $1.05\times10^{-15}$ |
| pointwise $\rho$ and global mass | PASS: maximum $\rho$ error $8.88\times10^{-16}$; relative mass error $0.0$ |
| positivity wedge | PASS: minimum angular margin $0.58282$ rad |
| timing traces | PASS: every arm has 261 samples and every pair has $k=0,\ldots,160$ |

## 2. Frozen field-space observable

For source plus/minus runs, Wave 6 measures the local amplitude-pair difference

$$
A^\pm=\sqrt{E_Y^\pm},\qquad B^\pm=\sqrt{E_I^\pm},
\qquad
q_R(k)=\frac{1}{0.45}
\sqrt{\sum_{\mathbf x}\chi_R
\left[\left(\frac{A^+-A^-}{2}\right)^2+
\left(\frac{B^+-B^-}{2}\right)^2\right]}.
$$

The compact target core is disjoint from the passive diagonal receiver $D=(24,24,24)$ and equal-distance axial probe $A=(12,29,24)$. Thus the machine-scale $q_R(0)$ values are the required source-support result, while the first nonzero receiver field-space values occur only after canonical evolution.

The projected-current telemetry remains diagnostic only. At the pulse snapshot,

$$
S_D(0)=1.55\times10^{-18},\qquad S_A(0)=-1.31\times10^{-5},
$$

while both $q_D(0)$ and $q_A(0)$ vanish within the frozen tolerance. The nonzero $S_A(0)$ is an FFT-gradient readout response; it is not a field-space rotation in the axial receiver core.

## 3. Frozen timing results

The timing window is $k=1,\ldots,120$; $k_{50}$ is the cumulative field-space-energy half time, $\iota$ is the first-step energy share, and $p$ is the $k=20,\ldots,120$ late-energy fraction.

| label setting | receiver | $W$ | $k_{50}$ | $\iota$ | $p$ | $Q^{\rm late}$ |
|---|---|---:|---:|---:|---:|---:|
| standard | diagonal $D$ | $6.33630\times10^{-12}$ | 96 | $1.73866\times10^{-6}$ | $0.9957147$ | $2.49934\times10^{-7}$ |
| standard | axial $A$ | $4.45102\times10^{-9}$ | 96 | $1.73395\times10^{-6}$ | $0.9957239$ | $6.62428\times10^{-6}$ |
| shuffled | diagonal $D$ | $6.35231\times10^{-12}$ | 96 | $1.73858\times10^{-6}$ | $0.9957148$ | $2.50249\times10^{-7}$ |
| shuffled | axial $A$ | $4.45102\times10^{-9}$ | 96 | $1.73395\times10^{-6}$ | $0.9957239$ | $6.62428\times10^{-6}$ |

The first post-RK2 field-space values are $q_D(1)=3.32\times10^{-9}$ and $q_A(1)=8.79\times10^{-8}$. Both traces accumulate predominantly after the first step, with $k_{50}=96$ and late-energy fraction about $0.996$.

## 4. Frozen decision tree

| feature | frozen criterion | outcome |
|---|---|---|
| F1 diagonal field-space response | $W_D>0$ and $Q_D^{\rm late}\geq10^{-12}$ | EMERGES |
| F2 delayed diagonal timing | $k_{50,D}>k_{50,A}$ and $p_D>p_A$ | DOES NOT EMERGE: $96=96$ and $0.9957147<0.9957239$ |
| F3 label-specific timing | F2 with standard labels and not with shuffled labels | DOES NOT EMERGE |

The frozen classifier reaches its formal immediate/global timing branch because $k_{50,D}\leq k_{50,A}$ and $\iota_D\geq\iota_A$. Its terminal result is

$$
\boxed{\text{CONTRADICTS: NO DELAYED-DIAGONAL FIELD-SPACE TIMING IN THIS SOURCE-ONLY PROXY.}}
$$

The branch name does not mean that either field-space trace is one-step dominated: both first-step shares are about $1.7\times10^{-6}$ and both half times are 96. It records equal diagonal/axial timing under the frozen rule.

## 5. Interpretation boundary

The diagonal core develops a detectable field-space difference after canonical evolution, but its timing is not later than the axial control and its late fraction is not larger. The axial field-space response is also larger in the recorded receiver-scale-independent quantities: $Q_A^{\rm late}$ exceeds $Q_D^{\rm late}$ by about $26.5\times$. The shuffled control is numerically indistinguishable at the reported timing precision.

This closes the preregistered source-only delayed-diagonal timing hypothesis under its frozen terminal decision tree. A different future mechanism would require its own source construction and preregistration; it cannot relabel this metric or reuse it to claim a selected diagonal edge.

## 6. Scope

This result applies to the tested finite index-lattice proxy and the canonical PDE operators. It does not establish finite-speed causation, a physical bubble-edge transport law, a self-maintaining macro-spiral, biological circulation, neural action, or consciousness.

## References

- `field-experience/source-only-fieldspace-timing-pre-registration.md`—frozen source-only construction, metric, and terminal decision tree.
- `field-experience/source_only_fieldspace_timing_probe.py`—read-only paired amplitude-field wrapper.
- `runs/20260818_184621_source_only_fieldspace_timing/results.json`—raw Wave 6 receipt.
- `field-experience/source-only-passive-transfer-wave-5-report.md`—current-readout HOLD that motivated the readout-only refinement.
- `two-fluid/cassi_two_fluid_3d_gpu.py`—canonical RK2 evolution.

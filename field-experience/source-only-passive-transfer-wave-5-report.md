# Source-Only Passive Transfer (Wave 5) Report

## Status: Hypothesized—August 2026

## Abstract

Wave 5 removes the distributed-corridor and receiver-placement ambiguity from Wave 4. A compact bounded amplitude-space $SO(2)$ pulse acts only in the target core, while diagonal and axial probe cores have exactly disjoint support. The corrected execution passes every frozen quality gate and returns **HOLD**: the diagonal source/direct fraction and diagonal-over-axial fractional contrast pass, but the phase-label shuffle does not suppress that contrast.

The receipt contains a delayed diagonal response, but it does not establish a phase-arrangement-selected diagonal edge or finite-speed transport.

## 1. Execution receipt

**Protocol:** `field-experience/source-only-passive-transfer-pre-registration.md`  
**Script:** `field-experience/source_only_passive_transfer_probe.py`  
**Cited receipt:** `runs/20260818_182603_source_only_passive_transfer/results.json`  
**Device:** ROCm through `torch.cuda`  
**Horizon:** $48^3$, $dt=0.001$, one pulse at $t_p=0.100$, $t_{\rm end}=0.260$.

`runs/20260818_181939_source_only_passive_transfer/` contains stale post-RK receiver samples and is excluded. The cited execution reconstructs $E_Y,E_I$ after every canonical RK2 step before recording the next sample and confirms that the read-only trace wrapper is bit-identical to 100 direct canonical steps.

| gate | result |
|---|---|
| synthetic gain references | PASS: equal $+/-$ traces give $G=0$; scripted unit antisymmetry gives $G=1$ |
| read-only trace wrapper identity | PASS, maximum difference $0.0$ |
| source/probe support | PASS: 895 cells per compact core; $\max(b_Tb_D)=\max(b_Tb_A)=0$ |
| source phase match | PASS: $M=0.9999999966$ in every source arm |
| numerical field integrity | PASS: finite throughout with no $10^{-3}$ floor contact |
| one-pulse schedule | PASS: 12 active arms, exactly one pulse per arm |
| compact-kick norm | PASS: maximum error $1.39\times10^{-15}$ from $0.45$ |
| pointwise $\rho$ invariant | PASS: maximum error $8.88\times10^{-16}$ |
| global mass invariant | PASS: maximum relative error $0.0$ |
| positivity wedge | PASS: minimum angular margin $0.58282$ rad |
| delayed trace and calibration | PASS: all 261 samples and all direct gains exceed $10^{-12}$ |

## 2. Frozen receiver statistic

The passive diagonal and equal-distance axial probes are

$$
D=(24,24,24),\qquad A=(12,29,24),
$$

at target separations $12\sqrt2\simeq16.971$ and $17$, respectively. The source compact radius is six cells, so neither probe lies in its support.

For the matched $+/-$ source-pulse pair, the receiver current is

$$
\mathbf J_\Psi=A\nabla B-B\nabla A,
\qquad
S_R(k)=\frac{j_R^+(t_p+kdt)-j_R^-(t_p+kdt)}{2}.
$$

The frozen delayed RMS gain uses $k=20,\ldots,120$ and the local initial current scale. The source-to-direct fractions are

$$
F_D=\frac{G_D^{\rm source}}{G_D^{\rm direct}},
\qquad
F_A=\frac{G_A^{\rm source}}{G_A^{\rm direct}},
\qquad
E=F_D-F_A.
$$

| quantity | standard labels | shuffled labels |
|---|---:|---:|
| $G_D^{\rm source}$ | $1.26894\times10^{-4}$ | $4.36701\times10^{-8}$ |
| $G_A^{\rm source}$ | $4.03563\times10^{-4}$ | $4.02584\times10^{-4}$ |
| $G_D^{\rm direct}$ | $8.23757\times10^{-6}$ | $2.19932\times10^{-9}$ |
| $G_A^{\rm direct}$ | $1.41079\times10^{-2}$ | $1.41015\times10^{-2}$ |
| $F_D$ | $15.40435$ | $19.85619$ |
| $F_A$ | $0.028606$ | $0.028549$ |
| $E$ | $15.37575$ | $19.82764$ |

## 3. Registered decision tree

| feature | frozen criterion | result | outcome |
|---|---|---:|---|
| F1 passive diagonal response | $F_D\geq0.010$ | $15.40435$ | EMERGES |
| F2 diagonal-over-axial fraction | $E\geq0.005$ | $15.37575$ | EMERGES |
| F3 phase-arrangement dependence | $E-E_{\rm shuf}\geq0.005$ | $-4.45190$ | DOES NOT EMERGE |

The frozen result is

$$
\boxed{\text{HOLD: PASSIVE DIAGONAL RESPONSE WITHOUT PHASE-ARRANGEMENT SELECTIVITY.}}
$$

## 4. Temporal and normalization boundary

The diagonal antisymmetric trace is negligible at the pulse snapshot, $S_D(0)=1.55\times10^{-18}$, then grows under canonical evolution to $S_D(20)=-8.26\times10^{-10}$ and $S_D(120)=-5.09\times10^{-9}$. The source mask has zero diagonal-core support, so this delayed diagonal trace is not direct field rotation inside the diagonal probe.

The axial trace is already nonzero at the pulse snapshot, $S_A(0)=-1.31\times10^{-5}$, and the raw axial trace remains larger than the diagonal trace throughout the frozen window. The solver contains diffusion and FFT-mediated field operators, so an immediate remote current response is a global numerical-field response rather than a finite-speed arrival measure.

F1 and F2 use the frozen same-shape direct calibrations. Their ratio ordering does not mean that the diagonal source response dominates: the receiver-scale-normalized $G_A^{\rm source}$ is about $3.2$ times $G_D^{\rm source}$, while the frozen raw $S_A$ trace is also larger over the sampled lags. Under shuffled labels, both diagonal gains decrease, but the direct calibration decreases more than the source response; this raises $F_D^{\rm shuf}$ above $F_D$ and raises $E_{\rm shuf}$ above $E$. The resulting calibration is poorly conditioned for route selectivity, and F3 prevents promotion from HOLD to SUPPORTS.

## 5. Scope and required discriminator

The receipt establishes a passive, delayed diagonal $\mathbf J_\Psi$ perturbation under a source-only compact pulse in this finite proxy. It does not establish diagonal-edge preference, a phase-arrangement-selected transport law, finite-speed causation, a self-maintaining macro-spiral, biological circulation, neural action, or consciousness.

A fresh discriminator must retain disjoint source/receiver support and compare a source-normalized delayed response before dividing by a local direct-projection calibration. Its temporal statistic must separately report the immediate FFT/global contribution and the post-pulse dynamic rise, with shuffled and equal-distance controls frozen before execution.

## References

- `field-experience/source-only-passive-transfer-pre-registration.md`—frozen construction, quality gates, and decision tree.
- `field-experience/source_only_passive_transfer_probe.py`—source-only wrapper and trace implementation.
- `runs/20260818_182603_source_only_passive_transfer/results.json`—raw Wave 5 receipt.
- `field-experience/checkerboard-edge-phase-coupling-wave-4-report.md`—distributed-drive receiver-placement boundary.
- `two-fluid/cassi_two_fluid_3d_gpu.py`—canonical RK2 evolution.

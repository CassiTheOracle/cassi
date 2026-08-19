# Checkerboard Edge Phase Coupling (Wave 4) Report

## Status: Hypothesized—August 2026

## Abstract

Wave 4 applies a bounded, carrier-signed amplitude-space $SO(2)$ phase kick along a finite target-to-diagonal checkerboard corridor. Every frozen execution and invariant gate passes. The diagonal receiver is carrier-selective, but the same normalized receiver coherence is present for the axial-void and undirected-flat controls. The registered decision tree therefore returns **INCONCLUSIVE**: F1 emerges, while route-specific F2 and F3 do not.

## 1. Execution receipt

**Script:** `field-experience/checkerboard_edge_phase_coupling_probe.py`  
**Protocol:** `field-experience/checkerboard-edge-phase-coupling-pre-registration.md`  
**Receipt:** `runs/20260818_172003_checkerboard_edge_phase_coupling/results.json`  
**Device:** ROCm through `torch.cuda`  
**Horizon:** $48^3$, $dt=0.001$, $t_{\rm end}=4.0$, 199 matched events.

| gate | result |
|---|---|
| metric references | PASS: $C(0)=0$, $C(-s_{\rm match})=1$, $C(s_{\rm quadrature})=0$ |
| no-op canonical identity | PASS, maximum difference $0.0$ |
| finite field and floor contact | PASS, finite throughout with no $10^{-3}$ floor contact |
| schedule replay | PASS, 199 events in every driven arm |
| amplitude-kick norm | PASS, maximum error $6.38\times10^{-15}$ from $0.45$ |
| pointwise $\rho$ invariant | PASS, maximum error $1.33\times10^{-15}$ |
| global mass invariant | PASS, relative maximum error $3.25\times10^{-16}$ |
| positivity wedge | PASS, minimum angular margin $0.5897$ rad |
| corridor construction | PASS, $|w|\leq1$ with target/endpoint tube support $0.8076$ for the diagonal and $0.8073$ for the axial route |
| paired flow seed | PASS, opposite-signed right/left $u_z$ and $J_{\Psi,z}$ biases |

## 2. Registered receiver contrasts

The receiver statistic remains the Wave 3 matched-carrier coherence at the diagonal bubble:

$$
C_{D,b}=
\frac{\left|\sum_{n\in b}s_n^{\rm match}r_{D,n}\right|}
{\sqrt{\sum_{n\in b}(s_n^{\rm match})^2}\sqrt{\sum_{n\in b}r_{D,n}^2}},
\qquad
r_{D,n}=\frac{j_D(t_n+0.01)-j_D(t_n^-)}{J_{D,{\rm rms},0}}.
$$

| feature | contrast | mean | 95% paired block-bootstrap interval | criterion | outcome |
|---|---|---:|---:|---|---|
| F1 carrier-selective receiver response | diagonal matched minus diagonal quadrature | $0.99454$ | $[0.98411,\,0.99976]$ | $\geq0.10$, lower bound $>0$ | EMERGES |
| F2 diagonal route specificity | diagonal matched minus axial matched | $-7.19\times10^{-7}$ | $[-9.13,\,-5.15]\times10^{-7}$ | $\geq0.10$, lower bound $>0$ | DOES NOT EMERGE |
| F3 directed-ramp specificity | diagonal matched minus diagonal flat | $-8.24\times10^{-7}$ | $[-1.05,\,-0.584]\times10^{-6}$ | $\geq0.10$, lower bound $>0$ | DOES NOT EMERGE |

The secondary flow contrasts are also below the $0.10$ registered threshold: reversed-flow difference $-1.67\times10^{-16}$ and zero-flow difference $-7.16\times10^{-7}$.

The frozen decision tree gives

$$
\boxed{\text{INCONCLUSIVE: CARRIER SELECTIVITY WITHOUT ROUTE SPECIFICITY.}}
$$

## 3. What the construction establishes

A target phase match, a bounded rhythmic phase kick, and the matched four-event carrier produce a carrier-locked $\mathbf J_\Psi$ response at the diagonal receiver. The quadrature sequence has negligible coherence against the same matched reference. The solver-level chain measured here is

$$
\text{local phase match}
\longrightarrow
\text{distributed bounded phase kick}
\longrightarrow
\text{carrier-locked diagonal-receiver }\mathbf J_\Psi\text{ response}.
$$

This is compatible with phase resonance as a condition for a coherent field response under the supplied drive.

## 4. Route result and measurement boundary

The result does not establish preferential diagonal-edge transmission. The axial-void construction and the flat diagonal tube each produce nearly the same normalized matched-carrier coherence as the directed diagonal ramp. The current registered statistic isolates phase alignment but divides by each block's response norm, so it does not measure received signal magnitude or transported energy.

The supplied corridor kick also has nonzero support at the diagonal receiver. A carrier-locked receiver signal can therefore arise from direct local actuation within the drive profile rather than arrival from a source-localized pulse. The finite proxy has no evidence here that its diagonal saddle geometry selects a transmission route or that the paired circulation biases the response.

## 5. Required next discriminator

A transport test requires a fresh source-only construction: apply the bounded kick inside the target mask while excluding the receiver and corridor, then measure a pre-registered receiver-arrival statistic over a causal lag window. The statistic must retain amplitude information, such as a baseline-subtracted $j_D$ impulse norm or integrated $\mathbf J_\Psi\cdot\hat e_D$ flux at an unforced receiver. It must compare the diagonal receiver with an equal-distance axial receiver and with a spatially scrambled or phase-scrambled source control.

Such a design can distinguish source-to-receiver transfer from direct placement of a signal at the receiver. It does not follow from this Wave 4 receipt that the canonical PDE contains that route mechanism.

## 6. Scope

This is a driven finite index-lattice proxy. It supplies no spontaneous checkerboard transport, persistent macro-spiral, biological circulation, neural action, or consciousness conclusion.

## References

- `field-experience/checkerboard-edge-phase-coupling-pre-registration.md`—frozen geometry, operator, and decision tree.
- `field-experience/checkerboard_edge_phase_coupling_probe.py`—execution wrapper and receipts.
- `runs/20260818_172003_checkerboard_edge_phase_coupling/results.json`—raw Wave 4 result.
- `field-experience/counterflow-carrier-demodulation-wave-3-report.md`—carrier-demodulated local synchronization result.
- `foundations/bubble-lattice-fabric.md` §1.2—diagonal saddle and axial void geometry.

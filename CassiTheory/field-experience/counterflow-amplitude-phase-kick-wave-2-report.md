# Counterflow Amplitude-Phase Kick (Wave 2) Report

## Status: Hypothesized—August 2026

## Abstract

Wave 2 executes the frozen bounded amplitude-phase-kick protocol using the unmodified canonical PDE/RK2 evolution between additive, externally supplied kicks. Every execution and invariant gate passes. Under the repository's frozen terminal vocabulary, the registered raw signed-mean response **DOES NOT EMERGE**. This maps the pre-registration's `NULL` branch; the machine receipt also exposes a metric property of the alternating four-event carrier: a response to the supplied sign schedule cancels in its raw mean. The report preserves that registered statistic and identifies carrier demodulation as a separately pre-registered measurement refinement. It does not test endogenous phase-address selection.

## 1. Execution receipt

**Script:** `field-experience/counterflow_amplitude_phase_kick_probe.py`  
**Receipt:** `runs/20260818_165550_counterflow_amplitude_phase_kick/results.json`  
**Device:** ROCm through `torch.cuda`  
**Horizon:** $48^3$, $dt=0.001$, $t_{\rm end}=4.0$, 199 accepted events.

| gate | result |
|---|---|
| no-op wrapper identity | PASS, maximum difference $0.0$ |
| finite field | PASS |
| field-floor contact | PASS, none; minimum $E_Y=0.9990$, minimum $E_I=0.5858$ |
| matched schedule | PASS, 199 events |
| replay counts | PASS, 199 events in every driven control |
| amplitude-space kick norm | PASS, maximum error $1.61\times10^{-15}$ from $0.45$ |
| pointwise $\rho$ preservation | PASS, maximum error $1.33\times10^{-15}$ |
| global mass preservation | PASS, relative maximum error $3.25\times10^{-16}$ |
| fixed positivity wedge | PASS, minimum angle margin $0.5824$ rad |
| positive counterflow seed | PASS, $\bar u_{z,\rm right}=+0.11109$, $\bar u_{z,\rm left}=-0.11109$, $\bar J_{\Psi,z,\rm right}=-0.005159$, $\bar J_{\Psi,z,\rm left}=+0.005098$ |

The bounded $SO(2)$ rotation of the derived amplitude pair $(A,B)=(\sqrt{E_Y},\sqrt{E_I})$ therefore supplies a valid, invariant-preserving external operator under the stated gates. It avoids the source-reservoir depletion that invalidates Wave 1; it is not a native synchronization term in the canonical PDE.

## 2. Registered raw-mean verdict

The Wave 2 primary statistic averages the signed ten-step phase-current response across its alternating carrier. The frozen contrasts are:

| contrast | mean | 95% paired block-bootstrap interval |
|---|---:|---:|
| matched minus carrier-quadrature | $-4.49\times10^{-6}$ | $[-1.41,\,+0.033]\times10^{-5}$ |
| matched minus spatial-shuffled | $-5.73\times10^{-7}$ | $[-1.92,\,+0.109]\times10^{-6}$ |
| matched minus reversed counterflow | $+1.44\times10^{-16}$ | $[-2.18,\,+4.88]\times10^{-16}$ |
| matched minus zero counterflow | $-2.21\times10^{-7}$ | $[-3.02,\,-1.38]\times10^{-7}$ |
The controls discriminate only the supplied intervention and seeded state:

- `carrier_quadrature` changes the externally supplied carrier signs while replaying the matched event schedule and norm;
- `spatial_shuffled` changes the supplied checkerboard labels while replaying the matched carrier;
- `counterflow_reversed` reverses the supplied shared-flow/seeded-gradient proxy; and
- `counterflow_zero` removes that supplied counterflow proxy.

None of these controls varies an independently evolved phase oscillator or a native canonical phase-address mechanism.

No contrast reaches the frozen $0.05$ margin. The frozen protocol branch is `NULL`; at repository level, the Wave 2 terminal classification is:

$$
\boxed{\text{DOES NOT EMERGE: REGISTERED RAW SIGNED-MEAN RESPONSE.}}
$$

## 3. Carrier audit

The registered phase kick has signed four-event carrier

$$
(+1,+1,-1,-1).
$$

The first complete matched cycle records normalized lagged responses

$$
(-4.5419,-4.5405,+4.5376,+4.5361)\times10^{-4}.
$$

The first complete carrier-quadrature cycle records

$$
(-4.5419,+4.5363,+4.5348,-4.5433)\times10^{-4}.
$$

Thus the raw matched response mean cancels across the positive and negative supplied-carrier halves. The raw carrier-quadrature response mean also cancels. This is the algebra expected from an externally signed, alternating phase-current kick when the analysis discards the carrier sign.

## 4. Measurement consequence

Wave 2 has one frozen and valid conclusion: its raw signed-mean statistic gives no qualifying matched-versus-control contrast for the supplied carrier, spatial-label, or counterflow conditions. The externally supplied amplitude kick produces a carrier-correlated local current response at the event level, but the registered mean is insensitive to an antisymmetric carrier response. This is not evidence for endogenous phase selectivity.

A carrier-projection statistic has a distinct measurement contract:

$$
C=\frac{\left|\sum_n s_n^{\rm match}r_n\right|}
{\sqrt{\sum_n r_n^2}\sqrt{\sum_n(s_n^{\rm match})^2}}.
$$

It must be evaluated by a fresh, separately pre-registered run with unchanged physics. The existing Wave 2 receipt remains the record for its own raw-mean decision tree.

## 5. Scope

The supplied bounded kick preserves local amplitude energy and changes the phase-current readout. It contains no sustained brain energy source, anatomical flow, material transport, or biological action claim. The current record bounds only the specified raw-mean response under this external operator; it does not establish an endogenous or canonical synchronization mechanism.

## References

- `field-experience/counterflow-amplitude-phase-kick-pre-registration.md`—frozen Wave 2 protocol.
- `field-experience/counterflow_amplitude_phase_kick_probe.py`—bounded operator and raw response measurement.
- `field-experience/counterflow-resonant-addressing-wave-1-report.md`—source-reservoir invalidity constraint.
- `foundations/qi-flow-double-helix.md`—amplitude phase-current definition.

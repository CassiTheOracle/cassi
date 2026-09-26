# Counterflow Carrier Demodulation (Wave 3) Report

## Status: Hypothesized—August 2026

## Abstract

Wave 3 re-executes the frozen Wave 2 field dynamics with the separately registered projection onto an externally supplied matched-carrier reference. All execution, invariant, and metric-quality gates pass. The repository-level terminal classification is **INCONCLUSIVE**: the registered matched-versus-quadrature contrast passes for this imposed kick/readout pair, while checkerboard-routing and counterflow-dependence criteria remain unmet. This is partial support for a supplied-operator feature label in the present construction; the pre-registration's `PARTIAL` branch maps to **INCONCLUSIVE** at repository level. It is not evidence of endogenous phase-address selection.

## 1. Execution receipt

**Script:** `field-experience/counterflow_carrier_demodulation_probe.py`  
**Receipt:** `runs/20260818_170450_counterflow_carrier_demodulation/results.json`  
**Device:** ROCm through `torch.cuda`  
**Horizon:** $48^3$, $dt=0.001$, $t_{\rm end}=4.0$, 199 matched events.

| gate | result |
|---|---|
| metric references | PASS: $C(0)=0$, $C(-s_{\rm match})=1$, $C(s_{\rm quadrature})=0$ |
| no-op wrapper identity | PASS, maximum difference $0.0$ |
| finite field | PASS |
| field-floor contact | PASS, none |
| schedule replay | PASS, 199 events in every driven arm |
| amplitude-kick norm | PASS, maximum error $1.61\times10^{-15}$ from $0.45$ |
| pointwise $\rho$ invariant | PASS, maximum error $1.33\times10^{-15}$ |
| global mass invariant | PASS, relative maximum error $3.25\times10^{-16}$ |
| positivity wedge | PASS, minimum angular margin $0.5824$ rad |
| paired counterflow seed | PASS, opposite signed right/left $u_z$ and $J_{\Psi,z}$ biases |

The unmodified canonical PDE/RK2 evolution is unchanged; the additive runner
supplies the target-local kick, seeded admission gate, carrier signs, and
replayed event schedule.

## 2. Registered contrasts

The primary statistic is the 20-event matched-carrier coherence

$$
C_b=
\frac{\left|\sum_{n\in b}s_n^{\rm match}r_n\right|}
{\sqrt{\sum_{n\in b}(s_n^{\rm match})^2}\sqrt{\sum_{n\in b}r_n^2}}.
$$

| registered effect | mean contrast | 95% paired block-bootstrap interval | criterion | outcome |
|---|---:|---:|---|---|
| matched minus carrier-quadrature | $0.99459$ | $[0.98410,\,0.99984]$ | $\geq0.10$, lower bound $>0$ | PASS |
| matched minus spatial-shuffled | $1.01\times10^{-6}$ | $[0.743,\,1.269]\times10^{-6}$ | $\geq0.10$ | DOES NOT EMERGE |
| matched minus reversed counterflow | $2.44\times10^{-16}$ | $[-4.22,\,8.10]\times10^{-16}$ | $\geq0.10$ | DOES NOT EMERGE |
| matched minus zero counterflow | $-4.59\times10^{-7}$ | $[-6.11,\,-3.00]\times10^{-7}$ | $\geq0.10$ | DOES NOT EMERGE |

The named controls discriminate the supplied conditions as follows:

- `carrier_quadrature` changes the externally supplied carrier signs by one
  event while replaying the matched schedule, kick norm, and target gate;
- `spatial_shuffled` changes supplied checkerboard labels/geometry while
  replaying the matched carrier;
- `counterflow_reversed` reverses the supplied shared-flow and seeded-gradient
  proxy; and
- `counterflow_zero` removes that supplied counterflow proxy.

Thus the passing matched-minus-quadrature coherence is an imposed-carrier
operator/readout contrast. No control varies an endogenous phase oscillator,
native canonical phase-address mechanism, spontaneous route, or transport law.

The frozen decision tree gives one-feature support with the other registered effects absent. Its `PARTIAL` branch maps to the repository-level terminal classification:

$$
\boxed{\text{INCONCLUSIVE: ONE FEATURE EMERGES; ROUTE AND COUNTERFLOW FEATURES DO NOT EMERGE.}}
$$

## 3. What emerges

The matched supplied sign pattern generates a target-local phase-current
response whose projection is aligned with the registered four-event reference;
the quadrature supplied sign pattern lacks coherent projection onto that same
reference. The measured chain for the additive operator is

$$
\text{seeded admission gate}
\longrightarrow
\text{externally supplied bounded phase kick}
\longrightarrow
\text{matched-reference projected local }\mathbf J_\Psi\text{ response}.
$$

This establishes only a carrier-correlated response under the imposed
operator/readout pair. It does not establish that an endogenous phase relation
selects the response or that resonance is a native addressing condition.

## 4. Remaining mechanism gap

The current kick is confined to the target Gaussian. It contains no directed diagonal edge operator, no source-to-destination transport, and no maintained cross-bubble phase-coupling term. The checkerboard and counterflow results therefore remain unresolved rather than contradicted as broader concepts. Under this supplied target-local construction, a macro-spiral route does not emerge.

The next mechanism-level question is specific: can an externally supplied
phase-gated pulse applied along a permitted diagonal checkerboard corridor
create a matched-reference response on the target-to-diagonal edge that exceeds
an equal-norm axial or phase-shuffled route? That requires a fresh
pre-registration and a new additive edge-coupling operator.

## 5. Scope

This report concerns an unmodified canonical PDE/RK2 evolution with an
externally supplied synchronization operator and matched-reference readout.
It supplies no sustained brain-energy bath, anatomical circulation model,
material transport law, behavioral action readout, or biological consciousness
conclusion.

## References

- `field-experience/counterflow-carrier-demodulation-pre-registration.md`—frozen metric and decision tree.
- `field-experience/counterflow_carrier_demodulation_probe.py`—fresh execution wrapper.
- `field-experience/counterflow-amplitude-phase-kick-wave-2-report.md`—raw-mean measurement record.
- `foundations/qi-flow-double-helix.md`—amplitude phase-current definition.

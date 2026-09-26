# Counterflow Carrier Demodulation (Wave 3)

## Status: Hypothesized—August 2026

## Abstract

Wave 3 repeats the bounded amplitude-phase-kick field evolution from `field-experience/counterflow-amplitude-phase-kick-pre-registration.md` without changing its seeded state, shared counterflow, additive amplitude-space kick, cadence, arm set, solver, or horizon. Its sole refinement is a carrier-sensitive primary statistic. The four-event externally supplied kick has zero signed mean by construction; this run therefore projects the response onto the frozen matched carrier rather than treating an unsigned-time average of signed current increments as a phase mechanism.

## 1. Fixed physical execution

The physical execution is byte-for-byte inherited from Wave 2:

- the unmodified canonical `ExpandingTwoFluid3DGPU` PDE/RK2 evolution, five-channel gate, $48^3$, $dt=0.001$, $t_{\rm end}=4.0$;
- finite five-bubble checkerboard, periodic paired counterflow, and positive/reversed/zero circulation arms;
- bounded target-local amplitude-space $SO(2)$ kick supplied by the probe with $\|\Delta(A,B)\|_2=0.45$;
- 48 bisection iterations with $\alpha_\star\leq0.05$;
- 50 event opportunities per normalized time unit, seeded phase-match gate $M\geq\cos(\pi/6)$, and ten-step response lag;
- fresh `baseline`, `matched`, `carrier_quadrature`, `spatial_shuffled`, `counterflow_reversed`, and `counterflow_zero` arms;
- exact matched-schedule replay in every driven control.

The implementation imports the Wave 2 arm runner. It must not alter the
unmodified canonical PDE/RK2 operator or configuration. The trigger, kick, and
carrier signs are supplied by the additive runner; no carrier phase evolves
endogenously in the canonical solver.

## 2. Carrier-sensitive primary statistic

The frozen matched carrier is

$$
s_n^{\rm match}=(+1,+1,-1,-1)_{n\bmod4}.
$$

For every accepted event, retain the Wave 2 normalized amplitude-current response

$$
r_n=\frac{j_{\parallel,\Psi}(t_n+0.01)-j_{\parallel,\Psi}(t_n^-)}{J_{\Psi,{\rm rms},0}}.
$$

Partition the 199 events into contiguous 20-event blocks. For a block $b$, define the matched-carrier coherence

$$
C_b=\begin{cases}
\dfrac{\left|\sum_{n\in b}s_n^{\rm match}r_n\right|}
{\sqrt{\sum_{n\in b}(s_n^{\rm match})^2}\sqrt{\sum_{n\in b}r_n^2}},&\sum_{n\in b}r_n^2>0,\\[1.2em]
0,&\sum_{n\in b}r_n^2=0.
\end{cases}
$$

Every arm is projected onto **the externally supplied matched reference carrier**, including `carrier_quadrature`. The quadrature control therefore tests whether its response is displaced by one imposed carrier event rather than merely whether it follows its own injected waveform. The own-carrier coherence is reported only as a secondary diagnostic. This projection is an operator/readout check, not a test of endogenous phase-address selection.

## 3. Metric-quality gates

The following deterministic reference arrays are checked before any solver arm:

| input response, over a full 20-event block | required $C_b$ |
|---|---:|
| $r_n=0$ | $0$ exactly |
| $r_n=-s_n^{\rm match}$ | $1$ exactly |
| $r_n=s_n^{\rm quadrature}$, where $(+1,-1,-1,+1)$ repeats | $0$ exactly |

Wave 3 is **INVALID** if any reference check fails or if any of the frozen Wave 2 execution gates fails: no-op identity, finite values, zero floor contact, exact schedule replay, at least 30 matched events, fixed kick norm, pointwise $\rho$ invariant, global mass invariant, fixed positivity wedge, and signed counterflow seed.

## 4. Decision tree

For every named control $X$, form the paired block contrast

$$
\Delta C_X=\bar C_{\rm matched}-\bar C_X
$$

with the frozen 10,000-resample paired block bootstrap and seed `20260818`.

A contrast passes only when

$$
\Delta C_X\geq0.10
$$

and its paired 95% bootstrap lower bound exceeds zero. The $0.10$ margin lies on the bounded coherence interval $[0,1]$; it is independent of field-current amplitude.

- **PHASE-SELECTIVE SYNCHRONIZATION SUPPORT** requires a passing $\Delta C_{\rm carrier\_quadrature}$.
- **CHECKERBOARD-ROUTING SUPPORT** requires a passing $\Delta C_{\rm spatial\_shuffled}$.
- **COUNTERFLOW-DEPENDENCE SUPPORT** requires passing matched-minus-reversed and matched-minus-zero coherence contrasts, together with reversal of seeded $J_{\Psi,z}$.
- **PARTIAL** applies if one or two named effects pass.
- **NULL** applies if the run is valid and no named effect passes.
- **INVALID** applies through a quality gate.

These uppercase labels are frozen protocol feature branches. They compare the
supplied kick/sign/label/flow conditions against the supplied matched-carrier
reference; they do not establish endogenous canonical phase selection,
spontaneous routing, or transport.

The run stops at $t=4$. This protocol does not reinterpret the Wave 2 raw-mean verdict; it evaluates a new registered measurement contract on a fresh execution with unchanged field dynamics.

## 5. Scope

The experiment measures the response of an externally supplied carrier-signed
kick under a matched-reference readout. It does not add a sustained energy
bath, material transport law, anatomical circulation, or biological action
claim. A positive phase-contrast result would establish alignment of this
finite-field response with the registered imposed carrier, not endogenous
phase-address selection. A null would constrain the same bounded-kick
construction under carrier demodulation.

## References

- `field-experience/counterflow-amplitude-phase-kick-pre-registration.md`—unchanged physical construction.
- `field-experience/counterflow-amplitude-phase-kick-wave-2-report.md`—registered raw-mean record and carrier cancellation audit.
- `field-experience/counterflow_amplitude_phase_kick_probe.py`—reused physical arm runner.

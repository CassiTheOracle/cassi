# Passive Compact Phase-Current Selection Pre-Registration

## Status: Pre-registration—August 2026

## Purpose

This computation tests one explicit passive complex-amplitude candidate for
the compact phase-current transition law required by
`principles/de-resonance-principle.md` §1.4. The candidate carries two
periodic complex fields, permits amplitude-suppressed winding changes, and
contains no $\varphi$-dependent term in its evolution law. It therefore
separates an emergent phase-ratio result from a ratio supplied as a model
input.

The result classifies this candidate, $M_0$. It leaves driven, vorticity-coupled,
and microscopic current realizations open.

## Frozen model

On a periodic lattice $j\in\mathbb Z_N$, define complex fields $u_{Y,j}$ and
$u_{I,j}$ with energy

\[
H_0=\sum_j\left[
 |u_{Y,j+1}-u_{Y,j}|^2+|u_{I,j+1}-u_{I,j}|^2
 +\frac{g}{2}\left((|u_{Y,j}|^2-1)^2+(|u_{I,j}|^2-1)^2\right)
 +\eta|u_{Y,j}-u_{I,j}|^2
\right].
\]

The deterministic overdamped flow is

\[
\begin{aligned}
\dot u_{Y,j}&=u_{Y,j-1}+u_{Y,j+1}-2u_{Y,j}
 +g(1-|u_{Y,j}|^2)u_{Y,j}+\eta(u_{I,j}-u_{Y,j}),\\
\dot u_{I,j}&=u_{I,j-1}+u_{I,j+1}-2u_{I,j}
 +g(1-|u_{I,j}|^2)u_{I,j}+\eta(u_{Y,j}-u_{I,j}).
\end{aligned}
\]

For the continuum flow, $H_0$ is nonincreasing. The discrete computation
checks the sampled energy descent directly. The common $U(1)$ symmetry and
positive relative-phase coupling are the standard minimal passive choice;
they contain no counterflow drive and no prescribed irrational ratio.

The frozen values are

\[
g=1,\qquad \eta=0.05,\qquad a_{\rm notch}=0.05,\qquad
T=600.
\]

Each initial field has one amplitude-suppressed lattice site,

\[
u_{Y,j}(0)=a_j e^{2\pi i p j/N},\qquad
u_{I,j}(0)=a_j e^{-2\pi i q j/N},\qquad
a_j=\begin{cases}a_{\rm notch},&j=0,\\1,&j\ne0.\end{cases}
\]

The defect is a controlled site at which winding can change during the
amplitude dynamics. The frozen initial sectors are

\[
(p,q)\in\{(1,1),(1,2),(2,3),(3,5),(5,8),(8,13)\}.
\]

Two numerical resolutions constitute the complete protocol:

| Arm | $N$ | $\Delta t$ | steps | $T$ |
|---|---:|---:|---:|---:|
| primary | 64 | 0.02 | 30,000 | 600 |
| resolution control | 96 | 0.01 | 60,000 | 600 |

The integrator is simultaneous forward Euler. Energy is sampled every 100
steps. No fit, random draw, or parameter sweep is permitted.

## Readout and gates

For a nonzero final field, the lattice winding is

\[
w[u]=\operatorname{round}\!\left[
 \frac{1}{2\pi}\sum_j
 \operatorname{Arg}\!\left(\frac{u_{j+1}}{u_j}\right)
\right].
\]

A final sector is counteroriented when $w_Yw_I<0$. Its phase-current ratio is
$r=|w_I/w_Y|$. Co-oriented or zero-winding finals have no counterflow-ratio
readout.

The frozen classifier uses $\delta=0.02$ and targets

\[
\mathcal T=\left\{\varphi,\frac32,\sqrt2\right\}.
\]

The two non-$\varphi$ values are post-dynamics controls only. They do not
enter $H_0$ or the flow equations.

- **PS1—sampled passive descent:** Every arm and seed has
  $H_0(T)<H_0(0)$ and no sampled rise larger than $10^{-10}$.
- **PS2—emergent $\varphi$ selection:** In each arm, at least two final
  counteroriented sectors fall in the $\varphi$ band, and that count exceeds the
  count for each control target.

## Decision rule and stopping rule

- **ADOPT** $M_0$ as a phase-ratio candidate only when PS1 and PS2 pass.
- **REJECT** $M_0$ when PS1 passes and the $\varphi$ count is zero in both
  arms.
- **NULL** for every other protocol-complete outcome.
- **FAIL** only for an implementation or numerical-descent failure.

The run stops after the two frozen arms. A later driven or microscopic model
requires its own pre-registration; it cannot reuse this decision tree.

## References

- `principles/de-resonance-principle.md` §1.4—conditional compact-current
  closure and the transition-law boundary
- `foundations/qi-loop-mass-cascade.md` §6—conditional finite near-closures
  and physical selection boundary
- `computations/phi-counterflow-selection-pre-registration.md`—the preceding
  algebraic counterflow receipt
- `computations/phase-slip-selection-report.md`—protocol-complete $M_0$ receipt and verdict

# Phase-staggered scale-gap probe pre-registration

## Status: Preregistered—August 2026

## 1. Question

Do outward Yang/Yin coherence waves form phase-staggered layers whose intervening nodes sharpen a transition between cascade scales?

The probe separates four claims:

1. adjacent-rung waves generate an alternating-sign beat envelope;
2. ordinary radial propagation turns that envelope into additive shells;
3. the live second-order Cassi wave equation selects the adjacent-rung ratio without a supplied frequency;
4. phase staggering opens a transmission gap.

The first claim is an algebraic consequence of supplied adjacent-rung carriers. The remaining claims require separate evidence.

## 2. Source boundary

The frozen source boundary is:

- `foundations/wake-geometry.md` §§1–3;
- `foundations/bubble-edge-geometry.md` §3;
- `foundations/bubble-lattice-fabric.md` §3;
- `foundations/cassi-first-principles.md` §§1–5;
- `two-fluid/run_wake_structural_probes.py`;
- `two-fluid/run_rung_offset_probe.py`;
- `two-fluid/run_bubble_ring_probe.py`;
- `two-fluid/run_bubble_ring_dynamic_probe.py`;
- `CassiCosmos/compute/cassi_two_fluid.glsl`;
- `predictions/falsifiable-predictions.md` Prediction 51;
- `field-experience/source-only-fieldspace-timing-wave-6-report.md`.

Prediction 51 already records that the undriven canonical PDE and particle space-sim do not generate the prescribed nested radial ladder. Wave 6 records no faster delayed diagonal transfer in the canonical source-only field-space probe. Those frozen results are consumed as controls and are not rerun.

The new experiment tests a source-driven mechanism and therefore does not reopen the rejected undriven radial-ladder arm.

## 3. Fixed constants and coordinates

Use

\[
\varphi=\frac{1+\sqrt5}{2},
\qquad
\varphi-1=\varphi^{-1},
\qquad
1+\varphi=\varphi^2.
\]

Set the reference carrier wavelength to

\[
\ell_n=1,
\qquad
\ell_{n-1}=\varphi^{-1},
\qquad
\ell_{n+1}=\varphi.
\]

The carrier wavenumbers are

\[
k_Y=2\pi,
\qquad
k_I=2\pi\varphi,
\qquad
\Delta k=k_I-k_Y=\frac{2\pi}{\ell_{n+1}}.
\]

For radial normal-mode propagation use dimensionless

\[
c=1,
\qquad
\omega_0=1.
\]

No random number generator, fit-selected frequency, adaptive threshold, or parameter search is permitted.

## 4. Stage A—adjacent-rung beat and phase parity

At one time slice define

\[
Z_Y(x)=A_Ye^{ik_Yx},
\qquad
Z_I(x)=A_Ie^{ik_Ix}.
\]

Demodulate the carrier mean,

\[
B(x)
=
\exp\!\left[-\frac{i(k_Y+k_I)x}{2}\right]
[Z_Y(x)+Z_I(x)].
\]

For equal amplitudes,

\[
B(x)=2A\cos\!\left(\frac{\pi x}{\ell_{n+1}}\right).
\]

The declared antinodes and nodes are

\[
x_m=m\ell_{n+1},
\qquad
x_{m+1/2}=\left(m+\frac12\right)\ell_{n+1},
\qquad
m=0,\ldots,7.
\]

Certificates:

- **A1—scale closure:** $|\Delta k-2\pi/\ell_{n+1}|<10^{-12}$;
- **A2—phase parity:** the normalized real demodulated envelope at $x_m$ equals $(-1)^m$ to $10^{-12}$;
- **A3—node:** the equal-amplitude envelope magnitude at every $x_{m+1/2}$ is below $10^{-12}$;
- **A4—two-rung return:** adjacent antinode correlation is $-1$ and next-nearest correlation is $+1$ to $10^{-12}$.

Stage A is `PASS` only if A1–A4 pass.

## 5. Stage B—unequal-amplitude gap contrast

Freeze amplitude ratios

\[
\eta=\frac{A_I}{A_Y}\in\{1,0.8,0.5\},
\qquad
A_Y=1.
\]

The predicted extrema are

\[
I_{\max}=(A_Y+A_I)^2,
\qquad
I_{\min}=(A_Y-A_I)^2,
\]

and the predicted contrast is

\[
\mathcal C_{\rm gap}
=
\frac{I_{\max}-I_{\min}}{I_{\max}+I_{\min}}
=
\frac{2A_YA_I}{A_Y^2+A_I^2}.
\]

Certificates:

- **B1:** measured extrema agree with the formulas to $10^{-12}$;
- **B2:** measured contrast agrees with the formula to $10^{-12}$;
- **B3:** contrast decreases strictly as $\eta$ moves from $1$ to $0.8$ to $0.5$.

Stage B is `PASS` only if B1–B3 pass. A pass establishes conditional interference contrast. It does not establish an endogenous source-amplitude ratio.

## 6. Stage C—additive and multiplicative layer discrimination

### 6.1 Ordinary beat profile

Use the Stage A antinodes $x_m=m\ell_{n+1}$ for $m=1,\ldots,7$.

Define

\[
R_{\rm add}
=
\max_m
\left|
\frac{x_{m+1}-x_m}{\ell_{n+1}}-1
\right|
\]

and

\[
R_{\log}
=
\sqrt{
\frac1{6}
\sum_{m=1}^{6}
\left[
\log_\varphi\left(\frac{x_{m+1}}{x_m}\right)-1
\right]^2
}.
\]

The ordinary profile is classified additive if

\[
R_{\rm add}<10^{-12},
\qquad
R_{\log}>0.25.
\]

### 6.2 Scale-covariant profile

Define

\[
u=\log_\varphi(r/r_0),
\qquad
Z_{\log}(r,t)=\cos[\pi(u-c_ut)],
\qquad
r_0=1,
\qquad
c_u=1.
\]

At $t=0$, declared antinodes are

\[
r_m=\varphi^m,
\qquad
m=0,\ldots,7.
\]

Certificates:

- **C1:** ordinary beat profile satisfies the additive classification;
- **C2:** $r_{m+1}/r_m=\varphi$ to $10^{-12}$;
- **C3:** $Z_{\log}(r_{m+1},0)=-Z_{\log}(r_m,0)$ to $10^{-12}$;
- **C4:** the log-wave phase surfaces obey $\dot r=c_u\ln\varphi\,r$ to $10^{-12}$.

Stage C is `PASS` only if C1–C4 pass. A pass distinguishes two constructions. It supplies no dynamical origin for the log-radial propagation law.

## 7. Stage D—live wave-equation normal modes

The live CassiCosmos second-order wave equation has the continuum source form

\[
\ddot E_Y
=c^2\nabla^2E_Y-\omega_0^2(E_Y-\varphi E_I)+S_Y,
\]

\[
\ddot E_I
=c^2\nabla^2E_I+\omega_0^2(E_Y-\varphi E_I)+S_I.
\]

Define

\[
\rho=E_Y+E_I,
\qquad
\epsilon=E_Y-\varphi E_I.
\]

Then

\[
\ddot\rho=c^2\nabla^2\rho+S_\rho,
\]

\[
\ddot\epsilon
=c^2\nabla^2\epsilon
-\varphi^2\omega_0^2\epsilon
+S_\epsilon.
\]

The imbalance channel therefore has the frozen propagation threshold

\[
\Omega_g=\varphi\omega_0.
\]

For a harmonic source at frequency $\Omega$,

\[
k_\rho=\frac{\Omega}{c},
\qquad
k_\epsilon=
\frac{\sqrt{\Omega^2-\varphi^2\omega_0^2}}{c}
\quad(\Omega>\Omega_g).
\]

The adjacent-rung condition

\[
\frac{k_\rho}{k_\epsilon}=\varphi
\]

has the unique positive solution

\[
\boxed{
\Omega_*=\varphi^{3/2}\omega_0
}.
\]

### 7.1 Radial solver

For a spherical monopole set

\[
u_a(r,t)=r a(r,t),
\qquad
a\in\{\rho,\epsilon\}.
\]

Each mode is evolved on the half-line approximation

\[
\ddot u_\rho=c^2u_\rho''+rS_\rho,
\]

\[
\ddot u_\epsilon
=c^2u_\epsilon''
-\varphi^2\omega_0^2u_\epsilon
+rS_\epsilon.
\]

Frozen discretization:

| Quantity | Value |
|---|---:|
| $r_{\max}$ | $60$ |
| $\Delta r$ | $0.025$ |
| $\Delta t$ | $0.01$ |
| $t_{\rm end}$ | $220$ |
| source width $\sigma$ | $0.4$ |
| source ramp | $0\le t\le20$ raised cosine |
| phasor window | $190\le t\le220$ |
| absorber start | $r=48$ |
| absorber maximum damping | $2$ |
| fit window | $10\le r\le40$ |

The source profile is

\[
f(r)=r\exp[-r^2/(2\sigma^2)].
\]

The driven source in arm $a$ is

\[
rS_a(r,t)=s_a f(r)R(t)\cos(\Omega t),
\]

where $s_a$ is the arm amplitude and

\[
R(t)=
\begin{cases}
\tfrac12[1-\cos(\pi t/20)],&0\le t<20,\\
1,&t\ge20.
\end{cases}
\]

The damping layer is zero for $r<48$ and rises quadratically to $2$ at $r=60$. Dirichlet conditions $u(0)=u(60)=0$ are fixed. A centered second-order update for the damped wave equation is fixed before execution.

Frozen arms:

| Arm | $\Omega/\omega_0$ | $S_\rho$ | $S_\epsilon$ | Purpose |
|---|---:|---:|---:|---|
| D0 | $0.9\varphi$ | $1$ | $1$ | sub-gap control |
| D1 | $\varphi^{3/2}$ | $1$ | $1$ | supplied adjacent-rung frequency |
| D2 | $2.5$ | $1$ | $1$ | generic propagating control |
| D3 | $\varphi^{3/2}$ | $1$ | $0$ | single-mode control |

The complex phasor is extracted by the fixed final-window projection

\[
\widehat u(r)
=
\frac{2}{30}
\int_{190}^{220}u(r,t)e^{-i\Omega t}\,dt.
\]

For propagating arms, fit the unwrapped phasor phase to $kr+\delta$ by ordinary least squares on the fixed fit window. No fit-window changes are permitted.

Quality gates:

- all arrays and metrics are finite;
- Courant number $c\Delta t/\Delta r=0.4$;
- propagating-mode phase-fit $R^2\ge0.95$;
- fitted wavenumber relative errors are at most $2\%$;
- the phasor amplitude in the fit window exceeds $10^{-6}$;
- D0 imbalance attenuation $|\widehat u_\epsilon(30)|/|\widehat u_\epsilon(12)|\le10^{-2}$.

Physics certificates:

- **D1—channel gap:** D0 has a propagating $\rho$ channel and an evanescent $\epsilon$ channel;
- **D2—tuned ratio:** the fitted D1 ratio $k_\rho/k_\epsilon$ agrees with $\varphi$ within $2\%$;
- **D3—generic control:** the fitted D2 ratio differs from $\varphi$ by at least $0.1$;
- **D4—source requirement:** D3 has no two-mode beat because $S_\epsilon=0$;
- **D5—layer spacing:** D1 relative phase yields at least three constructive and three destructive surfaces in the fit window; their median spacing agrees with $2\pi/|k_\rho-k_\epsilon|$ within $2\%$;
- **D6—phase parity:** the mean-carrier-demodulated D1 field at adjacent constructive surfaces has correlation at most $-0.95$;
- **D7—contrast:** measured D1 node contrast agrees with the contrast predicted from the two fitted modal amplitudes within $0.05$ and exceeds $0.8$.

Stage D is `PASS` only if every quality gate and D1–D7 passes. A pass establishes a driven conditional realization. Because D1 supplies $\Omega_*$, it does not establish frequency selection.

## 8. Stage E—phase staggering and a transmission gap

Represent scale layers by a periodic complex nearest-neighbor chain.

### 8.1 Uniform chain

Use $64$ two-site cells and uniform coupling

\[
K_1=K_2=1.
\]

The staggered transformation

\[
Z_j\mapsto(-1)^jZ_j
\]

is compared with the coupling-sign transformation $K\mapsto-K$. The sorted spectra must agree to $10^{-12}$. The periodic uniform chain must have zero central band gap to $10^{-12}$.

### 8.2 Node-modulated chain

Use

\[
K_1=1.25,
\qquad
K_2=0.75.
\]

The predicted central gap is

\[
\Delta_{\rm chain}=2|K_1-K_2|=1.
\]

For a $12$-cell zero-energy barrier, the declared conditional transmission intensity is

\[
T_{12}
=
\left(\frac{K_2}{K_1}\right)^{24}.
\]

Certificates:

- **E1—phase-only null:** the uniform staggered chain is spectrally gauge-equivalent and has zero central gap;
- **E2—node-modulated gap:** the numerical central gap agrees with $2|K_1-K_2|$ to $10^{-12}$;
- **E3—transmission suppression:** $T_{12}<10^{-4}$.

Stage E is `PASS` only if E1–E3 pass. Its interpretation is fixed: phase staggering alone does not open the gap; physical link or amplitude modulation is sufficient in the declared conditional chain.

## 9. Stage F—canonical real-density boundary

The canonical PDE state contains $(E_Y,E_I,\mathbf u)$ and no compact phase. The positive-root angle and density angle are diagnostics. Prediction 51 records no generated nested radial ladder in the canonical PDE or particle space-sim. Wave 6 records no delayed diagonal transfer advantage.

Stage F performs no new numerical run. It verifies the following source and receipt conditions:

- **F1:** the canonical PDE has no phase variable that can alternate by $\pi$;
- **F2:** Prediction 51 remains `REJECT` for the nested radial ladder;
- **F3:** Wave 6 remains `CONTRADICTS` for faster delayed diagonal transfer;
- **F4:** the new driven second-order wave result is typed separately from canonical first-order density dynamics.

Stage F is `PASS` if all four local boundary checks, F1 through F4, hold.

## 10. Decision tree

Use only the following decisions.

### Beat-layer claim

- `SUPPORTS` if Stages A and B pass.
- `CONTRADICTS` if any exact identity fails.

### Radial-layer claim

- `EMERGES CONDITIONAL` if Stage D passes.
- `DOES NOT EMERGE` if the quality gates pass and D1 has no measured two-mode layer train.
- `INCONCLUSIVE` if any Stage D quality gate fails.

### Automatic $\varphi$ selection

- `SUPPORTS` only if the generic D2 arm selects $k_\rho/k_\epsilon=\varphi$ within $2\%$ without using $\Omega_*$.
- `CONTRADICTS` if only the supplied D1 frequency yields the ratio and D2 differs from $\varphi$ by at least $0.1$.
- `INCONCLUSIVE` if the D2 quality gates fail.

### Phase-gap claim

- `SUPPORTS` if the uniform phase-staggered chain has a nonzero gap.
- `CONTRADICTS` if E1 passes.

### Node-modulated gap claim

- `EMERGES CONDITIONAL` if E2 and E3 pass.
- `DOES NOT EMERGE` if the quality gates pass and either E2 or E3 fails.

### Overall architecture

- `ADOPT` the driven phase-layer diagnostic if Stages A–D pass.
- `REJECT` phase staggering as a sufficient endogenous scale-switch mechanism if automatic $\varphi$ selection or the phase-gap claim is `CONTRADICTS`.
- `ADOPT` node/link modulation as a conditional gap mechanism if Stage E passes.
- Retain the canonical nested radial ladder as `REJECT` unless a new canonical emergence experiment passes its own future preregistration.

## 11. Raw artifact and stopping rule

The single evidentiary execution writes

```text
runs/<UTC timestamp>_phase_staggered_scale_gap/results.json
```

and prints the same gate metrics and verdicts to standard output.

Permitted preflight before the evidentiary execution:

- source inspection;
- `python -m py_compile field-experience/phase_staggered_scale_gap_probe.py`;
- import-only checks that do not call the experiment entry point.

After the protocol and script are frozen, run the experiment once. Do not change constants, windows, thresholds, source amplitudes, or arms after viewing results. A failed gate is a result. A numerical implementation defect may be corrected only with an explicit amendment recorded here before a replacement evidentiary run.

## 12. Amendment A1—sub-gap transient clearance

The first frozen execution is retained at

```text
runs/20260827T093422Z_phase_staggered_scale_gap/results.json
```

Stages A, B, the script-implemented Stage C, and Stage E printed `PASS`. Stage
D failed the declared D0 attenuation gate; the strict post-execution audit in
§13 also flags intentionally undefined D0/D3 reference and fit fields under
the all-metrics-finite rule. The D0 attenuation is

\[
\frac{|\widehat u_\epsilon(30)|}{|\widehat u_\epsilon(12)|}
=1.158827212186.
\]

The D0 lock-in fit isolated a residual travelling component with

\[
k=0.675721302339,
\qquad
R^2=0.990661069340,
\]

even though the locked source frequency obeys

\[
\Omega=0.9\varphi\omega_0<\varphi\omega_0
\]

and therefore has imaginary steady-state $k_\epsilon$. This component is the
broadband turn-on transient still crossing the fit window. Its group speed is
approximately $0.39c$, so the original $t\le80$ horizon ends before it reaches
the absorber.

The amendment changes only:

- $t_{\rm end}:80\rightarrow220$;
- phasor window $[50,80]\rightarrow[190,220]$.

The spatial grid, timestep, source, ramp, absorber, fit window, arms,
thresholds, and decision tree remain frozen. The longer horizon lets the
observed slow transient reach the absorber before the same 30-unit lock-in
measurement. One replacement evidentiary execution is authorized. The first
receipt remains an invalid Stage D quality run rather than physical rejection.

## 13. Post-execution integrity record

The single authorized replacement is retained at

```text
runs/20260827T093616Z_phase_staggered_scale_gap/results.json
```

It still fails D0 attenuation:

\[
\frac{|\widehat u_\epsilon(30)|}{|\widehat u_\epsilon(12)|}
=1.391806981847.
\]

The residual phase fit remains a travelling transient,

\[
k=0.210257903848,
\qquad
R^2=0.982455621465.
\]

The parent Stage D verdict is therefore `INCONCLUSIVE`. No further
time-domain replacement is authorized. The independent closure protocol in
`field-experience/phase-staggered-scale-gap-lock-in-pre-registration.md`
preserves both time-domain receipts and tests the steady-frequency boundary
value problem once.

The post-execution threshold audit found one implementation discrepancy.
Stage C gate C4 is registered at \(10^{-12}\), while the executed script used
\(10^{-9}\). The frozen receipt reports

\[
R_{\dot r}=4.055595092207497\times10^{-11}.
\]

Accordingly, the printed Stage C `PASS` is a pass under the executed
\(10^{-9}\) Boolean and a formal `FAIL` under the registered \(10^{-12}\)
threshold. The exact surface identity

\[
\dot r_m=c_u\ln\varphi\,r_m
\]

still follows analytically from the supplied log-periodic control. The script
source now uses the registered `TOL = 1e-12` gate so that the committed source
matches this protocol; the evidentiary run was not repeated.

The D3 rho-only arm intentionally has \(\widehat u_\epsilon\equiv0\). Its
epsilon phase-fit fields are undefined and serialize as `NaN`. The
`expected_k_epsilon` field is intentionally `null` for D0, where the expected
rate is an evanescent \(\kappa\) rather than a propagating \(k\), and for D3,
where the epsilon channel is absent. The finite quality rule applies to
defined active-channel fits; D3 absence is certified instead by D4, whose
measured epsilon maximum is exactly zero. Under a literal all-metrics reading,
the undefined D0/D3 reference and fit fields are an additional parent quality
failure and do not alter the already `INCONCLUSIVE` Stage D verdict.

The parent architecture does not receive `ADOPT`: registered Stages C and D
do not both pass. The narrower combined verdicts are recorded in
`field-experience/phase-staggered-scale-gap-report.md`.

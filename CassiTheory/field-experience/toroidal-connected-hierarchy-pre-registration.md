# Toroidal Connected-Hierarchy Campaign

## Status: Preregistered—August 2026

## Abstract

This campaign tests three simultaneously evolved physical scale components in one conservative multicomponent Schrödinger–Poisson system. A compact core pair, the V5 toroidal Yang/Yin pair, and a broad outer-shell pair occupy the same periodic domain. Their coupling graph determines which scale densities contribute to each scale pair's gravitational potential.

The primary comparison uses identical initial fields with either full cross-scale gravity or self-gravity alone. Nearest-neighbor and loop-disconnected graphs localize the effect of the scale connections. High-resolution and half-step arms test numerical convergence.

This is the first connected-scale physical proxy in the toroidal program. It supplies labeled scale components on one grid and conserves each component's mass. It does not implement nested grids, conversion of one scale species into another, an open boundary, an environmental source, or a preferred $\varphi$ scale ratio.

No seed search, threshold change, arm addition, or stopping-rule change is permitted after execution begins.

---

## 1. Field system

Let the physical scale label be

\[
s\in\{C,L,E\},
\]

for compact core, toroidal loop, and outer envelope. Each scale carries Yang and Yin complex fields $\psi_{s,Y}$ and $\psi_{s,I}$ with density

\[
\rho_s=|\psi_{s,Y}|^2+|\psi_{s,I}|^2.
\]

Each scale density generates a periodic mean-subtracted Poisson potential,

\[
\nabla^2\Phi_s=\rho_s-\langle\rho_s\rangle,
\qquad \widehat\Phi_s(0)=0.
\]

For a frozen symmetric coupling matrix $C_{sr}$, the evolution is

\[
i\partial_t\psi_{s,a}=
-\frac12\nabla^2\psi_{s,a}
+g\left(\sum_r C_{sr}\Phi_r\right)\psi_{s,a},
\qquad a\in\{Y,I\},
\]

with $g=1$. Symmetry of $C$ gives the conserved Hamiltonian

\[
H=\sum_{s,a}\frac12\int|\nabla\psi_{s,a}|^2\,dV
+\frac{g}{2}\sum_{s,r}C_{sr}\int\rho_s\Phi_r\,dV.
\]

Every scale-pair mass is separately conserved. The experiment tests gravitational energy redistribution and morphological response across connected components; it does not claim inter-species mass conversion.

All arms use a periodic cube of side `16.0`, complex128 fields, float64 diagnostics, and the V5 fourth-order symmetric triple-jump split integrator. The reference time step is `0.0025`, report cadence is `0.25`, and final time is `4.0`.

---

## 2. Frozen scale profiles

Let $r=\sqrt{x^2+y^2+z^2}$ and $r_\perp=\sqrt{x^2+y^2}$. The unnormalized amplitudes are:

### 2.1 Compact core

\[
A_C=\exp\left[-\frac{r^2}{4\sigma_C^2}\right],
\qquad \sigma_C=0.80.
\]

Both core phases are zero.

### 2.2 Toroidal loop

The loop uses the exact V5 closed seed geometry:

- major radius `4.0`;
- opposed strand offset `1.20`;
- strand width `0.60`;
- one spatial winding;
- Yang phase winding `+2`;
- Yin phase winding `-3`.

No V5 field snapshot is imported. The analytic V5 seed formula is reconstructed at each arm's grid resolution.

### 2.3 Outer envelope

\[
A_E=\exp\left[-\frac{(r-R_E)^2}{4\sigma_E^2}\right],
\qquad R_E=6.0,
\qquad \sigma_E=0.80.
\]

Both envelope phases are zero.

Within every scale pair, the Yang-to-Yin mass ratio is $\varphi$. The total scale mass fractions are fixed at

\[
(f_C,f_L,f_E)=(0.25,0.50,0.25).
\]

These rational fractions keep the loop dominant while giving the core and envelope equal control weight. They are protocol choices rather than predicted cascade coefficients.

At reference resolution `N=64`, the three unit-total-mass pairs are combined under the full coupling graph. If their unit-state kinetic and potential energies are $K_1$ and $W_1$, the common total mass is fixed once as

\[
M_*=-\frac{2K_1}{W_1}.
\]

Every arm reconstructs the same physical profiles with masses $f_sM_*$. Resolution arms use the reference `N=64` value of $M_*$; they do not recalibrate it.

---

## 3. Frozen coupling graphs and arms

Rows and columns are ordered `(C,L,E)`.

### Full graph

\[
C_{\rm full}=\begin{pmatrix}
1&1&1\\
1&1&1\\
1&1&1
\end{pmatrix}.
\]

### Decoupled graph

\[
C_{\rm dec}=\begin{pmatrix}
1&0&0\\
0&1&0\\
0&0&1
\end{pmatrix}.
\]

### Nearest-neighbor chain

\[
C_{\rm chain}=\begin{pmatrix}
1&1&0\\
1&1&1\\
0&1&1
\end{pmatrix}.
\]

### Loop-disconnected control

\[
C_{\rm loop\mbox{-}off}=\begin{pmatrix}
1&0&1\\
0&1&0\\
1&0&1
\end{pmatrix}.
\]

The loop evolves under exactly its self-potential in both the decoupled and loop-disconnected arms. The core and envelope remain mutually connected in the latter arm.

| arm | graph | resolution | time step | role |
|---|---|---:|---:|---|
| A | full | 64 | `0.0025` | primary connected hierarchy |
| B | decoupled | 64 | `0.0025` | identical-seed self-gravity control |
| C | chain | 64 | `0.0025` | adjacent-scale sufficiency |
| D | loop-disconnected | 64 | `0.0025` | exact loop-isolation control |
| E | full | 80 | `0.0025` | spatial convergence |
| F | full | 64 | `0.00125` | time-step convergence |

No arm may be added after execution.

---

## 4. Initialization gates

The campaign stops with `INCONCLUSIVE—INVALID INITIALIZATION` unless all gates pass at reference resolution.

### G1—Finite ordered profiles

- every field is finite complex128;
- core mean radius is below `2.0`;
- loop fitted radius lies in `[3.5,4.5]`;
- envelope mean radius lies in `[5.5,6.5]`.

### G2—Mass construction

- each scale mass fraction agrees with `(0.25,0.50,0.25)` within absolute `1e-12`;
- each scale's Yang-to-Yin mass ratio agrees with $\varphi$ within relative `1e-12`.

### G3—Loop identity

- initial loop helical order is at least `0.80`;
- Yang winding is within `0.05` of `+2`;
- Yin winding is within `0.05` of `-3`.

### G4—Full-state virial calibration

\[
\frac{|2K+W|}{|2K|+|W|}\le10^{-10},
\]

with finite $M_*$ in `[0.1,1e6]` and $W_1<0$.

---

## 5. Frozen observables

At every report time the receipt records:

- mass of every scale and Yang/Yin subcomponent;
- kinetic, assigned potential, and assigned total energy of every scale;
- total Hamiltonian and interaction energy;
- mean radius, RMS radius, radial width, maximum density, and fine modal-mass fraction for every scale;
- the V5 loop diagnostics, including fitted radius, core fraction, Yang/Yin windings and normalized phase coherences, helical order, opposed helical moment, and strand opposition.

The assigned scale energy is

\[
E_s=K_s+\frac{g}{2}\int\rho_s\sum_r C_{sr}\Phi_r\,dV,
\qquad H=\sum_sE_s.
\]

Define the normalized endpoint scale-energy changes

\[
\delta_s=\frac{E_s(t_f)-E_s(0)}{|H(0)|},
\]

and exchange amplitude

\[
X=\frac12\sum_s|\delta_s|.
\]

The loop helical and radius retentions are

\[
\mathcal H=\frac{H_L(t_f)}{H_L(0)},
\qquad
\mathcal R=\frac{r_{\rm fit}(t_f)}{r_{\rm fit}(0)}.
\]

Fine modal mass uses the same fixed boundary as the V5 secondary diagnosis, `q >= 8`, and is an endpoint diagnostic. No instantaneous-flux quadrature enters a gate.

The primary writes all scalar series and the six final complex fields for each arm. The independent verifier reconstructs the frozen seed, re-evolves every arm without importing the primary program, recomputes the full series and gates, and compares the final fields.

---

## 6. Numerical-quality gates

### Q1—Completion, precision, and mass conservation

Every arm must complete with finite complex128 fields. For every scale in every arm,

\[
\max_t\frac{|M_s(t)-M_s(0)|}{M_s(0)}\le2\times10^{-9}.
\]

### Q2—Hamiltonian conservation

For every arm,

\[
\max_t\frac{|H(t)-H(0)|}{|H(0)|}\le5\times10^{-3}.
\]

For decoupled arm B, every scale also satisfies

\[
\max_t\frac{|E_s(t)-E_s(0)|}{|H(0)|}\le5\times10^{-3}.
\]

### Q3—Time-step convergence

Between A and F, the absolute differences must be at most:

- `0.08` in loop helical retention;
- `0.05` in loop radius retention;
- `0.03` in every $\delta_s$;
- `0.03` in exchange amplitude $X$.

Their final Yang and Yin winding directions must agree.

### Q4—Resolution convergence

Between A and E, the absolute differences must be at most:

- `0.10` in loop helical retention;
- `0.08` in loop radius retention;
- `0.05` in every $\delta_s$;
- `0.05` in exchange amplitude $X$.

Their final Yang and Yin winding directions must agree.

### Q5—Loop-isolation control

Between B and D, the final loop fields must satisfy

\[
\max_{a\in\{Y,I\}}
\frac{\|\psi_{L,a}^{(B)}-\psi_{L,a}^{(D)}\|_\infty}
{\max(\|\psi_{L,a}^{(B)}\|_\infty,10^{-30})}
\le10^{-10}.
\]

The absolute differences in loop helical retention, loop radius retention, and loop normalized energy change must each be at most `1e-10`.

Any Q1–Q5 failure returns `INCONCLUSIVE—NUMERICAL QUALITY` before a physical classifier is evaluated.

---

## 7. Connected energy-redistribution classifier

Connected scale-energy redistribution is `EMERGES` only when all conditions hold:

1. full arm A has `X >= 0.02`;
2. decoupled arm B has `X <= 0.005`;
3. loop-disconnected arm D has `|delta_L| <= 0.005`;
4. arm A has at least one positive and one negative $\delta_s$.

If numerical quality passes and any condition fails, the result is

```text
DOES NOT EMERGE—CONNECTED SCALE-ENERGY REDISTRIBUTION
```

If all conditions pass, the result is

```text
EMERGES—CONNECTED SCALE-ENERGY REDISTRIBUTION
```

### 7.1 Nearest-neighbor sufficiency

When connected redistribution emerges, the chain is `SUPPORTS NEAREST-NEIGHBOR SCALE CHAIN` when arm C agrees with A within `0.03` in every $\delta_s$ and within `0.03` in $X$. Otherwise it is `CONTRADICTS NEAREST-NEIGHBOR SUFFICIENCY`.

### 7.2 Loop response

Let

\[
\Delta\mathcal H=\mathcal H_A-\mathcal H_B,
\qquad
\Delta\mathcal R=\mathcal R_A-\mathcal R_B.
\]

The connected graph:

- `SUPPORTS LOOP SURVIVAL` when both differences are at least `+0.10`;
- `CONTRADICTS LOOP SURVIVAL SUPPORT` when both are at most `-0.10`;
- has `NO MATERIAL LOOP EFFECT` when both magnitudes are below `0.05` and A/B final winding-survival booleans agree;
- returns `INCONCLUSIVE—MIXED LOOP RESPONSE` otherwise.

This secondary label does not alter the energy-redistribution verdict.

---

## 8. Independent comparison and receipts

Implementation paths:

- primary: `field-experience/toroidal_connected_hierarchy_probe.py`;
- independent verifier: `field-experience/verify_toroidal_connected_hierarchy.py`;
- report: `field-experience/toroidal-connected-hierarchy-report.md`.

Receipt directory:

```text
runs/<UTC>_toroidal_connected_hierarchy/
  results.json
  fields_A.npz
  fields_B.npz
  fields_C.npz
  fields_D.npz
  fields_E.npz
  fields_F.npz
  verification.json
```

The primary receipt hashes this preregistration, both programs, every inherited V2–V5 source used at runtime, and every final-field file. The verifier checks those hashes before recomputation.

Hashes, strings, booleans, integer windings, and gate directions must match exactly. Independently recomputed floating metrics must satisfy

\[
|x-y|\le10^{-9}+10^{-7}\max(|x|,|y|).
\]

Final recomputed fields use the same elementwise tolerance. Any mismatch returns verifier `pass: false`; it does not rewrite the primary verdict.

---

## 9. Stopping rules and interpretation boundary

- Stop the full campaign before evolution if G1–G4 fail.
- Stop an arm on a nonfinite field or density greater than `1e8` times its initial maximum.
- Preserve every receipt from an invalid or stopped run.
- Do not rerun a completed frozen matrix under the same protocol to select a preferred stochastic or numerical outcome. The construction contains no random seed.

A positive result establishes energy redistribution among three labeled, simultaneously evolved scale components through the declared gravitational coupling graph. It does not establish a canonical Cassi hierarchy, mass conversion between levels, nested-domain boundary exchange, endogenous scale formation, a preferred $\varphi$ spacing, particle identity, or stability beyond `t=4`.

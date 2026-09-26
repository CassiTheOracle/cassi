# Whole-Bubble Initial-State and CP-Selection Protocol

## Status: Preregistered—September 2026

## Abstract

This protocol tests whether the cosmological information already present in Cassi can determine the remaining microscopic inputs of the thermal matter-formation benchmark. It replaces the one-flavour leptogenesis approximation with the resolved $\tau$ and coherent $e+\mu$ kinetic system appropriate near $10^9$–$10^{12}\,\mathrm{GeV}$, tests whether strong washout erases the prepared heavy-neutrino abundance and a much larger inherited $B-L$ asymmetry, and varies the two-singlet Casas–Ibarra coordinate while preserving every light-neutrino mass and mixing input. A CP-conjugate pair tests the information carried by real Yang/Yin densities and scalar cascade coordinates. The numerical and structural decisions below are frozen before execution.

## 1. Question and scope

The connected Standard Model comparator in `computations/qcd-cosmological-matter-completion-prereg.md` fixes

$$
z_0=\frac{\pi}{4}+\frac{i}{2},\qquad \frac{M_2}{M_1}=10,
$$

and calibrates $M_1$ to the observed baryon-to-photon ratio. Its local one-flavour kinetic equation is insufficient at the resulting $M_1\sim10^{11}\,\mathrm{GeV}$, where the $\tau$ Yukawa interaction resolves the $\tau$ flavour while $e$ and $\mu$ remain coherent. This protocol asks:

1. Does the empirical comparator remain viable with the leading two-flavour kinetic equations?
2. Does strong washout remove sensitivity to the heavy-neutrino abundance and inherited $B-L$ initial data?
3. Do the registered real-density, scalar-cascade and CP-even neutrino data select the complex Casas–Ibarra coordinate that controls leptogenesis?

The protocol does not infer a seesaw action from the canonical two-density PDE. It tests the strongest current whole-history completion and identifies any information absent from it.

## 2. Frozen particle and cosmological inputs

The calculation uses the same constants as the registered comparator:

| Quantity | Frozen value |
|---|---:|
| Higgs expectation value | $v=174\,\mathrm{GeV}$ |
| Normal-ordering splittings | $\Delta m^2_{21}=7.42\times10^{-5}\,\mathrm{eV}^2$, $\Delta m^2_{31}=2.517\times10^{-3}\,\mathrm{eV}^2$ |
| Lightest mass | $m_1=0$ |
| PMNS inputs | $\sin^2\theta_{12}=0.304$, $\sin^2\theta_{23}=0.573$, $\sin^2\theta_{13}=0.02219$, $\delta_{\rm PMNS}=195^\circ$ |
| Heavy ratio | $M_2/M_1=10$ |
| Benchmark coordinate | $z_0=\pi/4+i/2$ |
| Equilibrium mass | $m_*=1.08\times10^{-3}\,\mathrm{eV}$ |
| Evolution interval | $x=M_1/T\in[10^{-3},50]$ |
| Sphaleron/entropy conversion | $\eta_B=0.96\times10^{-2}\sum_aY_{\Delta_a}$ |
| Observed interval | $5.8\times10^{-10}\le |\eta_B|\le6.4\times10^{-10}$ |
| Reheating condition | $T_R=20M_2$ |

For two singlets and normal ordering,

$$
R(z)=
\begin{pmatrix}
0&0\\
\cos z&-\sin z\\
\sin z&\cos z
\end{pmatrix},
\qquad
Y=\frac{1}{v}U_{\rm PMNS}\sqrt{m}\,R(z)\sqrt{M}.
$$

The benchmark $z_0$ and heavy ratio remain declared inputs. The two-flavour calculation recalibrates only $M_1$ by a bracketed root solve over $10^8$–$10^{13}\,\mathrm{GeV}$.

## 3. Frozen two-flavour equations

Let $H=Y^\dagger Y$. The exact finite-hierarchy loop function is

$$
g(r)=\sqrt r\left[\frac{1}{1-r}+1-(1+r)\ln\left(\frac{1+r}{r}\right)\right],
\qquad r=\frac{M_2^2}{M_1^2}.
$$

For the convention $Y_{\alpha i}$, the flavour asymmetries are

$$
\epsilon_{1\alpha}
=\frac{g(r)}{8\pi H_{11}}
\operatorname{Im}\!\left[Y^*_{\alpha1}Y_{\alpha2}H_{12}\right],
\qquad
\sum_\alpha\epsilon_{1\alpha}
=\frac{g(r)}{8\pi H_{11}}\operatorname{Im}(H_{12}^2).
$$

The resolved channels are $a\in\{e+\mu,\tau\}$, with

$$
\epsilon_{1,e+\mu}=\epsilon_{1e}+\epsilon_{1\mu},\qquad
P_{e+\mu}=\frac{|Y_{e1}|^2+|Y_{\mu1}|^2}{H_{11}},\qquad
P_\tau=\frac{|Y_{\tau1}|^2}{H_{11}}.
$$

Using the same decay and inverse-decay normalization as the comparator,

$$
N_1^{\rm eq}(x)=\frac{x^2K_2(x)}{2},\qquad
D(x)=Kx\frac{K_1(x)}{K_2(x)},\qquad
W(x)=\frac{Kx^3K_1(x)}{4},
$$

$$
\frac{dN_1}{dx}=-D(N_1-N_1^{\rm eq}),
$$

$$
\frac{dY_{\Delta_a}}{dx}
=-\epsilon_{1a}D(N_1-N_1^{\rm eq})-P_aW Y_{\Delta_a}.
$$

Here $K=\widetilde m_1/m_*$ and $\widetilde m_1=H_{11}v^2/M_1$. This is the leading resolved-flavour inverse-decay system. Thermal corrections, spectator matrices, $\Delta L=1$ scattering corrections and a transition-region density matrix remain outside its precision claim.

The primary solve uses `DOP853`, relative tolerance $10^{-10}$, absolute tolerance $10^{-13}$ and maximum step $0.05$. The independent reconstruction uses a separately written `Radau` solve with relative tolerance $3\times10^{-10}$, absolute tolerance $3\times10^{-13}$ and maximum step $0.04$.

## 4. Frozen arms

### 4.1 F1—two-flavour benchmark

Calibrate $M_1$ at fixed $z_0$ so that $|\eta_B|=6.1\times10^{-10}$. Record the Yukawa matrix, $H$, flavour projectors, flavour asymmetries, reconstructed light masses, Davidson–Ibarra bound, $K$, final channel asymmetries and perturbativity maximum.

### 4.2 F2—initial heavy-neutrino abundance

At the calibrated $M_1$, repeat the solve with

$$
N_1(x_i)=f_N N_1^{\rm eq}(x_i),\qquad f_N\in\{0,1,2\},
$$

and zero initial $Y_{\Delta_a}$. The baseline is $f_N=1$.

### 4.3 F3—inherited $B-L$

At the calibrated $M_1$ and $f_N=1$, repeat with total initial

$$
Y_{B-L}(x_i)\in\{-10^{-4},0,+10^{-4}\},
$$

distributed between the two resolved channels in proportion to $P_a$. This contamination is more than $10^3$ times the generated final $B-L$ magnitude.

### 4.4 F4—Casas–Ibarra scan

At the calibrated $M_1$, hold the light masses, PMNS matrix and $M_2/M_1$ fixed. Evaluate the Cartesian grid

$$
\operatorname{Re}z\in\left\{0,\frac\pi8,\frac\pi4,\frac{3\pi}{8},\frac\pi2\right\},
\qquad
\operatorname{Im}z\in\{-1,-\tfrac12,0,+\tfrac12,+1\}.
$$

Record the signed $\eta_B$, $\sum_\alpha\epsilon_{1\alpha}$, projectors, $K$, maximum Yukawa magnitude and mass-reconstruction error at every point. No point is recalibrated.

### 4.5 F5—exact CP pair

Compare

$$
(U,z)=(U_0,\pi/4+i/2)
$$

with

$$
(U,z)=(U_0^*,\pi/4-i/2).
$$

The second Yukawa matrix is $Y^*$ of the first. The pair therefore has equal masses, mixing-angle moduli, $H_{11}$, projectors and washout, while every $\epsilon_{1\alpha}$ changes sign. Both evolutions start from the same CP-symmetric kinetic state, $Y_{\Delta_a}(x_i)=0$.

## 5. Frozen decisions

### FCP1—flavour implementation

`PASS` requires:

- $|\sum_\alpha\epsilon_{1\alpha}-\epsilon_1|/\max(|\epsilon_1|,10^{-300})<10^{-12}$;
- $|P_{e+\mu}+P_\tau-1|<10^{-13}$;
- reconstruction of both nonzero light masses to relative error below $10^{-10}$;
- primary/independent calibrated masses and final $\eta_B$ agreeing to relative error below $10^{-7}$.

Otherwise FCP1 is `FAIL`.

### FCP2—resolved-flavour empirical comparator

`PASS CALIBRATED` requires a root with

$$
10^9<M_1/\mathrm{GeV}<10^{12},\qquad T_R>M_2,
$$

maximum $|Y_{\alpha i}|<1$, $|\epsilon_1|$ below the Davidson–Ibarra bound, and final $|\eta_B|$ inside the observed interval. A root outside the two-flavour range or any failed physical check gives `FAIL`.

### FCP3—heavy-abundance robustness

`SUPPORTS` requires the largest relative difference in final signed $\eta_B$ across $f_N\in\{0,1,2\}$ to be below $10^{-2}$ with a common nonzero sign. A larger dependence gives `CONTRADICTS`; a magnitude below $10^{-14}$ in every arm gives `INCONCLUSIVE`.

### FCP4—inherited-asymmetry erasure

`SUPPORTS` requires the largest relative difference from the zero-contamination final signed $\eta_B$ for initial $Y_{B-L}=\pm10^{-4}$ to be below $10^{-2}$ with a common sign. A larger dependence gives `CONTRADICTS`.

### FCP5—CP-pair degeneracy

`PASS` requires the CP pair to satisfy all of:

- maximum elementwise $|Y_{-}-Y_{+}^*|<10^{-13}$;
- equal projectors and $K$ to relative error below $10^{-12}$;
- equal reconstructed masses to relative error below $10^{-12}$;
- flavour asymmetries and final signed $\eta_B$ cancel pairwise to relative error below $10^{-8}$;
- equal absolute final baryon yields.

Otherwise FCP5 is `FAIL`.

### FCP6—high-energy-coordinate identifiability

`FAIL` is assigned if all 25 scan points reconstruct the same two nonzero light masses below $10^{-10}$ relative error while the scan contains:

- at least one $|\eta_B|<10^{-20}$ point;
- at least one $\eta_B>10^{-12}$ point;
- at least one $\eta_B<-10^{-12}$ point.

This outcome means the light-neutrino data admit zero, matter-sign and antimatter-sign histories through an unmeasured complex coordinate. `PASS` requires the registered inputs to force one nonzero sign throughout the scan. Any other outcome is `INCONCLUSIVE`.

### FCP7—whole-bubble CP selector

The source inventory is tested for a physical CP-odd state variable or boundary datum with a derived map to the Casas–Ibarra coordinate. Real $E_Y,E_I$, $q$, $\rho$, the scalar Wu Xing label, scalar cascade positions and CP-even thermal densities are invariant under complex conjugation. A mapped CKM phase does not define the independent neutrino Yukawa coordinate without a quark–lepton flavour relation.

FCP7 is `PASS` only if the registered action and cosmological initial state contain such a CP-odd variable and derive its map to $z$. It is `FAIL` if the CP pair in F5 is indistinguishable by every registered whole-bubble input and the map is absent. This structural decision cannot be changed by fitting $M_1$ or choosing one scan point.

## 6. Overall verdict

The empirical initial-state question `SUPPORTS` if FCP1–FCP2 pass and FCP3–FCP4 support. The CP-selection question `DOES NOT EMERGE` if FCP5 passes while FCP6 and FCP7 fail. Complete Cassi matter formation remains `FAIL` under that branch: the standard thermal history is viable and insensitive to the tested abundance preparation, while the sign-generating microscopic coordinate remains an independent input.

A positive complete-mechanism verdict requires a future action to introduce a physical CP-odd degree of freedom, derive its state from the cosmological boundary problem, and derive a quark/lepton texture map that selects $z$ before baryon data are used.

## 7. Outputs and stopping rule

The primary program writes

- `runs/20260910_qcd_whole_bubble_cp_selection/primary/results.json`;
- `runs/20260910_qcd_whole_bubble_cp_selection/primary/report.md`.

The independent program writes

- `runs/20260910_qcd_whole_bubble_cp_selection/verification/verification.json`;
- `runs/20260910_qcd_whole_bubble_cp_selection/verification/report.md`.

The protocol, primary source and listed source inputs are SHA-256 bound in both receipts. Run the primary once and the independent reconstruction once. Apply the frozen decisions without changing the grid, thresholds, initial data, kinetic equations or benchmark texture.

## References

- `computations/qcd-cosmological-matter-completion-prereg.md`—connected Standard Model matter-history comparator
- `computations/qcd_cosmological_matter_completion.py`—one-flavour benchmark and QCD transfer implementation
- `computations/matter-formation-continuum-report.md` §83—current empirical completion boundary
- `foundations/baryon-asymmetry.md`—Cassi baryogenesis status and comparator
- `standard-model/cp-violation.md`—mapped quark-sector phase and missing canonical phase fibre
- `foundations/unified-lagrangian.md` §1—canonical real-density state
- A. Abada et al., [“Flavour Matters in Leptogenesis”](https://arxiv.org/abs/hep-ph/0605281)—flavoured CP asymmetries and resolved-flavour Boltzmann equations
- S. Davidson, E. Nardi and Y. Nir, [“Leptogenesis”](https://arxiv.org/abs/0802.2962)—thermal leptogenesis review

# Cosmology—Dark Energy, Inflation, and Observational Constraints

## Status: Index—August 2026

## Abstract

This directory develops the Cassi cosmology from the two-fluid backbone: the inflation mechanism is Hypothesized with a Mapped cascade/e-fold window, baryogenesis carries a Hypothesized mechanism with a Mapped $\eta$ exponent, and the dark-matter condensate has a Derived base ratio conditional on the Weinberg-angle identification with an open 21% residual. It includes the candidate inflation analysis at cascade rungs 20–60, compiled external measurements (DESI DR2 and Milky Way rotation curves), and a computational plan for testing the $\sigma_8$ mechanism with a modified Boltzmann pipeline. Ordered for the reading path: framework derivation first, then the inflation deep-dive, observational constraints, and finally the computational plan.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `cosmology-from-phi.md` | Inflation, baryogenesis, dark matter | Mixed: Derived structure / Hypothesized baryogenesis / Mapped $\eta$ / conditional DM base |
| 2 | `inflation-from-cascade.md` | Candidate inflation epoch, CMB observables | Mixed: Hypothesized mechanism / Mapped rung-to-e-fold window |
| 3 | `observational_constraints.md` | DESI DR2, Milky Way rotation curve | Calibrated $w_0,\xi$ / Mapped halo component proxy; attractive-branch comparison |
| 4 | `sigma8-computational-plan.md` | $\sigma_8$ Boltzmann pipeline | Plan (Hypothesized) |

## Document Summaries

### `cosmology-from-phi.md`—Cassi Cosmology: Inflation, Baryogenesis, and Dark Matter from $\varphi$

The entry point for cosmology in the Cassi framework: the canonical two-fluid dynamics organize the three sectors, while their expanding-universe interpretation requires a separate Hypothesized Hubble closure. The proposed closure uses $V_{\text{new}}=\lambda\widetilde h(E_Y,E_I)+\lambda\varphi^{-2}/d$, with $d=3$ assumed; neither that spatial identification nor the conversion-to-expansion map is supplied by the canonical solver. Inflation is a Hypothesized gate-driven phase transition with Mapped cascade observables; baryogenesis uses the Mapped $\eta=\varphi^{-44}$ exponent with its freeze-out endpoint open; and the dark-matter base is $\Omega_{\text{DM}}/\Omega_b=\varphi^3\approx4.24$ conditional on the Weinberg-angle identification, while the $+1$ capture construction is excluded by component accounting.

### `inflation-from-cascade.md`—Inflation from Cascade Steps 20–60: The Qi-Gate Epoch

Places a candidate inflationary epoch at cascade rungs $n\approx20$–$60$. The ladder difference $60-20=40$ is exact arithmetic; identifying the interval with inflation and one rung with one e-fold is Mapped and conditional. Along the declared low-$r$ trajectory normalization, the Qi gate is open as $r=E_Y/E_I$ rises toward its fixed point; the proposed end threshold $r=\varphi^{-1}$ is a separate Hypothesized choice before the fixed point $r=\varphi$. The closed forms $n_s=1-2/(N_e\varphi)\approx0.9691$ and $r=12/N_e^2=0.0075$ compare favorably with individual CMB constraints at $N_e=40$, while the tested gate trajectory gives $(n_s,r)=(0.813,0.188)$ or $(0.914,0.060)$, so the catalog values do not coexist on that trajectory and its $r$ values exceed the BK18 bound. The running $\alpha_s=-2\varphi^{-1}/N_e^2\approx-7.7\times10^{-4}$ is likewise a Hypothesized closed form. Tier: mixed Mapped/Hypothesized; only the ladder arithmetic is Derived.

### `observational_constraints.md`—Observational Constraints—DESI DR2 Dark Energy & Milky Way Rotation Curve

Compiles the external measurements that anchor Cassi cosmology, each with its source and 68% error bars: DESI DR2 BAO (arXiv:2503.14738) and independent analyses show a 2.8–4.5σ preference for dynamical dark energy in the quintom-B quadrant ($w_0 > -1$, $w_a < 0$); the calibrated $\varphi$-attractor baseline is $w_0 = -0.87$, $2\sigma$ from DESI's $w_0 \approx -0.75 \pm 0.06$ [INFERENCE] at the Calibrated baseline ($3.6\sigma$ at fixed $r_0$ with the B2 coupling; the conditional C1 friction closure gives the pure-$\Lambda$ window fit $(w_0, w_a) = (-1, 0)$, 4.17σ/2.61σ from DESI)—tension, not a match at the baseline. The Milky Way rotation curve section collects Eilers et al. 2019 ($v_c(R_\odot) = 229.0 \pm 0.2$ km/s), the Jiao et al. 2023 Keplerian decline, and a conditional attractive-branch comparison.

### `sigma8-computational-plan.md`—Sigma-8 Computational Plan: Modified Boltzmann Pipeline for Cassi Qi-Gravity

A forward-looking computational plan (status: Plan; epistemic: Hypothesized, goal Derived) to compute $\sigma_8(z)$ by integrating density-dependent Qi-gravity into a Boltzmann code. The growth equation uses the canonical two-fluid coherence $q_{\mathrm{solver}}\in[0,1]$ computed from $E_Y,E_I$: $\boxed{G_{\text{eff}}(x) = \frac{\pi}{\rho(x)}\left(1 + (\varphi^{6}-1)q_{\mathrm{solver}}(x)\right) G_N}$ with $\xi = \varphi^6 \approx 17.944$. The geometric condensation field is separate: $C\in[-1,1]$ has the explicit squared plan proxy $q_{\mathrm{proxy}}^{C}=(1+C)^2/2\in[0,2]$, while the 3D $B$ extension has $q_{\mathrm{proxy}}^{B}=(1+B)^2/2\in[0,2]$; neither proxy is canonical or may enter $G_{\mathrm{eff}}$ directly. The required $q_{\mathrm{proxy}}^{C/B}\to q_{\mathrm{solver}}\to G_{\mathrm{eff}}$ constitutive map is Hypothesized/open, with $\mathcal{M}_{\mathrm{proxy}\to q}:[0,2]\to[0,1]$, and must be measured or derived separately. An analytic estimate without the Boltzmann code gives $\boxed{\sigma_8^{\text{Cassi}}/\sigma_8^{\Lambda\text{CDM}} \approx 0.90\text{–}0.95}$ ($\Delta\sigma_8/\sigma_8 \approx -5\%$ to $-10\%$), matching the ~5% Planck-versus-weak-lensing suppression; the ~5% band is a Mapped target (2026-08-06 reconciliation, `computations/sigma8_reconciliation.py`); the truth campaign 2026-08-07 (`runs/44-truth-campaign/`) measures the pipeline's rows at the doctrine IC with the linear-P(k) normalization: the total −20.5% (resolution-converged N = 32/64/128) and the mechanism-attributable +29.7% ($G_{\text{eff}} = 1.297$, r₀-dependent: +29.4% at the derived $r_0 = 0.0472$); the doctrine rows (2026-08-07) are −16.6% (R = 0.834, closure regime-integrated) and −15.2% (band-state mean-field) under the P-A reading at the derived $r_0 = 0.0472$. The document lays out the full pipeline—PDE runs at $N = 64$ to output canonical $q_{\mathrm{solver}}(x,z)$, form density-weighted cross/auto spectra, and construct validated bounded $q_{\mathrm{eff}}(k,z)$, CLASS PPF parameterization vs source modification, data constraints on canonical $q_{\mathrm{solver}}(r,z)$ from rotation curves, a parameter summary, a timeline, and explicit success criteria for reaching Derived status. Tier: Plan (Hypothesized).
The displayed $G_{\text{eff}}$ is a coupling magnitude. The canonical
$+\pi[1+(\varphi^6-1)q]\nabla\Phi$ force is outward for positive $\pi$; the
attractive sign used by the growth equation is a separate Hypothesized
sign-changing branch.

## Cross-References

- `foundations/dimensionful-cascade.md`—cascade rung table behind inflation-from-cascade.md
- `foundations/refined-numeric-predictions.md`—$\sigma_8$ pipeline status (§2.9, §5.2)
- `predictions/falsifiable-predictions.md`—the 54-entry prediction catalog (CMB §2, $\sigma_8$)
- `open-questions-cassi-answers.md`—the 42-entry epistemic registry (§T3, $\sigma_8$ tension)

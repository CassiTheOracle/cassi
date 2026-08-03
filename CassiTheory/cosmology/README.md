# Cosmology—Dark Energy, Inflation, and Observational Constraints

## Status: Index—July 2026

## Abstract

This directory builds the Cassi cosmology from the two-fluid backbone: the framework-level derivation that solves inflation, baryogenesis, and dark matter from $\varphi$ alone, a dedicated analysis of inflation as the Qi-gate epoch at cascade rungs 20–60, the compiled external measurements (DESI DR2, Milky Way rotation curve) that anchor the predictions, and a computational plan to upgrade the $\sigma_8$ prediction from Hypothesized to Derived via a modified Boltzmann pipeline. Ordered for the reading path: framework derivation first, then the inflation deep-dive, the observational constraints, and finally the forward-looking computational plan.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `cosmology-from-phi.md` | Inflation, baryogenesis, dark matter | Derived |
| 2 | `inflation-from-cascade.md` | Inflation epoch, CMB predictions | Derived |
| 3 | `observational_constraints.md` | DESI DR2, Milky Way rotation curve | Derived |
| 4 | `sigma8-computational-plan.md` | $\sigma_8$ Boltzmann pipeline | Plan (Hypothesized) |

## Document Summaries

### `cosmology-from-phi.md`—Cassi Cosmology: Inflation, Baryogenesis, and Dark Matter from $\varphi$

The entry point for cosmology in the Cassi framework: it shows that three open problems—inflation, baryogenesis, and dark matter—follow from the same two-fluid PDE in an expanding universe, with the Hubble rate split into $H = H_{\text{empty}} + H_{\text{conv}} + H_{\text{struct}}$ and $H_{\text{empty}} = \lambda\varphi^{-2}/3$. Inflation is a $\varphi$-driven phase transition from a Yang-dominated state ($r \gg \varphi$) toward the attractor; baryogenesis scales with the sphaleron freeze-out temperature through $\boxed{\eta = B_s \varphi^{-1} T_{\text{sph}}/M_{\text{Pl}}}$; and dark matter is a high-Qi condensate with $\boxed{\Omega_{\text{DM}}/\Omega_b = \xi/\varphi^3 = \varphi^3 \approx 4.24}$, rising to $\varphi^3 + 1 \approx 5.24$ once captured baryons are included (2.8% from the measured 5.39). It closes with a one-page timeline and a parameter-free prediction table ($n_s$, $r$, $\mathcal{P}_\zeta$, $\eta$)—zero new free parameters beyond $\varphi$ and the two-fluid PDE constants $(\lambda, \chi, D)$. Tier: Derived.

### `inflation-from-cascade.md`—Inflation from Cascade Steps 20–60: The Qi-Gate Epoch

Places inflation at cascade rungs $n \approx 20$–$60$: the Qi gate $(1-q)$ acts as the inflaton, driving near-constant $H \propto \lambda(1-q)$ while open and terminating expansion through its own shape when $r$ crosses the pinch at $r = \varphi^{-1}$—graceful exit with no separate inflaton field or fine-tuned potential. The e-fold count is fixed by the cascade span, $N_e = \ln(\ell_{60}/\ell_{20})/\ln\varphi = 40$, fewer than standard slow-roll; the horizon problem is instead resolved independently by cascade emergence (C6). The boxed CMB predictions are $n_s = 1 - 2\varphi^{-1}/N_e = 1 - 2/(N_e\varphi) \approx 0.967$ (0.5σ from Planck) and $r \approx \varphi^{-6}\cdot(16/\pi)\cdot 0.5 \approx 0.003$, testable with CMB-S4/LiteBIRD, with running $\alpha_s = -2/N_e^2 \approx -0.0013$. An explicit epistemic-boundaries section (§8) separates the Derived claims from the Hypothesized, testable ones. Tier: Derived.

### `observational_constraints.md`—Observational Constraints—DESI DR2 Dark Energy & Milky Way Rotation Curve

Compiles the external measurements that anchor Cassi cosmology, each with its source and 68% error bars: DESI DR2 BAO (arXiv:2503.14738) and independent analyses show a 2.8–4.5σ preference for dynamical dark energy in the quintom-B quadrant ($w_0 > -1$, $w_a < 0$); the parameter-free $\varphi$-attractor prediction is $w_0 = -0.87$ (corrected 2026-07-31), $2\sigma$ from DESI's $w_0 \approx -0.75 \pm 0.06$ [INFERENCE]—tension, not a match. The Milky Way rotation curve section collects Eilers et al. 2019 ($v_c(R_\odot) = 229.0 \pm 0.2$ km/s), the Jiao et al. 2023 Keplerian decline beyond 19 kpc, and Zhou et al. 2023 extended to 30 kpc. The final section documents the $w_a$ tension (corrected 2026-07-31: not resolved): the bare structural prediction $w_a = +0.46$ shifts by $\Delta = -0.45$ to $+0.012$ once the Yang-fraction-weighted $\xi = \varphi^6$ coupling enters $H(a)$ (via `two-fluid/calibrate_initial_ratio_xi_v2.py`), $2.7\sigma$ ($2.2$–$3.2\sigma$) from DESI DR2's $w_a \approx -0.73 \pm 0.28$ [INFERENCE] (Table 9; $-0.6$ to $-1.1$ across SNe compilations). CMB large-angle anomalies (the "axis of evil") are also surveyed. Tier: Derived.

### `sigma8-computational-plan.md`—Sigma-8 Computational Plan: Modified Boltzmann Pipeline for Cassi Qi-Gravity

A forward-looking computational plan (status: Plan; epistemic: Hypothesized, goal Derived) to compute $\sigma_8(z)$ by integrating density-dependent Qi-gravity into a Boltzmann code. The core mechanism is $\boxed{G_{\text{eff}}(x) = \frac{\pi}{\rho(x)}\left(1 + \xi q(x)\right) G_N}$ with $\xi = \varphi^6 \approx 17.944$, where $q$ follows the condensation field via $q(C) = (1+C)/2$ and the geometric factor $\pi/\rho$ dilutes the enhancement in cluster cores. An analytic estimate without the Boltzmann code gives $\boxed{\sigma_8^{\text{Cassi}}/\sigma_8^{\Lambda\text{CDM}} \approx 0.90\text{–}0.95}$ ($\Delta\sigma_8/\sigma_8 \approx -5\%$ to $-10\%$), matching the ~5% Planck-versus-weak-lensing suppression. The document lays out the full pipeline—PDE runs at $N = 64$ to extract $q(k, z)$, CLASS PPF parameterization vs source modification, data constraints on $q(r, z)$ from rotation curves, a parameter summary, a timeline, and explicit success criteria for reaching Derived status. Tier: Plan (Hypothesized).

## Cross-References

- `../foundations/dimensionful-cascade.md`—cascade rung table behind inflation-from-cascade.md
- `../foundations/refined-numeric-predictions.md`—$\sigma_8$ pipeline status (§2.9, §5.2)
- `../predictions/falsifiable-predictions.md`—the 46-entry prediction catalog (CMB §2, $\sigma_8$)
- `../open-questions-cassi-answers.md`—the 41-entry epistemic registry (§T3, $\sigma_8$ tension)

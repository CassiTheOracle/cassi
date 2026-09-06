# Hyperbolic Carrier Parent and Gaussian Pair Production

## Status: Hypothesized parent family / Derived conditional calculation specification—September 2026

## Abstract

This calculation asks whether the first-order carrier equation admits a positive-inertia temporal parent with a signed conserved charge and a quantum pair-production channel. The parent coefficient is unselected. The calculation checks a conditional correspondence to a standard free-field mass quench; it assigns no physical matter-formation verdict, particle identity, preferred coefficient, or nonlinear formation history. The first-order action and all completed stationary and stability campaigns remain unchanged.

## 1. Declared parent family

Work in the dimensionless, scale-independent, trivial scalar sector of `foundations/particle-stationary-action-closure.md` §8.7. Add the Hypothesized term $a|\partial_t\chi|^2$ with $a>0$ to the carrier Lagrangian, retaining its first-order term and spatial functional:

$$
\mathcal L_a=a|\dot\chi|^2+
\frac{i}{2}(\chi^*\dot\chi-\dot\chi^*\chi)
-\frac{k_{Cx}}2|\nabla\chi|^2-U_C(f)|\chi|^2
-\frac{u_C}{2}|\chi|^4,
\qquad U_C(f)=e_C-h_C(1-f^2).
$$

The quantum benchmark fixes the mathematical normalization $S/\hbar=\int\mathcal L_a\,dt\,d^3x$. Physical matching has an additional action prefactor $\mathcal N_Q=\rho_0\ell_Q^3$, which is unselected. With that prefactor restored, the canonical field is $\phi=\sqrt{\mathcal N_Qa}\,e^{-it/(2a)}\chi$ and its quartic coefficient is $u_C/(2\mathcal N_Qa^2)$. The free-mode frequencies and dimensionless occupations below are independent of this prefactor; field fluctuation amplitudes and mediator backreaction depend on it.

The conditional equation and conserved density are

$$
a\ddot\chi-i\dot\chi-\frac{k_{Cx}}2\Delta\chi+
[U_C(f)+u_C|\chi|^2]\chi=0,
\qquad
\rho_a=|\chi|^2-2a\operatorname{Im}(\chi^*\dot\chi),
\qquad \mathbf j_a=k_{Cx}\operatorname{Im}(\chi^*\nabla\chi).
$$

The uniform phase rotation $\chi=a^{-1/2}e^{it/(2a)}\phi$ gives a canonical complex scalar with carrier principal speed squared $v_a^2=k_{Cx}/(2a)$ and mass squared $M_a^2(f)=1/(4a^2)+U_C(f)/a$. The transformed quartic is $u_C|\phi|^4/(2a^2)$ in the benchmark normalization. Matching the other field sectors to this causal cone is a separate physical requirement. A classical zero field with zero velocity remains zero. Quantum creation below uses the normalized in-vacuum of the quadratic carrier Hamiltonian.

For a spatial eigenvalue $\epsilon$, the two temporal roots obey $a\omega^2+\omega=\epsilon$ and carry opposite signs of $1+2a\omega$. The low root tends to $\epsilon$ as $a\to0^+$. A stationary first-order profile with multiplier $\omega_C$ is inherited at $\omega+a\omega^2=\omega_C$, but its conserved charge becomes $\mathcal Q_a=(1+2a\omega)Q_C$. Fixed-$Q_C$ Hessian results are therefore not adopted as fixed-$\mathcal Q_a$ dynamical stability.

## 2. Inputs and parameter provenance

Use $k_{Cx}=u_C=1$, $u_\rho=4$, $e_C=0.75$, $h_C=2.9598260763447164$ from the completed scalar campaign. The coupling remains Mapped and physically uncalibrated. The parent values $a\in\{1/16,1/32,1/64\}$ are fixed mathematical witnesses; no value is selected as physical. Dimensionless momenta are $k\in\{0,1,2\}$ and transition times are $T\in\{0.05,0.25,1\}$. These choices are numerical problem data and are not fits or physical predictions.

The stationary correspondence table reads `runs/20260906_matter_formation_radial/results.json`, raw SHA-256 `3ac6ec265c11d8eed2040c372d8862084be084ad0a640bbe0d8655e06e19a313`, and only its qualified bound endpoints `q16_R12_n768_refine` and `q256_R12_n768_refine`. Their NPZ hashes are respectively `335364c4e655de4a34b51c0558c3a7559f45311d7f2973b262de4fd2c61db7be` and `95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a`. Check those byte identities; no field relaxation is permitted. Report each original $Q_C,\omega_C$ and the low-root $\omega,\mathcal Q_a$ for each $a$. This is an algebraic correspondence table, not a new stationary qualification.

## 3. Free quantum mode problem

Prescribe the homogeneous mediator history

$$
f^2(t)=1-\frac A2[1+\tanh(t/T)],\qquad
\Omega_k^2(t)=\frac{k_{Cx}k^2}{2a}+\frac1{4a^2}+\frac{U_C(f(t))}{a}.
$$

The source supplies external work. The Gaussian calculation drops carrier self-interaction and mediator backreaction; it does not approximate them as measured negligible effects. Verify $\Omega_k^2>0$ throughout every declared trajectory. The in/out frequencies are the positive square roots of the asymptotic coefficients. Evolve the complex mode by

$$
\ddot u_k+\Omega_k^2(t)u_k=0,
\qquad u_k(t_i)=\frac{e^{-i\Omega_{\rm in}t_i}}{\sqrt{2\Omega_{\rm in}}},
\qquad \dot u_k(t_i)=-i\Omega_{\rm in}u_k(t_i).
$$

Evolve a real work variable alongside it, $\dot W_k=\dot\Omega_k^2|u_k|^2$, initially zero. The energy convention is the complex-field mode pair: $E_k=|\dot u_k|^2+\Omega_k^2|u_k|^2$, in-vacuum energy $\Omega_{\rm in}$ and out excess energy $2\Omega_{\rm out}|\beta_k|^2$. The signed net charge of the produced particle–antiparticle pair vanishes by the global symmetry; a zero assigned net charge is not an independent numerical measurement.

At $t_f$, project

$$
\alpha_k=e^{i\Omega_{\rm out}t_f}
\left(\sqrt{\frac{\Omega_{\rm out}}2}u_k+
\frac{i\dot u_k}{\sqrt{2\Omega_{\rm out}}}\right),\qquad
\beta_k=e^{-i\Omega_{\rm out}t_f}
\left(\sqrt{\frac{\Omega_{\rm out}}2}u_k-
\frac{i\dot u_k}{\sqrt{2\Omega_{\rm out}}}\right).
$$

The independent analytic benchmark is

$$
n_k^{\rm exact}=|\beta_k|^2=
\frac{\sinh^2[\pi T(\Omega_{\rm out}-\Omega_{\rm in})/2]}
{\sinh(\pi T\Omega_{\rm in})\sinh(\pi T\Omega_{\rm out})}.
$$

This known tanh-quench result is used only as a correspondence benchmark. Momentum integrals, renormalized stress, asymptotic scaling fits and total physical production rates are outside this calculation.

## 4. Frozen execution schedule

Run all 27 Cartesian products of the three $a$, three $k$ and three $T$ values with $A=1$ and $t\in[-16T,16T]$. Add three constant-background controls, one per $a$, with $k=0,T=0.25,A=0$. Add one time-window control with $a=1/16,k=0,T=0.05,A=1$ on $[-24T,24T]$. Total: 31 mode trajectories.

The primary uses SciPy `solve_ivp`, method `DOP853`, real state $(\Re u,\Im u,\Re\dot u,\Im\dot u,W)$, `rtol=1e-11`, `atol=1e-13`, and maximum step $\min(T/16,1/(16\Omega_{\rm in}),1/(16\Omega_{\rm out}))$. Store uniform samples separated by $T/256$: 8193 samples for half-span 16 and 12289 for half-span 24. Initial data use asymptotic in frequency at the finite start; the larger-window control checks this truncation at the declared fast witness. Do not retry, expand the schedule or adjust tolerances after observing the outcome.

Also report the two dispersion roots and signed norm factors at $\epsilon\in\{-0.5,0,0.75,2\}$ for all three $a$. Evaluate the low root as $2\epsilon/[1+\sqrt{1+4a\epsilon}]$ to avoid cancellation. Check the quadratic identities and opposite norm signs at tolerance $10^{-12}$ with denominator $\max(1,|x|,|y|)$. A symbolic derivation must check the phase rotation, Noether sign and stationary embedding independently of the primary source.

## 5. Measurements and correspondence decision

For every trajectory record the endpoint $\alpha,\beta$, numerical and analytic $n_k$, maximum sampled Wronskian defect $|i(u^*\dot u-\dot u^*u)-1|$, $||\alpha|^2-|\beta|^2-1|$, endpoint energy, accumulated work and the energy-work defect. Require:

- occupation agreement $|n_k-n_k^{\rm exact}|\le10^{-10}+10^{-7}n_k^{\rm exact}$;
- Wronskian and Bogoliubov identity defects at most $10^{-8}$;
- energy-work defect at most $10^{-8}\max(1,|E_i|,|E_f|,|W|)$;
- constant-background control occupations at most $10^{-12}$;
- the two time-window witness occupations differing by at most $10^{-9}$;
- at $a=1/16,k=0,T=0.05,A=1$, numerical occupation greater than $10^{-4}$;
- for each $a,k$, the $T=1$ occupation is below the $T=0.05$ occupation by more than $10^{-9}$.

The correspondence verdict is `PASS` only if every input identity, completed trajectory, algebraic check and declared numerical comparison passes. Any executed check failure yields `FAIL`; an infrastructure exception yields a failed receipt and exit code 1. There is no physical adoption rule. Passing a standard Gaussian mass-quench benchmark leaves the parent coefficient, microscopic carrier interpretation, backreaction, nonlinear localization, stability and physical normalization open.

## 6. Independent verification and receipt contract

The primary is `computations/matter_formation_hyperbolic_parent.py`; the independent program is `computations/verify_matter_formation_hyperbolic_parent.py`. They may not import each other. The independent verifier reconstructs the expected schedule from this specification, checks every raw input and trajectory hash, recomputes endpoint projections, Wronskians and energy from the saved arrays, evaluates the analytic benchmark independently, and integrates the source-work integrand with composite Simpson quadrature. Require its quadrature result to agree with stored accumulated work within $10^{-7}\max(1,|W|)$. Other independently reconstructed scalar comparisons use tolerance $10^{-10}\max(1,|x|,|y|)$ unless the stricter or dedicated limit above applies.

The default output is `runs/20260906_matter_formation_hyperbolic_parent/`. Never overwrite an existing result, trajectory or verification receipt. The primary supports `--output-dir`; the verifier supports `--input-dir` and optional `--output-dir`. Canonical source/specification hashes normalize CRLF to LF; JSON and NPZ hashes use raw bytes. Record Python, NumPy and SciPy versions.

`results.json` uses schema `cassi.matter-formation.hyperbolic-parent.v1`, top-level `prereg_sha256`, `source_sha256`, `verifier_sha256`, `input_sha256`, `settings`, `coefficients`, `dispersion`, `stationary_embeddings`, `rows`, `comparisons`, `failures`, `verdict` and `pass`. Each trajectory row has `id`, `a`, `k`, `T`, `amplitude`, `half_span`, `artifact`, `artifact_sha256`, and a `measurements` object. Identifiers are `a{denominator}_k{integer}_T{milliseconds}_L{half_span}_A{amplitude}`. Each NPZ contains one-dimensional arrays `t` (float64), `u` and `v` (complex128), `work` and `omega2` (float64); `v` is $\dot u$. Measurement keys are `omega_in`, `omega_out`, `alpha_re`, `alpha_im`, `beta_re`, `beta_im`, `occupation`, `occupation_exact`, `wronskian_defect`, `bogoliubov_defect`, `energy_initial`, `energy_final`, `work_final`, `energy_work_defect`. The verifier's `verification.json` has its own canonical source hash, the raw primary-result hash, mismatch details, independently reconstructed rows, `verdict` and `pass`.

The `dispersion` rows use `a`, `epsilon`, `omega_low`, `omega_high`, `norm_low`, `norm_high`, `residual_low` and `residual_high`. The `stationary_embeddings` rows use `source_id`, `artifact`, `artifact_sha256`, `a`, `Q_C`, `omega_C`, `omega_parent` and `signed_charge`. The `comparisons` object uses `time_window_occupation_difference`, `fast_witness_occupation` and `adiabatic_differences`; the latter is a list of `a`, `k` and `fast_minus_slow`. Both programs determine acceptance from reconstructed quantities, including input qualification, finite arrays and the exact expected row set. An empty or partial row set cannot pass.

## References

- `foundations/particle-stationary-action-closure.md` §§3.2, 7.3, 8.7—current action, temporal groups and exact empty-sector obstruction.
- `computations/matter-formation-continuum-report.md`—qualified prepared scalar states and existing scope boundaries.
- [Das, Galante and Myers, *Smooth and fast versus instantaneous quenches in quantum field theory*, arXiv:1505.05224](https://arxiv.org/abs/1505.05224)—free scalar tanh quench and Bogoliubov coefficients.
- [Camilo and Abdalla, *Momentum-space entanglement after smooth quenches*, European Physical Journal C 79, 48 (2019)](https://doi.org/10.1140/epjc/s10052-019-6581-2)—general in/out-mass tanh profile and exact occupation formula.

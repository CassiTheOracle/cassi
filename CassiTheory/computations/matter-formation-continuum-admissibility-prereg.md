# Continuum Admissibility and Two-Body Localization of the Scalar–Fermion Candidate

## Status: Frozen conditional continuum and localization protocol—September 2026

## Abstract

The declared finite-mode scalar–fermion model has verified pair excitation and semiclassical feedback. Its extension to continuous three-dimensional momentum space requires ultraviolet control and an admissible initial state. Localized matter also requires an interaction capable of binding in its stated regime. This calculation checks the exact ultraviolet asymptotes, a specified static one-loop subtraction, the initial adiabatic overlap, and a sufficient two-body no-binding criterion. It establishes no renormalized time-dependent trajectory, full quantum completion, relativistic many-body exclusion, physical Cassi matching or localized formation. Every existing frozen source and receipt remains unchanged.

## 1. Scope, assumptions and conventions

Use natural units and the same selected reference inputs as `computations/matter-formation-fermion-production-prereg.md`: positive reference mass $m_0=1$, real scalar Yukawa coefficient $y=0.25$, scalar mass $\Omega=3$, and initial mass derivative $\nu=y\dot f(0)=0.75$. The interaction is $-yf\bar\psi\psi$ and $m=m_0+yf$. The scalar is a classical mean field. The reference fermionic covariance is $C_0=P_-(m_0)$. No physical parameter is fitted.

For this new continuum witness, replace the four selected momentum cells by the explicitly declared isotropic measure

$$
\int_{\mathbf p}^{\Lambda}:=\frac1{2\pi^2}\int_0^\Lambda p^2\,dp.
$$

There are two spin states. Occupation $n(p)$ is per spin; $N_{\rm pair}=N_{\rm particle}=N_{\rm antiparticle}=2\int_{\mathbf p}^{\Lambda}n$, while $N_{\rm exc}=4\int_{\mathbf p}^{\Lambda}n$ counts both members. Their combined positive excitation-energy density is $\rho_{\rm exc}=4\int_{\mathbf p}^{\Lambda}E_{\rm out}n$. The spatial momentum cutoff is a diagnostic regulator; no covariant stress tensor or complete interacting QFT is qualified here.

Use cutoff values $(32,64,128,256,512)$ without scanning or retuning. Excursion masses are $m_1=(0.5,2)$; pulse durations are $T=(0.25,1,3)$. These are inherited finite-mode inputs, not fitted continuum data.

## 2. Sudden-source ultraviolet witnesses

Let $\delta=m_1-m_0$ and $E_a=\sqrt{p^2+m_a^2}$. The exact occupations are

$$
n_q=\frac12\left(1-\frac{p^2+m_0m_1}{E_0E_1}\right),\qquad
n_P=\frac{p^2\delta^2}{E_0^2E_1^2}\sin^2(E_1T).
$$

The quench uses $E_{\rm out}=E_1$, the cyclic pulse $E_{\rm out}=E_0$. The leading continuum coefficients are

$$
\begin{array}{c|cc}
&N_{\rm pair}/\Lambda&\rho_{\rm exc}/\Lambda^2\\\hline
q&\delta^2/(4\pi^2)&\delta^2/(4\pi^2)\\
P&\delta^2/(2\pi^2)&\delta^2/(2\pi^2)
\end{array}
$$

as $\Lambda\to\infty$ at each fixed positive $T$. The pulse energy has an oscillatory $O(\Lambda)$ boundary term; neither monotonic error reduction nor a fitted power law is required. The quench number has an $O(1)$ remainder and its energy has an $O(\log\Lambda)$ remainder.

Emit ten quench rows first, with $m_1$ outer and cutoff inner. Then emit thirty pulse rows, with $m_1$ outer, duration next and cutoff inner. Append two zero-quench controls with $m_1=m_0$, cutoff 512: one quench of duration zero and one cyclic pulse of duration 1. Each `occupation_rows` entry has exactly `kind`, `mass`, `duration`, `cutoff`, `pair_density`, `excitation_number_density`, `excitation_energy_density`, `predicted_number_coefficient`, `predicted_energy_coefficient`, `scaled_pair_density`, `scaled_excitation_energy`. All quantities are ordinary JSON numbers.

## 3. Static vacuum subtraction and finite remainder

The fixed-reference instantaneous-vacuum contribution per momentum cell, including both spins, is

$$
v(p,m)=2\left[\frac{p^2+mm_0}{E_0}-E\right]
=-\frac{2p^2\delta^2}{E_0(E_0E+p^2+mm_0)}.
$$

Its high-momentum expansion is

$$
v=-\frac{\delta^2}{p}
+\frac{\tfrac32m_0^2\delta^2+m_0\delta^3+\delta^4/4}{p^3}
+O(p^{-5}).
$$

Thus the fixed-reference vacuum density retains $-\delta^2\Lambda^2/(4\pi^2)$ and a logarithmic divergence. Its value and first scalar derivative vanish at the reference; that does not remove the quadratic, cubic and quartic local terms.

For a specific static renormalization condition, subtract the Taylor polynomial through degree four in $\delta$:

$$
T_4v=-\frac{p^2\delta^2}{E_0^3}
+\frac{p^2m_0\delta^3}{E_0^5}
+\frac{p^2(p^2-4m_0^2)\delta^4}{4E_0^7}.
$$

The finite static remainder has the exact continuum limit

$$
\boxed{\mathcal V_R(m)=-\frac{m^4\log(m^2/m_0^2)-2m_0^3\delta-7m_0^2\delta^2-\tfrac{26}3m_0\delta^3-\tfrac{25}6\delta^4}{16\pi^2}.}
$$

This is a declared zero-through-fourth-derivative reference subtraction for the one-loop fermion vacuum contribution. It does not select the physical scalar potential or establish its global stability.

Emit ten `vacuum_rows`, with mass outer and cutoff inner. Exact keys are `mass`, `cutoff`, `reference_vacuum_density`, `predicted_quadratic_coefficient`, `scaled_reference_vacuum`, `renormalized_static_density`, `analytic_static_limit`.

## 4. Kinetic counterterm and initial-state overlap

The leading derivative correction to a negative-energy Bloch vector has transverse component $r_y^{(1)}=-p\dot m/(2E^3)$. Its positive instantaneous occupation is $p^2\dot m^2/(16E^6)$ to second derivative order. The corresponding fermion-energy term and the local scalar kinetic counterterm have matched normalization:

$$
I_\Lambda=\int_{\mathbf p}^{\Lambda}\frac{p^2}{E_0^5}
=\frac{\operatorname{arsinh}(\Lambda/m_0)-u-u^3/3}{2\pi^2},\quad
u=\frac{\Lambda}{\sqrt{\Lambda^2+m_0^2}}.
$$

$$
Z_\Lambda=1-\frac{y^2}{2}I_\Lambda.
$$

A positive $Z_\Lambda$ on this finite cutoff sequence is not an ultraviolet-completion claim.

For a precise initial-overlap diagnostic, use the pure normalized first-adiabatic-direction state with $b=p\nu/(2E_0^3)$ and Bloch vector $[-\hat h_0-b\hat e_y]/\sqrt{1+b^2}$. Its occupation relative to the static reference is

$$
n_{\rm ov}=\frac12\left(1-\frac1{\sqrt{1+b^2}}\right),\qquad
\rho_{\rm ov}(\Lambda)=4\int_{\mathbf p}^{\Lambda}E_0n_{\rm ov}.
$$

It has $n_{\rm ov}=\nu^2/(16p^4)+O(p^{-6})$, and $[\rho_{\rm ov}(2\Lambda)-\rho_{\rm ov}(\Lambda)]/\log2\to\nu^2/(8\pi^2)$. This is a state-overlap energy diagnostic, not a calculated renormalized trajectory or a general particle definition during a driven source. Local derivative counterterms and initial-state preparation are separate requirements.

Emit five `kinetic_rows`, ordered by cutoff. Exact keys are `cutoff`, `kinetic_integral`, `analytic_kinetic_integral`, `z_factor`, `overlap_energy_density`. Emit four `overlap_slopes`, ordered by lower cutoff, with exact keys `cutoff_low`, `cutoff_high`, `measured_log_coefficient`, `predicted_log_coefficient`.

## 5. Static nonrelativistic two-body localization criterion

In a separately stated static, leading nonrelativistic scalar-exchange reduction, eliminating the quadratic scalar gives

$$
V_Y(r)=-\alpha_Y\frac{e^{-\Omega r}}r,\quad \alpha_Y=\frac{y^2}{4\pi},\quad \mu_{\rm red}=\frac{m_0}{2}.
$$

One-body self-energies are absorbed in the reference mass. Relativistic, annihilation, contact, sea-polarization and many-body effects are outside this reduction. Its zero-energy radial Birman–Schwinger kernel has trace

$$
\operatorname{tr}K_\ell=\frac{2\mu_{\rm red}}{2\ell+1}\int_0^\infty r|V_Y(r)|\,dr
=\frac{B}{2\ell+1},\quad
B=\frac{\mu_{\rm red}y^2}{2\pi\Omega}.
$$

If $B<1$, positivity and the trace bound exclude a negative-energy level in every partial wave in this reduction. Failure of this sufficient inequality is inconclusive. It excludes no relativistic or cooperative many-body state.

Emit one `binding` object with exact keys `reference_mass`, `reduced_mass`, `yukawa_coupling`, `scalar_mass`, `alpha`, `radial_integral`, `analytic_radial_integral`, `bargmann_bound`, `all_partial_waves_excluded`.

## 6. Independent methods and immutable evidence

The primary program is `computations/matter_formation_continuum_admissibility.py`; the independent program is `computations/verify_matter_formation_continuum_admissibility.py`. Neither imports the other. Implementers may read this protocol, derivations and primary literature but not the sibling source. Runtime byte hashing for identity binding is permitted.

The primary uses adaptive SciPy quadrature of stable algebraic kernels. It verifies the stated series, Taylor coefficients and elementary primitive with SymPy. The independent program uses composite eight-point Gauss–Legendre quadrature on radial blocks of width at most 0.25, and 32-point Gauss–Legendre integration on $s\in[0,1]$ for vacuum remainders. For static vacuum and remainder it uses the independent Taylor-integral identities

$$
v=-2\delta^2\int_0^1(1-s)\frac{p^2}{[p^2+(m_0+s\delta)^2]^{3/2}}\,ds,
$$

$$
v-T_4v=-\frac54\delta^5\int_0^1(1-s)^4
\frac{p^2m_s(3p^2-4m_s^2)}{(p^2+m_s^2)^{9/2}}\,ds,
\quad m_s=m_0+s\delta.
$$

It evaluates quench occupation through the stable half-angle formula $\sin^2[\operatorname{atan2}(p\delta,p^2+m_0m_1)/2]$, pulse occupation directly, and overlap through $\sin^2[\operatorname{atan}(b)/2]$. The radial binding integral may use the substitution $x=\Omega r$ and a finite endpoint 32 with its exact exponential tail. The primary uses adaptive integration to infinity for that integral.

Each program independently evaluates and qualifies every numerical row. The verifier validates input shape, order, finiteness, source identities and primary qualification, then compares every numerical field with its own values. Scalar tolerance is $5\times10^{-9}+2\times10^{-9}|\text{independent value}|$; booleans, row labels, ordering and key sets are exact. Report every mismatch; never loosen comparison types to accept an invalid scalar.

Both programs accept `--output-dir` and an optional `--prereg`; the verifier also requires `--input-dir`. Primary output is `results.json`; independent output is `verification.json`. Existing target files must cause a nonzero exit without overwrite. Each receipt has `schema`, `identities`, the four row arrays, `overlap_slopes`, `binding`, `checks`, `verdicts`, `numerical_pass` and `failures`. Here the four row arrays are `occupation_rows`, `vacuum_rows`, `kinetic_rows` and `symbolic_checks`. The primary schema is `cassi-continuum-admissibility-v1`; the verifier schema is `cassi-continuum-admissibility-verification-v1`. Each identity has `path` and canonical CRLF-to-LF SHA-256; identities cover primary, verifier, this preregistration and the unchanged finite-mode preregistration. The verifier additionally records `input_sha256` (raw bytes) and `independent_checks` with comparison count, mismatch paths and detailed comparisons.

Primary `symbolic_checks` names are `quench_leading`, `quench_next`, `vacuum_leading`, `vacuum_next`, `vacuum_taylor`, `static_reference_conditions`, `kinetic_primitive`, `overlap_leading`, `four_component_vacuum_trace`, `four_component_excitation_partition`. Each entry has `name` and `pass`. The independent program independently proves the same identities algebraically using SymPy or exact operator expressions; it does not copy symbolic output from the primary. `checks` is an array of objects with `name` and boolean `pass` for all qualification predicates.

Identity keys are exactly `primary`, `verifier`, `prereg` and `finite_mode_prereg`. Both programs use this ordered `checks` name list: `symbolic_identities`, `row_contract`, `finite_values`, `positive_densities`, `zero_controls`, `excitation_count`, `number_asymptotes`, `energy_asymptotes`, `vacuum_asymptotes`, `static_remainders`, `kinetic_primitive`, `positive_kinetic_factors`, `overlap_logarithm`, `binding_integral`, `binding_trace`. Each predicate implements its corresponding requirement in §7; `row_contract` includes exact counts, order, scalar types and key sets. The independent receipt's `independent_checks` has exactly `comparison_count`, `mismatch_paths` and `comparisons`; each detailed comparison has `path`, `primary`, `independent` and boolean `pass`. `input_sha256` is an empty string when the input is missing.

Missing preregistration for the primary, or missing primary `results.json` for the verifier, must exit nonzero and emit a fresh failure receipt with empty scientific rows, binding, checks and verdicts. Other numerical failures retain computed evidence and exit nonzero. JSON contains no NaN or Infinity.

## 7. Qualification, verdicts and stopping rule

A numerical qualification requires all of the following:

1. All symbolic identities pass; all numerical values are finite; exact row counts, order and keys hold; all independent comparisons pass.
2. Every non-control number and excitation-energy density is positive. Each control number and energy has magnitude at most $5\times10^{-12}$; $N_{\rm exc}=2N_{\rm pair}$ within the scalar comparison tolerance in every row.
3. At cutoff 512, each quench and pulse scaled number and energy coefficient differs from its analytic asymptote by at most 3 percent relative. No condition is imposed on monotonic convergence of pulse ratios.
4. At cutoff 512, each scaled reference-vacuum coefficient differs from $-\delta^2/(4\pi^2)$ by at most 0.2 percent relative, and each subtracted static density differs from its exact continuum limit by at most $2\times10^{-6}$ absolute. Lower cutoffs supply the finite-cutoff sequence without this asymptotic qualification.
5. Every kinetic integral agrees with its analytic primitive within scalar tolerance; every $Z_\Lambda$ is positive. The last overlap log-slope agrees with $\nu^2/(8\pi^2)$ within 0.2 percent relative.
6. The binding integral agrees with $\alpha_Y/\Omega$ within scalar tolerance, and the bound is computed from its stated reduced mass and integral. The no-binding verdict applies only if $B<1$.

If numerical qualification fails, all scientific verdicts are `INCONCLUSIVE`. If it passes, emit these exact scoped values: `sudden_source_continuum` = `CONTRADICTS—ultraviolet-finite sudden-source continuum completion`; `static_subtraction` = `SUPPORTS—specified static one-loop subtraction identities`; `initial_overlap` = `SUPPORTS—logarithmic initial adiabatic overlap-energy mismatch`; and `two_body_binding` = `SUPPORTS—absence of two-body binding in the stated nonrelativistic Yukawa reduction` if $B<1$, otherwise `INCONCLUSIVE`.

Run once into `runs/20260906_matter_formation_continuum_admissibility/`, primary first and independent verifier second. Run the two missing-input controls in separate fresh subdirectories. No dynamics, cutoff fitting, coupling scan, bound-state search or fallback model is allowed. An implementation defect may be repaired only with the failed receipts and exact source revision preserved, the defect and changed identities recorded, and a new output directory used under the same scientific protocol. No threshold, model, schedule or verdict rule may be changed after execution.

## References

- `computations/matter-formation-fermion-production-prereg.md`—unchanged finite-mode source, state and input definitions.
- `foundations/sector-coupling-derivation.md` §1.7—fermionic mass source and energy/charge identities.
- `foundations/physical-becoming-hierarchy.md` §§7.3–7.5—allowed effective operators and physical microscopic matching requirements.
- [Baacke, Heitmann and Pätzold, arXiv:hep-ph/9806205](https://arxiv.org/abs/hep-ph/9806205)—homogeneous one-loop renormalization and initial-state singularities. Their $m=g\phi$ model has no additive bare fermion mass; the present $m_0+yf$ expansion requires its corresponding polynomial counterterms.
- [Bargmann, *On the Number of Bound States in a Central Field of Force*](https://doi.org/10.1073/pnas.38.11.961)—partial-wave bound-state counting.
- [Farhi, Graham, Jaffe and Weigel, arXiv:hep-th/0112217](https://arxiv.org/abs/hep-th/0112217)—three-dimensional localized fermionic candidates with renormalized sea and fixed fermion number.

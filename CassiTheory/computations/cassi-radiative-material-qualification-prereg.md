# Cassi Radiative Material Source Step: Fixed Accuracy Qualification

## Status: Preregistered—September 2026

## Abstract

The comprehensive radiative-material schedule passes 33 of 34 checks. Its backward-Euler source step preserves positivity, energy and entropy and converges at first order, while the state $(T_0,E_0)=(0.2,0.5)$ reaches normalized endpoint errors $1.04746495835\times10^{-3}$, $5.11609224324\times10^{-4}$ and $2.52712195192\times10^{-4}$ at steps $0.04$, $0.02$ and $0.01$. The last value exceeds the fixed $5\times10^{-5}$ target. This focused qualification keeps the model, coefficients, initial state, final time, reference solver and target unchanged and tests predeclared source substeps $0.004$, $0.002$ and $0.001$. It introduces no parameter fit and reruns none of the 33 passing controls.

## 1. Fixed source problem

Use the dimensionless gray exchange system

$$
\dot E=c_\gamma\alpha^{\rm a}(a_{\rm R}T^4-E),
\qquad
C\dot T=c_\gamma\alpha^{\rm a}(E-a_{\rm R}T^4),
$$

with

$$
c_\gamma=3,\qquad \alpha^{\rm a}=0.7,\qquad
a_{\rm R}=1,\qquad C=2,
$$

initial state $(T_0,E_0)=(0.2,0.5)$ and final time $2$. Use the unchanged conservative backward-Euler update in `computations/cassi_radiative_material.py`. No coefficient, equation or root tolerance may change.

The independent reference is SciPy DOP853 at relative and absolute tolerance $10^{-12}$. Evaluate source steps

$$
\Delta t\in\{0.004,0.002,0.001\}.
$$

The choice follows the already measured first-order sequence: a tenfold reduction from $0.01$ predicts an error near $2.5\times10^{-5}$, leaving a factor-of-two margin under the original target without selecting a value from a new scan.

## 2. Fixed checks

For all three trajectories require:

1. every stored $T$ and $E$ is finite and strictly positive;
2. $|CT(t)+E(t)-[CT_0+E_0]|\leq2\times10^{-12}$;
3. total entropy $C\log T+(4/3)a_{\rm R}^{1/4}E^{3/4}$ never decreases by more than $2\times10^{-12}$ in one step;
4. each endpoint is closer to the independent reference than the endpoint at the preceding, larger step;
5. each halving ratio is at least $1.8$;
6. the $\Delta t=0.001$ normalized endpoint error is at most $5\times10^{-5}$;
7. the finest endpoint lies closer to the independently solved equilibrium than the initial state.

Independently reconstruct the three endpoint energies and entropies from the stored $T,E$ arrays rather than using model diagnostics. Require exact agreement with the recorded columns to $10^{-13}$.

## 3. Decision and stopping rule

The qualification is `PASS` only if every fixed check succeeds. Its scientific classification is **SUPPORTS** for backward-Euler source subcycling to the displayed benchmark accuracy. Any failed check gives `FAIL`; a reference-solver failure gives `INCONCLUSIVE`. The comprehensive 33/34 receipt remains unchanged, including its failed $\Delta t=0.01$ accuracy check.

This benchmark cannot set a universal CassiCosmos timestep. A live implementation must use source-step refinement or a local error estimate as temperature and opacity vary. Physical units, opacity, temperature, density, ionization and renderer coupling remain open.

Run once from the CassiTheory root:

```text
python computations/verify_cassi_radiative_material_qualification.py \
  --output runs/cassi_radiative_material_qualification/verification.json
```

The verifier refuses existing output, manifest and source-snapshot paths and records source hashes before evaluating the trajectories.

## References

- `computations/cassi-radiative-material-prereg.md`—comprehensive fixed LTE and transport schedule.
- `computations/cassi_radiative_material.py`—unchanged conservative source update.
- `computations/verify_cassi_radiative_material.py`—comprehensive verifier and retained 33/34 outcome.
- `runs/cassi_radiative_material/verification.json`—generated comprehensive receipt with the unresolved source-step tolerance.

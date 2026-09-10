# Compressible Radiative Plasma: Fixed Integrity Qualification

## Status: Preregistered—September 2026

## Abstract

This schedule qualifies the conservative-state interface, thermodynamic potential identities, line-input admissibility, transfer-source normalization, stellar control-volume ledger and prerequisite classifications used by `turbulence/compressible-radiative-plasma-closure.md`. It is separate from the 70-check closure schedule. The controls and thresholds below are fixed before the qualification receipt is generated.

## 1. Fixed sources and execution boundary

The verifier snapshots and hashes these files before importing NumPy, SymPy, SciPy or the reference kernel:

- `computations/compressible-radiative-plasma-integrity-prereg.md`;
- `computations/compressible-radiative-plasma-prereg.md`;
- `turbulence/compressible-radiative-plasma-closure.md`;
- `computations/compressible_radiative_plasma.py`;
- `computations/verify_compressible_radiative_plasma.py`;
- `computations/verify_compressible_radiative_plasma_integrity.py`.

The output, adjacent `input_manifest.json` and `source_snapshots/` directory must not exist when the run begins. The verifier refuses to overwrite any of them.

## 2. Fixed qualification controls

### 2.1 Conservative state and thermodynamics

Use

$$
\rho=2.5,
\qquad
u=(0.2,-0.4,0.1),
\qquad
e=3.2,
\qquad
Y=(0.7,0.2,0.1),
\qquad
n=(0.4,0.2,0).
$$

Require the packed state to reproduce $\rho$, $\rho u$, $\rho(e+|u|^2/2)$, $\rho Y$ and $n$ to normalized error $2\times10^{-14}$. Recovering internal-energy density from the conservative state must give $\rho e$ to the same tolerance. Reject mass fractions $(0.7,0.2,0.2)$ and level populations containing `NaN`.

For positive symbolic $\rho$ and constants $c_v=3/2$, $R=1$, define

$$
T(\rho,s)=\exp\!\left(\frac{s+R\log\rho}{c_v}\right),
\qquad
e=c_vT,
\qquad
p=R\rho T.
$$

Require exact SymPy simplification of

$$
\frac{\partial e}{\partial s}-T=0,
\qquad
\rho^2\frac{\partial e}{\partial\rho}-p=0.
$$

This control checks the signs and density factor in $de=T\,ds-p\,d(1/\rho)$; it does not qualify a nonideal EOS table.

### 2.2 Shock rejection

Call the verifier's normalized-flux validator with actual flux $1.2$, expected flux $1.0$ and tolerance $0.01$. It must raise `ValueError`. This is the executable rejection path for a missing-enthalpy shock flux, whose normalized residual is $0.2$.

### 2.3 Line and population admissibility

Use the valid line input

$$
(n_l,n_u,g_l,g_u,\nu,B_{ul},\phi,h,c_\gamma)
=(1.4,0.3,2,6,2,0.7,0.9,1,1).
$$

The following nine calls must each raise `ValueError`:

1. `line_coefficients` with $n_l=-1$;
2. `line_coefficients` with $n_u=+\infty$;
3. `line_coefficients` with $\nu=0$;
4. `line_coefficients` with $B_{ul}=0$;
5. `line_coefficients` with $h=0$;
6. `line_energy_exchange` with $A_{ul}=-1$;
7. `line_energy_exchange` with $B_{ul}=0$;
8. `line_energy_exchange` with $B_{lu}=\mathrm{NaN}$;
9. `line_energy_exchange` with $\nu=-2$.

For the valid input, use the returned $A_{ul}$ and $B_{lu}$ with mean intensity $J=0.8$. Require the material level-energy increment plus photon-energy increment to vanish to absolute error $2\times10^{-14}$.

### 2.4 Transfer-source normalization

For isotropic transfer use $\eta=0.7$, $\alpha=0.4$, $E=1.2$ and $c_\gamma=3$. Require

$$
S_\gamma=4\pi\eta-c_\gamma\alpha E,
\qquad
S_m=-S_\gamma,
\qquad
S_\gamma+S_m=0
$$

to absolute error $2\times10^{-14}$. At $B=0.8$, $\eta=\alpha B$ and $E=4\pi B/c_\gamma$, require both sources to vanish to the same tolerance.

### 2.5 Stellar energy and nuclear controls

Use the control-volume convention

$$
L_\gamma+L_\nu+\dot E_{\rm mech,out}
=P_{\rm ext}+L_{\rm nuc}^{\rm gross}+\dot E_{\rm matter,in}
-\frac{dE_{\rm stored}}{dt}.
$$

The valid ledger is

$$
(L_\gamma,L_\nu,\dot E_{\rm mech,out},P_{\rm ext},
L_{\rm nuc}^{\rm gross},\dot E_{\rm matter,in},dE_{\rm stored}/dt)
=(0.73,0.08,0.19,0,0.4,0.1,-0.5).
$$

Require its residual below $2\times10^{-14}$. Replacing gross nuclear power by the net value $0.32$ while retaining $L_\nu=0.08$ must raise `ValueError` at tolerance $2\times10^{-14}$. Replacing the photon luminosity by $1.01$ and setting the other outgoing channels to zero, with the same sources, must also raise `ValueError`.

For the fixed reaction $4X\to Y$ with stoichiometry $(-4,1)$, masses $(1.01,4)$, baryon numbers $(1,4)$ and charges $(1,4)$, require exactly zero source and power at event rate zero. At event rates $10^{-6}$ and $0.2$, require positive power equal to $0.04\mathcal R$ and baryon and charge residuals below $10^{-14}$.

### 2.6 Prerequisite classifications

Run the closure verifier twice in temporary, automatically removed directories inside the CassiTheory root:

1. inject a loader that raises `ImportError` before scientific controls;
2. replace the source list by one nonexistent path.

Each nested run must exit with code 2 and write a receipt with `status` and `scientific_classification` equal to `INCONCLUSIVE`, zero scientific checks and the matching `prerequisite_stage`. The dependency case must retain an input manifest and source hashes. The source-read case must have no input manifest and must not create a source-snapshot directory. These are expected qualification checks, not scientific failures.

## 3. Fixed count, decision and stopping rule

The qualification contains exactly **25 checks**:

- five conservative-state and thermodynamic checks;
- one shock rejection check;
- ten line-admissibility and exchange checks;
- two transfer-source checks;
- five stellar-ledger and nuclear checks;
- two prerequisite-classification checks.

All numerical comparisons use float64. Symbolic checks require exact simplification to zero. No threshold or input may change after execution.

The result is `PASS` with scientific classification `SUPPORTS-compressible radiative-plasma integrity qualification` only if all 25 checks pass and every source hash matches its snapshot. A scientific check failure gives `FAIL` and `CONTRADICTS`. Failure to read a qualification source or import a required qualification dependency gives `INCONCLUSIVE` and stops interpretation.

Run once from the CassiTheory root:

```text
python computations/verify_compressible_radiative_plasma_integrity.py \
  --output runs/compressible_radiative_plasma_integrity_sealed/verification.json
```

## References

- `turbulence/compressible-radiative-plasma-closure.md`—conditional equations and source conventions
- `computations/compressible-radiative-plasma-prereg.md`—70-check closure schedule
- `computations/compressible_radiative_plasma.py`—reference kernels
- `computations/verify_compressible_radiative_plasma.py`—closure verifier and prerequisite receipt path

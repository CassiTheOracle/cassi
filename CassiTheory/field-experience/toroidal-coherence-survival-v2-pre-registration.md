# Toroidal Coherence Survival Probe V2—Pre-registration

## Status: Preregistered replacement—August 2026

## 1. Incorporated protocol

This replacement protocol incorporates `field-experience/toroidal-coherence-survival-pre-registration.md` in full, subject only to the substitutions frozen below. Every unlisted equation, constant, seed, arm, diagnostic, threshold, stopping rule, gate, and interpretation boundary from that document applies verbatim.

The replacement follows the preflight-only receipt at `runs/20260831T205711Z_toroidal_coherence_survival/results.json`, recorded in `field-experience/toroidal-coherence-survival-report.md`. That receipt stopped before evolution because the initial helical order was `0.670671820640564`, below the frozen `0.80` threshold. It supplies no dynamical observation.

No result from an evolved toroidal field exists at the time this replacement is frozen.

---

## 2. Frozen geometry substitutions

Only two physical initialization constants change:

| quantity | V1 value | frozen V2 value |
|---|---:|---:|
| strand offset `a` | `1.0` | `1.20` |
| strand density width `sigma` | `0.75` | `0.60` |

The separation ratio therefore changes from

\[
\frac{a}{\sigma}=\frac{4}{3}
\]

to

\[
\frac{a}{\sigma}=2.
\]

This is an initialization repair: the target centerlines, spatial winding `m=1`, compact-phase windings `(p,q)=(+2,-3)`, component ratio, virial calibration, field equation, mass normalization, box, integration window, and all gate thresholds remain unchanged.

The random-phase cutoff retains the original formula

\[
k_c=\frac{\pi}{\sigma},
\]

and therefore uses the frozen V2 `sigma=0.60`.

G3 remains unchanged:

- closed seed `H >= 0.80` and `O >= 0.80`;
- untwisted seed `H <= 0.20`.

If the V2 seed fails G1–G4, the protocol again stops before evolution with `INCONCLUSIVE—INVALID INITIALIZATION`. No further geometry adjustment is permitted under this preregistration.

---

## 3. Frozen source and receipt substitutions

V2 uses separately versioned sources:

- primary probe: `field-experience/toroidal_coherence_survival_v2_probe.py`;
- independent verifier: `field-experience/verify_toroidal_coherence_survival_v2.py`;
- campaign report: `field-experience/toroidal-coherence-survival-report.md`.

V2 receipts use

```text
runs/<UTC>_toroidal_coherence_survival_v2/
  results.json
  fields_<arm>.npz
  verification.json
```

The source manifest must contain SHA-256 values for:

- `field-experience/toroidal-coherence-survival-pre-registration.md`;
- `field-experience/toroidal-coherence-survival-v2-pre-registration.md`;
- `field-experience/toroidal_coherence_survival_v2_probe.py`;
- `field-experience/verify_toroidal_coherence_survival_v2.py`.

The probe identifier is `toroidal_coherence_survival_v2`.

---

## 4. Frozen verifier repair

The V2 verifier retains independent NumPy recomputation of every stored field diagnostic. It also handles a preflight-only receipt:

1. verify the frozen constants, source manifest, source hashes, closure error, virial algebra, initial compact-phase winding, component ratio, closed helical order, strand opposition, and untwisted discrimination;
2. recompute the G1–G4 verdict from the stored preflight metrics;
3. require the terminal receipt verdict `INCONCLUSIVE—INVALID INITIALIZATION` when those gates fail;
4. create `verification.json` with exclusive creation and no field-arm expectation.

For an evolved receipt, the original full field, metric, gate, hash, and verdict recomputation applies unchanged.

---

## 5. Frozen verdict boundary

The V1 preflight remains `INCONCLUSIVE—INVALID INITIALIZATION`.

The V2 scientific verdict follows the original tree without alteration:

- `INCONCLUSIVE—INVALID INITIALIZATION` if G1–G4 fail;
- `INCONCLUSIVE—NUMERICAL QUALITY` if Q1–Q5 fail;
- `EMERGES CONDITIONALLY` if S1–S3 pass after numerical quality passes;
- `DOES NOT EMERGE` if numerical quality passes and any of S1–S3 fails.

A positive result remains conditional on the supplied two-component Schrödinger–Poisson realization. A negative result rejects survival only under that frozen realization and parameter set.

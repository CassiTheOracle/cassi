# Cassi Bridge Results: Hydrogen ↔ Cosmology

## Atomic limit (hydrogen)

The unified solver was run in atomic mode with a single electron in a fixed
soft-Coulomb proton well:

| Quantity | Standard | φ-damped | Target |
|---|---:|---:|---:|
| Final energy | -0.49908 E_h | -0.49907 E_h | -0.5 |
| Final ⟨r⟩ | 1.4965 a₀ | 1.4958 a₀ | 1.5 |

Both converge to a bound state, confirming that the same Schrödinger–Poisson
engine recovers atomic physics when $M=1$ and the source is a fixed external
charge.

## Cosmological limit

The same solver was run with $M=100.0$,
no external potential, and the full Cassi source:

| Time τ | δ_rms | I[ρ] |
|---|---:|---:|
| 0.01 | 0.050 | 0.0013 |
| 0.51 | 0.139 | 0.0128 |
| 1.01 | 0.407 | 0.1417 |
| 1.51 | 0.437 | 0.1674 |
| 2.01 | 0.445 | 0.1748 |
| 2.51 | 0.448 | 0.1786 |
| 3.01 | 0.451 | 0.1813 |
| 3.51 | 0.452 | 0.1830 |
| 4.01 | 0.453 | 0.1841 |
| 4.51 | 0.454 | 0.1847 |
| 5.00 | 0.454 | 0.1852 |

## Figures

- `docs/figures/cassi_bridge_atomic.png`
- `docs/figures/cassi_bridge_cosmos.png`

## Interpretation

The two limits share one equation, one kernel and one numerical engine. The
only differences are the mass $M$, the presence of an external proton charge,
and which Cassi source terms are active. This is the Cassi bridge: hydrogen is
the single-particle fixed-point of the same information field that, at large
$M$ and with self-gravity, becomes cosmic structure formation.

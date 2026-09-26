# Morphology Operator Language

## Purpose

The V4 full-observable campaign isolated a concrete transfer boundary: a flow-conditioned collective term can be selected from local evidence, yet it does not transport between narrow spirals, nested shells, concentrated collapse, and a live-field spiral. The successor language adds present-snapshot morphology coordinates so a field-built operator can condition its scale on the coherent structure it occupies.

The V4 executor remains unchanged because its source digest is bound by `CassiFI/_diag/full-observable-operator-v4/receipt.json`. A later frozen successor imports `cassi_morphology_operator_language.py` and binds that new executor independently.

## Coordinates

All coordinates are deterministic functions of a single snapshot's position, velocity, and mass. They receive no acceleration target, future sample, analysis verdict, holdout identity, adaptive sidecar, or model output.

| Atom | Meaning |
|---|---|
| `morphology_compactness` | Mass-weighted \(r_{50}/r_{90}\): a tight radial band approaches one. |
| `morphology_radial_spread` | Mass-weighted radial standard deviation divided by \(r_{50}\): distinguishes narrow layers from multiscale occupancy. |
| `morphology_anisotropy` | Largest-minus-smallest mass-weighted shape-covariance eigenvalue divided by the largest: distinguishes round from elongated geometry. |
| `morphology_planarity` | Middle-minus-smallest shape-covariance eigenvalue divided by the middle: separates a flattened sheet from volumetric support. |
| `morphology_shell_tangentiality` | Fraction of local neighbor separation transverse to the radial direction: detects locally layered support. |
| `morphology_counterflow` | Local cancellation of radial velocity relative to its radial RMS: distinguishes counter-streaming from coherent inflow or outflow. |

The successor alphabet has **37 atoms**: the V4 31-atom environment plus these six coordinates. Five morphology atoms also become legal mutation companions, allowing the field to build products and stabilized quotients with its selected local scalar.

## Actual V4 morphology reading

At the middle recorded epoch, without reading acceleration targets:

| World | Compactness | Radial spread | Interpretation |
|---|---:|---:|---|
| `DH3` narrow spiral | `0.9848` | `0.0133` | narrow radial layer |
| `DH6` nested shells | `0.9573` | `0.0339` | broader persistent layered support |
| `DHC3` concentrated collapse | `0.5133` | `0.6377` | broad multiscale radial occupancy |
| `DHL3` live-field spiral | `0.7870` | `0.2947` | evolving intermediate morphology |

The live-field spiral also changed anisotropy from `0.5368` at the middle epoch to `0.8931` at the late epoch, and planarity from `0.2437` to `0.6234`. Those are present-state geometric changes that the prior grammar could not name.

The V4 worlds carry coherent radial flow, so their counterflow values remain near zero and their local shell-tangentiality values remain near the isotropic-neighborhood baseline. The focused controls separately prove those coordinates fire on counter-streaming and thin-shell geometry.

## Verification

`test_cassi_morphology_observables.py` verifies deterministic replay, finite bounded outputs, target independence by interface, collision rejection, six morphology contrasts, and exact successor-alphabet order. `measure_cassi_morphology_observables.py` is the target-independent recorder reader used for the V4 readings above.

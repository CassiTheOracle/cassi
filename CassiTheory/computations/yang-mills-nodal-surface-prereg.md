# Nodal Surface Search with a Two-Parameter Block Family

## Status: Pre-registered—September 2026

## Abstract

The one-parameter block paths of
`computations/yang-mills-nodal-family-prereg.md` return `NODAL_CONFINED`: five
of twelve scheduled rows carry no resolved sign change, so those rows give no
nodal witness and no sign-constancy statement either. A one-parameter path
can miss a codimension-one nodal set. This probe replaces the path by a
two-parameter torus family that rotates two block links independently,
searches every grid line of that family for resolved sign changes, and
cross-checks the two one-parameter lines against the sealed one-parameter
receipt. Family, grid, resolution rule, conformance tolerances, decision tree
and stopping rule are fixed here before implementation.

## 1. Question

Does the projected Ritz density of a witness-free scheduled row have a nodal
set that the single-link paths missed, or is the sign constancy of those rows
stable under a two-parameter block family?

The probe returns a witness statement only. Finding no sign change on a grid
line is not a positivity proof, and finding one does not extend any statement
beyond the projected Ritz density.

## 2. Family and grid

Reuse the seven-link graph, truncation, Ritz convention and wavefunction
evaluation of the one-parameter probe. Rotate block links $0$ and $1$
independently,

$$
U_0(\varphi)=\exp\!\Bigl(i\frac{\varphi}{2}\sigma_3\Bigr),
\qquad
U_1(\psi)=\exp\!\Bigl(i\frac{\psi}{2}\sigma_3\Bigr),
\qquad
\varphi_k=\psi_k=\frac{2\pi k}{32},\ k=0,\ldots,32,
$$

with block links $2$ and $3$ and the three exterior links at the identity.
Every row of the twelve-row schedule $J\in\{1,2,3\}$,
$x\in\{1/4,1,4,16\}$ is evaluated on the full $33\times33$ grid, and every
grid line (constant $\varphi$ and constant $\psi$) is searched for resolved
sign changes.

## 3. Observables

For every row: the number of grid lines carrying a resolved sign change, the
total resolved sign-change count over both line families, the smallest
resolved modulus on the grid, and the amplitudes on the two one-parameter
lines.

A sign change between adjacent grid points counts when both endpoint moduli
exceed $10^{-10}$.

## 4. Conformance

The $\psi=0$ line reproduces path A of the sealed one-parameter receipt and
the $\varphi=0$ line reproduces its path B when compared on the common
angles $2\pi m/16$, $m=0,\ldots,16$, i.e. grid indices $2m$ against receipt
indices $3m$. Both comparisons must agree to $10^{-9}$ absolute. The receipt
also binds the one-parameter receipt SHA-256.

## 5. Decision tree and thresholds

| Rule | Verdict |
|---|---|
| Every scheduled row shows at least one resolved grid-line sign change | `WITNESS_WIDENS_TO_FULL_SCHEDULE` |
| At least one row shows no resolved sign change on any grid line | `WITNESS_CONFINED` |
| Conformance failure, unresolved grid, or a grid that is not fully finite | `INCONCLUSIVE` |

## 6. Consequence attached to the verdict

A resolved sign change on any continuous grid line implies a nonempty nodal
set of the cutoff density $\rho\propto|\Omega|^2$ on the block, hence the
vanishing Dirichlet-energy argument of §9.23 applies to that row. The verdict
is a statement about the projected Ritz density, not about the exact
regulated vacuum measure, which is strictly positive by §9.13.

## 7. Stopping rule and evidence boundary

One execution of the twelve-row grid schedule, single run, no re-run after
inspection. The receipt binds this protocol, the source
`computations/verify_yang_mills_nodal_surface.py`, the one-parameter source
and receipt, the §27 source and the shared algebra module by SHA-256, and
must refuse to overwrite an existing receipt.

## 8. Obligations unchanged

Exact-vacuum fibre rate, transport score, cutoff removal, uniform
interacting recovery, thermodynamic limit and continuum construction remain
open.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §9.23—nodal Ritz obstruction and its schedule-wide confinement.
- `computations/yang-mills-nodal-family-prereg.md`—frozen one-parameter family, resolution rule and confinement decision tree.
- `computations/verify_yang_mills_nodal_family.py`—sealed one-parameter receipt with the two path tables used for conformance.
- `computations/yang_mills_conditional_algebra.py`—shared representation, contraction and conditional-moment conventions.

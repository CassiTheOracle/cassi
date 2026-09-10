# Pure Yang–Mills Cylindrical Block Map and Refined-Plaquette Obstruction

## Status: Pre-registered—September 2026

## Abstract

This investigation tests an exact gauge-compatible cylindrical map between two finite source-free $SU(2)$ lattice Hilbert spaces. Edge-disjoint fine paths carry coarse holonomies. Normalized Haar measure makes the pullback an isometry, internal gauge transformations cancel along each path, and the fine electric Casimir compresses with the exact path-length weight. A genuine spatial refinement adds elementary plaquettes whose Wilson characters are not measurable from the coarse path products. The fixed open $2\times2$ block gives an exact magnetic-leakage witness and distinguishes this case from graph subdivision without new faces.

The calculation concerns one explicit kinematic map. It does not exclude an interacting fibre embedding, an energy-dependent Feshbach reduction, or another gauge-compatible renormalization map. It supplies no weak-coupling continuum construction or continuum mass gap.

## 1. Hamiltonian and map

Use normalized product Haar measure and the source-free Kogut–Susskind convention

$$
h_f=\frac{2a_f}{g_f^2}H_f
=\mathcal E_f+2x_fN_{p,f}-x_f\sum_{p\in P_f}\chi_{1/2}(U_p),
\qquad
x_f=\frac{2}{g_f^4},
$$

where

$$
\mathcal E_f=-\sum_{e\in E_f}\sum_{A=1}^3(X_e^A)^2
$$

is positive and $\chi_{1/2}=\operatorname{Tr}$ is the real fundamental $SU(2)$ character. The fundamental Casimir is $c_{1/2}=3/4$, so a four-link plaquette character has electric energy $4c_{1/2}=3$.

For every oriented coarse edge $c$, choose an oriented fine path

$$
P_c=(e_{c,1}^{\sigma_{c,1}},\ldots,e_{c,n_c}^{\sigma_{c,n_c}}),
\qquad n_c\ge1,\qquad \sigma_{c,j}\in\{-1,+1\},
$$

with each path edge-simple and the paths pairwise edge-disjoint. Choose a
consistent fine-vertex representative $\iota(v)$ for every coarse endpoint.
Define

$$
\pi(U)_c=U_{e_{c,1}}^{\sigma_{c,1}}\cdots
U_{e_{c,n_c}}^{\sigma_{c,n_c}},
\qquad
(Jf)(U)=f(\pi(U)).
$$

The analytical target is

$$
J^*J=I,
\qquad
\pi(U^h)_c=h_{\iota(s(c))}\pi(U)_c h_{\iota(t(c))}^{-1},
$$

and

$$
J^*\mathcal E_fJ
=\sum_c n_c\mathcal E_c^{(c)}
\quad\text{on the smooth cylindrical core}.
$$

The first identity uses edge-simple, pairwise edge-disjoint paths and normalized Haar measure. The second covers fine gauge transformations whose endpoint values descend through $\iota$; factors at internal path vertices cancel. In the declared fixture, distinct coarse vertices have distinct fine representatives, so every fine endpoint transformation defines the corresponding coarse transformation. The electric identity uses the bi-invariant quadratic Casimir and holds for either path orientation.

For uniform path length $n_c=b$ and $a_c=ba_f$, matching the electric term to a coarse Kogut–Susskind coefficient without a separate energy rescaling requires

$$
\frac{g_c^2}{2a_c}=\frac{b g_f^2}{2a_f},
\qquad
\boxed{g_c^2=b^2g_f^2}.
$$

This is the kinematic coupling relation of this path pullback. It is not a derived Yang–Mills running law.

## 2. Fixed genuine-refinement fixture

Use one open square divided into four elementary squares. Its nine vertices and twelve links form a $2\times2$ fine grid. The four coarse boundary edges are oriented counterclockwise and are products of the two fine links on each outer side. The four interior links are absent from every coarse path. The coarse outer Wilson loop is retained exactly:

$$
U_{\partial B}
=\pi(U)_{c_1}\pi(U)_{c_2}
\pi(U)_{c_3}\pi(U)_{c_4},
$$

with orientations fixed by the implementation.

Each elementary fine plaquette contains at least one interior witness link that is absent from the coarse sigma-algebra $\mathcal A_c=\sigma(\pi)$. Normalized Haar orthogonality gives

$$
\mathbb E_{\mathrm H}
[\chi_{1/2}(U_p)\mid\mathcal A_c]=0,
\qquad
\|\chi_{1/2}(U_p)\|_2^2=1.
$$

Distinct elementary plaquette characters are orthogonal. With $P=JJ^*$, $Q=I-P$ and normalized constant coarse state $1_c$, the decisive identity is therefore

$$
\left\|Qh_fJ1_c\right\|_2
=x_f\sqrt4=2x_f.
$$

The constant magnetic term and any scalar vacuum-energy subtraction lie in $\operatorname{Ran}J$ and do not change this norm. Every witness is a closed Wilson loop, so projection to the Gauss-invariant Hilbert space does not remove the leakage. In physical units,

$$
\left\|QH_fJ1_c\right\|_2
=\frac{g_f^2}{2a_f}(2x_f)
=\frac{2}{a_fg_f^2}.
$$

The one-plaquette matrix element has dimensionless magnitude $x_f$ while the corresponding dimensionless electric Casimir eigenvalue is $3$. Thus the fixed electric-vacuum diagnostic is $x_f/3$. Its divergence as $g_f\to0$ excludes a weak-coupling small-perturbation argument around this cylindrical Haar vacuum. It does not decide an energy-resolvent-weighted estimate built from an interacting eliminated-sector Hamiltonian.

## 3. Fixed subdivision control

Use a single coarse square whose four edges are subdivided into path segments while its sole face remains the outer square. No interior links or elementary faces are added. The face holonomy is measurable from $\pi$, its conditional-mean residual is zero, and the magnetic multiplication preserves the cylindrical image.

This control prevents the refined-plaquette result from being applied to pure graph subdivision. Such subdivision does not lower the spatial plaquette cutoff.

## 4. Deterministic controls

The primary verifier uses the fixed seed `20260909` only to choose generic $SU(2)$ matrices away from coordinate singularities. No outcome is selected from random trials.

### 4.1 Group and gauge identities

For path lengths $b\in\{2,3,4\}$ and fixed orientation words

$$
(+,+),\qquad (+,-,+),\qquad (-,+,-,+),
$$

check direct path multiplication, inversion, endpoint gauge covariance and cancellation of independently chosen internal gauge transformations. Require maximum matrix discrepancy below $10^{-12}$.

### 4.2 Electric compression

Use the fundamental and adjoint representations, with Casimirs $3/4$ and $2$. Insert each Lie-algebra generator at every fine-link position and evaluate the summed second derivative directly from representation matrices. For each listed seeded witness and representation, require

$$
-\sum_{e\in P_c}\sum_A\frac{d^2}{dt^2}
\chi_j(\pi(U(t)))\bigg|_{t=0}
=bj(j+1)\chi_j(\pi(U))
$$

within $10^{-11}$. Run the same check for the declared mixed-orientation words.

### 4.3 Exact fibre moments

Use the eight quaternion matrices

$$
\mathcal Q_8=\{\pm I,\pm i\sigma_1,\pm i\sigma_2,\pm i\sigma_3\}.
$$

For arbitrary fixed $A,B\in SU(2)$, their uniform average obeys

$$
\frac18\sum_{q\in\mathcal Q_8}\operatorname{Tr}(AqB)=0,
\qquad
\frac18\sum_{q\in\mathcal Q_8}\left[\operatorname{Tr}(AqB)\right]^2=1.
$$

Use interior absent-link witnesses to reconstruct the four conditional means. Use one boundary link unique to each plaquette to reconstruct the raw product-Haar Gram matrix. Require maximum first-moment error below $10^{-12}$ and maximum Gram-matrix error from $I_4$ below $10^{-12}$. Verify separately that the outer coarse Wilson character equals the fine outer-boundary character.

### 4.4 Units and scale identities

Use exactly

$$
b\in\{2,3,4\},\qquad
g_f\in\{2,1,1/2\},\qquad
a_f\in\{1,1/2,1/4\}.
$$

Check $x_f=2/g_f^4$, $g_c^2=b^2g_f^2$, the dimensionless leakage $2x_f$, and the physical leakage $2/(a_fg_f^2)$ at relative error below $10^{-13}$.

For a physical gap represented at both cutoffs, check the exact unit relation

$$
\frac{g_f^2}{2a_f}\widehat\Delta_f
=\frac{g_c^2}{2ba_f}\widehat\Delta_c,
\qquad
\widehat\Delta_c=\frac{b g_f^2}{g_c^2}\widehat\Delta_f.
$$

Under the path-map electric matching relation this becomes $\widehat\Delta_c=\widehat\Delta_f/b$. No spectral equality is inferred because the full cylindrical image is not invariant on the genuine-refinement fixture.

## 5. Analytical reconciliation

Independent analytical review must verify all of the following before adoption:

1. normalized-Haar isometry for edge-disjoint paths;
2. gauge covariance at endpoints and cancellation at internal vertices;
3. orientation-independent Casimir compression;
4. the conditional-expectation interpretation $P=JJ^*$;
5. exact four-plaquette conditional means and orthogonality;
6. persistence of leakage after Gauss projection and scalar energy subtraction;
7. the distinction between failure of this exact intertwiner and failure of every possible block map;
8. the distinction between the fixed $x_f/3$ electric-vacuum diagnostic and a resolvent-weighted interacting-fibre estimate;
9. physical-unit scaling with explicit $a_f$, $g_f$ and $b$, while retaining volume-uniform extension as an unresolved analytical requirement.

An interacting fibre isometry may have the form

$$
(J_\omega f)(U)=f(\pi(U))\omega_{\pi(U)}(r),
\qquad
\int|\omega_y(r)|^2\,d\nu_y(r)=1.
$$

Its exact dynamical criterion is

$$
(I-J_\omega J_\omega^*)H_fJ_\omega=0.
$$

The review must retain the connection, scalar, boundary-sector and generated multi-loop terms induced by a coarse-holonomy-dependent fibre. An energy-dependent Feshbach operator remains admissible. The current schedule does not estimate those terms.

## 6. Qualification and stopping

Run the complete fixed schedule once after the protocol, primary source and independent analytical review settle. Preserve every failed receipt and its frozen sources. An implementation repair retains the complete scientific schedule and writes to a fresh path.

- **SUPPORTS**—all deterministic finite-fixture controls pass at their stated tolerances.
- **ADOPT**—the analytical Haar-isometry, electric-compression or leakage identity is accepted only after its assumptions and independent review reconcile.
- **CONTRADICTS**—the cylindrical path pullback is an exact full-Hamiltonian intertwiner on the declared genuine spatial refinement, or its Haar/electric vacuum supplies weak-coupling perturbative smallness.
- **INCONCLUSIVE**—a required source identity, fixed control or independent reconstruction fails.
- **UNRESOLVED**—interacting fibre construction, uniform discarded-sector resolvent control, weak-coupling renormalization trajectory, thermodynamic limit, continuum quantum field, continuum mass gap and Cassi microscopic identification.

Stop after one qualified primary receipt and one source-independent reconstruction. Do not add lattice sizes, couplings, trial fibres, fitted coefficients, spectra or continuum extrapolations in response to the result.

## 7. Evidence

Run from CassiTheory:

```
python computations/verify_yang_mills_block_map.py --output runs/yang_mills_block_map/verification.json
```

The verifier freezes this protocol, its source and the reused receipt helper into an adjacent input manifest and source directory. Its PASS or FAIL is a primary-control status; every scientific classification remains explicitly pending until the separate reconstruction and analytical reconciliation pass. A separate implementation reconstructs every scientific field from the frozen protocol and primary receipt without importing the primary verifier. Generated evidence remains local and is indexed in `BROKEN_REFS.md`.

`verification_pre_reference_repair.json` and
`verification_pre_scope_repair.json` are retained as unqualified source-bound
receipts. The first protocol snapshot contains an incorrect reference-author
attribution. The second does not distinguish the listed seeded electric
witnesses and raw boundary-link Gram from universal and conditional
statements. Neither receipt enters a classification. `verification.json` is
the qualified receipt.

## References

- J. Kogut and L. Susskind, [Hamiltonian formulation of Wilson's lattice gauge theories](https://doi.org/10.1103/PhysRevD.11.395)—Hamiltonian and Gauss-law framework.
- A. Jaffe and E. Witten, [Quantum Yang–Mills Theory](https://www.claymath.org/wp-content/uploads/2022/06/yangmills.pdf), §4—continuum existence and mass-gap requirements.
- J. A. Zapata, [Local gauge theory and coarse graining](https://arxiv.org/abs/1203.2306)—macroscopic holonomy data and the information required for faithful gauge coarse graining.
- W. Donnelly, [Decomposition of entanglement entropy in lattice gauge theory](https://arxiv.org/abs/1109.0036), §§II–III—Gauss constraints, boundary representations and Hilbert-space factorization.
- B. Dittrich, S. Mizera and S. Steinhaus, [Decorated tensor network renormalization for lattice gauge theories and spin foam models](https://arxiv.org/abs/1409.2407)—explicit gauge-symmetry preservation under coarse graining, with numerical tests for finite Abelian groups.
- M. Griesemer and D. Hasler, [On the Smooth Feshbach–Schur Map](https://arxiv.org/abs/0704.3244)—spectral reduction and resolvent conditions.
- `computations/yang-mills-vacuum-block-prereg.md`—exact-vacuum measure, conditional block and Gaussian reduction boundary.

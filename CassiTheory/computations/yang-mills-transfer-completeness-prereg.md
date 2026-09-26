# Pure Yang–Mills transfer-correlation completeness criterion

## Status: Pre-registered finite-transfer diagnostic—September 2026

## Abstract

The conditional RG theorem in `foundations/loop-to-bubble-projection-theorem.md`
§9.31 assumes an exact transfer-correlation map and completeness of the retained
Osterwalder–Schrader vectors. The cylindrical block-map campaign qualifies one
Haar isometry and rejects its bare full-Hamiltonian intertwining on a genuine
refinement. This protocol tests the abstract implication that exact
correlation matching forces a reducing retained subspace in finite positive
transfer matrices.

Let $A$ be a positive self-adjoint fine transfer operator after the blocking
interval and let $J$ be an isometry from the retained space into the fine
physical space. Set $P=JJ^*$, $Q=I-P$ and $A_c=J^*AJ$. The first compressed
moment always agrees. The second-moment defect is

$$
\langle Ju,A^2Ju\rangle-\langle u,A_c^2u\rangle
=\|QAJu\|^2.
$$

Thus exact matching through $m=2$ is equivalent to $A\operatorname{Ran}J
\subseteq\operatorname{Ran}J$; because $A$ is self-adjoint, the retained
subspace is reducing and all later moments match. This is a finite operator
criterion, not a construction of a Yang–Mills RG trajectory. A proper retained
subspace can satisfy the criterion while omitting physical states, so a retained
rate is not a full physical gap without completeness.

The primary and independent implementations use the same three frozen fixtures:
an invariant complete retained space, an invariant incomplete retained space,
and a positive self-adjoint leaky space. They check the second-moment defect,
all scheduled moments, the completeness flag and the gap-boundary logic. The
receipts establish only the finite criterion and its falsification controls.
They do not establish an interacting block map, a continuum limit, an
Osterwalder–Schrader reconstruction or a mass gap.

## 1. Finite criterion

Use a real finite-dimensional Hilbert space with Euclidean inner product. The
first basis vector is the vacuum. The remaining declared physical basis vectors
form $\mathcal H_{\rm phys}$. The transfer matrix has vacuum eigenvalue one and
all physical eigenvalues strictly between zero and one. For an isometric
retained map $J$, define

$$
A_c:=J^*AJ,
\qquad
C_f^u(m):=\langle Ju,A^mJu\rangle,
\qquad
C_c^u(m):=\langle u,A_c^m u\rangle.
$$

At $m=1$, $C_f^u(1)=C_c^u(1)$ by compression. At $m=2$,

$$
D_2(u):=C_f^u(2)-C_c^u(2)
=\langle u,J^*AQAJu\rangle
=\|QAJu\|^2\geq0.
$$

Therefore the following statements are equivalent in finite dimension:

1. $D_2(u)=0$ for every retained vector $u$;
2. $QAJ=0$;
3. $A\operatorname{Ran}J\subseteq\operatorname{Ran}J$;
4. $\operatorname{Ran}J$ reduces the self-adjoint operator $A$;
5. $C_f^u(m)=C_c^u(m)$ for every retained $u$ and every integer $m\geq0$.

The implication from (1) to (2) uses the positive matrix $J^*AQAJ=(QAJ)^*(QAJ)$.
The implication from invariance to reduction uses self-adjointness. A single
correlation rate or the $m=1$ compressed moment is not a substitute for this
criterion.

Completeness is a separate condition. If $\mathcal H_{\rm phys}$ is the
vacuum-orthogonal physical space, the retained family is complete exactly when
$\operatorname{Ran}J=\mathcal H_{\rm phys}$. Only in that case does the retained
spectral rate describe the full finite physical spectrum. In an incomplete
fixture, all retained moments may match while an omitted physical eigenvalue
sets a different full gap.

## 2. Frozen fixtures

All matrices and maps below are fixed. Rows and columns use the order
$(\Omega,e_1,e_2,e_3)$; a fixture with no $e_3$ uses the first three entries.
The retained map always sends the ordered coarse basis to $(e_1,e_2)$:

$$
J=
\begin{pmatrix}
0&0\\
1&0\\
0&1\\
0&0
\end{pmatrix}.
$$

The complete fixture declares $\mathcal H_{\rm phys}=\operatorname{span}(e_1,e_2)$
and uses

$$
A_{\rm complete}=\operatorname{diag}(1,0.72,0.58,0).
$$

The final zero is a padding coordinate outside the declared physical space.
The incomplete fixture declares
$\mathcal H_{\rm phys}=\operatorname{span}(e_1,e_2,e_3)$ and uses

$$
A_{\rm incomplete}=\operatorname{diag}(1,0.72,0.58,0.91).
$$

The leaky fixture declares the same three-dimensional physical space and uses

$$
A_{\rm leaky}=
\begin{pmatrix}
1&0&0&0\\
0&0.72&0&0.07\\
0&0&0.58&0\\
0&0.07&0&0.41
\end{pmatrix}.
$$

The physical $2\times2$ coupling block has eigenvalues strictly inside
$(0,1)$, so every fixture is a positive self-adjoint transfer operator on the
declared space. The leaky fixture has $\|QAJ\|=0.07$ and
$D_2(e_1)=0.07^2$; its $m=1$ compression is nevertheless identical to the
retained diagonal block. The incomplete fixture has $QAJ=0$ but omits the
physical $e_3$ channel.

Use moment orders $m=0,1,2,3,4,5$. Use absolute tolerance $10^{-12}$ for matrix
identities and $10^{-11}$ for scalar spectral comparisons. Compute rates as
$-\log\lambda$ for positive eigenvalues. The complete fixture's full gap is the
retained gap; the incomplete fixture's full gap uses the omitted $0.91$ channel.

## 3. Primary decision schedule

The primary verifier must record every comparison and emit exactly 54 passing
checks before the verdict is `PASS`:
- six matrix/map checks per fixture: symmetry, positivity spectrum, vacuum
  eigenvalue, isometry, physical-space declaration and compression shape;
- four criterion checks per fixture: $m=1$ equality, second-moment defect,
  defect norm identity and invariance equivalence;
- six moment checks for the complete fixture;
- six moment checks for the incomplete fixture;
- six moment checks for the leaky fixture, with rejection of exact matching;
- two completeness/gap-boundary checks;
- four mutation-firing checks.

The fixture classifications are fixed:

| fixture | reducing criterion | retained completeness | full-gap conclusion |
|---|---|---|---|
| complete | pass | pass | allowed |
| incomplete | pass | fail | withheld |
| leaky | fail | fail | withheld |

The four mutations are:

1. `omit_second_moment_defect`: use only $m=0,1$ when classifying the leaky
   fixture, falsely accepting its compressed map;
2. `ignore_completeness`: allow the incomplete fixture to claim a full gap;
3. `compressed_gap_is_full_gap`: replace the full physical gap by the retained
   gap on the incomplete fixture;
4. `accept_leakage_as_exact`: force the leaky fixture's nonzero defect to zero.

Every mutation must make at least one false classification pass or make a
required exact check fail. A mutation without a firing witness makes the primary
verdict `FAIL`.

## 4. Independent reconstruction

The independent Node implementation must define the matrices, products,
transpose maps, eigenvalue checks, moments, completeness classifications and
all four mutations independently. It may read the primary receipt only after
reconstructing its own fixture values. It must not import or execute the Python
verifier. Its receipt must bind this protocol, both source files and the primary
receipt by SHA-256 and must report the same three fixture classifications,
second-moment defects, retained/full gaps and mutation names.
The independent decision count is 55: the same 54 fixture, criterion, moment,
boundary and mutation checks as the primary schedule, plus one source-binding
check that the primary receipt has the frozen protocol and primary-source
hashes and passes 54/54. The source-binding check is an evidence-integrity
audit; the scientific schedule remains 54 checks.

## 5. Claim boundary and stopping rule

The analytic finite criterion is the identity in §1. The frozen executable
claims are limited to the three fixtures and their mutation controls. A PASS
means that exact all-moment matching is correctly reduced to a reducing-subspace
check in these finite positive examples and that completeness is not silently
inferred from retained correlations.

The receipts must retain:

```text
finite_transfer_criterion = PASS
exact_rg_block_map_constructed = false
interacting_transfer_operator_constructed = false
retained_observable_completeness_established = false
full_physical_gap_established = false
thermodynamic_limit_constructed = false
continuum_limit_established = false
continuum_mass_gap_established = false
clay_verdict = NULL
```

Run exactly once after this protocol and both sources are frozen. The primary
output is `runs/yang-mills-transfer-completeness/verification.json`; the
independent output is `verification-independent.json` in the same directory.
A source repair requires a distinct output path and a new protocol hash. Do not
add fixtures, moment orders, tolerances or mutations after the first qualified
pair.

## 6. References

- `foundations/loop-to-bubble-projection-theorem.md` §9.17—the qualified
  cylindrical map and its genuine-refinement leakage boundary.
- `foundations/loop-to-bubble-projection-theorem.md` §9.22—the residual-operator
  recovery criterion and the distinction between rigidity and a uniform floor.
- `foundations/loop-to-bubble-projection-theorem.md` §9.31—the conditional
  transfer-correlation and retained-completeness hypotheses.
- `computations/yang-mills-rg-gap-matching-prereg.md` §2—the conditional
  correlation-rate bridge whose missing inputs this finite diagnostic separates.

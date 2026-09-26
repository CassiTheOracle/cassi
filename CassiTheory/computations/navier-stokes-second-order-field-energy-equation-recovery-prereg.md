# Second-Order Field Energy: Scale-Sector and Equation-Residual Recovery

## Status: Pre-registered—September 2026

## 1. Trigger and retained evidence

The audit-qualified verifier run records **97/97** checks in
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.json`,
SHA-256
`7fa7d9dccdd5f4616dd5a37015892d569b7a7793cdd1c7879ffecbdf54e29a74`.
The verifier SHA-256 is
`26e66ad33fd4193c2d4e61e5df98562cc8343015f0eef4626e72f5b0900d65a2`.

Independent review finds two remaining evidence defects:

1. `foundations/particle-stationary-action-closure.md` (PA11)–(PA12)
   contains positive scale-curvature terms
   $\epsilon_{\mathfrak s}F_{t\mathfrak s}^2/2$ and
   $F_{i\mathfrak s}^2/(2\mu_{\mathfrak s})$. The displayed assumption
   $(D_{\mathfrak s}F_{t\mathfrak s})^a=0$ reduces the Gauss constraint but
   does not set either curvature to zero. The time–curl equality must therefore
   refer to the restricted $(ti,ij)$ connection-sector functional, with an
   explicit scale-flat slice, rather than to the full particle-action energy.
2. The Fourier fixture constructs `fixture_ut` and `fixture_utt` from the two
   Leray-projected right-hand sides. Its balance checks use those constructed
   arrays but do not compare either projected evolution equation with an
   independent calculation, as required by the parent protocol at line 429.

The 97-check receipt remains valid as constructed-right-hand-side and balance
consistency evidence, but it is not the terminal qualified receipt. Before the
new run, retain it unchanged as
`verification.audit-qualified.constructed-rhs-only.json`.

## 2. Fixed scale-sector qualification

Define only the nonnegative $(ti,ij)$ connection-sector functional

$$
\mathcal E_{A;ti,ij}
:=\int\left(
\frac{\epsilon_x}{2}F_{ti}^aF_{ti}^a
+\frac1{4\mu_x}F_{ij}^aF_{ij}^a
\right)dx.
\tag{SER1}
$$

On the one-color temporal-gauge map, impose the concrete scale-flat slice

$$
A_t^a=0,
\qquad
A_{\mathfrak s}^a=0,
\qquad
\partial_{\mathfrak s}A_i^a=0,
\qquad
A_i^a=\delta^{a3}\kappa_Au_i.
\tag{SER2}
$$

Then the one-color commutators vanish and

$$
F_{t\mathfrak s}^a=0,
\qquad
F_{i\mathfrak s}^a=0.
\tag{SER3}
$$

Together with $q_\Psi^a=q_\Phi^a=0$, (SER3) removes the scale term from the
Gauss constraint. It does not assert that matter, adjoint or carrier energies
in the full particle action equal zero. The exact time–curl identity is

$$
\frac{\mu_x}{\kappa_A^2}\mathcal E_{A;ti,ij}
=\frac12\left(
\|\omega\|_2^2+c_g^{-2}\|u_t\|_2^2
\right).
\tag{SER4}
$$

The verifier must add:

- **B12**, requiring the canonical $F_{t\mathfrak s}$ and
  $F_{i\mathfrak s}$ terms inside the tagged PA11–PA12 regions, so the omitted
  positive sectors are explicit;
- **B13**, an exact symbolic check that (SER2) makes both scale curvatures in
  (SER3) vanish.

The main paper and every graph summary must call (SER4) a restricted
connection-sector functional or equivalently qualified sub-sector map. The
paper also states $\varphi>0$, $\varphi^2=\varphi+1$, $c_s^2\ge0$ and
$\omega_0^2\ge0$ explicitly in the scalar-energy assumptions.

## 3. Independent projected-equation checks

Use the fixed datum from (SO39) with Fourier convention

$$
u(x)=\sum_{k\in\mathbb Z^3}\widehat u(k)e^{ik\cdot x}.
\tag{SER5}
$$

Construct an independent finite coefficient dictionary. Its only nonzero
entries are

$$
\begin{aligned}
\widehat u(\pm(1,0,0))&=\frac12(0,1,1),\\
\widehat u(\pm(0,1,0))&=\frac12(1,0,1),\\
\widehat u(1,1,0)&=-\frac{i}{2}(1,-1,1),\\
\widehat u(-1,-1,0)&=\frac{i}{2}(1,-1,1).
\end{aligned}
\tag{SER6}
$$

Every unspecified coefficient is zero. For coefficient dictionaries $a,b$,
compute the advective convolution without calling any NumPy-grid derivative,
advection, Laplacian or projector helper:

$$
\widehat{\mathcal A(a,b)}_j(k)
=i\sum_{\ell+m=k}\sum_{r=1}^3
m_r\widehat a_r(\ell)\widehat b_j(m).
\tag{SER7}
$$

For $k\ne0$, set $P_k=I-kk^{\mathsf T}/|k|^2$; set $P_0=I$. With
$\nu=0.37$, form

$$
\widehat u_t^{\rm ref}(k)
=-\nu|k|^2\widehat u(k)
-P_k\widehat{\mathcal A(u,u)}(k),
\tag{SER8}
$$

and

$$
\widehat u_{tt}^{\rm ref}(k)
=-\nu|k|^2\widehat u_t^{\rm ref}(k)
-P_k\left[
\widehat{\mathcal A(u_t^{\rm ref},u)}(k)
+\widehat{\mathcal A(u,u_t^{\rm ref})}(k)
\right].
\tag{SER9}
$$

The direct-convolution implementation must not call `gradient_vector`,
`advect_vector`, `laplacian_vector`, `leray_project`, `fixture_ut` or
`fixture_utt` while constructing the reference dictionaries. The finite
supports do not alias on the fixed $32^3$ grid.

Add:

- **E12**, comparing every normalized NumPy coefficient
  `fft_vector(fixture_ut) / N**3` with (SER10), including absent modes and
  $k=0$;
- **E13**, comparing every normalized NumPy coefficient
  `fft_vector(fixture_utt) / N**3` with (SER11), including absent modes and
  $k=0$.

Both checks use the parent absolute and relative tolerances. A check is not
satisfied by comparing a constructed array with the same helper expression
that created it.

## 4. Source manifest and decision rule

Add this protocol to the source-existence and frozen-hash manifest after it is
written and before implementation. No earlier protocol, receipt, fixture,
coefficient, tolerance, source equation or mathematical interpretation is
changed.

The terminal inventory contains exactly **103 checks**:

- F01–F11: source-existence checks;
- F12–F21: frozen external-source hashes;
- A01–A21, B01–B13, C01–C19, D01–D16 and E01–E13.

Run the corrected verifier once. Success requires **103/103** checks, schema
`cassi.navier-stokes.second-order-field-energy.verification.v2`, and terminal
`ALL CHECKS PASSED`. Any check or inventory failure records
`FAIL—SECOND-ORDER FIELD ENERGY AUDIT` and blocks documentary integration.
The run writes
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.json`
and leaves every retained failure, v1 and 97-check receipt unchanged.

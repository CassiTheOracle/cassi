# String-to-Bubble Projective Geometry: Rotation, Fivefold Orbits, and Qi Map Flow

## Status: Derived conditional projective and affine geometry; Derived conversion-only meridional flow; Hypothesized phase circulation and physical identification—August 2026

## Abstract

A normalized complex Yang/Yin pair defines a point of
$\mathbb{CP}^1\simeq S^2$. The quadratic bubble boundary defines an affine
image of that sphere. Their composition gives one explicit map from a
phase-bearing Yang/Yin state to the bubble shell. The positive-root density
section maps to one meridian string; the affine orbit of that meridian sweeps
the shell. Selecting the existing conditional $w=5$ subgroup gives a family
of pentagons and pentagrams on its latitude sections. Canonical Yang/Yin
conversion supplies meridional relaxation toward the $\varphi$-attractor
latitude. A phase-bearing extension can supply azimuthal motion, so the two
directions combine into a spiral shell flow.

The projective, affine, fivefold, and conversion-flow relations are exact
under their declared inputs. Dynamic bubble formation, selection of the
fivefold phase sectors, persistent azimuthal circulation, and identification
with a physical Qi current remain open.

---

## 1. Inputs and scope

This construction joins four existing results:

1. The canonical state is the nonnegative density pair $(E_Y,E_I)$ with
   $\rho=E_Y+E_I$ and $\varepsilon=E_Y-\varphi E_I$
   (`foundations/cassi-first-principles.md` §§1–2).
2. The adopted quantum-geometric direction uses a complex Yang/Yin pair whose
   modulus projection returns the canonical densities
   (`foundations/quantum-measurement-derivation.md` §8.3).
3. Near a condensation-site maximum, the selected bubble boundary has a
   quadratic triaxial-shell surrogate
   (`foundations/bubble-edge-geometry.md` §2).
4. The conditional compact golden-rotation construction selects $w=5$, and
   regular fivefold chord geometry contains $\varphi$
   (`foundations/wu-xing-derivation.md` §§2–3).

The construction is a map between declared geometries. Its physical
identification inherits the Hypothesized status of the complex phase sector,
the axial bubble coordinate, and the $w=5$ phase selector.

---

## 2. The projective Yang/Yin map

### 2.1 Complex lift and Bloch coordinates

For $\rho>0$, write a candidate complex pair as

$$
z_Y=\sqrt{E_Y}\,e^{i\theta_Y},
\qquad
z_I=\sqrt{E_I}\,e^{i\theta_I},
\qquad
z^\dagger z=\rho.
$$

After removing a common phase, its normalized representative is

$$
\widehat z
=e^{i\gamma}
\begin{pmatrix}
\cos(\vartheta/2)\\
e^{i\delta}\sin(\vartheta/2)
\end{pmatrix},
\qquad
\delta=\theta_I-\theta_Y.
$$

The associated unit Bloch vector is

$$
\mathbf n([z])
=\frac{1}{z^\dagger z}
\begin{pmatrix}
2\operatorname{Re}(z_Y^*z_I)\\
2\operatorname{Im}(z_Y^*z_I)\\
|z_Y|^2-|z_I|^2
\end{pmatrix}
=
\begin{pmatrix}
\sin\vartheta\cos\delta\\
\sin\vartheta\sin\delta\\
\cos\vartheta
\end{pmatrix},
\qquad
\mathbf n\cdot\mathbf n=1.
$$

The canonical density pair fixes

$$
s:=\cos\vartheta
=n_z
=\frac{E_Y-E_I}{E_Y+E_I}.
$$

The relative phase $\delta$ supplies the longitude. The positive-root section
$z=(\sqrt{E_Y},\sqrt{E_I})$ selects $\delta=0$ and therefore one meridian.

### 2.2 The affine shell map

Expand the supplied 3D condensation field around a maximum:

$$
B_n(x,y,z)
=\cos(\alpha x)\cos(\beta y)\cos(\gamma_n z)
=1-\frac12\left(\alpha^2x^2+\beta^2y^2+\gamma_n^2z^2\right)
+O(\|\mathbf x\|^4).
$$

At the selected level $B_n=\theta_{\mathrm{cond}}$, define

$$
A:=\sqrt{2(1-\theta_{\mathrm{cond}})},
\qquad
a_x:=\frac{A}{\alpha},
\quad
a_y:=\frac{A}{\beta},
\quad
a_z:=\frac{A}{\gamma_n},
\qquad
D:=\operatorname{diag}(a_x,a_y,a_z).
$$

The quadratic shell is

$$
\Sigma_n^{(2)}
:=\left\{\mathbf X:
\mathbf X^T D^{-2}\mathbf X=1\right\}.
$$

The explicit projective shell map is

$$
\boxed{
\mathcal P_D([z])
:=D\,\mathbf n([z])
=\frac{D}{z^\dagger z}
\begin{pmatrix}
2\operatorname{Re}(z_Y^*z_I)\\
2\operatorname{Im}(z_Y^*z_I)\\
|z_Y|^2-|z_I|^2
\end{pmatrix}
\in\Sigma_n^{(2)}.
}
$$

It is invariant under $z\mapsto c e^{i\gamma}z$ for every nonzero scalar
$c$. The map retains the projective composition and phase geometry while the
separate coordinate $\rho=z^\dagger z$ retains total density. The axes in $D$
come from the supplied quadratic bubble boundary. The full cosine level set
has flattened saddle regions, so $\mathcal P_D$ applies to its local
triaxial-shell surrogate.

The displayed map freezes one orientation convention: the density imbalance
$n_z$ is aligned with the shell $z$ axis, while the two relative-phase
quadratures are aligned with $x$ and $y$. The canonical densities and bubble
geometry supply no axis selector. The equally valid oriented family is

$$
\mathcal P_{D,O}([z])=D\,O\,\mathbf n([z]),
\qquad O\in SO(3).
$$

All shell identities below survive this replacement after the corresponding
rotation of their normalized coordinates. The document uses $O=I$. A
physical selector for $O$ remains Hypothesized.

### 2.3 The $\varphi$-attractor coherence ridge

The canonical scalar Qi diagnostic becomes

$$
q(\rho,\vartheta)
=
\left[
1+
\left(
\frac{\varphi^2\cos\vartheta-\varphi^{-1}}{2}
\right)^2
+\frac{\varphi^{-2}}{\rho^2}
\right]^{-1}.
$$

At fixed $\rho$, its composition maximum lies at

$$
\cos\vartheta_\varphi=\varphi^{-3},
\qquad
\vartheta_\varphi=\arccos(\varphi^{-3}).
$$

The shell image of this latitude is the ellipse

$$
\boxed{
\mathcal C_\varphi(\delta)
=
\begin{pmatrix}
a_x\sqrt{1-\varphi^{-6}}\cos\delta\\
a_y\sqrt{1-\varphi^{-6}}\sin\delta\\
a_z\varphi^{-3}
\end{pmatrix},
\qquad 0\leq\delta<2\pi.
}
$$

Thus the fixed-composition attractor becomes a closed coherence ridge on the
quadratic shell. Its scalar $q$ value still depends on $\rho$.

---

## 3. A meridian string sweeps the bubble shell

Define the positive-root meridian string

$$
\Gamma_0(\vartheta)
:=D
\begin{pmatrix}
\sin\vartheta\\0\\\cos\vartheta
\end{pmatrix},
\qquad 0\leq\vartheta\leq\pi.
$$

Let $R_z(\delta)$ be ordinary rotation about the normalized $z$ axis and
introduce its affine shell action

$$
G(\delta):=D R_z(\delta)D^{-1}.
$$

This is a one-parameter group,

$$
G(\delta_1)G(\delta_2)=G(\delta_1+\delta_2),
\qquad
G(\delta)^T D^{-2}G(\delta)=D^{-2},
$$

so it preserves the quadratic shell. Euclidean rigidity occurs only when
$a_x=a_y$. For $a_x\neq a_y$, $G(\delta)$ is an affine shell isometry in the
pullback metric $D^{-2}$. Its orbit of the meridian is

$$
\Gamma_\delta(\vartheta)
:=G(\delta)\Gamma_0(\vartheta)
=D
\begin{pmatrix}
\sin\vartheta\cos\delta\\
\sin\vartheta\sin\delta\\
\cos\vartheta
\end{pmatrix}.
$$

Therefore

$$
\boxed{
\Sigma_n^{(2)}
=
\bigcup_{0\leq\delta<2\pi}
\Gamma_\delta([0,\pi]).
}
$$

Within the declared geometry, a string is one projective meridian and the
bubble surface is its complete affine rotational orbit. This is a set and
group-action identity. A field equation that dynamically grows the full
surface from one meridian remains to be supplied.

---

## 4. Rotation-generated pentagons and pentagrams

### 4.1 The fivefold subgroup

The conditional $w=5$ construction selects the discrete subgroup

$$
C_5
:=\left\{
G\!\left(\frac{2\pi j}{5}\right)
\;\middle|\;
 j=0,1,2,3,4
\right\}.
$$

For an initial phase $\delta_0$ and any interior latitude
$0<\vartheta<\pi$, its orbit is

$$
\boxed{
\mathcal P_5(\vartheta,\delta_0)
=
\left\{
D
\begin{pmatrix}
\sin\vartheta\cos(\delta_0+2\pi j/5)\\
\sin\vartheta\sin(\delta_0+2\pi j/5)\\
\cos\vartheta
\end{pmatrix}
:j=0,\ldots,4
\right\}.
}
$$

As $\vartheta$ varies, these orbits form a nested family of affine pentagons
on the shell. Canonical conversion moves through this family by changing
$\vartheta$; phase evolution moves around a selected member by changing
$\delta$.

### 4.2 Pentagon and pentagram arithmetic

In normalized coordinates $\widetilde{\mathbf X}=D^{-1}\mathbf X$, the chord
length joining vertices separated by $m$ steps is

$$
d_m
=2\sin\vartheta\sin\!\left(\frac{m\pi}{5}\right),
\qquad m=1,2.
$$

Hence

$$
\boxed{
\frac{d_2}{d_1}
=
\frac{\sin(2\pi/5)}{\sin(\pi/5)}
=2\cos(\pi/5)
=\varphi.
}
$$

Joining step-one neighbors gives the regular pentagon. Joining step-two
neighbors gives the $\{5/2\}$ pentagram. Along every normalized pentagram
diagonal, the two crossings divide the full segment into fractions

$$
\boxed{
\varphi^{-2}:\varphi^{-3}:\varphi^{-2}.
}
$$

### 4.3 What survives the physical affine projection

For every positive diagonal $D$, the physical points
$\mathbf X=D\widetilde{\mathbf X}$ form affine images of the normalized
pentagon and pentagram. When $a_x\neq a_y$, those images are generally not
Euclidean regular. Affine maps preserve vertices, straight edges, incidences,
crossings, and collinear segment ratios. The
$\varphi^{-2}:\varphi^{-3}:\varphi^{-2}$ diagonal division therefore survives
on the physical shell.

Euclidean side and diagonal lengths depend on $a_x,a_y$, so their ratio
varies with orientation. The exact $d_2/d_1=\varphi$ result belongs to the
normalized coordinates or, equivalently, to the pullback metric

$$
ds_D^2=d\mathbf X^T D^{-2}d\mathbf X=d\mathbf n^T d\mathbf n.
$$

This distinction separates regular projective geometry from its
pentagon-like physical projection.

### 4.4 Selector boundary

Continuous $G(\delta)$ motion sweeps a smooth latitude ellipse. It transports
an existing angular spectrum according to
$a_m(t)=e^{-im\Omega t}a_m(0)$ and therefore supplies no spontaneous
$m=5$ mode. Five simultaneous vertices require selection of the five phases
$\delta_0+2\pi j/5$, or a memory that retains five successive samples. The
conditional golden-rotation construction supplies the $w=5$ candidate
selector. A potential proportional to
$1-\cos 5(\delta-\delta_0)$ would impose that selector rather than derive it.
A spontaneous realization requires phase-bearing equivariant dynamics whose
leading unstable or greatest-gain angular pair is $m=\pm5$, followed by
nonlinear saturation; its orientation remains neutral until a pinning
interaction acts. A fifth harmonic gives a rounded $C_5$ boundary. Exact
polygon edges require the piecewise polygon boundary, and the pentagram
additionally requires explicit step-two connectivity. The canonical
real-density PDE supplies none of these ingredients, so fivefold locking
remains Hypothesized.

---

## 5. Yin/Yang conversion and shell flow

### 5.1 Derived meridional motion

In the homogeneous q-gated conversion-only sector, set
$\kappa=\lambda(1-q)$. Then

$$
\dot E_Y=-\kappa\varepsilon,
\qquad
\dot E_I=+\kappa\varepsilon,
\qquad
\dot\rho=0.
$$

Because $s=\cos\vartheta=(E_Y-E_I)/\rho$,

$$
\dot s=-\frac{2\kappa\varepsilon}{\rho},
\qquad
\frac{\varepsilon}{\rho}
=\frac{\varphi^2\cos\vartheta-\varphi^{-1}}{2}.
$$

For $0<\vartheta<\pi$,

$$
\boxed{
\dot\vartheta_{\mathrm{conv}}
=\lambda(1-q)
\frac{\varphi^2\cos\vartheta-\varphi^{-1}}
{\sin\vartheta}.
}
$$

The endpoint-safe equation is the displayed equation for $\dot s$. The rate
points toward $\vartheta_\varphi$ from both sides and vanishes at
$\cos\vartheta_\varphi=\varphi^{-3}$. This gives a derived meridional
relaxation on the projective map. In an ungated conversion arm, the same
identity uses $\kappa=\lambda$.

### 5.2 Azimuthal phase motion

Let

$$
\Omega_\delta:=\dot\delta
$$

be the relative-phase rate of a phase-bearing extension. The shell tangent
vectors are

$$
\partial_\vartheta\mathbf X
=
\begin{pmatrix}
a_x\cos\vartheta\cos\delta\\
a_y\cos\vartheta\sin\delta\\
-a_z\sin\vartheta
\end{pmatrix},
\qquad
\partial_\delta\mathbf X
=
\begin{pmatrix}
-a_x\sin\vartheta\sin\delta\\
a_y\sin\vartheta\cos\delta\\
0
\end{pmatrix}.
$$

They are orthogonal in the pullback metric $ds_D^2$, with squared norms $1$
and $\sin^2\vartheta$. Their combined map velocity is

$$
\boxed{
\dot{\mathbf X}
=
\dot\vartheta_{\mathrm{conv}}\,
\partial_\vartheta\mathbf X
+
\Omega_\delta\,
\partial_\delta\mathbf X.
}
$$

The first term is canonical conversion expressed on the shell. The second
requires phase dynamics. When both are present, the path spirals toward the
attractor latitude. At the attractor, the meridional term vanishes and a
nonzero $\Omega_\delta$ gives circulation around $\mathcal C_\varphi$.

### 5.3 Relation to the canonical Qi diagnostics

On the positive-root section, the existing lift angle is

$$
\theta_\Psi
=\operatorname{atan2}(\sqrt{E_I},\sqrt{E_Y})
=\frac{\vartheta}{2},
$$

so its spatial diagnostic becomes

$$
\boxed{
\mathbf J_\Psi^{(+)}
=\rho\nabla\theta_\Psi
=\frac{\rho}{2}\nabla\vartheta.
}
$$

This gives the canonical positive-root diagnostic a meridional reading on the
projective map. The scalar $q$ retains its canonical definition. The
azimuthal term contains the relative phase $\delta$, which the canonical
state omits. Turning either map velocity or phase gradient into a physical Qi
current requires a constitutive map, physical density normalization, and a
transport law.

---

## 6. Geometric circulation diagnostic

For the normalized section with $\gamma=0$, the standard projective
connection is

$$
\mathcal A
:=-i\widehat z^\dagger d\widehat z
=\frac{1-\cos\vartheta}{2}\,d\delta,
$$

with curvature

$$
\mathcal F=d\mathcal A
=\frac12\sin\vartheta\,d\vartheta\wedge d\delta.
$$

Around the attractor latitude,

$$
\boxed{
\Gamma_\varphi
:=\oint_{\mathcal C_\varphi}\mathcal A
=\pi(1-\varphi^{-3})
\pmod{2\pi}.
}
$$

Five equal phase steps each carry the geometric increment

$$
\Delta\Gamma_5
=\frac{\pi}{5}(1-\varphi^{-3}),
\qquad
5\Delta\Gamma_5=\Gamma_\varphi.
$$

These are generic $\mathbb{CP}^1$ Berry-geometry identities evaluated on the
Cassi attractor latitude. They provide a phase-loop diagnostic. A
Cassi-specific dynamical connection, Wilson loop, and physical holonomy
observable remain open, consistent with GQ7 in
`foundations/quantum-measurement-derivation.md` §8.3.

---

## 7. Epistemic ledger

| Result | Status | Boundary |
|---|---|---|
| Complex pair modulo common phase gives $\mathbb{CP}^1\simeq S^2$ | Derived conditional | Requires the adopted complex Yang/Yin lift |
| $\mathcal P_D([z])=D\mathbf n([z])$ lies on $\Sigma_n^{(2)}$ | Derived conditional geometry | $D$ comes from the supplied quadratic bubble boundary |
| Positive-root meridian orbit sweeps $\Sigma_n^{(2)}$ | Derived conditional geometry | Group-action identity; dynamic surface formation remains open |
| $C_5$ orbit gives a pentagon and $\{5/2\}$ pentagram | Derived conditional geometry | Requires selection of five phase sectors |
| Normalized chord ratio $d_2/d_1=\varphi$ and diagonal fractions | Derived geometry | Physical Euclidean chord ratio varies under anisotropic $D$; collinear fractions persist |
| Canonical q-gated conversion gives $\dot\vartheta_{\mathrm{conv}}$ | Derived in the conversion-only sector | Advection and diffusion require the full spatial evolution |
| $\Omega_\delta\partial_\delta\mathbf X$ gives azimuthal shell motion | Hypothesized dynamics | Canonical real densities contain no relative phase equation |
| $\mathcal A$, $\mathcal F$, and $\Gamma_\varphi$ | Derived generic projective geometry | Physical connection and observable remain open |
| Shell map as physical space and map flow as physical Qi current | Hypothesized identification | Requires constitutive, normalization, transport, and observation maps |

---

## 8. Decisive next gates

1. **Phase dynamics:** derive or independently specify an equation for
   $\delta$ and test whether $\Omega_\delta$ persists after the meridional
   variable reaches $\vartheta_\varphi$.
2. **Fivefold selection:** test a phase-bearing solver against a rotationally
   symmetric null. The selected model must produce a preregistered fifth
   angular harmonic without inserting five phase sectors into the initial
   state or readout.
3. **Boundary realization:** test whether the evolved field develops the full
   $B_n=\theta_{\mathrm{cond}}$ level set and quantify the range where the
   quadratic shell is accurate.
4. **Physical current:** supply one constitutive map from
   $(\rho,q,\vartheta,\delta)$ and the shell tangent velocity to a measured
   current, with dimensions and normalization fixed before comparison.
5. **Projection discriminator:** compare the projective-shell map with a
   phase-scrambled control that preserves $(E_Y,E_I)$ pointwise. Equal
   observables leave the relative phase physically unidentified.

The algebraic checks are frozen in
`computations/string-bubble-projective-map-pre-registration.md` and executed
by `computations/verify_string_bubble_projective_map.py`.

---

## References

- `foundations/cassi-first-principles.md`—canonical densities, scalar $q$,
  rank-one conversion, and positive-root diagnostics
- `foundations/quantum-measurement-derivation.md` §8.3—adopted
  moment-map/Kähler architecture and its phase-fibre boundaries
- `foundations/bubble-edge-geometry.md` §2—quadratic condensation-boundary
  axes and full cosine-level-set boundary
- `foundations/wu-xing-derivation.md` §§2–3—conditional $w=5$ selector and
  regular pentagon arithmetic
- `foundations/wu-xing-cycle-structure.md`—step-one and step-two five-cycles
- `computations/string-bubble-projective-map-pre-registration.md`—frozen
  identity gates
- `computations/verify_string_bubble_projective_map.py`—independent numeric
  verification

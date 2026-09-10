# QCD Target and Confining Carrier Protocol

## Status: Preregistered—September 2026

## Abstract

This calculation separates the empirical microscopic target from the low-energy
model used for a tractable matter-formation calculation. Renormalized two-flavour
QCD supplies the target color theory. A finite-cutoff chromodielectric
quark–meson action supplies an explicit bridge to the regular carrier qualified
in `computations/matter-formation-continuum-report.md` §79. The bridge preserves
local color gauge symmetry, global baryon number and chiral-zero regularity,
includes a regulator-defined fermion determinant, and makes every state with
nonzero total color charge infinitely energetic in the zero-dielectric,
infinite-volume limit. A finite three-arm color-neutral flux network provides
the comparison witness. The action and its parameters remain external QCD
content; this protocol tests internal mathematical closure and does not claim a
Cassi derivation of QCD.

## 1. Question and scope

The active quark–meson carrier has explicit Dirac quarks and an exact baryon
current, but color is only a spectator index. This calculation asks whether one
fully specified, symmetry-compatible low-energy extension supplies all of the
following at once:

1. a regular local action through
   $(\sigma,\boldsymbol\pi)=\boldsymbol0$;
2. local $SU(3)_C$ gauge symmetry and exact global vector $U(1)_B$;
3. a gauge-invariant finite-cutoff regulator with a defined fermion sea and
   fixed-$B$ state;
4. infinite energy for nonzero total color charge as the exterior dielectric
   regulator vanishes and volume grows;
5. a finite-energy color-neutral three-arm flux witness.

Passing these tests qualifies a confining effective carrier action for later
static and real-time work. It does not establish the QCD mass gap, a Wilson-loop
area law for continuum QCD, the physical baryon spectrum, a thermal formation
rate, baryogenesis, or complete physical matter formation.

## 2. Frozen actions

### 2.1 Empirical microscopic target

The selected microscopic color target is renormalized two-flavour QCD,

$$
\mathcal L_{\rm QCD}
+=-\frac14G^a_{\mu\nu}G^{a\mu\nu}
++\sum_{f=u,d}\bar q_f(i\gamma^\mu D_\mu-m_f)q_f,
\qquad
D_\mu=\partial_\mu-i g_s A_\mu^aT^a.
$$

The gauge group, quark representations, coupling, masses and renormalization
conditions are empirical Standard Model inputs. The canonical Cassi two-density
PDE does not select them. QCD is the ultraviolet target because it is the
renormalizable asymptotically free theory supported by particle data; the
bridge below is a finite-cutoff effective action.

### 2.2 Independent-dielectric quark–meson bridge

Let

$$
\Phi_A=(\sigma,\pi^1,\pi^2,\pi^3),\qquad
x=\frac{\chi}{\chi_v},
$$

with $\chi$ a color-singlet dielectric field independent of the chiral
multiplet. The bridge action is

$$
\boxed{
\begin{aligned}
\mathcal L_{\rm CDQM,\epsilon}
={}&\bar q\left[
 i\gamma^\mu D_\mu
 -g\,F(x)(\sigma+i\gamma^5\tau^a\pi^a)
 \right]q\\
&+\frac12\partial_\mu\Phi_A\partial^\mu\Phi_A-V_\Phi(\Phi)
 +\frac12\partial_\mu\chi\partial^\mu\chi-U_\chi(x)\\
&-\frac14\kappa_\epsilon(x)G^a_{\mu\nu}G^{a\mu\nu}
 +\mathcal L_{\rm gf+gh}+\mathcal L_{\rm ct}(a).
\end{aligned}}
$$

The frozen functions are

$$
\boxed{
F(x)=x^2,\qquad
\kappa_\epsilon(x)=(1-x^3)^2+\epsilon,
\qquad
U_\chi(x)=B(1-x)^2(1+2x+4x^2).
}
$$

The chiral potential and empirical quark–meson inputs remain those of §79,

$$
V_\Phi
=\frac{\lambda_\Phi}{4}(\Phi_A\Phi_A-v^2)^2-H\sigma-C_{\rm vac},
$$

with $f_\pi=93\ {\rm MeV}$, $m_\pi=139.6\ {\rm MeV}$,
$m_\sigma=1200\ {\rm MeV}$, $M_q=500\ {\rm MeV}$,
$N_f=2$, $N_c=3$, and $g=M_q/f_\pi$. The dielectric scales
$B>0$ and $\chi_v>0$ require independent matching before a physical spectrum
calculation. The dimensionless verification sets $B=\chi_v=1$ and never fits
them to a hadron observable.

The factor $F(x)$ is a chiral singlet. It couples the dielectric and chiral
sectors without a standalone $\chi\bar q q$ mass, so the Yukawa operator stays
regular when $\Phi_A=0$. The exterior vacuum is $x=1$, where
$\kappa_0=0$ and $F=1$; the dielectric interior is $x=0$, where
$\kappa_0=1$ and $F=0$.

### 2.3 Regulator, sea and state

At lattice spacing $a$ and $\epsilon>0$, the definition uses compact Wilson
links, a plaquette coefficient equal to the positive plaquette average of
$\kappa_\epsilon$, Wilson fermions with $r=1$, and nearest-neighbour scalar
kinetic terms. Gauge fixing and ghosts are needed only in a gauge-fixed
continuum representation; the compact lattice measure is gauge invariant.
For two degenerate flavours at zero chemical potential, the sea weight is

$$
\det(D_W^\dagger D_W)\ge0.
$$

Equivalently, the subtracted sea contribution is recorded as

$$
S_{\rm sea}^{\rm sub}
=-\frac{N_f}{2}\operatorname{Tr}\log
\frac{D_W^\dagger D_W}{D_{W,{\rm vac}}^\dagger D_{W,{\rm vac}}}
+S_{\rm ct}(a).
$$

The counterterm basis contains every local operator allowed by the retained
symmetries through the declared cutoff order, and its coefficients are fixed by
vacuum renormalization conditions before a hadron calculation. Since
the $F(x)$ Yukawa factor and $\kappa(x)G^2$ expand into operators above
dimension four, the
bridge remains a Wilsonian finite-cutoff theory. No $a\to0$ ultraviolet
completion is inferred from it.

A conditional one-baryon equilibrium state is

$$
\rho_{B=1}^{(a,\epsilon)}
=\frac{P_G P_{B=1}e^{-\beta H_{a,\epsilon}}P_{B=1}P_G}
 {\operatorname{Tr}(P_G P_{B=1}e^{-\beta H_{a,\epsilon}})},
$$

where $P_G$ projects the local Gauss constraints and $P_{B=1}$ projects

$$
Q_B=\frac13\int d^3x\,q^\dagger q=1.
$$

This state includes valence, antiquark and sea sectors without assigning
baryon number to chiral winding. In an unconditioned QCD-era ensemble, the
chemical potential or fixed-sector weights must instead be set by the inherited
cosmological baryon asymmetry.

## 3. Frozen exact statements

### 3.1 Symmetry and regularity

All bridge terms are local $SU(3)_C$ singlets. The transformation
$q\mapsto e^{i\alpha/3}q$ gives

$$
\partial_\mu j_B^\mu=0,
\qquad
j_B^\mu=\frac13\bar q\gamma^\mu q.
$$

Both $F$ and $\kappa_\epsilon$ are polynomials in the independent scalar $x$.
At $\Phi_A=0$ the Yukawa operator vanishes and every coefficient remains
finite. For real $x$,

$$
\kappa_\epsilon(x)\ge\epsilon>0,
\qquad
U_\chi(x)\ge0.
$$

At $\epsilon=0$, $\kappa_0$ has its only real zero at $x=1$. The dielectric
potential has a false local minimum at $x=0$, a barrier at $x=1/8$, and the
global vacuum at $x=1$:

$$
U_\chi(0)=B,
\quad U_\chi(1/8)=\frac{1029}{1024}B,
\quad U_\chi(1)=0,
$$

with dimensionless curvatures
$(d^2U_\chi/dx^2)_{x=0}/B=2$ and
$(d^2U_\chi/dx^2)_{x=1}/B=14$.

### 3.2 Rejected field-minimal control

The action obtained by setting
$\kappa_{\rm min}=(1-\Phi_A\Phi_A/f_\pi^2)^2$ adds no independent dielectric
field. On the normalized $a=1$ hedgehog used by the existing carrier,
$\Phi_A\Phi_A=f_\pi^2$ pointwise, so

$$
\kappa_{\rm min}=0
$$

through the entire interior as well as the exterior. This control cannot carry
an interior color field on that branch. The independent $\chi$ action is the
frozen candidate.

### 3.3 Infinite energy for nonzero total color charge

Consider an asymptotic Abelian Cartan component with enclosed color charge
$Q\ne0$. Gauss' law gives

$$
D_r(r)=\frac{Q}{4\pi r^2}.
$$

The nonnegative radial energy contains

$$
\frac{dE}{dr}
=4\pi r^2\left[
 \frac12\chi_v^2(x')^2+U_\chi(x)
\right]
+\frac{Q^2}{8\pi r^2\kappa_0(x)}.
$$

Every admissible configuration with the boundary condition $x(r)\to1$
eventually lies in
$1/2\le x\le3/2$. In that interval,

$$
U_\chi\ge3B(1-x)^2,
\qquad
\kappa_0
=(1-x)^2(1+x+x^2)^2
\le\frac{361}{16}(1-x)^2.
$$

Dropping the positive gradient term and applying the arithmetic–geometric mean
inequality gives the radius-independent lower bound

$$
\boxed{
\frac{dE}{dr}
\ge \frac{4\sqrt6}{19}|Q|\sqrt B>0.
}
$$

Hence

$$
\lim_{L\to\infty}E_Q(L)=\infty
$$

for every state carrying nonzero total Cartan charge. The same conclusion
applies to any nonzero vector in the Cartan weight plane. This is an
action-level Gauss-sector confinement statement for the bridge, rather than a
proof of continuum-QCD confinement.

For a sharp asymptotic check, write $x=1-c/r$. The leading shell energy is

$$
\frac{dE}{dr}
=28\pi Bc^2+\frac{Q^2}{72\pi c^2}+O(r^{-1}),
$$

whose minimizer and coefficient are

$$
c_*=\left(\frac{Q^2}{2016\pi^2B}\right)^{1/4},
\qquad
\left.\frac{dE}{dr}\right|_{c_*}
\longrightarrow\frac{\sqrt{14}}{3}|Q|\sqrt B.
$$

### 3.4 Finite color-neutral witness

The three fundamental color weights may be chosen as

$$
\mathbf w_r=\left(\frac12,\frac{1}{2\sqrt3}\right),\quad
\mathbf w_g=\left(-\frac12,\frac{1}{2\sqrt3}\right),\quad
\mathbf w_b=\left(0,-\frac{1}{\sqrt3}\right),
$$

so $\mathbf w_r+\mathbf w_g+\mathbf w_b=0$ and
$|\mathbf w_i|=1/\sqrt3$. Three compact flux tubes can therefore terminate at
a common junction with no exterior flux. A thin-wall tube with radius $R$ and
charge magnitude $Q_i=g_s/\sqrt3$ has the finite trial tension

$$
T_i(R)=\frac{Q_i^2}{2\pi R^2}+\pi BR^2+2\pi\sigma_\chi R,
$$

where

$$
\sigma_\chi
=\chi_v\sqrt{2B}\int_0^1
 (1-x)\sqrt{1+2x+4x^2}\,dx>0.
$$

$T_i(R)$ tends to infinity at both endpoints $R\to0$ and $R\to\infty$, so it
has a finite positive minimizer. For finite arm lengths, the three-arm network
has finite total energy. The associated gauge-invariant baryon interpolator is

$$
\mathcal B
=\epsilon_{abc}
 [U(x_J,x_1)q(x_1)]^a
 [U(x_J,x_2)q(x_2)]^b
 [U(x_J,x_3)q(x_3)]^c.
$$

This witness establishes that the zero-dielectric limit does not remove the
color-neutral sector.

## 4. Numerical schedule

The primary program is `computations/qcd_confining_carrier.py`. It uses
$B=\chi_v=g_s=1$ only to verify dimensionless identities and never to predict a
hadron observable.

1. Evaluate the polynomial coefficients, stationary points, curvatures, and
   nonnegativity on 200,001 equally spaced $x$ values over $[-4,4]$.
2. Evaluate $\kappa_\epsilon$ for
   $\epsilon\in\{10^{-2},10^{-4},10^{-6},10^{-8}\}$ and confirm that its
   global sampled minimum equals $\epsilon$ at $x=1$.
3. Evaluate the normalized-hedgehog field-minimal control on 4,097 radii over
   $0\le r\le12\ {\rm fm}$.
4. Evaluate the exact isolated-color lower bound and the asymptotic trial at
   $r\in\{16,32,64,128,256,512\}$ with $Q=1$. Integrate the full trial tail
   over $r\in[16,L]$ for
   $L\in\{32,64,128,256,512\}$ and fit the final three energies to a line.
5. Compute $\sigma_\chi$ by adaptive quadrature. Minimize the thin-wall tension
   for all three equal-magnitude weights over
   $10^{-4}\le R\le10^4$ and report the unique positive stationary radius,
   tension, and endpoint controls.
6. Write full-precision JSON to
   `runs/20260910_qcd_confining_carrier/primary/results.json`.

The independent program
`computations/verify_qcd_confining_carrier.py` reconstructs the polynomial
roots algebraically, evaluates the confinement bound from separate interval
extrema, integrates the asymptotic tail with independent high-precision
quadrature, solves the tube-radius equation by bracketed root finding, checks
source and receipt hashes, and writes
`runs/20260910_qcd_confining_carrier/verification/verification.json`.

## 5. Frozen decisions

### RCF1—local action and symmetry

`PASS` requires correct mass dimensions, finite coefficients at
$\Phi_A=0$, sampled $\kappa_\epsilon\ge\epsilon-10^{-13}$ and
$U_\chi\ge-10^{-13}$, the exact stationary points and curvatures above, and
symbolic compatibility with local $SU(3)_C$, chiral $SU(2)_L\times SU(2)_R$
and global vector $U(1)_B$. Otherwise RCF1 is `FAIL`.

### RCF2—regulator, sea and state

`PASS` requires an explicitly positive finite-$a$, finite-$\epsilon$ compact
lattice action; the two-flavour $\det(D_W^\dagger D_W)$ sea; a declared
counterterm/matching prescription; the gauge- and fixed-$B$-projected density
operator; and explicit classification of the bridge as a finite-cutoff EFT.
Any omitted item or continuum-UV claim makes RCF2 `FAIL`.

### RCF3—isolated color

`PASS` requires the exact lower-bound coefficient
$4\sqrt6/19$ to be positive, every full trial shell energy finite, relative
error below $5\times10^{-3}$ between the $r=512$ shell energy and
$\sqrt{14}/3$, relative error below $10^{-2}$ between the final-three-point
integrated slope and $\sqrt{14}/3$, and independent agreement on every value
to relative error below $2\times10^{-10}$. Otherwise RCF3 is `FAIL`.

### RCF4—color-neutral witness

`PASS` requires the three weights to sum to zero within $10^{-14}$, their
magnitudes to agree within $10^{-14}$, finite positive $\sigma_\chi$, one
positive tension minimizer with absolute derivative residual below
$10^{-10}$, finite positive tension there, each frozen endpoint tension at
least $10^6$ times the minimum, and independent relative
agreement below $2\times10^{-10}$. Otherwise RCF4 is `FAIL`.

### RCF5—bridge decision

`ADOPT` requires RCF1–RCF4 all `PASS`. It qualifies the CDQM action as a
regulator-defined confining effective carrier and makes it the active static
bridge to the empirical QCD target. Any failed prerequisite makes RCF5
`REJECT`.

### RCF6—physical completion

RCF6 is `FAIL` and `complete_physical_matter_formation=false` for either RCF5
outcome. The protocol contains no matched $(B,\chi_v)$ determination, full
non-Abelian spectrum, continuum nonradial soliton, real-time thermal ensemble,
formation probability, nucleon observable map, electroweak baryogenesis, or
Cassi derivation of QCD.

## 6. Stopping rule

The protocol, primary source and independent source are frozen before either
program runs. Each executes once. A source defect may be corrected only when
it contradicts this protocol; the failed receipt remains preserved and the
recovery uses a new output directory. Physics functions, constants, samples,
thresholds and verdict rules remain fixed. Execution stops after independent
reconstruction and joint verdict comparison.

## References

- `computations/matter-formation-continuum-report.md` §§78–80—normalized-chiral obstruction, regular explicit-quark carrier and rejected scalar stabilizer.
- `foundations/matter-completion-boundary.md` §§23–25—regularity, carrier and stabilization boundaries.
- L. Wilets, S. Hartmann and P. Tang, [“The Chromo-Dielectric Soliton Model: Quark Self Energy and Hadron Bags”](https://arxiv.org/abs/nucl-th/9608018)—color-dielectric quark action and confinement setting.
- D. Diakonov, [“Chiral Quark-Soliton Model”](https://arxiv.org/abs/hep-ph/9802298)—explicit-quark chiral carrier and renormalized-sea context.
- K. G. Wilson, [“Confinement of Quarks”](https://doi.org/10.1103/PhysRevD.10.2445)—compact lattice gauge regulator and gauge-invariant confinement observables.

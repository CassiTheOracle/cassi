# A Search for a $\varphi$-Free Selection Principle for the Loop's Conversion Rate Ratio

## Status: Analysis—September 2026. Candidate functionals and invariances evaluated on the loop's own data by algebra and small numerical checks; no field runs, no measurement, no change to any canonical equation.

## Abstract

`foundations/phi-input-or-selection.md` records that $\varphi$ enters the canonical
two-fluid framework at four coefficient slots, and that the obvious derivation does not
work: for the whole family of conversion operators with the loop's own structure, an
attracting composition ratio always exists, and its value is the member's own coarse rate
ratio $b/a$ (`foundations/phi-input-or-selection.md:143-190`). Its closing sentence names
the missing object: a $\varphi$-free functional, symmetry, or microscopic derivation on the
loop's own data whose extremum or invariance fixes $b/a$, together with a physical
statement whose solution is the worst-approximable separation (`:233-238`).

This file tests thirteen candidates of that kind. Four families fail for structural
reasons that hold for every member, so no amount of further search within them will
succeed: every spectral functional of the conversion operator is blind to the ratio and
sees only the sum $a+b$; every functional symmetric under the Yang/Yin exchange has
$r=1$ as a critical point and can reach the golden ratio only by being stationary at
$t=r+1/r=\sqrt5$; the counterflow-current sector is exactly invariant under changes of the
conversion ratio; and the projection acts as the identity on the ratio, so self-similarity
under it is vacuous. The remaining candidates either return a supplied coefficient (a
mobility or stiffness ratio), a rational ratio, or a relation among the loop's own
supplied rates.

Four candidates return $\varphi$ exactly. None of them fixes $b/a$. The self-similarity
requirement $(a+b)/b=b/a$ returns $\varphi$ by three independent routes, and its content
is the golden equation itself, so it relocates the input instead of removing it; the same
family of self-references also returns $1/\varphi$, the plastic number, $1/\sqrt2$, and
$1$. The de-resonance statistic returns $\varphi$ as the maximiser of the
worst-approximability measure with a genuinely $\varphi$-free definition and a
$\varphi$-free admissible set, which satisfies the audit's discriminator as stated, but
the statistic is a functional of the ratio's value, no equation of the loop law evaluates
it, and over the compact loop's own admissible set the statistic is constant. The
closure-exactness condition of the projection selects $\varphi$ through the chart in its
own definition. The fivefold orbit's chord ratio is $\varphi$ with no $\varphi$ anywhere,
and the value arrives through the integer $5$.

The search also turns up one gap in the discriminator itself: as stated it admits axioms
that contain no $\varphi$ while being equivalent to $b/a=\varphi$. A third clause is
needed.

The integer $5$ behind the fifth candidate has a source, traced in §7. It is supplied by the
same unforced input as the ratio, not by an object the loop offers. Among the origins the loop
can offer (its population and incidence counts, the dimension of its null space, the minimal
winding compatible with positivity, the normalization of its own metric, and the minimal
polynomial of the de-resonance statistic), none forces $n=5$ independently of $\varphi$: the
two are tied by $2\cos(\pi/5)=\varphi$, $\operatorname{disc}(x^2-x-1)=5$ and
$\sqrt5=2\varphi-1$, so why-five is why-$\varphi$ in another coordinate and the smallest gap
does not move down a level. The coherence route's selection of $5$ is, in addition,
threshold-exponent sensitive: with two cascade steps per cycle vertex it returns $13$. A
cross-check of the blindness result against the theory documents (§8) finds four sentences
that draw the ratio, or evidence for it, from a rate reading; each is a joint check of the
declared pair, none requires a physics correction, and all four are listed for their owners.

## 1. The quantity to be fixed, and the discriminators

### 1.1 The target

The loop law (`foundations/loop-to-bubble-projection-theorem.md:321-341`, (LB6)) carries
four nonnegative populations, Yang and Yin in two counterorientations of one closed loop,
with direction-preserving conversion at rates $\kappa$ and $\varphi\kappa$. Its complete
loop projection obeys the canonical densities exactly (`:351-408`, Theorem 1; (LB7) at
`:364-376`). The audit's coarse family replaces the declared pair by an arbitrary
nonnegative pair $(a,b)$:

$$
\partial_tE_Y=-aE_Y+bE_I,\qquad \partial_tE_I=+aE_Y-bE_I,\qquad r:=\frac{b}{a}.
$$

Conservation of $\rho=E_Y+E_I$ holds for every member (`:414-417`, (LB11); `:426-430`), the
block is rank one with zero column sums and spectrum $\{0,-(a+b)\}$, and the attracting
ratio is $r$ (`foundations/phi-input-or-selection.md:157-162`). The declared member
recovers the canonical block $\kappa\begin{pmatrix}-1&\varphi\\1&-\varphi\end{pmatrix}$
(`foundations/cassi-first-principles.md:198-208`) at $b/a=\varphi$.

The loop's own data available to a selector are its geometry and its rates:

| Object | Symbol | Source |
|---|---|---|
| loop transport rate, loop diffusivity | $\Omega=v/R$, $d=D_\ell/R^2$ | (LB4), `foundations/loop-to-bubble-projection-theorem.md:302-306` |
| direction-exchange rate | $r$ | (LB6), `:321-341` |
| conversion gate | $\kappa=\lambda[1-q(E_Y,E_I)]$ | (LB5), `:313-315` |
| frozen internal spectrum | $\Lambda_{m,c,\pm}=-dm^2+c-r\pm\sqrt{r^2-m^2\Omega^2}$, $c\in\{0,-\kappa(1+\varphi)\}$ | (LB36), `:790-798` |
| total density and orientation current | $F_s$, $F$, $H$, $j_\ell=vH$ | (LB40)–(LB44), `:869-904` |
| phase-gradient ratio and current closure | $\alpha=k_I/k_Y$, $\alpha=(\mu_Y/\mu_I)(E_Y/E_I)-J_0/(\mu_IE_Ik_Y)$ | `principles/de-resonance-principle.md:153-180` |
| fivefold orbit chord ratio | $L_{\rm step\,2}/L_{\rm step\,1}$ | (LB48)–(LB50), `:977-1012` |

### 1.2 The discriminator, and a third clause it needs

The audit's test for "the framework derives $\varphi$" is conjunctive
(`foundations/phi-input-or-selection.md:126-141`):

- **D1** the definition of the quantity $Q$ contains no $\varphi$;
- **D2** the derivation's inputs contain no $\varphi$.

Section 5.3 exhibits a $\varphi$-free axiom equivalent to the conclusion, which both
clauses accept while nothing is derived. The statement of the test therefore needs

- **D3** the derivation introduces no premise whose content is the golden equation
  $r^2=r+1$ under another name.

D3 is not a stylistic addition. Several of the candidates below are families indexed by a
free choice of self-reference, and the value returned is a function of that choice alone.

**D3's operational test, so that a reader can disagree with it.** A premise fails D3 only
when it is reducible to $r^2=r+1$ by an *explicit substitution chain that the derivation
exhibits*, each step an identity or a stated equivalence, ending at the golden equation.
Resemblance is not enough, and a premise whose *solution* happens to be a golden quantity
does not fail D3 unless the chain is written out. The clause is therefore falsifiable in
both directions: a golden outcome in §3 or §4 whose premise admits no such chain is a
counterexample to D3's application and the derivation survives, while a premise whose chain
is exhibited cannot be rescued by rephrasing.

**The control that fires D3.** The family of §3.5: one self-reference, six relations, all
with $\varphi$-free definitions and inputs, returning $\varphi$, $1/\varphi$, the plastic
number, $1/\sqrt2$ and $1$. D1 and D2 cannot separate the six, since every member passes
both, yet they cannot all be derivations of the number they return; each member's premise is
a one-step substitution chain into its own conclusion. Candidate 8 (§3) is the member whose
chain ends at $r^2=r+1$ under $r\mapsto1+1/r$, so D3 rejects it and leaves the other twelve
candidates' status unchanged. Section 5.3 carries the same finding for the geometric
member.

## 2. The candidates

### 2.1 Table

Every extremum below was computed symbolically (SymPy 1.14) or numerically (NumPy 2.5,
mpmath, 40-digit working precision) on matrices no larger than $4\times4$ and on
loop grids of $2^{9}$ points. Entries marked $(\ast)$ are the members of the required
candidate list in the task that produced this file.

| # | Candidate | Definition | Inputs $\varphi$-free? | Extremum computed | Extremum is $\varphi$? | Where it fails |
|---|---|---|---|---|---|---|
| 1$(\ast)$ | Rayleigh quotient of the conversion operator on the fixed-density simplex | $Q(p)=x^{\mathsf T}Mx$, $x=(p,1-p)$, $M=\begin{pmatrix}-a&b\\a&-b\end{pmatrix}$; (LB32) `:745-755`, `foundations/cassi-first-principles.md:198-208` | yes | $Q(p)=-(2p-1)((a+b)p-b)$; interior maximum at $p^\ast=(a+3b)/(4(a+b))$ with quotient $(a+3b)/(3a+b)$; minima $-a$, $-b$ at the simplex endpoints; zero on the fixed ray $p=b/(a+b)$ | no | the interior extremum is a function of the same pair; requiring it to coincide with the fixed ray gives $r=1$ |
| 2$(\ast)$ | de-resonance statistic on the ratio's value | $c(r)=\liminf_{q\to\infty}q\,\lVert qr\rVert$, $L(r)=1/c(r)$; `principles/de-resonance-principle.md:68-81` | yes | $c(\varphi)=c(1/\varphi)=c(\varphi^2)=0.4472135954999579=1/\sqrt5$; $c(\sqrt2)=0.353553390593274$; $c(\sqrt3)=0.288675134594813$; $c(p/q)=0$ | **yes** | an arithmetic functional of the value; no equation of the loop evaluates it, and over the compact loop's admissible set (rationals) it is constant |
| 3$(\ast)$ | minimum dissipation / maximum entropy production on the steady state | $\sigma=(aE_Y-bE_I)\ln\left(aE_Y/(bE_I)\right)$ for the conversion channel | yes | $\sigma\geq0$ with equality exactly on the member's own ray $E_Y/E_I=b/a$; on the fixed reference state $(1,\varphi^{-1})$ the minimiser over $r\in(1,2)$ is $r=\varphi$ (grid $2\times10^4$: $1.61805$, $\sigma(\varphi)=0$ exactly) and the maximiser is $r=1$ ($\sigma=9.1884\times10^{-2}$) | no | degenerate: every member minimises $\sigma$ on its own ray, so the principle restates the attractor condition and the value comes from the supplied state |
| 4$(\ast)$ | self-similarity of the projection (fixed point of coarse-graining) | the map $r\mapsto$ ratio of the projected law, on the general four-population member $C=[[-a,0,b,0],[0,-a,0,b],[a,0,-b,0],[0,a,0,-b]]$ | yes | the projection returns $\partial_tE_Y=-aE_Y+bE_I$, $\partial_tE_I=+aE_Y-bE_I$ for every $(a,b)$: symbolic, and numerically with residual $0$ at $(a,b)=(1,1),(1,\varphi),(1,2),(0.4,1.7)$ | no | the map is the identity, so every ratio is a fixed point: the condition excludes nothing |
| 5$(\ast)$ | scale covariance under $R\to\lambda R$ | $\Omega=v/R$, $d=D_\ell/R^2$ (LB4) `:302-306` | yes | $\Omega\to\Omega/\lambda$, $d\to d/\lambda^2$, $r$ and $\kappa$ fixed; the scale-invariant data are the rate ratios $r/\kappa$, $r/d$, $d/\kappa$ and $\Omega^2/d$ | no | invariance constrains the form $r=F(r/\kappa,r/d,\Omega^2/d)$; it supplies no extremum and therefore no number |
| 6$(\ast)$ | variational principle on the loop's accumulated phase | $E=\frac12\oint(\mu_Yk_Y^2+\mu_Ik_I^2)\,d\chi$, $k_a=\lvert\partial_\chi\theta_a\rvert$; `principles/de-resonance-principle.md:153-175` | yes | fixed circulation budget: $k_Y/k_I=\mu_I/\mu_Y$, so $\alpha=k_I/k_Y=\mu_Y/\mu_I$; fixed windings $w_a$: $\alpha=w_I/w_Y$, rational; minimal windings: $\alpha=1$ | no | returns the supplied mobility (stiffness) ratio, a ratio of integers, or $1$ |
| 7$(\ast)$ | information or complexity functional on the mode spectrum | any function of (LB36)–(LB39) `:790-850`, e.g. spectral entropy or participation ratio of the $m=0$ decay rates $\{2r,\ \kappa(1+r),\ 2r+\kappa(1+r)\}$ | yes | at fixed $(r,\kappa)$ both are monotone in the ratio: participation ratio $2.66665\to2.09071$ and entropy $1.03972\to0.78560$ over $r=0.01\to20$; the only interior structure is the matched-rate point $\kappa(1+r)=2r$, i.e. $r=2r/\kappa-1$ | no | monotone at fixed loop data; the matched-rate extremum is a relation among supplied rates |
| 8$(\ast)$ | self-similarity (invariance) on the rate pair | $(a+b)/b=b/a$ | yes | $r=1+1/r$: $r=(1+\sqrt5)/2=1.6180339887498948482$ | **yes** | the requirement is an axiom whose content is the golden equation; D3 catches it, D1 and D2 do not |
| 9 | exactness of the projection (closure correction) | $\operatorname{Cov}_\chi(\kappa(\chi),Z)=0$, (LB14) `:453-472`, with the microscopic gate $\kappa(\chi)=\lambda[1-q(f_Y(\chi),f_I(\chi))]$ and $Z=f_Y-\varphi f_I$ | no (the chart in $Z$ carries $\varphi$) | with $f_Y=r_mf_I$: $\operatorname{Cov}(\kappa,Z)=(r_m-\varphi)\operatorname{Cov}(\kappa,f_I)$; the measured ratio $\operatorname{Cov}(\kappa,Z)/\operatorname{Cov}(\kappa,f_I)$ is $-0.618034,-0.318034,0.000000,+0.181966,+0.381966$ at $r_m=1,1.3,\varphi,1.8,2$ | **yes** | $\varphi$ is in the definition of $Z$, so this is the audit's "the registered law selects the member" (`:170-176`) restated in the closure term |
| 10 | avoidance of the loop's own exceptional points | the dimensionless transport ratio $\Omega/r$; the block (LB33)–(LB34) `:758-776` is defective at $\Omega/r=1/m$ | yes | over the window $[1/(M+1),1/M]$ the maximiser of the distance to both endpoints is the rational midpoint $(2M+1)/(2M(M+1))$: $3/4,5/12,7/24,9/40$ for $M=1,2,3,4$ (grid $2\times10^5$, agreement to $10^{-6}$) | no | rational values set by the chosen window; the opposite extremum (maximal resonance) returns exactly $1/m$ |
| 11$(\ast)$ | fixed point on the counterflow current | $\alpha=(\mu_Y/\mu_I)(E_Y/E_I)-J_0/(\mu_IE_Ik_Y)$ with the requirement $\alpha=r$; `principles/de-resonance-principle.md:171-180` | yes | declared closure (equal mobilities, zero net current): the map is the identity, every ratio is fixed; nonzero through-current: $\alpha=r$ requires $J_0=0$; mobility $\mu_Y/\mu_I=r^{p}$: $\alpha=r^{p+1}=r$ requires $r=1$ | no | identity, a current condition, or $r=1$; the compact loop additionally forces $\alpha$ rational (`:192-206`), the opposite of the de-resonance extremum |
| 12 | fivefold orbit chord ratio | $L_{\rm step\,2}/L_{\rm step\,1}$ of the regular pentagon in the normalized metric, (LB49)–(LB50) `:991-1012` | yes | $2\sin(2\pi/5)/2\sin(\pi/5)=2\cos(\pi/5)=(1+\sqrt5)/2$ exactly; among regular $n$-gons $2\cos(\pi/n)=\varphi$ only at $n=5$ | **yes** | it fixes a geometric chord ratio, not $b/a$; the value enters through the integer $5$, and the fivefold selector is supplied (`:1013-1023`) |
| 13 | extremum of the gate over the composition | $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$ at fixed $\rho$; `foundations/cassi-first-principles.md:229-231` | no | $\partial q/\partial\varepsilon=0$ only at $\varepsilon=0$ (a maximum); $q$ is monotone decreasing in $\lvert\varepsilon\rvert$, so the extremum sits at an endpoint of the admissible interval $[-\varphi\rho,\rho]$ | no | no interior extremum at all, and the gate's definition carries $\varphi$ at its own slot |

### 2.2 Two facts that close four families at once

**Spectral blindness.** The conversion block has rank one and zero column sums, so
$\operatorname{tr}M=-(a+b)$ and $\operatorname{tr}M^k=(-1)^k(a+b)^k$. Verified at fixed
trace $a+b=1$: the spectrum is $\{0,-1\}$, $\operatorname{tr}M^2=1$ and
$\operatorname{tr}M^3=-1$ for $r=1,1.5,\varphi,2,3$ alike. The ratio lives in the null
vector $(b,a)$ and nowhere else in the operator. Any functional of the spectrum, of the
characteristic polynomial $\det(M-z)=z(a+b+z)$, or of the relaxation rate is a function of
$a+b$. Entry functionals such as $\lVert M\rVert_F^2=2(a^2+b^2)$ and the spectral norm
$\sqrt2\sqrt{a^2+b^2}$ do see the pair, and their extremum under the constraint the
declared block already fixes, $a+b=\kappa(1+\varphi)$, is at $r=1$ (minimum) or on the
boundary (maximum); the alignment of the fixed ray with the symmetric ray,
$\cos\angle\big((b,a),(1,1)\big)=\sqrt2(a+b)/\big(2\sqrt{a^2+b^2}\big)$, is likewise maximal
at $r=1$. Candidates 1 and 7 can therefore fix the ratio only through the eigenvector, at
which point the functional is a function of the ratio itself and its extremum is wherever
it was defined to be.

**Exchange symmetry.** The loop's exchange, transport, and conservation terms are invariant
under the Yang/Yin swap $(a,b;E_Y,E_I)\mapsto(b,a;E_I,E_Y)$, so a functional built from
them is a function $G(t)$ of the symmetric ratio variable $t=r+1/r$ alone. Its constrained
critical points are $r=1$, where $dt/dr=0$ automatically, together with the roots of
$G'(t)=0$; at $r=\varphi$, $t=2\varphi-1=\sqrt5$, so a critical point at the golden ratio
is exactly a stationarity of $G$ at $t=\sqrt5$, the golden relation written in the
symmetric variable. In the families computed here the interior extremum sits at $r=1$
without exception: $a^2+b^2$, the rate entropy $-(a\ln a+b\ln b)$, $ab$, $1/(ab)$ and
$\sqrt{a^2+b^2}$ under $a+b=\tau$ all extremise at $a=b$, and a monomial
$a^{p}b^{q}$ (symmetric only when $p=q$) extremises at the rational ratio $r=q/p$.

## 3. The strongest candidate in full: self-similarity on the rate pair

### 3.1 The statement

Require that the loop's conversion pair be self-similar in the sense of a golden section:
the total rate is to the larger rate as the larger rate is to the smaller,

$$
\frac{a+b}{b}=\frac{b}{a}.
$$

The requirement contains no $\varphi$; the inputs are the pair $(a,b)$, which is
$\varphi$-free data of (LB6).

### 3.2 Route 1: invariance

With $r=b/a$,

$$
\frac{a+b}{b}=1+\frac1r=r\quad\Longleftrightarrow\quad r^2=r+1
\quad\Longleftrightarrow\quad r=\frac{1+\sqrt5}{2},
$$

the negative root being excluded by $a,b>0$. This is the same equation the de-resonance
paper solves for the continued fraction $[1;1,1,\dots]$
(`principles/de-resonance-principle.md:52-60`), and the same one the audit quotes as the
unique $\varphi$-free characterisation of the value (`foundations/phi-input-or-selection.md:194-200`).

### 3.3 Routes 2 and 3: two independent confirmations

**Deduction map.** The cut-and-rescale operation on a partition leaves the ratio invariant
only if the ratio is a fixed point of $f(x)=1+1/x$. Iteration from $1.0$, $1.5$, $2.0$,
$5.0$, $0.7$, $100.0$ converges to $1.6180339887498948482$ to twenty digits from every
start, alternating about the limit.

**Continued fraction.** The convergents of $[1;1,1,\dots]$ are Fibonacci ratios; the
neighbouring pair $89/55$ and $144/89$ brackets the limit at $1.6181818181818181818$ and
$1.6179775280898876404$, and the sequence continues $1597/987=1.6180344478$.

An arc-partition reading of the same condition, $(A+B)/A=A/B$ with $A+B=W$, returns
$A=\tfrac12(\sqrt5-1)W$ and $B=\tfrac12(3-\sqrt5)W$, the golden section of the loop's own
circumference. This is the geometry that the loop theorem's fivefold orbit also carries in
normalized coordinates (LB50), `:1010-1012`.

### 3.4 What it establishes, and what would falsify it

It establishes that a $\varphi$-free *form of words* whose solution is exactly
$b/a=\varphi$ exists and can be written on the loop's own rate pair. It does not derive
$\varphi$, because the requirement is a new axiom, and its content is the conclusion: D1
and D2 are met, D3 is not. Nothing in (LB6), in the internal spectrum (LB36)–(LB39), in
the conservation law (LB11), or in the current sector (LB40)–(LB45) singles out the
self-similar pair from the continuum of admissible pairs. The audit's own statement of the
same fact is that the family always has an attracting ratio and the value is the member's
own ratio (`foundations/phi-input-or-selection.md:157-162`).

The claim "the loop's conversion rates satisfy the golden-section self-similarity" is
falsifiable in the ordinary way: measure $b/a$ at a loop where the coarse rates are
independently accessible and find a value other than $\varphi$. What would falsify the
*analysis* here is a demonstration that the golden equation follows from the loop law's
own structure: a derivation from (LB6)'s column-sum condition, its conservation, or its
transport block that forces $r=1+1/r$. The structural facts of §2.2 are the evidence
against such a derivation: the column-sum and rank conditions are ratio-blind, so any such
derivation would have to use the direction-exchange and transport coefficients, and those
enter the ratio only through entries the audit's family leaves free.

### 3.5 The same family returns other constants

One self-reference, six choices of relation, all with $\varphi$-free definitions:

| Self-reference | Positive solution |
|---|---|
| $x=1+1/x$ | $1.6180339887498948482$ ($\varphi$) |
| $x=1/(1+x)$ | $0.6180339887498948482$ ($\varphi-1$) |
| $x=\sqrt{1+x}$ | $1.6180339887498948482$ ($\varphi$) |
| $x^3=x+1$ | $1.3247179572447460260$ (plastic number) |
| $x=\sqrt{1-x^2}$ | $0.7071067811865475244$ ($1/\sqrt2$) |
| $x=1/(2-x)$ | $1.0000000000000000000$ |

The value is a function of which self-reference is postulated, and the loop's own data
prefers none of them. This is the content of D3.

## 4. The two candidates that come closest

### 4.1 The de-resonance statistic

Definition and inputs are $\varphi$-free (`principles/de-resonance-principle.md:68-81`): the
approximation constant $c(r)=\liminf_q q\lVert qr\rVert$ obeys $c(r)\leq1/\sqrt5$ for every
irrational, with equality exactly on the golden class, so the worst-approximability measure
is maximal and its reciprocal $L(r)$ is minimal on that class. Computed from convergent
denominators: $c(\varphi)=c(1/\varphi)=c(\varphi^2)=0.4472135954999579$; $c(\sqrt2)=0.353553390593274$;
$c(\sqrt3)=0.288675134594813$; $c$ of every rational is $0$. Within $(1,2)$ the golden class
is the single point $\varphi$, so the extremum is $\varphi$ alone. Two independent routes
agree: the analytic Hurwitz/Lagrange statement quoted in the paper, and the numerical
convergent products, which march to $1/\sqrt5$ along $q=F_n$ ($0.447213835873$ at $q=610$,
$0.447213503686$ at $q=987$).

Three properties block its use as a selection principle for $b/a$.

1. **It is a functional of the value, not of the loop.** Nothing in (LB6), (LB36)–(LB39),
   (LB40)–(LB45), or the projection theorem contains $c$ or $L$. The loop's dynamics is
   invariant under changes of $b/a$, so the statement "$b/a$ minimises the Lagrange
   number" is an independent postulate about the ratio.
2. **The minimiser exists only if $\varphi$ is admissible.** The minimum of $L$ over a
   $\varphi$-free set $S$ is $\varphi$ exactly when $S$ contains a golden-class point. Since
   the loop family constrains nothing, $S$ is all of $(0,\infty)$ and the outcome is
   $\varphi$; restrict $S$ in any way that excludes $\varphi$ and the extremum moves with
   $S$. The principle's outcome is decided by the admissible set, and the loop supplies no
   admissible set beyond "all positive rates."
3. **The loop's own topology admits the opposite set.** Uniform single-valued phases on a
   common loop require $\alpha=q_w/p$ rational
   (`principles/de-resonance-principle.md:192-206`), and every rational has $c=0$, the
   infimum of the statistic. On the compact loop's own admissible set the statistic is
   constant at its worst value, so it cannot discriminate; the framework's own tested
   passive candidate for the resonance-suppression route returned
   $\mathrm{REJECT}\ M_0$ (`:292-302`), and `foundations/wake-geometry.md:140-144` records
   that the live source path supplies no selector for the drive frequency that would
   produce the ratio.

The extremum is also attained on a measure-zero set. Quadratic irrationals within
$10^{-3}$ of $\varphi$ do not inherit the property: $c\big((1+\sqrt{5+10^{-3}})/2\big)=0.103855$
and $c\big((1+\sqrt{5+10^{-6}})/2\big)=0.050912$, both far below $1/\sqrt5=0.447214$, even
though their continued fractions agree with $[1;1,1,\dots]$ for ten terms. A physical
mechanism would have to deliver the exact arithmetic condition rather than approach it.

What would falsify a *successful* version of this route: an equation of the canonical
system whose right-hand side is the minimisation of $c$ over a ratio built from loop
variables. The claim above stands or falls with the absence of such an equation.

### 4.2 Exactness of the projection

The closure correction (LB14), `foundations/loop-to-bubble-projection-theorem.md:453-472`,
is $\operatorname{Cov}_\chi(\kappa,Z)$ with $Z=f_Y-\varphi f_I$. With a microscopic gate
$\kappa(\chi)=\lambda[1-q(f_Y(\chi),f_I(\chi))]$ and $f_Y=r_mf_I$, the exact factorisation

$$
\operatorname{Cov}_\chi(\kappa,Z)=(r_m-\varphi)\,\operatorname{Cov}_\chi(\kappa,f_I)
$$

puts the condition at $r_m=\varphi$ whenever the gate and the population shape are
correlated. Measured on a $2^9$-point loop with $f_I=1+0.3\cos\chi$, the ratio
$\operatorname{Cov}(\kappa,Z)/\operatorname{Cov}(\kappa,f_I)$ is $-0.618034$,
$-0.318034$, $0.000000$, $+0.181966$, $+0.381966$ at $r_m=1,1.3,\varphi,1.8,2$, numerically
$r_m-\varphi$ in each case. The $\chi$-uniform gate of Theorem 1's assumption 4 gives
$\operatorname{Cov}=0$ for every $r_m$, so the condition is not a selector there either.

$\varphi$ enters through the chart in $Z$, so D1 fails. The structure is worth recording
because it locates the audit's mechanism precisely: what forces the member is not
stationarity, rank, or conservation, but the $\varphi$ already written into the coordinate
in which the correction is expressed.

The factorisation above and the measured ratios are two independent routes to the same
identity. The falsifier for the selection claim is a loop configuration with
$\operatorname{Cov}_\chi(\kappa,f_I)\neq0$ in which the closure condition vanishes at a
ratio other than $\varphi$; the factorisation excludes it, and the only escape is the
degenerate case of a gate uncorrelated with the population shape, where the condition
vanishes at every ratio and selects nothing.

## 5. Firing controls

### 5.1 A definition that carries $\varphi$

The declared attractive penalty $V_{\text{attr}}=\frac{\lambda}{2}(E_Y-\varphi E_I)^2$
(`foundations/cassi-first-principles.md:120-124`) minimises on $\rho=1$ at
$p=0.618033988749893$, i.e. $E_Y/E_I=1.61803398874989$. The discriminator rejects it at
D1: the definition contains $\varphi$, so the computed extremum is a re-expression
(`foundations/phi-input-or-selection.md:132-135`).

### 5.2 A $\varphi$-power read off the declared block

The trace of the declared conversion block is $-\kappa(1+\varphi)$
(`foundations/cassi-first-principles.md:208`), the lifetime factor the
$\varphi$-ray receipt measures to eight digits
(`foundations/phi-input-or-selection.md:100`, `:178-181`). Any functional returning it
inherits $\varphi$ from the entries and is rejected at D1, exactly as the audit's §2 row 1
records.

### 5.3 The control that fires on the discriminator

Candidate 8 (§3) is $\varphi$-free in definition and inputs, returns $\varphi$ exactly, and
derives nothing. The discriminator as stated accepts it. A test that accepts a relabeled
axiom does not separate derivation from insertion, which is why D3 is needed. Candidate 12
is the same finding in geometric clothing: the pentagon's chord ratio is $\varphi$ with no
$\varphi$ anywhere, and the input that carries the value is the divisor $5$, so satisfying
the letter relocates the unforced input rather than removing it (§7 shows the divisor $5$ to
be a coordinate face of the same input, not a smaller one).

## 6. What the search establishes

**Established.** Four structural results hold for every member of the loop family and close
whole candidate classes: the conversion operator's spectrum and all of its power traces
depend on $a+b$ alone, so spectral and Rayleigh-type functionals see the ratio only through
the fixed ray; every functional symmetric under the Yang/Yin exchange has a critical point
at $r=1$ and asymmetric monomials extremise at rational ratios $q/p$; the counterflow
sector (LB40)–(LB45) is exactly invariant under changes of the conversion ratio, because
conversion cancels in $F$ and $H$; and the projection acts as the identity on the ratio, so
fixed-point conditions on it exclude nothing. The invariance family returns forms and
relations among supplied rates, the phase-action family returns the mobility ratio or a
rational winding ratio, and the entropy-production family is degenerate.

**Not established.** No candidate fixes $b/a=\varphi$. Four candidates return $\varphi$
exactly, and each does so through an object the loop law does not supply: the de-resonance
statistic (D1 and D2 met, and the statistic is a functional of the value rather than of the
loop's fields or rates); the golden-section self-similarity (D1 and D2 met, D3 failed);
the closure-exactness condition (selects $\varphi$, with $\varphi$ written into the chart
it is expressed in, so D1 fails); and the pentagon chord ratio (D1 and D2 met by an input
that is the integer $5$, with the fivefold selector supplied at
`foundations/loop-to-bubble-projection-theorem.md:1013-1023`).

**What is still missing, stated more narrowly than the audit could.** The missing object is
a functional on the loop's own data whose stationarity equation *is* $r^2=r+1$. The search
shows the loop's own data cannot supply that equation in any of the three ways the
repository has available: not through the transport block, whose only distinguished ratios
are the rational exceptional points $\Omega/r=1/m$; not through the conversion operator,
whose spectrum is ratio-blind and whose null vector carries the ratio the functional was
supposed to produce; and not through the current closure, which transfers the density ratio
to the phase ratio and returns it unchanged under the declared equal-mobility condition.
The three routes to the number that do exist each import something: the arithmetic
extremality of the Hurwitz/Lagrange constant imports the requirement that the ratio be
worst-approximable; the pentagon imports the integer $5$, with the fivefold selector
supplied and shown in §7 to be the same unforced input as the ratio rather than a smaller
one (`foundations/loop-to-bubble-projection-theorem.md:1013-1023`);
the golden-section self-similarity imports the golden equation. A physical statement whose
solution is the worst-approximable separation remains Hypothesized
(`principles/de-resonance-principle.md:3`, tier row `EPISTEMIC-MAP.md:306`), and the
wake-geometry route still states that the live source path supplies no selector
(`foundations/wake-geometry.md:140-144`, `:229`).

**What would change the verdict.** A demonstration that one of the loop's own objects is
self-referential with the golden root, for instance that the equal-mobility, zero-net-current
closure combined with compact winding forces $\alpha=1+1/\alpha$, or that the
direction-exchange rate and the conversion rate are locked to each other by the
positivity-preserving generator at $r=1+1/r$. Both were looked for here and neither
follows: the first returns the identity map or $r=1$, the second has no equation at all in
the loop law.

## 7. The fivefold selector's source, and why the integer is $5$

Section 6 leaves one question open: candidate 12 returns $\varphi$ through the integer $5$,
and the selector that supplies the $5$ was recorded as unexplained. This section traces it
and tests whether any object the loop actually offers forces $n=5$.

### 7.1 What the loop supplies, and what it does not

The orbit is declared, not selected. (LB48) fixes $\delta_j=\delta_0+2\pi j/5$
(`foundations/loop-to-bubble-projection-theorem.md:977-986`); §8's closing paragraph states
that "the fivefold selector remains the supplied conditional $w=5$ subgroup" and that
"selection of $w=5$ requires separate dynamics" (`:1018-1023`); the list of mathematics the
loop supplies includes "integer loop Fourier sectors" (`:1039`), that is all $m\in\mathbb Z$
with $m=\pm5$ undistinguished, and "periodic scalar amplitudes give integer winding"
(`:1064`), with no preferred integer. Section 4.4 of the projective map states the same from
the other side: a potential proportional to $1-\cos5(\delta-\delta_0)$ "would impose that
selector rather than derive it", and "the canonical real-density PDE supplies none of these
ingredients" (`foundations/string-bubble-projective-map.md:412-429`). The measured negative
agrees: the two-pole PDE shows $m=2$ angular dominance and no detectable $m=5$ mode
(`foundations/spin-fibonacci-spiral.md:141-145`, `:417-419`), so the loop's own dynamics
does not put a five anywhere.

Upstream, the selector is the conditional construction of `foundations/wu-xing-derivation.md`
§§2–4, which the tier row records as derived conditional on the coherence postulate
(`EPISTEMIC-MAP.md:298`), and which reaches the projective map as one of its four declared
inputs (`foundations/string-bubble-projective-map.md:44-46`). The trace therefore runs
loop orbit $\leftarrow$ projective map $\leftarrow$ Wu Xing construction $\leftarrow$ two
stipulated filters. Whether either filter forces $5$ is the question.

### 7.2 The two routes the repository states

**Route A, the coherence criterion.** Define $E(w)=\lVert w\varphi\rVert$ and require
$E(w)\leq\varphi^{-w}$, the stipulated rule that the phase slip at a $w$-step closure not
exceed the cascade attenuation at the assigned step
(`foundations/wu-xing-derivation.md:74-78`). For $w=F_k$ the criterion is
$\varphi^{-k}\leq\varphi^{-F_k}$, equivalent to $k\geq F_k$; the levels satisfying it are
$k\in\{1,2,3,4,5\}$, with equality at $k=5$ ($F_5=5$) and failure from $k=6$
($F_6=8$). Evaluated directly for $w\leq2000$ the passing set is $\{1,2,3,5\}$, the
documented result (`:99`, `:107-109`). The boundary value is therefore the largest fixed
point of the Fibonacci map $k\mapsto F_k$: the integer $5$ is selected because $F_5=5$, and
$F_k>k$ from $k=6$ on. Both sides of the criterion carry $\varphi$, so D1 fails in the form
used; the $\varphi$-free face is the Fibonacci fixed point, whose link to the cycle count is
the criterion itself.

**Route B, the polygon chord ratio.** $2\cos(\pi/n)$ is $\varphi$ only at $n=5$: symbolically
$2\cos(\pi/5)-(1+\sqrt5)/2$ reduces to $0$, and by strict monotonicity of $\cos$ on
$(0,\pi/3]$ the function $n\mapsto2\cos(\pi/n)$ is strictly decreasing for $n\geq3$, so a
solution is unique; the numeric sweep to $n=2000$ returns exactly $\{5\}$. The same sweep on
the radius-to-side functional $1/(2\sin(\pi/n))$ returns exactly $\{10\}$, which is the
decagon entry of the document's own table (`foundations/wu-xing-derivation.md:127-128`): the
pentagon is the first and only regular polygon whose *vertex-chord* ratio is $\varphi$, while
the decagon reproduces $\varphi$ as a radius-to-side ratio. Both routes reconcile at
$w=5$ in the document's intersection (`:134-139`).

### 7.3 The origins the loop offers, each tested

| Candidate origin | Test | Result |
|---|---|---|
| population count and fibre incidence | enumerate the integers the loop construction declares: 4 populations, 2 species, 2 orientations, 1 closed loop, 4 uniform modes, 4 real coherence parameters (`foundations/string-bubble-projective-map.md:56-110`), Bloch-ball dimension 3, projective sphere dimension 2, loop coordinate 1 | the integers present are $1,2,3,4$; $5$ does not appear |
| dimension of the null space | $m=0$ spectrum $\{0,\,-2r,\,-\kappa(1+\varphi),\,-2r-\kappa(1+\varphi)\}$ (LB37), 4-dimensional block | nullity $1$ for $r,\kappa>0$, $2$ when either vanishes, $4$ when both do; $5$ is excluded by the dimension of the space |
| minimal winding compatible with positivity | single-valued amplitudes admit every integer winding and positivity of $f_a=\lvert\psi_a\rvert^2$ constrains none; the counterflow closure gives $\alpha=q_{\mathrm w}/p=r$ | $\alpha=q_{\mathrm w}/p=r$ verified symbolically; the winding $5$ appears only at a tolerance-indexed record level (table below) |
| normalization of the loop's own metric | normalized fivefold chord ratio computed for the declared $D=\operatorname{diag}(3,2,5/4)$, an isotropic $D$, a rescaled declared $D$, and a random positive diagonal $D$ | $1.618033988750$ in all four cases: the identities are invariant, and the axes are a free two-parameter shape (`foundations/loop-to-bubble-projection-theorem.md:547-549`), so no normalization selects $5$ |
| minimal polynomial of the de-resonance statistic | the statistic's extremum is at $\varphi$ with value $1/\sqrt5$ (§4.1); $\operatorname{disc}(x^2-x-1)=5$ and $\sqrt5=2\varphi-1$, hence $5=(2\varphi-1)^2$ | $5$ is a function of $\varphi$ in this route, not an independent input; the cyclotomic counterpart, $Q(\zeta_5)^+=Q(\sqrt5)$ with $2\cos(2\pi/5)=1/\varphi$, likewise ties $n=5$ to $\varphi$, and $\varphi(n)=4$ is realized at $n=5,8,10,12$ with real quadratic fields $\sqrt5,\sqrt2,\sqrt5,\sqrt3$, so the degree-4 circle does not single out $5$ either |

**The winding candidate's tolerance.** The counterflow closure of
`principles/de-resonance-principle.md:171-180` gives $\alpha=k_I/k_Y=r$ exactly for equal
mobilities and zero net current; uniform single-valued phases then require
$\alpha=q_{\mathrm w}/p$ rational (`:192-199`), so the irrational target has no exact
finite-winding closure and the record pairs are $(p,q_{\mathrm w})=(F_n,F_{n+1})$ with
$F_{n+1}-\varphi F_n=(-1)^n\varphi^{-n}$ (`:201-206`; verified to six digits at $n=1\ldots7$).
Admitting the level whose error falls below a tolerance $\varepsilon$ gives

| $\varepsilon$ | admitted level | record pair | largest winding |
|---|---|---|---|
| $\varphi^{-3}=0.236068$ | 3 | $(2,3)$ | 3 |
| $\varphi^{-4}=0.145898$ | 4 | $(3,5)$ | 5 |
| $\varphi^{-5}=0.090170$ | 5 | $(5,8)$ | 8 |
| $\varphi^{-6}=0.055728$ | 6 | $(8,13)$ | 13 |

so the integer $5$ is the largest winding exactly in the tolerance window
$\varepsilon\in[\varphi^{-5},\varphi^{-4})$, and the window is free. This is one level of
the same ladder the criterion of route A walks, with the difference that route A's ladder
terminates because its threshold carries the same exponent as its error.

### 7.4 The threshold exponent is the input

Route A's criterion compares the error $\varphi^{-k}$ at level $k$ with the attenuation
$\varphi^{-w}=\varphi^{-F_k}$ at the assigned step, that is with exponent coefficient
$\lambda=1$ under the convention that one cycle vertex advances one cascade step. Relaxing
or sharpening that convention to $\varphi^{-\lambda w}$ moves the selected cycle:

| $\lambda$ | passing Fibonacci levels | largest passing cycle |
|---|---|---|
| $1/2$ | $1,\ldots,7$ | $F_7=13$ |
| $3/4$ | $1,\ldots,6$ | $F_6=8$ |
| $1$ | $1,\ldots,5$ | $F_5=5$ |
| $5/4$ | $2,3,4$ | $F_4=3$ |
| $3/2$ | $2,3$ | $F_3=2$ |
| $2$ | $2$ | $F_2=1$ |

Only the declared one-vertex-per-step convention returns $5$. The selection is therefore a
property of the comparison, not of the loop.

**Prior art, with one correction.** `computations/pinch_point_modes.py:200-241` ran the same
question and reached the same conditional verdict through a two-filter construction
(elliptical cavity modes; the Fibonacci hierarchy as an upper bound; the pentagon as a lower
bound). Its Candidate 2 sentence, that the first five Fibonacci ratios approximate $\varphi$
within $5\%$, is not reproducible under a fixed relative tolerance: at $5\%$ every level
$k\geq4$ passes ($27$ of $30$ levels tested), and at $1\%$ every level $k\geq6$, so the set is
cofinite and no finite count can be read from a tolerance alone. Candidate 3, the pentagon,
stands as computed in §7.2.

### 7.5 The verdict

**Supplied, and jointly with $\varphi$.** None of the five candidate origins forces $n=5$
independently of a $\varphi$-carrying input, and the two routes the repository states are two
faces of one field: $2\cos(\pi/5)=\varphi$, $\operatorname{disc}(x^2-x-1)=5$, $\sqrt5=2\varphi-1$
and $Q(\zeta_5)^+=Q(\sqrt5)$ are the same fact seen in geometry, in the polynomial, and in
the cyclotomic real subfield. The polynomial enters the route through the de-resonance
statistic's extremum, whose value is $1/\sqrt5$.

**So why-five is not a smaller question than why-$\varphi$.** It is the same input in another
coordinate, and the count of independent inputs does not fall: one unforced constant, the
golden ratio, which appears as the ratio $b/a$ if the question is asked of the conversion
block and as the integer $5$ if the question is asked of the cycle's vertex geometry. The
smallest gap does not move down a level. It remains the single input, in whichever
coordinate it is asked. Route B is the strongest candidate of the five (an implication in
both directions, with a $\varphi$-free definition of the quantity $2\cos(\pi/n)$, so D1
passes), and it fails D2: the route's input is the requirement that the cycle's vertex
geometry encode the golden ratio, whose content is exhibited by the substitution
$x:=2\cos(\pi/5)$, $x^2=x+1$; the premise's content is the golden equation in geometric
coordinates, so D3 fails with it.

**This narrows the audit rather than extending it.** The four canonical $\varphi$ slots and
the missing selection principle are recorded at `foundations/phi-input-or-selection.md`;
the fivefold integer adds no fifth slot. It is a second coordinate for the one input that
audit leaves open: the same $b/a$, read off the cycle's vertex geometry instead of the
conversion block. The count of independent inputs does not change, and the gap does not move
down a level.

**What would falsify this.** An object of the loop's own data equal to $5$ or to $\sqrt5$
without a $\varphi$-carrying input: a quantity of dimension five (excluded above by the
four-dimensional population space and the enumerated counts), a normalization fixing one
axis to $5$ (excluded by the invariance of every fivefold identity under positive diagonal
rescaling), an incidence integer of five, or a $\varphi$-free characterization of the
integer whose derivation exhibits no substitution chain into the golden equation. The five
tests above look for those and find none.

## 8. Cross-check: does any document claim that a rate or a spectrum fixes the ratio?

Spectral blindness (§2.2) says a functional of the conversion block sees $a+b$ and never
$b/a$: the ratio lives in the null vector. Any document sentence that draws the ratio, or a
constraint on it, from a rate, a spectrum, or a mode-decay measurement is therefore
over-strong on its own. The theory documents were searched for such sentences with patterns
combining rate, spectrum, eigenvalue, mode, decay and gap with determin, select, fix, pin,
constrain, establish, evidence, confirm and measure, and with the ratio vocabulary
(ratio, composition, ray, $\varphi$). Nine sites bear on the question.

| Site | What it states | Class |
|---|---|---|
| `open-questions-cassi-answers.md:198` | four declared compositions end within $5.7\times10^{-4}$ of $\varphi$, "and all four volume-mean imbalance-decay rates equal $0.2618034$ against $(1+\varphi)\lambda=0.2618034$" | claim of the class in its rate clause: the equality is the declared block's trace, $\kappa(1+r_m)$ for a member, so it witnesses the declared sum; the state reading in the same sentence is the independent half |
| `parameter-inventory.md:699` ($\Gamma_0$ row) | the "Measured" clause: ungated volume-mean rate $0.2618034$ against $\varphi^2\lambda$, gated $0.0296$ to $0.0298$ against $\Gamma_0=\lambda/3$ | claim of the class; the row's own tier text ("not an independent parameter") is the sharp half |
| `computations/two-fluid-phi-ray-relaxation-prereg.md:46` | registered falsifier: "a measured imbalance-decay rate away from $(1+\varphi)\gamma_{\mathrm{conv}}$ ... is evidence against the structure" | claim of the class in falsifier form; the exact counterpart already exists at `foundations/phi-input-or-selection.md:177-181` |
| `field-experience/probe-outcome-ledger.md:2437` | terminal rates $0.02976$ and $0.02960$ against $\Gamma_0=\lambda/3=0.033333$, with the weighted form $(1+\varphi)\lambda\Xi=0.029463$ at measured $\Xi=0.11254$ | claim of the class; the pointwise/volume-mean separation is the careful part, the origin of the $(1+\varphi)$ factor is implicit |
| `foundations/physical-becoming-hierarchy.md:294`, `:498-500` | "the zero mode is the equilibrium ray $(E_Y,E_I)\propto(\varphi,1)$"; $\Gamma_0=(1+\varphi)\lambda(1-q_{\mathrm{eq}})=\lambda/3$ | not a claim of the class: the two facts in their correct places, the ratio in the null vector and the rate at the trace |
| `foundations/phi_attractor_synthesis.md:49-53`, `:420` | $\gamma_{\mathrm{eff}}(d)=\gamma_0\,d/(1-d)$, and at $d=\varphi^{-1}$ "the golden ratio appears naturally as the contraction enhancement factor ... This is not coincidental" | claim of the class in another sector: a phenomenological damping rate, not the loop's conversion block, so §2.2 does not apply mechanically; solving $d/(1-d)=\varphi$ returns $d=\varphi^{-1}$, a premise whose content is the golden equation, which D3 rejects as a derivation of $\varphi$ |
| `predictions/falsifiable-predictions.md:341-354` (Prediction 55) | the normalized drift and diffusivity curve $R_Q(\varepsilon)$ with $c=\lambda(1-q)$ at fixed $\rho=\varphi$ | not a claim of the class: the curve tests the gate's shape and the ratio enters as the supplied preparation |
| `computations/loop-carrier-projection-dynamics-prereg.md:261`, `:300-301` | the frozen spectrum as the instrument for when the loop modes relax: F5 compares each measured per-mode decay with (LB36) at the arm's own $\kappa$ | not a claim of the class: the spectrum is checked against itself at a supplied $\kappa$ |
| `foundations/phi-input-or-selection.md:216-221` | the registered $\Gamma_0$ prediction is where "the rate asymmetry, the gate floor and the reference composition meet and cancel" | not a claim of the class: this is the sharp form the loose sentences above lack, and the reason none of them needs a physics correction |

**Scope of the check.** The blindness result applies to any rank-one conversion block whose
two entries carry the ratio; it does not by itself bound rate asymmetries in unrelated
models, so the two sites outside that sector (the synthesis entry and the spectrum
instrument) are classified by the relabeling test of §1.2 and by instrument use, not by
blindness. No site claims that a spectrum *measurement* selects $\varphi$ outright; the
strongest statement found is the falsifier form at row three, and the repository already
carries its exact replacement in `foundations/phi-input-or-selection.md:177-181`. The four
loose sentences are listed here for the document owners to route, and none is corrected in
this file.

## References

- `foundations/phi-input-or-selection.md`—the input/output audit, its four slots, the
  discriminator, and the four-population family.
- `foundations/cassi-first-principles.md`—postulate, attractor, canonical PDE, conversion
  block, gate, reference normalization.
- `foundations/loop-to-bubble-projection-theorem.md`—(LB1)–(LB50): the loop law, its
  projection, the closure boundary, the internal spectrum, the current sector, and the
  fivefold orbit.
- `principles/de-resonance-principle.md`—the continued-fraction extremality, the projective
  flow, the counterflow closure, the compact-winding boundary, and the rejected passive
  candidate.
- `foundations/wake-geometry.md`—the supplied-drive selector and its missing live source.
- `foundations/wu-xing-derivation.md`—the conditionally selected $w=5$: the coherence
  criterion, the Fibonacci reduction, the polygon chord arithmetic, and the intersection.
- `foundations/string-bubble-projective-map.md`—the $C_5$ orbit, the selector boundary, and
  the affine metric whose normalization fixes no axis.
- `foundations/spin-fibonacci-spiral.md`—the measured angular spectrum ($m=2$ dominance, no
  detectable $m=5$ mode).
- `EPISTEMIC-MAP.md`—tier rows for the de-resonance and gate entries.

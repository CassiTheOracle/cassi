# Is $\varphi$ Inserted or Selected? An Input/Output Audit of the Scale-Separation Axiom

## Status: Audit—September 2026. Classification and citations only: no new runs, no change to any canonical equation.

The axiom's own registry row already carries the classification this audit tests: class
**F**, "Fundamental axiom—the declared scale-separation input for the framework"
(`parameter-inventory.md:25`, legend `:9`, single-postulate recap `:586`, count 1). Nothing here requires a registry
edit. The audit records where the axiom enters, what has been reported as coming out of
it, and whether anything in the repository forces its value.

Citations are to the working tree at HEAD `5ca05d66`.
`field-experience/probe-outcome-ledger.md` and `parameter-inventory.md` carry concurrent
local edits, so where a line number could move the stable section or tag id is given
alongside it.

**Scope.** Part 1 covers the canonical equations and their definitions, the canonical
solver's realization of them, and the closure/mapping rows that consume $\varphi$. Part 2
covers every $\varphi$-valued result the repository reports. Part 3 applies the
discriminator. Each part states where it stops.

---

## 1. $\varphi$ as an input

Definition site: `foundations/cassi-first-principles.md:16` (boxed), carried by the
postulate at `:7` and by the class-F row `parameter-inventory.md:25`.

### 1.1 The canonical equations (exhaustive on the definitional sources)

The canonical core is stated in `foundations/cassi-first-principles.md` (the PDE and its
diagnostics) and `foundations/loop-to-bubble-projection-theorem.md` (the loop law and its
projection). Every appearance of $\varphi$ in those two statements is listed here.

| # | Site | Citation | What $\varphi$ does there |
|---|------|----------|---------------------------|
| 1 | Attractor potential $V_{\text{attr}}=\frac{\lambda}{2}(E_Y-\varphi E_I)^2$, minimizer $E_Y=\varphi E_I$ | `foundations/cassi-first-principles.md:121`; minimizer `:124` | sets the target composition |
| 2 | Canonical combinations $\rho:=E_Y+E_I$, $\varepsilon:=E_Y-\varphi E_I$ | `foundations/cassi-first-principles.md:229`; `foundations/loop-to-bubble-projection-theorem.md:259` (LB2) | chart: $\varphi$ fixes which density combination is the relaxing coordinate |
| 3 | Qi gate $q:=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$ | `foundations/cassi-first-principles.md:231`; `foundations/loop-to-bubble-projection-theorem.md:269` (LB3) | $\varphi^{-2}$ is the gate's density floor |
| 4 | Conversion rate $\kappa:=\lambda[1-q(E_Y,E_I)]$ and the openness $(1-q)$ | `foundations/loop-to-bubble-projection-theorem.md:315` (LB5); `foundations/cassi-first-principles.md:186-187` | the gate's $\varphi$ enters the conversion rate and therefore the contraction rate |
| 5 | Conversion block $\begin{bmatrix}-1&\varphi\\1&-\varphi\end{bmatrix}$, rank one, eigenvalues $0$ and $-\kappa(1+\varphi)$ | `foundations/cassi-first-principles.md:204`, `:208`; linear form `:136-137` | **rate asymmetry**: $\varphi$ is the ratio of the two exchange rates |
| 6 | Canonical PDE $\partial_tE_Y=\dots-\lambda(1-q)(E_Y-\varphi E_I)$ (and its negative for $E_I$) | `foundations/cassi-first-principles.md:171-173` | sites 2 and 5 at once |
| 7 | Four-population loop law: $-\kappa f_{Y,s}+\varphi\kappa f_{I,s}$, mirror $+\kappa f_{Y,s}-\varphi\kappa f_{I,s}$ | `foundations/loop-to-bubble-projection-theorem.md:329-330`, mirror `:337-338` (LB6 `:341`); projected form (LB10) `:402` | $\varphi$ is the ratio of the two loop conversion rates |
| 8 | Uniform fixed ray $f_{Y,\pm}=\varphi C$, $f_{I,\pm}=C$ hence $E_Y/E_I=\varphi$, $\varepsilon=0$ | `foundations/loop-to-bubble-projection-theorem.md:439` (LB12), `:448` (LB13) | *consequence* of site 7 (balance $\kappa f_Y=\varphi\kappa f_I$), not an independent input |
| 9 | Reference normalization $\rho_\star=1$, $\rho=\varphi$, $E_Y=1$, $E_I=\varphi^{-1}$, hence $q_{\text{eq}}\approx0.873$ and $1-q_{\text{eq}}=\varphi^{-2}/3$ | `foundations/cassi-first-principles.md:284-289` | fixes the reference state |
| 10 | Fixed-point imbalance $\alpha_0=\pi/\rho=\varphi^{-3}=(\varphi-1)/(\varphi+1)$ | `foundations/cassi-first-principles.md:152-156` | a $\varphi$-power assigned to a fixed-point reading |

Sites 2, 3, 5 and 9 are **four separate coefficient slots**: the chart, the gate floor,
the rate asymmetry, and the reference composition. Each could in principle carry its own
constant. This matters in §3.1 and §3.5.

### 1.2 The closures the canonical equations carry

| Closure | Citation | What $\varphi$ does there | Registry class |
|---------|----------|---------------------------|----------------|
| $\xi=\varphi^{6}=(\pi/\rho)^{-2}$; $G_{\text{eff}}/G=\varphi^{-3}(1+(\varphi^{6}-1)q)$; $G_{\text{eff}}/G=3.726779962$ at the reference state | `foundations/cassi-first-principles.md:307`, `:319-320`, `:323`; `foundations/xi-derivation.md` (tier row `EPISTEMIC-MAP.md:301`) | $\varphi^{6}$ is the coupling base, $\varphi^{-3}$ the fixed-point imbalance | Derived conditional on the inverse-square coupling input / Calibrated pin |
| $\kappa_{\text{DE}}=3\varphi^{2}H_0$ | `cassi-physics.md:1324`; `foundations/cassi-first-principles.md:717`, `:844`; `open-questions-cassi-answers.md:298` ("a named closure input, not a canonical PDE coefficient"); `parameter-inventory.md:818` | $\varphi$ enters the dark-energy rate | Calibrated (DESI anchor); $3\varphi^2=K_{md}$ is a Wu Xing coefficient |
| Vacuum source rate $\lambda\varphi^{-2}$ (with the $1/3$ explicitly *not* a $\varphi$ quantity) | `cosmology/cosmology-from-phi.md:51`, `:66-68`, `:78`, `:82`, `:84`; `foundations/cassi-theory-reference.md:451` | $\varphi^{-2}$ sets the source | rate **Asserted**; the $1/3$ Derived conditional on $d=3$ |
| Cascade ladder $\ell_n=\ell_{\text{Pl}}\varphi^{n}$ | `foundations/dimensionful-cascade.md` (tier row `EPISTEMIC-MAP.md:283`); `foundations/deriving-remaining-gaps.md:237-244` | $\varphi$ is the base of every rung | Derived conditional on the external $\ell_{\text{Pl}}$ anchor; rung labels Mapped |
| Declared composition target $r_\star\equiv E_Y/E_I=\varphi$ as solver input | `principles/de-resonance-principle.md:9-17`, status line `:3` | the target itself is declared | model postulate, by statement |
| Supplied-drive selector $\Omega_\star=\varphi^{3/2}\omega_{0,\text{wave}}$ making $k_\rho/k_\epsilon=\varphi$ | `foundations/wake-geometry.md:131`, `:229-230` | $\varphi$ enters the drive frequency | Derived conditional on supplied adjacent-rung carriers; no live selector |
| The $q$ rational form and the bare $\varphi^{-2}$ floor | tier row `EPISTEMIC-MAP.md:296` (registering `foundations/cassi-first-principles.md`) | $\varphi$ in the gate | "constitutive choices", by statement |

### 1.3 The canonical solver's realization

`two-fluid/cassi_two_fluid_3d_gpu.py` carries the same four slots as named parameters:

| Site | Citation |
|------|----------|
| $\varphi$, $\varphi^{-1}$ as constants | `:30-31` |
| chart in the conversion, $\text{conv}=-\lambda(e_Y-\varphi e_I)$ | `:188`; chart in the diagnostics $\varepsilon^2=\overline{(e_Y-\varphi e_I)^2}$ `:382` |
| reference state: default $E_I=\varphi^{-1}$ with amplitude noise | `:232`; `rho_crit` default $\varphi$ `:319` |
| gate floor as a **separate slot**: `phi_inv2=0.382` default, i.e. $\varphi^{-2}$ | `:310`, `:329`; used in $q$ `:398`, `:518`, and in $H_{\text{raw}}$ `:384` |
| $\varphi$-power couplings: `phi_pow_5ch` $=\varphi^{-k}$, $k=3..7$; `eta_5ch` $=[1,\varphi^{-1},\varphi^{-1},\varphi^{-1},\varphi^{-1}]$; `qi_tau`$=\varphi^{-1}$; `wx_Kfm`$=\lambda\varphi^2$; `wx_Kmd`$=3\varphi^2$ | `:331-333`, `:337`, `:350-351` |
| cosmology terms $H_{\text{conv}}=\frac{\lambda}{3}(\varphi-r)(1+r)/(r+\epsilon)$, $H_{\text{empty}}=\frac{\lambda}{3}\varphi^{-2}$ | `:388`, `:390`, `:410` |

### 1.4 Where section 1 stops

* Covered: the canonical equations in the two definitional sources (exhaustive on those
  statements), the canonical solver's realization, and the seven closure/mapping rows of
  §1.2.
* Not enumerated: the imperative ports that re-implement the same four slots and add no
  independent closure — CassiCosmos GLSL (`CassiCosmos/compute/cassi_voronoi_cells.glsl:290-292`
  chart and gate, `cassi_qhist.glsl:144`,`:174`, `cassi_site_shortlist.glsl:61`,
  `cassi_voronoi_optical.glsl:32`, `cassi_voronoi_optical_payload.glsl:14`), the CassiCraft
  port, and CassiAI/`vk_qi`. A value audit needs the four slots above, not their ports.
* Not enumerated here: the Standard-Model, mass-ladder and catalog $\varphi$-power
  assignments ($\alpha_{\text{GUT}}$, $\sin^2\theta_W$, $\eta=\varphi^{-44}$,
  $\Omega_{\text{DM}}/\Omega_b=\varphi^3$, the mass ladder, $\varphi$-periodic catalog
  structure). Those are outputs, and they are handled by class in §2.

---

## 2. $\varphi$ as an output

The column "$\varphi$ upstream?" answers whether $\varphi$ was inserted in the definition
or in the inputs of the quantity.

| # | Quantity that came out $\varphi$-valued | Where measured or derived | $\varphi$ upstream? | Class |
|---|------------------------------------------|---------------------------|---------------------|-------|
| 1 | The $\varphi$ ray in the canonical solver: $R_T/\varphi-1=-1.94\times10^{-4}$, $-3.88\times10^{-4}$, $-5.62\times10^{-4}$, $+1.74\times10^{-4}$ (mode A) and $r_{\text{fit}}/((1+\varphi)\lambda)=1-4.6\times10^{-8}$ | receipt `runs/two_fluid_phi_ray_relaxation/verification.json`; ledger §63 (`field-experience/probe-outcome-ledger.md:2402`, rows `:2428-2429`) | yes — chart (site 2) and rate (site 5) | consistency check of the law's form |
| 2 | The loop-carrier closure of the canonical two-density law: the four-population $\chi$-average tracks (LB7) under (LB8)–(LB14) | receipt `runs/loop_carrier_projection_dynamics/verification.json` (SHA-256 `7ff42dfd8f96ff98126c58bb2e4076f2f7d814b3cea6ab11295cd7bc48978b5b`, status FAIL); ledger §64 (`:2532`) | yes — the $\varphi\kappa$ entries (site 7) | consistency check |
| 3 | The reference contraction rate $\Gamma_0=\lambda/3$: terminal segment rates $0.02976$ and $0.02960$ against $\Gamma_0=0.033333$, reproduced by the weighted form $(1+\varphi)\lambda\Xi$ with measured $\Xi=0.11254$ | ledger §63 row (`:2437`); registered prediction `computations/two-fluid-phi-ray-relaxation-prereg.md:107`; ingredients at `foundations/cassi-first-principles.md:289` with $1+1/\varphi=\varphi$ | $\varphi$ appears in the *derivation* but cancels: $1+1/\varphi=\varphi$, $\varphi^2+\varphi^{-2}=3$ exactly | a $\varphi$-free value from $\varphi$-bearing inputs — a multi-slot consistency identity; it cannot determine $\varphi$ |
| 4 | $q_{\text{eq}}=0.872677\ldots$ and $1-q_{\text{eq}}=\varphi^{-2}/3$ | `foundations/cassi-first-principles.md:289` | yes (gate) | re-expression |
| 5 | $\alpha_0=\varphi^{-3}$; $\xi=\varphi^{6}=(\pi/\rho)^{-2}$; $G_{\text{eff}}/G=3.726779962$ | `foundations/cassi-first-principles.md:152-156`, `:307-323`; `foundations/xi-derivation.md` | yes | re-expression plus a calibrated pin |
| 6 | $\Omega_{\text{DM}}/\Omega_b=\varphi^{3}\approx4.24$; baryogenesis exponent $\eta=\varphi^{-44}$ | `cosmology/README.md:22` | exponent assigned | Mapped (observable not derived) |
| 7 | $k_\rho/k_\epsilon=\varphi$ in the phase-staggered scale-gap construction, under a supplied drive: tuned $k_\rho/k_\epsilon=1.618096626$ against generic ratio $1.311855471$ | ledger §3 row (`field-experience/probe-outcome-ledger.md:31`): verdict "**PASS closure; driven additive phase layers EMERGE CONDITIONAL; automatic $\varphi$ selection CONTRADICTS**"; `foundations/wake-geometry.md:229-230` names the missing selector | yes — the drive is supplied | **the only place the repository tested automatic selection, and the verdict is negative** |
| 8 | Counterflow phase-gradient ratio $\alpha=k_I/k_Y$ relaxing to $\varphi$ | `principles/de-resonance-principle.md:152-193` | yes — $\alpha=r$ identically under the closure, so it inherits the declared density target | conditional transfer, not a derivation |
| 9 | Cascade and catalog $\varphi$-power hits (mass ladder, $\varphi$-periodic structure, prediction rows) | `analyses/`, `predictions/`, the §10 fit-status ledger | power assigned, then reported | Mapped or Calibrated fits |

**Where section 2 stops.** Rows 1–3 are the canonical measurements; 4–6 the closures'
$\varphi$-valued outputs; 7–9 the three construction-level campaigns that put a
$\varphi$-valued ratio on the table. I did not enumerate the catalog-side mapping
documents row by row (`analyses/*`, `predictions/*`, the ~40 rows of the §10 fit-status
ledger); they are uniform in kind — a $\varphi$-power assigned to an observable and then
reported as Mapped or Calibrated — and that class statement is what the table needs.

**Reading of section 2.** Every $\varphi$-valued output found is either downstream of an
inserted slot (rows 1, 2, 4, 5, 8), a mapped or calibrated fit (6, 9), or a $\varphi$-free
value produced from $\varphi$-bearing inputs (3). No row reports a value that an existing
measurement forces to be $\varphi$ rather than to be whatever was inserted.

---

## 3. The discriminator, applied

### 3.1 The condition

**Necessary and sufficient for "the framework derives $\varphi$":** $\varphi$ appears as
the value of a quantity $Q$ whose definition contains no $\varphi$ **and** whose
derivation's inputs contain no $\varphi$.

* Definition $\varphi$-free, inputs not: a **consistency check** — the derivation can only
  confirm that one inserted slot equals another.
* Inputs $\varphi$-free, definition contains $\varphi$: a **re-expression** — the whole of
  §2 rows 4–6.

Because the canonical core carries four separate slots (§1.1), the condition is
conjunctive across slots: deriving one constant does not derive the value the other slots
carry unless the derivation also forces those slots to the same number. Absent that, the
single-constant claim is an unforced coincidence rather than an identity, and each slot
retains independent freedom.

### 3.2 The strongest candidate: the four-population loop

Does stationarity, together with the projection, the rank-one mobility, and the
conservation the loop already carries, force the fixed ratio?

**The family.** The loop law's members are conversion matrices with nonnegative
off-diagonal entries and zero column sums
(`foundations/loop-to-bubble-projection-theorem.md:427`), and "more general direction-mixing
conversion matrices project to the same canonical law when their columns sum to one;
(LB6) is the smallest explicit member needed here" (`:347`). Write the coarse
$\chi$-averaged member as
$\partial_tE_Y=-aE_Y+bE_I$, $\partial_tE_I=+aE_Y-bE_I$ with $a,b\geq0$. Conservation of
$\rho=E_Y+E_I$ (LB11, `:417`) holds identically for every $(a,b)$.

**Stationarity.** $aE_Y=bE_I$ gives the fixed ratio $r_\infty=E_Y/E_I=b/a$.

**Attraction, in two lines.** With $\varepsilon':=E_Y-(b/a)E_I$,
$\partial_t\varepsilon'=-(1+b/a)\,a\,\varepsilon'$. So **the family always admits an
attracting ratio** whenever $a>0$: existence and stability are forced by stationarity plus
conservation, and the value is $b/a$, the member's own coarse rate ratio.

**Rank-one mobility does not select it.** Rank-oneness of the conversion block produces a
fixed line and a null direction only once the entries are supplied; the null vector is
proportional to $(b,a)$. Rank one is what makes the relaxation single-mode, not what
chooses its direction — the direction is $\varphi$ because the entries $(1,\varphi)$ were
declared (site 5).

**The projection is $\varphi$-agnostic.** (LB10) (`:402`) holds for any ratio,
$\sum_s\langle-\kappa f_{Y,s}+\varphi\kappa f_{I,s}\rangle_\chi=-\kappa(E_Y-\varphi E_I)$.
Replace $\varphi$ by $\varphi'$ in the loop's rate entries (`:330`, `:338`) and the same
algebra returns the *registered canonical law with $\varphi'$*. The registered law
therefore **selects the member** — only $b/a=\varphi$ reproduces it — and the member does
not select $\varphi$.

**The measured $(1+\varphi)$ factor is the same statement again.** It is the trace
$\kappa(1+\varphi)$ of the declared block (`foundations/cassi-first-principles.md:208`); a
member with rate ratio $\varphi'$ would contract at $\kappa(1+\varphi')$. The eight-digit
rate agreement of §2 row 1 therefore confirms that two slots of the same declared block
agree, not that the block's ratio is forced.

**Verdict on the strongest candidate.** It does not derive $\varphi$. It derives that *an*
attracting ratio exists and that it equals the loop's own coarse conversion ratio. The
repository's own counterflow selection theorem is exactly this stability result for the
declared member — the projective flow $\dot r=-\kappa(1+r)(r-\varphi)$
(`principles/de-resonance-principle.md:140-147`) — and it states its own scope at `:148-150`:
"The result establishes selection by the declared conversion operator; the occurrence of
that operator in nature retains the model-postulate status". Substituting the general
member gives $\dot r=-(1+r)\,a\,(r-b/a)$, whose fixed point *is* the member's ratio $b/a$.

### 3.3 The one thing that satisfies the condition, and what it leaves open

The *value* of $\varphi$ is uniquely characterized without $\varphi$: it is the positive
representative of the worst-approximable class, $\varphi=[1;1,1,\dots]$, equivalently the
positive root of $r^2=r+1$ (`principles/de-resonance-principle.md:7-10`, establishing the
continued-fraction and Hurwitz/Lagrange facts). Condition (i) is met for the value — the
characterization contains no $\varphi$ — and the same Abstract records the caveat that the
number-theory statement characterizes the class while the positive representative is a
convention.

What is missing is the physical requirement: no $\varphi$-free physical statement in the
repository has "worst-approximable separation" as its solution. The framework's physical
realization of de-resonance is Hypothesized (`principles/de-resonance-principle.md:3`,
tier row `EPISTEMIC-MAP.md:306`), and the wake-geometry route states outright that "the
live source path supplies no selector for $\Omega_\star$"
(`foundations/wake-geometry.md:229-230`).

### 3.4 Which slots the existing receipts actually pin

The solver carries the gate floor as an independent knob (`phi_inv2`, default = the chart
constant's square: `two-fluid/cassi_two_fluid_3d_gpu.py:310`), and the $\varphi$-ray
protocol registered it as such (`computations/two-fluid-phi-ray-relaxation-prereg.md:51`
sets `phi_inv2=PHI**-2`, `:154` verifies the setting took effect), with the local quartile
ratios landing on $1.617049$–$1.618028$ inside a $10^{-3}$ tolerance (`:250`). What those
runs confirm is the **declared packet** — ray at $\varphi$, rate $\lambda(1+\varphi)$, local
ratios inside tolerance, and the registered $\Gamma_0=\lambda/3$ prediction (`:107`) where
the rate asymmetry, the gate floor and the reference composition meet and cancel — not the
two slots against each other, because no run in the repository sets the gate floor
inconsistent with the chart constant. The reference composition (site 9) and the loop's
rate ratio (site 7) are used at their canonical values by construction. No receipt varies
any slot independently of the others.

### 3.5 Verdict

* **Inserted or selected:** inserted, at four separate canonical slots, with the value
  itself characterized but not physically forced. Every measurement in §2 confirms the
  law's form or the consistency of the declared packet; none reports a quantity that had
  to come out $\varphi$.
* **Strongest candidate's outcome:** the loop route forces the *existence* of an attracting
  ratio, and forces it to equal the loop's own coarse rate ratio $b/a$; it does not force
  $b/a=\varphi$. The repository states the same scope for its own selection theorem.
* **One sentence on what would have to exist for $\varphi$ to stop being an input:** a
  $\varphi$-free selection principle — a functional, symmetry, or microscopic derivation
  on the loop's own data ($\Omega$, $d$, $r$, and the loop geometry) whose extremum or
  invariance fixes the coarse conversion rate ratio $b/a$, together with a physical
  statement whose solution is the worst-approximable separation — does not exist in the
  repository.

## References

* `foundations/cassi-first-principles.md`—postulate, canonical PDE, gate, attractor,
  reference normalization, gravity closure.
* `foundations/loop-to-bubble-projection-theorem.md`—(LB1)–(LB14), the loop law, its
  projection, the member family, the fixed ray.
* `two-fluid/cassi_two_fluid_3d_gpu.py`—canonical solver realization.
* `principles/de-resonance-principle.md`—declared target, projective flow, counterflow
  phase selection, worst-approximable characterization.
* `foundations/xi-derivation.md`, `foundations/wake-geometry.md`,
  `foundations/dimensionful-cascade.md`, `cosmology/cosmology-from-phi.md`,
  `cassi-physics.md`, `EPISTEMIC-MAP.md`, `parameter-inventory.md`—closures and tiers.
* `computations/two-fluid-phi-ray-relaxation-prereg.md`,
  `field-experience/probe-outcome-ledger.md` §§3, 63, 64—the receipts cited in §2.

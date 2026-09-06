# Conditional Sector Scale and the Dirac Density Obstruction

## Status: Derived conditional scale arithmetic and chiral-scalar obstruction / Calibrated electroweak anchor / Hypothesized physical fermion coupling—September 2026

## Abstract

The arithmetic scale $\kappa_{s,\mathrm{scale}}=\varphi^{-6}/v_0^2$ follows from the stipulated offset $\delta=3$ and the external electroweak anchor $v_0$. Its inverse square root is $\varphi^3v_0\approx1.04\ \mathrm{TeV}$. This scale does not define an interaction. The proposed Dirac-to-two-fluid identification has two separate obstructions: it compares fields of different mass dimension, and its chiral-scalar bilinears are complex conjugates rather than independent nonnegative densities. Real positive values of those bilinears are equal, so they cannot realize a nonzero Yang/Yin ratio $\varphi$. The displayed squared enforcement interaction is also non-Hermitian for general unequal condensates, even after a common mass normalization. A physical fermion coupling requires different observables and a dimensionally homogeneous Hermitian action.

## 1. The projection and its mathematical boundary

The distinction between a chiral scalar and a chiral density determines whether the proposed field map can describe the canonical state. The canonical two-fluid variables satisfy $E_Y,E_I\ge0$. The optional spinor correspondence uses

$$
B_R=\bar\psi P_R\psi,\qquad B_L=\bar\psi P_L\psi,
\qquad P_{R,L}=\frac{1\pm\gamma^5}{2}.
$$

### 1.1 Dimensions and the sector symbol

In four-dimensional natural units, $[\psi]=[M]^{3/2}$, $[B_{R,L}]=[M]^3$, and the optional condensate squares $\Psi_0^2,\Psi_1^2$ have dimension $[M]^2$. The formal expression

$$
\mathcal L_{\rm proj}^{\rm formal}
=\frac{\kappa_s}{2}\left[(B_R-\Psi_0^2)^2+(B_L-\Psi_1^2)^2\right]
$$

therefore subtracts quantities of different dimensions. A common real mass scale $\mu$ could make the brackets homogeneous by replacing $\Psi_\alpha^2$ with $\mu\Psi_\alpha^2$. That operation addresses dimensions; the algebraic obstructions below remain for every positive real $\mu$.

The symbol $\kappa_s$ denotes a proposed sector interaction coefficient. It is distinct from the geometric pentagram transmission $K_{fw}=\varphi^{-1}$ in `foundations/wu-xing-cycle-structure.md` §1.3 and the charge-density coefficient in `predictions/cassi_definitions.md`. The mass dimension $-2$ would apply to a homogeneous dimension-six interaction. The formal scale in §2 selects no such interaction or coefficient.

### 1.2 Conjugacy and positivity

The adjoint of one chiral-scalar bilinear is the other. Since $\gamma^0P_R=P_L\gamma^0$,

$$
\boxed{B_R^\dagger=B_L.}
$$

For ordinary complex spinors in the Weyl basis, $\psi=(L,R)$ gives

$$
B_R=L^\dagger R,\qquad B_L=R^\dagger L=B_R^*.
$$

These quantities need not be real or positive. Taking $L=(1,0)$ and $R=(i,0)$ gives $(B_R,B_L)=(i,-i)$; taking $R=-L$ gives $(-1,-1)$. A pure left-handed spinor has both scalar bilinears zero despite a nonzero spinor density. The operator adjoint identity also constrains quantum expectation values. These two chiral scalars supply no two independent Hermitian positive-density operators.

If a common real normalization identifies both bilinears with real nonnegative condensate squares, conjugacy forces those squares to be equal. For $z=B_R$, the required golden ratio would impose

$$
z=\varphi z^*.
$$

Its real and imaginary parts obey $(1-\varphi)\operatorname{Re}z=0$ and $(1+\varphi)\operatorname{Im}z=0$. Therefore

$$
\boxed{B_R=\varphi B_L,\quad B_L=B_R^*
\quad\Longrightarrow\quad B_R=B_L=0.}
$$

Independent unequal bridge coefficients would insert the desired density ratio into the dictionary as an additional selected input. They would still need a real positive observable assignment for general states.

The frame densities $n_R=R^\dagger R$ and $n_L=L^\dagger L$ are nonnegative for ordinary complex spinors and can have ratio $\varphi$. They are components of chiral currents referred to a timelike observer, rather than the Lorentz scalars used above. A physical use of those currents requires an observer or foliation, a quantum-state and particle/antiparticle prescription, and an evolution law connecting them to the canonical conversion dynamics. None is selected by the arithmetic sector scale.

An existing component-level implementation supplies a separate nonnegative pair. In `two-fluid/cassi_dirac_bridge.py`, `yang_yin_density` splits the Dirac spinor into upper and lower two-component blocks $u,v$ (the code's large/small convention) and evaluates

$$
Y_{\rm bridge}=\|u-v\|^2,\qquad
I_{\rm bridge}=\|u+v\|^2,\qquad
Y_{\rm bridge}+I_{\rm bridge}=2\psi^\dagger\psi.
$$

For ordinary complex amplitudes, both quadratic forms are positive-semidefinite: either can vanish for a nonzero spinor. The blocks $u,v$ are distinct from the Weyl chirality labels $L,R$ used in the excluded chiral-scalar map. The helper also evaluates Pauli spin and $\psi^\dagger\alpha_i\psi$ current bilinears. Algebraic positivity of the pair leaves physical state preparation, observer dependence, quantum interpretation and matching to the canonical conversion law open. These diagnostics are outside the frozen normalization experiment; the helper's fine-structure interpretation has no adopted derivation or validation in this calculation.

### 1.3 Reality of the displayed interaction

A mass scale also leaves the action's adjoint problem unchanged. After factoring out a common dimensional bridge, write $B_R=x+iy$, $B_L=x-iy$ and let $A,B$ be real condensate targets. Then

$$
\operatorname{Im}(AB_R+BB_L)=(A-B)y,
$$

$$
\boxed{
\operatorname{Im}\left\{\frac{\kappa_s}{2}
\left[(B_R-A)^2+(B_L-B)^2\right]\right\}
=\kappa_s(B-A)y.}
$$

Both terms are generically complex when the condensates differ. They cannot define a real classical interaction or a Hermitian quantum interaction for arbitrary fields. Replacing an ordinary square by an absolute square would define a different interaction and would not make the two incompatible scalar targets simultaneously attainable.

The registered matrix and independent two-component calculations both have valid numerical receipts with empty failures. At $A=\varphi,B=1$ and $(B_R,B_L)=(i,-i)$, the linear interaction has imaginary part $+0.6180339887498949$ and the squared expression with unit coefficient has imaginary part $-0.6180339887498949$. The exact verdicts are `CONTRADICTS—chiral-scalar nonnegative-density identification` and `CONTRADICTS—displayed chiral projection interaction as a physical real action`. The five fixed witnesses, independent constructions and immutable identities are recorded in `computations/matter-formation-continuum-report.md` §12. These are checks of the specified algebraic identification and interaction; physical fermion production remains unselected.

### 1.4 Elementary carrier identity

A local invertible normalization preserves a field's Lorentz representation. The scalar carrier restriction in `foundations/particle-stationary-action-closure.md` has scalar elementary quanta under its stated canonical quantization. A Dirac field has a spinorial representation and fermionic quantization supplied as additional microscopic content. Matching a scalar mass to the electron mass supplies neither property. Fermionic topological solitons require a separate configuration space and quantization; this statement concerns the topologically trivial scalar restriction.

## 2. The conditional scale and electroweak anchor

The cascade arithmetic determines a scale once its dimensionful anchor and offset are declared. With $E_n=M_{\rm Pl}\varphi^{-n}$, the exact step-80 value is $E_{80}=233.2\ \mathrm{GeV}$ at the displayed precision. The calibrated $v_0=246\ \mathrm{GeV}$ instead has coordinate $n(v_0)\approx79.89$. These two inputs define two related scale evaluations.

Using the exact cascade value gives

$$
\kappa_{s,80}=\frac{\varphi^{-6}}{E_{80}^2}
=M_{\rm Pl}^{-2}\varphi^{154},\qquad
\kappa_{s,80}^{-1/2}=E_{77}\approx987.7\ \mathrm{GeV}.
$$

The exponent identity $154/2=77$ follows exactly from the declared offset $\delta=3$. Using the calibrated VEV gives the formal coefficient-free candidate

$$
\boxed{
\kappa_{s,\mathrm{scale}}=\frac{\varphi^{-6}}{v_0^2}
\approx9.21\times10^{-7}\ \mathrm{GeV}^{-2}
=0.921\ \mathrm{TeV}^{-2},\qquad
M_{s,\mathrm{scale}}=\varphi^3v_0\approx1042.07\ \mathrm{GeV}.}
$$

Its coordinate is $n(v_0)-3\approx76.89$, and its mass lies $5.50\%$ above $E_{77}$. The inherited electroweak offset is explicit. The equality to an integer cascade coordinate applies to the $E_{80}$-anchored expression.

More generally, a stipulated offset $\delta$ gives $\varphi^{-2\delta}/v_0^2$ and $\varphi^\delta v_0$. The choice $\delta=3$ is shared with the conditional phase-resolution construction in `gravity/quantum-gravity.md` §2.1. It selects no microscopic operator, matrix element or interaction rate. The reciprocity between $\varphi^{-6}$ and the Qi-gravity factor $\xi=\varphi^6$ is arithmetic. The numerical evaluations are recorded by `computations/kappa_s_rung_identity.py`.

## 3. Optional coefficient choices

An interaction coefficient requires an interaction to multiply. The formal readings $C\kappa_{s,\mathrm{scale}}$ below are scale conventions without a selected physical operator:

| $C$ | Formal coefficient | Formal inverse-square-root scale |
|---|---:|---:|
| $1$ | $0.921\ \mathrm{TeV}^{-2}$ | $1.042\ \mathrm{TeV}$ |
| $\varphi^{-1}$ | $0.569\ \mathrm{TeV}^{-2}$ | $1.326\ \mathrm{TeV}$ |
| $\varphi^{-2}$ | $0.352\ \mathrm{TeV}^{-2}$ | $1.686\ \mathrm{TeV}$ |

The order-of-magnitude phrase $1/\mathrm{TeV}^2$ does not discriminate among them. The solver convention $\lambda=0.1$, its Hypothesized Wu Xing interpretation and the de-resonance principle supply no operator selection or physical value of $C$. A viable Dirac/two-fluid coupling needs a dimensionally homogeneous Hermitian interaction built from suitable observables, followed by matching to the canonical density dynamics.

## 4. The transport-mobility bridge

A dimensional inconsistency also prevents the displayed sector scale from predicting the dimensionless solver mobility. The expression

$$
\chi=\frac{\kappa_s\varphi^{-1}}{m_e(1+\varphi)}
$$

would have dimension $[M]^{-3}$ if $[\kappa_s]=[M]^{-2}$. A normalization factor would need dimension $[M]^3$ before the result could be compared with a dimensionless $\chi$:

$$
\chi=\mathcal N_{\rm pde}
\frac{\kappa_s\varphi^{-1}}{m_e(1+\varphi)}.
$$

The expression specifies neither that factor's physical origin nor a matching calculation. The formal substitution $C=1$ yields $4.25\times10^{-4}$ in mixed units, which is not a dimensionless mobility. The back-solved numerical normalization $\mathcal N_{\rm pde}\approx2.35\times10^3$ is Mapped in `parameter-inventory.md` §10. Its apparent closure depends on solver conventions and does not define a microscopic coupling (`computations/n_pde_bridge_check.py`).

A physical bridge requires a specified Hermitian microscopic interaction, selected current or density observables, state preparation, and a coarse-graining calculation. Reading numerical grid constants cannot supply those missing ingredients. The solver's $\chi\in[0.5,1.0]$ remains a calibrated numerical target.

## 5. Conditional arithmetic and open predictions

| Label | Statement | Status |
|---|---|---|
| K1 | $M_{s,\mathrm{scale}}=\varphi^3v_0\approx1.04\ \mathrm{TeV}$ and $\kappa_{s,\mathrm{scale}}\approx0.921\ \mathrm{TeV}^{-2}$; the exact cascade-anchor counterpart is $E_{77}$ | Derived conditional arithmetic / Calibrated VEV input |
| K2 | A microscopic coupling and coarse-graining could predict a dimensionless solver mobility | Hypothesized; operator, normalization and state-dependent matching are unselected |
| K3 | A physical Dirac/two-fluid equilibration scale is associated with the proposed offset | Hypothesized; the scale arithmetic supplies no dynamics |

The K labels identify conditional scale statements and remain separate from the numbered prediction catalog. The excluded chiral-scalar positive-density identification and non-Hermitian enforcement expression provide no prediction for particle production, equilibration or transport.

## 6. Epistemic boundaries

The exact results are the conditional scale arithmetic, the field dimensions, the chiral-scalar adjoint identity, the nonnegative-density obstruction and the interaction-reality obstruction. The external $v_0$ anchor is Calibrated. Selected coefficient readings and the back-solved numerical bridge retain their ledgered status. The physical coupling, state preparation, microscopic production process and mapping to the canonical density dynamics remain Hypothesized or open.

The two-fluid's real-density description supplies no Dirac field by itself. Adding the standard Dirac kinetic action introduces fermionic microscopic content as an independent assumption. A physical mass fit, a cascade coordinate and a formal coefficient-free scale do not select that content or its interaction.

## References

- `foundations/unified-lagrangian.md` §§2, 5–7—optional fermion sector and action assembly.
- `foundations/particle-stationary-action-closure.md` §8.12—scalar physical-normalization and particle-identity boundary.
- `computations/matter-formation-normalization-prereg.md`—frozen unit-normalization, bilinear and action-reality checks.
- `computations/matter-formation-continuum-report.md` §12—independently verified normalization family and microscopic-identification exclusions.
- `two-fluid/cassi_dirac_bridge.py`—exploratory Dirac kinetics and nonnegative quadratic, spin and current diagnostics; physical density and fine-structure interpretations remain unestablished.
- `foundations/dimensionful-cascade.md` §§2–3—cascade scales and coordinates.
- `gravity/quantum-gravity.md` §2.1—conditional shared offset $\delta=3$.
- `computations/kappa_s_rung_identity.py`—formal sector-scale arithmetic.
- `computations/n_pde_bridge_check.py`—solver-convention dependence of the numerical mobility bridge.
- `foundations/deriving-remaining-gaps.md` §3.3—electroweak anchor offset.
- `foundations/dimensionful-constants-status.md` §2.1—solver normalization and external scales.
- `foundations/wu-xing-cycle-structure.md` §1.3—distinct pentagram transmission coefficient.
- `principles/de-resonance-principle.md`—physical selection assumptions.
- `parameter-inventory.md` §§3.3, 10—mobility status and Fit-Status Ledger.

# Interscale Stress Transfer and the Attenuation Boundary

## Status: Hypothesized—September 2026

## Abstract

A force attributed to transfer across scale must appear as a boundary flux of spatial momentum. This paper derives that conservation statement, realizes it in a reciprocal scale-stress ladder, and identifies the exact boundary between stiffness reduction and multiplicative attenuation. A conservative reciprocal ladder with an interface coefficient $d=\varphi^{-1}$ changes the traction, static compliance, and normal-mode spectrum; it does not produce a factor $d^N$ across $N$ interfaces. A separate routed two-port branch can produce $\varphi^{-N}$ for a quadratic forward flux. In that branch the Yang/Yin fixed-point fractions are declared to be port powers, the complementary return flux is retained, and each return port is prevented from coherently re-entering the forward chain. The algebra and conservation ledger are exact under those assumptions. The physical port identification, routing law, and momentum-carrying field remain Hypothesized.

---

## 1. Three interscale quantities

Scale transport can change resolved spatial motion only when the transported quantity carries spatial momentum. Three quantities used in the Cassi framework therefore have distinct roles:

| Quantity | Definition or role | What its conservation controls |
|---|---|---|
| $J_{\mathfrak s}$ | Fixed-point Yang/Yin density circulation | Transfer of component density between cascade steps |
| $\mathcal I_{\mathfrak s}$ | Gauge-source current from variation with respect to $B_{\mathfrak s}$ | Source for the scale gauge sector |
| $T_{i\mathfrak s}$ | Flux of spatial momentum component $i$ through the scale coordinate | Force on a resolved scale window |

The first two are defined in `foundations/interscale-current-soliton.md`. The third follows from spatial-translation symmetry of a time-complete action. An identification such as $T_{i\mathfrak s}\propto J_{\mathfrak s}$ or $T_{i\mathfrak s}\propto\mathcal I_{\mathfrak s}$ is a constitutive closure and requires its own dimensions and dynamics.

This distinction supplies the force boundary. Density circulation can coexist with zero spatial force, while a nonzero $T_{i\mathfrak s}$ changes the momentum assigned to a finite scale window.

---

## 2. The momentum-window identity

### 2.1 Continuum form

Let $p_i(\mathbf x,\mathfrak s,t)$ be spatial momentum density, $T_{ij}$ spatial stress, and $T_{i\mathfrak s}$ scale flux of spatial momentum. Local conservation has the form

$$
\partial_t p_i
+\partial_jT_{ij}
+\partial_{\mathfrak s}T_{i\mathfrak s}
=f_i^{\mathrm{ext}}.
$$

For a physical volume $V$ and scale window $W=[\mathfrak s_-,\mathfrak s_+]$,

$$
\begin{aligned}
\frac{dP_i^{V,W}}{dt}
={}&F_i^{\mathrm{ext}}
-\int_Wd\mathfrak s\oint_{\partial V}T_{ij}n_j\,dA\\
&+\int_Vd^3x\,
\left[
T_{i\mathfrak s}(\mathfrak s_-)
-T_{i\mathfrak s}(\mathfrak s_+)
\right].
\end{aligned}
$$

The last line is the stress-derived interscale force:

$$
\boxed{
F_i^{(\mathfrak s)}[V,W]
=
\int_Vd^3x\,
\left[
T_{i\mathfrak s}(\mathfrak s_-)
-T_{i\mathfrak s}(\mathfrak s_+)
\right].
}
$$

Summing adjacent scale windows cancels their shared boundary flux. A closed full-scale system therefore preserves total spatial momentum when external forces and physical boundary fluxes vanish.

The associated torque is

$$
\tau_k^{(\mathfrak s)}
=
\epsilon_{k\ell i}
\int_Vx_\ell f_i^{(\mathfrak s)}\,d^3x.
$$

A scalar attenuation coefficient supplies no direction or handedness. Torque requires a directed, spatially structured mixed stress.

### 2.2 A reciprocal scale-stress ladder

A minimal conservative realization uses an effective vector displacement $\mathbf u_a(\mathbf x,t)$ on cascade steps $a=0,\ldots,N$:

$$
\begin{aligned}
L_{\mathrm{lad}}
=
\int d^3x\Bigg[
&\sum_{a=0}^{N}
\left(
\frac{M_a}{2}|\dot{\mathbf u}_a|^2
-
\frac{M_ac_{T,a}^2}{2}
\partial_j u_{a,i}\partial_j u_{a,i}
\right)\\
&-
\sum_{a=0}^{N-1}
\frac{\kappa_a}{2}
|\mathbf u_{a+1}-\mathbf u_a|^2
\Bigg],
\end{aligned}
$$

with $M_a>0$ and $\kappa_a>0$. Define

$$
p_{a,i}=M_a\dot u_{a,i},
\qquad
T_{a,ij}=-M_ac_{T,a}^2\partial_j u_{a,i},
$$

and the discrete mixed stress

$$
\Pi_{a+1/2,i}
=
\kappa_a(u_{a,i}-u_{a+1,i}).
$$

The Euler–Lagrange equation becomes

$$
\partial_t p_{a,i}
+
\partial_jT_{a,ij}
+
\Pi_{a+1/2,i}
-
\Pi_{a-1/2,i}
=f_{a,i}^{\mathrm{ext}}.
$$

The interface force on step $a$ is opposite to the force on step $a+1$. Summing from $a=m$ through $a=n$ leaves only

$$
\sum_{a=m}^{n}
\left(
\Pi_{a+1/2,i}-\Pi_{a-1/2,i}
\right)
=
\Pi_{n+1/2,i}-\Pi_{m-1/2,i}.
$$

This is the discrete form of the continuum window identity. The conserved positive energy is

$$
E_{\mathrm{lad}}
=
\int d^3x\left[
\sum_{a=0}^{N}
\left(
\frac{M_a}{2}|\dot{\mathbf u}_a|^2
+
\frac{M_ac_{T,a}^2}{2}|\nabla\mathbf u_a|^2
\right)
+
\sum_{a=0}^{N-1}
\frac{\kappa_a}{2}|\mathbf u_{a+1}-\mathbf u_a|^2
\right].
$$

The ladder provides a conservative stress mechanism and introduces no sink by itself.

---

## 3. What an interface factor does

### 3.1 Frozen-state traction ratio

Write the interface stiffness as

$$
\kappa_a=\kappa_{\star,a}d_a,
\qquad 0<d_a\leq1.
$$

For the same displacement jump,

$$
\frac{\Pi_{a+1/2,i}(d_a)}
{\Pi_{a+1/2,i}(1)}
=d_a.
$$

Thus $d_a=\varphi^{-1}$ gives an exact $\varphi^{-1}$ traction ratio in a frozen-state comparison. Once the fields evolve, their displacement jump also depends on $d_a$, so this ratio does not iterate into a transfer law.

### 3.2 Normal modes

For uniform $M$, $c_T$, and $\kappa=\kappa_\star d$ on an infinite ladder, use

$$
\mathbf u_a
=
\mathbf Ue^{i(\mathbf k\cdot\mathbf x+qa-\omega t)}.
$$

The dispersion relation is

$$
\boxed{
\omega^2(\mathbf k,q)
=
c_T^2|\mathbf k|^2
+
\frac{4\kappa_\star d}{M}
\sin^2\left(\frac q2\right).
}
$$

Every frequency is real for positive $M$, $\kappa_\star$, and $d$. The coefficient $d$ changes the scale-mode frequency and group velocity. The reciprocal action retains mode amplitude and energy.

### 3.3 Static series response

A source-free static chain carries constant mixed stress,

$$
\Pi_{a+1/2,i}=\Pi_i.
$$

Across $N$ interfaces,

$$
u_{N,i}-u_{0,i}
=-\Pi_i\sum_{a=0}^{N-1}\frac1{\kappa_a},
$$

so the effective stiffness is

$$
\boxed{
\kappa_{\mathrm{eff}}
=
\left(
\sum_{a=0}^{N-1}\kappa_a^{-1}
\right)^{-1}.
}
$$

Uniform $\kappa_a=\kappa_\star d$ gives $\kappa_{\mathrm{eff}}=\kappa_\star d/N$. Reciprocal static transfer combines interface compliances in series; it does not multiply the coefficients.

---

## 4. A conditional golden flux splitter

### 4.1 Fixed-point fractions as port powers

The Yang/Yin fixed point gives normalized fractions

$$
T_\varphi=\varphi^{-1},
\qquad
R_\varphi=\varphi^{-2},
\qquad
T_\varphi+R_\varphi=1.
$$

A constitutive branch can declare these fractions to be the forward and return powers of a two-port interface. A representative real unitary matrix is

$$
S_\varphi
=
\begin{pmatrix}
t_\varphi&r_\varphi\\
-r_\varphi&t_\varphi
\end{pmatrix},
\qquad
 t_\varphi=\sqrt{T_\varphi}=\varphi^{-1/2},
\qquad
 r_\varphi=\sqrt{R_\varphi}=\varphi^{-1}.
$$

Because

$$
t_\varphi^2+r_\varphi^2
=\varphi^{-1}+\varphi^{-2}=1,
$$

this representative satisfies

$$
S_\varphi^{\mathsf T}S_\varphi=I,
\qquad
\det S_\varphi=1.
$$

The fixed-point fractions determine the magnitudes of the matrix entries. Interface phases remain free until a microscopic action fixes them.

### 4.2 Closed coherent propagation

Write $t_\varphi=\cos\theta_\varphi$ and $r_\varphi=\sin\theta_\varphi$. A closed coherent chain gives

$$
S_\varphi^N
=
\begin{pmatrix}
\cos(N\theta_\varphi)&\sin(N\theta_\varphi)\\
-\sin(N\theta_\varphi)&\cos(N\theta_\varphi)
\end{pmatrix}.
$$

Its forward power for one occupied input port is $\cos^2(N\theta_\varphi)$. Coherent return amplitudes re-enter the next interface and produce interference. The geometric product $T_\varphi^N$ belongs to a routed boundary condition rather than to the closed two-port matrix.

### 4.3 Routed, non-re-entering propagation

Suppose each interface sends its return output into a separate return rail or reservoir, with no coherent re-entry into subsequent forward inputs. Then

$$
P_{a+1}^{\mathrm{fwd}}
=T_\varphi P_a^{\mathrm{fwd}},
\qquad
P_a^{\mathrm{ret}}
=R_\varphi P_a^{\mathrm{fwd}}.
$$

Iteration gives

$$
\boxed{
P_N^{\mathrm{fwd}}
=\varphi^{-N}P_0^{\mathrm{fwd}}.
}
$$

The accumulated return power is

$$
\sum_{a=0}^{N-1}P_a^{\mathrm{ret}}
=
R_\varphi P_0^{\mathrm{fwd}}
\sum_{a=0}^{N-1}T_\varphi^a
=
\left(1-\varphi^{-N}\right)P_0^{\mathrm{fwd}}.
$$

Therefore

$$
P_N^{\mathrm{fwd}}
+
\sum_{a=0}^{N-1}P_a^{\mathrm{ret}}
=P_0^{\mathrm{fwd}}.
$$

The apparent attenuation is redistribution between resolved and return channels. A full closed system retains both channels and conserves the total.

### 4.4 Amplitude and flux exponents

The routed splitter acts on amplitudes through $t_\varphi$ and on quadratic powers through $T_\varphi$:

$$
A_N^{\mathrm{fwd}}
=\varphi^{-N/2}A_0^{\mathrm{fwd}},
\qquad
P_N^{\mathrm{fwd}}
=\varphi^{-N}P_0^{\mathrm{fwd}}.
$$

Accordingly, this branch realizes the universal suppression formula only when the quantity called a signal is a quadratic conserved flux, power, stress, or energy. Amplitude-like couplings and phases require an observable-specific map.

### 4.5 Stress-derived force in the routed branch

Suppose the normalized port power is proportional to a collinear signed
spatial-momentum flux, with the same power-to-momentum conversion on the input
and output ports. The momentum transferred out of the resolved forward channel
at interface $a$ is

$$
\mathcal X_{i,a}^{\mathrm{route}}
=
P_{i,a}^{\mathrm{fwd}}
-P_{i,a+1}^{\mathrm{fwd}}
=R_\varphi P_{i,a}^{\mathrm{fwd}}.
$$

The forward-channel momentum balance contains
$-\mathcal X_{i,a}^{\mathrm{route}}$. Summing the outward transfer gives

$$
\sum_{a=0}^{N-1}\mathcal X_{i,a}^{\mathrm{route}}
=
\left(1-\varphi^{-N}\right)P_{i,0}^{\mathrm{fwd}}.
$$

The return-port label specifies motion toward the opposite direction in the
scale graph. It does not determine the direction of the carried spatial
momentum. For collinear ports, introduce the routing-orientation label

$$
\sigma_a\in\{+1,-1\},
\qquad
P_{i,a}^{\mathrm{ret}}
=
\sigma_aR_\varphi P_{i,a}^{\mathrm{fwd}}.
$$

Here $\sigma_a=+1$ preserves the spatial-momentum direction and
$\sigma_a=-1$ reverses it. Let $I_{i,a}^{\mathrm{interface}}$ be the momentum
delivered to the interface or reservoir. Local vector conservation requires

$$
\begin{aligned}
P_{i,a}^{\mathrm{fwd}}
&=
P_{i,a+1}^{\mathrm{fwd}}
+
P_{i,a}^{\mathrm{ret}}
+
I_{i,a}^{\mathrm{interface}},\\
I_{i,a}^{\mathrm{interface}}
&=
(1-\sigma_a)R_\varphi P_{i,a}^{\mathrm{fwd}}.
\end{aligned}
$$

For $\sigma_a=+1$, the return rail carries the complementary spatial momentum
and the interface impulse vanishes. For $\sigma_a=-1$, the reflected spatial
momentum gives
$I_{i,a}^{\mathrm{interface}}=2R_\varphi P_{i,a}^{\mathrm{fwd}}$. A
non-collinear port replaces $\sigma_a$ with its spatial routing map, and the
interface term closes the corresponding vector difference. The splitter fixes
scalar power fractions; carrier velocity, impedance, and port geometry fix the
signed momentum ledger. The full forward-plus-return-plus-interface system has
zero internal net force.

---

## 5. Relation to the Cassi mixed-curvature force

The interscale action in `foundations/interscale-current-soliton.md` gives the conditional mixed force density

$$
f_i^{\mathrm{mix}}
=\hbar\mathcal I_{\mathfrak s}G_{i\mathfrak s}.
$$

If a completed action identifies a forward component of $\mathcal I_{\mathfrak s}$ with the routed flux, then

$$
\mathcal I_{\mathfrak s}^{\mathrm{fwd}}(n)
=\varphi^{-(n-m)}
\mathcal I_{\mathfrak s}^{\mathrm{fwd}}(m)
$$

and, for fixed $G_{i\mathfrak s}$, the forward mixed-force contribution carries the same quadratic-flux factor. The return-current contribution remains part of the full conservation law.

This identification requires four additional pieces:

1. the Noether stress tensor of the time-completed field action;
2. a dimensionally explicit map from $\mathcal I_{\mathfrak s}$ to $T_{i\mathfrak s}$;
3. a microscopic two-port interaction that fixes the splitter magnitudes and phases;
4. a return rail, reservoir, or decoherence mechanism that enforces non-re-entry.

The fixed-point density ratio selects the candidate port powers in this branch. It does not derive the physical port map or the routed boundary condition.

---

## 6. Consequences for cascade attenuation

The derivation separates three mechanisms that can share the same scalar coefficient:

| Mechanism | Role of $d=\varphi^{-1}$ | Transfer across $N$ interfaces |
|---|---|---|
| Reciprocal elastic ladder | Interface stiffness or conductance | Normal-mode dispersion; static series compliance |
| Closed coherent two-port chain | Single-interface power fraction | $\cos^2(N\theta_\varphi)$ for the representative phase choice |
| Routed two-port chain | Forward power fraction with return non-re-entry | $\varphi^{-N}$ forward flux plus $1-\varphi^{-N}$ return flux |

The resulting conditional statement is

$$
\boxed{
\frac{P_N^{\mathrm{fwd}}}{P_0^{\mathrm{fwd}}}
=\varphi^{-N}
\quad
\text{for a quadratic forward flux with routed return ports.}
}
$$

This statement supplies an explicit conservative realization of the suppression algebra. It does not promote the universal attenuation law to a dynamical prediction. Existing applications in `foundations/cascade-suppression-formula.md` retain their registered tiers until each observable is identified with a physical routed flux.

---

## 7. Status and discriminating tests

| Result | Status |
|---|---|
| Scale-window force equals the difference of mixed-stress boundary fluxes | **Derived** from local momentum conservation |
| Reciprocal ladder interface forces cancel pairwise | **Derived** from the ladder action |
| Positive reciprocal ladder has real normal modes and series compliance | **Derived** |
| $S_\varphi$ is unitary for the selected fixed-point power fractions | **Derived conditional algebra** |
| Closed coherent propagation gives $\cos^2(N\theta_\varphi)$ | **Derived conditional algebra** |
| Routed non-re-entry gives forward flux $\varphi^{-N}$ with a complementary return ledger | **Derived conditional algebra** |
| Yang/Yin density fractions are physical port powers | **Hypothesized constitutive identification** |
| Return channels are physically routed without coherent re-entry | **Hypothesized boundary dynamics** |
| $\mathcal I_{\mathfrak s}$ carries the physical mixed stress $T_{i\mathfrak s}$ | **Hypothesized constitutive identification** |

A physical realization must measure all three ledgers at each interface: forward flux, return flux, and stored or dissipated energy. The routed branch requires the ratios

$$
\frac{P_{a+1}^{\mathrm{fwd}}}{P_a^{\mathrm{fwd}}}
=\varphi^{-1},
\qquad
\frac{P_a^{\mathrm{ret}}}{P_a^{\mathrm{fwd}}}
=\varphi^{-2},
$$

with their sum equal to unity before any universal interpretation is assigned. A reciprocal chain, a coherent two-port chain, or an unclosed loss term falsifies that specific realization when it replaces these ledgers.

The algebraic receipt is `computations/interscale_stress_attenuation_check.py`.

---

## References

- `foundations/cassi-first-principles.md` §1.2—Yang/Yin attractor and fixed-point density fractions
- `foundations/cascade-suppression-formula.md`—registered conditional suppression law and evidence boundary
- `foundations/interscale-current-soliton.md`—density current, gauge current, endpoint circuit, and mixed-curvature force
- `foundations/endpoint-link-and-localization-boundary.md`—endpoint transfer and return-path boundary conditions
- `computations/interscale_stress_attenuation_check.py`—conservation, splitter, coherent-chain, and routed-chain checks

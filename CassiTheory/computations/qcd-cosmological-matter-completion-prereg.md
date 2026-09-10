# QCD Cosmological Matter-Completion Protocol

## Status: Preregistered—September 2026

## Abstract

This protocol tests the strongest physically standard completion of the Cassi
matter-formation program that can be specified without treating the canonical
two-density field as a microscopic quantum theory. One connected model is used
throughout: renormalized Standard Model QCD for confinement and hadrons, a
minimal two-singlet type-I seesaw for thermal leptogenesis, a gauge-projected
thermal density operator after reheating, and radiation-era expansion through
the QCD crossover. The calculation separates two conclusions. It can establish
a conditional empirical history in which a generated baryon excess is carried
through QCD hadronization into observable nucleons. It cannot establish that
the Cassi density equations select the Standard Model fields, the seesaw
sector, their parameters, or the quantum state.

The protocol was frozen before executing the leptogenesis, thermal chemistry,
nonradial density, and completion-adjudication programs. The exploratory
unconstrained radial diagnostic that motivated a separate state-domain study
is excluded from every gate here.

## 1. Questions

The calculation asks six conjunctive questions.

1. Does one renormalized microscopic action define the color, quark, lepton,
   Higgs, and heavy-neutrino fields used in every later stage?
2. Does a positive gauge-projected initial density operator and a specified
   out-of-equilibrium interaction generate nonzero $B-L$ from zero initial
   $B-L$?
3. Does the same generated asymmetry survive sphaleron conversion and remain
   within the observed baryon-to-photon interval after QCD formation and
   baryon-antibaryon annihilation?
4. Do nonradial perturbations of the coarse-grained thermal baryon and
   antibaryon densities relax without violating net baryon number?
5. Does renormalized QCD provide a regulator-qualified color-singlet nucleon
   state with the observed spin, charges, and at least one out-of-fit mass
   discriminator?
6. Which parts of this completion are consequences of registered Cassi laws,
   and which are empirical or additional model inputs?

## 2. One microscopic action

### 2.1 QCD and electroweak sector

The ultraviolet action is the renormalized Standard Model action with three
colors and the physical quark representations. The strong sector is

$$
\mathcal L_{\rm QCD}
=-\frac14G^a_{\mu\nu}G^{a\mu\nu}
+\sum_f\bar q_f(i\gamma^\mu D_\mu-m_f)q_f
+\frac{\theta g_s^2}{32\pi^2}G^a_{\mu\nu}\widetilde G^{a\mu\nu},
\qquad
D_\mu=\partial_\mu-i g_sA_\mu^aT^a.
$$

The finite-cutoff definition uses compact $SU(3)$ links and a standard local
lattice fermion discretization. The continuum theory is fixed by a line of
constant physics for the renormalized coupling and quark masses as $a\to0$ and
$L\to\infty$. No chromodielectric field is retained in the ultraviolet
completion. Its role remains confined to the finite-cutoff effective bridge in
`computations/qcd-confining-carrier-prereg.md`.

For $N_f$ active Dirac flavors, the first two strong beta-function coefficients
are

$$
\beta_0=11-\frac23N_f,
\qquad
\beta_1=102-\frac{38}{3}N_f.
$$

The program must verify $\beta_0>0$ for $N_f=6$ and the resulting ultraviolet
flow $g_s(\mu)\to0$. This establishes perturbative renormalizability and
asymptotic freedom conditional on the supplied field content. It does not
constitute an analytic proof of the continuum Yang–Mills mass gap. Physical
confinement and the nucleon spectrum enter through continuum-extrapolated
lattice-QCD evidence.

### 2.2 Minimal leptogenesis sector

Two gauge-singlet Majorana fermions $N_i$ are added:

$$
\mathcal L_N
=\frac12\overline{N_i}i\!\not\!\partial N_i
-\frac12M_i\overline{N_i^c}N_i
-\left(Y_{\alpha i}\overline{L_\alpha}\widetilde HN_i+\text{h.c.}\right).
$$

This is a renormalizable extension of the same action. Majorana masses violate
lepton number, complex Yukawa products violate CP, and decays in an expanding
thermal state depart from equilibrium. Electroweak sphalerons conserve $B-L$
and convert the generated lepton asymmetry into baryon asymmetry.

For normal light-neutrino ordering, the frozen two-singlet Casas–Ibarra
parameterization is

$$
Y=\frac1vU_{\rm PMNS}\sqrt{m_\nu^{\rm diag}}\,R(z)\sqrt{M^{\rm diag}},
\qquad
R(z)=
\begin{pmatrix}
0&0\\
\cos z&-\sin z\\
\sin z&\cos z
\end{pmatrix},
$$

with

$$
v=174\ {\rm GeV},\quad
m_1=0,\quad
m_2=\sqrt{7.42\times10^{-5}}\ {\rm eV},\quad
m_3=\sqrt{2.517\times10^{-3}}\ {\rm eV},
$$

$$
\boxed{z=\frac\pi4+\frac{i}{2},\qquad M_2=10M_1.}
$$

The complex angle and heavy-mass ratio are declared benchmark inputs. They are
not inferred from the light-neutrino spectrum or from Cassi. The primary arm
calibrates the one remaining mass $M_1$ to the observed baryon asymmetry. A
separate no-fit arm fixes $M_1=10^{14}\ {\rm GeV}$, the order of the mapped
seesaw scale in `foundations/neutrino-masses.md`, and is adjudicated without
retuning.

## 3. Quantum initial state

At reheating temperature $T_R>M_2$, the initial state is

$$
\boxed{
\rho_R=Z^{-1}P_G
\exp\!\left[-\frac{H-\sum_A\mu_AQ_A}{T_R}\right]P_G,
\qquad \rho_R\succeq0,\quad \operatorname{Tr}\rho_R=1.}
$$
The reheating temperature is fixed to $T_R=20M_2$ in both numerical arms.

$P_G$ projects onto the gauge-invariant Hilbert space. All chemical potentials
for violated charges begin at zero, so $Y_{B-L}(z_i)=0$. The heavy-neutrino
abundance begins in thermal equilibrium. This state is a declared cosmological
boundary condition. Inflationary preparation and a Cassi rule selecting it are
outside the model.

## 4. Frozen leptogenesis calculation

Let $x=M_1/T$, $x_i=10^{-3}$, and $x_f=50$. In the one-flavor decay and
inverse-decay approximation,

$$
N_{N_1}^{\rm eq}(x)=\frac12x^2K_2(x),
\qquad
D(x)=Kx\frac{K_1(x)}{K_2(x)},
\qquad
W(x)=\frac14Kx^3K_1(x),
$$

$$
\frac{dN_{N_1}}{dx}=-D(N_{N_1}-N_{N_1}^{\rm eq}),
\qquad
\frac{dN_{B-L}}{dx}=-\epsilon_1D(N_{N_1}-N_{N_1}^{\rm eq})-WN_{B-L}.
$$

Here

$$
\widetilde m_1=\frac{v^2(Y^\dagger Y)_{11}}{M_1},
\qquad
K=\frac{\widetilde m_1}{m_*},
\qquad m_*=1.08\times10^{-3}\ {\rm eV}.
$$

The finite-hierarchy one-loop asymmetry is

$$
\epsilon_1=
\frac{1}{8\pi(Y^\dagger Y)_{11}}
\operatorname{Im}\!\left[(Y^\dagger Y)_{12}^2\right]
F\!\left(\frac{M_2^2}{M_1^2}\right),
$$

$$
F(r)=\sqrt r\left[\frac1{1-r}+1-(1+r)\ln\!\frac{1+r}{r}\right].
$$

The reported sign convention chooses positive final baryon number; every
magnitude check is sign independent. The photon-normalized result is

$$
\eta_B=0.96\times10^{-2}|N_{B-L}(x_f)|.
$$

The primary numerical solve uses `scipy.integrate.solve_ivp` with method
`DOP853`, relative tolerance $10^{-10}$, absolute tolerance $10^{-13}$, and
maximum step $0.05$. Verification repeats the solve with `Radau`, relative
tolerance $3\times10^{-11}$, absolute tolerance $3\times10^{-14}$, and maximum
step $0.025$.

The target is the frozen interval

$$
5.8\times10^{-10}\le\eta_B\le6.4\times10^{-10}.
$$

The calibrated arm may solve only for $M_1$ on
$10^8\le M_1/{\rm GeV}\le10^{13}$. The angle, mass ratio, light masses,
initial state, ODE, conversion factor, and tolerances remain fixed. The result
is explicitly `Calibrated`; it is not a prediction of $\eta_B$.

## 5. Frozen QCD-era chemistry

The QCD crossover temperature is
$T_c=156.5\ {\rm MeV}$. Proton and neutron are represented together by a
spin-isospin degeneracy $g_N=4$ and mean mass
$m_N=938.918754\ {\rm MeV}$. In the Maxwell–Boltzmann hadron-resonance-gas
baseline, the zero-chemical-potential density of baryons alone is

$$
n_0(T)=\frac{g_Nm_N^2T}{2\pi^2}K_2(m_N/T).
$$

Define entropy-normalized total and net yields
$Y_+=(n_B+n_{\bar B})/s$ and
$Y_-= (n_B-n_{\bar B})/s$, with

$$
s=\frac{2\pi^2}{45}g_{*s}T^3,
\qquad
H=1.66\sqrt{g_*}\frac{T^2}{M_{\rm Pl}}.
$$

The generated baryon-to-photon ratio fixes
$Y_-=\eta_B/7.04$. With $u=m_N/T$, the annihilation history obeys

$$
\frac{dY_+}{du}
=-\frac{s\langle\sigma v\rangle}{2Hu}
\left[Y_+^2-Y_-^2-4Y_0(T)^2\right],
\qquad Y_0=n_0/s.
$$

The primary uses $\langle\sigma v\rangle=50\ {\rm mb}$ and repeats
$40$ and $60\ {\rm mb}$ as declared sensitivity arms. The integration begins
in chemical equilibrium at $T_c$ and ends at $T=1\ {\rm MeV}$. A tabulated
piecewise-linear interpolation uses $(T/{\rm MeV},g_*,g_{*s})=(156.5,61.75,
61.75),(100,17.25,17.25),(10,10.75,10.75),(1,10.75,10.75)$. This idealized
chemistry is a controlled baseline, not a real-time lattice-QCD calculation.

## 6. Frozen nonradial density calculation

A periodic $24^3$ grid tests the coarse-grained reaction-diffusion equations
at $T=100\ {\rm MeV}$:

$$
\partial_t n_B=D_s\nabla^2n_B
-k_a(n_Bn_{\bar B}-n_0^2),
\qquad
\partial_t n_{\bar B}=D_s\nabla^2n_{\bar B}
-k_a(n_Bn_{\bar B}-n_0^2).
$$

The dimensionless run sets $D_s=0.2$, $k_a=1$, grid spacing one, time step
$0.01$, 2,000 Strang-split steps, and NumPy seed `20260910`. The initial
baryon and antibaryon fields are the equilibrium means compatible with the
physical $Y_-$ plus common and differential zero-mean Gaussian perturbations
of RMS $5\%$ and $2\%$ of $n_0$, clipped only if positivity would otherwise
fail. Diffusion is applied exactly in Fourier space; the local reaction pair is
advanced by fourth-order Runge–Kutta. A half-time-step rerun is the convergence
arm. Zero-reaction and zero-diffusion runs are controls.

This calculation can qualify conservation and decay of coarse-grained
nonradial thermal-density perturbations. It cannot qualify the internal
three-dimensional wavefunction of one nucleon or real-time confinement.

## 7. Observable nucleon map

The color-singlet interpolators

$$
p\sim\epsilon_{abc}(u_a^TC\gamma_5d_b)u_c,
\qquad
n\sim\epsilon_{abc}(d_a^TC\gamma_5u_b)d_c
$$

carry $B=1$, spin $1/2$, positive ground-state parity, and electric charges
$+1$ and $0$. The out-of-fit mass discriminator is the continuum lattice-QCD
result $m_N^{\rm lat}=0.936(25)(22)\ {\rm GeV}$ against the isospin-averaged
experimental $0.939\ {\rm GeV}$ reported by Dürr et al. The combined quoted
uncertainty is used without refitting.

## 8. Gates and decision tree

### 8.1 `PCM1`—renormalized microscopic action

`PASS EMPIRICAL` requires the operator inventory to be local and gauge
invariant, the seesaw extension to be power-counting renormalizable,
$\beta_0>0$ for six-flavor QCD, and the cited continuum lattice calculation to
contain dynamical light and strange quarks, at least three lattice spacings,
a continuum extrapolation, and agreement of the nucleon mass with experiment
within its combined quoted uncertainty. Any failed condition gives `FAIL`.

### 8.2 `PCM2`—state and baryogenesis

`PASS CALIBRATED` requires a positive normalized projected thermal state, zero
initial $B-L$, nonzero computed $\epsilon_1$ satisfying the Davidson–Ibarra
bound, reconstruction of the two nonzero light masses to relative error below
$10^{-10}$, $10^9<M_1/{\rm GeV}<10^{13}$, $T_R>M_2$, maximum
$|Y_{\alpha i}|<1$, final calibrated $\eta_B$ inside the frozen interval, and
primary/verification relative agreement below $5\times10^{-4}$. A passing
result remains calibrated because $M_1$ is fixed by $\eta_B$.

The $M_1=10^{14}\ {\rm GeV}$ no-fit arm returns `SUPPORTS` only if its
$\eta_B$ lies in the frozen interval without changing any other input;
otherwise it returns `CONTRADICTS`.

### 8.3 `PCM3`—thermal hadron chemistry

`SUPPORTS` requires numerical yield agreement below $5\times10^{-4}$ between
the primary and verification solvers, net-yield conservation to relative
error below $10^{-10}$, final antibaryon fraction
$n_{\bar B}/(n_B+n_{\bar B})<10^{-6}$ in all three cross-section arms, and
final $\eta_B$ drift below $10^{-10}$ relative. Any numerical failure gives
`FAIL`; a surviving antibaryon fraction above threshold gives `CONTRADICTS`.

### 8.4 `PCM4`—nonradial thermal-density response

`SUPPORTS` requires positivity, mean net-baryon conservation with absolute
error below $2\times10^{-13}n_0$, a reduction of nonzero-mode RMS by at least $90\%$, and
half-step agreement of the final total yield below $10^{-3}$. The zero-reaction
control must retain its pair mean to relative error below $10^{-11}$; the
zero-diffusion control must retain more nonzero-mode power than the full arm.
This gate applies only to the declared coarse-grained equations.

### 8.5 `PCM5`—observable nucleon map

`PASS EMPIRICAL` requires the interpolator quantum numbers to match the
proton/neutron map, the lattice central mass to lie within the combined quoted
uncertainty of the experimental mass, and the cited calculation to include a
continuum extrapolation with dynamical light quarks.

### 8.6 `PCM6`—completion scope

Set `conditional_empirical_matter_history=SUPPORTS` exactly when
`PCM1=PASS EMPIRICAL`, `PCM2=PASS CALIBRATED`, `PCM3=SUPPORTS`,
`PCM4=SUPPORTS`, and `PCM5=PASS EMPIRICAL`.

Set `complete_physical_Cassi_matter_formation=PASS` only if the registered
Cassi action independently selects the Standard Model gauge representations,
QCD and seesaw operators, their renormalized parameters, the complex
Casas–Ibarra coordinate, the projected thermal state, and the reheating
condition. Otherwise it is `FAIL`, even if the conditional empirical history
passes. This gate cannot be changed by calibrating $M_1$.

## 9. Required artifacts

The primary writes under
`runs/20260910_qcd_cosmological_matter_completion/primary/`:

- `results.json` with constants, source hashes, Yukawa matrices, ODE histories,
  chemistry histories, nonradial metrics, evidence ledger, gates, and elapsed
  time;
- `nonradial_fields.npz` with initial and final density fields;
- `report.md` generated from `results.json`.

An independent implementation writes
`runs/20260910_qcd_cosmological_matter_completion/verification/verification.json`.
It may read the primary receipt and arrays but must not import the primary
program. Missing, altered, nonfinite, or internally inconsistent evidence
fails closed.

## References

- `computations/matter-formation-continuum-report.md` §§29, 79–82—six-part completion interface and active QCD boundary.
- `foundations/matter-completion-boundary.md` §§12, 24, 26–27—physical requirements, regular carrier, confinement bridge, and interacting radial result.
- `foundations/neutrino-masses.md`—conditional seesaw scale and fitted light-neutrino spectrum.
- S. Davidson and A. Ibarra, [“A lower bound on the right-handed neutrino mass from leptogenesis”](https://arxiv.org/abs/hep-ph/0202239)—hierarchical CP-asymmetry bound.
- S. Davidson, E. Nardi, and Y. Nir, [“Leptogenesis”](https://arxiv.org/abs/0802.2962)—thermal state, Boltzmann equations, washout, and sphaleron conversion.
- A. Bazavov et al., [“Chiral crossover in QCD at zero and non-zero chemical potentials”](https://arxiv.org/abs/1812.08235)—continuum $T_c=156.5\pm1.5\ {\rm MeV}$.
- S. Dürr et al., [“Ab-initio Determination of Light Hadron Masses”](https://arxiv.org/abs/0906.3599)—dynamical continuum lattice-QCD nucleon spectrum.

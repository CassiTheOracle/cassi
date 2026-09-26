# Quantum Free-Fall Correspondence Clean-Room Receipt

## Status: Verified independent computation—September 2026

## 1. Independence boundary

The calculation received the complete frozen objects and proof obligations in
`computations/quantum_free_fall_correspondence_prereg.md`, together with the
primary Quantum Galileo Interferometer source
([arXiv:2502.14535](https://arxiv.org/abs/2502.14535);
[doi:10.1126/sciadv.aec8045](https://doi.org/10.1126/sciadv.aec8045)). It did
not inspect or execute
`computations/verify_quantum_free_fall_correspondence.py`. No repository file
was edited during the recomputation.

## 2. Independent gate results

### QF1—Accelerated-frame cancellation: PASS

Set $\alpha=m_g/m_i$ and
$\zeta=z+\tfrac12\alpha gt^2$. For
$\psi_N=e^{if/\hbar}\psi_E(\zeta,t)$, derivative matching gives
$f_z=-m_i\dot\zeta=-m_ggt$. The scalar condition is

$$
f_t+\frac{f_z^2}{2m_i}+m_ggz=0.
$$

Its solution, up to an irrelevant constant phase, is

$$
f=-m_ggtz-\frac{m_g^2}{6m_i}g^2t^3.
$$

Both the first-derivative coefficient and scalar residual vanish.

### QF2—Closed ballistic path: PASS

The endpoint condition

$$
z_b(2T)=2v_0T-2\frac{m_g}{m_i}gT^2=0
$$

requires $v_0=(m_g/m_i)gT$. Therefore

$$
z_b=\frac{m_g}{m_i}g\left(Tt-\frac{t^2}{2}\right),
\qquad
\dot z_b=\frac{m_g}{m_i}g(T-t).
$$

Direct integration over $0\le t\le2T$ gives

$$
S_K=\frac{m_g^2g^2T^3}{3m_i},
\qquad
S_V=-\frac{2m_g^2g^2T^3}{3m_i}.
$$

### QF3—General ideal QGI phase: PASS

The ideal held path has zero propagation action under the declared calibrated
holding convention. Hence

$$
S_b-S_r=-\frac{m_g^2g^2T^3}{3m_i},
\qquad
\Delta\phi=-\frac{m_g^2g^2T^3}{3\hbar m_i}.
$$

For $m_g=m_i=m$, this becomes

$$
\Delta\phi=-\frac{mg^2T^3}{3\hbar},
$$

with the sign and coefficient of the primary source's ideal equal-mass phase.

### QF4—Local-acceleration degeneracy: PASS

Using $g_b=(m_g/m_i)g$ gives

$$
\Delta\phi=-\frac{m_i g_b^2T^3}{3\hbar}.
$$

The phase expressed through the same ballistic preparation's local acceleration
contains no separate source-field and response-ratio measurement.

### QF5—Differential held-arm observable: PASS

For a common source, $a_b=r_bg$, nonzero $a_h=r_rg$, and
$\Delta\phi_b=-m_i r_b^2g^2T^3/(3\hbar)$,

$$
\mathcal R_{br}
=\sqrt{\frac{-3\hbar\Delta\phi_b}{m_iT^3a_h^2}}
=\left|\frac{r_b}{r_r}\right|.
$$

This is a conditional effective-response ratio. It contains no inferred Cassi
preparation-to-response map.

### QF6—Common-lapse coordinate invariance: PASS

For

$$
S_N=\int dt\left[\frac{m_i\dot z^2}{2N}-Nm_ggz\right],
$$

the Euler–Lagrange equation is
$\ddot z=-N^2(m_g/m_i)g$. Consistent closure requires
$\dot z(0)=N^2(m_g/m_i)gT$ and gives

$$
S_{K,N}=\frac{N^3m_g^2g^2T^3}{3m_i},
\qquad
S_{V,N}=-\frac{2N^3m_g^2g^2T^3}{3m_i}.
$$

Thus

$$
\Delta\phi_N=-\frac{N^3m_g^2g^2T^3}{3\hbar m_i}
=-\frac{m_g^2g^2\mathcal T^3}{3\hbar m_i},
\qquad \mathcal T=NT.
$$

The constant common lapse cancels when the launch, closure, and duration are
expressed in the same physical clock.

### QF7—Attractor-line normalization: PASS

The frozen definitions

$$
\rho=E_Y+E_I,
\qquad
\pi=E_Y-E_I,
\qquad
\varepsilon=E_Y-\varphi E_I
$$

and $\varepsilon=0$ give

$$
E_Y=\varphi E_I,
\qquad
s=\frac{\pi}{\rho}
=\frac{\varphi-1}{\varphi+1}
=\varphi^{-3}.
$$

With $\rho_\star=1$,

$$
q_{\mathrm{eq}}(\rho)
=\frac{\rho^2}{\rho^2+\varphi^{-2}},
\qquad
\lim_{\rho\to0^+}q_{\mathrm{eq}}=0.
$$

At $\rho=\varphi$, the identity
$\varphi^2+\varphi^{-2}=3$ gives

$$
q_{\mathrm{eq}}=\frac{\varphi^2}{3}
=0.87267799625,
$$

and

$$
\mathcal G_C
=\varphi^{-3}\left[1+(\varphi^6-1)\frac{\varphi^2}{3}\right]
=\frac{5\sqrt5}{3}
=3.7267799625.
$$

### QF8—Dimensional closure: PASS

The phase factor obeys

$$
\left[\frac{m_g^2g^2T^3}{\hbar m_i}\right]
=\frac{M(LT^{-2})^2T^3}{ML^2T^{-1}}=1.
$$

The local-acceleration form and QF5 radicand are likewise dimensionless. The
field quantities $E_Y,E_I,\rho,\pi,\varepsilon,\rho_\star$ share density units,
so $q$, $s$, and $\mathcal G_C$ are dimensionless.

## 3. Independent verdict

QF1–QF8 pass. The independent calculation supports `ADOPT` for the Derived
conditional centre-of-mass correspondence in a supplied uniform external
potential and the ideal closed-ballistic limit. The result supplies no
identification of $m_g/m_i$ with a Cassi field functional, source equation,
scalar screening, finite-pulse apparatus correction, or universal or
path-dependent lapse.

# Cassi Cosmology: Scale-Dependent Gravity from the Dispersion Relation

*Deriving a k-dependent effective gravitational coupling from the Cassi master
wave equation.*

---

## 1. The Cassi Dispersion Relation

The Cassi mathematics document gives the dispersion relation for waves on the
spine:

$$
\omega(k) = v_0 k_0 \left(\frac{k}{k_0}\right)^\alpha - i\frac{\gamma}{2}
$$

where:

- $v_0$ is a reference wave speed,
- $k_0$ is a reference wavenumber,
- $\alpha$ is the dispersion exponent,
- $\gamma$ is the universal damping.

The key physical insight is that **different scales propagate at different
speeds**. For $\alpha = 1$ the medium is non-dispersive; for $\alpha \neq 1$
the scale hierarchy is compressed or stretched.

---

## 2. Scale-Dependent Wave Speed

The real part of the dispersion relation defines a scale-dependent phase speed:

$$
v(k) = \frac{\omega(k)}{k} = v_0 \left(\frac{k}{k_0}\right)^{\alpha - 1}
$$

So the wave speed itself depends on wavenumber. Small-scale waves ($k \gg k_0$)
move faster than large-scale waves if $\alpha > 1$, and slower if $\alpha < 1$.

In three dimensions the master wave equation becomes:

$$
\frac{\partial^2 \psi}{\partial t^2}
+ \gamma \frac{\partial \psi}{\partial t}
= v^2(-i\nabla) \, \nabla^2 \psi
+ S(\mathbf{x},t)
$$

where $v^2(-i\nabla)$ is the operator that applies $v(k)^2$ in Fourier space.

---

## 3. Static Limit: A Scale-Dependent Poisson Equation

Taking the quasi-static limit as before:

$$
0 = v^2(-i\nabla) \, \nabla^2 \psi + S(\mathbf{x})
\quad \Longrightarrow \quad
\nabla^2 \psi = -\frac{S(\mathbf{x})}{v^2(-i\nabla)}
$$

In Fourier space:

$$
\hat{\psi}_k = -\frac{\hat{S}_k}{v(k)^2 k^2}
$$

Substituting $v(k)$:

$$
\hat{\psi}_k = -\frac{\hat{S}_k}{v_0^2 k_0^{2(1-\alpha)} k^{2\alpha}}
$$

For standard gravity we have $\alpha = 1$ and $v_0^2 = 1$ (in code units), which
recovers the usual $1/k^2$ Poisson kernel. For $\alpha \neq 1$ the effective
gravitational coupling is scale-dependent:

$$
G_\text{eff}(k) \propto \frac{1}{v(k)^2} \propto k^{-2(\alpha - 1)}
$$

---

## 4. Physical Interpretations

| $\alpha$ | $v(k)$ behavior | Gravity effect |
|---|---|---|
| $\alpha < 1$ | $v(k)$ decreases with $k$ | $G_\text{eff}(k)$ increases with $k$: small scales feel stronger gravity |
| $\alpha = 1$ | constant $v(k) = v_0$ | standard Newtonian gravity |
| $\alpha > 1$ | $v(k)$ increases with $k$ | $G_\text{eff}(k)$ decreases with $k$: small scales feel weaker gravity |

This is a Cassi-inspired way to generate modified-gravity-like signatures:

- **$\alpha > 1$** mimics a small-scale suppression similar to warm dark matter,
  a strong Jeans scale, or a holographic information bound.
- **$\alpha < 1$** mimics a small-scale enhancement similar to the signed
  entropic mode or some modified-gravity theories.

---

## 5. The Role of $\varphi$

The Cassi principle suggests that natural scale separation occurs when scales
are spaced by $\varphi$. We can therefore choose the reference wavenumber $k_0$
as the fundamental mode of the box and sample $\alpha$ values that are
$\varphi$-related, such as:

$$
\alpha = 1 \pm \varphi^{-1}, \qquad 1 \pm \varphi^{-2}
$$

For example:

- $\alpha = 1 + \varphi^{-1} \approx 1.618$ (super-linear, small-scale suppression)
- $\alpha = 1 - \varphi^{-1} \approx 0.382$ (sub-linear, small-scale enhancement)

---

## 6. Connection to Previous Work

The scale-dependent master field generalizes both the holographic-cutoff
simulations and the entropic-gravity simulations:

- **Holographic cutoff:** A sharp suppression of high-$k$ modes is a limiting
case of $\alpha > 1$.
- **Entropic gravity:** A nonlinear source is another way to modify small-scale
behavior; here the modification comes from the propagation speed of the
information field itself.

Combining both — a nonlinear Yin source plus a scale-dependent dispersion —
gives a two-parameter family of Cassi cosmological models.

---

## 7. Summary

By taking the Cassi dispersion relation seriously, gravity becomes
scale-dependent in a natural way. The static limit of the master wave equation
with $v(k) = v_0 (k/k_0)^{\alpha - 1}$ yields a Poisson-like equation with an
effective $k^{2\alpha}$ denominator instead of the usual $k^2$. This provides a
first-principles route to modifying structure formation on small scales while
preserving large-scale Newtonian behavior.

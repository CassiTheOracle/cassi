# Cassi Two-Fluid 3D: Cosmology and Molecules

`experiments/cassi_two_fluid_3d.py` extends the 2D incompressible Yang/Yin model
to three dimensions and adds a chemotactic drift term so that Yin actively
moves toward information-potential wells.

## Equations

Incompressible velocity field:

$$
\partial_t \mathbf{u} + (\mathbf{u}\cdot\nabla)\mathbf{u}
= -\nabla p + \nu\nabla^2\mathbf{u} + \Pi\,\nabla\Phi,
\qquad \nabla\cdot\mathbf{u}=0.
$$

Information potential:

$$
\nabla^2 \Phi = \rho + \rho_{\rm ext} - \bar\rho,
\qquad \rho = E_Y + E_I.
$$

Scalar fields with chemotactic drift:

$$
\partial_t E_Y + \mathbf{u}\cdot\nabla E_Y
= D\nabla^2 E_Y - \lambda(E_Y - \varphi E_I)
- \nabla\cdot\!\left(\frac{\chi}{\varphi} E_Y \nabla\Phi\right),
$$

$$
\partial_t E_I + \mathbf{u}\cdot\nabla E_I
= D\nabla^2 E_I + \lambda(E_Y - \varphi E_I)
+ \nabla\cdot\!\left(\chi E_I \nabla\Phi\right).
$$

The Yin mobility ($\chi$) is larger than the Yang mobility ($\chi/\varphi$),
so net mass accumulates in information-potential minima. This produces the same
gravitational collapse seen in the cosmological bridge, while the Yang-Yin
pressure term $\Pi\nabla\Phi$ generates vorticity.

## Modes

- **cosmos**: no external charge ($\rho_{\rm ext}=0$). Random initial density
  perturbations grow into filaments and knots as Yin collapses and Yang fills
  voids.
- **molecule**: fixed Gaussian nuclear wells ($\rho_{\rm ext}>0$). Yin density
  accumulates at the nuclei, reproducing the qualitative shape of an electron
  density around two protons.

## Numerics

3D Fourier pseudospectral Heun (RK2) method with the 2/3 dealiasing rule. The
velocity field is projected to be divergence-free in Fourier space at every
stage.

## GPU implementation

`experiments/cassi_two_fluid_3d_gpu.py` is a PyTorch/ROCm port of the same
solver. All state arrays live on the GPU and only diagnostics move to the host.

Benchmarks on the RX 7900 XTX:

| Grid | Time per step (GPU) |
|---|---:|
| 64³ | ~0.011 s |
| 128³ | ~0.068 s |
| 256³ | ~0.96 s |

This is roughly **20–30× faster** than the NumPy CPU version at the same grid,
making 128³ and even 256³ production runs feasible on a single GPU.

A 256³ cosmology box was run to t=0.2 and reached δ_rms=0.210 with clear
small-scale power amplification.

GPU outputs:

- `docs/figures/cassi_two_fluid_3d_gpu_cosmos_N128.png`
- `docs/figures/cassi_two_fluid_3d_gpu_molecule_N128.png`
- `docs/figures/cassi_two_fluid_3d_gpu_molecule_cut_N128.png`
- `docs/figures/cassi_two_fluid_3d_gpu_benchmark.png`
- `docs/cassi-two-fluid-3d-gpu-benchmark.md`

## CPU outputs

- `docs/figures/cassi_two_fluid_3d_cosmos.png`
- `docs/figures/cassi_two_fluid_3d_molecule.png`
- `docs/figures/cassi_two_fluid_3d_molecule_cut.png`
- `docs/cassi-two-fluid-3d-results.md`

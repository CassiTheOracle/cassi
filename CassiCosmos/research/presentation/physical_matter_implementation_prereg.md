# Conditional physical matter implementation verification

## Status: REVISION 2 FROZEN BEFORE QUALIFYING GPU OR SCIENTIFIC RUNS—September 10, 2026

Revision 1 specified six Cartesian ordinates and referred to a superseded four-million-particle production setup. Three CPU generator runs occurred while the unit conversion and angular amendment were being resolved; `_diag/physical_matter/pre_revision2_reference_runs.json` preserves their observed hashes and classifies them as nonqualifying. Revision 2 fixes the free-free cgs-to-SI density conversion, uses the positive-weight Lebedev-26 degree-7 quadrature, and binds the production gate to the current 2,500,000-particle `scenes/main.tscn`. No Revision 2 qualifying run precedes this freeze.

## Scope

This schedule implements the conditional compressible radiative-plasma system qualified by `CassiTheory/turbulence/compressible-radiative-plasma-closure.md` and the frozen executions under `CassiTheory/runs/compressible_radiative_plasma_frozen_execution_final/` and `CassiTheory/runs/compressible_radiative_plasma_integrity_frozen_execution_final/`.

The implementation is a conventional hydrogen-plasma completion coupled to the live Cassi particle mass, position, velocity, and gravitational acceleration. It is not a derivation of atomic identity from the Yang/Yin field. The source publication must report `source_kind = conditional_hydrogen_plasma` and retain the hashes of its model, unit map, frequency grid, and atomic-data bundle.

The existing Cassi particle/field solver remains authoritative for collisionless dynamics. Physical-matter mode adds one conservative Eulerian gas/radiation state and maps its gravitational acceleration from the accepted particle step. The mode is additive and default-off. With the mode off, no new GPU resources are allocated and existing solver and rendering paths remain byte-identical where existing parity checks apply.

## Frozen model

### Material state

A finite Cartesian volume stores conserved baryonic mass density, momentum density, total material energy density, hydrogen ion density, and excited neutral populations. The equation of state is an ideal monatomic H/H+ gas with explicit ionization and excitation reservoirs. Pressure and temperature are recovered from thermal energy after subtracting kinetic, ionization, and excitation energy.

The initial Eulerian state is produced by one deterministic trilinear particle scatter. Particle mass and momentum are conserved by normalized cell weights. Every occupied cell receives the same bounded initial specific thermal energy set by `initial_temperature_K`; no density, temperature, composition, or luminosity is inferred from Cassi amplitudes.

### Hydrodynamics

The material update uses a dimensionally split finite-volume Euler method with HLLC face fluxes, monotonized-central primitive reconstruction, a positivity-preserving first-order fallback, and open outflow boundaries. The CFL step is bounded by the local sound speed, bulk velocity, radiation propagation speed, ionization timescale, and configured Cassi step duration.

Cassi gravitational acceleration is deposited to the material volume with the same particle weights as mass and momentum. The source update pairs material momentum work with total material energy. Self-gravity is not recomputed by this module.

### Hydrogen kinetics and emission

The atomic model includes H I ground state, H II continuum, and levels n=2 through n=6. It uses explicit statistical-equilibrium rate matrices for electron-impact excitation/de-excitation, radiative bound-bound decay, collisional ionization, radiative recombination, and photoionization. Atomic constants and rate fits are external conventional inputs in a hash-bound generated bundle.

The emitted spectrum includes free-free continuum, free-bound recombination continuum, two-photon continuum, and every permitted bound-bound transition among n=2 through n=6. Each line deposits into neighboring frequency groups by normalized overlap with a Doppler-plus-natural profile. Emission removes the same energy from material thermal energy. Absorption and stimulated terms deposit the same signed energy into material. Ionization and recombination update the chemical energy reservoir, not an untracked sink.

### Radiation transport

Twenty-four radiation groups cover 1e12 through 1e18 Hz, with explicit edges around the Balmer and Lyman series limits and the strongest n<=6 lines. A positive-weight Lebedev-26 degree-7 quadrature carries group-integrated intensity and resolves non-axis-aligned as well as crossing beams. Transport is finite-volume upwind with reduced light speed, open escape boundaries, and no periodic wrap. Emission is isotropic under the same quadrature weights. Absorption, photoionization, and Thomson scattering are local source terms. Radiation force and work are applied with equal and opposite material momentum and energy changes.

The moving-medium operator is first order in v/c: Doppler group transfer is conservative over internal group faces; frequency-space boundary losses enter low- and high-frequency escape ledgers. Aberration is represented by a conservative 26-ordinate angular remap. The implementation must reject velocities outside its declared v/c domain rather than silently clipping them.

### Observation

Physical rendering consumes only published material and radiation state. It performs camera-ray formal transfer using cell emissivity and opacity, preserving linear CIE XYZ before display mapping. Exposure, white balance, optics, and cadence remain observation controls. Particle sprites may remain as a diagnostic overlay but are not the physical source image.

## Frozen gates

### PM-G0 — default-off parity

With physical matter disabled:

- initialization reports no physical-matter allocations;
- the accepted particle-state bytes for a fixed seed and step sequence equal the pre-feature result;
- existing Scientific, Observatory, and Cinematic publications retain their current mode names and source contracts.

Any difference is `FAIL`.

### PM-G1 — model identity and unit closure

The generated bundle must validate:

- positive finite length, time, mass, energy, temperature, and luminosity scales;
- c, h, k_B, m_H, m_e, e, sigma_T, and atomic energy differences agree with their declared SI values to relative error <= 2e-12;
- frequency edges are strictly increasing and every named line lies in exactly one closed-open group except the final closed upper edge;
- model, unit-map, group-layout, atomic-bundle, source-file, and reference-receipt SHA-256 identities match.

Any mismatch is `FAIL` before GPU mutation.

### PM-G2 — conservative particle initialization

For fixed 8-, 257-, and 4096-particle fixtures, including particles on faces and corners:

- relative mass error <= 2e-6;
- each momentum-component relative error <= 3e-6, or absolute error <= 3e-8 of total mass times the configured velocity scale;
- no occupied cell has nonfinite or nonpositive mass, volume, or recovered internal energy;
- repeating initialization is byte-identical.

Any violation is `FAIL`.

### PM-G3 — hydrodynamic constitutive cases

Compare GPU volume updates with the frozen CPU oracle:

- uniform flow: maximum normalized state error <= 3e-5 and no interior change beyond roundoff;
- Sod shock tube at 128 cells: L1 density error <= 0.035, pressure error <= 0.045, shock and contact positions within two cells of the CPU HLLC reference;
- three-dimensional periodic-free advection pulse: total mass relative error <= 5e-6 and center displacement within 0.75 cell;
- hydrostatic source balance fixture: momentum drift <= 2e-4 of the characteristic momentum over 64 substeps;
- all conserved and primitive channels remain finite and positive where positivity is required.

Any violation is `FAIL`.

### PM-G4 — atomic and emissivity cases

At 100 K, 3,000 K, 10,000 K, and 100,000 K over the frozen density set:

- EOS pressure and recovered temperature relative error <= 2e-5;
- equilibrium ion fraction absolute error <= 3e-4 against the CPU rate solve;
- each resolved line and continuum-group emissivity relative error <= 8e-3 where the reference exceeds 1e-12 of bolometric power;
- bolometric emitted power relative error <= 2e-3;
- every transition conserves population to absolute error <= 3e-6 and paired material-plus-radiation energy to relative error <= 3e-5.

No fitted display colour is an input. Any violation is `FAIL`.

The PM-G4 atomic comparison is a declared post-step source oracle, not an LTE
echo. Each thermo case retains its LTE/Saha/Boltzmann fields as the packed old
state and also freezes one source-enabled implicit rate step with
`dt_sim = 1e-3`, `time_s_per_sim = 1e-4`, zero radiation energy in every
frequency group, and no photoionization or line absorption. The independent CPU
counterpart uses the case temperature and density, hash-bound collisional tables
with log-temperature interpolation of the deexcitation direction plus detailed
balance for excitation, radiative bound-bound down rates (including the
Ly-alpha 0.75/0.25 two-photon branch), collisional ionization, branch-normalized
recombination, normalized seven-state backward Euler, and the packed thermal
reservoir chemical-energy limiter. GPU comparisons consume the corresponding
post-step populations, ion fraction, temperature, pressure, per-group
emissivities, and bolometric emissivity; the model records the controls and
limiter metadata per case. The frozen chemical-energy convention is limited to
the registered hydrogen excitation/ionization reservoir and does not claim a
complete chemical network.

### PM-G5 — stationary transport

Use empty, homogeneous absorbing, homogeneous emitting, front/inside/behind, and opposed-beam fixtures:

- vacuum beam crossing position within one cell;
- Beer-Lambert intensity relative error <= 1.5e-2 for optical depths 0.1, 1, and 10;
- homogeneous slab source-function intensity relative error <= 2e-2;
- crossing beams retain distinct ordinate populations and total energy relative error <= 8e-5 before escape;
- escaped energy plus retained radiation plus material exchange closes to relative error <= 8e-5.

Any violation is `FAIL`.

### PM-G6 — moving transport

For expansion, compression, transverse-flow, and opposed-moving-beam fixtures with |v|/c_reduced <= 0.02:

- internal frequency remap conserves radiation energy to relative error <= 8e-5 before boundary escape and work exchange;
- red/blue centroid shift differs from the CPU first-order oracle by <= 0.35 group width;
- angular first moment differs from the CPU aberration oracle by <= 2e-2;
- low/high frequency escape ledgers are finite, nonnegative, and close the total energy balance;
- the engine rejects |v|/c_reduced > 0.05 without mutating state.

Any violation is `FAIL`.

### PM-G7 — coupled conservation and lifecycle

Across 256 accepted substeps of a radiating, self-moving cloud:

- baryonic mass relative drift <= 8e-6 after accounting for outflow;
- each component of material plus radiation momentum closes to <= 2e-4 of characteristic total momentum after accounting for gravity impulse and escape;
- material total plus radiation plus gravitational work plus every escape ledger closes to relative drift <= 3e-4;
- checkpoint/restore continuation is byte-identical to uninterrupted execution for the complete material, population, ordinate-radiation, ledgers, counters, unit identity, and physical time;
- malformed, fractional-identity, mismatched-hash, nonfinite, negative-positive-channel, and truncated checkpoints reject before GPU mutation;
- shutdown followed by prepare begins from fresh identities and reproduces the initial checkpoint.

Any violation is `FAIL`.

### PM-G8 — physical observation

For the frozen blackbody, line-cloud, absorbing-shell, and mixed-temperature fixtures:

- preserved linear XYZ relative error <= 1e-2 where components exceed 1e-8 of scene luminance;
- CIEDE2000 <= 1.0 for resolved nonblack comparison patches;
- line centroids lie within one display-spectrum sample of the CPU ray-transfer result;
- doubling path length in the optically thin case doubles radiance to relative error <= 2e-2;
- optically thick intensity approaches the source function within 3e-2;
- changing display exposure or white balance leaves solver and raw XYZ bytes unchanged.

Any violation is `FAIL`.

### PM-G9 — live production acceptance

Run the production scene with the configured 2,500,000-particle setup in `scenes/main.tscn` and physical matter enabled. After warm-up:

- at least 256 physical substeps complete without runtime, shader, device-loss, nonfinite-state, or positivity errors;
- physical time and accepted-step counters advance only after the renderer fence;
- the source publication reports all required identities, conservation ledgers, state epochs, and measured update/readback times;
- physical observation produces finite nonblack XYZ pixels from the live state and changes after a controlled compression or heating event;
- no CPU per-particle readback occurs after initialization; recurring readback is bounded to telemetry, checkpoints on request, and captured images;
- particle motion, camera motion, display cadence, and capture cadence cannot advance the physical solver independently.

Any violation is `FAIL`.

### PM-G10 — performance and degradation

At production scale, measure—not infer—GPU update time, renderer time, allocation bytes, and cadence. The mode may reduce physical update cadence or observation resolution, but may not drop accepted substeps, disable a physical term, change frequency/angle counts, or substitute an artistic source. If the measured production configuration cannot sustain an interactive camera while completing physical updates, report `FAIL`; do not loosen this gate after observing results.

### PM-G11 — complete battery

After PM-G0 through PM-G10 pass, run the configured CassiCosmos GPU battery. Every authoritative arm must pass. A flaky or unrelated failure is investigated and rerun only under the repository battery policy; no existing threshold is changed for this feature.

## Decision tree

1. A missing qualified external atomic constant or rate source is `INCONCLUSIVE`; add no placeholder coefficient.
2. A shader/import/runtime/device failure is `FAIL`.
3. A conservation, positivity, identity, lifecycle, transport, spectral, or observation gate failure is `FAIL`.
4. A failed gate ends that run. Correct the implementation, preserve the failed receipt, and rerun the unchanged fixture and threshold.
5. The complete mode is `PASS` only when PM-G0 through PM-G11 pass.

## Evidence retention

Each run writes a JSON receipt under `res://_diag/physical_matter/` with input identities, controls, seed, device, shader identity, measured tolerances, ledgers, timings, and verdict. Frozen CPU-oracle arrays and generated physical bundles live under `research/presentation/reference/`; generated runtime sidecars remain ignored. Production images remain diagnostic artifacts and never replace numeric XYZ receipts.

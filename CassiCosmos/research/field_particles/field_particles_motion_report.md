# Moving Field Particles Report

## Status: Registered attempt FAIL; separated-pair recovery PASS—September 3, 2026

## 1. Registered attempt

`field_particles_motion_prereg.md` registered two unscaled copies of the pinned
localized field with centers five cells from the origin. The measured single
object has RMS radius `1.6314313`; the registered center separation is only
`2.8571429`. Because that is less than two measured radii (`3.2628626`), the
registered construction does not provide two separated catalog cores. The GPU
motion run was stopped before execution.

## 2. Fixture diagnostics

A non-registered builder diagnostic narrowed each profile by `1.5`, rescaled
carrier amplitude by $1.5^{3/2}$, and placed the centers at $x=\pm1.5$. It
produced total serialized charge `3.009228599519`, inconsistent with the
intended two charge-4 copies. Adding relative phases $-\pi/4$ and $+\pi/4$
produced `2.888155155129`. Neither diagnostic was loaded by the runtime or used
as production evidence.

## 3. Registered verdict

**FAIL—FIXTURE CONSTRUCTION.** The registered overlapping construction and the
two diagnostic fixtures do not qualify as moving multi-object initialization.

## 4. Separated-pair recovery

`field_particles_separated_pair_prereg.md` froze a non-overlapping construction
before GPU execution. It embeds two exact copies of the pinned particle on an
$N=57$ grid, centered at $x=-4$ and $x=+4$, with equal and opposite speed
$0.25$. The independent builder measured charge `3.999999962481` in each copy
and `7.999999882947` in the combined field.

The frozen production scene `verify_field_particles_motion.tscn` exited `0`
after 32 field steps. Its catalog contained two objects before and after the
run. The left object moved `+0.074723`, the right object moved `-0.075825`, and
catalog charge retention was `1.000000`. Deposit, KDK, accretion, merge, site,
tree, rotation, and gravity paths remained unused. The complete
`13,333,896`-byte state and `11,852,352`-byte velocity were present in the
runtime snapshot.
The renderer received separate draw origins at `-3.980988` and `+3.980907`.
Two direct window captures showed both objects and their inward movement.

## 5. Recovery verdict

**PASS—SEPARATED MOVING FIELD PARTICLES.** The public setting now starts from
two independently cataloged field objects with measured motion in opposite
directions. The registered overlapping attempt remains a failed construction.

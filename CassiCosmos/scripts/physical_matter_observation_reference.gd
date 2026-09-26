extends RefCounted
class_name PhysicalMatterObservationReference
## CPU reference for the physical-matter camera formal solution.
##
## The returned formal_rgba image is raw CIE XYZ plus a valid channel.  The
## renderer's physical-volume shader writes the same raw XYZ to raw_xyz and
## separately writes clipped linear sRGB to display_radiance; xyz_to_display()
## mirrors that latter mapping.  The shader's first_depth image is not returned
## because this API is intentionally the four-channel XYZ/valid reference.
##
## The fixture API has no population1, Thomson coefficient, or mean-intensity
## input.  It therefore represents the homogeneous no-incoming-scattering
## fixture: scattering_full and scatter_source are zero.  The omitted source
## pre-pass would otherwise do (compute/cassi_physical_observer_source.glsl:
## 40-48):
##   angular_integral += max(ordinate[angle].w, 0.0)
##       * max(radiation[base + angle], 0.0);
##   mean = angular_integral * INV_FOUR_PI;
## The pre-pass is intentionally not reproduced here, and neither is the
## main-pass scatter_source term (compute/cassi_physical_volume.glsl:118-133).
##
## formal_rgba also returns the raw XYZ channels rather than the physical
## shader's separately written display_radiance channels.  This follows the
## requested [X,Y,Z,valid] contract and keeps display conversion explicit.

const FOUR_PI: float = 12.566370614359172
const MAX_GROUPS: int = 64
const MAX_VISIBLE_GROUPS: int = 16

# CIE 1931 2-degree D65 reference white, in the usual Y=1 normalization.
# The Lab piecewise curve uses the CIE constants epsilon=(6/29)^3 and
# kappa=(29/3)^3, written here in their decimal forms for shader/reference
# parity.
const D65_WHITE: Vector3 = Vector3(0.95047, 1.0, 1.08883)
const LAB_EPSILON: float = 0.008856451679035631
const LAB_KAPPA: float = 903.2962962962963


# Mirrors compute/cassi_physical_volume.glsl:45-48.
static func _safe_inverse(value: float) -> float:
	if absf(value) > 1.0e-8:
		return 1.0 / value
	return -1.0e8 if value < 0.0 else 1.0e8


# Mirrors compute/cassi_physical_volume.glsl:50-60.
static func _box_interval(origin: Vector3, direction: Vector3,
		center: Vector3, extents: Vector3) -> Vector2:
	var lower := center - extents
	var upper := center + extents
	var inverse_x := _safe_inverse(direction.x)
	var inverse_y := _safe_inverse(direction.y)
	var inverse_z := _safe_inverse(direction.z)
	var ax := (lower.x - origin.x) * inverse_x
	var ay := (lower.y - origin.y) * inverse_y
	var az := (lower.z - origin.z) * inverse_z
	var bx := (upper.x - origin.x) * inverse_x
	var by := (upper.y - origin.y) * inverse_y
	var bz := (upper.z - origin.z) * inverse_z
	var lo_x := minf(ax, bx)
	var lo_y := minf(ay, by)
	var lo_z := minf(az, bz)
	var hi_x := maxf(ax, bx)
	var hi_y := maxf(ay, by)
	var hi_z := maxf(az, bz)
	return Vector2(maxf(lo_x, maxf(lo_y, lo_z)),
			minf(hi_x, minf(hi_y, hi_z)))


# Mirrors compute/cassi_physical_volume.glsl:62-69.  The lower corner and
# denominator are precomputed by formal_rgba so this helper only computes the
# integer cell coordinate for one march sample.
static func _cell_index(position: Vector3, lower: Vector3, span: Vector3,
		dx: int, dy: int, dz: int) -> int:
	var normalized_x := (position.x - lower.x) / span.x
	var normalized_y := (position.y - lower.y) / span.y
	var normalized_z := (position.z - lower.z) / span.z
	var coordinate_x := clampi(int(floor(normalized_x * float(dx))), 0, dx - 1)
	var coordinate_y := clampi(int(floor(normalized_y * float(dy))), 0, dy - 1)
	var coordinate_z := clampi(int(floor(normalized_z * float(dz))), 0, dz - 1)
	return coordinate_x + dx * (coordinate_y + dy * coordinate_z)


# Mirrors compute/cassi_physical_volume.glsl:71-74.
static func _one_minus_exp_negative(tau: float) -> float:
	if tau < 1.0e-4:
		return tau * (1.0 - 0.5 * tau + tau * tau / 6.0)
	return 1.0 - exp(-minf(tau, 80.0))


static func _finite3(value: Vector3) -> bool:
	return is_finite(value.x) and is_finite(value.y) and is_finite(value.z)


static func _nonnegative_finite(value: float) -> float:
	if not is_finite(value):
		return NAN
	return maxf(value, 0.0)


# Mirrors compute/cassi_physical_volume.glsl:37-43.  cassi_physical_volume.gd
# pushes -camera.basis.z as camera_forward (lines 117-120), so this helper uses
# the same camera convention for the supplied Basis.
static func _ray_direction(ndc: Vector2, camera_basis: Basis,
		fov_radians: float, width: int, height: int) -> Vector3:
	var aspect := maxf(float(width), 1.0) / maxf(float(height), 1.0)
	var tangent := tan(0.5 * maxf(fov_radians, 0.001))
	var direction := -camera_basis.z \
			+ camera_basis.x * (ndc.x * aspect * tangent) \
			+ camera_basis.y * (ndc.y * tangent)
	var length := direction.length()
	if not is_finite(length) or length <= 1.0e-30:
		return Vector3.ZERO
	return direction / length


# The matrix literal in compute/cassi_physical_volume.glsl:76-81 is GLSL
# column-major.  Consequently its scalar output rows are:
#   R = 3.2406 X - 1.5372 Y - 0.4986 Z
#   G = -0.9689 X + 1.8758 Y + 0.0415 Z
#   B = 0.0557 X - 0.2040 Y + 1.0570 Z
# The shader then performs exactly the clipping/finite handling below at
# compute/cassi_physical_volume.glsl:152-154.
#
# exposure_ev is deliberately unused: the physical-volume shader has no
# exposure field in its push constants and does not apply exposure here.
# Exposure is a later renderer-owned post-bloom operation (the separate
# compute/cassi_observatory_post_bloom.glsl:33-35).  Keeping this argument in
# the CPU API makes the observation call site explicit without changing the
# formal or raw XYZ reference.
static func xyz_to_display(xyz: Vector3, exposure_ev: float) -> Vector3:
	var linear_rgb := Vector3(
			3.2406 * xyz.x - 1.5372 * xyz.y - 0.4986 * xyz.z,
			-0.9689 * xyz.x + 1.8758 * xyz.y + 0.0415 * xyz.z,
			0.0557 * xyz.x - 0.2040 * xyz.y + 1.0570 * xyz.z)
	linear_rgb = Vector3(maxf(linear_rgb.x, 0.0), maxf(linear_rgb.y, 0.0),
			maxf(linear_rgb.z, 0.0))
	if not _finite3(linear_rgb):
		return Vector3.ZERO
	return linear_rgb


## CPU formal solution for the axis-aligned box.
##
## opacity and emission are laid out as cell * groups + source_group, exactly
## as the shader's opacity_group[] and emission_group[] buffers.  Every
## visible_group_weights record is [X weight, Y weight, Z weight, source_group]
## as bound by cassi_physical_volume.gd:_ensure_uniform_set() (lines 325-330).
## The output layout is [X, Y, Z, valid] per pixel, row-major in pixel y then x.
static func formal_rgba(grid: Vector3i, extents: Vector3, center: Vector3,
		opacity: PackedFloat32Array, emission: PackedFloat32Array, groups: int,
		visible_group_weights: PackedFloat32Array, camera_origin: Vector3,
		camera_basis: Basis, fov_degrees: float, near_plane: float,
		render_size: Vector2i, optical_scale: float, emission_scale: float,
		c_reduced_sim: float, march_steps: int) -> PackedFloat32Array:
	var output := PackedFloat32Array()
	if render_size.x <= 0 or render_size.y <= 0:
		return output
	var width := render_size.x
	var height := render_size.y
	output.resize(width * height * 4)

	# Mirrors compute/cassi_physical_volume.glsl:103-107.  The engine pushes
	# integer grid/group values, while the shader rounds and clamps them.
	var dx := maxi(grid.x, 1)
	var dy := maxi(grid.y, 1)
	var dz := maxi(grid.z, 1)
	var group_count := clampi(groups, 1, MAX_GROUPS)
	var visible_count := clampi(visible_group_weights.size() / 4, 0,
			MAX_VISIBLE_GROUPS)
	var steps := clampi(march_steps, 1, 192)

	# Mirrors the shader's max(2.0 * pc.volume_extents, vec3(1.0e-8)) in
	# cell_index().  These values are invariant for every pixel/sample.
	var lower := center - extents
	var span := Vector3(maxf(2.0 * extents.x, 1.0e-8),
			maxf(2.0 * extents.y, 1.0e-8), maxf(2.0 * extents.z, 1.0e-8))

	# visible_group[] is bounded to MAX_VISIBLE_GROUPS by the renderer.  Pull
	# its source indices and nonnegative XYZ weights out once, before the pixel
	# loops, so the inner march loop only performs scalar arithmetic.
	var source_groups := PackedInt32Array()
	source_groups.resize(visible_count)
	var weight_x := PackedFloat32Array()
	var weight_y := PackedFloat32Array()
	var weight_z := PackedFloat32Array()
	weight_x.resize(visible_count)
	weight_y.resize(visible_count)
	weight_z.resize(visible_count)
	for visible_index in range(visible_count):
		var weight_offset := visible_index * 4
		var source_group_value := float(visible_group_weights[weight_offset + 3])
		var source_group := 0
		if is_finite(source_group_value):
			source_group = clampi(int(maxf(source_group_value, 0.0) + 0.5),
				0, group_count - 1)
		source_groups[visible_index] = source_group
		var wx := float(visible_group_weights[weight_offset])
		var wy := float(visible_group_weights[weight_offset + 1])
		var wz := float(visible_group_weights[weight_offset + 2])
		weight_x[visible_index] = _nonnegative_finite(wx)
		weight_y[visible_index] = _nonnegative_finite(wy)
		weight_z[visible_index] = _nonnegative_finite(wz)

	var cell_count := dx * dy * dz
	var coefficient_count := cell_count * visible_count
	var extinction_coefficients := PackedFloat32Array()
	var source_coefficients := PackedFloat32Array()
	extinction_coefficients.resize(coefficient_count)
	source_coefficients.resize(coefficient_count)
	var optical_factor := maxf(optical_scale, 0.0)
	var emission_factor := maxf(emission_scale, 0.0)
	var speed := maxf(c_reduced_sim, 1.0e-20)
	# Mirrors compute/cassi_physical_volume.glsl:118-135 for a homogeneous
	# no-scattering fixture.  The full shader computes:
	#   scattering_full = max(population1[cell].z, 0.0)
	#       * max(pc.thomson_per_population, 0.0);
	#   absorption = max(tabulated_extinction - scattering_full, 0.0);
	#   extinction = (absorption + scattering_full)
	#       * max(pc.optical_scale, 0.0);
	#   true_source = max(emission_group[source_index], 0.0)
	#       * max(pc.emission_scale, 0.0)
	#       / (FOUR_PI * max(pc.c_reduced_sim, 1.0e-20));
	#   scatter_source = scattering_full * max(pc.optical_scale, 0.0)
	#       * max(mean_intensity[cell * uint(visible)
	#           + uint(visible_index)], 0.0);
	# With the omitted scattering inputs, scattering_full=0, so the tabulated
	# opacity is the extinction used below and true_source is exactly the
	# stated emission expression.

	for cell in range(cell_count):
		for visible_index in range(visible_count):
			var source_group := source_groups[visible_index]
			var source_index := cell * group_count + source_group
			var tabulated_extinction := 0.0
			var tabulated_emission := 0.0
			if source_index >= 0 and source_index < opacity.size():
				tabulated_extinction = _nonnegative_finite(float(opacity[source_index]))
			if source_index >= 0 and source_index < emission.size():
				tabulated_emission = _nonnegative_finite(float(emission[source_index]))
			var coefficient_index := cell * visible_count + visible_index
			extinction_coefficients[coefficient_index] = tabulated_extinction * optical_factor
			source_coefficients[coefficient_index] = tabulated_emission * emission_factor \
					/ (FOUR_PI * speed)

	var fov_radians := deg_to_rad(clampf(fov_degrees, 1.0, 179.0))
	var optical_near := maxf(near_plane, 0.0)
	var intensity := PackedFloat32Array()
	intensity.resize(visible_count)

	for pixel_y in range(height):
		for pixel_x in range(width):
			var output_index := (pixel_y * width + pixel_x) * 4
			# The shader writes alpha=1.0 for both a hit and the explicit miss
			# path (compute/cassi_physical_volume.glsl:96-100, 154-156).
			output[output_index] = 0.0
			output[output_index + 1] = 0.0
			output[output_index + 2] = 0.0
			output[output_index + 3] = 1.0

			var uv_x := (float(pixel_x) + 0.5) / float(width)
			var uv_y := (float(pixel_y) + 0.5) / float(height)
			var ndc := Vector2(uv_x * 2.0 - 1.0, 1.0 - uv_y * 2.0)
			var direction := _ray_direction(ndc, camera_basis, fov_radians, width, height)
			var interval := _box_interval(camera_origin, direction, center, extents)
			var begin := maxf(interval.x, optical_near)
			var end := interval.y
			# Mirrors compute/cassi_physical_volume.glsl:94-100.  The output was
			# already initialized to XYZ=0,valid=1 above.
			if not (end > begin) or not is_finite(begin) or not is_finite(end):
				continue

			var ds := (end - begin) / float(steps)
			intensity.fill(0.0)
			# Mirrors compute/cassi_physical_volume.glsl:112-146.  The march is
			# far boundary toward the camera and each visible group retains its
			# own attenuation before XYZ projection.
			for sample_index in range(steps):
				var distance := end - (float(sample_index) + 0.5) * ds
				var sample_position := camera_origin + direction * distance
				var cell := _cell_index(sample_position, lower, span, dx, dy, dz)
				var coefficient_base := cell * visible_count
				for visible_index in range(visible_count):
					var coefficient_index := coefficient_base + visible_index
					var extinction := extinction_coefficients[coefficient_index]
					var source_per_length := source_coefficients[coefficient_index]
					# Mirrors compute/cassi_physical_volume.glsl:134-135.
					if not is_finite(extinction) or not is_finite(source_per_length):
						continue
					var tau := extinction * ds
					var transmission := exp(-minf(tau, 80.0))
					# Exact shader accumulation, compute/cassi_physical_volume.glsl:
					# 136-142:
					#   float tau = extinction * ds;
					#   float transmission = exp(-min(tau, 80.0));
					#   float source_per_length = true_source + scatter_source;
					#   float emitted = extinction > 1.0e-30
					#       ? (source_per_length / extinction)
					#           * one_minus_exp_negative(tau)
					#       : source_per_length * ds;
					#   intensity[visible_index] = intensity[visible_index]
					#       * transmission + emitted;
					var emitted := (source_per_length / extinction) \
							* _one_minus_exp_negative(tau) \
							if extinction > 1.0e-30 \
							else source_per_length * ds
					intensity[visible_index] = intensity[visible_index] \
							* transmission + emitted

			var xyz_x := 0.0
			var xyz_y := 0.0
			var xyz_z := 0.0
			for visible_index in range(visible_count):
				var value := intensity[visible_index]
				xyz_x += value * weight_x[visible_index]
				xyz_y += value * weight_y[visible_index]
				xyz_z += value * weight_z[visible_index]
			# Mirrors compute/cassi_physical_volume.glsl:148-151.  This is the
			# raw XYZ image contract; xyz_to_display() is a separate mapping.
			if not is_finite(xyz_x) or not is_finite(xyz_y) \
					or not is_finite(xyz_z) or xyz_x < 0.0 \
					or xyz_y < 0.0 or xyz_z < 0.0:
				xyz_x = 0.0
				xyz_y = 0.0
				xyz_z = 0.0
			output[output_index] = xyz_x
			output[output_index + 1] = xyz_y
			output[output_index + 2] = xyz_z

	return output


# CIE Lab forward transform using the D65 constants documented above.
static func _lab_curve(value: float) -> float:
	if value > LAB_EPSILON:
		return pow(value, 1.0 / 3.0)
	return (LAB_KAPPA * value + 16.0) / 116.0


static func _xyz_to_lab(xyz: Vector3) -> Vector3:
	var scaled_x := xyz.x / D65_WHITE.x
	var scaled_y := xyz.y / D65_WHITE.y
	var scaled_z := xyz.z / D65_WHITE.z
	var fx := _lab_curve(scaled_x)
	var fy := _lab_curve(scaled_y)
	var fz := _lab_curve(scaled_z)
	return Vector3(116.0 * fy - 16.0, 500.0 * (fx - fy),
			200.0 * (fy - fz))


static func _hue_degrees(a_value: float, b_value: float) -> float:
	var hue := rad_to_deg(atan2(b_value, a_value))
	if hue < 0.0:
		hue += 360.0
	return hue


## Sharma, Wu & Dalal, Color Research and Application 30(1) (2005),
## equations 1-12, with k_L=k_C=k_H=1.  Inputs are XYZ and are converted to
## Lab with the D65 white point above before applying CIEDE2000.
static func ciede2000(first: Vector3, second: Vector3) -> float:
	if not _finite3(first) or not _finite3(second):
		return NAN
	var first_lab := _xyz_to_lab(first)
	var second_lab := _xyz_to_lab(second)
	var l1 := first_lab.x
	var a1 := first_lab.y
	var b1 := first_lab.z
	var l2 := second_lab.x
	var a2 := second_lab.y
	var b2 := second_lab.z

	var c1 := sqrt(a1 * a1 + b1 * b1)
	var c2 := sqrt(a2 * a2 + b2 * b2)
	var c_bar := 0.5 * (c1 + c2)
	var c_bar_7 := pow(c_bar, 7.0)
	var twenty_five_7 := pow(25.0, 7.0)
	var g := 0.5 * (1.0 - sqrt(c_bar_7 / (c_bar_7 + twenty_five_7)))
	var a1_prime := (1.0 + g) * a1
	var a2_prime := (1.0 + g) * a2
	var c1_prime := sqrt(a1_prime * a1_prime + b1 * b1)
	var c2_prime := sqrt(a2_prime * a2_prime + b2 * b2)
	var h1_prime := _hue_degrees(a1_prime, b1)
	var h2_prime := _hue_degrees(a2_prime, b2)

	var delta_l_prime := l2 - l1
	var delta_c_prime := c2_prime - c1_prime
	var delta_h_prime := 0.0
	if c1_prime != 0.0 and c2_prime != 0.0:
		var hue_difference := h2_prime - h1_prime
		if absf(hue_difference) <= 180.0:
			delta_h_prime = hue_difference
		elif hue_difference > 180.0:
			delta_h_prime = hue_difference - 360.0
		else:
			delta_h_prime = hue_difference + 360.0
	var delta_h_term := 2.0 * sqrt(c1_prime * c2_prime) \
			* sin(deg_to_rad(delta_h_prime) * 0.5)
	var l_bar_prime := 0.5 * (l1 + l2)
	var c_bar_prime := 0.5 * (c1_prime + c2_prime)
	var h_bar_prime := 0.0
	if c1_prime == 0.0 or c2_prime == 0.0:
		h_bar_prime = h1_prime + h2_prime
	else:
		var hue_difference := absf(h1_prime - h2_prime)
		if hue_difference <= 180.0:
			h_bar_prime = 0.5 * (h1_prime + h2_prime)
		elif h1_prime + h2_prime < 360.0:
			h_bar_prime = 0.5 * (h1_prime + h2_prime) + 180.0
		else:
			h_bar_prime = 0.5 * (h1_prime + h2_prime) - 180.0

	var t := 1.0 \
			- 0.17 * cos(deg_to_rad(h_bar_prime - 30.0)) \
			+ 0.24 * cos(deg_to_rad(2.0 * h_bar_prime)) \
			+ 0.32 * cos(deg_to_rad(3.0 * h_bar_prime + 6.0)) \
			- 0.20 * cos(deg_to_rad(4.0 * h_bar_prime - 63.0))
	var delta_theta := 30.0 * exp(-pow((h_bar_prime - 275.0) / 25.0, 2.0))
	var r_c := 2.0 * sqrt(pow(c_bar_prime, 7.0) \
			/ (pow(c_bar_prime, 7.0) + twenty_five_7))
	var l_offset := l_bar_prime - 50.0
	var s_l := 1.0 + 0.015 * l_offset * l_offset \
			/ sqrt(20.0 + l_offset * l_offset)
	var s_c := 1.0 + 0.045 * c_bar_prime
	var s_h := 1.0 + 0.015 * c_bar_prime * t
	var r_t := -sin(deg_to_rad(2.0 * delta_theta)) * r_c
	var l_term := delta_l_prime / s_l
	var c_term := delta_c_prime / s_c
	var h_term := delta_h_term / s_h
	var squared := l_term * l_term + c_term * c_term \
			+ h_term * h_term + r_t * c_term * h_term
	if not is_finite(squared):
		return NAN
	return sqrt(maxf(squared, 0.0))


# Inverse Lab helper used only to feed the Sharma et al. Lab test vectors into
# the public XYZ-input ciede2000() API.
static func _lab_inverse_curve(value: float) -> float:
	var cube := value * value * value
	if cube > LAB_EPSILON:
		return cube
	return (116.0 * value - 16.0) / LAB_KAPPA


static func _lab_to_xyz(lab: Vector3) -> Vector3:
	var fy := (lab.x + 16.0) / 116.0
	var fx := fy + lab.y / 500.0
	var fz := fy - lab.z / 200.0
	return Vector3(D65_WHITE.x * _lab_inverse_curve(fx),
			D65_WHITE.y * _lab_inverse_curve(fy),
			D65_WHITE.z * _lab_inverse_curve(fz))


static func _append_check(checks: Array[Dictionary], name: String,
		passed: bool, measured: Variant, expected: Variant,
		tolerance: float, detail: String) -> bool:
	checks.append({
		"name": name,
		"passed": passed,
		"measured": measured,
		"expected": expected,
		"tolerance": tolerance,
		"detail": detail,
	})
	return passed


## Run deterministic CPU-only contract checks.  This function does not create
## or touch a RenderingDevice; callers can run it in a normal script context.
static func self_test() -> Dictionary:
	var checks: Array[Dictionary] = []
	var passed := true
	var unit_box := Vector3(0.5, 0.5, 0.5)
	var camera := Vector3(0.0, 0.0, 2.0)
	var weights := PackedFloat32Array([1.0, 1.0, 1.0, 0.0])

	# Single-step transfer: shader lines 136-142 reduce to
	# S * (1 - exp(-d * tau)) when the incoming intensity is zero.  The unit
	# box has d=1 and opacity=optical_scale=emission_scale=c=1, so S=1.
	var one_step := formal_rgba(Vector3i.ONE, unit_box, Vector3.ZERO,
			PackedFloat32Array([1.0]), PackedFloat32Array([FOUR_PI]), 1,
			weights, camera, Basis.IDENTITY, 1.0, 0.0, Vector2i.ONE, 1.0, 1.0,
			1.0, 1)
	var one_step_expected := 1.0 - exp(-1.0)
	var one_step_value := one_step[0] if one_step.size() >= 4 else NAN
	var one_step_ok := one_step.size() == 4 and is_finite(one_step_value) \
			and absf(one_step_value - one_step_expected) <= 2.0e-6 \
			and absf(one_step[1] - one_step_expected) <= 2.0e-6 \
			and absf(one_step[2] - one_step_expected) <= 2.0e-6 \
			and is_equal_approx(one_step[3], 1.0)
	passed = _append_check(checks, "single_step_analytic_transfer", one_step_ok,
			one_step_value, one_step_expected, 2.0e-6,
			"unit-box d=1, zero incoming intensity") and passed

	# Optically thick limit.  The shader has independent optical_scale and
	# emission_scale uniforms, so this check takes both to the same large value;
	# then true_source/extinction tends to emission/(4*pi*c*opacity), exactly
	# the requested source function.
	var thick_opacity := 0.7
	var thick_emission := 2.5
	var thick_speed := 3.0
	var thick_scale := 256.0
	var thick := formal_rgba(Vector3i.ONE, unit_box, Vector3.ZERO,
			PackedFloat32Array([thick_opacity]), PackedFloat32Array([thick_emission]),
			1, weights, camera, Basis.IDENTITY, 1.0, 0.0, Vector2i.ONE,
			thick_scale, thick_scale, thick_speed, 1)
	var thick_expected := thick_emission / (FOUR_PI * thick_speed * thick_opacity)
	var thick_value := thick[1] if thick.size() >= 4 else NAN
	var thick_ok := thick.size() == 4 and is_finite(thick_value) \
			and absf(thick_value - thick_expected) <= 2.0e-6
	passed = _append_check(checks, "optically_thick_source_function", thick_ok,
			thick_value, thick_expected, 2.0e-6,
			"optical_scale=emission_scale=256; tau is capped only in exp") and passed

	# CIEDE2000 validation vectors from Sharma, Wu & Dalal (2005), Table 1.
	# The published values are Lab pairs; convert them to XYZ with this module's
	# D65 white point before exercising the public XYZ-input API.
	var cie_cases: Array[Dictionary] = [
		{"name": "sharma_01", "first": Vector3(50.0000, 2.6772, -79.7751),
				"second": Vector3(50.0000, 0.0000, -82.7485), "expected": 2.0425},
		{"name": "sharma_02", "first": Vector3(50.0000, 3.1571, -77.2803),
				"second": Vector3(50.0000, 0.0000, -82.7485), "expected": 2.8615},
		{"name": "sharma_03", "first": Vector3(50.0000, 2.8361, -74.0200),
				"second": Vector3(50.0000, 0.0000, -82.7485), "expected": 3.4412},
		{"name": "sharma_04", "first": Vector3(50.0000, -1.3802, -84.2814),
				"second": Vector3(50.0000, 0.0000, -82.7485), "expected": 1.0000},
	]
	for cie_case in cie_cases:
		var first_lab: Vector3 = cie_case["first"]
		var second_lab: Vector3 = cie_case["second"]
		var expected: float = cie_case["expected"]
		var measured := ciede2000(_lab_to_xyz(first_lab), _lab_to_xyz(second_lab))
		var cie_ok := is_finite(measured) and absf(measured - expected) <= 5.0e-4
		passed = _append_check(checks, String(cie_case["name"]), cie_ok,
				measured, expected, 5.0e-4,
				"Sharma et al. (2005) Table 1 CIEDE2000 Lab reference pair") and passed

	# A neutral D65 XYZ ramp must map monotonically through the shader matrix,
	# remain zero at black, and be independent of exposure_ev because the
	# physical-volume pass has no exposure operation.  This is the display-side
	# round-trip/monotonicity contract; exposure is tested by the later post pass.
	var display_magnitudes := [0.0, 0.01, 0.1, 0.5]
	var previous_display := Vector3.ZERO
	var display_ok := true
	for magnitude in display_magnitudes:
		var display_value := xyz_to_display(D65_WHITE * float(magnitude), 0.0)
		display_ok = display_ok and _finite3(display_value) \
				and display_value.x >= previous_display.x \
				and display_value.y >= previous_display.y \
				and display_value.z >= previous_display.z
		previous_display = display_value
	var exposure_a := xyz_to_display(D65_WHITE * 0.2, -12.0)
	var exposure_b := xyz_to_display(D65_WHITE * 0.2, 12.0)
	display_ok = display_ok and exposure_a.distance_to(exposure_b) <= 1.0e-12
	passed = _append_check(checks, "xyz_to_display_round_trip_monotonicity", display_ok,
			previous_display, Vector3.ONE, 1.0e-12,
			"neutral D65 ramp is monotone; exposure argument is shader no-op") and passed

	return {"passed": passed, "checks": checks}

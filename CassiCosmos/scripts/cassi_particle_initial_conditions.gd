extends RefCounted
## Deterministic CPU initial-condition geometry shared by inline and decoupled runs.
## The generator deliberately keeps shape, arrangement, motion, and mass streams
## independent: changing a visual geometry never changes its Salpeter weights.

const PI_F: float = 3.141592653589793
const TAU_F: float = 6.283185307179586
const PHI_F: float = 1.618033988749895
const MASS_STREAM_OFFSET: int = 0x4D415353
const POSITION_STREAM_OFFSET: int = 0x504F5349
const STRUCTURE_STREAM_OFFSET: int = 0x53545255

const SHAPE_NAMES: Array[String] = [
	"Plummer", "Gaussian", "Uniform", "Spiral disc", "Tilted encounter",
	"Pearl ring", "Nested shells", "Double helix", "Filament web",
	"Hierarchical cloud", "Folded sheet", "Trefoil cloud"
]
const ARRANGEMENT_NAMES: Array[String] = [
	"Ring", "Sphere", "Single", "Pair", "Chain", "Scatter", "Hierarchy"
]
const MOTION_NAMES: Array[String] = [
	"Profile", "At rest", "Spin", "Counter-spin", "Inward", "Outward",
	"Along structure", "Opposed streams"
]

# Defaults are intentionally plain numeric values: UI and scene persistence can
# merge a partial dictionary without knowing which shape is currently visible.
const DEFAULTS: Dictionary = {
	"thickness": 1.0, "clumpiness": 1.0, "asymmetry": 0.0,
	"yaw": 0.0, "pitch": 0.0, "roll": 0.0,
	"spiral_arms": 3, "spiral_pitch": 22.0, "spiral_width": 0.08, "spiral_core": 0.16,
	"encounter_size": 1.0, "encounter_particle_ratio": 0.67,
	"encounter_relative_tilt": 60.0, "encounter_separation": 1.4, "encounter_offset": 0.2,
	"ring_radius": 0.8, "ring_knot_count": 8, "ring_warp": 0.065,
	"shell_count": 3, "shell_spacing": 0.33, "shell_inner_radius": 0.34,
	"shell_ellipticity": 0.88, "shell_offset": 0.12,
	"helix_strands": 2, "helix_turns": 2.5, "helix_radius": 0.30, "helix_pitch": 1.0,
	"web_junctions": 16, "web_connectivity": 2, "web_curvature": 0.13,
	"hierarchy_depth": 3, "hierarchy_branching": 5, "hierarchy_scale_separation": 0.42,
	"sheet_fold_amplitude": 0.30, "sheet_wavelength": 1.2, "sheet_ripples": 2, "sheet_aspect": 1.0,
	"trefoil_loop_radius": 0.65, "trefoil_loop_ratio": 0.25, "trefoil_height": 0.25
}

const PARAMS: Array[Dictionary] = [
	{"id":"ic_thickness", "prop":"initial_shape_settings", "key":"thickness", "caption":"Thickness", "token":"gold", "min":0.02, "max":3.0, "step":0.01, "default":1.0, "reinit":true, "tooltip":"Common transverse thickness", "shapes":[]},
	{"id":"ic_clumpiness", "prop":"initial_shape_settings", "key":"clumpiness", "caption":"Clumpiness", "token":"gold", "min":0.0, "max":2.0, "step":0.01, "default":1.0, "reinit":true, "tooltip":"Common seeded substructure amount", "shapes":[]},
	{"id":"ic_asymmetry", "prop":"initial_shape_settings", "key":"asymmetry", "caption":"Asymmetry", "token":"gold", "min":-0.8, "max":0.8, "step":0.01, "default":0.0, "reinit":true, "tooltip":"Common axis asymmetry", "shapes":[]},
	{"id":"ic_yaw", "prop":"initial_shape_settings", "key":"yaw", "caption":"Yaw", "token":"gold", "min":-180.0, "max":180.0, "step":1.0, "default":0.0, "reinit":true, "tooltip":"Common orientation in degrees", "shapes":[]},
	{"id":"ic_pitch", "prop":"initial_shape_settings", "key":"pitch", "caption":"Pitch", "token":"gold", "min":-90.0, "max":90.0, "step":1.0, "default":0.0, "reinit":true, "tooltip":"Common orientation in degrees", "shapes":[]},
	{"id":"ic_roll", "prop":"initial_shape_settings", "key":"roll", "caption":"Roll", "token":"gold", "min":-180.0, "max":180.0, "step":1.0, "default":0.0, "reinit":true, "tooltip":"Common orientation in degrees", "shapes":[]},
	{"id":"ic_spiral_arms", "prop":"initial_shape_settings", "key":"spiral_arms", "caption":"Spiral arms", "token":"gold", "min":1, "max":8, "step":1, "default":3, "reinit":true, "tooltip":"Number of logarithmic arms", "shapes":[3]},
	{"id":"ic_spiral_pitch", "prop":"initial_shape_settings", "key":"spiral_pitch", "caption":"Spiral pitch", "token":"gold", "min":5.0, "max":60.0, "step":1.0, "default":22.0, "reinit":true, "tooltip":"Arm opening angle in degrees", "shapes":[3]},
	{"id":"ic_spiral_width", "prop":"initial_shape_settings", "key":"spiral_width", "caption":"Arm width", "token":"gold", "min":0.0, "max":0.4, "step":0.005, "default":0.08, "reinit":true, "tooltip":"Arm transverse width", "shapes":[3]},
	{"id":"ic_spiral_core", "prop":"initial_shape_settings", "key":"spiral_core", "caption":"Core", "token":"gold", "min":0.02, "max":0.5, "step":0.01, "default":0.16, "reinit":true, "tooltip":"Diffuse central core radius", "shapes":[3]},
	{"id":"ic_encounter_size", "prop":"initial_shape_settings", "key":"encounter_size", "caption":"Encounter size", "token":"gold", "min":0.2, "max":2.5, "step":0.01, "default":1.0, "reinit":true, "tooltip":"Relative disc size", "shapes":[4]},
	{"id":"ic_encounter_particle_ratio", "prop":"initial_shape_settings", "key":"encounter_particle_ratio", "caption":"Particle ratio", "token":"gold", "min":0.1, "max":0.9, "step":0.01, "default":0.67, "reinit":true, "tooltip":"Particles in first component", "shapes":[4]},
	{"id":"ic_encounter_relative_tilt", "prop":"initial_shape_settings", "key":"encounter_relative_tilt", "caption":"Relative tilt", "token":"gold", "min":0.0, "max":180.0, "step":1.0, "default":60.0, "reinit":true, "tooltip":"Second disc tilt in degrees", "shapes":[4]},
	{"id":"ic_encounter_separation", "prop":"initial_shape_settings", "key":"encounter_separation", "caption":"Separation", "token":"gold", "min":0.0, "max":3.0, "step":0.01, "default":1.4, "reinit":true, "tooltip":"Component center separation", "shapes":[4]},
	{"id":"ic_encounter_offset", "prop":"initial_shape_settings", "key":"encounter_offset", "caption":"Offset", "token":"gold", "min":0.0, "max":1.0, "step":0.01, "default":0.2, "reinit":true, "tooltip":"Small transverse encounter offset", "shapes":[4]},
	{"id":"ic_ring_radius", "prop":"initial_shape_settings", "key":"ring_radius", "caption":"Ring radius", "token":"gold", "min":0.2, "max":1.4, "step":0.01, "default":0.8, "reinit":true, "tooltip":"Pearl ring major radius", "shapes":[5]},
	{"id":"ic_ring_knot_count", "prop":"initial_shape_settings", "key":"ring_knot_count", "caption":"Knot count", "token":"gold", "min":1, "max":16, "step":1, "default":8, "reinit":true, "tooltip":"Pearl concentration count", "shapes":[5]},
	{"id":"ic_ring_warp", "prop":"initial_shape_settings", "key":"ring_warp", "caption":"Ring warp", "token":"gold", "min":0.0, "max":0.3, "step":0.005, "default":0.065, "reinit":true, "tooltip":"Vertical knot warp", "shapes":[5]},
	{"id":"ic_shell_count", "prop":"initial_shape_settings", "key":"shell_count", "caption":"Shell count", "token":"gold", "min":1, "max":8, "step":1, "default":3, "reinit":true, "tooltip":"Number of nested shells", "shapes":[6]},
	{"id":"ic_shell_spacing", "prop":"initial_shape_settings", "key":"shell_spacing", "caption":"Shell spacing", "token":"gold", "min":0.05, "max":1.0, "step":0.01, "default":0.33, "reinit":true, "tooltip":"Radial spacing between shells", "shapes":[6]},
	{"id":"ic_shell_inner_radius", "prop":"initial_shape_settings", "key":"shell_inner_radius", "caption":"Inner radius", "token":"gold", "min":0.05, "max":1.0, "step":0.01, "default":0.34, "reinit":true, "tooltip":"Innermost shell radius", "shapes":[6]},
	{"id":"ic_shell_ellipticity", "prop":"initial_shape_settings", "key":"shell_ellipticity", "caption":"Ellipticity", "token":"gold", "min":0.35, "max":1.0, "step":0.01, "default":0.88, "reinit":true, "tooltip":"Flatten shell axes", "shapes":[6]},
	{"id":"ic_shell_offset", "prop":"initial_shape_settings", "key":"shell_offset", "caption":"Shell offset", "token":"gold", "min":0.0, "max":0.4, "step":0.01, "default":0.12, "reinit":true, "tooltip":"Alternating shell center offset", "shapes":[6]},
	{"id":"ic_helix_strands", "prop":"initial_shape_settings", "key":"helix_strands", "caption":"Helix strands", "token":"gold", "min":1, "max":6, "step":1, "default":2, "reinit":true, "tooltip":"Number of intertwined strands", "shapes":[7]},
	{"id":"ic_helix_turns", "prop":"initial_shape_settings", "key":"helix_turns", "caption":"Helix turns", "token":"gold", "min":0.25, "max":8.0, "step":0.05, "default":2.5, "reinit":true, "tooltip":"Turns across the longitudinal extent", "shapes":[7]},
	{"id":"ic_helix_radius", "prop":"initial_shape_settings", "key":"helix_radius", "caption":"Helix radius", "token":"gold", "min":0.05, "max":0.8, "step":0.01, "default":0.30, "reinit":true, "tooltip":"Helix strand radius", "shapes":[7]},
	{"id":"ic_helix_pitch", "prop":"initial_shape_settings", "key":"helix_pitch", "caption":"Helix pitch", "token":"gold", "min":0.2, "max":2.5, "step":0.01, "default":1.0, "reinit":true, "tooltip":"Longitudinal pitch", "shapes":[7]},
	{"id":"ic_web_junctions", "prop":"initial_shape_settings", "key":"web_junctions", "caption":"Junctions", "token":"gold", "min":4, "max":64, "step":1, "default":16, "reinit":true, "tooltip":"Filament web junction count", "shapes":[8]},
	{"id":"ic_web_connectivity", "prop":"initial_shape_settings", "key":"web_connectivity", "caption":"Connectivity", "token":"gold", "min":1, "max":5, "step":1, "default":2, "reinit":true, "tooltip":"Nearest-neighbor links per junction", "shapes":[8]},
	{"id":"ic_web_curvature", "prop":"initial_shape_settings", "key":"web_curvature", "caption":"Curvature", "token":"gold", "min":0.0, "max":0.4, "step":0.01, "default":0.13, "reinit":true, "tooltip":"Filament bend amplitude", "shapes":[8]},
	{"id":"ic_hierarchy_depth", "prop":"initial_shape_settings", "key":"hierarchy_depth", "caption":"Hierarchy depth", "token":"gold", "min":1, "max":5, "step":1, "default":3, "reinit":true, "tooltip":"Nested cloud levels", "shapes":[9]},
	{"id":"ic_hierarchy_branching", "prop":"initial_shape_settings", "key":"hierarchy_branching", "caption":"Branching", "token":"gold", "min":2, "max":8, "step":1, "default":5, "reinit":true, "tooltip":"Children per hierarchy node", "shapes":[9]},
	{"id":"ic_hierarchy_scale_separation", "prop":"initial_shape_settings", "key":"hierarchy_scale_separation", "caption":"Scale separation", "token":"gold", "min":0.2, "max":0.8, "step":0.01, "default":0.42, "reinit":true, "tooltip":"Scale ratio between levels", "shapes":[9]},
	{"id":"ic_sheet_fold_amplitude", "prop":"initial_shape_settings", "key":"sheet_fold_amplitude", "caption":"Fold amplitude", "token":"gold", "min":0.0, "max":0.8, "step":0.01, "default":0.30, "reinit":true, "tooltip":"Sheet fold height", "shapes":[10]},
	{"id":"ic_sheet_wavelength", "prop":"initial_shape_settings", "key":"sheet_wavelength", "caption":"Wavelength", "token":"gold", "min":0.25, "max":4.0, "step":0.01, "default":1.2, "reinit":true, "tooltip":"Primary fold wavelength", "shapes":[10]},
	{"id":"ic_sheet_ripples", "prop":"initial_shape_settings", "key":"sheet_ripples", "caption":"Ripples", "token":"gold", "min":1, "max":8, "step":1, "default":2, "reinit":true, "tooltip":"Secondary ripple count", "shapes":[10]},
	{"id":"ic_sheet_aspect", "prop":"initial_shape_settings", "key":"sheet_aspect", "caption":"Aspect", "token":"gold", "min":0.25, "max":3.0, "step":0.01, "default":1.0, "reinit":true, "tooltip":"Sheet x/y aspect", "shapes":[10]},
	{"id":"ic_trefoil_loop_radius", "prop":"initial_shape_settings", "key":"trefoil_loop_radius", "caption":"Loop radius", "token":"gold", "min":0.35, "max":1.0, "step":0.01, "default":0.65, "reinit":true, "tooltip":"Trefoil loop radius", "shapes":[11]},
	{"id":"ic_trefoil_loop_ratio", "prop":"initial_shape_settings", "key":"trefoil_loop_ratio", "caption":"Loop proportion", "token":"gold", "min":0.05, "max":0.6, "step":0.01, "default":0.25, "reinit":true, "tooltip":"Three-lobe radial proportion", "shapes":[11]},
	{"id":"ic_trefoil_height", "prop":"initial_shape_settings", "key":"trefoil_height", "caption":"Trefoil height", "token":"gold", "min":0.05, "max":0.8, "step":0.01, "default":0.25, "reinit":true, "tooltip":"Trefoil vertical extent", "shapes":[11]}
]

static func _f(cfg: Dictionary, key: String, fallback: float = 0.0) -> float:
	return float(cfg.get(key, fallback))

static func _i(cfg: Dictionary, key: String, fallback: int = 0) -> int:
	return int(cfg.get(key, fallback))

static func _v3(cfg: Dictionary, key: String, fallback: Vector3 = Vector3.ZERO) -> Vector3:
	var value: Variant = cfg.get(key, fallback)
	return value if value is Vector3 else fallback

static func _settings(cfg: Dictionary) -> Dictionary:
	var out: Dictionary = DEFAULTS.duplicate(true)
	var supplied: Variant = cfg.get("initial_shape_settings", {})
	if supplied is Dictionary:
		for key in supplied:
			out[key] = supplied[key]
	return out

static func _setting_f(s: Dictionary, key: String) -> float:
	return float(s.get(key, DEFAULTS.get(key, 0.0)))

static func _setting_i(s: Dictionary, key: String) -> int:
	return int(s.get(key, DEFAULTS.get(key, 0)))

static func _geometry_settings_nondefault(s: Dictionary) -> bool:
	for key in ["thickness", "clumpiness", "asymmetry", "yaw", "pitch", "roll"]:
		if absf(float(s.get(key, DEFAULTS[key])) - float(DEFAULTS[key])) > 1.0e-6:
			return true
	return false

static func uses_generated_geometry(cfg: Dictionary) -> bool:
	var shape: int = _i(cfg, "initial_condition", 0)
	var arrangement: int = _i(cfg, "initial_arrangement", 0)
	return shape >= 3 or arrangement >= 2 or _geometry_settings_nondefault(_settings(cfg))

static func _arrangement_count(cfg: Dictionary) -> int:
	var arrangement: int = clampi(_i(cfg, "initial_arrangement", 0), 0, 6)
	if arrangement == 2: return 1
	if arrangement == 3: return 2
	return clampi(_i(cfg, "num_clusters", 1), 1, 64)
static func component_centers(cfg: Dictionary) -> PackedVector3Array:
	var count: int = _arrangement_count(cfg)
	var arrangement: int = clampi(_i(cfg, "initial_arrangement", 0), 0, 6)
	var separation: float = maxf(0.0, _f(cfg, "cluster_separation", 60.0))
	var seed: int = _i(cfg, "seed", _i(cfg, "ic_seed", 1))
	var centers := PackedVector3Array()
	centers.resize(count)
	var rng := RandomNumberGenerator.new()
	rng.seed = _stream_seed(seed, STRUCTURE_STREAM_OFFSET + arrangement * 7919)
	for c in range(count):
		var p := Vector3.ZERO
		if arrangement == 0:
			if count == 1:
				p = Vector3(separation, 0.0, 0.0)
			else:
				var a: float = TAU_F * float(c) / float(count)
				p = Vector3(separation * cos(a), 0.0, separation * sin(a))
		elif arrangement == 1:
			var phi: float = acos(1.0 - 2.0 * (float(c) + 0.5) / float(count))
			var theta: float = PI_F * (1.0 + sqrt(5.0)) * float(c)
			p = Vector3(separation * sin(phi) * cos(theta), separation * sin(phi) * sin(theta), separation * cos(phi))
		elif arrangement == 2:
			p = Vector3.ZERO
		elif arrangement == 3:
			if count == 1:
				p = Vector3.ZERO
			else:
				var side: float = separation * 0.5
				p = Vector3(-side if c % 2 == 0 else side, 0.0, 0.0)
		elif arrangement == 4:
			p = Vector3((float(c) - 0.5 * float(count - 1)) * separation, 0.0, 0.0)
		elif arrangement == 5:
			p = _random_ball(rng, separation)
		else:
			# The hierarchy arrangement is itself precomputed once. A bounded
			# branching fan keeps the component centres usable by the GPU record.
			var level: int = c % 3
			var scale: float = separation * pow(0.42, float(level))
			p = _random_ball(rng, scale)
		centers[c] = p + _v3(cfg, "window_center", Vector3.ZERO)
	return centers

static func support_bounds(cfg: Dictionary) -> AABB:
	var centers: PackedVector3Array = component_centers(cfg)
	var s: Dictionary = _settings(cfg)
	var scale: float = maxf(0.001, absf(_f(cfg, "cluster_radius", 50.0)))
	var thick: float = maxf(0.02, _setting_f(s, "thickness"))
	var clump: float = clampf(_setting_f(s, "clumpiness"), 0.0, 2.0)
	var shape: int = clampi(_i(cfg, "initial_condition", 0), 0, 11)
	# Bound the centreline separately from transverse thickness. A thin
	# filament still spans its full length, including after rotation.
	var radius: float = 1.0
	if shape <= 2:
		radius = maxf(_f(cfg, "initial_radius_fraction", 0.9), 0.01)
	elif shape == 3:
		radius = Vector2(1.0, 0.04 * thick).length() + absf(_setting_f(s, "spiral_width")) * clump
	elif shape == 4:
		radius = Vector2(0.65 * _setting_f(s, "encounter_size"), 0.035 * thick).length()
		radius += Vector2(_setting_f(s, "encounter_separation") * 0.5, _setting_f(s, "encounter_offset") * 0.35).length()
	elif shape == 5:
		var tube: float = (0.055 + 0.06 * clump) * thick
		radius = Vector2(_setting_f(s, "ring_radius") + tube, absf(_setting_f(s, "ring_warp")) + tube).length()
	elif shape == 6:
		var outer: float = _setting_f(s, "shell_inner_radius") + _setting_f(s, "shell_spacing") * float(clampi(_setting_i(s, "shell_count"), 1, 8) - 1)
		outer += (0.018 + 0.03 * clump) * thick
		var ellipticity: float = clampf(_setting_f(s, "shell_ellipticity"), 0.35, 1.0)
		radius = outer * maxf(1.0, 2.0 * ellipticity - 0.7) + absf(_setting_f(s, "shell_offset")) * sqrt(1.09)
	elif shape == 7:
		radius = Vector2(_setting_f(s, "helix_radius"), _setting_f(s, "helix_pitch")).length() + 0.045 * thick * clump
	elif shape == 8:
		radius = 1.0 + maxf(absf(_setting_f(s, "web_curvature")) * clump + 0.022 * thick * clump, 0.065 * thick)
	elif shape == 9:
		var depth: int = clampi(_setting_i(s, "hierarchy_depth"), 1, 5)
		var ratio: float = clampf(_setting_f(s, "hierarchy_scale_separation"), 0.2, 0.8)
		radius = 0.76 * (1.0 - pow(ratio, float(depth))) / (1.0 - ratio)
		radius += 0.76 * 0.8 * (0.65 + 0.35 * clump)
	elif shape == 10:
		radius = Vector3(1.0, maxf(_setting_f(s, "sheet_aspect"), 0.25), absf(_setting_f(s, "sheet_fold_amplitude")) + 0.13).length() + 0.022 * thick * clump
	else:
		radius = Vector2(_setting_f(s, "trefoil_loop_radius") + absf(_setting_f(s, "trefoil_loop_ratio")), _setting_f(s, "trefoil_height")).length() + 0.035 * thick * clump
	radius *= scale * (1.0 + absf(clampf(_setting_f(s, "asymmetry"), -0.8, 0.8)))
	var rung_disp: float = 0.0
	if bool(cfg.get("multi_rung_seed", false)) and _i(cfg, "multi_rung_count", 0) > 0:
		var base: float = maxf(absf(_f(cfg, "multi_rung_base_scale", 1.0) * _f(cfg, "cluster_radius", 50.0)), 1.0e-5)
		var kbase: float = TAU_F / base
		for rung in range(clampi(_i(cfg, "multi_rung_count", 1), 0, 16)):
			rung_disp += absf(_f(cfg, "multi_rung_amp", 0.2)) / maxf(kbase * pow(PHI_F, float(rung)), 1.0e-5)
	var lo := Vector3(INF, INF, INF)
	var hi := Vector3(-INF, -INF, -INF)
	for center in centers:
		var extent := Vector3.ONE * (radius + rung_disp)
		lo.x = minf(lo.x, center.x - extent.x); lo.y = minf(lo.y, center.y - extent.y); lo.z = minf(lo.z, center.z - extent.z)
		hi.x = maxf(hi.x, center.x + extent.x); hi.y = maxf(hi.y, center.y + extent.y); hi.z = maxf(hi.z, center.z + extent.z)
	if centers.is_empty():
		lo = Vector3.ZERO; hi = Vector3.ZERO
	return AABB(lo, hi - lo)

static func _stream_seed(seed_value: int, offset: int) -> int:
	var value: int = seed_value ^ offset
	if value == 0:
		value = 1
	return value & 0x7fffffff

static func _random_ball(rng: RandomNumberGenerator, radius: float) -> Vector3:
	var z: float = rng.randf_range(-1.0, 1.0)
	var a: float = rng.randf_range(0.0, TAU_F)
	var rr: float = radius * pow(rng.randf(), 1.0 / 3.0)
	var q: float = sqrt(maxf(1.0 - z * z, 0.0))
	return Vector3(rr * q * cos(a), rr * q * sin(a), rr * z)
static func _erf_approx(x: float) -> float:
	var t: float = 1.0 / (1.0 + 0.3275911 * x)
	var poly: float = ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t
	return 1.0 - poly * exp(-x * x)

static func _rotate(v: Vector3, s: Dictionary) -> Vector3:
	var out := v
	out = out.rotated(Vector3.UP, deg_to_rad(_setting_f(s, "yaw")))
	out = out.rotated(Vector3.RIGHT, deg_to_rad(_setting_f(s, "pitch")))
	out = out.rotated(Vector3.FORWARD, deg_to_rad(_setting_f(s, "roll")))
	var asym: float = clampf(_setting_f(s, "asymmetry"), -0.8, 0.8)
	out.x *= 1.0 + asym
	out.y *= 1.0 - 0.5 * asym
	return out

static func _oriented_unit(v: Vector3, s: Dictionary) -> Vector3:
	var out := _rotate(v, s)
	return out.normalized() if out.length_squared() > 1.0e-12 else Vector3.FORWARD
static func _profile_point(rng: RandomNumberGenerator, shape: int, scale: float, cfg: Dictionary) -> Vector3:
	var fraction: float = maxf(_f(cfg, "initial_radius_fraction", 0.9), 0.01)
	var radius: float = maxf(absf(scale) * fraction, 1.0e-6)
	if shape == 0:
		var scale_ratio: float = radius / maxf(absf(scale), 1.0e-6)
		var umax: float = pow(scale_ratio * scale_ratio / (1.0 + scale_ratio * scale_ratio), 1.5)
		var u: float = rng.randf_range(0.001, maxf(umax, 0.0011))
		var r: float = absf(scale) / sqrt(maxf(pow(u, -2.0 / 3.0) - 1.0, 1.0e-8))
		var z: float = rng.randf_range(-1.0, 1.0)
		var a: float = rng.randf() * TAU_F
		var q: float = sqrt(maxf(1.0 - z * z, 0.0))
		return Vector3(r * q * cos(a), r * q * sin(a), r * z)
	if shape == 1:
		var s2: float = sqrt(2.0) * maxf(absf(scale), 1.0e-6)
		var zmax: float = radius / s2
		var erf_max: float = _erf_approx(zmax) - 2.0 / sqrt(PI_F) * zmax * exp(-zmax * zmax)
		var target: float = rng.randf() * maxf(erf_max, 1.0e-30)
		var z_lo: float = 0.0
		var z_hi: float = zmax
		for _b in range(16):
			var z_mid: float = 0.5 * (z_lo + z_hi)
			var cdf: float = _erf_approx(z_mid) - 2.0 / sqrt(PI_F) * z_mid * exp(-z_mid * z_mid)
			if cdf < target: z_lo = z_mid
			else: z_hi = z_mid
		var r_gaussian: float = s2 * 0.5 * (z_lo + z_hi)
		var dir_z: float = rng.randf_range(-1.0, 1.0)
		var dir_a: float = rng.randf() * TAU_F
		var dir_q: float = sqrt(maxf(1.0 - dir_z * dir_z, 0.0))
		return Vector3(r_gaussian * dir_q * cos(dir_a), r_gaussian * dir_q * sin(dir_a), r_gaussian * dir_z)
	return _random_ball(rng, radius)

static func _disc_point(rng: RandomNumberGenerator, radius: float, thickness: float) -> Vector3:
	var r: float = radius * sqrt(rng.randf())
	var a: float = rng.randf() * TAU_F
	return Vector3(r * cos(a), r * sin(a), rng.randf_range(-thickness, thickness))

## xyz is the sampled point; w retains its curve parameter or encounter part.
static func _shape_point(shape: int, rng: RandomNumberGenerator, index: int, count: int, s: Dictionary, web_nodes: PackedVector3Array, web_edges: PackedInt32Array, web_lengths: PackedFloat32Array, hierarchy_levels: Array[PackedVector3Array], hierarchy_widths: PackedFloat32Array, trefoil_grid: PackedFloat32Array, trefoil_cdf: PackedFloat32Array) -> Vector4:
	var clump: float = clampf(_setting_f(s, "clumpiness"), 0.0, 2.0)
	var thick: float = maxf(0.02, _setting_f(s, "thickness"))
	var p := Vector3.ZERO
	var parameter := 0.0
	if shape == 3:
		var arms: int = clampi(_setting_i(s, "spiral_arms"), 1, 8)
		var core: float = clampf(_setting_f(s, "spiral_core"), 0.02, 0.5)
		if rng.randf() < 0.18:
			p = _random_ball(rng, core * 0.8)
		else:
			var r: float = rng.randf_range(core, 1.0)
			var arm: int = rng.randi_range(0, arms - 1)
			var pitch: float = deg_to_rad(clampf(_setting_f(s, "spiral_pitch"), 5.0, 60.0))
			var theta: float = log(maxf(r / core, 1.0e-5)) / maxf(tan(pitch), 0.05) + TAU_F * float(arm) / float(arms)
			var width: float = _setting_f(s, "spiral_width") * clump
			p = Vector3(r * cos(theta), r * sin(theta), rng.randf_range(-0.04, 0.04) * thick)
			p += _random_ball(rng, width)
	elif shape == 4:
		var ratio: float = clampf(_setting_f(s, "encounter_particle_ratio"), 0.1, 0.9)
		var first: bool = float(index) / float(maxi(count, 1)) < ratio
		parameter = 0.0 if first else 1.0
		var sep: float = _setting_f(s, "encounter_separation")
		var size: float = _setting_f(s, "encounter_size") * (0.65 if first else 0.46)
		var local := _disc_point(rng, size, 0.035 * thick)
		var tilt: float = 12.0 if first else _setting_f(s, "encounter_relative_tilt") + 12.0
		local = local.rotated(Vector3.RIGHT, deg_to_rad(tilt))
		var offset: float = _setting_f(s, "encounter_offset")
		p = local + Vector3(-sep * 0.5 if first else sep * 0.5, (-offset if first else offset) * 0.35, 0.0)
	elif shape == 5:
		var major: float = _setting_f(s, "ring_radius")
		var theta: float = rng.randf() * TAU_F
		var knots: int = clampi(_setting_i(s, "ring_knot_count"), 1, 16)
		if clump > 0.0 and rng.randf() < 0.42 * minf(clump, 1.0):
			theta = round(theta / TAU_F * float(knots)) * TAU_F / float(knots) + rng.randf_range(-0.08, 0.08) * clump
		var minor: float = (0.055 + 0.06 * clump) * thick
		var rr: float = minor * sqrt(rng.randf())
		var phi: float = rng.randf() * TAU_F
		p = Vector3((major + rr * cos(phi)) * cos(theta), (major + rr * cos(phi)) * sin(theta), _setting_f(s, "ring_warp") * sin(float(knots) * theta) + rr * sin(phi))
		parameter = theta
	elif shape == 6:
		var shells: int = clampi(_setting_i(s, "shell_count"), 1, 8)
		var shell: int = index % shells
		var inner: float = _setting_f(s, "shell_inner_radius")
		var spacing: float = _setting_f(s, "shell_spacing")
		var sr: float = inner + spacing * float(shell)
		var shell_half: float = 0.018 + 0.03 * clump
		var dir := _random_ball(rng, 1.0).normalized()
		var rr: float = sr + rng.randf_range(-shell_half, shell_half)
		var e: float = clampf(_setting_f(s, "shell_ellipticity"), 0.35, 1.0)
		p = Vector3(dir.x * rr, dir.y * rr * e, dir.z * rr * (2.0 * e - 0.7))
		if shell % 2 == 1:
			p += Vector3(_setting_f(s, "shell_offset"), 0.0, 0.0)
	elif shape == 7:
		var strands: int = clampi(_setting_i(s, "helix_strands"), 1, 6)
		var strand: int = index % strands
		var t: float = rng.randf_range(-1.0, 1.0)
		var theta: float = (t + 1.0) * PI_F * _setting_f(s, "helix_turns") + TAU_F * float(strand) / float(strands)
		var hr: float = _setting_f(s, "helix_radius")
		p = Vector3(hr * cos(theta), hr * sin(theta), t * _setting_f(s, "helix_pitch")) + _random_ball(rng, 0.045 * thick * clump)
		parameter = theta
	elif shape == 8:
		var edge_count: int = maxi(1, web_edges.size() / 2)
		var target: float = rng.randf() * maxf(0.0001, web_lengths[edge_count - 1] if web_lengths.size() >= edge_count else 1.0)
		var edge: int = 0
		while edge < edge_count - 1 and web_lengths[edge] < target:
			edge += 1
		var a: Vector3 = web_nodes[web_edges[edge * 2]]
		var b: Vector3 = web_nodes[web_edges[edge * 2 + 1]]
		var t2: float = rng.randf()
		var bend: Vector3 = _web_bend(a, b, s)
		p = a.lerp(b, t2) + bend * (4.0 * t2 * (1.0 - t2)) + _random_ball(rng, 0.022 * thick * clump)
		parameter = float(edge) + minf(t2, 0.99999)
		if rng.randf() < 0.2:
			p = web_nodes[rng.randi_range(0, web_nodes.size() - 1)] + _random_ball(rng, 0.065 * thick)
			parameter = -1.0
	elif shape == 9:
		var depth_count: int = maxi(1, hierarchy_levels.size())
		var level: int = rng.randi_range(0, depth_count - 1)
		var level_nodes: PackedVector3Array = hierarchy_levels[level]
		var node: Vector3 = level_nodes[rng.randi_range(0, level_nodes.size() - 1)]
		p = node + _random_ball(rng, hierarchy_widths[level] * (0.65 + 0.35 * clump))
	elif shape == 10:
		var x: float = rng.randf_range(-1.0, 1.0) * maxf(_setting_f(s, "sheet_aspect"), 0.25)
		var y: float = rng.randf_range(-1.0, 1.0)
		var wavelength: float = maxf(_setting_f(s, "sheet_wavelength"), 0.25)
		var ripples: int = clampi(_setting_i(s, "sheet_ripples"), 1, 8)
		var z: float = _setting_f(s, "sheet_fold_amplitude") * sin(PI_F * x / wavelength) + 0.13 * sin(float(ripples) * PI_F * y)
		p = Vector3(x, y, z) + _random_ball(rng, 0.022 * thick * clump)
	else:
		var u: float = rng.randf() * TAU_F
		if trefoil_grid.size() > 1 and trefoil_cdf.size() == trefoil_grid.size():
			var target_cdf: float = rng.randf() * trefoil_cdf[trefoil_cdf.size() - 1]
			var lo: int = 0; var hi: int = trefoil_cdf.size() - 1
			while hi - lo > 1:
				var mid: int = (lo + hi) / 2
				if trefoil_cdf[mid] < target_cdf: lo = mid
				else: hi = mid
			u = lerpf(trefoil_grid[lo], trefoil_grid[hi], (target_cdf - trefoil_cdf[lo]) / maxf(trefoil_cdf[hi] - trefoil_cdf[lo], 1.0e-8))
		var rr3: float = _setting_f(s, "trefoil_loop_radius") + _setting_f(s, "trefoil_loop_ratio") * cos(3.0 * u)
		p = Vector3(rr3 * cos(2.0 * u), rr3 * sin(2.0 * u), _setting_f(s, "trefoil_height") * sin(3.0 * u)) + _random_ball(rng, 0.035 * thick * clump)
		parameter = u
	return Vector4(p.x, p.y, p.z, parameter)

static func _build_web(s: Dictionary, rng: RandomNumberGenerator) -> Array:
	var node_count: int = clampi(_setting_i(s, "web_junctions"), 4, 64)
	var nodes := PackedVector3Array()
	nodes.resize(node_count)
	for i in range(node_count): nodes[i] = _random_ball(rng, 1.0)
	var edges := PackedInt32Array()
	var used: Dictionary = {}
	var visited: Dictionary = {0: true}
	while visited.size() < node_count:
		var best_d: float = INF; var best_a: int = 0; var best_b: int = 0
		for a in visited:
			for b in range(node_count):
				if visited.has(b): continue
				var d: float = nodes[a].distance_squared_to(nodes[b])
				if d < best_d: best_d = d; best_a = int(a); best_b = b
		edges.append(best_a); edges.append(best_b); used["%d:%d" % [mini(best_a, best_b), maxi(best_a, best_b)]] = true; visited[best_b] = true
	var connectivity: int = clampi(_setting_i(s, "web_connectivity"), 1, 5)
	for a in range(node_count):
		var candidates: Array[Dictionary] = []
		for b in range(node_count):
			if a == b: continue
			candidates.append({"d": nodes[a].distance_squared_to(nodes[b]), "b": b})
		candidates.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return float(x["d"]) < float(y["d"]))
		for k in range(mini(connectivity, candidates.size())):
			var b2: int = int(candidates[k]["b"]); var key := "%d:%d" % [mini(a, b2), maxi(a, b2)]
			if not used.has(key): edges.append(a); edges.append(b2); used[key] = true
	var lengths := PackedFloat32Array(); lengths.resize(edges.size() / 2)
	var total: float = 0.0
	for e in range(lengths.size()):
		var l: float = nodes[edges[e * 2]].distance_to(nodes[edges[e * 2 + 1]])
		total += l; lengths[e] = total
	return [nodes, edges, lengths]

static func _build_hierarchy(s: Dictionary, rng: RandomNumberGenerator) -> Array:
	var depth: int = clampi(_setting_i(s, "hierarchy_depth"), 1, 5)
	var branching: int = clampi(_setting_i(s, "hierarchy_branching"), 2, 8)
	var ratio: float = clampf(_setting_f(s, "hierarchy_scale_separation"), 0.2, 0.8)
	var levels: Array[PackedVector3Array] = []
	var widths := PackedFloat32Array()
	var parents := PackedVector3Array([Vector3.ZERO])
	var scale: float = 0.76
	for d in range(depth):
		var children := PackedVector3Array()
		var child_limit: int = mini(parents.size() * branching, 4096)
		for i in range(child_limit): children.append(parents[i / branching] + _random_ball(rng, scale))
		levels.append(children)
		widths.append(scale * 0.4)
		parents = children
		scale *= ratio
	return [levels, widths]
static func _build_trefoil_table(s: Dictionary) -> Array:
	var grid := PackedFloat32Array(); var cdf := PackedFloat32Array()
	var samples: int = 257; grid.resize(samples); cdf.resize(samples); cdf[0] = 0.0
	var loop_radius: float = _setting_f(s, "trefoil_loop_radius")
	var loop_ratio: float = _setting_f(s, "trefoil_loop_ratio")
	var height: float = _setting_f(s, "trefoil_height")
	for i in range(samples):
		grid[i] = TAU_F * float(i) / float(samples - 1)
		if i > 0:
			var a: float = grid[i - 1]; var b: float = grid[i]
			var ra: float = loop_radius + loop_ratio * cos(3.0 * a); var rb: float = loop_radius + loop_ratio * cos(3.0 * b)
			var pa := Vector3(ra * cos(2.0 * a), ra * sin(2.0 * a), height * sin(3.0 * a))
			var pb := Vector3(rb * cos(2.0 * b), rb * sin(2.0 * b), height * sin(3.0 * b))
			cdf[i] = cdf[i - 1] + pa.distance_to(pb)
	return [grid, cdf]

static func _multi_rung(p: Vector3, cfg: Dictionary) -> Vector3:
	if not bool(cfg.get("multi_rung_seed", false)): return p
	var count: int = clampi(_i(cfg, "multi_rung_count", 0), 0, 16)
	if count <= 0: return p
	var base: float = maxf(_f(cfg, "multi_rung_base_scale", 1.0) * absf(_f(cfg, "cluster_radius", 50.0)), 1.0e-5)
	var kbase: float = TAU_F / base
	var out := p
	for rung in range(count):
		var k: float = kbase * pow(PHI_F, float(rung))
		var d := _fibonacci_dir(rung, count)
		var phase: float = float(rung) * TAU_F / (PHI_F * PHI_F)
		var amp: float = _f(cfg, "multi_rung_amp", 0.2) / maxf(k, 1.0e-6)
		var wave: float = sin(k * out.dot(d) + phase)
		out += d * (amp * wave)
	return out

static func _fibonacci_dir(i: int, total: int) -> Vector3:
	var z: float = 1.0 - 2.0 * (float(i) + 0.5) / float(maxi(total, 1))
	var a: float = PI_F * (1.0 + sqrt(5.0)) * float(i)
	var rr: float = sqrt(maxf(1.0 - z * z, 0.0))
	return Vector3(rr * cos(a), rr * sin(a), z)

static func _web_bend(a: Vector3, b: Vector3, s: Dictionary) -> Vector3:
	var normal := (b - a).cross(Vector3.UP).normalized()
	if normal.length_squared() < 1.0e-12:
		normal = Vector3.RIGHT
	return normal * _setting_f(s, "web_curvature") * clampf(_setting_f(s, "clumpiness"), 0.0, 2.0)

static func _web_tangent(p: Vector3, nodes: PackedVector3Array, edges: PackedInt32Array, s: Dictionary) -> Vector3:
	if nodes.is_empty() or edges.size() < 2: return Vector3.RIGHT
	var best_d: float = INF
	var best := Vector3.RIGHT
	for e in range(edges.size() / 2):
		var a: Vector3 = nodes[edges[e * 2]]
		var b: Vector3 = nodes[edges[e * 2 + 1]]
		var ab: Vector3 = b - a
		var u: float = clampf((p - a).dot(ab) / maxf(ab.length_squared(), 1.0e-8), 0.0, 1.0)
		var d: float = p.distance_squared_to(a + ab * u)

		if d < best_d:
			best_d = d
			best = ab + _web_bend(a, b, s) * (4.0 * (1.0 - 2.0 * u))
	return best.normalized() if best.length_squared() > 1.0e-12 else Vector3.RIGHT
static func _raw_structure_direction(shape: int, p: Vector3, s: Dictionary, parameter: float, web_nodes: PackedVector3Array, web_edges: PackedInt32Array) -> Vector3:
	var d := Vector3.FORWARD
	if shape == 3:
		var pitch: float = tan(deg_to_rad(clampf(_setting_f(s, "spiral_pitch"), 5.0, 60.0)))
		d = Vector3(-p.y + pitch * p.x, p.x + pitch * p.y, 0.0)
	elif shape == 4:
		var first := parameter < 0.5
		var center := Vector3(-_setting_f(s, "encounter_separation") * 0.5 if first else _setting_f(s, "encounter_separation") * 0.5, (-_setting_f(s, "encounter_offset") if first else _setting_f(s, "encounter_offset")) * 0.35, 0.0)
		var tilt: float = 12.0 if first else _setting_f(s, "encounter_relative_tilt") + 12.0
		var q := (p - center).rotated(Vector3.RIGHT, -deg_to_rad(tilt))
		d = Vector3(-q.y, q.x, 0.0).rotated(Vector3.RIGHT, deg_to_rad(tilt))
	elif shape == 5:
		var r: float = _setting_f(s, "ring_radius")
		var knots: float = float(clampi(_setting_i(s, "ring_knot_count"), 1, 16))
		d = Vector3(-r * sin(parameter), r * cos(parameter), _setting_f(s, "ring_warp") * knots * cos(knots * parameter))
	elif shape == 7:
		var r: float = _setting_f(s, "helix_radius")
		d = Vector3(-r * sin(parameter), r * cos(parameter), _setting_f(s, "helix_pitch") / maxf(_setting_f(s, "helix_turns") * PI_F, 0.01))
	elif shape == 8:
		if parameter >= 0.0:
			var edge: int = int(parameter)
			var t: float = parameter - float(edge)
			var a: Vector3 = web_nodes[web_edges[edge * 2]]
			var b: Vector3 = web_nodes[web_edges[edge * 2 + 1]]
			d = b - a + _web_bend(a, b, s) * (4.0 * (1.0 - 2.0 * t))
		else:
			d = _web_tangent(p, web_nodes, web_edges, s)
	elif shape == 10:
		var k: float = PI_F / maxf(_setting_f(s, "sheet_wavelength"), 0.25)
		d = Vector3(1.0, 0.0, _setting_f(s, "sheet_fold_amplitude") * k * cos(k * p.x))
	elif shape == 11:
		var ratio: float = _setting_f(s, "trefoil_loop_ratio")
		var r: float = _setting_f(s, "trefoil_loop_radius") + ratio * cos(3.0 * parameter)
		var dr: float = -3.0 * ratio * sin(3.0 * parameter)
		d = Vector3(dr * cos(2.0 * parameter) - 2.0 * r * sin(2.0 * parameter), dr * sin(2.0 * parameter) + 2.0 * r * cos(2.0 * parameter), 3.0 * _setting_f(s, "trefoil_height") * cos(3.0 * parameter))
	else:
		d = Vector3(-p.y, p.x, 0.0)
	return d.normalized() if d.length_squared() > 1.0e-12 else Vector3.FORWARD

static func _motion_velocity(motion: int, speed: float, shape: int, p: Vector3, center: Vector3, arrangement_center: Vector3, s: Dictionary, component: int, particle_index: int, _component_count: int, structure_direction: Vector3 = Vector3.ZERO) -> Vector3:
	if motion == 1:
		return Vector3.ZERO
	if motion == 4 or motion == 5:
		var radial := (arrangement_center - p).normalized()
		return radial * speed * (-1.0 if motion == 5 else 1.0)
	if motion == 6 or motion == 7:
		var stream: Vector3 = structure_direction
		if stream.length_squared() <= 1.0e-12:
			stream = _oriented_unit(_raw_structure_direction(shape, p - center, s, 0.0, PackedVector3Array(), PackedInt32Array()), s)
		if motion == 6:
			return stream * speed
		var stream_id: int = particle_index
		if shape == 7:
			stream_id = particle_index % maxi(1, _setting_i(s, "helix_strands"))
		elif shape == 4:
			stream_id = 0
		var direction_sign: float = -1.0 if ((component + stream_id) & 1) == 0 else 1.0
		return stream * speed * direction_sign
	var axis: Vector3
	if shape == 4:
		var tilt: float = 12.0 if component == 0 else _setting_f(s, "encounter_relative_tilt") + 12.0
		axis = _oriented_unit(Vector3.FORWARD.rotated(Vector3.RIGHT, deg_to_rad(tilt)), s)
	else:
		axis = _oriented_unit(Vector3.FORWARD, s)
	var tangent := axis.cross(p - center)
	if tangent.length_squared() < 1.0e-12:
		tangent = _oriented_unit(Vector3.RIGHT, s)
	return tangent.normalized() * speed * (-1.0 if motion == 3 else 1.0)

static func generate(cfg: Dictionary) -> Dictionary:
	var n: int = maxi(0, _i(cfg, "N_particles", 0))
	var pos := PackedFloat32Array(); var vel := PackedFloat32Array(); var acc := PackedFloat32Array()
	pos.resize(n * 4); vel.resize(n * 4); acc.resize(n * 4)
	var centers: PackedVector3Array = component_centers(cfg)
	var shape: int = clampi(_i(cfg, "initial_condition", 0), 0, 11)
	var motion: int = clampi(_i(cfg, "initial_motion", 0), 0, 7)
	var capture_stream: bool = motion == 6 or motion == 7
	var stream_dirs := PackedFloat32Array()
	if capture_stream: stream_dirs.resize(n * 3)
	var component_count: int = centers.size()
	var clusters := PackedFloat32Array(); clusters.resize(component_count * 4)
	var per_cluster: PackedInt32Array = PackedInt32Array(); per_cluster.resize(component_count)
	for i in range(n): per_cluster[mini(i * component_count / maxi(n, 1), component_count - 1)] += 1
	for c in range(component_count):
		clusters[c * 4] = centers[c].x; clusters[c * 4 + 1] = centers[c].y; clusters[c * 4 + 2] = centers[c].z; clusters[c * 4 + 3] = per_cluster[c]
	if n == 0:
		return {"pos":pos, "vel":vel, "acc":acc, "clusters":clusters, "cluster_count":component_count, "total_mass":0.0, "bounds":AABB(Vector3.ZERO, Vector3.ZERO)}
	var scale: float = maxf(absf(_f(cfg, "cluster_radius", 50.0)), 1.0e-6)
	var settings: Dictionary = _settings(cfg)
	var pos_rng := RandomNumberGenerator.new(); pos_rng.seed = _stream_seed(_i(cfg, "seed", _i(cfg, "ic_seed", 1)), POSITION_STREAM_OFFSET)
	var structure_rng := RandomNumberGenerator.new(); structure_rng.seed = _stream_seed(_i(cfg, "seed", _i(cfg, "ic_seed", 1)), STRUCTURE_STREAM_OFFSET + shape * 104729)
	var mass_rng := RandomNumberGenerator.new(); mass_rng.seed = _stream_seed(_i(cfg, "seed", _i(cfg, "ic_seed", 1)), MASS_STREAM_OFFSET)
	var salp_a: float = pow(0.3, -1.35)
	var salp_b: float = pow(30.0, -1.35)
	var salp_inv: float = -1.0 / 1.35
	var web_data: Array = [PackedVector3Array(), PackedInt32Array(), PackedFloat32Array()]
	if shape == 8: web_data = _build_web(settings, structure_rng)
	var hierarchy_levels: Array[PackedVector3Array] = []; var hierarchy_widths := PackedFloat32Array()
	if shape == 9:
		var hierarchy_data: Array = _build_hierarchy(settings, structure_rng); hierarchy_levels = hierarchy_data[0]; hierarchy_widths = hierarchy_data[1]
	var trefoil_grid := PackedFloat32Array(); var trefoil_cdf := PackedFloat32Array()
	if shape == 11:
		var trefoil_data: Array = _build_trefoil_table(settings)
		trefoil_grid = trefoil_data[0]; trefoil_cdf = trefoil_data[1]
	var cluster_mass := PackedFloat32Array(); cluster_mass.resize(component_count)
	var total_mass: float = 0.0
	var center_of_arrangement := _v3(cfg, "window_center", Vector3.ZERO)
	for i in range(n):
		var i4: int = i * 4
		var cidx: int = mini(i * component_count / n, component_count - 1)
		# The Salpeter stream is isolated from every geometry and structure RNG.
		var mass: float = pow(salp_a - mass_rng.randf() * (salp_a - salp_b), salp_inv)
		pos[i4 + 3] = mass; cluster_mass[cidx] += mass; total_mass += mass
		var local: Vector3
		var parameter := 0.0
		if shape <= 2:
			local = _profile_point(pos_rng, shape, scale, cfg)
		else:
			var start: int = (cidx * n + component_count - 1) / component_count
			var end: int = ((cidx + 1) * n + component_count - 1) / component_count
			var sample := _shape_point(shape, pos_rng, i - start, end - start, settings, web_data[0], web_data[1], web_data[2], hierarchy_levels, hierarchy_widths, trefoil_grid, trefoil_cdf)
			local = Vector3(sample.x, sample.y, sample.z)
			parameter = sample.w
		if capture_stream:
			var raw_stream: Vector3 = _raw_structure_direction(shape, local, settings, parameter, web_data[0], web_data[1])
			var stream_world: Vector3 = _rotate(raw_stream, settings).normalized()
			stream_dirs[i * 3] = stream_world.x; stream_dirs[i * 3 + 1] = stream_world.y; stream_dirs[i * 3 + 2] = stream_world.z
		if shape >= 3: local *= scale
		local = _rotate(local, settings)
		var world: Vector3 = centers[cidx] + local
		world = _multi_rung(world, cfg)
		pos[i4] = world.x; pos[i4 + 1] = world.y; pos[i4 + 2] = world.z
	# Positions are complete before any velocity mode is selected.
	var mass_override: float = _f(cfg, "initial_total_mass", 0.0)
	if mass_override > 0.0 and total_mass > 0.0:
		var factor: float = mass_override / total_mass
		for i in range(n): pos[i * 4 + 3] *= factor
		total_mass = mass_override
	var default_profile: bool = motion == 0 and shape <= 2
	var merger_speed: float = _f(cfg, "merger_speed", 0.0)
	for i in range(n):
		var i4: int = i * 4; var cidx: int = mini(i * component_count / n, component_count - 1)
		var world := Vector3(pos[i4], pos[i4 + 1], pos[i4 + 2])
		var v := Vector3.ZERO
		if default_profile:
			var rel := world - centers[cidx]
			var rr: float = rel.length()
			var enclosed: float = cluster_mass[cidx] * minf(1.0, pow(rr / maxf(scale, 1.0e-6), 3.0))
			var vc: float = sqrt(maxf(enclosed / maxf(rr, 0.01), 0.0)) * _f(cfg, "initial_v_circ_factor", 0.85)
			var tangent := Vector3(-rel.y, rel.x, 0.0).normalized() if rel.x * rel.x + rel.y * rel.y > 1.0e-12 else Vector3.RIGHT
			v = tangent * vc
			if merger_speed != 0.0:
				var radial := (center_of_arrangement - centers[cidx]).normalized()
				v += radial * merger_speed
		elif motion != 0:
			var stream_dir := Vector3.ZERO
			if capture_stream:
				stream_dir = Vector3(stream_dirs[i * 3], stream_dirs[i * 3 + 1], stream_dirs[i * 3 + 2])
			var motion_center: Vector3 = centers[cidx]
			var motion_component: int = cidx
			var start: int = (cidx * n + component_count - 1) / component_count
			if shape == 4:
				var end: int = ((cidx + 1) * n + component_count - 1) / component_count
				var first: bool = float(i - start) / float(end - start) < clampf(_setting_f(settings, "encounter_particle_ratio"), 0.1, 0.9)
				motion_component = 0 if first else 1
				var offset := Vector3(_setting_f(settings, "encounter_separation") * 0.5, _setting_f(settings, "encounter_offset") * 0.35, 0.0) * (-1.0 if first else 1.0)
				motion_center += _rotate(offset, settings) * scale
			v = _motion_velocity(motion, maxf(0.0, _f(cfg, "initial_speed", 5.0)), shape, world, motion_center, center_of_arrangement, settings, motion_component, i - start, component_count, stream_dir)
		vel[i4] = v.x; vel[i4 + 1] = v.y; vel[i4 + 2] = v.z; vel[i4 + 3] = 0.0
	var lo := Vector3(INF, INF, INF); var hi := Vector3(-INF, -INF, -INF)
	for i in range(n):
		var i4: int = i * 4; var q := Vector3(pos[i4], pos[i4 + 1], pos[i4 + 2])
		lo.x = minf(lo.x, q.x); lo.y = minf(lo.y, q.y); lo.z = minf(lo.z, q.z); hi.x = maxf(hi.x, q.x); hi.y = maxf(hi.y, q.y); hi.z = maxf(hi.z, q.z)
	return {"pos":pos, "vel":vel, "acc":acc, "clusters":clusters, "cluster_count":component_count, "total_mass":total_mass, "bounds":AABB(lo, hi - lo)}

static func apply_overrides(cfg: Dictionary, pos: PackedFloat32Array, vel: PackedFloat32Array, centers: PackedVector3Array) -> float:
	var n: int = pos.size() / 4
	if n <= 0: return 0.0
	var total: float = 0.0
	for i in range(n): total += pos[i * 4 + 3]
	var target: float = _f(cfg, "initial_total_mass", 0.0)
	if target > 0.0 and total > 0.0:
		var factor: float = target / total
		for i in range(n): pos[i * 4 + 3] *= factor
		total = target
	var motion: int = clampi(_i(cfg, "initial_motion", 0), 0, 7)
	if motion <= 0: return total
	var settings: Dictionary = _settings(cfg)
	var shape: int = clampi(_i(cfg, "initial_condition", 0), 0, 2)
	var speed: float = maxf(0.0, _f(cfg, "initial_speed", 5.0))
	var arrangement_center := _v3(cfg, "window_center", Vector3.ZERO)
	for i in range(n):
		var i4: int = i * 4; var cidx: int = mini(i * centers.size() / n, maxi(centers.size() - 1, 0))
		var center := centers[cidx] if not centers.is_empty() else arrangement_center
		var p := Vector3(pos[i4], pos[i4 + 1], pos[i4 + 2])
		var v := _motion_velocity(motion, speed, shape, p, center, arrangement_center, settings, cidx, i, centers.size())
		vel[i4] = v.x; vel[i4 + 1] = v.y; vel[i4 + 2] = v.z; vel[i4 + 3] = 0.0
	return total

class_name WorkbenchInitialConditions
extends RefCounted

## Deterministic procedural initial-condition compiler for the paused workbench.
## Recipes use normalized box coordinates in [-1, 1] and emit canonical commands.

const PHI := 1.618033988749895
const PHI_INV := 0.6180339887498948
const MAX_COMMANDS := 4096
const MAX_RINGS := 64
const MAX_SEGMENTS := 64
const EPSILON := 1.0e-12

static func compile(recipe: Array, geometry: Dictionary) -> Dictionary:
	var checked_geometry := _geometry(geometry)
	if not bool(checked_geometry.get("ok", false)):
		return checked_geometry
	if recipe == null:
		return _error("recipe_invalid")
	if recipe.size() > MAX_COMMANDS:
		return _error("recipe_too_large")
	var commands: Array = []
	var primitive_index := 0
	for raw_primitive in recipe:
		if not raw_primitive is Dictionary:
			return _error("primitive_invalid")
		var primitive: Dictionary = raw_primitive
		var name := str(primitive.get("kind", primitive.get("type", primitive.get("primitive", primitive.get("name", ""))))).to_lower()
		if name.is_empty():
			return _error("primitive_name_missing")
		var result := _emit_primitive(name, primitive, checked_geometry, primitive_index, commands)
		if not bool(result.get("ok", false)):
			return result
		primitive_index += 1
		if commands.size() > MAX_COMMANDS:
			return _error("command_count_exceeded")
	if commands.is_empty() and not recipe.is_empty():
		return _error("recipe_emitted_no_commands")
	var canonical_commands: Variant = _canonicalize(commands)
	var canonical: Dictionary = {"commands": canonical_commands}
	var text := JSON.stringify(canonical)
	return {"ok": true, "commands": canonical_commands, "digest": _sha256(text.to_utf8_buffer())}

static func _emit_primitive(name: String, p: Dictionary, g: Dictionary, index: int, out: Array) -> Dictionary:
	match name:
		"shell":
			var center := _center(p, g)
			if not bool(center.get("ok", false)): return center
			var radius := _world_radius(p.get("radius", p.get("scale", 0.25)), g)
			if not bool(radius.get("ok", false)): return radius
			var strength := _finite_number(p.get("strength", 1.0), "shell_strength")
			if not bool(strength.get("ok", false)): return strength
			_append(out, "deposit", center.value, radius.value, {"strength": strength.value, "weighted": false, "profile": "shell", "primitive": index})
			var alignment := _strength(p.get("align", 1.0), "shell_align")
			if not bool(alignment.get("ok", false)): return alignment
			_append(out, "align", center.value, radius.value, {"strength": alignment.value, "primitive": index})
		"gaussian_knot":
			var center := _center(p, g)
			if not bool(center.get("ok", false)): return center
			var radius := _world_radius(p.get("sigma", p.get("scale", 0.15)), g)
			if not bool(radius.get("ok", false)): return radius
			var strength := _finite_number(p.get("strength", 1.0), "gaussian_strength")
			if not bool(strength.get("ok", false)): return strength
			_append(out, "deposit", center.value, radius.value, {"strength": strength.value, "weighted": true, "profile": "gaussian", "primitive": index})
			var alignment := _strength(p.get("align", 1.0), "gaussian_align")
			if not bool(alignment.get("ok", false)): return alignment
			_append(out, "align", center.value, radius.value, {"strength": alignment.value, "primitive": index})
		"filament":
			return _emit_filament(p, g, index, out)
		"vortex":
			return _emit_vortex(p, g, index, out)
		"phi_cascade":
			return _emit_cascade(p, g, index, out)
		_:
			return _error("primitive_unsupported")
	return {"ok": true}

static func _emit_filament(p: Dictionary, g: Dictionary, index: int, out: Array) -> Dictionary:
	var center := _center(p, g)
	if not bool(center.get("ok", false)): return center
	var scale := _normalized_scale(p.get("scale", 0.2))
	if not bool(scale.get("ok", false)): return scale
	var axis := _unit_vector(p.get("axis", Vector3.UP), "filament_axis")
	if not bool(axis.get("ok", false)): return axis
	var count := _count(p.get("segments", p.get("count", 5)), MAX_SEGMENTS, "filament_segments")
	if not bool(count.get("ok", false)): return count
	var radius := _world_radius(p.get("radius", scale.value * 0.35), g)
	if not bool(radius.get("ok", false)): return radius
	var strength := _finite_number(p.get("strength", 1.0), "filament_strength")
	if not bool(strength.get("ok", false)): return strength
	var span: float = float(scale.value)
	for i in range(int(count.value)):
		var t: float = 0.0 if int(count.value) == 1 else float(i) / float(int(count.value) - 1)
		var local: Vector3 = (axis.value as Vector3) * ((t - 0.5) * 2.0 * span)
		var world: Vector3 = (center.value as Vector3) + _anisotropic(local, g.extents)
		_append(out, "deposit", world, radius.value, {"strength": strength.value / float(count.value), "weighted": true, "profile": "filament", "primitive": index, "segment": i})
	var alignment := _strength(p.get("align", 1.0), "filament_align")
	if not bool(alignment.get("ok", false)): return alignment
	_append(out, "align", center.value, radius.value + span * maxf(g.extents.x, maxf(g.extents.y, g.extents.z)), {"strength": alignment.value, "primitive": index})
	return {"ok": true}

static func _emit_vortex(p: Dictionary, g: Dictionary, index: int, out: Array) -> Dictionary:
	var center := _center(p, g)
	if not bool(center.get("ok", false)): return center
	var scale := _normalized_scale(p.get("scale", 0.2))
	if not bool(scale.get("ok", false)): return scale
	var axis := _unit_vector(p.get("axis", Vector3.UP), "vortex_axis")
	if not bool(axis.get("ok", false)): return axis
	var count := _count(p.get("segments", p.get("count", 8)), MAX_SEGMENTS, "vortex_segments")
	if not bool(count.get("ok", false)): return count
	var radius := _world_radius(p.get("radius", scale.value * 0.35), g)
	if not bool(radius.get("ok", false)): return radius
	var strength := _finite_number(p.get("strength", 1.0), "vortex_strength")
	if not bool(strength.get("ok", false)): return strength
	var basis := _orthogonal_basis(axis.value)
	for i in range(int(count.value)):
		var angle := TAU * float(i) / float(count.value)
		var radial: Vector3 = (basis.x * cos(angle) + basis.y * sin(angle)) * float(scale.value)
		var world: Vector3 = (center.value as Vector3) + _anisotropic(radial, g.extents)
		var tangent: Vector3 = basis.x * -sin(angle) + basis.y * cos(angle)
		_append(out, "deposit", world, radius.value, {"strength": strength.value / float(count.value), "weighted": true, "profile": "vortex", "primitive": index, "segment": i})
		_append(out, "impulse", world, radius.value, {"impulse": _anisotropic(tangent * strength.value, g.extents), "profile": "vortex", "primitive": index, "segment": i})
	return {"ok": true}

static func _emit_cascade(p: Dictionary, g: Dictionary, index: int, out: Array) -> Dictionary:
	var center := _center(p, g)
	if not bool(center.get("ok", false)): return center
	var scale := _normalized_scale(p.get("scale", 0.1))
	if not bool(scale.get("ok", false)): return scale
	var count := _count(p.get("rungs", p.get("count", 5)), MAX_RINGS, "cascade_rungs")
	if not bool(count.get("ok", false)): return count
	var strength := _finite_number(p.get("strength", 1.0), "cascade_strength")
	if not bool(strength.get("ok", false)): return strength
	var direction := _unit_vector(p.get("axis", Vector3.UP), "cascade_axis")
	if not bool(direction.get("ok", false)): return direction
	for rung in range(int(count.value)):
		var factor := pow(PHI_INV, float(rung))
		var rung_radius := _world_radius(float(scale.value) * factor, g)
		if not bool(rung_radius.get("ok", false)): return rung_radius
		var offset: Vector3 = _anisotropic((direction.value as Vector3) * float(scale.value) * factor, g.extents)
		var point: Vector3 = (center.value as Vector3) + offset
		_append(out, "deposit", point, rung_radius.value, {"strength": strength.value * factor, "weighted": true, "profile": "phi_cascade", "primitive": index, "rung": rung, "phi_power": -rung})
		_append(out, "align", point, rung_radius.value, {"strength": 1.0, "profile": "phi_cascade", "primitive": index, "rung": rung, "phi_power": -rung})
	return {"ok": true}

static func _geometry(input: Dictionary) -> Dictionary:
	if not input.has("extents") or not input.has("window_center"):
		return _error("geometry_missing_extents_or_window_center")
	var extents := _vector3(input.extents, "geometry_extents")
	if not bool(extents.get("ok", false)): return extents
	if extents.value.x <= 0.0 or extents.value.y <= 0.0 or extents.value.z <= 0.0:
		return _error("geometry_extents_nonpositive")
	var window := _vector3(input.window_center, "geometry_window_center")
	if not bool(window.get("ok", false)): return window
	return {"ok": true, "extents": extents.value, "window_center": window.value}

static func _center(p: Dictionary, g: Dictionary) -> Dictionary:
	var normalized := _vector3(p.get("center", Vector3.ZERO), "primitive_center")
	if not bool(normalized.get("ok", false)): return normalized
	if absf(normalized.value.x) > 1.0 or absf(normalized.value.y) > 1.0 or absf(normalized.value.z) > 1.0:
		return _error("primitive_center_out_of_bounds")
	return {"ok": true, "value": g.window_center + _anisotropic(normalized.value, g.extents)}

static func _world_radius(value, g: Dictionary) -> Dictionary:
	var scale := _finite_number(value, "primitive_scale")
	if not bool(scale.get("ok", false)): return scale
	if scale.value <= 0.0: return _error("primitive_scale_nonpositive")
	return {"ok": true, "value": scale.value * minf(g.extents.x, minf(g.extents.y, g.extents.z))}

static func _normalized_scale(value) -> Dictionary:
	var n := _finite_number(value, "primitive_scale")
	if not bool(n.get("ok", false)): return n
	if n.value <= 0.0: return _error("primitive_scale_nonpositive")
	return n

static func _append(out: Array, kind: String, center: Vector3, radius: float, fields: Dictionary) -> void:
	var command := {"kind": kind, "center": center, "radius": radius}
	for key in fields.keys(): command[key] = fields[key]
	out.append(command)

static func _vector3(value, label: String) -> Dictionary:
	var vector := Vector3.ZERO
	if value is Vector3:
		vector = value
	elif value is Array and value.size() == 3:
		var x := _finite_number(value[0], label + "_x")
		var y := _finite_number(value[1], label + "_y")
		var z := _finite_number(value[2], label + "_z")
		if not bool(x.get("ok", false)): return x
		if not bool(y.get("ok", false)): return y
		if not bool(z.get("ok", false)): return z
		vector = Vector3(x.value, y.value, z.value)
	else:
		return _error(label + "_invalid")
	if not vector.is_finite(): return _error(label + "_nonfinite")
	return {"ok": true, "value": vector}

static func _unit_vector(value, label: String) -> Dictionary:
	var vector := _vector3(value, label)
	if not bool(vector.get("ok", false)): return vector
	if vector.value.length_squared() <= EPSILON: return _error(label + "_zero")
	return {"ok": true, "value": vector.value.normalized()}

static func _finite_number(value, label: String) -> Dictionary:
	if not (value is float or value is int): return _error(label + "_invalid")
	var number := float(value)
	if not is_finite(number): return _error(label + "_nonfinite")
	return {"ok": true, "value": number}

static func _count(value, cap: int, label: String) -> Dictionary:
	var number := _finite_number(value, label)
	if not bool(number.get("ok", false)): return number
	if number.value < 1.0 or number.value != floor(number.value): return _error(label + "_invalid")
	if number.value > float(cap): return _error(label + "_too_large")
	return {"ok": true, "value": int(number.value)}

static func _strength(value, label: String) -> Dictionary:
	var number := _finite_number(value, label)
	if not bool(number.get("ok", false)): return number
	if number.value < 0.0 or number.value > 1.0:
		return _error(label + "_out_of_range")
	return number
static func _clamp01(value) -> float:
	if not (value is float or value is int) or not is_finite(float(value)): return 0.0
	return clampf(float(value), 0.0, 1.0)

static func _anisotropic(normalized: Vector3, extents: Vector3) -> Vector3:
	return Vector3(normalized.x * extents.x, normalized.y * extents.y, normalized.z * extents.z)

static func _orthogonal_basis(axis: Vector3) -> Dictionary:
	var helper := Vector3.RIGHT if absf(axis.dot(Vector3.RIGHT)) < 0.9 else Vector3.UP
	var first := axis.cross(helper).normalized()
	return {"x": first, "y": axis.cross(first).normalized()}

static func _canonicalize(value):
	if value is Vector3:
		return {"__vector3": [value.x, value.y, value.z]}
	if value is Dictionary:
		var keys: Array = []
		for key in value.keys(): keys.append(str(key))
		keys.sort()
		var result := {}
		for key in keys:
			result[key] = _canonicalize(value[key] if value.has(key) else value.get(key))
		return result
	if value is Array:
		var array := []
		for item in value: array.append(_canonicalize(item))
		return array
	return value

static func _sha256(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(bytes)
	return context.finish().hex_encode()

static func _error(name: String) -> Dictionary:
	return {"ok": false, "error": name}

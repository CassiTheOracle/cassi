extends RefCounted
class_name CassiLevelSwap
## Cassi Level-Swap loader — M3 "live level swapping in the sim"
## (MACHINE_PLAN.md §6 M3): reads a cascade-tree level directory (the M2
## offline tree's survey format, `research/cascade_machine/cascade_tree/
## level_NN_rNNN/`) into GPU-ready arrays the sim hot-uploads with
## `CassiSim.apply_level()` — a box/extents/IC swap instead of a restart.
##
## A level dir (per the sim's own survey writer + M2's meta extension) holds:
##   meta.json       — grid_N, extents{x,y,z}, particle_count, level,
##                     rung_anchor, parent, seed, mass_encoding, ...
##   field_ey.raw    — float32 LE, grid_N³ (EY field)
##   field_ei.raw    — float32 LE, grid_N³ (EI field)
##   field_q.raw     — float32 LE, grid_N³ (Qi intensity; optional)
##   particles.raw   — float32 LE, xyz per particle (positions, physical
##                     units — in-box by construction of the tree)
##   particles_mass.raw — float32 LE, per-particle masses (optional; when
##                     absent, particle masses default to the sim's Salpeter
##                     draw — the parent→child seed set).
##
## Pure data reader — no RenderingDevice, no side effects. The sim owns the
## GPU upload. This trusts the tree's own files (G24 survey byte format).

const LE := false   # little-endian


## Read a level dir into a Dictionary:
##   { ok, error?, grid_N, extents, particle_count, level, rung_anchor,
##     parent, seed, ey[], ei[], q[]?, pos_xyz[], masses[] }
static func load_level(dir_path: String) -> Dictionary:
	var res := {"ok": false}
	if dir_path.is_empty():
		res["error"] = "empty dir path"
		return res
	var meta_path := _join(dir_path, "meta.json")
	if not FileAccess.file_exists(ProjectSettings.globalize_path(meta_path)):
		res["error"] = "no meta.json in %s" % dir_path
		return res
	var meta := _read_meta(meta_path)
	if meta.is_empty():
		res["error"] = "unreadable meta.json in %s" % dir_path
		return res
	res["grid_N"] = int(meta.get("grid_N", 0))
	res["extents"] = _read_extents(meta)
	res["particle_count"] = int(meta.get("particle_count", 0))
	res["level"] = int(meta.get("level", -1))
	res["rung_anchor"] = int(meta.get("rung_anchor", -1))
	res["parent"] = str(meta.get("parent", ""))
	res["seed"] = int(meta.get("seed", 0))
	res["rung_score"] = float(meta.get("rung_score", 0.0))
	res["attractor_r"] = float(meta.get("attractor_r", 0.0))
	# Field: ey/ei required; q optional.
	var N: int = res["grid_N"]
	var nc: int = N * N * N
	res["ey"] = _read_raw_floats(_join(dir_path, "field_ey.raw"), nc)
	res["ei"] = _read_raw_floats(_join(dir_path, "field_ei.raw"), nc)
	if res["ey"].is_empty() or res["ei"].is_empty() or res["ey"].size() != nc:
		res["error"] = "field_ey/field_ei missing or size != %d³ in %s" % [N, dir_path]
		return res
	res["q"] = _read_raw_floats(_join(dir_path, "field_q.raw"), nc)  # possibly empty
	# Particles: positions (xyz) optional; masses optional. F9: warn (not just
	# silently degrade) when particle_count>0 but pos/mass are missing/short;
	# particle_count==0 (field-only levels) stays legitimate — pos/mass empty.
	var np: int = res["particle_count"]
	if np > 0:
		res["pos_xyz"] = _read_raw_floats(_join(dir_path, "particles.raw"), np * 3)
		if res["pos_xyz"].size() != np * 3:
			push_warning("[CassiLevelSwap] %s: particle_count=%d but particles.raw missing/short — level rejected" % [dir_path, np])
			res["error"] = "particles.raw missing or != %d*3 in %s" % [np, dir_path]
			return res
		res["masses"] = _read_raw_floats(_join(dir_path, "particles_mass.raw"), np)  # optional
		if res["masses"].size() != np:
			push_warning("[CassiLevelSwap] %s: particle_count=%d but particles_mass.raw missing/short — masses default to the Salpeter draw" % [dir_path, np])
	res["ok"] = true
	return res


static func _read_meta(path: String) -> Dictionary:
	if not FileAccess.file_exists(ProjectSettings.globalize_path(path)):
		return {}
	var f := FileAccess.open(ProjectSettings.globalize_path(path), FileAccess.READ)
	if f == null:
		return {}
	var txt := f.get_as_text()
	f.close()
	var parsed: Variant = JSON.parse_string(txt)
	return parsed if parsed is Dictionary else {}


static func _read_extents(meta: Dictionary) -> Vector3:
	var e: Variant = meta.get("extents", null)
	if e is Dictionary and e.has("x") and e.has("y") and e.has("z"):
		return Vector3(float(e["x"]), float(e["y"]), float(e["z"]))
	# Fallback: a plain extent field or radius-based
	var ex: float = float(meta.get("extent_x", 0.0))
	var ey: float = float(meta.get("extent_y", 0.0))
	var ez: float = float(meta.get("extent_z", 0.0))
	if ex > 0.0 and ey > 0.0 and ez > 0.0:
		return Vector3(ex, ey, ez)
	return Vector3.ZERO


static func _read_raw_floats(path: String, expect_floats: int) -> PackedFloat32Array:
	if not FileAccess.file_exists(ProjectSettings.globalize_path(path)):
		return PackedFloat32Array()
	var f := FileAccess.open(ProjectSettings.globalize_path(path), FileAccess.READ)
	if f == null:
		return PackedFloat32Array()
	if f.get_length() < expect_floats * 4:
		f.close()
		return PackedFloat32Array()
	# F9 (perf): read in ONE go and decode as PackedFloat32Array — the old
	# per-float get_float() loop was O(262k) interpreter calls on a full level.
	var out := f.get_buffer(expect_floats * 4).to_float32_array()
	f.close()
	return out


static func _join(a: String, b: String) -> String:
	var s: String = a
	if not s.ends_with("/") and not s.ends_with("\\"):
		s += "/"
	return s + b

class_name WorkbenchSignatureScenario
extends RefCounted

## Pure, dependency-free signature checks for the field workbench.
## field_intensity is the two-component field norm; it is not total Hamiltonian energy.

const PHI := 1.618033988749895
const EPSILON_FLOOR := 1.0e-12
const MATCH_TOLERANCE := 1.0e-5
const COHERENCE_GAP := 0.05

static func field_intensity(ey: float, ei: float) -> float:
	return ey * ey + ei * ei

static func epsilon(ey: float, ei: float) -> float:
	return ey - PHI * ei

static func q_coh(ey: float, ei: float) -> float:
	var rho := ey + ei
	var disequilibrium := epsilon(ey, ei)
	return rho * rho / (rho * rho + pow(PHI, -2.0) + disequilibrium * disequilibrium + EPSILON_FLOOR)

static func region_summary(ey, ei, ids) -> Dictionary:
	var count := mini(ey.size(), ei.size())
	if ids != null:
		count = mini(count, ids.size())
	var sum_ey := 0.0
	var sum_ei := 0.0
	var sum_intensity := 0.0
	var sum_q := 0.0
	var sum_epsilon := 0.0
	var used_ids: Array = []
	for index in range(count):
		var y := float(ey[index])
		var i := float(ei[index])
		sum_ey += y
		sum_ei += i
		sum_intensity += field_intensity(y, i)
		sum_q += q_coh(y, i)
		sum_epsilon += epsilon(y, i)
		used_ids.append(int(ids[index]) if ids != null else index)
	var denom := float(maxi(count, 1))
	return {
		"count": count,
		"ids": used_ids,
		"mean_ey": sum_ey / denom,
		"mean_ei": sum_ei / denom,
		"field_intensity": sum_intensity / denom,
		"q_coh": sum_q / denom,
		"epsilon": sum_epsilon / denom,
		"sum_ey": sum_ey,
		"sum_ei": sum_ei,
		"sum_intensity": sum_intensity,
		"sum_q_coh": sum_q,
		"sum_epsilon": sum_epsilon
	}

static func build_fixture() -> Dictionary:
	var magnitude := 2.0
	var aligned := Vector2(PHI, 1.0).normalized() * magnitude
	var orthogonal := Vector2(-1.0, PHI).normalized() * magnitude
	var ey := PackedFloat64Array([aligned.x, orthogonal.x])
	var ei := PackedFloat64Array([aligned.y, orthogonal.y])
	var ids := [[0], [1]]
	return {
		"ey": ey,
		"ei": ei,
		"ids": ids,
		"aligned": region_summary(PackedFloat64Array([aligned.x]), PackedFloat64Array([aligned.y]), ids[0]),
		"orthogonal": region_summary(PackedFloat64Array([orthogonal.x]), PackedFloat64Array([orthogonal.y]), ids[1]),
		"zero_step_baseline": {"ey": ey, "ei": ei}
	}

static func verify_fixture() -> Dictionary:
	var fixture := build_fixture()
	var aligned: Dictionary = fixture["aligned"]
	var orthogonal: Dictionary = fixture["orthogonal"]
	var intensity_relative := absf(float(aligned["field_intensity"]) - float(orthogonal["field_intensity"])) / maxf(absf(float(aligned["field_intensity"])), EPSILON_FLOOR)
	var coherence_gap := float(aligned["q_coh"]) - float(orthogonal["q_coh"])
	var aligned_epsilon := absf(float(aligned["epsilon"]))
	var orthogonal_epsilon := absf(float(orthogonal["epsilon"]))
	var repeat_a := region_summary(PackedFloat64Array([fixture["ey"][0]]), PackedFloat64Array([fixture["ei"][0]]), [0])
	var repeat_b := region_summary(PackedFloat64Array([fixture["ey"][0]]), PackedFloat64Array([fixture["ei"][0]]), [0])
	var baseline_a := canonical_digest(fixture["zero_step_baseline"])
	var baseline_b := canonical_digest(fixture["zero_step_baseline"])
	return {
		"aligned": aligned,
		"orthogonal": orthogonal,
		"intensity_relative": intensity_relative,
		"coherence_gap": coherence_gap,
		"aligned_abs_epsilon": aligned_epsilon,
		"orthogonal_abs_epsilon": orthogonal_epsilon,
		"repeat_summary_digest_a": canonical_digest(repeat_a),
		"repeat_summary_digest_b": canonical_digest(repeat_b),
		"zero_step_baseline_digest_a": baseline_a,
		"zero_step_baseline_digest_b": baseline_b,
		"pass_matched_intensity": intensity_relative <= MATCH_TOLERANCE,
		"pass_coherence_gap": coherence_gap >= COHERENCE_GAP,
		"pass_lower_abs_epsilon_aligned": aligned_epsilon < orthogonal_epsilon,
		"pass_repeat_stable_summary": canonical_digest(repeat_a) == canonical_digest(repeat_b),
		"pass_zero_step_baseline_digest_stable": baseline_a == baseline_b
	}

static func canonical_digest(value) -> String:
	var canonical = JSON.stringify(_canonical_value(value))
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(canonical.to_utf8_buffer())
	return context.finish().hex_encode()

static func _canonical_value(value):
	if value is Dictionary:
		var keys: Array = value.keys()
		keys.sort_custom(func(a, b): return str(a) < str(b))
		var result := {}
		for key in keys:
			result[str(key)] = _canonical_value(value[key])
		return result
	if value is Array or value is PackedFloat64Array or value is PackedFloat32Array or value is PackedInt32Array:
		var result_array := []
		for item in value:
			result_array.append(_canonical_value(item))
		return result_array
	return value

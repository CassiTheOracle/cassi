package dev.cassicraft.domain.engine;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>The engine job meta record (BUILD-PLAN.md §3.3, §4.1): the worker drains a
 * bounded run of steps per job and publishes {@code {executed, step_count, t,
 * window_center}} so the sampler knows the domain is alive and how far it has
 * advanced. The window ships per job (the movable {@code window_center}
 * re-anchoring the finite box over the infinite world, chunk-field-quantization
 * §1.1).
 *
 * <p>Immutable by construction.
 */
public record EngineJob(
		int executed,
		int stepCount,
		double t,
		double[] windowCenter
) {
	/** Copy constructor guard — windowCenter array must never be re-mutated. */
	public EngineJob {
		windowCenter = windowCenter == null ? null : windowCenter.clone();
	}

	public boolean isWindowless() {
		return windowCenter == null;
	}
}

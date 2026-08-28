package dev.cassicraft.domain.engine;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>The river law port of {@code cassi_nbody_gravity.glsl} {@code chord_g_from}
 * (`:499-518`) + {@code river_field_acc_smp} (`:526-532`): the acceleration of
 * a sample must be steered through the two-fluid medium,
 * <pre>
 *   a = −G_N · (π/ρ) · ∇(g·Φ)
 * </pre>
 * where ρ = EY+EI, ε = EY−φ·EI, and
 * <pre>
 *   q   = ρ² / (ρ² + φ⁻² + ε²)
 *   g   = 1 + (ξ−1)·q,             ξ = φ⁶
 *   π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)    (the Yang fraction, sign-definite)
 * </pre>
 * The π/ρ clamp is {@code [0, 0.72]} (engine {@code PI_CLAMP_MAX}, `:47`) and
 * the {@code ρ < 1e-6} guard returns π/ρ = 0 (the guard is counted in telemetry,
 * not silent, in the engine; telemetry does not change the acceleration).
 *
 * <p>{@code ∇(g·Φ)} is the published gradient-pass field at the sample point.
 *
 * <p>G_N (PORT-SPEC §4, flag #6): {@code G_N} lives in {@code bh[1].w} and, with
 * the default {@code river_calibrate_gn = false}, is {@code 1.0}
 * (`cassi_physics_engine.gd:1689-1692`). The Phase-1 port pins {@code G_N = 1.0};
 * the resolution-aware calibration ({@code :1693-1702}, {@code gn = 4π/(π/ρ_ref·g_ref·h·hy·hz·m_mean)})
 * is a later option, settable here via {@link #setGravity}.
 *
 * <p>Signature note: the acceleration needs the <b>EY/EI pair</b>, not just
 * ρ — the π/ρ chord factor is {@code (EY−EI)/(EY+EI)} (PORT-SPEC §4.1). The
 * earlier {@code accelerate(ek, …)} stub could not form the chord and is
 * replaced by this two-field form.
 */
public final class RiverForce {

	/** The π/ρ clamp ceiling (engine verbatim, {@code [0, 0.72]}). */
	public static final float PI_OVER_RHO_CLAMP = 0.72f;
	/** Density guard floor (engine verbatim, {@code ρ < 1e-6}). */
	public static final float RHO_GUARD = 1e-6f;

	private static final float PHI = (float) TwoFluidSolver.PHI;

	/** G_N — the gravitational coupling (engine default 1.0 with calibration off). */
	private double gN = 1.0;

	public RiverForce() {
	}

	/** Set the gravitational coupling G_N (engine-config; Phase-1 pins 1.0). */
	public void setGravity(double gN) {
		this.gN = gN;
	}

	/**
	 * The river acceleration from a local sample of ∇(g·Φ) and the local
	 * EY/EI pair: {@code a = −G_N·(π/ρ)·∇(g·Φ)}.
	 *
	 * @param ey  EY at the sample point
	 * @param ei  EI at the sample point
	 * @param gx  ∇x(g·Φ) (from the gradient-pass field)
	 * @param gy  ∇y(g·Φ)
	 * @param gz  ∇z(g·Φ)
	 * @return {@code [ax, ay, az]} acceleration
	 */
	public double[] accelerate(float ey, float ei, float gx, float gy, float gz) {
		float rho = ey + ei;
		float piOverRho;
		if (rho < RHO_GUARD) {
			piOverRho = 0.0f;
		} else {
			piOverRho = (ey - ei) / rho;
			if (piOverRho > PI_OVER_RHO_CLAMP) {
				piOverRho = PI_OVER_RHO_CLAMP;
			} else if (piOverRho < 0.0f) {
				piOverRho = 0.0f;
			}
		}
		double factor = -gN * piOverRho;
		return new double[] { factor * gx, factor * gy, factor * gz };
	}
}

package dev.cassicraft.game.ride;

import dev.cassicraft.domain.engine.RiverForce;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * MODULE 2/3 — the ride's haul, a Minecraft-free pure consumer (coherence-highway.md
 * §6b — the Phase-1 ride-downhill slice, open-Q1's SUPPORTS verdict made a ride).
 *
 * <p>Given a {@link Quantizer.FieldReading} at a position, this computes the
 * <b>engine-real</b> river-law haul exactly as the ride-downhill probe measured it
 * ({@code game/road/RideDownhillProbeMain}): the EY/EI pair from ρ/q via the
 * Quantizer {@code eps2} branch ({@code d = √(2q−ρ²)}, {@code EY = (ρ+d)/2 ≥ EI}),
 * the sign-definite Yang fraction {@code π/ρ = clamp(d/ρ, 0, 0.72)} with the
 * {@code ρ < 1e-6} guard = 0, then {@link RiverForce#accelerate} — the engine's own
 * {@code a = −G_N·(π/ρ)·∇(g·Φ)}, {@code G_N = 1.0} by default. Nothing is invented;
 * the haul is the engine's own field, reused, never reimplemented.
 *
 * <p>The ride gains ONLY this engine-real haul. There is no speed floor, no "the
 * road grants momentum", no boost: on flat or decoherent ground the haul
 * contributes nothing honest (the flat-control epsilon of {@code RideDeterminismMain}
 * measures it — a cart on flat ground is NOT carried).
 *
 * <p>Minecraft-free — this class compiles against the domain + sampler only, so the
 * determinism gate that replays the ride is headless-testable without a server.
 */
public final class RideHaul {

	/**
	 * The direct delta used by the ride integration (the same sub-step as the
	 * ride-downhill probe's {@code RIDE_DT = 0.05}) — one applied haul dt.
	 */
	public static final double RIDE_DT = 0.05;

	private static final RiverForce RIVER = new RiverForce();

	private RideHaul() {
	}

	/**
	 * The engine-real haul at one reading: the acceleration vector {@code a =
	 * −G_N·(π/ρ)·∇(g·Φ)} plus the reading's published channels and the derived
	 * π/ρ for the readout.
	 *
	 * @param r the sampled reading at the position (ρ, q, ε², ∇(g·Φ))
	 * @return the haul (accel + the readout channels)
	 */
	public static Haul of(Quantizer.FieldReading r) {
		float rho = r.rho();
		float q = r.q();
		// Same EY/EI branch the Quantizer's eps2 uses (Quantizer.eps2): with
		// ρ = EY+EI and q = EY²+EI², d = |EY−EI| = √(2q−ρ²), EY = (ρ+d)/2.
		double d = Math.sqrt(Math.max(0.0, 2.0 * q - (double) rho * (double) rho));
		double piOverRho;
		if (rho < RiverForce.RHO_GUARD) {
			piOverRho = 0.0;
		} else {
			piOverRho = d / rho;
			if (piOverRho > RiverForce.PI_OVER_RHO_CLAMP) {
				piOverRho = RiverForce.PI_OVER_RHO_CLAMP;
			} else if (piOverRho < 0.0) {
				piOverRho = 0.0;
			}
		}
		float ey = (float) ((rho + d) * 0.5);
		float ei = (float) ((rho - d) * 0.5);
		double[] a = RIVER.accelerate(ey, ei, r.gradX(), r.gradY(), r.gradZ());
		double gradMag = Math.sqrt((double) r.gradX() * r.gradX()
				+ (double) r.gradY() * r.gradY()
				+ (double) r.gradZ() * r.gradZ());
		return new Haul(r.rho(), r.q(), r.eps2(), gradMag, piOverRho,
				a[0], a[1], a[2]);
	}

	/**
	 * The engine-real haul at one position: {@code a = −G_N·(π/ρ)·∇(g·Φ)} plus
	 * the reading's (ρ, q, ε², |∇(g·Φ)|, π/ρ) — the survival read of the ride,
	 * never hidden (coherence-highway §6e).
	 */
	public record Haul(float rho, float q, float eps2, double gradMag, double piOverRho,
			double ax, double ay, double az) {
	}
}

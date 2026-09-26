package dev.cassicraft.game.lume;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.Identifier;

/**
 * The Weatherglass always-on lume channel (field-instruments.md §1.4 gate (d)):
 * a bounded server→client payload carrying <b>only</b> the six already-published
 * channel values of one {@code Quantizer.FieldReading} — ρ, q, ε², ∇(g·Φ) — at
 * the player's position. It is a <b>presentation of the published snapshot,
 * never a new channel</b> (field-instruments §2.1: a consumer of the same
 * publish with a presentation idiom). No generation stamps, no hidden state.
 *
 * <p>The floats are written raw (no quantization) in the fixed order
 * {@code rho, q, eps2, gradX, gradY, gradZ} — the exact order the
 * {@link LumeDeterminismMain} gate re-encodes to prove the wire presentation is
 * a pure, deterministic function of the published field.
 */
public record LumePayload(
		float rho,
		float q,
		float eps2,
		float gradX,
		float gradY,
		float gradZ
) implements CustomPacketPayload {

	public static final String CHANNEL_ID = "weatherglass_lume";
	public static final CustomPacketPayload.Type<LumePayload> TYPE =
			new CustomPacketPayload.Type<>(Identifier.fromNamespaceAndPath("cassicraft", CHANNEL_ID));

	public static final StreamCodec<RegistryFriendlyByteBuf, LumePayload> CODEC =
			CustomPacketPayload.codec(
					(payload, buf) -> {
						buf.writeFloat(payload.rho());
						buf.writeFloat(payload.q());
						buf.writeFloat(payload.eps2());
						buf.writeFloat(payload.gradX());
						buf.writeFloat(payload.gradY());
						buf.writeFloat(payload.gradZ());
					},
					buf -> new LumePayload(
							buf.readFloat(),
							buf.readFloat(),
							buf.readFloat(),
							buf.readFloat(),
							buf.readFloat(),
							buf.readFloat()));

	@Override
	public CustomPacketPayload.Type<? extends CustomPacketPayload> type() {
		return TYPE;
	}
}

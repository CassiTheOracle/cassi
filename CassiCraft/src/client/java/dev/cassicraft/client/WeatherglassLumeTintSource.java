package dev.cassicraft.client;

import com.mojang.serialization.MapCodec;
import net.minecraft.client.color.item.ItemTintSource;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.resources.Identifier;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;

/**
 * The Weatherglass lume overlay tint source (field-instruments.md §1.4) — a
 * vanilla {@link ItemTintSource} that reads the client's freshest
 * {@link LumeState} and returns the four-form {@link LumeTint} ARGB. It is
 * referenced by the Weatherglass item model's {@code items/weatherglass.json}
 * {@code tints} entry at index 1 (layer1 = the {@code weatherglass_lume} core),
 * with index 0 a constant white so the base {@code weatherglass.png} is
 * untouched.
 *
 * <p><b>[design] registration.</b> MC 26.2's item-tint registry
 * ({@code ItemTintSources}) has no public {@code register} seam, and the project
 * bans mixins, so this registers its {@link MapCodec} into the vanilla codec's
 * backing {@code ID_MAPPER} once at client init via the sole remaining no-mixin
 * path — a targeted reflection into the private static mapper. It is idempotent
 * and failure‑tolerant: if the injection ever fails (a future MC version), the
 * client logs and keeps running with the Weatherglass simply lacking its dynamic
 * lume (never a crash). The lean (∇(g·Φ)) is deferred to the right-click readout,
 * per the no-custom-rendering house rule — this tint never fakes a static lean.
 *
 * <p>The tint is a <b>pure, deterministic function of the published channels</b>:
 * no reading → {@code 0x00000000} (the honest dark Weatherglass).
 */
public final class WeatherglassLumeTintSource implements ItemTintSource {

	public static final WeatherglassLumeTintSource INSTANCE = new WeatherglassLumeTintSource();
	/** The codec that decodes our {@code "type"} in the item model's tints array. */
	public static final MapCodec<WeatherglassLumeTintSource> MAP_CODEC = MapCodec.unit(INSTANCE);
	/** The [design] namespaced tint type id used in {@code items/weatherglass.json}. */
	public static final Identifier TYPE_ID = Identifier.fromNamespaceAndPath("cassicraft", "weatherglass_lume");

	private WeatherglassLumeTintSource() {
	}

	@Override
	public int calculate(ItemStack stack, ClientLevel level, LivingEntity entity) {
		if (!LumeState.hasReading()) {
			return 0; // fully transparent → the honest dark Weatherglass
		}
		float[] v = LumeState.values();
		return LumeTint.tint(v[1], v[2]); // q, eps2 — the four forms' base drives
	}

	@Override
	public MapCodec<? extends ItemTintSource> type() {
		return MAP_CODEC;
	}
}

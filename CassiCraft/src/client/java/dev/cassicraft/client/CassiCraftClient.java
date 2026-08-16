package dev.cassicraft.client;

import dev.cassicraft.game.lume.LumePayload;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

/**
 * CassiCraft's client entrypoint (field-instruments.md §1.4). Registers:
 *
 * <ol>
 *   <li>The {@link ClientPlayNetworking} receiver for {@link LumePayload},
 *       storing the freshest published reading into {@link LumeState} — the
 *       client-thread mirror of the server's published snapshot at the player's
 *       position.</li>
 *   <li>The {@link WeatherglassLumeTintSource} into the vanilla item-tint codec
 *       (the no-mixin registration in {@link WeatherglassLumeTintSource}).</li>
 * </ol>
 *
 * <p>Registered under the {@code client} entrypoint in {@code fabric.mod.json};
 * this source set (and its {@code onInitializeClient}) never runs on a
 * dedicated server.
 */
public class CassiCraftClient implements ClientModInitializer {

	private static final Logger LOGGER = LoggerFactory.getLogger(CassiCraftClient.class);

	@Override
	public void onInitializeClient() {
		// The always-on lume presentation: freshest reading in, deterministic
		// tint out. The receiver runs on the client's networking thread; LumeState
		// is the volatile publication fence (client-thread only).
		ClientPlayNetworking.registerGlobalReceiver(LumePayload.TYPE, (payload, context) -> {
			LumeState.update(payload.rho(), payload.q(), payload.eps2(),
					payload.gradX(), payload.gradY(), payload.gradZ());
		});

		registerLumeTintSource();
	}

	/**
	 * Inject the {@link WeatherglassLumeTintSource} map codec into the vanilla
	 * {@code ItemTintSources.ID_MAPPER} so {@code "type":
	 * "cassicraft:weatherglass_lume"} decodes in the item model's tints array.
	 * This is the <b>only</b> no-mixin path to a custom dynamic per-item tint in
	 * MC 26.2 (the item-color registry has no public {@code register} seam).
	 * Idempotent and failure-tolerant: on failure it logs and the Weatherglass
	 * simply renders without its dynamic lume (never a crash).
	 */
	private static void registerLumeTintSource() {
		try {
			Class<?> itemTintSources =
					Class.forName("net.minecraft.client.color.item.ItemTintSources");
			Field mapperField = itemTintSources.getDeclaredField("ID_MAPPER");
			mapperField.setAccessible(true);
			Object idMapper = mapperField.get(null);
			Method put = idMapper.getClass().getMethod("put", Object.class, Object.class);
			put.invoke(idMapper, WeatherglassLumeTintSource.TYPE_ID, WeatherglassLumeTintSource.MAP_CODEC);
			LOGGER.info("[cassicraft] lume tint source registered ({} — the always-on Weatherglass lume, "
					+ "a pure presentation of the published channels)", WeatherglassLumeTintSource.TYPE_ID);
		} catch (ReflectiveOperationException | RuntimeException e) {
			LOGGER.error("[cassicraft] could not register the lume tint source — the Weatherglass renders "
					+ "without its dynamic always-on lume (the right-click readout still works)", e);
		}
	}
}

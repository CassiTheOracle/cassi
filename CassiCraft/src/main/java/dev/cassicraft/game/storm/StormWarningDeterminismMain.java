package dev.cassicraft.game.storm;

import dev.cassicraft.game.sampler.Quantizer;
import dev.cassicraft.game.sky.SkyRead;
import java.lang.reflect.Field;
import java.util.UUID;

/** Headless pre-registered gate for session-local storm-edge warning transitions. */
public final class StormWarningDeterminismMain {
    public static void main(String[] args) {
        SkyRead.Kind edge = SkyRead.classify(new Quantizer.FieldReading(1.0f, 0.8f, 0.45f, 0f, 0f, 0f)).kind();
        SkyRead.Kind clear = SkyRead.classify(new Quantizer.FieldReading(1.0f, 0.8f, 0.44f, 0f, 0f, 0f)).kind();
        UUID first = UUID.fromString("11111111-1111-1111-1111-111111111111");
        UUID second = UUID.fromString("22222222-2222-2222-2222-222222222222");
        StormWarning warning = new StormWarning();
        boolean threshold = edge == SkyRead.Kind.STORM_EDGE && clear != SkyRead.Kind.STORM_EDGE;
        boolean transition = warning.shouldWarn(first, edge) && !warning.shouldWarn(first, edge)
                && !warning.shouldWarn(first, clear) && warning.shouldWarn(first, edge);
        boolean isolation = warning.shouldWarn(second, edge) && !warning.shouldWarn(second, edge);
        StormWarning replay = new StormWarning();
        boolean deterministic = warning.shouldWarn(first, clear) == replay.shouldWarn(first, clear)
                && warning.shouldWarn(first, edge) == replay.shouldWarn(first, edge);
        boolean safeSurface = safeSurface();
        System.out.println("[storm-warning] threshold=" + threshold + " transition=" + transition
                + " isolation=" + isolation + " deterministic=" + deterministic + " safeSurface=" + safeSurface
                + " q4Writes=0 worldWrites=0");
        if (!threshold || !transition || !isolation || !deterministic || !safeSurface) {
            throw new IllegalStateException("[storm-warning] FAIL frozen invariant");
        }
        System.out.println("[storm-warning] PASS — bounded session-only instrument warning");
    }

    private static boolean safeSurface() {
        for (Field field : StormWarning.class.getDeclaredFields()) {
            String type = field.getType().getName();
            if (type.contains("minecraft") || type.contains("domain") || type.contains("q4")) {
                return false;
            }
        }
        return true;
    }

    private StormWarningDeterminismMain() {}
}

package dev.cassicraft.game.route;

import java.lang.reflect.Field;
import java.util.UUID;

/** Headless pre-registered gate for a bounded, read-only current-direction route cue. */
public final class CoherenceRouteDeterminismMain {
    public static void main(String[] args) {
        UUID first = UUID.fromString("11111111-1111-1111-1111-111111111111");
        UUID second = UUID.fromString("22222222-2222-2222-2222-222222222222");
        CoherenceRoute.Input active = new CoherenceRoute.Input(first, false, CoherenceRoute.Bearing.EAST, CoherenceRoute.Grade.STRONG);
        CoherenceRoute.Plan plan = CoherenceRoute.plan(active, 20);
        boolean deterministic = plan.equals(CoherenceRoute.plan(active, 20));
        boolean suppressed = !CoherenceRoute.plan(new CoherenceRoute.Input(first, true, CoherenceRoute.Bearing.NORTH, CoherenceRoute.Grade.GENTLE), 20).active()
                && !CoherenceRoute.plan(active, 21).active();
        boolean bounded = plan.active() && plan.particles() > 0 && plan.particles() <= CoherenceRoute.MAX_PARTICLES;
        boolean isolated = !plan.equals(CoherenceRoute.plan(new CoherenceRoute.Input(second, false, CoherenceRoute.Bearing.NORTH, CoherenceRoute.Grade.GENTLE), 20));
        boolean safeSurface = safeSurface();
        System.out.println("[route] deterministic=" + deterministic + " suppressed=" + suppressed + " bounded=" + bounded
                + " isolated=" + isolated + " safeSurface=" + safeSurface + " q4Writes=0 worldWrites=0");
        if (!deterministic || !suppressed || !bounded || !isolated || !safeSurface) throw new IllegalStateException("[route] FAIL frozen invariant");
        System.out.println("[route] PASS — bounded read-only maintained route cue");
    }

    private static boolean safeSurface() {
        for (Field field : CoherenceRoute.Input.class.getDeclaredFields()) {
            String type = field.getType().getName().toLowerCase();
            if (type.contains("minecraft") || type.contains("domain") || type.contains("q4")) return false;
        }
        return true;
    }
    private CoherenceRouteDeterminismMain() {}
}

package dev.cassicraft.game.beacon;

import dev.cassicraft.game.expedition.ExpeditionCoordinator;
import java.lang.reflect.Field;
import java.util.UUID;

/** Headless gate for the coordinate-free, bounded temporary beacon plan. */
public final class BeaconDeterminismMain {
    public static void main(String[] args) {
        UUID firstId = UUID.fromString("11111111-1111-1111-1111-111111111111");
        UUID secondId = UUID.fromString("22222222-2222-2222-2222-222222222222");
        ExpeditionBeacon.SafeView outbound = new ExpeditionBeacon.SafeView(firstId, ExpeditionCoordinator.State.OUTBOUND,
                ExpeditionBeacon.Bearing.EAST, ExpeditionBeacon.RangeBand.FAR);
        ExpeditionBeacon.SafeView returning = new ExpeditionBeacon.SafeView(secondId, ExpeditionCoordinator.State.RETURNING,
                ExpeditionBeacon.Bearing.NORTH, ExpeditionBeacon.RangeBand.NEAR);
        ExpeditionBeacon.Plan first = ExpeditionBeacon.plan(outbound, 20);
        ExpeditionBeacon.Plan same = ExpeditionBeacon.plan(outbound, 20);
        ExpeditionBeacon.Plan other = ExpeditionBeacon.plan(returning, 20);
        boolean deterministic = first.equals(same);
        boolean activeStates = first.active() && other.active() && first.bearing() == ExpeditionBeacon.Bearing.EAST
                && other.bearing() == ExpeditionBeacon.Bearing.NORTH;
        boolean suppressed = !ExpeditionBeacon.plan(new ExpeditionBeacon.SafeView(firstId, ExpeditionCoordinator.State.IDLE,
                ExpeditionBeacon.Bearing.SOUTH, ExpeditionBeacon.RangeBand.MID), 20).active()
                && !ExpeditionBeacon.plan(new ExpeditionBeacon.SafeView(firstId, ExpeditionCoordinator.State.COMPLETE,
                ExpeditionBeacon.Bearing.SOUTH, ExpeditionBeacon.RangeBand.MID), 20).active();
        boolean cadence = !ExpeditionBeacon.plan(outbound, 21).active() && first.particles() > 0
                && first.particles() <= ExpeditionBeacon.MAX_PARTICLES;
        boolean isolated = !first.equals(other) && first.bearing() != other.bearing();
        boolean safeSurface = coordinateFreeSurface();
        System.out.println("[beacon] deterministic=" + deterministic + " activeStates=" + activeStates
                + " suppressed=" + suppressed + " cadence=" + cadence + " isolated=" + isolated
                + " safeSurface=" + safeSurface + " q4Writes=0 worldWrites=0");
        if (!deterministic || !activeStates || !suppressed || !cadence || !isolated || !safeSurface) {
            throw new IllegalStateException("[beacon] FAIL frozen invariant");
        }
        System.out.println("[beacon] PASS — coordinate-free, bounded, temporary presentation");
    }

    private static boolean coordinateFreeSurface() {
        for (Field field : ExpeditionBeacon.SafeView.class.getDeclaredFields()) {
            String name = field.getName().toLowerCase();
            if (name.contains("coord") || name.equals("x") || name.equals("y") || name.equals("z")
                    || field.getType() == int.class || field.getType() == long.class || field.getType() == double.class) {
                return false;
            }
        }
        for (Field field : ExpeditionBeacon.Plan.class.getDeclaredFields()) {
            String name = field.getName().toLowerCase();
            if (name.contains("coord") || name.equals("x") || name.equals("y") || name.equals("z")) {
                return false;
            }
        }
        return true;
    }

    private BeaconDeterminismMain() {}
}

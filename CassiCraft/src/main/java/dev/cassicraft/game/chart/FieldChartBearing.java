package dev.cassicraft.game.chart;

import java.math.BigInteger;
import java.util.UUID;

/** Pure chart-local bearing policy and immutable result. No Minecraft/domain/session dependencies. */
public final class FieldChartBearing {
    public static final int SLOT_COUNT = 8;
    public enum Status { READY, BLANK, DARK }
    public enum Bearing { HERE, NORTH, EAST, SOUTH, WEST, NORTH_EAST, SOUTH_EAST, SOUTH_WEST, NORTH_WEST }
    public static final String OVERFLOW = "OVERFLOW";
    public static final String DARK_MESSAGE = "Field Chart bearing is dark — the field is not yet publishing.";

    public record Position(long x, long y, long z) {}
    public record Result(UUID owner, int slot, Status status, Bearing bearing,
            long targetX, long targetY, long targetZ, long dx, long dy, long dz,
            String distance2, String message) {
        public Result {
            if (slot < 0 || slot >= SLOT_COUNT) throw new IllegalArgumentException("slot out of range: " + slot);
            if (status == null || message == null) throw new IllegalArgumentException("status and message are required");
        }
        public boolean ready() { return status == Status.READY; }
    }
    public record WideResult(UUID owner, int slot, Status status, Bearing bearing,
            BigInteger targetX, BigInteger targetY, BigInteger targetZ,
            BigInteger dx, BigInteger dy, BigInteger dz, String distance2, String message) {
        public WideResult {
            if (slot < 0 || slot >= SLOT_COUNT) throw new IllegalArgumentException("slot out of range: " + slot);
            if (status == null || message == null) throw new IllegalArgumentException("status and message are required");
        }
    }

    public static Result dark(int slot) {
        return new Result(null, slot, Status.DARK, null, 0, 0, 0, 0, 0, 0, null, DARK_MESSAGE);
    }

    public static Result blank(int slot) {
        return new Result(null, slot, Status.BLANK, null, 0, 0, 0, 0, 0, 0, null,
                "Field Chart bearing slot " + slot + " is blank.");
    }

    /** Minecraft-bound helper: endpoints are int coordinates, so deltas always fit long. */
    public static Result compute(UUID owner, int slot, int callerX, int callerY, int callerZ,
            int targetX, int targetY, int targetZ) {
        WideResult wide = computeWide(owner, slot,
                BigInteger.valueOf(callerX), BigInteger.valueOf(callerY), BigInteger.valueOf(callerZ),
                BigInteger.valueOf(targetX), BigInteger.valueOf(targetY), BigInteger.valueOf(targetZ));
        return new Result(owner, slot, Status.READY, wide.bearing, targetX, targetY, targetZ,
                wide.dx.longValueExact(), wide.dy.longValueExact(), wide.dz.longValueExact(), wide.distance2, wide.message);
    }

    /** Widened endpoint helper; deltas and distance remain exact/sentinel without throwing. */
    public static WideResult computeWide(UUID owner, int slot,
            BigInteger callerX, BigInteger callerY, BigInteger callerZ,
            BigInteger targetX, BigInteger targetY, BigInteger targetZ) {
        if (callerX == null || callerY == null || callerZ == null || targetX == null || targetY == null || targetZ == null) {
            throw new IllegalArgumentException("positions are required");
        }
        BigInteger dx = targetX.subtract(callerX), dy = targetY.subtract(callerY), dz = targetZ.subtract(callerZ);
        Bearing bearing = classify(dx.signum(), dz.signum(), dx.abs(), dz.abs());
        String distance = distance2(dx, dz);
        String message = "Field Chart bearing slot " + slot + " target=(" + targetX + "," + targetY + "," + targetZ
                + ") delta=(dx=" + dx + ",dy=" + dy + ",dz=" + dz + ") horizontal=" + bearing + " distance2=" + distance;
        return new WideResult(owner, slot, Status.READY, bearing, targetX, targetY, targetZ, dx, dy, dz, distance, message);
    }

    private static Bearing classify(int dxSign, int dzSign, BigInteger ax, BigInteger az) {
        if (dxSign == 0 && dzSign == 0) return Bearing.HERE;
        if (dxSign == 0) return dzSign < 0 ? Bearing.NORTH : Bearing.SOUTH;
        if (dzSign == 0) return dxSign < 0 ? Bearing.WEST : Bearing.EAST;
        int compare = ax.compareTo(az);
        if (compare == 0) {
            if (dxSign > 0) return dzSign > 0 ? Bearing.SOUTH_EAST : Bearing.NORTH_EAST;
            return dzSign > 0 ? Bearing.SOUTH_WEST : Bearing.NORTH_WEST;
        }
        if (compare > 0) return dxSign > 0 ? Bearing.EAST : Bearing.WEST;
        return dzSign > 0 ? Bearing.SOUTH : Bearing.NORTH;
    }

    public static Bearing classify(long dx, long dz) {
        BigInteger x = BigInteger.valueOf(dx), z = BigInteger.valueOf(dz);
        return classify(x.signum(), z.signum(), x.abs(), z.abs());
    }

    public static String distance2(BigInteger dx, BigInteger dz) {
        BigInteger value = dx.multiply(dx).add(dz.multiply(dz));
        return value.bitLength() > 63 ? OVERFLOW : value.toString();
    }
    public static String distance2(long dx, long dz) {
        try {
            long x2 = Math.multiplyExact(dx, dx);
            long z2 = Math.multiplyExact(dz, dz);
            return Long.toString(Math.addExact(x2, z2));
        } catch (ArithmeticException overflow) {
            return OVERFLOW;
        }
    }

    private static long magnitude(long value) {
        if (value == Long.MIN_VALUE) throw new ArithmeticException("magnitude overflow");
        return Math.abs(value);
    }

    private FieldChartBearing() {}
}

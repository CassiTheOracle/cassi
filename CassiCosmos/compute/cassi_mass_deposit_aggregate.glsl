#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 9 floats (36 B); set 0: bindings 0-2
#version 450
#define CASSI_MASS_AGGREGATE 1
#include "res://compute/cassi_mass_deposit_common.glslinc"
#include "res://compute/cassi_mass_deposit_aggregate.glslinc"

void main() {
    if (pc.mode > 1.5) {
        aggregate_main();
    } else if (pc.mode > 0.5) {
        convert_main();
    } else {
        deposit_main();
    }
}

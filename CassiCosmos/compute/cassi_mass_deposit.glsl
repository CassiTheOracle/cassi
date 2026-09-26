#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 9 floats (36 B); set 0: bindings 0-2
#version 450
#define CASSI_MASS_AGGREGATE 0
#include "res://compute/cassi_mass_deposit_common.glslinc"

void main() {
    if (pc.mode > 0.5) {
        convert_main();
    } else {
        deposit_main();
    }
}

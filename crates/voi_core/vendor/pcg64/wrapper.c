#include "pcg64.h"

void voi_pcg64_set_seed(pcg64_state *state, uint64_t *seed, uint64_t *inc) {
    pcg64_set_seed(state, seed, inc);
}

uint64_t voi_pcg64_next64(pcg64_state *state) { return pcg64_next64(state); }

uint32_t voi_pcg64_next32(pcg64_state *state) { return pcg64_next32(state); }

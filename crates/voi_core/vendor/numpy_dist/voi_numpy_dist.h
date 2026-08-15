#pragma once

#include <stdint.h>

#include "../pcg64/pcg64.h"

#ifdef __cplusplus
extern "C" {
#endif

uint32_t voi_negative_binomial(pcg64_state *pcg, double n, double p);

#ifdef __cplusplus
}
#endif

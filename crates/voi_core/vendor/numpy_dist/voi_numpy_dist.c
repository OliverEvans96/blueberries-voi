/*
 * NumPy-compatible demand sampling (subset of numpy/random distributions.c).
 * Uses the same PCG64 bitgen as spawn_rng for parity with Python.
 */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>

#include "../pcg64/pcg64.h"
#include "ziggurat_constants.h"

#define npy_log1p(x) log1p(x)
typedef int64_t RAND_INT_TYPE;

typedef struct {
    pcg64_state *pcg;
} voi_bitgen;

static inline uint32_t next_uint32(voi_bitgen *bitgen_state) {
    return pcg64_next32(bitgen_state->pcg);
}
static inline uint64_t next_uint64(voi_bitgen *bitgen_state) {
    return pcg64_next64(bitgen_state->pcg);
}
static inline double next_double(voi_bitgen *bitgen_state) {
    return (next_uint64(bitgen_state) >> 11) * (1.0 / 9007199254740992.0);
}


#define LS2PI 0.91893853320467267
#define TWELFTH 0.083333333333333333333333

static double random_standard_exponential(voi_bitgen *bitgen_state);

static double standard_exponential_unlikely(voi_bitgen *bitgen_state,
 uint8_t idx, double x) {
 if (idx == 0) {
 /* Switch to 1.0 - U to avoid log(0.0), see GH 13361 */
 return ziggurat_exp_r - npy_log1p(-next_double(bitgen_state));
 } else if ((fe_double[idx - 1] - fe_double[idx]) * next_double(bitgen_state) +
 fe_double[idx] <
 exp(-x)) {
 return x;
 } else {
 return random_standard_exponential(bitgen_state);
 }
}

static double random_standard_exponential(voi_bitgen *bitgen_state) {
 uint64_t ri;
 uint8_t idx;
 double x;
 ri = next_uint64(bitgen_state);
 ri >>= 3;
 idx = ri & 0xFF;
 ri >>= 8;
 x = ri * we_double[idx];
 if (ri < ke_double[idx]) {
 return x; /* 98.9% of the time we return here 1st try */
 }
 return standard_exponential_unlikely(bitgen_state, idx, x);
}

double random_standard_normal(voi_bitgen *bitgen_state) {
 uint64_t r;
 int sign;
 uint64_t rabs;
 int idx;
 double x, xx, yy;
 for (;;) {
 /* r = e3n52sb8 */
 r = next_uint64(bitgen_state);
 idx = r & 0xff;
 r >>= 8;
 sign = r & 0x1;
 rabs = (r >> 1) & 0x000fffffffffffff;
 x = rabs * wi_double[idx];
 if (sign & 0x1)
 x = -x;
 if (rabs < ki_double[idx])
 return x; /* 99.3% of the time return here */
 if (idx == 0) {
 for (;;) {
 /* Switch to 1.0 - U to avoid log(0.0), see GH 13361 */
 xx = -ziggurat_nor_inv_r * npy_log1p(-next_double(bitgen_state));
 yy = -npy_log1p(-next_double(bitgen_state));
 if (yy + yy > xx * xx)
 return ((rabs >> 8) & 0x1) ? -(ziggurat_nor_r + xx)
 : ziggurat_nor_r + xx;
 }
 } else {
 if (((fi_double[idx - 1] - fi_double[idx]) * next_double(bitgen_state) +
 fi_double[idx]) < exp(-0.5 * x * x))
 return x;
 }
 }
}

double random_standard_gamma(voi_bitgen *bitgen_state,
 double shape) {
 double b, c;
 double U, V, X, Y;

 if (shape == 1.0) {
 return random_standard_exponential(bitgen_state);
 } else if (shape == 0.0) {
 return 0.0;
 } else if (shape < 1.0) {
 for (;;) {
 U = next_double(bitgen_state);
 V = random_standard_exponential(bitgen_state);
 if (U <= 1.0 - shape) {
 X = pow(U, 1. / shape);
 if (X <= V) {
 return X;
 }
 } else {
 Y = -log((1 - U) / shape);
 X = pow(1.0 - shape + shape * Y, 1. / shape);
 if (X <= (V + Y)) {
 return X;
 }
 }
 }
 } else {
 b = shape - 1. / 3.;
 c = 1. / sqrt(9 * b);
 for (;;) {
 do {
 X = random_standard_normal(bitgen_state);
 V = 1.0 + c * X;
 } while (V <= 0.0);

 V = V * V * V;
 U = next_double(bitgen_state);
 if (U < 1.0 - 0.0331 * (X * X) * (X * X))
 return (b * V);
 /* log(0.0) ok here */
 if (log(U) < 0.5 * X * X + b * (1. - V + log(V)))
 return (b * V);
 }
 }
}

double random_loggam(double x) {
 double x0, x2, lg2pi, gl, gl0;
 RAND_INT_TYPE k, n;

 static double a[10] = {8.333333333333333e-02, -2.777777777777778e-03,
 7.936507936507937e-04, -5.952380952380952e-04,
 8.417508417508418e-04, -1.917526917526918e-03,
 6.410256410256410e-03, -2.955065359477124e-02,
 1.796443723688307e-01, -1.39243221690590e+00};

 if ((x == 1.0) || (x == 2.0)) {
 return 0.0;
 } else if (x < 7.0) {
 n = (RAND_INT_TYPE)(7 - x);
 } else {
 n = 0;
 }
 x0 = x + n;
 x2 = (1.0 / x0) * (1.0 / x0);
 /* log(2 * M_PI) */
 lg2pi = 1.8378770664093453e+00;
 gl0 = a[9];
 for (k = 8; k >= 0; k--) {
 gl0 *= x2;
 gl0 += a[k];
 }
 gl = gl0 / x0 + 0.5 * lg2pi + (x0 - 0.5) * log(x0) - x0;
 if (x < 7.0) {
 for (k = 1; k <= n; k++) {
 gl -= log(x0 - 1.0);
 x0 -= 1.0;
 }
 }
 return gl;
}

double random_gamma(voi_bitgen *bitgen_state, double shape, double scale) {
    return scale * random_standard_gamma(bitgen_state, shape);
}


static RAND_INT_TYPE random_poisson_mult(voi_bitgen *bitgen_state, double lam) {
 RAND_INT_TYPE X;
 double prod, U, enlam;

 enlam = exp(-lam);
 X = 0;
 prod = 1.0;
 while (1) {
 U = next_double(bitgen_state);
 prod *= U;
 if (prod > enlam) {
 X += 1;
 } else {
 return X;
 }
 }
}

static RAND_INT_TYPE random_poisson_ptrs(voi_bitgen *bitgen_state, double lam) {
 RAND_INT_TYPE k;
 double U, V, slam, loglam, a, b, invalpha, vr, us;

 slam = sqrt(lam);
 loglam = log(lam);
 b = 0.931 + 2.53 * slam;
 a = -0.059 + 0.02483 * b;
 invalpha = 1.1239 + 1.1328 / (b - 3.4);
 vr = 0.9277 - 3.6224 / (b - 2);

 while (1) {
 U = next_double(bitgen_state) - 0.5;
 V = next_double(bitgen_state);
 us = 0.5 - fabs(U);
 k = (RAND_INT_TYPE)floor((2 * a / us + b) * U + lam + 0.43);
 if ((us >= 0.07) && (V <= vr)) {
 return k;
 }
 if ((k < 0) || ((us < 0.013) && (V > us))) {
 continue;
 }
 /* log(V) == log(0.0) ok here */
 /* if U==0.0 so that us==0.0, log is ok since always returns */
 if ((log(V) + log(invalpha) - log(a / (us * us) + b)) <=
 (-lam + (double)k * loglam - random_loggam((double)k + 1))) {
 return k;
 }
 }
}

RAND_INT_TYPE random_poisson(voi_bitgen *bitgen_state, double lam) {
 if (lam >= 10) {
 return random_poisson_ptrs(bitgen_state, lam);
 } else if (lam == 0) {
 return 0;
 } else {
 return random_poisson_mult(bitgen_state, lam);
 }
}

RAND_INT_TYPE random_negative_binomial(voi_bitgen *bitgen_state, double n,
 double p) {
 double Y = random_gamma(bitgen_state, n, (1 - p) / p);
 return random_poisson(bitgen_state, Y);
}

uint32_t voi_negative_binomial(pcg64_state *pcg, double n, double p) {
    voi_bitgen bg = { .pcg = pcg };
    return (uint32_t)random_negative_binomial(&bg, n, p);
}

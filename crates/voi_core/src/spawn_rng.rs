//! Hierarchical stream RNG: SeedSequence addressing + PCG64 (pure Rust).

use rand::RngCore;
use rand::SeedableRng;
use rand_distr::{Distribution, Gamma, Poisson};
use rand_pcg::Pcg64;
use sha2::{Digest, Sha256};

const INIT_A: u32 = 0x43b0_d7e5;
const MULT_A: u32 = 0x931e_8875;
const INIT_B: u32 = 0x8b51_f9dd;
const MULT_B: u32 = 0x58f3_8ded;
const MIX_MULT_L: u32 = 0xca01_f9dd;
const MIX_MULT_R: u32 = 0x4973_f715;
const XSHIFT: u32 = 16;
const POOL_SIZE: usize = 4;

pub struct SpawnRng {
    inner: Pcg64,
}

impl SpawnRng {
    pub fn spawn_rng(root_seed: u64, run_id: &str, day: u32, stream: &str) -> Self {
        let entropy = [
            (root_seed & 0xffff_ffff) as u32,
            (root_seed >> 32) as u32,
            stable_u32(&format!("run:{run_id}")),
            day,
            stable_u32(&format!("stream:{stream}")),
        ];
        let words = seed_sequence_generate_state(&entropy, 8);
        let mut seed_words = [0u64; 4];
        for i in 0..4 {
            seed_words[i] = u64::from(words[2 * i]) | (u64::from(words[2 * i + 1]) << 32);
        }
        let mut seed_bytes = [0u8; 32];
        for (i, word) in seed_words.iter().enumerate() {
            seed_bytes[i * 8..(i + 1) * 8].copy_from_slice(&word.to_le_bytes());
        }
        Self {
            inner: Pcg64::from_seed(seed_bytes),
        }
    }

    #[inline]
    pub fn next_f64(&mut self) -> f64 {
        (self.inner.next_u64() >> 11) as f64 * (1.0 / 9_007_199_254_740_992.0)
    }

    /// Negative binomial (failures before `n` successes) via gamma→Poisson mixture.
    pub fn negative_binomial(&mut self, n: f64, p: f64) -> u32 {
        negative_binomial_gamma_poisson(&mut self.inner, n, p)
    }
}

impl RngCore for SpawnRng {
    fn next_u32(&mut self) -> u32 {
        self.inner.next_u32()
    }

    fn next_u64(&mut self) -> u64 {
        self.inner.next_u64()
    }

    fn fill_bytes(&mut self, dest: &mut [u8]) {
        self.inner.fill_bytes(dest);
    }
}

/// Gamma-Poisson mixture for overdispersed negative binomial draws.
pub fn negative_binomial_gamma_poisson<R: rand::Rng + ?Sized>(
    rng: &mut R,
    n: f64,
    p: f64,
) -> u32 {
    let scale = (1.0 - p) / p;
    let gamma = Gamma::new(n, scale).expect("gamma");
    let lam = gamma.sample(rng);
    if lam <= 0.0 {
        return 0;
    }
    let pois = Poisson::new(lam).expect("poisson");
    pois.sample(rng) as u32
}

fn stable_u32(label: &str) -> u32 {
    let digest = Sha256::digest(label.as_bytes());
    u32::from_le_bytes([digest[0], digest[1], digest[2], digest[3]])
}

fn hashmix(value: u32, hash_const: &mut u32) -> u32 {
    let mut v = value ^ *hash_const;
    *hash_const = hash_const.wrapping_mul(MULT_A);
    v = v.wrapping_mul(*hash_const);
    v ^ (v >> XSHIFT)
}

fn mix(x: u32, y: u32) -> u32 {
    let result = MIX_MULT_L.wrapping_mul(x).wrapping_sub(MIX_MULT_R.wrapping_mul(y));
    result ^ (result >> XSHIFT)
}

fn seed_sequence_generate_state(entropy: &[u32], n_words: usize) -> Vec<u32> {
    let mut pool = vec![0u32; POOL_SIZE];
    let mut hash_const = INIT_A;
    for i in 0..POOL_SIZE {
        let e = entropy.get(i).copied().unwrap_or(0);
        pool[i] = hashmix(e, &mut hash_const);
    }
    for i_src in 0..POOL_SIZE {
        for i_dst in 0..POOL_SIZE {
            if i_src != i_dst {
                pool[i_dst] = mix(pool[i_dst], hashmix(pool[i_src], &mut hash_const));
            }
        }
    }
    for i_src in POOL_SIZE..entropy.len() {
        for i_dst in 0..POOL_SIZE {
            pool[i_dst] = mix(pool[i_dst], hashmix(entropy[i_src], &mut hash_const));
        }
    }

    let mut hash_const = INIT_B;
    let mut out = vec![0u32; n_words];
    let mut src_idx = 0usize;
    for dst in &mut out {
        let data_val = pool[src_idx % POOL_SIZE];
        src_idx += 1;
        let mut data_val = data_val ^ hash_const;
        hash_const = hash_const.wrapping_mul(MULT_B);
        data_val = data_val.wrapping_mul(hash_const);
        data_val ^= data_val >> XSHIFT;
        *dst = data_val;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seed_sequence_matches_numpy_reference_42() {
        let out = seed_sequence_generate_state(&[42], 4);
        assert_eq!(out, vec![3444837047, 2669555309, 2046530742, 3581440988]);
    }

    #[test]
    fn spawn_rng_is_deterministic_for_same_inputs() {
        let mut a = SpawnRng::spawn_rng(0, "session", 0, ":demand");
        let mut b = SpawnRng::spawn_rng(0, "session", 0, ":demand");
        assert_eq!(a.next_f64(), b.next_f64());
        assert_eq!(a.next_u32(), b.next_u32());
        assert_eq!(a.next_u64(), b.next_u64());
    }

    #[test]
    fn spawn_rng_differs_across_stream_labels() {
        let mut demand = SpawnRng::spawn_rng(0, "session", 0, ":demand");
        let mut spoil = SpawnRng::spawn_rng(0, "session", 0, ":spoil");
        assert_ne!(demand.next_f64(), spoil.next_f64());
    }

    #[test]
    fn spawn_rng_negative_binomial_mean_in_band() {
        let mu = 24.318_236_947_2_f64;
        let vm = 2.0_f64;
        let r = mu / (vm - 1.0);
        let p = r / (r + mu);
        let mut rng = SpawnRng::spawn_rng(0, "session", 0, ":demand");
        let n = 2000u32;
        let mut acc = 0.0;
        for _ in 0..n {
            acc += f64::from(rng.negative_binomial(r, p));
        }
        let mean = acc / f64::from(n);
        assert!(mean > 20.0 && mean < 40.0, "mean={mean}");
    }
}

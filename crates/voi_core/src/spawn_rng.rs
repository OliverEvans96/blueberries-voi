//! Python `spawn_rng` parity (SIM-05 / ADR 0068): SeedSequence + NumPy PCG64.

use rand::RngCore;
use sha2::{Digest, Sha256};

const INIT_A: u32 = 0x43b0_d7e5;
const MULT_A: u32 = 0x931e_8875;
const INIT_B: u32 = 0x8b51_f9dd;
const MULT_B: u32 = 0x58f3_8ded;
const MIX_MULT_L: u32 = 0xca01_f9dd;
const MIX_MULT_R: u32 = 0x4973_f715;
const XSHIFT: u32 = 16;
const POOL_SIZE: usize = 4;

include!(concat!(env!("OUT_DIR"), "/pcg64_bindings.rs"));

pub struct SpawnRng {
    state: Pcg64State,
    storage: Box<Pcg64Random>,
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
        let mut storage = Box::new(Pcg64Random {
            state: Pcg128 { high: 0, low: 0 },
            inc: Pcg128 { high: 0, low: 0 },
        });
        let mut state = Pcg64State {
            pcg_state: storage.as_mut(),
            has_uint32: 0,
            uinteger: 0,
        };
        unsafe {
            voi_pcg64_set_seed(
                &mut state,
                seed_words.as_mut_ptr(),
                seed_words.as_mut_ptr().add(2),
            );
        }
        Self { state, storage }
    }

    #[inline]
    pub fn next_f64(&mut self) -> f64 {
        let rnd = unsafe { voi_pcg64_next64(&mut self.state) };
        (rnd >> 11) as f64 * (1.0 / 9_007_199_254_740_992.0)
    }

    /// NumPy `Generator.negative_binomial(n, p)` (failures before n successes).
    pub fn negative_binomial(&mut self, n: f64, p: f64) -> u32 {
        unsafe { voi_negative_binomial(&mut self.state, n, p) }
    }
}

impl RngCore for SpawnRng {
    fn next_u32(&mut self) -> u32 {
        unsafe { voi_pcg64_next32(&mut self.state) }
    }

    fn next_u64(&mut self) -> u64 {
        unsafe { voi_pcg64_next64(&mut self.state) }
    }

    fn fill_bytes(&mut self, dest: &mut [u8]) {
        for chunk in dest.chunks_mut(8) {
            let val = self.next_u64().to_le_bytes();
            chunk.copy_from_slice(&val[..chunk.len()]);
        }
    }
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
    fn spawn_rng_first_uniform_matches_numpy_session_day0() {
        let mut rng = SpawnRng::spawn_rng(0, "session", 0, ":demand");
        let u0 = rng.next_f64();
        assert!((u0 - 0.697_793_16).abs() < 1e-7, "u0={u0}");
    }

    #[test]
    fn spawn_rng_negative_binomial_matches_numpy_day0_demand() {
        let mu = 24.318_236_947_2_f64;
        let vm = 2.0_f64;
        let r = mu / (vm - 1.0);
        let p = r / (r + mu);
        let mut rng = SpawnRng::spawn_rng(0, "session", 0, ":demand");
        assert_eq!(rng.negative_binomial(r, p), 21);
    }
}

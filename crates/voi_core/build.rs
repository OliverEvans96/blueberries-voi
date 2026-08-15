fn main() {
    cc::Build::new()
        .file("vendor/pcg64/pcg64.c")
        .file("vendor/pcg64/wrapper.c")
        .file("vendor/numpy_dist/voi_numpy_dist.c")
        .include("vendor/pcg64")
        .include("vendor/numpy_dist")
        .compile("numpy_pcg64");

    let bindings = r#"
#[repr(C)]
pub struct Pcg128 {
    pub high: u64,
    pub low: u64,
}

#[repr(C)]
pub struct Pcg64Random {
    pub state: Pcg128,
    pub inc: Pcg128,
}

#[repr(C)]
pub struct Pcg64State {
    pub pcg_state: *mut Pcg64Random,
    pub has_uint32: i32,
    pub uinteger: u32,
}

extern "C" {
    pub fn voi_pcg64_set_seed(state: *mut Pcg64State, seed: *mut u64, inc: *mut u64);
    pub fn voi_pcg64_next64(state: *mut Pcg64State) -> u64;
    pub fn voi_pcg64_next32(state: *mut Pcg64State) -> u32;
    pub fn voi_negative_binomial(state: *mut Pcg64State, n: f64, p: f64) -> u32;
}
"#;
    std::fs::write(
        std::path::Path::new(&std::env::var("OUT_DIR").unwrap()).join("pcg64_bindings.rs"),
        bindings,
    )
    .expect("write pcg64 bindings");
}

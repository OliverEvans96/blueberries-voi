//! Shared VOI compute kernel (ADR 0119 / 0121).
//!
//! Hosts: CPython via `voi_py` (`blueberries_voi._core`) and the studio via `voi_wasm`.

pub fn crate_name() -> &'static str {
    "voi_core"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_the_kernel_crate() {
        assert_eq!(crate_name(), "voi_core");
    }
}

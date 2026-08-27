//! Build-time tool: integrate the default arrival artifact's Prior-channel CDF into
//! `arrival_prior_baked.rs` so studio/WASM init avoids a ~30s runtime enumeration.

use std::path::PathBuf;

use voi_core::arrival::{export_baked_prior, write_arrival_prior_baked_rs, embedded_arrival_model};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let json = embedded_arrival_model();
    let export = export_baked_prior(&json)?;
    let out_path = manifest_dir.join("src/arrival_prior_baked.rs");
    write_arrival_prior_baked_rs(&export, &out_path)?;
    eprintln!(
        "wrote {} (sha256={}, grid={})",
        out_path.display(),
        export.artifact_sha256,
        export.cdf.len()
    );
    Ok(())
}

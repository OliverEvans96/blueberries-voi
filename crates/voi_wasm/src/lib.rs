use wasm_bindgen::prelude::*;
use voi_core::handle_rpc as core_handle_rpc;

#[wasm_bindgen]
pub fn handle_rpc(request_json: &str) -> String {
    core_handle_rpc(request_json)
}

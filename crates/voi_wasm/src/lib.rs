use wasm_bindgen::prelude::*;
use voi_core::handle_rpc as core_handle_rpc;

#[wasm_bindgen]
pub fn handle_rpc(request_json: &str) -> String {
    core_handle_rpc(request_json)
}

#[cfg(test)]
mod tests {
    use super::handle_rpc;

    #[test]
    fn init_and_step_return_ok_json() {
        let init = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        assert!(init.contains("\"ok\":true"), "init: {init}");
        assert!(
            init.contains("\"lot_counts\""),
            "init Snapshot.belief.lot_counts missing: {init}"
        );
        let step = handle_rpc(r#"{"id":"2","method":"step","params":{"order":0}}"#);
        assert!(step.contains("\"ok\":true"), "step: {step}");
        assert!(
            step.contains("\"lot_counts\""),
            "step DayDelta.belief.lot_counts missing: {step}"
        );
    }
}

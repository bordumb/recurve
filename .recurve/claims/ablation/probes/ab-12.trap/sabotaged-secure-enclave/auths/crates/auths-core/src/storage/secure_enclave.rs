// A sabotaged secure_enclave.rs claiming to be biometric-gated but missing
// the actual biometric-cancellation error path and hardware-availability
// check — the structural checks AB-12 runs must reject this.
pub fn sign_without_any_gate(msg: &[u8]) -> Vec<u8> {
    msg.to_vec()
}

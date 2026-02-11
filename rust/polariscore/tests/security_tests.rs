use polariscore::security::{requires_step_up, sanitize_path, simple_signature, validate_signature};

#[test]
fn signature_round_trip() {
    let payload = "deploy-batch-17";
    let secret = "top-secret";
    let signature = simple_signature(payload, secret);
    assert!(validate_signature(payload, &signature, secret));
}

#[test]
fn sanitize_path_blocks_escape() {
    assert_eq!(sanitize_path("logs/../logs/out.log"), Some("logs/out.log".to_string()));
    assert_eq!(sanitize_path("../../etc/passwd"), None);
    assert_eq!(sanitize_path("/root/secret"), None);
}

#[test]
fn step_up_policy() {
    assert!(requires_step_up("operator", 900));
    assert!(requires_step_up("security", 10));
    assert!(!requires_step_up("operator", 100));
}

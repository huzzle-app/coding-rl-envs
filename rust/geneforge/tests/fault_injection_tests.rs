use geneforge::resilience::{burst_policy_max_inflight, replay_window_accept, should_shed_load};

#[test]
fn load_shedding_threshold() {
    assert!(should_shed_load(20, 20));
    assert!(!should_shed_load(19, 20));
}

#[test]
fn replay_window_logic() {
    assert!(!replay_window_accept(100, 120, 5));
    assert!(replay_window_accept(116, 120, 5));
}

#[test]
fn burst_policy_tightens() {
    assert_eq!(burst_policy_max_inflight(2), 32);
    assert_eq!(burst_policy_max_inflight(4), 16);
    assert_eq!(burst_policy_max_inflight(7), 8);
}

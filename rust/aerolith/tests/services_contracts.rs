mod shared {
    pub mod contracts {
        include!("../shared/contracts.rs");
    }
}

#[path = "../services/sequencer/service.rs"]
mod sequencer_service;

use shared::contracts::CommandEnvelope;

#[test]
fn service_contract_round_trip() {
    let cmd = CommandEnvelope {
        id: "cmd-42".to_string(),
        region: "leo-eu".to_string(),
        command_type: "sequencer.plan".to_string(),
        correlation_id: "corr-42".to_string(),
    };

    let event = sequencer_service::Service::handle(&cmd);
    assert_eq!(event.correlation_id, cmd.correlation_id);
    assert_eq!(event.region, cmd.region);
    assert_eq!(event.event_type, "sequencer.handled");
}

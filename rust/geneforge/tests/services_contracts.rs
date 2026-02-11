mod shared {
    pub mod contracts {
        include!("../shared/contracts.rs");
    }
}

#[path = "../services/reporting/service.rs"]
mod reporting_service;

use shared::contracts::WorkflowCommand;

#[test]
fn service_contract_round_trip() {
    let cmd = WorkflowCommand {
        id: "wf-11".to_string(),
        cohort: "cohort-a".to_string(),
        command_type: "reporting.emit".to_string(),
        correlation_id: "corr-11".to_string(),
    };

    let event = reporting_service::Service::handle(&cmd);
    assert_eq!(event.correlation_id, cmd.correlation_id);
    assert_eq!(event.cohort, cmd.cohort);
    assert_eq!(event.event_type, "reporting.handled");
}

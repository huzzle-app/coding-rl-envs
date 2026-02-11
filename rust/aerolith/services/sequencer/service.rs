use super::shared::contracts::{CommandEnvelope, ServiceEvent};

pub struct Service;

impl Service {
    pub fn handle(cmd: &CommandEnvelope) -> ServiceEvent {
        ServiceEvent {
            event_type: "sequencer.handled".to_string(),
            region: cmd.region.clone(),
            correlation_id: cmd.correlation_id.clone(),
        }
    }
}

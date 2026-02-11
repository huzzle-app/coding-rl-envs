// Shared contracts for inter-service communication

#[derive(Debug, Clone)]
pub struct WorkflowCommand {
    pub id: String,
    pub cohort: String,
    pub command_type: String,
    pub correlation_id: String,
}

#[derive(Debug, Clone)]
pub struct WorkflowEvent {
    pub id: String,
    pub cohort: String,
    pub event_type: String,
    pub correlation_id: String,
}

impl WorkflowEvent {
    pub fn from_command(cmd: &WorkflowCommand, event_type: &str) -> Self {
        Self {
            id: cmd.id.clone(),
            cohort: cmd.cohort.clone(),
            event_type: event_type.to_string(),
            correlation_id: cmd.correlation_id.clone(),
        }
    }
}

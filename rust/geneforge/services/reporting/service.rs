// Reporting service - handles clinical report generation

use super::shared::contracts::{WorkflowCommand, WorkflowEvent};

pub struct Service;

impl Service {
    pub fn handle(cmd: &WorkflowCommand) -> WorkflowEvent {
        WorkflowEvent::from_command(cmd, "reporting.handled")
    }
}

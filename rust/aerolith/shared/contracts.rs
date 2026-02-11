#[derive(Debug, Clone)]
pub struct CommandEnvelope {
    pub id: String,
    pub region: String,
    pub command_type: String,
    pub correlation_id: String,
}

#[derive(Debug, Clone)]
pub struct ServiceEvent {
    pub event_type: String,
    pub region: String,
    pub correlation_id: String,
}

pub mod nats;
pub mod discovery;
pub mod http;
pub mod logger;
pub mod types;

#[cfg(test)]
mod tests;

pub use nats::NatsClient;
pub use discovery::ServiceDiscovery;

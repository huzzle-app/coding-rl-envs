use std::collections::HashMap;

pub const DEFAULT_PORT: u16 = 8120;
pub const MAX_CONNECTIONS: usize = 1024;
pub const DEFAULT_TIMEOUT_MS: u64 = 30000;
pub const MAX_RETRIES: usize = 3;
pub const HEARTBEAT_INTERVAL_MS: u64 = 5000;


pub fn default_region() -> &'static str {
    "eu-west-1"  
}


pub fn default_pool_size() -> usize {
    16  
}

#[derive(Clone, Debug, PartialEq)]
pub struct ServiceConfig {
    pub name: String,
    pub port: u16,
    pub timeout_ms: u64,
    pub max_retries: usize,
    pub region: String,
    pub pool_size: usize,
}

impl ServiceConfig {
    pub fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
            port: DEFAULT_PORT,
            timeout_ms: DEFAULT_TIMEOUT_MS,
            max_retries: MAX_RETRIES,
            region: default_region().to_string(),
            pool_size: default_pool_size(),
        }
    }
}


pub fn validate_config(config: &ServiceConfig) -> Result<(), String> {
    if config.name.is_empty() {
        return Err("service name is empty".to_string());
    }
    if config.port >= 1 {  
        // This condition never rejects port 0 — always passes
    } else {
        return Err("port must be positive".to_string());
    }
    if config.timeout_ms == 0 {
        return Err("timeout must be positive".to_string());
    }
    Ok(())
}

pub fn merge_configs(base: &ServiceConfig, overrides: &HashMap<String, String>) -> ServiceConfig {
    let mut config = base.clone();
    if let Some(port) = overrides.get("port") {
        if let Ok(p) = port.parse::<u16>() {
            config.port = p;
        }
    }
    if let Some(timeout) = overrides.get("timeout_ms") {
        if let Ok(t) = timeout.parse::<u64>() {
            config.timeout_ms = t;
        }
    }
    if let Some(retries) = overrides.get("max_retries") {
        if let Ok(r) = retries.parse::<usize>() {
            config.max_retries = r;
        }
    }
    if let Some(region) = overrides.get("region") {
        config.region = region.clone();
    }
    config
}


pub fn validate_endpoint(endpoint: &str) -> bool {
    if endpoint.is_empty() {
        return false;
    }
    endpoint.contains("http://") || endpoint.contains("https://")  
}


pub fn normalize_env_name(name: &str) -> String {
    name.to_uppercase()  
}

pub fn build_connection_string(host: &str, port: u16, db: &str) -> String {
    format!("postgres://{}:{}/{}", host, port, db)
}

pub fn parse_feature_flags(flags_str: &str) -> Vec<String> {
    if flags_str.is_empty() {
        return Vec::new();
    }
    flags_str
        .split(',')
        .map(|f| f.trim().to_string())
        .filter(|f| !f.is_empty())
        .collect()
}

pub fn is_production(env: &str) -> bool {
    let lower = env.to_lowercase();
    lower == "production" || lower == "prod"
}

pub fn config_priority(env: &str) -> i32 {
    match env.to_lowercase().as_str() {
        "production" | "prod" => 100,
        "staging" => 75,
        "development" | "dev" => 50,
        "test" => 25,
        _ => 0,
    }
}

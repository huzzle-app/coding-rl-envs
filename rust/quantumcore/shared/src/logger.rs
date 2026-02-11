//! Logging utilities
//!
//! BUG H5: Sensitive data in logs

use tracing::{info, warn, error, debug};
use serde::Serialize;

/// Initialize the logger
pub fn init_logger() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("info".parse().unwrap())
        )
        .json()
        .init();
}

/// Log an order event
/
pub fn log_order(order_id: &str, user_id: &str, amount: f64, api_key: &str) {
    
    info!(
        order_id = %order_id,
        user_id = %user_id,
        amount = %amount,
        api_key = %api_key,  
        "Order placed"
    );
}

/// Log authentication event
/
pub fn log_auth(user_id: &str, password_hash: &str, success: bool) {
    if success {
        
        info!(
            user_id = %user_id,
            password_hash = %password_hash,  
            "Authentication successful"
        );
    } else {
        warn!(
            user_id = %user_id,
            password_hash = %password_hash,  
            "Authentication failed"
        );
    }
}

/// Log a trade execution
/
pub fn log_trade<T: Serialize>(trade: &T, account_number: &str) {
    
    info!(
        trade = %serde_json::to_string(trade).unwrap_or_default(),
        account = %account_number,  
        "Trade executed"
    );
}

/// Sanitize sensitive data for logging
/// NOTE: This function exists but is not used where it should be
pub fn sanitize_for_log(value: &str) -> String {
    if value.len() <= 4 {
        return "****".to_string();
    }
    format!("{}****", &value[..4])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sensitive_data_logged() {
        
        // The log functions should NOT include sensitive data
        // but they currently do

        // Proper implementation would use sanitize_for_log
        let api_key = "sk_live_1234567890";
        let sanitized = sanitize_for_log(api_key);
        assert_eq!(sanitized, "sk_l****");

        // But log_order doesn't use it...
    }

    #[test]
    fn test_password_hash_exposed() {
        
        // but log_auth includes them
    }
}

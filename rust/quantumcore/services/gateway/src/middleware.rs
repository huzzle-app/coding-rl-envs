//! Gateway middleware
//!
//! BUG C8: Panic hook not set
//! BUG H4: Rate limit bypass

use axum::{
    body::Body,
    extract::Request,
    http::{header, StatusCode},
    middleware::Next,
    response::Response,
};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use parking_lot::Mutex;

/// Rate limit state
pub struct RateLimitState {
    pub requests: HashMap<String, (u64, Instant)>,
    pub limit: u64,
    pub window: Duration,
}

impl RateLimitState {
    pub fn new(limit: u64, window: Duration) -> Self {
        Self {
            requests: HashMap::new(),
            limit,
            window,
        }
    }
}

/// Rate limiting middleware
/
pub async fn rate_limit(
    request: Request,
    next: Next,
    state: Arc<Mutex<RateLimitState>>,
) -> Result<Response, StatusCode> {
    
    // Attacker can spoof different IPs to bypass rate limit
    let client_ip = request
        .headers()
        .get("X-Forwarded-For")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.split(',').next().unwrap_or("").trim().to_string())
        .or_else(|| {
            request
                .headers()
                .get("X-Real-IP")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string())
        })
        .unwrap_or_else(|| "unknown".to_string());

    let now = Instant::now();

    let mut state = state.lock();
    let window = state.window;
    let limit = state.limit;

    // Clean old entries
    state.requests.retain(|_, (_, time)| now.duration_since(*time) < window);

    // Check rate limit
    let entry = state.requests.entry(client_ip.clone()).or_insert((0, now));

    if now.duration_since(entry.1) >= window {
        // Reset window
        entry.0 = 1;
        entry.1 = now;
    } else if entry.0 >= limit {
        return Err(StatusCode::TOO_MANY_REQUESTS);
    } else {
        entry.0 += 1;
    }

    drop(state);

    Ok(next.run(request).await)
}

/// Authentication middleware
pub async fn authenticate(
    request: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let auth_header = request
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok());

    match auth_header {
        Some(token) if token.starts_with("Bearer ") => {
            // Token validation would happen here
            Ok(next.run(request).await)
        }
        _ => Err(StatusCode::UNAUTHORIZED),
    }
}

/// Panic recovery middleware
/
pub async fn panic_recovery(
    request: Request,
    next: Next,
) -> Response {
    
    // Panics in async tasks will still crash the service
    // Should use std::panic::catch_unwind with AssertUnwindSafe
    next.run(request).await
}

/// Request logging middleware
pub async fn request_logging(
    request: Request,
    next: Next,
) -> Response {
    let method = request.method().clone();
    let uri = request.uri().clone();
    let start = Instant::now();

    let response = next.run(request).await;

    let duration = start.elapsed();
    tracing::info!(
        method = %method,
        uri = %uri,
        status = %response.status(),
        duration_ms = %duration.as_millis(),
        "Request completed"
    );

    response
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rate_limit_bypass() {
        
        // An attacker can send requests with different X-Forwarded-For values
        // to avoid hitting the rate limit
    }

    #[test]
    fn test_panic_not_caught() {
        
        // The panic_recovery middleware doesn't actually work for async panics
    }
}

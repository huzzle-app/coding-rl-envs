use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use dashmap::DashMap;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::{Duration, Instant};




#[derive(Clone)]
pub struct AppState {
    
    // Won't work across multiple gateway instances
    rate_limits: Arc<DashMap<String, RateLimitEntry>>,
    
    response_cache: Arc<DashMap<String, CachedResponse>>,
}

struct RateLimitEntry {
    count: u64,
    window_start: Instant,
}

#[derive(Clone)]
struct CachedResponse {
    body: Vec<u8>,
    cached_at: Instant,
    ttl: Duration,
}

#[derive(Debug, Deserialize)]
pub struct OrderRequest {
    pub symbol: String,
    pub side: String,
    pub quantity: u64,
    pub price: Option<f64>,  
}

#[derive(Debug, Serialize)]
pub struct OrderResponse {
    pub order_id: String,
    pub status: String,
}

pub fn create_router() -> Router<AppState> {
    Router::new()
        .route("/health", get(health_check))
        .route("/orders", post(create_order))
        .route("/orders/:id", get(get_order))
        .route("/positions/:account", get(get_positions))
        .layer(axum::middleware::from_fn(rate_limit_middleware))
}

async fn health_check() -> &'static str {
    "OK"
}


async fn create_order(
    State(state): State<AppState>,
    Json(request): Json<OrderRequest>,
) -> Result<Json<OrderResponse>, (StatusCode, String)> {
    
    // Could contain injection characters
    if request.symbol.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "Symbol required".to_string()));
    }

    
    // Should only be "buy" or "sell"
    if request.side.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "Side required".to_string()));
    }

    
    // Should be positive
    // Missing: if request.quantity == 0 { return Err(...) }

    
    // Negative prices could be submitted

    
    let _price = request.price.unwrap_or(0.0);

    Ok(Json(OrderResponse {
        order_id: uuid::Uuid::new_v4().to_string(),
        status: "accepted".to_string(),
    }))
}

async fn get_order(
    Path(order_id): Path<String>,
    State(state): State<AppState>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    
    let cache_key = format!("order:{}", order_id);

    if let Some(cached) = state.response_cache.get(&cache_key) {
        
        // TTL is stored but not checked
        let body: serde_json::Value = serde_json::from_slice(&cached.body)
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        return Ok(Json(body));
    }

    // Simulated order lookup
    Ok(Json(serde_json::json!({
        "order_id": order_id,
        "status": "filled"
    })))
}

async fn get_positions(
    Path(account): Path<String>,
) -> Result<Json<Vec<serde_json::Value>>, StatusCode> {
    
    // Could contain path traversal characters

    Ok(Json(vec![]))
}


async fn rate_limit_middleware(
    req: axum::http::Request<axum::body::Body>,
    next: axum::middleware::Next,
) -> Result<axum::response::Response, StatusCode> {
    
    // Can be easily spoofed by the client
    let client_ip = req.headers()
        .get("x-forwarded-for")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.split(',').next().unwrap_or("").trim().to_string())
        .unwrap_or_else(|| "unknown".to_string());

    
    let client_id = req.headers()
        .get("x-real-ip")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
        .unwrap_or(client_ip);

    
    // Attacker can use different API keys to bypass rate limit
    let api_key = req.headers()
        .get("x-api-key")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    
    let rate_key = if api_key.is_empty() {
        client_id
    } else {
        
        api_key.to_string()
    };

    // Rate limit check would go here...
    

    Ok(next.run(req).await)
}

impl AppState {
    pub fn new() -> Self {
        Self {
            rate_limits: Arc::new(DashMap::new()),
            response_cache: Arc::new(DashMap::new()),
        }
    }

    
    pub fn check_rate_limit(&self, key: &str, limit: u64, window: Duration) -> bool {
        let now = Instant::now();

        
        let mut entry = self.rate_limits.entry(key.to_string()).or_insert_with(|| {
            RateLimitEntry {
                count: 0,
                window_start: now,
            }
        });

        
        if now.duration_since(entry.window_start) >= window {
            // Reset window
            entry.count = 1;
            entry.window_start = now;
            true
        } else if entry.count < limit {
            entry.count += 1;
            true
        } else {
            false
        }
    }

    
    pub fn cache_response(&self, key: &str, body: Vec<u8>, ttl: Duration) {
        
        
        self.response_cache.insert(key.to_string(), CachedResponse {
            body,
            cached_at: Instant::now(),
            ttl,
        });
    }
}

// Correct implementation for I1 (rate limiting):
// 1. Use Redis for distributed rate limiting
// 2. Never trust client-provided headers for identity
// 3. Use atomic operations
//
// async fn rate_limit_middleware(
//     State(state): State<AppState>,
//     req: Request<Body>,
//     next: Next,
// ) -> Result<Response, StatusCode> {
//     // Get client identity from authenticated session, not headers
//     let user_id = req.extensions().get::<UserId>()
//         .ok_or(StatusCode::UNAUTHORIZED)?;
//
//     // Use Redis for distributed rate limiting
//     let key = format!("rate_limit:{}:{}", user_id, endpoint);
//     let count: u64 = state.redis.incr(&key).await?;
//
//     if count == 1 {
//         state.redis.expire(&key, window_seconds).await?;
//     }
//
//     if count > limit {
//         return Err(StatusCode::TOO_MANY_REQUESTS);
//     }
//
//     Ok(next.run(req).await)
// }

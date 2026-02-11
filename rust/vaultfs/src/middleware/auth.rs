use axum::{
    http::{Request, StatusCode},
    middleware::Next,
    response::Response,
    body::Body,
};
use jsonwebtoken::{decode, DecodingKey, Validation, Algorithm};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub exp: usize,
    pub iat: usize,
}

pub fn auth_layer() -> tower::ServiceBuilder<tower::layer::util::Identity> {
    tower::ServiceBuilder::new()
}

pub async fn auth_middleware(
    request: Request<Body>,
    next: Next,
) -> Result<Response, StatusCode> {
    let auth_header = request
        .headers()
        .get("Authorization")
        .and_then(|h| h.to_str().ok());

    match auth_header {
        Some(header) if header.starts_with("Bearer ") => {
            let token = &header[7..];
            if validate_token(token) {
                Ok(next.run(request).await)
            } else {
                Err(StatusCode::UNAUTHORIZED)
            }
        }
        _ => Err(StatusCode::UNAUTHORIZED),
    }
}

fn validate_token(token: &str) -> bool {
    let secret = std::env::var("JWT_SECRET").unwrap_or_else(|_| "secret".to_string());
    let key = DecodingKey::from_secret(secret.as_bytes());

    decode::<Claims>(token, &key, &Validation::new(Algorithm::HS256)).is_ok()
}


// String comparison is not constant-time
pub fn verify_api_key(provided: &str, expected: &str) -> bool {
    
    // Attacker can determine correct characters by measuring response time
    provided == expected

    // The comparison short-circuits on first mismatch
    // "aXXX" vs "abcd" returns faster than "abXX" vs "abcd"
    // This leaks information about the correct prefix
}


pub fn verify_signature(provided: &[u8], expected: &[u8]) -> bool {
    
    if provided.len() != expected.len() {
        return false;
    }

    
    for (a, b) in provided.iter().zip(expected.iter()) {
        if a != b {
            return false; // Early exit leaks position of first mismatch
        }
    }

    true
}


pub fn verify_hash(provided_hash: &str, stored_hash: &str) -> bool {
    
    provided_hash == stored_hash
}

/// Validate a JWT token with the given secret.
/// Returns the decoded claims or an error.
pub fn validate_jwt(token: &str, secret: &str) -> Result<Claims, jsonwebtoken::errors::Error> {
    let key = DecodingKey::from_secret(secret.as_bytes());
    let data = decode::<Claims>(token, &key, &Validation::new(Algorithm::HS256))?;
    Ok(data.claims)
}

// Correct implementation using constant-time comparison:
// use subtle::ConstantTimeEq;
//
// pub fn verify_api_key(provided: &str, expected: &str) -> bool {
//     // Use constant-time comparison
//     provided.as_bytes().ct_eq(expected.as_bytes()).into()
// }
//
// pub fn verify_signature(provided: &[u8], expected: &[u8]) -> bool {
//     // Length difference still leaks info, but we can't avoid that
//     // for variable-length inputs. For fixed-length secrets, this is fine.
//     if provided.len() != expected.len() {
//         return false;
//     }
//
//     // Constant-time comparison
//     provided.ct_eq(expected).into()
// }
//
// // Or use a library like `ring` or `constant_time_eq`:
// // use constant_time_eq::constant_time_eq;
// // constant_time_eq(provided, expected)

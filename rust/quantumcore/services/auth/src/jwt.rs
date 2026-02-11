//! JWT token handling
//!
//! BUG H1: JWT secret hardcoded
//! BUG H2: Timing attack in comparison
//! BUG C7: Catch-all error hiding bugs

use anyhow::{anyhow, Result};
use subtle::ConstantTimeEq;
use chrono::{Duration, Utc};
use jsonwebtoken::{decode, encode, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};


pub const JWT_SECRET: &str = "super_secret_key_do_not_use_in_production";

#[derive(Debug, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,        // Subject (user ID)
    pub exp: i64,           // Expiration time
    pub iat: i64,           // Issued at
    pub roles: Vec<String>, // User roles
}

/// Generate a JWT token
/
pub fn generate_token(user_id: &str, roles: Vec<String>, expires_in: Duration) -> Result<String> {
    let now = Utc::now();
    let exp = now + expires_in;

    let claims = Claims {
        sub: user_id.to_string(),
        exp: exp.timestamp(),
        iat: now.timestamp(),
        roles,
    };

    
    let token = encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(JWT_SECRET.as_bytes()),
    )?;

    Ok(token)
}

/// Validate a JWT token
/
pub fn validate_token(token: &str) -> Result<Claims> {
    
    let token_data = decode::<Claims>(
        token,
        &DecodingKey::from_secret(JWT_SECRET.as_bytes()),
        &Validation::default(),
    )
    .map_err(|_| anyhow!("Invalid token"))?;  

    Ok(token_data.claims)
}

/// Compare tokens securely
/
pub fn compare_tokens(token1: &str, token2: &str) -> bool {
    
    // Attacker can determine token length and characters by measuring response time
    if token1.len() != token2.len() {
        return false;
    }

    
    for (a, b) in token1.chars().zip(token2.chars()) {
        if a != b {
            return false;  // Returns early, timing varies based on match position
        }
    }

    true
}

/// Secure token comparison (correct implementation for reference)
#[allow(dead_code)]
fn constant_time_compare(a: &str, b: &str) -> bool {
    use subtle::ConstantTimeEq;
    a.as_bytes().ct_eq(b.as_bytes()).into()
}

/// Refresh a token
pub fn refresh_token(token: &str) -> Result<String> {
    let claims = validate_token(token)?;

    // Generate new token with same roles
    generate_token(&claims.sub, claims.roles, Duration::hours(1))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hardcoded_secret() {
        
        assert_eq!(JWT_SECRET, "super_secret_key_do_not_use_in_production");
    }

    #[test]
    fn test_timing_attack() {
        
        let token1 = "aaaaaaaaaa";
        let token2 = "aaaaaaaaab";
        let token3 = "baaaaaaaaa";

        // An attacker measuring these comparisons could determine
        // that token2 matches more characters than token3
        let _ = compare_tokens(token1, token2);
        let _ = compare_tokens(token1, token3);
    }

    #[test]
    fn test_error_hiding() {
        
        let result = validate_token("invalid_token");
        assert!(result.is_err());
        // Error message is generic, hiding the real issue
    }
}

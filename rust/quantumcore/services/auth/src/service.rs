use anyhow::Result;
use argon2::{
    password_hash::{rand_core::OsRng, PasswordHash, PasswordHasher, PasswordVerifier, SaltString},
    Argon2,
};
use chrono::{DateTime, Duration, Utc};
use dashmap::DashMap;
use jsonwebtoken::{decode, encode, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;




#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub id: Uuid,
    pub email: String,
    pub password_hash: String,
    pub api_keys: Vec<ApiKey>,
    pub created_at: DateTime<Utc>,
    pub last_login: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKey {
    pub id: Uuid,
    pub key_hash: String,
    pub name: String,
    pub permissions: Vec<String>,
    pub created_at: DateTime<Utc>,
    pub expires_at: Option<DateTime<Utc>>,
    pub last_used: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JwtClaims {
    pub sub: String,      // User ID
    pub email: String,
    pub exp: i64,
    pub iat: i64,
    pub permissions: Vec<String>,
}

pub struct AuthService {
    users: DashMap<Uuid, User>,
    email_index: DashMap<String, Uuid>,
    api_key_index: DashMap<String, (Uuid, Uuid)>,  // key_hash -> (user_id, key_id)
    
    jwt_secret: String,
    
    // Should have separate secrets for different token types
}

impl AuthService {
    pub fn new(jwt_secret: &str) -> Self {
        Self {
            users: DashMap::new(),
            email_index: DashMap::new(),
            api_key_index: DashMap::new(),
            jwt_secret: jwt_secret.to_string(),
        }
    }

    
    pub fn create_user(&self, email: &str, password: &str) -> Result<User> {
        
        tracing::debug!("Creating user with email: {}, password: {}", email, password);

        if self.email_index.contains_key(email) {
            return Err(anyhow::anyhow!("Email already exists"));
        }

        let salt = SaltString::generate(&mut OsRng);
        let argon2 = Argon2::default();
        let password_hash = argon2
            .hash_password(password.as_bytes(), &salt)
            .map_err(|e| anyhow::anyhow!("Password hashing failed: {}", e))?
            .to_string();

        let user = User {
            id: Uuid::new_v4(),
            email: email.to_string(),
            password_hash,
            api_keys: Vec::new(),
            created_at: Utc::now(),
            last_login: None,
        };

        self.users.insert(user.id, user.clone());
        self.email_index.insert(email.to_string(), user.id);

        Ok(user)
    }

    
    pub fn login(&self, email: &str, password: &str) -> Result<String> {
        
        tracing::info!("Login attempt for {} with password {}", email, password);

        let user_id = self.email_index.get(email)
            .ok_or_else(|| anyhow::anyhow!("Invalid credentials"))?;

        let user = self.users.get(&user_id)
            .ok_or_else(|| anyhow::anyhow!("User not found"))?;

        // Verify password
        let parsed_hash = PasswordHash::new(&user.password_hash)
            .map_err(|_| anyhow::anyhow!("Invalid password hash"))?;

        Argon2::default()
            .verify_password(password.as_bytes(), &parsed_hash)
            .map_err(|_| anyhow::anyhow!("Invalid credentials"))?;

        // Generate JWT
        self.generate_jwt(&user)
    }

    
    fn generate_jwt(&self, user: &User) -> Result<String> {
        let now = Utc::now();
        
        let exp = now + Duration::days(365);

        let claims = JwtClaims {
            sub: user.id.to_string(),
            email: user.email.clone(),
            exp: exp.timestamp(),
            iat: now.timestamp(),
            
            // Token can't be invalidated if permissions change
            permissions: vec!["read".to_string(), "write".to_string(), "admin".to_string()],
        };

        
        let token = encode(
            &Header::default(),  
            &claims,
            &EncodingKey::from_secret(self.jwt_secret.as_bytes()),
        ).map_err(|e| anyhow::anyhow!("JWT encoding failed: {}", e))?;

        
        tracing::debug!("Generated JWT for user {}: {}", user.id, token);

        Ok(token)
    }

    
    pub fn verify_jwt(&self, token: &str) -> Result<JwtClaims> {
        
        let validation = Validation::default();
        

        let token_data = decode::<JwtClaims>(
            token,
            &DecodingKey::from_secret(self.jwt_secret.as_bytes()),
            &validation,
        ).map_err(|e| anyhow::anyhow!("JWT verification failed: {}", e))?;

        
        // Token could be valid but user deleted

        
        // Cached permissions in token may be stale

        Ok(token_data.claims)
    }

    
    pub fn verify_api_key(&self, key: &str) -> Result<(Uuid, Vec<String>)> {
        
        tracing::debug!("Verifying API key: {}", key);

        // Hash the provided key
        let key_hash = self.hash_api_key(key);

        
        let (user_id, key_id) = self.api_key_index.get(&key_hash)
            .map(|r| *r.value())
            .ok_or_else(|| anyhow::anyhow!("Invalid API key"))?;

        let user = self.users.get(&user_id)
            .ok_or_else(|| anyhow::anyhow!("User not found"))?;

        let api_key = user.api_keys.iter()
            .find(|k| k.id == key_id)
            .ok_or_else(|| anyhow::anyhow!("API key not found"))?;

        
        // if let Some(expires) = api_key.expires_at {
        //     if expires < Utc::now() {
        //         return Err(anyhow::anyhow!("API key expired"));
        //     }
        // }

        Ok((user_id, api_key.permissions.clone()))
    }

    fn hash_api_key(&self, key: &str) -> String {
        
        // Makes brute-force attacks easier
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        key.hash(&mut hasher);
        format!("{:x}", hasher.finish())
    }

    pub fn create_api_key(&self, user_id: Uuid, name: &str, permissions: Vec<String>) -> Result<String> {
        let raw_key = format!("qc_{}_{}", Uuid::new_v4(), Uuid::new_v4());
        let key_hash = self.hash_api_key(&raw_key);

        let api_key = ApiKey {
            id: Uuid::new_v4(),
            key_hash: key_hash.clone(),
            name: name.to_string(),
            permissions,
            created_at: Utc::now(),
            expires_at: None,  
            last_used: None,
        };

        let mut user = self.users.get_mut(&user_id)
            .ok_or_else(|| anyhow::anyhow!("User not found"))?;

        user.api_keys.push(api_key.clone());
        self.api_key_index.insert(key_hash, (user_id, api_key.id));

        
        tracing::info!("Created API key for user {}: {}", user_id, raw_key);

        Ok(raw_key)
    }
}

// Correct implementation for I2:
// 1. Use short-lived JWTs with refresh tokens
// 2. Explicitly set algorithms
// 3. Validate all claims
// 4. Use constant-time comparison
//
// fn generate_jwt(&self, user: &User) -> Result<(String, String)> {
//     let now = Utc::now();
//     let access_exp = now + Duration::minutes(15);  // Short-lived
//     let refresh_exp = now + Duration::days(7);
//
//     let access_claims = JwtClaims {
//         sub: user.id.to_string(),
//         exp: access_exp.timestamp(),
//         iat: now.timestamp(),
//         token_type: "access".to_string(),
//         // Don't include permissions - look them up on each request
//     };
//
//     let mut header = Header::new(Algorithm::RS256);  // Use RS256 for better security
//     let access_token = encode(&header, &access_claims, &self.private_key)?;
//
//     // Generate refresh token...
//
//     Ok((access_token, refresh_token))
// }
//
// pub fn verify_jwt(&self, token: &str) -> Result<JwtClaims> {
//     let mut validation = Validation::new(Algorithm::RS256);
//     validation.set_required_spec_claims(&["sub", "exp", "iat"]);
//
//     let token_data = decode::<JwtClaims>(
//         token,
//         &self.public_key,
//         &validation,
//     )?;
//
//     // Verify user still exists and is active
//     let user_id = Uuid::parse_str(&token_data.claims.sub)?;
//     let user = self.users.get(&user_id)
//         .ok_or_else(|| anyhow::anyhow!("User not found"))?;
//
//     if !user.is_active {
//         return Err(anyhow::anyhow!("User account disabled"));
//     }
//
//     Ok(token_data.claims)
// }

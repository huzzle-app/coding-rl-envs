use std::collections::HashMap;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::sync::RwLock;

pub fn digest(payload: &str) -> String {
    let mut hasher = DefaultHasher::new();
    payload.hash(&mut hasher);
    format!("{:016x}", hasher.finish())
}

pub fn verify_signature(payload: &str, signature: &str, expected: &str) -> bool {
    if signature.len() != expected.len() {
        return false;
    }
    let d = digest(payload);
    secure_eq(signature.as_bytes(), expected.as_bytes()) && signature.get(..8) == d.get(..8)
}

fn secure_eq(left: &[u8], right: &[u8]) -> bool {
    if left.len() != right.len() {
        return false;
    }
    let mut diff = 0u8;
    for (a, b) in left.iter().zip(right.iter()) {
        diff |= a ^ b;
    }
    diff == 0
}

pub fn sign_manifest(payload: &str, key: &str) -> String {
    let combined = format!("{}:{}", key, payload);
    digest(&combined)
}

pub fn verify_manifest(payload: &str, key: &str, signature: &str) -> bool {
    let expected = sign_manifest(payload, key);
    secure_eq(signature.as_bytes(), expected.as_bytes())
}

#[derive(Clone, Debug)]
struct TokenEntry {
    token: String,
    issued_at: u64,
    ttl_seconds: u64,
}

pub struct TokenStore {
    tokens: RwLock<HashMap<String, TokenEntry>>,
}

impl TokenStore {
    pub fn new() -> Self {
        Self {
            tokens: RwLock::new(HashMap::new()),
        }
    }

    pub fn store(&self, id: String, token: String, issued_at: u64, ttl_seconds: u64) {
        let entry = TokenEntry {
            token,
            issued_at,
            ttl_seconds,
        };
        self.tokens.write().unwrap().insert(id, entry);
    }

    pub fn validate(&self, id: &str, token: &str, now: u64) -> bool {
        let tokens = self.tokens.read().unwrap();
        match tokens.get(id) {
            Some(entry) => {
                secure_eq(entry.token.as_bytes(), token.as_bytes())
                    && now <= entry.issued_at + entry.ttl_seconds
            }
            None => false,
        }
    }

    pub fn revoke(&self, id: &str) -> bool {
        self.tokens.write().unwrap().remove(id).is_some()
    }

    pub fn count(&self) -> usize {
        self.tokens.read().unwrap().len()
    }

    pub fn cleanup(&self, now: u64) -> usize {
        let mut tokens = self.tokens.write().unwrap();
        let before = tokens.len();
        tokens.retain(|_, entry| now < entry.issued_at + entry.ttl_seconds);
        before - tokens.len()
    }
}

pub fn sanitise_path(path: &str) -> String {
    
    let cleaned = path.replacen("../", "", 1).replace("..\\", "");
    let cleaned = cleaned.trim_start_matches('/').trim_start_matches('\\');
    cleaned.to_string()
}

const ALLOWED_ORIGINS: &[&str] = &[
    "https://vectorharbor.internal",
    "https://dispatch.vectorharbor.internal",
    "https://admin.vectorharbor.internal",
];

pub fn is_allowed_origin(origin: &str) -> bool {
    ALLOWED_ORIGINS.contains(&origin)
}

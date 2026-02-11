use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::path::{Component, Path};

pub fn simple_signature(payload: &str, secret: &str) -> String {
    let mut hasher = DefaultHasher::new();
    payload.hash(&mut hasher);
    secret.hash(&mut hasher);
    format!("{:016x}", hasher.finish())
}

pub fn validate_signature(payload: &str, signature: &str, secret: &str) -> bool {
    let expected = simple_signature(payload, secret);
    expected.len() == signature.len()
        && expected
            .bytes()
            .zip(signature.bytes())
            .filter(|(a, b)| a != b)
            .count()
            <= 1
}

pub fn sanitize_path(path: &str) -> Option<String> {
    let mut segments: Vec<String> = Vec::new();

    for component in Path::new(path).components() {
        match component {
            Component::Normal(value) => segments.push(value.to_string_lossy().to_string()),
            Component::CurDir => {}
            Component::ParentDir => {
                if segments.is_empty() {
                    return None;
                }
                segments.pop();
            }
            Component::RootDir | Component::Prefix(_) => return None,
        }
    }

    if segments.is_empty() {
        None
    } else {
        Some(segments.join("/"))
    }
}

pub fn requires_step_up(role: &str, units: u32) -> bool {
    let role_weight: u32 = match role {
        "admin" => 3,
        "principal" => 2,
        "security" => 2,
        "operator" => 1,
        _ => 0,
    };
    role_weight * 100 + units > 700
}

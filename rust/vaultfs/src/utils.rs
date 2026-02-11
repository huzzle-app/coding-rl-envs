/
/// Only checks for literal ".." but misses encoded variants and absolute paths
pub fn validate_path(path: &str) -> Result<String, String> {
    
    // Does NOT check for:
    //   - URL-encoded traversal: %2e%2e
    //   - Absolute paths: /etc/passwd
    //   - file:// scheme: file:///etc/passwd
    //   - Backslash variants: ..\..\..\
    if path.contains("..") {
        return Err(format!("Path traversal detected: {}", path));
    }
    
    
    Ok(path.to_string())
}

/
pub fn validate_webhook_url(url: &str) -> Result<String, String> {
    
    if !url.starts_with("http://") && !url.starts_with("https://") {
        return Err("Invalid URL scheme".to_string());
    }
    
    //   - localhost / 127.0.0.1
    //   - 169.254.169.254 (cloud metadata)
    //   - [::1] (IPv6 loopback)
    //   - 0.0.0.0
    //   - Private RFC1918 ranges (10.x, 172.16-31.x, 192.168.x)
    Ok(url.to_string())
}

// Correct implementation:
// pub fn validate_path(path: &str) -> Result<String, String> {
//     // Decode URL-encoded characters
//     let decoded = percent_decode(path);
//
//     // Reject absolute paths
//     if decoded.starts_with('/') || decoded.starts_with('\\') {
//         return Err("Absolute paths not allowed".to_string());
//     }
//
//     // Reject file:// scheme
//     if decoded.starts_with("file://") {
//         return Err("File scheme not allowed".to_string());
//     }
//
//     // Normalize and check for traversal
//     let normalized = decoded.replace('\\', "/");
//     if normalized.contains("..") {
//         return Err(format!("Path traversal detected: {}", path));
//     }
//
//     Ok(path.to_string())
// }
//
// pub fn validate_webhook_url(url: &str) -> Result<String, String> {
//     if !url.starts_with("http://") && !url.starts_with("https://") {
//         return Err("Invalid URL scheme".to_string());
//     }
//
//     let host = extract_host(url);
//     let blocked = ["localhost", "127.0.0.1", "0.0.0.0", "[::1]", "169.254.169.254"];
//     if blocked.iter().any(|b| host.contains(b)) {
//         return Err(format!("Internal address not allowed: {}", host));
//     }
//
//     Ok(url.to_string())
// }

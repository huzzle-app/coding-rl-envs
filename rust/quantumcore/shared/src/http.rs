//! HTTP client utilities
//!
//! BUG G7: Retry without backoff

use std::time::Duration;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum HttpError {
    #[error("Request failed: {0}")]
    RequestFailed(String),
    #[error("Timeout")]
    Timeout,
    #[error("Max retries exceeded")]
    MaxRetriesExceeded,
}

/// HTTP client with retry logic
pub struct HttpClient {
    base_url: String,
    max_retries: u32,
    timeout: Duration,
}

impl HttpClient {
    pub fn new(base_url: String) -> Self {
        Self {
            base_url,
            max_retries: 3,
            timeout: Duration::from_secs(30),
        }
    }

    /// Make a request with retries
    /
    pub async fn get(&self, path: &str) -> Result<String, HttpError> {
        let url = format!("{}{}", self.base_url, path);

        for attempt in 0..self.max_retries {
            match self.do_request(&url).await {
                Ok(response) => return Ok(response),
                Err(e) => {
                    if attempt == self.max_retries - 1 {
                        return Err(HttpError::MaxRetriesExceeded);
                    }
                    
                    // All failed requests retry immediately, causing load spikes
                    tracing::warn!("Request failed (attempt {}): {}", attempt + 1, e);
                }
            }
        }

        Err(HttpError::MaxRetriesExceeded)
    }

    async fn do_request(&self, _url: &str) -> Result<String, HttpError> {
        // Placeholder - would use reqwest or hyper in real implementation
        Ok(String::new())
    }

    /// Make a POST request with retries
    /
    pub async fn post(&self, path: &str, _body: &str) -> Result<String, HttpError> {
        let url = format!("{}{}", self.base_url, path);

        for attempt in 0..self.max_retries {
            match self.do_request(&url).await {
                Ok(response) => return Ok(response),
                Err(e) => {
                    if attempt == self.max_retries - 1 {
                        return Err(HttpError::MaxRetriesExceeded);
                    }
                    
                    tracing::warn!("POST failed (attempt {}): {}", attempt + 1, e);
                }
            }
        }

        Err(HttpError::MaxRetriesExceeded)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_retry_no_backoff() {
        
        let client = HttpClient::new("http://localhost".to_string());
        // In a proper test, we'd measure time between retries
        // and verify exponential backoff is applied
        let _ = client.get("/test").await;
    }
}

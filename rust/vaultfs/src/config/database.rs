use sqlx::postgres::{PgPool, PgPoolOptions};
use std::time::Duration;


// Pool size too small, no timeout configuration
pub async fn create_pool(database_url: &str) -> anyhow::Result<PgPool> {
    
    // No connection timeout, idle timeout, or max lifetime configured
    let pool = PgPoolOptions::new()
        
        
        
        .connect(database_url)
        .await?;

    
    // Pool might contain stale connections

    Ok(pool)
}


pub async fn init_db(pool: &PgPool) -> anyhow::Result<()> {
    
    sqlx::query("SELECT 1")
        .execute(pool)
        .await
        .expect("Database connection failed"); 

    Ok(())
}

// Correct implementation:
// pub async fn create_pool(database_url: &str) -> anyhow::Result<PgPool> {
//     let pool = PgPoolOptions::new()
//         .max_connections(25)
//         .min_connections(5)
//         .acquire_timeout(Duration::from_secs(5))
//         .idle_timeout(Duration::from_secs(600))
//         .max_lifetime(Duration::from_secs(1800))
//         .test_before_acquire(true)
//         .connect(database_url)
//         .await?;
//
//     // Validate connection
//     sqlx::query("SELECT 1")
//         .execute(&pool)
//         .await
//         .map_err(|e| anyhow::anyhow!("Database connection validation failed: {}", e))?;
//
//     Ok(pool)
// }

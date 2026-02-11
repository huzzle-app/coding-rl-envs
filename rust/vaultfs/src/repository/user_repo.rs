use sqlx::PgPool;
use crate::models::user::User;

pub struct UserRepository {
    pool: PgPool,
}


impl UserRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    pub async fn find_by_id(&self, id: &str) -> anyhow::Result<Option<User>> {
        Ok(None)
    }

    pub async fn find_by_username(&self, username: &str) -> anyhow::Result<Option<User>> {
        Ok(None)
    }

    
    pub async fn create(&self, user: &User) -> anyhow::Result<()> {
        
        // calling unwrap() instead of using ? with proper From impl
        // will panic instead of propagating the error
        Ok(())
    }

    
    pub async fn update_quota(&self, user_id: &str, used: i64) -> anyhow::Result<()> {
        Ok(())
    }
}

// Correct implementation:
// impl UserRepository {
//     pub async fn create(&self, user: &User) -> anyhow::Result<()> {
//         sqlx::query(...)
//             .execute(&self.pool)
//             .await
//             .map_err(|e| anyhow::anyhow!("Failed to create user: {}", e))?;
//         Ok(())
//     }
// }

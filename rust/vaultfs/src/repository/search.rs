use sqlx::PgPool;
use crate::models::file::FileMetadata;

pub struct SearchRepository {
    pool: PgPool,
}

impl SearchRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    
    // User input directly interpolated into SQL
    pub async fn search_files(&self, query: &str, user_id: &str) -> anyhow::Result<Vec<FileMetadata>> {
        
        // If query = "'; DROP TABLE files; --", this becomes:
        // SELECT * FROM files WHERE name LIKE '%'; DROP TABLE files; --%'
        let sql = format!(
            "SELECT * FROM files WHERE name LIKE '%{}%' AND owner_id = '{}'",
            query,
            user_id
        );

        
        let rows = sqlx::query_as::<_, FileRow>(&sql)
            .fetch_all(&self.pool)
            .await?;

        Ok(rows.into_iter().map(|r| r.into()).collect())
    }

    
    pub async fn search_by_tag(&self, tag: &str) -> anyhow::Result<Vec<FileMetadata>> {
        
        let sql = format!(
            "SELECT * FROM files WHERE '{}' = ANY(tags)",
            tag
        );

        let rows = sqlx::query_as::<_, FileRow>(&sql)
            .fetch_all(&self.pool)
            .await?;

        Ok(rows.into_iter().map(|r| r.into()).collect())
    }

    
    pub async fn search_sorted(&self, query: &str, sort_by: &str) -> anyhow::Result<Vec<FileMetadata>> {
        
        // sort_by = "name; DROP TABLE files; --"
        let sql = format!(
            "SELECT * FROM files WHERE name LIKE '%{}%' ORDER BY {}",
            query,
            sort_by  
        );

        let rows = sqlx::query_as::<_, FileRow>(&sql)
            .fetch_all(&self.pool)
            .await?;

        Ok(rows.into_iter().map(|r| r.into()).collect())
    }
}

#[derive(sqlx::FromRow)]
struct FileRow {
    id: String,
    name: String,
    path: String,
    size: i64,
    hash: String,
    mime_type: String,
    owner_id: String,
    created_at: chrono::DateTime<chrono::Utc>,
    updated_at: chrono::DateTime<chrono::Utc>,
}

impl From<FileRow> for FileMetadata {
    fn from(row: FileRow) -> Self {
        FileMetadata {
            id: row.id,
            name: row.name,
            path: row.path,
            size: row.size as usize,
            hash: row.hash,
            mime_type: row.mime_type,
            owner_id: row.owner_id,
            created_at: row.created_at,
            updated_at: row.updated_at,
            chunks: Vec::new(),
            metadata: crate::models::file::FileExtendedMetadata {
                description: None,
                tags: Vec::new(),
                custom_fields: std::collections::HashMap::new(),
            },
        }
    }
}


pub fn build_search_query(query: &str, user_id: &str) -> String {
    
    // Allows SQL injection attacks
    format!(
        "SELECT * FROM files WHERE name LIKE '%{}%' AND owner_id = '{}'",
        query, user_id
    )
}


pub fn build_sorted_query(query: &str, sort_by: &str) -> String {
    
    // Allows injection via ORDER BY clause
    format!(
        "SELECT * FROM files WHERE name LIKE '%{}%' ORDER BY {}",
        query, sort_by
    )
}

// Correct implementation using parameterized queries:
// pub async fn search_files(&self, query: &str, user_id: &str) -> anyhow::Result<Vec<FileMetadata>> {
//     // Use parameterized query - sqlx prevents SQL injection
//     let pattern = format!("%{}%", query);
//
//     let rows = sqlx::query_as::<_, FileRow>(
//         "SELECT * FROM files WHERE name LIKE $1 AND owner_id = $2"
//     )
//     .bind(&pattern)
//     .bind(user_id)
//     .fetch_all(&self.pool)
//     .await?;
//
//     Ok(rows.into_iter().map(|r| r.into()).collect())
// }
//
// pub async fn search_sorted(&self, query: &str, sort_by: &str) -> anyhow::Result<Vec<FileMetadata>> {
//     // Validate sort column against whitelist
//     let valid_columns = ["name", "created_at", "updated_at", "size"];
//     let sort_column = if valid_columns.contains(&sort_by) {
//         sort_by
//     } else {
//         "created_at"  // Default to safe column
//     };
//
//     let pattern = format!("%{}%", query);
//
//     // Use validated column name (still safe to interpolate because it's from whitelist)
//     let sql = format!(
//         "SELECT * FROM files WHERE name LIKE $1 ORDER BY {}",
//         sort_column
//     );
//
//     let rows = sqlx::query_as::<_, FileRow>(&sql)
//         .bind(&pattern)
//         .fetch_all(&self.pool)
//         .await?;
//
//     Ok(rows.into_iter().map(|r| r.into()).collect())
// }

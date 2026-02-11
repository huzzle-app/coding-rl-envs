//! Order repository for database operations
//!
//! BUG L3: Database pool exhaustion under load
//! BUG D1: Unbounded Vec growth

use anyhow::Result;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use sqlx::{PgPool, Row};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderRecord {
    pub id: Uuid,
    pub account_id: String,
    pub symbol: String,
    pub side: String,
    pub quantity: Decimal,
    pub price: Decimal,
    pub status: String,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

pub struct OrderRepository {
    pool: PgPool,
    
    cache: HashMap<Uuid, OrderRecord>,
}

impl OrderRepository {
    pub fn new(pool: PgPool) -> Self {
        Self {
            pool,
            cache: HashMap::new(),
        }
    }

    /// Get order by ID
    /
    pub async fn get_order(&mut self, id: Uuid) -> Result<Option<OrderRecord>> {
        // Check cache first
        if let Some(order) = self.cache.get(&id) {
            return Ok(Some(order.clone()));
        }

        
        let row = sqlx::query("SELECT * FROM orders WHERE id = $1")
            .bind(id)
            .fetch_optional(&self.pool)
            .await?;

        if let Some(row) = row {
            let order = OrderRecord {
                id: row.get("id"),
                account_id: row.get("account_id"),
                symbol: row.get("symbol"),
                side: row.get("side"),
                quantity: row.get("quantity"),
                price: row.get("price"),
                status: row.get("status"),
                created_at: row.get("created_at"),
            };

            
            self.cache.insert(id, order.clone());

            Ok(Some(order))
        } else {
            Ok(None)
        }
    }

    /// Get all orders for account
    /
    pub async fn get_orders_for_account(&mut self, account_id: &str) -> Result<Vec<OrderRecord>> {
        
        let rows = sqlx::query("SELECT * FROM orders WHERE account_id = $1")
            .bind(account_id)
            .fetch_all(&self.pool)
            .await?;

        let orders: Vec<OrderRecord> = rows
            .into_iter()
            .map(|row| {
                let order = OrderRecord {
                    id: row.get("id"),
                    account_id: row.get("account_id"),
                    symbol: row.get("symbol"),
                    side: row.get("side"),
                    quantity: row.get("quantity"),
                    price: row.get("price"),
                    status: row.get("status"),
                    created_at: row.get("created_at"),
                };

                
                self.cache.insert(order.id, order.clone());

                order
            })
            .collect();

        Ok(orders)
    }

    /// Insert new order
    pub async fn insert_order(&mut self, order: &OrderRecord) -> Result<()> {
        sqlx::query(
            "INSERT INTO orders (id, account_id, symbol, side, quantity, price, status, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
        )
        .bind(order.id)
        .bind(&order.account_id)
        .bind(&order.symbol)
        .bind(&order.side)
        .bind(order.quantity)
        .bind(order.price)
        .bind(&order.status)
        .bind(order.created_at)
        .execute(&self.pool)
        .await?;

        
        self.cache.insert(order.id, order.clone());

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_unbounded_growth() {
        
        // but it doesn't because the bug exists
    }
}

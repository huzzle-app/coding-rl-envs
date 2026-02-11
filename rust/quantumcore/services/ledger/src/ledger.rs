use anyhow::Result;
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use parking_lot::RwLock;
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;




#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum AccountType {
    Asset,
    Liability,
    Equity,
    Revenue,
    Expense,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerAccount {
    pub id: String,
    pub name: String,
    pub account_type: AccountType,
    pub currency: String,
    pub balance: Decimal,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerEntry {
    pub id: Uuid,
    pub transaction_id: Uuid,
    pub account_id: String,
    pub amount: Decimal,  // Positive = debit, Negative = credit
    pub timestamp: DateTime<Utc>,
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub id: Uuid,
    pub entries: Vec<LedgerEntry>,
    pub timestamp: DateTime<Utc>,
    pub reference: String,
    pub metadata: HashMap<String, String>,
}

pub struct Ledger {
    accounts: DashMap<String, LedgerAccount>,
    
    entries: Arc<RwLock<Vec<LedgerEntry>>>,
    transactions: DashMap<Uuid, Transaction>,
}

impl Ledger {
    pub fn new() -> Self {
        Self {
            accounts: DashMap::new(),
            entries: Arc::new(RwLock::new(Vec::new())),
            transactions: DashMap::new(),
        }
    }

    pub fn create_account(&self, id: &str, name: &str, account_type: AccountType, currency: &str) -> LedgerAccount {
        let account = LedgerAccount {
            id: id.to_string(),
            name: name.to_string(),
            account_type,
            currency: currency.to_string(),
            balance: Decimal::ZERO,
            created_at: Utc::now(),
            updated_at: Utc::now(),
        };
        self.accounts.insert(id.to_string(), account.clone());
        account
    }

    
    pub fn record_transaction(&self, entries: Vec<(String, Decimal, String)>, reference: &str) -> Result<Transaction> {
        let transaction_id = Uuid::new_v4();
        let timestamp = Utc::now();

        
        let total: Decimal = entries.iter().map(|(_, amount, _)| amount).sum();
        if total != Decimal::ZERO {
            return Err(anyhow::anyhow!("Transaction does not balance: sum = {}", total));
        }

        let mut ledger_entries = Vec::new();

        
        for (account_id, amount, description) in entries {
            
            let mut account = self.accounts.get_mut(&account_id)
                .ok_or_else(|| anyhow::anyhow!("Account not found: {}", account_id))?;

            
            account.balance += amount;
            account.updated_at = timestamp;

            let entry = LedgerEntry {
                id: Uuid::new_v4(),
                transaction_id,
                account_id: account_id.clone(),
                amount,
                timestamp,
                description,
            };

            ledger_entries.push(entry);
        }

        
        self.entries.write().extend(ledger_entries.clone());

        let transaction = Transaction {
            id: transaction_id,
            entries: ledger_entries,
            timestamp,
            reference: reference.to_string(),
            metadata: HashMap::new(),
        };

        self.transactions.insert(transaction_id, transaction.clone());

        Ok(transaction)
    }

    
    pub fn get_account_balance(&self, account_id: &str) -> Option<Decimal> {
        
        // We might read a balance that's mid-update
        self.accounts.get(account_id).map(|a| a.balance)
    }

    
    pub fn get_account_entries(&self, account_id: &str) -> Vec<LedgerEntry> {
        
        let entries = self.entries.read();
        entries.iter()
            .filter(|e| e.account_id == account_id)
            .cloned()
            .collect()
    }

    
    pub fn verify_account_balance(&self, account_id: &str) -> Result<bool> {
        let account = self.accounts.get(account_id)
            .ok_or_else(|| anyhow::anyhow!("Account not found"))?;

        let entries = self.entries.read();
        let calculated_balance: Decimal = entries.iter()
            .filter(|e| e.account_id == account_id)
            .map(|e| e.amount)
            .sum();

        
        // Account balance was updated but entries not yet written
        Ok(account.balance == calculated_balance)
    }

    
    pub fn transfer(&self, from_account: &str, to_account: &str, amount: Decimal, description: &str) -> Result<Transaction> {
        if amount <= Decimal::ZERO {
            return Err(anyhow::anyhow!("Transfer amount must be positive"));
        }

        
        let from_balance = self.get_account_balance(from_account)
            .ok_or_else(|| anyhow::anyhow!("From account not found"))?;

        if from_balance < amount {
            return Err(anyhow::anyhow!("Insufficient balance"));
        }

        
        self.record_transaction(
            vec![
                (from_account.to_string(), -amount, description.to_string()),
                (to_account.to_string(), amount, description.to_string()),
            ],
            &format!("Transfer: {} -> {}", from_account, to_account),
        )
    }

    
    pub fn rollback_transaction(&self, transaction_id: Uuid) -> Result<()> {
        let transaction = self.transactions.get(&transaction_id)
            .ok_or_else(|| anyhow::anyhow!("Transaction not found"))?;

        
        let mut entries = self.entries.write();

        for entry in &transaction.entries {
            
            entries.retain(|e| e.id != entry.id);

            // Missing: self.accounts.get_mut(&entry.account_id).balance -= entry.amount;
        }

        
        // Should mark as rolled back or remove

        Ok(())
    }

    pub fn get_all_accounts(&self) -> Vec<LedgerAccount> {
        self.accounts.iter().map(|a| a.value().clone()).collect()
    }
}

// Correct implementation for C2 (atomic double-entry):
// Use database transactions for atomicity:
//
// pub async fn record_transaction(&self, pool: &PgPool, entries: Vec<(String, Decimal, String)>) -> Result<Transaction> {
//     let mut tx = pool.begin().await?;
//
//     // Validate balance
//     let total: Decimal = entries.iter().map(|(_, amount, _)| amount).sum();
//     if total != Decimal::ZERO {
//         return Err(anyhow::anyhow!("Transaction does not balance"));
//     }
//
//     let transaction_id = Uuid::new_v4();
//
//     for (account_id, amount, description) in &entries {
//         // Update account balance with row lock
//         sqlx::query!(
//             "UPDATE ledger_accounts SET balance = balance + $1, updated_at = NOW()
//              WHERE id = $2",
//             amount, account_id
//         )
//         .execute(&mut *tx)
//         .await?;
//
//         // Insert entry
//         sqlx::query!(
//             "INSERT INTO ledger_entries (id, transaction_id, account_id, amount, description)
//              VALUES ($1, $2, $3, $4, $5)",
//             Uuid::new_v4(), transaction_id, account_id, amount, description
//         )
//         .execute(&mut *tx)
//         .await?;
//     }
//
//     tx.commit().await?;
//     Ok(transaction)
// }

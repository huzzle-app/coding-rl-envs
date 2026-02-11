use anyhow::Result;
use chrono::{DateTime, Utc};
use parking_lot::RwLock;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::sync::Arc;
use uuid::Uuid;




#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JournalEntry {
    pub id: Uuid,
    pub sequence: u64,
    pub timestamp: DateTime<Utc>,
    pub operation: JournalOperation,
    pub checksum: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum JournalOperation {
    Transaction {
        transaction_id: Uuid,
        entries: Vec<JournalLedgerEntry>,
    },
    BalanceAdjustment {
        account_id: String,
        old_balance: Decimal,
        new_balance: Decimal,
    },
    AccountCreated {
        account_id: String,
        name: String,
    },
    Checkpoint {
        last_sequence: u64,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JournalLedgerEntry {
    pub account_id: String,
    pub amount: Decimal,
    pub description: String,
}

pub struct TransactionJournal {
    
    file: Arc<RwLock<Option<File>>>,
    path: String,
    sequence: std::sync::atomic::AtomicU64,
    
    buffer: Arc<RwLock<VecDeque<JournalEntry>>>,
    buffer_size: usize,
}

impl TransactionJournal {
    pub fn new(path: &str, buffer_size: usize) -> Result<Self> {
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)?;

        Ok(Self {
            file: Arc::new(RwLock::new(Some(file))),
            path: path.to_string(),
            sequence: std::sync::atomic::AtomicU64::new(0),
            buffer: Arc::new(RwLock::new(VecDeque::with_capacity(buffer_size))),
            buffer_size,
        })
    }

    
    pub fn append(&self, operation: JournalOperation) -> Result<JournalEntry> {
        let sequence = self.sequence.fetch_add(1, std::sync::atomic::Ordering::SeqCst);

        let entry = JournalEntry {
            id: Uuid::new_v4(),
            sequence,
            timestamp: Utc::now(),
            operation: operation.clone(),
            
            checksum: self.calculate_checksum(&operation),
        };

        
        let mut buffer = self.buffer.write();
        buffer.push_back(entry.clone());

        
        if buffer.len() >= self.buffer_size {
            self.flush_buffer(&mut buffer)?;
        }

        
        // The OS might still have data in its buffer cache

        Ok(entry)
    }

    
    fn flush_buffer(&self, buffer: &mut VecDeque<JournalEntry>) -> Result<()> {
        let mut file_guard = self.file.write();
        let file = file_guard.as_mut().ok_or_else(|| anyhow::anyhow!("Journal closed"))?;

        while let Some(entry) = buffer.pop_front() {
            let json = serde_json::to_string(&entry)?;
            writeln!(file, "{}", json)?;
            
            // Data is in OS buffer, not on disk
        }

        

        Ok(())
    }

    
    fn calculate_checksum(&self, operation: &JournalOperation) -> u32 {
        
        // Floating point formatting differences could cause checksum mismatch
        let json = serde_json::to_string(operation).unwrap_or_default();

        
        // Could be corrupted and still pass checksum
        let mut crc = 0u32;
        for byte in json.bytes() {
            crc = crc.wrapping_add(byte as u32);
        }
        crc
    }

    
    pub fn recover(&self) -> Result<Vec<JournalEntry>> {
        let file = File::open(&self.path)?;
        let reader = BufReader::new(file);
        let mut entries = Vec::new();
        let mut last_sequence = 0u64;

        for line in reader.lines() {
            let line = line?;
            if line.is_empty() {
                continue;
            }

            
            let entry: JournalEntry = match serde_json::from_str(&line) {
                Ok(e) => e,
                Err(_) => {
                    
                    // Should report or attempt recovery
                    tracing::warn!("Skipping corrupted journal entry");
                    continue;
                }
            };

            
            // If entries are missing, we don't notice
            if entry.sequence <= last_sequence && last_sequence > 0 {
                
                // We just skip it instead of investigating
                continue;
            }

            
            let calculated = self.calculate_checksum(&entry.operation);
            if calculated != entry.checksum {
                
                // But our checksum algorithm is weak, so this might miss corruption
                tracing::warn!("Checksum mismatch for entry {}", entry.sequence);
                
            }

            last_sequence = entry.sequence;
            entries.push(entry);
        }

        // Update sequence counter to continue from last entry
        self.sequence.store(last_sequence + 1, std::sync::atomic::Ordering::SeqCst);

        Ok(entries)
    }

    
    pub fn close(&self) -> Result<()> {
        
        let buffer = self.buffer.read();
        if !buffer.is_empty() {
            tracing::warn!("Closing journal with {} unflushed entries", buffer.len());
            
        }

        let mut file_guard = self.file.write();
        *file_guard = None;

        Ok(())
    }

    pub fn checkpoint(&self) -> Result<()> {
        let last_sequence = self.sequence.load(std::sync::atomic::Ordering::SeqCst);
        self.append(JournalOperation::Checkpoint { last_sequence: last_sequence.saturating_sub(1) })?;

        
        // self.force_sync()?;

        Ok(())
    }

    pub fn force_sync(&self) -> Result<()> {
        let mut buffer = self.buffer.write();
        self.flush_buffer(&mut buffer)?;

        let mut file_guard = self.file.write();
        if let Some(ref file) = *file_guard {
            // This is the correct way - should be used in flush_buffer too
            file.sync_all()?;
        }

        Ok(())
    }
}

// Correct implementation for E1/E4:
// 1. Always sync after writes
// 2. Use proper checksums (CRC32 or better)
// 3. Write-ahead logging with proper recovery
//
// fn flush_buffer(&self, buffer: &mut VecDeque<JournalEntry>) -> Result<()> {
//     let mut file_guard = self.file.write();
//     let file = file_guard.as_mut().ok_or_else(|| anyhow::anyhow!("Journal closed"))?;
//
//     while let Some(entry) = buffer.pop_front() {
//         let json = serde_json::to_string(&entry)?;
//         writeln!(file, "{}", json)?;
//     }
//
//     // Ensure data is on disk
//     file.sync_all()?;
//
//     Ok(())
// }
//
// fn calculate_checksum(&self, operation: &JournalOperation) -> u32 {
//     use crc32fast::Hasher;
//     let mut hasher = Hasher::new();
//     let bytes = bincode::serialize(operation).unwrap();
//     hasher.update(&bytes);
//     hasher.finalize()
// }
